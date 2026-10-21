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
