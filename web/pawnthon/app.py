''' Telas do Pawnthon Chess (login, lobby, sala de espera e partida) e a conversa com o servidor.
Toda regra do jogo roda no servidor Python (chess_engine.py); aqui desenhamos o que ele manda
e enviamos as ações do jogador pelo WebSocket. '''

import time

import pygame

import browser
import net
import theme
from board import BoardView
from theme import u
from ui import UI

LINKEDIN = "https://www.linkedin.com/in/kassiobcunha/"
PORTFOLIO = "https://portifolio-web-kassio.vecel.app/"
RELEASES = "https://github.com/KassioB/Online_Chess/releases/latest/download/"
DOWNLOADS = (("dl_windows", "Windows", "PawnthonChess.exe"), ("dl_linux", "Linux", "PawnthonChess-linux.tar.gz"))
TECH = "Xadrez desenvolvido somente com Python"

ROLE_LABEL = {"white": "brancas", "black": "pretas", "spectator": "espectador"}
STATUS_LABEL = {
    "waiting": "Sala de espera",
    "playing": "Em andamento",
    "checkmate": "Xeque-mate",
    "stalemate": "Empate (afogamento)",
    "timeout": "Fim por tempo",
}
ENDED = ("checkmate", "stalemate", "timeout")

TOKEN_KEY = "pawnthon_token"
ROOM_KEY = "pawnthon_room"
RELOAD_KEY = "pawnthon_reload"


