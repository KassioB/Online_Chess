''' Pawnthon Chess: cliente do xadrez online feito 100% em Python com pygame-ce.

No navegador ele roda em WebAssembly pelo pygbag (python -m pygbag web/pawnthon);
no desktop roda direto com "python main.py" e conversa com o mesmo servidor. '''

import asyncio
import time

import pygame

import browser
import theme
from app import App


def clamp(value, low, high):
    return max(low, min(high, value))


QUALITY_KEY = "pawnthon_quality"
QUALITIES = (1.0, 0.85)  # último recurso: só o computador que não segura nem 25 quadros/s perde um pouco de nitidez
SLOW_MS = 40      # trabalho médio por quadro acima disso => baixa a qualidade
CHECK_FRAMES = 120 # quantos quadros ocupados compõem cada medição


def chooseScreen(quality=1.0):
    ''' Escolhe o tamanho do framebuffer para ocupar a janela sem faixas pretas.
    Paisagem é desenhada com 800 unidades de altura e retrato com 480 de largura; telas de alta
    densidade (celular, retina) ganham um framebuffer maior para o texto ficar nítido.
    "quality" encolhe esse framebuffer (o navegador estica de volta) em máquinas lentas. '''
    viewport = browser.viewport()
    if viewport is None:
        return (1280, 800), 1.0, False
    width, height, dpr = viewport
    aspect = width / max(1, height)
    if aspect >= 0.95:
        designW, designH = clamp(round(800 * aspect), 1100, 1800), 800
        scale = clamp(height * dpr / 800, 1.0, 2.0) * quality
        portrait = False
    else:
        designW, designH = 480, clamp(round(480 / aspect), 860, 1100)
        scale = clamp(width * dpr / 480, 1.0, 2.0) * quality
        portrait = True
    return (round(designW * scale), round(designH * scale)), scale, portrait


def savedQuality():
    try:
        return clamp(int(browser.storageGet(QUALITY_KEY) or 0), 0, len(QUALITIES) - 1)
    except ValueError:
        return 0


async def main():
    pygame.init()
    level = savedQuality()  # a escolha de uma visita anterior vale para as próximas
    size, scale, portrait = chooseScreen(QUALITIES[level])
    theme.setScale(scale)
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("Pawnthon Chess")
    pygame.display.set_icon(pygame.image.load(theme.BASE + "/favicon.png"))
    app = App(screen, portrait)
    clock = pygame.time.Clock()
    frames = 0
    pending = None  # tamanho novo visto na última checagem (só aplica se continuar igual, evita tremer ao arrastar a janela)
    work = count = 0
    while app.running:
        started = time.perf_counter()
        events = pygame.event.get()
        drawn = app.frame(events)
        if drawn:
            pygame.display.flip()
        spent = (time.perf_counter() - started) * 1000
        frames += 1

        # o tamanho da janela pode mudar depois da largada (layout ainda assentando, rotação do
        # celular, painel redimensionado): sem isto o jogo ficava pequeno no meio da tela
        if browser.BROWSER and frames % 20 == 0:
            wanted = chooseScreen(QUALITIES[level])
            if wanted[0] != screen.get_size():
                if pending == wanted[0]:
                    size, scale, portrait = wanted
                    theme.setScale(scale)
                    screen = pygame.display.set_mode(size)
                    app.resize(screen, portrait)
                    pending = None
                else:
                    pending = wanted[0]
            else:
                pending = None

        # computador fraco: mede quanto custa desenhar um quadro e, se não der conta, reduz a resolução
        if browser.BROWSER and drawn and level < len(QUALITIES) - 1 and spent < 250:  # ignora travadas pontuais (aba em segundo plano)
            work += spent
            count += 1
            if count >= CHECK_FRAMES:
                if work / count > SLOW_MS:
                    level += 1
                    browser.storageSet(QUALITY_KEY, str(level))
                    size, scale, portrait = chooseScreen(QUALITIES[level])
                    theme.setScale(scale)
                    screen = pygame.display.set_mode(size)
                    app.resize(screen, portrait)
                work = count = 0

        clock.tick(app.fps)
        await asyncio.sleep(0)  # devolve o controle para o navegador a cada quadro (exigência do pygbag)
    pygame.quit()


asyncio.run(main())
