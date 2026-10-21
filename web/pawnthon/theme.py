''' Paleta, fontes e funções de desenho usadas por todas as telas.
Todos os tamanhos são escritos em "unidades de design" e passam por u(), que aplica a escala
da tela (telas de alta densidade usam um framebuffer maior para o texto ficar nítido). '''

import os

import pygame

BASE = os.path.dirname(os.path.abspath(__file__))

# paleta: #FF204E, #A0153E, #5D0E41, #00224D + branco e preto
RED = (255, 32, 78)
CRIMSON = (160, 21, 62)
WINE = (93, 14, 65)
NAVY = (0, 34, 77)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

BG = (0, 24, 58)
CARD = NAVY
CARD2 = (10, 45, 92)
TEXT = WHITE
MUTED = (185, 194, 214)
PINK = (255, 122, 150)
ONLINE = (61, 220, 132)
LIGHT_SQ = (243, 230, 234)

S = 1.0  # escala definida em main.py conforme a tela


def u(n):
    return int(round(n * S))


# ---------- fontes e texto ----------

FONT_FILES = {
    "regular": "Poppins-Regular.ttf",
    "semibold": "Poppins-SemiBold.ttf",
    "bold": "Poppins-Bold.ttf",
    "mono": "JetBrainsMono-Bold.ttf",
}
_fonts = {}
_texts = {}


def font(size, weight="regular"):
    key = (weight, u(size))
    if key not in _fonts:
        _fonts[key] = pygame.font.Font(os.path.join(BASE, "fonts", FONT_FILES[weight]), key[1])
    return _fonts[key]


def text(s, size, color=TEXT, weight="regular"):
    key = (s, size, color, weight)
    img = _texts.get(key)
    if img is None:
        if len(_texts) > 600:  # o relógio gera textos novos todo segundo
            _texts.clear()
        img = _texts[key] = font(size, weight).render(s, True, color)
    return img


def draw(surf, s, pos, size, color=TEXT, weight="regular", anchor="topleft"):
    img = text(s, size, color, weight)
    rect = img.get_rect(**{anchor: pos})
    surf.blit(img, rect)
    return rect


def ellipsize(s, size, weight, maxWidth):
    f = font(size, weight)
    if f.size(s)[0] <= maxWidth:
        return s
    while s and f.size(s + "…")[0] > maxWidth:
        s = s[:-1]
    return s + "…"


def wrap(s, size, weight, maxWidth):
    f = font(size, weight)
    lines, line = [], ""
    for word in s.split(" "):
        test = (line + " " + word).strip()
        if line and f.size(test)[0] > maxWidth:
            lines.append(line)
            line = word
        else:
            line = test
    if line:
        lines.append(line)
    return lines


# ---------- formas ----------

def rrect(surf, color, rect, radius, width=0):
    pygame.draw.rect(surf, color, rect, width, border_radius=u(radius))


def card(surf, rect, radius=12, accentTop=False, color=CARD):
    # sombra + cartão com borda vinho, igual aos cartões da versão anterior do site
    shadow = pygame.Surface((rect.w + u(24), rect.h + u(24)), pygame.SRCALPHA)
    for i in range(6):
        pygame.draw.rect(shadow, (0, 0, 0, 14), shadow.get_rect().inflate(-u(4) * i, -u(4) * i), border_radius=u(radius + 12 - 2 * i))
    surf.blit(shadow, (rect.x - u(12), rect.y - u(4)))
    if accentTop:
        # faixa vermelha no topo: o cartão vermelho fica por baixo, deslocado 4px
        rrect(surf, RED, rect, radius)
        rrect(surf, color, pygame.Rect(rect.x, rect.y + u(4), rect.w, rect.h - u(4)), radius)
    else:
        rrect(surf, color, rect, radius)
        rrect(surf, WINE, rect, radius, max(1, u(1)))


def alphaRect(surf, rgba, rect, radius=0):
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(layer, rgba, layer.get_rect(), border_radius=u(radius) if radius else 0)
    surf.blit(layer, rect.topleft)


def background(surf):
    # fundo azul-marinho com dois brilhos suaves (carmim e vinho), pré-calculado uma vez
    global _bg
    if _bg is None or _bg.get_size() != surf.get_size():
        w, h = surf.get_size()
        _bg = pygame.Surface((w, h))
        _bg.fill(BG)
        glow = pygame.Surface((w // 4, h // 4), pygame.SRCALPHA)
        gw, gh = glow.get_size()
        for (cx, cy, color, alpha) in ((0.85, -0.05, CRIMSON, 70), (-0.05, 1.05, WINE, 90)):
            for i in range(24, 0, -1):
                r = int(max(gw, gh) * 0.03 * i)
                pygame.draw.ellipse(glow, (*color, alpha // 24), (int(cx * gw) - r, int(cy * gh) - r * 2 // 3, r * 2, r * 4 // 3))
        _bg.blit(pygame.transform.smoothscale(glow, (w, h)), (0, 0))
    surf.blit(_bg, (0, 0))


_bg = None


# ---------- imagens ----------

_images = {}


def image(path, size=None):
    key = (path, size)
    if key not in _images:
        img = pygame.image.load(os.path.join(BASE, path)).convert_alpha()
        if size:
            img = pygame.transform.smoothscale(img, size)
        _images[key] = img
    return _images[key]