def readBuildId():
    try:
        with open(theme.BASE + "/build_id.txt", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


BUILD_ID = readBuildId()


def formatTime(seconds):
    s = max(0, int(-(-seconds // 1)))  # arredonda para cima, como o Math.ceil
    return f"{s // 60}:{s % 60:02d}"


class App:
    def __init__(self, screen, portrait):
        self.screen = screen
        self.W, self.H = screen.get_size()
        self.portrait = portrait
        self.ui = UI(screen)
        self.net = net.Client()
        self.board = BoardView()
        self.running = True

        self.view = "connecting"
        self.me = None
        self.authMode = "login"
        self.authError = ""
        self.authBusy = False
        self.tokenSent = False
        self.wasOnline = False
        self.everOnline = False

        self.rooms = []
        self.lobbyScroll = 0

        self.game = None
        self.leftRoom = None  # sala que acabamos de deixar: ignora atualizações dela que ainda estavam a caminho
        self.clockAt = 0
        self.waitingServer = False
        self.confirmKick = None
        self.promotion = None  # (início, fim) do peão esperando o jogador escolher a peça nova

        self.toastText = None
        self.toastUntil = 0
        self.drawnAt = 0
        self.startedAt = time.time()
        self.redraw = True

    # ---------- utilidades ----------

    def resize(self, screen, portrait):
        # a janela do navegador mudou de tamanho/orientação: refaz as medidas sem perder a partida
        self.screen = screen
        self.W, self.H = screen.get_size()
        self.portrait = portrait
        self.ui.screen = screen
        self.ui.overlay.reset(screen.get_size())
        self.redraw = True

    def toast(self, text):
        self.toastText, self.toastUntil = text, time.time() + 3

    def send(self, data):
        if data["type"] in ("join", "create_room"):
            self.leftRoom = None
        self.net.send(data)

    @property
    def fps(self):
        # menos quadros parado economiza bateria; animação e digitação a 60
        if self.board.animating or self.ui.down:
            return 60
        return 30 if (self.ui.domFocus or self.ui.focus) else 20

    # ---------- mensagens do servidor ----------

    def handle(self, msg):
        kind = msg.get("type")
        if kind == "build":
            # o servidor foi atualizado depois que esta aba abriu: recarrega para baixar o cliente novo
            # (só uma tentativa por versão, para nunca ficar recarregando em loop)
            server = msg.get("id")
            if browser.BROWSER and server and BUILD_ID and server != BUILD_ID                     and browser.storageGet(RELOAD_KEY, session=True) != server:
                browser.storageSet(RELOAD_KEY, server, session=True)
                browser.reload()
        elif kind == "need_login":
            token = browser.storageGet(TOKEN_KEY)
            if token and not self.tokenSent:
                self.tokenSent = True  # tenta voltar com a sessão salva só uma vez por conexão
                self.send({"type": "auth", "token": token})
                return
            if token:
                browser.storageSet(TOKEN_KEY, None)  # sessão expirada
            self.me, self.game = None, None
            self.authBusy = False
            self.view = "auth"
        elif kind == "auth_error":
            self.authError, self.authBusy = msg["message"], False
        elif kind == "hello":
            self.me = msg["username"]
            browser.storageSet(TOKEN_KEY, msg["token"])
            self.authBusy, self.authError = False, ""
            self.ui.setValue("pass", "")
            # depois de recarregar a página volta para a sala em que estava
            saved = browser.storageGet(ROOM_KEY, session=True)
            if saved:
                roomId, role = saved.split(":")
                self.send({"type": "join", "room": int(roomId), "role": role})
            else:
                self.view = "lobby"
        elif kind == "rooms":
            self.rooms = msg["rooms"]
            if self.view != "room":
                self.view = "lobby"
        elif kind == "state":
            self.onState(msg)
        elif kind == "kicked":
            browser.storageSet(ROOM_KEY, None, session=True)
            self.leaveRoomLocally()
            self.toast(f'Você foi removido da sala "{msg["room"]}" pelo dono')
        elif kind == "error":
            self.waitingServer = False
            self.toast(msg["message"])
            if self.view != "room":
                browser.storageSet(ROOM_KEY, None, session=True)
                self.view = "lobby"

    def onState(self, msg):
        if msg["room"]["id"] == self.leftRoom:
            return
        isNewGame = self.game is None or self.game["room"]["id"] != msg["room"]["id"]
        if isNewGame:
            self.board.reset()
        else:
            lastId = (self.game["lastMove"] or {}).get("id")
            moveId = (msg["lastMove"] or {}).get("id")
            if msg.get("inCheck") and moveId is not None and moveId != lastId:
                browser.playCheckSound()
        self.board.onState(msg, isNewGame)
        self.game = msg
        self.clockAt = time.time()
        self.waitingServer = False
        browser.storageSet(ROOM_KEY, f'{msg["room"]["id"]}:{msg["role"]}', session=True)
        self.view = "room"

    def leaveRoomLocally(self):
        if self.game:
            self.leftRoom = self.game["room"]["id"]
        self.game = None
        self.promotion = None
        self.board.reset()
        self.view = "lobby"

    # ---------- estado da partida ----------

    def isPlayer(self):
        return self.game and self.game["role"] in ("white", "black")

    def myTurn(self):
        g = self.game
        return g and g["room"]["status"] == "playing" and g["role"] == ("white" if g["whiteToMove"] else "black")

    def isOwner(self):
        return self.game["room"]["owner"] == self.me

    # ---------- quadro ----------

    def frame(self, events):
        for e in events:
            if e.type == pygame.QUIT:
                self.running = False
        now = time.time()
        messages = self.net.update(now)
        for msg in messages:
            self.handle(msg)
        online = self.net.online
        if online and not self.wasOnline:
            self.tokenSent = False
            self.everOnline = True
        if not online and self.wasOnline:
            self.toast("Conexão perdida, reconectando...")
        changed = online != self.wasOnline
        self.wasOnline = online

        # parado e sem novidade não há o que redesenhar: poupa o computador fraco (o relógio, o
        # cursor piscando e os avisos pedem um quadro a cada 0,25 s; digitar no campo real da
        # página não gera evento no pygame, então enquanto há foco redesenha sempre)
        if not (events or messages or changed or self.board.animating or self.ui.down
                or self.ui.domFocus or self.ui.focus or now - self.drawnAt > 0.25 or self.redraw):
            return False
        self.drawnAt, self.redraw = now, False

        ui = self.ui
        ui.begin(events)
        theme.background(self.screen)
        content = self.drawHeader()
        content = self.drawFooter(content)
        if self.view == "auth":
            self.drawAuth(content)
        elif self.view == "lobby":
            self.drawLobby(content)
        elif self.view == "room" and self.game:
            if self.game["room"]["started"]:
                self.drawGame(content)
            else:
                self.drawWaiting(content)
        else:
            theme.draw(self.screen, "Conectando ao servidor...", content.center, 18, theme.MUTED, anchor="center")
            if not browser.BROWSER and now - self.startedAt > 5:
                # no plano gratuito do Render o servidor dorme e leva até ~1 min para acordar
                theme.draw(self.screen, "O servidor pode estar acordando, isso leva até 1 minuto...",
                           (content.centerx, content.centery + u(34)), 14, theme.MUTED, anchor="center")
        self.drawToast(content)
        ui.end()
        return True

    # ---------- topo e rodapé ----------

    def drawHeader(self):
        s = self.screen
        h = u(64 if self.portrait else 76)
        pygame.draw.rect(s, theme.BLACK, (0, 0, self.W, h))
        pygame.draw.rect(s, theme.RED, (0, h - u(3), self.W, u(3)))
        logo = u(40 if self.portrait else 50)
        x = u(16 if self.portrait else 22)
        s.blit(theme.image("img/logo.png", (logo, logo)), (x, (h - u(3) - logo) // 2))
        size = 19 if self.portrait else 23
        r = theme.draw(s, "Pawnthon", (x + logo + u(12), (h - u(3)) // 2), size, theme.WHITE, "bold", "midleft")
        theme.draw(s, " Chess", (r.right, r.centery), size, theme.RED, "bold", "midleft")
        if self.me:
            label = "Sair" if self.portrait else "Sair da conta"
            w = theme.font(14, "semibold").size(label)[0] + u(8)
            btn = pygame.Rect(self.W - x - w, (h - u(3)) // 2 - u(14), w, u(28))
            if self.ui.button(btn, label, "link", size=14):
                self.send({"type": "logout"})
                browser.storageSet(TOKEN_KEY, None)
                browser.storageSet(ROOM_KEY, None, session=True)
                self.me, self.game, self.view = None, None, "auth"
            if not self.portrait:
                theme.draw(s, self.me, (btn.x - u(14), btn.centery), 15, theme.WHITE, "semibold", "midright")
        if self.everOnline and not self.net.online:
            pill = theme.text("Reconectando...", 13, theme.WHITE, "semibold")
            rect = pill.get_rect(midtop=(self.W // 2, h + u(8))).inflate(u(20), u(8))
            theme.rrect(s, theme.CRIMSON, rect, 12)
            s.blit(pill, pill.get_rect(center=rect.center))
        return pygame.Rect(0, h, self.W, self.H - h)

    def drawFooter(self, content):
        s, ui = self.screen, self.ui
        h = u(92 if self.portrait else 58)
        top = self.H - h
        pygame.draw.rect(s, theme.BLACK, (0, top, self.W, h))
        pygame.draw.rect(s, theme.RED, (0, top, self.W, u(3)))
        x = u(16 if self.portrait else 22)
        icon = u(32)
        if self.portrait:
            lines = theme.wrap(TECH, 12, "regular", self.W - 2 * x)
            y = top + u(12)
            for line in lines[:2]:
                theme.draw(s, line, (x, y), 12, theme.MUTED)
                y += u(18)
            rowY = top + h - u(12) - icon
        else:
            rowY = top + (h + u(3) - icon) // 2
            theme.draw(s, TECH, (x, rowY + icon // 2), 13, theme.MUTED, anchor="midleft")
        right = self.W - x
        portfolio = pygame.Rect(right - icon, rowY, icon, icon)
        linkedin = pygame.Rect(portfolio.x - u(10) - icon, rowY, icon, icon)
        self.drawLinkedIn(linkedin, ui.link("linkedin", linkedin, LINKEDIN, "LinkedIn de KassioBC"))
        self.drawBriefcase(portfolio, ui.link("portfolio", portfolio, PORTFOLIO, "Portfólio de KassioBC"))
        r = theme.draw(s, "KassioBC", (linkedin.x - u(12), rowY + icon // 2), 13, theme.WHITE, "bold", "midright")
        theme.draw(s, "Desenvolvido por ", (r.x, r.centery), 13, theme.MUTED, anchor="midright")
        return pygame.Rect(content.x, content.y, content.w, top - content.y)

    def drawLinkedIn(self, rect, hover):
        s = self.screen
        theme.rrect(s, theme.RED if hover else theme.WINE, rect, 6)
        box = rect.inflate(-u(14), -u(14))
        theme.rrect(s, theme.WHITE, box, 3)
        theme.draw(s, "in", (box.centerx + u(1), box.centery + u(1)), 12, theme.RED if hover else theme.WINE, "bold", "center")

    def drawBriefcase(self, rect, hover):
        s = self.screen
        theme.rrect(s, theme.RED if hover else theme.WINE, rect, 6)
        w = max(1, u(2))
        body = pygame.Rect(0, 0, u(18), u(13))
        body.center = (rect.centerx, rect.centery + u(2))
        handle = pygame.Rect(0, 0, u(8), u(5))
        handle.midbottom = (rect.centerx, body.top + w)
        theme.rrect(s, theme.WHITE, handle, 2, w)
        theme.rrect(s, theme.WHITE, body, 2, w)
        pygame.draw.line(s, theme.WHITE, (body.left, body.centery - u(1)), (body.right - 1, body.centery - u(1)), w)

    def drawToast(self, content):
        if not self.toastText or time.time() > self.toastUntil:
            return
        s = self.screen
        lines = theme.wrap(self.toastText, 14, "semibold", min(u(520), self.W - u(64)))
        lh = u(22)
        rect = pygame.Rect(0, 0, max(theme.font(14, "semibold").size(l)[0] for l in lines) + u(40), lh * len(lines) + u(20))
        rect.midbottom = (self.W // 2, content.bottom - u(20))
        theme.rrect(s, theme.BLACK, rect, 8)
        pygame.draw.rect(s, theme.RED, (rect.x, rect.y, u(4), rect.h), border_top_left_radius=u(8), border_bottom_left_radius=u(8))
        y = rect.y + u(10)
        for line in lines:
            theme.draw(s, line, (rect.x + u(22), y), 14, theme.WHITE, "semibold")
            y += lh

    # ---------- login / cadastro ----------

    def drawAuth(self, area):
        s, ui = self.screen, self.ui
        register = self.authMode == "register"
        formW = u(340)
        pad = u(28)
        # paisagem: marca à esquerda e formulário à direita; retrato: um embaixo do outro
        brandW = 0 if self.portrait else u(300)
        cardW = min(self.W - u(32), formW + pad * 2 + (brandW + pad if brandW else 0))
        formW = cardW - pad * 2 - (brandW + pad if brandW else 0)
        brandH = 0 if brandW else u(172)
        formH = u(300) + (u(26) if self.authError else 0) + brandH
        cardH = formH + pad * 2
        card = pygame.Rect(0, 0, cardW, cardH)
        card.center = area.center
        theme.card(s, card, 14, accentTop=True)

        if brandW:
            brand = pygame.Rect(card.x + pad, card.y + pad, brandW, cardH - pad * 2)
            # logo e nome centralizados na altura da coluna
            logo = u(150)
            top = brand.centery - (logo + u(10) + u(40)) // 2
            s.blit(theme.image("img/logo_mark.png", (logo, logo)), (brand.centerx - logo // 2, top))
            self.drawBrandName(brand.centerx, top + logo + u(10), 28)
            pygame.draw.line(s, theme.WINE, (brand.right + pad // 2, card.y + pad), (brand.right + pad // 2, card.bottom - pad), max(1, u(1)))
            x = brand.right + pad
            y = card.y + pad
        else:
            logo = u(104)
            s.blit(theme.image("img/logo_mark.png", (logo, logo)), (card.centerx - logo // 2, card.y + pad))
            y = card.y + pad + logo + u(4)
            self.drawBrandName(card.centerx, y, 24)
            y += u(48)
            pygame.draw.line(s, theme.WINE, (card.x + pad, y), (card.right - pad, y), max(1, u(1)))
            y += u(16)
            x = card.x + pad

        theme.draw(s, "Criar conta" if register else "Entrar", (x, y), 21, theme.WHITE, "bold")
        y += u(44)
        theme.draw(s, "Usuário", (x, y), 14, theme.WHITE, "semibold")
        y += u(24)
        user = ui.input("user", pygame.Rect(x, y, formW, u(44)), "Seu nome de usuário", maxlength=20)
        y += u(56)
        theme.draw(s, "Senha", (x, y), 14, theme.WHITE, "semibold")
        y += u(24)
        pwd = ui.input("pass", pygame.Rect(x, y, formW, u(44)), "Sua senha", password=True, maxlength=64)
        y += u(56)
        if self.authError:
            theme.draw(s, theme.ellipsize(self.authError, 13, "semibold", formW), (x, y), 13, theme.RED, "semibold")
            y += u(26)
        label = ("Criando conta..." if register else "Entrando...") if self.authBusy else ("Criar conta" if register else "Entrar")
        submit = ui.button(pygame.Rect(x, y, formW, u(46)), label, "primary", enabled=not self.authBusy and self.net.online)
        if (submit or ui.submitted in ("user", "pass")) and not self.authBusy and self.net.online:
            if not user.strip() or not pwd:
                self.authError = "Preencha usuário e senha"
            else:
                self.authBusy, self.authError = True, ""
                self.send({"type": "register" if register else "login", "username": user.strip(), "password": pwd})
        y += u(62)
        question = "Já tem conta? " if register else "Não tem conta? "
        action = "Entrar" if register else "Criar conta"
        qw = theme.font(14).size(question)[0]
        aw = theme.font(14, "semibold").size(action)[0]
        left = x + (formW - qw - aw) // 2
        theme.draw(s, question, (left, y + u(12)), 14, theme.MUTED, anchor="midleft")
        if ui.button(pygame.Rect(left + qw, y, aw, u(24)), action, "link", size=14):
            self.authMode = "login" if register else "register"
            self.authError = ""
        if browser.BROWSER:
            self.drawDownloads(card, area)

    def drawDownloads(self, card, area):
        # só no navegador: convida a baixar o aplicativo, que roda bem mais leve que o WebAssembly
        s, ui = self.screen, self.ui
        btnW, btnH, gap = u(136), u(34), u(12)
        top = card.bottom + u(22)
        if top + u(24) + btnH > area.bottom:
            return  # janela baixa demais: não cabe sem encostar no rodapé
        theme.draw(s, "Baixe o aplicativo, bem mais rápido que no navegador:", (card.centerx, top), 13, theme.MUTED, anchor="midtop")
        x = card.centerx - (btnW * 2 + gap) // 2
        for i, (id, label, file) in enumerate(DOWNLOADS):
            rect = pygame.Rect(x + i * (btnW + gap), top + u(24), btnW, btnH)
            hover = ui.link(id, rect, RELEASES + file, f"Baixar para {label}")
            theme.rrect(s, theme.RED if hover else theme.CARD2, rect, 8)
            theme.rrect(s, theme.RED if hover else theme.WINE, rect, 8, max(1, u(1)))
            theme.draw(s, f"Baixar {label}", rect.center, 13, theme.WHITE, "semibold", "center")

    def drawBrandName(self, cx, y, size):
        w1 = theme.font(size, "bold").size("Pawnthon ")[0]
        w2 = theme.font(size, "bold").size("Chess")[0]
        left = cx - (w1 + w2) // 2
        theme.draw(self.screen, "Pawnthon ", (left, y), size, theme.WHITE, "bold")
        theme.draw(self.screen, "Chess", (left + w1, y), size, theme.RED, "bold")

    # ---------- lobby ----------

    def drawLobby(self, area):
        s, ui = self.screen, self.ui
        margin = u(16 if self.portrait else 24)
        width = min(u(960), area.w - margin * 2)
        x = area.centerx - width // 2
        y = area.y + margin

        # criar sala
        pad = u(20)
        cardH = u(120)
        card = pygame.Rect(x, y, width, cardH)
        theme.card(s, card)
        theme.draw(s, "Criar sala", (card.x + pad, card.y + pad), 18, theme.WHITE, "bold")
        rowY = card.y + pad + u(40)
        inner = card.w - pad * 2
        # o lado (brancas ou pretas) é escolhido depois, dentro da sala de espera
        createW, gap = u(110), u(10)
        inputW = inner - createW - gap
        name = ui.input("roomName", pygame.Rect(card.x + pad, rowY, inputW, u(42)), "Nome da sala", maxlength=30)
        createRect = pygame.Rect(card.x + pad + inputW + gap, rowY, createW, u(42))
        if ui.button(createRect, "Criar") or ui.submitted == "roomName":
            self.send({"type": "create_room", "name": name})
            ui.setValue("roomName", "")

        # lista de salas
        y = card.bottom + u(26)
        theme.draw(s, "Salas", (x, y), 18, theme.WHITE, "bold")
        y += u(36)
        listArea = pygame.Rect(x - u(12), y, width + u(24), area.bottom - y - u(8))
        if not self.rooms:
            theme.draw(s, "Nenhuma sala aberta. Crie uma!", (x, y), 15, theme.MUTED)
            return
        itemH = u(132) if self.portrait else u(84)
        gap = u(12)
        total = len(self.rooms) * (itemH + gap)
        self.lobbyScroll = ui.scroll(listArea, self.lobbyScroll, total)
        clip = s.get_clip()
        s.set_clip(listArea)
        ui.clip = listArea
        top = y - self.lobbyScroll
        for room in self.rooms:
            rect = pygame.Rect(x, top, width, itemH)
            top += itemH + gap
            if rect.bottom < listArea.top or rect.top > listArea.bottom:
                continue
            self.drawRoomCard(rect, room)
        ui.clip = None
        s.set_clip(clip)
        if total > listArea.h:  # barra de rolagem
            barH = max(u(30), listArea.h * listArea.h // total)
            barY = listArea.y + (listArea.h - barH) * self.lobbyScroll // max(1, total - listArea.h)
            theme.rrect(s, theme.WINE, pygame.Rect(listArea.right - u(6), barY, u(4), barH), 2)

    def drawRoomCard(self, rect, room):
        s, ui = self.screen, self.ui
        theme.card(s, rect, 10)
        pygame.draw.rect(s, theme.CRIMSON, (rect.x, rect.y, u(4), rect.h), border_top_left_radius=u(10), border_bottom_left_radius=u(10))
        pad = u(18)
        info = f'{STATUS_LABEL[room["status"]]} · criada por {room["owner"]} · {room["spectators"]} espectador(es)'
        if self.portrait:
            textW = rect.w - pad * 2
            theme.draw(s, theme.ellipsize(room["name"], 16, "bold", textW), (rect.x + pad, rect.y + u(12)), 16, theme.WHITE, "bold")
            theme.draw(s, theme.ellipsize(info, 12, "regular", textW), (rect.x + pad, rect.y + u(40)), 12, theme.MUTED)
            bw = (rect.w - pad * 2 - u(16)) // 3
            by, bh = rect.bottom - u(56), u(42)
            buttons = [pygame.Rect(rect.x + pad + i * (bw + u(8)), by, bw, bh) for i in range(3)]
        else:
            bw, bh, gap = u(150), u(40), u(8)
            textW = rect.w - pad * 2 - bw * 2 - u(110) - gap * 3
            theme.draw(s, theme.ellipsize(room["name"], 16, "bold", textW), (rect.x + pad, rect.y + u(14)), 16, theme.WHITE, "bold")
            theme.draw(s, theme.ellipsize(info, 13, "regular", textW), (rect.x + pad, rect.y + u(44)), 13, theme.MUTED)
            right = rect.right - pad
            by = rect.centery - bh // 2
            buttons = [pygame.Rect(right - u(110) - gap - bw * 2 - gap, by, bw, bh),
                       pygame.Rect(right - u(110) - gap - bw, by, bw, bh),
                       pygame.Rect(right - u(110), by, u(110), bh)]
        for color, r in zip(("white", "black"), buttons[:2]):
            holder = room[color]
            mine = holder == self.me
            otherMine = room["black" if color == "white" else "white"] == self.me
            if mine:
                label = f"Voltar ({ROLE_LABEL[color]})"
            elif holder:
                label = f"{ROLE_LABEL[color]}: {holder}"
            else:
                label = f"Jogar de {ROLE_LABEL[color]}" if not self.portrait else ROLE_LABEL[color].capitalize()
            enabled = not ((holder and not mine) or otherMine)
            if ui.button(r, label, "secondary" if holder else "primary", enabled, size=13 if self.portrait else 14):
                self.send({"type": "join", "room": room["id"], "role": color})
        if ui.button(buttons[2], "Assistir", "secondary", size=13 if self.portrait else 14):
            self.send({"type": "join", "room": room["id"], "role": "spectator"})

    # ---------- sala ----------

    def leaveRoom(self):
        browser.storageSet(ROOM_KEY, None, session=True)
        self.send({"type": "leave"})
        self.leaveRoomLocally()

    def kickButton(self, rect, username):
        # dois cliques: o primeiro pede confirmação (não dá para desfazer)
        confirming = self.confirmKick and self.confirmKick[0] == username and time.time() < self.confirmKick[1]
        if self.ui.button(rect, "Confirmar?" if confirming else "Remover", "danger", size=13):
            if confirming:
                self.send({"type": "kick", "username": username})
                self.confirmKick = None
            else:
                self.confirmKick = (username, time.time() + 3)

    def drawWaiting(self, area):
        s, ui, g = self.screen, self.ui, self.game
        room = g["room"]
        margin = u(16 if self.portrait else 24)
        pad = u(22)
        width = min(u(680), area.w - margin * 2)
        seatH = u(118)
        seatsH = seatH * 2 + u(12) if self.portrait else seatH
        specs = g["spectatorNames"]
        specH = max(1, len(specs)) * u(42)
        cardH = pad * 2 + u(64) + seatsH + u(20) + u(32) + specH + u(16) + u(30) + u(58)
        card = pygame.Rect(0, 0, width, cardH)
        card.centerx = area.centerx
        card.y = max(area.y + margin, area.centery - cardH // 2)
        theme.card(s, card, 14)
        x, y, inner = card.x + pad, card.y + pad, card.w - pad * 2

        theme.draw(s, theme.ellipsize(room["name"], 21, "bold", inner), (x, y), 21, theme.WHITE, "bold")
        theme.draw(s, f'Sala criada por {room["owner"]}', (x, y + u(34)), 14, theme.MUTED)
        y += u(64)

        if self.portrait:
            seats = [pygame.Rect(x, y, inner, seatH), pygame.Rect(x, y + seatH + u(12), inner, seatH)]
        else:
            half = (inner - u(12)) // 2
            seats = [pygame.Rect(x, y, half, seatH), pygame.Rect(x + half + u(12), y, half, seatH)]
        for color, r in zip(("white", "black"), seats):
            self.drawSeat(r, color)
        y += seatsH + u(20)

        theme.draw(s, "ESPECTADORES", (x, y), 13, theme.MUTED, "semibold")
        y += u(32)
        if not specs:
            theme.draw(s, "Ninguém assistindo ainda", (x, y + u(8)), 14, theme.MUTED)
            y += u(42)
        for name in specs:
            row = pygame.Rect(x, y, inner, u(36))
            theme.rrect(s, theme.CARD2, row, 6)
            theme.draw(s, name + (" (você)" if name == self.me else ""), (row.x + u(12), row.centery), 14, theme.WHITE, anchor="midleft")
            if self.isOwner() and name != self.me:
                self.kickButton(pygame.Rect(row.right - u(106), row.y + u(4), u(100), u(28)), name)
            y += u(42)
        y += u(16)

        if g["role"] == "spectator" and (not room["white"] or not room["black"]):
            status = 'Clique em "Sentar aqui" para escolher o seu lado'
        elif not room["white"] or not room["black"]:
            status = "Esperando o outro jogador entrar..."
        elif self.isPlayer() and not room["ready"][g["role"]]:
            status = 'Marque "Estou pronto" para começar a partida'
        else:
            status = "A partida começa quando os dois jogadores estiverem prontos"
        if g["role"] == "spectator" and room["white"] and room["black"]:
            status += " (você está assistindo)"
        theme.draw(s, theme.ellipsize(status, 14, "semibold", inner), (x, y), 14, theme.WHITE, "semibold")
        y += u(30) + u(10)

        bx = x
        if self.isPlayer():
            ready = room["ready"][g["role"]]
            r = pygame.Rect(bx, y, u(170), u(44))
            if ui.button(r, "Cancelar pronto" if ready else "Estou pronto", "secondary" if ready else "primary"):
                self.send({"type": "ready", "ready": not ready})
            bx = r.right + u(10)
        if ui.button(pygame.Rect(bx, y, u(170), u(44)), "Voltar ao lobby", "secondary"):
            self.leaveRoom()

    def drawSeat(self, rect, color):
        s, g = self.screen, self.game
        room = g["room"]
        name = room[color]
        ready = bool(name) and room["ready"][color]
        theme.rrect(s, theme.CARD2, rect, 10)
        theme.rrect(s, theme.ONLINE if ready else theme.WINE, rect, 10, max(1, u(1)))
        pad = u(14)
        sw = pygame.Rect(rect.x + pad, rect.y + pad + u(2), u(16), u(16))
        theme.rrect(s, theme.WHITE if color == "white" else theme.BLACK, sw, 3)
        theme.rrect(s, theme.MUTED, sw, 3, max(1, u(1)))
        theme.draw(s, "Brancas" if color == "white" else "Pretas", (sw.right + u(8), sw.centery), 14, theme.MUTED, "semibold", "midleft")
        y = rect.y + pad + u(40)
        if name:
            online = g["online"].get(color)
            pygame.draw.circle(s, theme.ONLINE if online else theme.MUTED, (rect.x + pad + u(4), y), u(4))
            r = theme.draw(s, theme.ellipsize(name + (" (você)" if name == self.me else ""), 17, "bold", rect.w - pad * 2 - u(80)),
                           (rect.x + pad + u(16), y), 17, theme.WHITE, "bold", "midleft")
            if name == room["owner"]:
                self.badge((r.right + u(8), y), "dono", theme.CRIMSON, theme.WHITE)
        else:
            theme.draw(s, "— vago —", (rect.x + pad, y), 16, theme.MUTED, anchor="midleft")
        y = rect.bottom - pad - u(14)
        label = "Esperando jogador" if not name else ("Pronto" if ready else "Não está pronto")
        if ready:
            r = self.badge((rect.x + pad, y), label + "    ", theme.ONLINE, theme.BLACK)
            # sinal de visto desenhado (a fonte não tem o caractere ✓)
            w = max(2, u(2))
            pts = [(r.right - u(20), r.centery), (r.right - u(16), r.centery + u(4)), (r.right - u(9), r.centery - u(4))]
            pygame.draw.lines(self.screen, theme.BLACK, False, pts, w)
        else:
            self.badge((rect.x + pad, y), label, theme.BLACK, theme.MUTED)
        if name and name != self.me and self.isOwner():
            self.kickButton(pygame.Rect(rect.right - pad - u(100), y - u(14), u(100), u(28)), name)
        # escolha do lado: sentar num lugar vago (ou trocar de lado) e levantar do seu
        seat = pygame.Rect(rect.right - pad - u(120), y - u(17), u(120), u(34))
        if not name:
            if self.ui.button(seat, "Sentar aqui", size=13):
                self.send({"type": "sit", "role": color})
        elif name == self.me and g["role"] == color:
            if self.ui.button(seat, "Levantar", "secondary", size=13):
                self.send({"type": "sit", "role": "spectator"})

    def badge(self, midleft, label, bg, fg):
        img = theme.text(label, 12, fg, "bold")
        rect = img.get_rect(midleft=(midleft[0] + u(10), midleft[1])).inflate(u(20), u(8))
        theme.rrect(self.screen, bg, rect, 12)
        self.screen.blit(img, img.get_rect(center=rect.center))
        return rect

    # ---------- partida ----------

    def drawGame(self, area):
        s, ui, g = self.screen, self.ui, self.game
        margin = u(16 if self.portrait else 28)
        pad = BoardView.framePad() + u(4)
        if self.portrait:
            sq = (area.w - margin * 2 - pad * 2) // 8
            panelH = u(330)
            sq = min(sq, (area.h - margin * 3 - pad * 2 - panelH) // 8)
            boardSize = sq * 8
            origin = (area.centerx - boardSize // 2, area.y + margin + pad)
            panel = pygame.Rect(area.x + margin, origin[1] + boardSize + pad + margin, area.w - margin * 2, 0)
            panel.h = area.bottom - margin - panel.y
        else:
            panelW = u(360)
            sq = (area.h - margin * 2 - pad * 2) // 8
            sq = min(sq, (area.w - margin * 3 - pad * 2 - panelW) // 8)
            boardSize = sq * 8
            groupW = boardSize + pad * 2 + margin + panelW
            left = area.centerx - groupW // 2
            origin = (left + pad, area.centery - boardSize // 2)
            panel = pygame.Rect(left + pad * 2 + boardSize + margin, origin[1] - pad, panelW, 0)
        self.board.layout(origin, sq)
        ui.rects["board"] = self.board.rect
        self.board.draw(s, g, self.isPlayer())

        if self.promotion and not self.myTurn():
            self.promotion = None
        if self.promotion:
            # escolha da peça da promoção: clicar fora cancela o lance
            colour = "w" if g["role"] == "white" else "b"
            self.board.drawPromotion(s, colour, ui.mouse)
            choice = self.board.promotionClick(ui.mouse)
            if choice:
                ui.hand = True
            if ui.clicked:
                choice = self.board.promotionClick(ui.clicked)
                if choice:
                    start, end = self.promotion
                    self.send({"type": "move", "start": start, "end": end, "promotion": choice})
                    self.waitingServer = True
                self.promotion = None
        # clique no tabuleiro
        elif ui.clicked and self.board.rect.collidepoint(ui.clicked) and self.myTurn() and not self.waitingServer:
            move = self.board.click(ui.clicked, g)
            if move:
                (sr, sc), (er, ec) = move
                if g["board"][sr][sc][1] == "P" and er in (0, 7):
                    self.promotion = move  # o lance só vai para o servidor depois da escolha
                else:
                    self.send({"type": "move", "start": move[0], "end": move[1]})
                    self.waitingServer = True
        if self.myTurn() and not self.promotion and ui.hover(self.board.rect):
            ui.hand = True

        self.drawPanel(panel)

    def drawPanel(self, panel):
        s, ui, g = self.screen, self.ui, self.game
        room = g["room"]
        pad = u(18)
        contentH = u(370) + (u(26) if g["spectatorNames"] else 0)
        if not panel.h:
            panel.h = contentH
        theme.card(s, panel, 12)
        x, y, inner = panel.x + pad, panel.y + pad, panel.w - pad * 2

        theme.draw(s, theme.ellipsize(room["name"], 18, "bold", inner), (x, y), 18, theme.WHITE, "bold")
        y += u(40)
        clock = g["clock"]
        passed = time.time() - self.clockAt if clock["running"] else 0
        turn = "white" if g["whiteToMove"] else "black"
        for color in ("black", "white"):
            row = pygame.Rect(x, y, inner, u(48))
            active = clock["running"] and color == turn
            theme.rrect(s, theme.WINE if active else theme.CARD2, row, 8)
            if active:
                theme.rrect(s, theme.RED, row, 8, max(1, u(1)))
            sw = pygame.Rect(row.x + u(10), row.centery - u(8), u(16), u(16))
            theme.rrect(s, theme.WHITE if color == "white" else theme.BLACK, sw, 3)
            theme.rrect(s, theme.MUTED, sw, 3, max(1, u(1)))
            name = room[color]
            online = name and g["online"].get(color)
            pygame.draw.circle(s, theme.ONLINE if online else theme.MUTED, (sw.right + u(12), row.centery), u(4))
            label = (name + (" (você)" if name == self.me else "")) if name else "— vago —"
            theme.draw(s, theme.ellipsize(label, 14, "semibold", inner - u(150)), (sw.right + u(22), row.centery), 14, theme.WHITE, "semibold", "midleft")
            left = clock[color] - (passed if color == turn else 0)
            self.clockBox(pygame.Rect(row.right - u(92), row.y + u(8), u(84), u(32)), formatTime(left), 19, active and left <= 30)
            y += u(56)

        moveLeft = clock["moveLeft"] - passed
        theme.draw(s, "Tempo da jogada", (x, y + u(14)), 14, theme.MUTED, anchor="midleft")
        self.clockBox(pygame.Rect(x + inner - u(62), y, u(62), u(28)), formatTime(moveLeft) if clock["running"] else "--",
                      15, clock["running"] and moveLeft <= 10)
        y += u(36)
        bar = pygame.Rect(x, y, inner, u(6))
        theme.rrect(s, theme.BLACK, bar, 3)
        ratio = max(0, moveLeft / clock["moveLimit"]) if clock["running"] else 0
        if ratio > 0:
            theme.rrect(s, theme.RED, pygame.Rect(bar.x, bar.y, max(u(6), int(bar.w * ratio)), bar.h), 3)
        y += u(22)

        status = self.statusText()
        for line in theme.wrap(status, 15, "bold", inner)[:2]:
            theme.draw(s, line, (x, y), 15, theme.WHITE, "bold")
            y += u(24)
        if g["lastMove"]:
            theme.draw(s, "Último lance: " + g["lastMove"]["notation"], (x, y + u(4)), 14, theme.MUTED)
        y += u(30)
        if g["spectatorNames"]:
            theme.draw(s, theme.ellipsize("Espectadores: " + ", ".join(g["spectatorNames"]), 13, "regular", inner), (x, y), 13, theme.MUTED)
            y += u(26)

        y = max(y + u(4), panel.bottom - pad - u(44)) if self.portrait else y + u(6)
        bx = x
        if self.isPlayer() and room["status"] in ENDED:
            r = pygame.Rect(bx, y, u(150), u(44))
            if ui.button(r, "Nova partida"):
                self.send({"type": "restart"})
            bx = r.right + u(10)
        if ui.button(pygame.Rect(bx, y, u(160), u(44)), "Voltar ao lobby", "secondary"):
            self.leaveRoom()

    def clockBox(self, rect, label, size, low):
        s = self.screen
        pulse = low and int(time.time() * 2) % 2 == 0
        theme.rrect(s, theme.RED if low else theme.BLACK, rect, 6)
        if pulse:
            theme.alphaRect(s, (0, 0, 0, 70), rect, 6)
        theme.draw(s, label, rect.center, size, theme.WHITE, "mono", "center")

    def statusText(self):
        g = self.game
        status = g["room"]["status"]
        if status == "waiting":
            text = "Esperando o outro jogador entrar..."
        elif status == "checkmate":
            text = "Pretas venceram por xeque-mate" if g["whiteToMove"] else "Brancas venceram por xeque-mate"
        elif status == "stalemate":
            text = "Empate por afogamento"
        elif status == "timeout":
            loser = g["timeout"]["loser"]
            winner = "Pretas" if loser == "white" else "Brancas"
            why = "ficaram 1 minuto sem jogar" if g["timeout"]["reason"] == "move" else "esgotaram o tempo total"
            text = f"{winner} venceram: as {ROLE_LABEL[loser]} {why}"
        elif self.myTurn():
            text = "Xeque! Proteja o seu rei" if g.get("inCheck") else "Sua vez!"
        else:
            text = "Vez das brancas" if g["whiteToMove"] else "Vez das pretas"
            if g.get("inCheck"):
                text = "Xeque! " + text
        if g["role"] == "spectator":
            text += " (você está assistindo)"
        return text
