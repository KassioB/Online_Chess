''' Interface "imediata": a cada quadro as telas desenham botões e campos e já perguntam
se foram clicados. Simples de seguir e sem árvore de widgets para manter sincronizada. '''

import time

import pygame

import browser
import theme
from theme import u

DRAG_THRESHOLD = 10


class UI:
    def __init__(self, screen):
        self.screen = screen
        self.overlay = browser.Overlay(screen.get_size())
        self.mouse = (-1, -1)
        self.down = False
        self.pressedAt = None
        self.clicked = None
        self.dragged = 0
        self.dragDy = 0
        self.wheel = 0
        self.clip = None
        self.hand = False
        self.lastHand = None
        self.values = {}
        self.focus = None  # campo com foco no desktop
        self.order = []
        self.keys = []
        self.typed = ""
        self.submitted = None
        self.domFocus = ""
        self.rects = {}  # nome -> retângulo dos botões do quadro (usado só pelos testes)

    # ---------- quadro ----------

    def begin(self, events):
        self.clicked = None
        self.wheel = 0
        self.dragDy = 0
        self.hand = False
        self.submitted = None
        self.keys, self.typed = [], ""
        self.lastOrder, self.order = self.order, []
        self.rects = {}
        for e in events:
            if e.type == pygame.MOUSEMOTION:
                self.mouse = e.pos
                if self.down:
                    self.dragged += abs(e.rel[1]) + abs(e.rel[0])
                    self.dragDy += e.rel[1]
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.mouse = self.pressedAt = e.pos
                self.down, self.dragged = True, 0
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self.mouse = e.pos
                if self.down and self.dragged < u(DRAG_THRESHOLD):
                    self.clicked = e.pos
                    self.focus = None  # o campo clicado pega o foco de novo ao ser desenhado
                self.down = False
            elif e.type == pygame.MOUSEWHEEL:
                self.wheel += e.y
            elif e.type == pygame.KEYDOWN:
                self.keys.append(e)
            elif e.type == pygame.TEXTINPUT:
                self.typed += e.text
        self.overlay.begin()
        self.domFocus = self.overlay.focused()

    def end(self):
        # Tab passa para o próximo campo (no navegador quem cuida disso é a própria página)
        if not browser.BROWSER and self.focus in self.order:
            for e in self.keys:
                if e.key == pygame.K_TAB:
                    i = self.order.index(self.focus)
                    self.focus = self.order[(i + 1) % len(self.order)]
        self.overlay.publish(self.rects)
        self.overlay.end()
        if self.hand != self.lastHand:
            browser.setCursor(self.hand)
            self.lastHand = self.hand

    # ---------- testes de clique ----------

    def inClip(self, pos):
        return self.clip is None or self.clip.collidepoint(pos)

    def hover(self, rect):
        return rect.collidepoint(self.mouse) and self.inClip(self.mouse)

    def clickedIn(self, rect):
        return (self.clicked is not None and rect.collidepoint(self.clicked) and self.pressedAt
                and rect.collidepoint(self.pressedAt) and self.inClip(self.clicked))

    # ---------- botões ----------

    def button(self, rect, label, kind="primary", enabled=True, size=15):
        self.rects.setdefault(label, rect)
        hover = enabled and self.hover(rect)
        if hover:
            self.hand = True
        s = self.screen
        if kind == "primary":
            bg = theme.CRIMSON if hover else theme.RED
            if not enabled:
                bg = (110, 40, 70)
            theme.rrect(s, bg, rect, 8)
            color = theme.WHITE if enabled else (200, 170, 185)
        elif kind == "danger":
            if hover:
                theme.rrect(s, theme.RED, rect, 6)
            theme.rrect(s, theme.RED, rect, 6, max(1, u(1)))
            color = theme.WHITE if hover else theme.RED
        elif kind == "link":
            color = theme.WHITE if hover else theme.RED
            r = theme.draw(s, label, rect.center, size, color, "semibold", "center")
            pygame.draw.line(s, color, (r.left, r.bottom - u(3)), (r.right, r.bottom - u(3)), max(1, u(1)))
            return enabled and self.clickedIn(rect)
        else:  # secondary
            theme.rrect(s, theme.CARD2, rect, 8)
            theme.rrect(s, theme.RED if hover else theme.WINE, rect, 8, max(1, u(1)))
            color = theme.WHITE if enabled else theme.MUTED
        label = theme.ellipsize(label, size, "semibold", rect.w - u(16))
        theme.draw(s, label, rect.center, size, color, "semibold", "center")
        return enabled and self.clickedIn(rect)

    # ---------- campos de texto ----------

    def input(self, id, rect, placeholder, password=False, maxlength=30):
        s = self.screen
        self.order.append(id)
        if browser.BROWSER:
            self.overlay.input(id, rect, password, maxlength)
            value = self.overlay.value(id)
            focused = self.domFocus == id
            if self.overlay.takeEnter(id):
                self.submitted = id
        else:
            if self.clickedIn(rect):
                self.focus = id
            focused = self.focus == id
            value = self.values.get(id, "")
            if focused:
                for e in self.keys:
                    if e.key == pygame.K_BACKSPACE:
                        value = value[:-1]
                    elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.submitted = id
                value = (value + self.typed)[:maxlength]
            if self.hover(rect):
                self.hand = True
        self.values[id] = value

        theme.rrect(s, theme.CARD2, rect, 8)
        theme.rrect(s, theme.RED if focused else theme.WINE, rect, 8, u(2) if focused else max(1, u(1)))
        pad = u(12)
        shown = "•" * len(value) if password else value
        clip = s.get_clip()
        inner = rect.inflate(-pad * 2, 0)
        s.set_clip(inner.clip(clip) if clip else inner)
        if shown:
            img = theme.text(shown, 15, theme.WHITE)
            x = inner.x if img.get_width() <= inner.w else inner.right - img.get_width()  # rola até o fim
            s.blit(img, (x, rect.centery - img.get_height() // 2))
            caretX = x + img.get_width()
        else:
            theme.draw(s, placeholder, (inner.x, rect.centery), 15, (120, 135, 165), anchor="midleft")
            caretX = inner.x
        if focused and int(time.time() * 2) % 2 == 0:
            pygame.draw.line(s, theme.WHITE, (caretX + u(1), rect.centery - u(10)), (caretX + u(1), rect.centery + u(10)), max(1, u(2)))
        s.set_clip(clip)
        return value

    def setValue(self, id, value):
        self.values[id] = value
        self.overlay.setValue(id, value)

    # ---------- links externos ----------

    def link(self, id, rect, href, label):
        ''' área clicável que abre um site em nova aba; devolve se o mouse está em cima '''
        self.overlay.link(id, rect, href, label)
        hover = self.hover(rect)
        if not browser.BROWSER:
            if hover:
                self.hand = True
            if self.clickedIn(rect):
                browser.openUrl(href)
        return hover

    # ---------- rolagem ----------

    def scroll(self, area, offset, contentHeight):
        if self.hover(area):
            offset -= self.wheel * u(48)
        if self.down and self.pressedAt and area.collidepoint(self.pressedAt):
            offset -= self.dragDy
        return max(0, min(offset, max(0, contentHeight - area.h)))
