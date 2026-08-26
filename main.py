import asyncio
import sys
import os
import traceback

sys.path.insert(0, 'Cliente')

import pygame as p

width = height = 500
dim = 8
sqsize = height // dim
maxfps = 20
images = {}


def loadImages():
    pieces = ["wP", "wR", "wN", "wB", "wQ", "wK", "bP", "bR", "bN", "bB", "bQ", "bK"]
    for piece in pieces:
        # Usando caminho relativo simples para o Pygbag não ter problemas de barra invertida
        path = f"Cliente/images/{piece}.png"
        images[piece] = p.transform.scale(p.image.load(path), (sqsize, sqsize))


async def main():
    p.init()
    screen = p.display.set_mode((width, height))
    p.display.set_caption("Online Chess")
    clock = p.time.Clock()
    screen.fill(p.Color("White"))

    try:
        import ChessEngine
        gameOver = False
        gs = ChessEngine.GameState()
        await gs.socket.connect()
        validMoves = gs.getValidMoves()
        moveMade = False
        loadImages()
        running = True
        animate = False
        sqSelected = ()

        while running:
            for e in p.event.get():
                if e.type == p.QUIT:
                    gs.socket.close()
                    running = False

                elif e.type == p.MOUSEBUTTONDOWN and (
                    (gs.socket.turn and gs.socket.player == '0') or
                    (gs.socket.turn and gs.socket.player == '1')
                ):
                    if not gameOver:
                        location = p.mouse.get_pos()
                        col = location[0] // sqsize
                        row = location[1] // sqsize
                        if sqSelected == (row, col):
                            sqSelected = ()
                            gs.socket.playerClicks = []
                        else:
                            sqSelected = (row, col)
                            gs.socket.playerClicks.append(sqSelected)

                        if len(gs.socket.playerClicks) == 2:
                            move = ChessEngine.Move(
                                gs.socket.playerClicks[0],
                                gs.socket.playerClicks[1],
                                gs.socket.board
                            )
                            if move in validMoves:
                                gs.makeMove(move)
                                moveMade = True
                                animate = True
                                sqSelected = ()
                                gs.socket.clicks(gs.socket.playerClicks)
                                gs.socket.turn = not gs.socket.turn
                                gs.socket.playerClicks = []
                            if not moveMade:
                                gs.socket.playerClicks = [sqSelected]

            if len(gs.socket.playerClicks) == 2 and not gs.socket.turn:
                move = ChessEngine.Move(
                    gs.socket.playerClicks[0],
                    gs.socket.playerClicks[1],
                    gs.socket.board
                )
                if move in validMoves:
                    gs.makeMove(move)
                    moveMade = True
                    animate = True
                    sqSelected = ()
                    gs.socket.playerClicks = []
                    if gs.socket.player == '0' or gs.socket.player == '1':
                        gs.socket.turn = not gs.socket.turn

            if moveMade:
                if animate:
                    animateMove(gs.moveLog[-1], screen, gs.socket.board, clock, gs)
                validMoves = gs.getValidMoves()
                moveMade = False
                animate = False

            drawGameState(screen, gs, validMoves, sqSelected)

            if gs.checkMate:
                gameOver = True
                if gs.socket.whiteToMove:
                    drawText(screen, 'O PRETO VENCEU POR CHECKMATE', width, height)
                else:
                    drawText(screen, 'O BRANCO VENCEU POR CHECKMATE', width, height)
            elif gs.stalemate:
                gameOver = True
                drawText(screen, 'stalemate', width, height)

            clock.tick(maxfps)
            p.display.flip()

            await asyncio.sleep(0)
    except Exception as exc:
        trace = traceback.format_exc()
        print(trace)
        while True:
            screen.fill((200, 200, 200))
            y = 10
            for line in trace.split('\n'):
                font = p.font.SysFont("Helvetica", 14, False, False)
                surf = font.render(line, True, (255, 0, 0))
                screen.blit(surf, (10, y))
                y += 20
            p.display.flip()
            for e in p.event.get():
                if e.type == p.QUIT:
                    sys.exit()
            await asyncio.sleep(0)


def highlightSquares(screen, gs, validMoves, sqSelected):
    if sqSelected != ():
        r, c = sqSelected
        if gs.socket.board[r][c][0] == ('w' if gs.socket.whiteToMove else 'b'):
            s = p.Surface((sqsize, sqsize))
            s.set_alpha(100)
            s.fill(p.Color('dark gray'))
            screen.blit(s, (c * sqsize, r * sqsize))
            s.fill(p.Color('blue'))
            for move in validMoves:
                if move.startRow == r and move.startCol == c:
                    screen.blit(s, (move.endCol * sqsize, move.endRow * sqsize))


def drawGameState(screen, gs, validMoves, sqSelected):
    drawBoard(screen, gs)
    highlightSquares(screen, gs, validMoves, sqSelected)
    drawPieces(screen, gs.socket.board)


def drawBoard(screen, gs):
    global colours
    colours = [
        p.Color("white"),
        p.Color("black" if (gs.socket.player == '0' or gs.socket.player == '1') else "gray")
    ]
    for r in range(dim):
        for c in range(dim):
            colour = colours[((r + c) % 2)]
            p.draw.rect(screen, colour, p.Rect(c * sqsize, r * sqsize, sqsize, sqsize))


def drawPieces(screen, board):
    for r in range(dim):
        for c in range(dim):
            piece = board[r][c]
            if piece != "--":
                screen.blit(images[piece], p.Rect(c * sqsize, r * sqsize, sqsize, sqsize))


def animateMove(move, screen, board, clock, gs):
    global colours
    dR = move.endRow - move.startRow
    dC = move.endCol - move.startCol
    framesPerSquare = 7
    frameCount = (abs(dR) + abs(dC)) * framesPerSquare
    for frame in range(frameCount + 1):
        r, c = (
            move.startRow + dR * frame / frameCount,
            move.startCol + dC * frame / frameCount,
        )
        drawBoard(screen, gs)
        drawPieces(screen, board)
        colour = colours[(move.endRow + move.endCol) % 2]
        endSquare = p.Rect(move.endCol * sqsize, move.endRow * sqsize, sqsize, sqsize)
        p.draw.rect(screen, colour, endSquare)
        if move.pieceCaptured != '--':
            screen.blit(images[move.pieceCaptured], endSquare)
        screen.blit(images[move.pieceMoved], p.Rect(c * sqsize, r * sqsize, sqsize, sqsize))
        p.display.flip()
        clock.tick(60)


def drawText(screen, text, w, h):
    font = p.font.SysFont("Helvetica", 32, True, False)
    textObject = font.render(text, 0, p.Color('Black'))
    textLocation = p.Rect(0, 0, w, h).move(
        w / 2 - textObject.get_width() / 2,
        h / 2 - textObject.get_height() / 2
    )
    screen.blit(textObject, textLocation)
    textObject = font.render(text, 0, p.Color("red"))
    screen.blit(textObject, textLocation.move(2, 2))


if __name__ == "__main__":
    asyncio.run(main())
