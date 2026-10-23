''' Tabuleiro: desenho, destaque dos lances, animação e cliques.
É a mesma lógica do ChessMain.py da versão desktop (drawBoard, highlightSquares, drawPieces,
animateMove e o loop de cliques com sqSelected/playerClicks), agora com a moldura e as cores
da paleta. As regras continuam no servidor: aqui só usamos a lista de lances válidos que ele manda. '''

import time

import pygame

import theme
from theme import u

DIM = 8
PIECES = ["wP", "wR", "wN", "wB", "wQ", "wK", "bP", "bR", "bN", "bB", "bQ", "bK"]
FRAMES_PER_SQUARE = 7  # mesma velocidade do animateMove do pygame (a 60 quadros por segundo)

SELECTED = (0, 34, 77, 140)
TARGET = (255, 32, 78, 140)
LAST_MOVE = (255, 32, 78, 56)
CHECK = (255, 0, 40, 170)
PROMOTION_PIECES = ("Q", "R", "B", "N")
CHECK_BANNER_SECONDS = 1.6


class BoardView:
    def __init__(self):
        self.images = {}
        self.imageSize = 0
        self.frameCache = None
        self.reset()

    def reset(self):
        self.sqSelected = None
        self.playerClicks = []
        self.animation = None
        self.lastMoveId = None
        self.checkAt = 0  # quando o último xeque aconteceu (o aviso "XEQUE!" aparece por um tempo)

    # ---------- geometria ----------

    @staticmethod
    def framePad():
        return u(12)

    def layout(self, origin, sq):
        self.origin, self.sq = origin, sq
        self.rect = pygame.Rect(origin[0], origin[1], sq * DIM, sq * DIM)

    # ---------- estado vindo do servidor ----------

    def onState(self, state, isNewGame):
        lastMove = state["lastMove"]
        moveId = lastMove["id"] if lastMove else None
        if moveId != self.lastMoveId:
            self.sqSelected, self.playerClicks = None, []
            if not isNewGame and moveId is not None:
                self.startAnimation(lastMove)
                if state.get("inCheck"):
                    # o aviso de xeque aparece quando a peça termina de andar
                    self.checkAt = time.time() + self.animation["duration"]
        self.lastMoveId = moveId

    def startAnimation(self, move):
        dR = move["end"][0] - move["start"][0]
        dC = move["end"][1] - move["start"][1]
        duration = (abs(dR) + abs(dC)) * FRAMES_PER_SQUARE / 60
        self.animation = {"move": move, "dR": dR, "dC": dC, "start": time.time(), "duration": duration}

    @property
    def animating(self):
        return self.animation is not None

    # ---------- desenho ----------

    def piece(self, name):
        if self.imageSize != self.sq:
            self.imageSize = self.sq
            for p in PIECES:
                # os arquivos dos peões estão como wp.png/bp.png
                file = p[0] + "p" if p[1] == "P" else p
                self.images[p] = theme.image(f"images/{file}.png", (self.sq, self.sq))
        return self.images[name]

    def squareRect(self, r, c):
        return pygame.Rect(self.origin[0] + c * self.sq, self.origin[1] + r * self.sq, self.sq, self.sq)

    def drawFrame(self, surf):
        # moldura em degradê carmim → vinho, contorno preto e anel vermelho
        pad = self.framePad()
        outer = self.rect.inflate(pad * 2, pad * 2)
        if self.frameCache is None or self.frameCache[0] != outer.size:
            grad = pygame.Surface((2, 2))
            grad.set_at((0, 0), theme.CRIMSON)
            grad.set_at((1, 0), theme.CRIMSON)
            grad.set_at((0, 1), theme.WINE)
            grad.set_at((1, 1), theme.WINE)
            grad = pygame.transform.smoothscale(grad, outer.size)
            mask = pygame.Surface(outer.size, pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=u(12))
            grad = grad.convert_alpha()
            grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            self.frameCache = (outer.size, grad)
        shadow = theme.alphaRect
        shadow(surf, (0, 0, 0, 90), outer.move(0, u(10)).inflate(u(10), u(10)), 16)
        theme.rrect(surf, theme.RED, outer.inflate(u(4) * 2, u(4) * 2), 16)
        theme.rrect(surf, theme.BLACK, outer.inflate(u(2) * 2, u(2) * 2), 14)
        surf.blit(self.frameCache[1], outer.topleft)
        pygame.draw.rect(surf, theme.BLACK, self.rect.inflate(u(2) * 2, u(2) * 2))

    def colours(self, isPlayer):
        return [theme.LIGHT_SQ, theme.CRIMSON if isPlayer else theme.WINE]

    def drawBoard(self, surf, game, isPlayer):
        colours = self.colours(isPlayer)
        for r in range(DIM):
            for c in range(DIM):
                pygame.draw.rect(surf, colours[(r + c) % 2], self.squareRect(r, c))
        if game["lastMove"] and not self.animation:
            for r, c in (game["lastMove"]["start"], game["lastMove"]["end"]):
                theme.alphaRect(surf, LAST_MOVE, self.squareRect(r, c))
        king = self.kingInCheck(game)
        if king and not self.animation:
            # casa do rei ameaçado em vermelho, com um brilho por baixo da peça
            rect = self.squareRect(*king)
            theme.alphaRect(surf, CHECK, rect)
            pygame.draw.rect(surf, theme.RED, rect, max(2, u(3)))

    def kingInCheck(self, game):
        if not game.get("inCheck"):
            return None
        king = ("w" if game["whiteToMove"] else "b") + "K"
        for r in range(DIM):
            for c in range(DIM):
                if game["board"][r][c] == king:
                    return r, c
        return None

    def highlightSquares(self, surf, game):
        if not self.sqSelected:
            return
        r, c = self.sqSelected
        if game["board"][r][c][0] != ("w" if game["whiteToMove"] else "b"):
            return
        theme.alphaRect(surf, SELECTED, self.squareRect(r, c))
        for sr, sc, er, ec in game["validMoves"]:
            if sr == r and sc == c:
                theme.alphaRect(surf, TARGET, self.squareRect(er, ec))

    def drawPieces(self, surf, board):
        for r in range(DIM):
            for c in range(DIM):
                if board[r][c] != "--":
                    surf.blit(self.piece(board[r][c]), self.squareRect(r, c))

    def drawAnimation(self, surf, game, isPlayer):
        a = self.animation
        t = min(1.0, (time.time() - a["start"]) / a["duration"]) if a["duration"] else 1.0
        move = a["move"]
        r = move["start"][0] + a["dR"] * t
        c = move["start"][1] + a["dC"] * t
        self.drawBoard(surf, game, isPlayer)
        self.drawPieces(surf, game["board"])
        er, ec = move["end"]
        pygame.draw.rect(surf, self.colours(isPlayer)[(er + ec) % 2], self.squareRect(er, ec))
        if move["pieceCaptured"] != "--":
            surf.blit(self.piece(move["pieceCaptured"]), self.squareRect(er, ec))
        surf.blit(self.piece(move["pieceMoved"]), (self.origin[0] + c * self.sq, self.origin[1] + r * self.sq))
        if t >= 1:
            self.animation = None

    def drawText(self, surf, text):
        band = pygame.Rect(self.rect.x, self.rect.centery - u(30), self.rect.w, u(60))
        theme.alphaRect(surf, (0, 34, 77, 200), band)
        size = 20 if self.rect.w > u(400) else 16
        theme.draw(surf, text, band.center, size, theme.BLACK, "bold", "center")
        theme.draw(surf, text, (band.centerx + u(2), band.centery + u(2)), size, theme.RED, "bold", "center")

    def draw(self, surf, game, isPlayer):
        self.drawFrame(surf)
        clip = surf.get_clip()
        surf.set_clip(self.rect)
        if self.animation:
            self.drawAnimation(surf, game, isPlayer)
        else:
            self.drawBoard(surf, game, isPlayer)
            self.highlightSquares(surf, game)
            self.drawPieces(surf, game["board"])
        surf.set_clip(clip)
        status = game["room"]["status"]
        if status == "checkmate":
            self.drawText(surf, "O PRETO VENCEU POR CHECKMATE" if game["whiteToMove"] else "O BRANCO VENCEU POR CHECKMATE")
        elif status == "stalemate":
            self.drawText(surf, "stalemate")
        elif status == "timeout":
            self.drawText(surf, "O PRETO VENCEU POR TEMPO" if game["timeout"]["loser"] == "white" else "O BRANCO VENCEU POR TEMPO")
        elif status == "playing" and game.get("inCheck") and not self.animation                 and time.time() - self.checkAt < CHECK_BANNER_SECONDS:
            self.drawText(surf, "XEQUE!")

    # ---------- promoção do peão ----------

    def promotionRects(self):
        ''' as 4 opções (rainha, torre, bispo, cavalo) lado a lado no meio do tabuleiro '''
        size = int(self.sq * 1.15)
        gap = u(10)
        total = size * 4 + gap * 3
        x = self.rect.centerx - total // 2
        y = self.rect.centery - size // 2 + u(14)
        return [pygame.Rect(x + i * (size + gap), y, size, size) for i in range(4)]

    def drawPromotion(self, surf, colour, mouse):
        theme.alphaRect(surf, (0, 0, 0, 150), self.rect)
        rects = self.promotionRects()
        panel = rects[0].union(rects[-1]).inflate(u(36), u(36))
        panel.y -= u(30)
        panel.h += u(30)
        theme.rrect(surf, theme.NAVY, panel, 12)
        theme.rrect(surf, theme.RED, panel, 12, max(1, u(2)))
        theme.draw(surf, "Promover peão para:", (panel.centerx, panel.y + u(24)), 16, theme.WHITE, "bold", "center")
        for rect, p in zip(rects, PROMOTION_PIECES):
            hover = rect.collidepoint(mouse)
            theme.rrect(surf, theme.CRIMSON if hover else theme.LIGHT_SQ, rect, 8)
            if hover:
                theme.rrect(surf, theme.RED, rect, 8, max(2, u(3)))
            img = theme.image(f"images/{colour}{p}.png", (int(rect.w * 0.9), int(rect.h * 0.9)))
            surf.blit(img, img.get_rect(center=rect.center))
        return panel

    def promotionClick(self, pos):
        ''' devolve a peça clicada ("Q", "R", "B" ou "N") ou None '''
        for rect, p in zip(self.promotionRects(), PROMOTION_PIECES):
            if rect.collidepoint(pos):
                return p
        return None

    # ---------- cliques (mesma lógica do loop de eventos do ChessMain.py) ----------

    def click(self, pos, game):
        ''' devolve (start, end) quando dois cliques formam um lance válido '''
        if not self.rect.collidepoint(pos):
            return None
        col = (pos[0] - self.origin[0]) // self.sq
        row = (pos[1] - self.origin[1]) // self.sq
        if self.sqSelected == (row, col):
            self.sqSelected, self.playerClicks = None, []
        else:
            self.sqSelected = (row, col)
            self.playerClicks.append(self.sqSelected)
        if len(self.playerClicks) == 2:
            (sr, sc), (er, ec) = self.playerClicks
            if [sr, sc, er, ec] in game["validMoves"]:
                self.sqSelected, self.playerClicks = None, []
                return [sr, sc], [er, ec]
            self.playerClicks = [self.sqSelected]
        return None
