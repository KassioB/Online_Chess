''' Pawnthon Chess: cliente do xadrez online feito 100% em Python com pygame-ce.

No navegador ele roda em WebAssembly pelo pygbag (python -m pygbag web/pawnthon);
no desktop roda direto com "python main.py" e conversa com o mesmo servidor. '''

import asyncio

import pygame

import browser
import theme
from app import App


def clamp(value, low, high):
    return max(low, min(high, value))


def chooseScreen():
    ''' Escolhe o tamanho do framebuffer para ocupar a janela sem faixas pretas.
    Paisagem é desenhada com 800 unidades de altura e retrato com 480 de largura; telas de alta
    densidade (celular, retina) ganham um framebuffer maior para o texto ficar nítido. '''
    viewport = browser.viewport()
    if viewport is None:
        return (1280, 800), 1.0, False
    width, height, dpr = viewport
    aspect = width / max(1, height)
    if aspect >= 0.95:
        designW, designH = clamp(round(800 * aspect), 1100, 1800), 800
        scale = clamp(height * dpr / 800, 1.0, 2.0)
        portrait = False
    else:
        designW, designH = 480, clamp(round(480 / aspect), 860, 1100)
        scale = clamp(width * dpr / 480, 1.0, 2.0)
        portrait = True
    return (round(designW * scale), round(designH * scale)), scale, portrait


async def main():
    pygame.init()
    size, scale, portrait = chooseScreen()
    theme.S = scale
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("Pawnthon Chess")
    pygame.display.set_icon(pygame.image.load(theme.BASE + "/favicon.png"))
    app = App(screen, portrait)
    clock = pygame.time.Clock()
    while app.running:
        app.frame(pygame.event.get())
        pygame.display.flip()
        clock.tick(app.fps)
        await asyncio.sleep(0)  # devolve o controle para o navegador a cada quadro (exigência do pygbag)
    pygame.quit()


asyncio.run(main())
