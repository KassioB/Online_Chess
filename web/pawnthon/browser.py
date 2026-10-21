''' Tudo o que depende de estar no navegador (pygbag/WebAssembly) ou no desktop.

O canvas do pygame não abre o teclado do celular nem consegue abrir links em nova aba sem ser
bloqueado. Por isso, no navegador, o Python cria campos de texto e links reais da página,
invisíveis, exatamente em cima do que o pygame desenha: o toque cai no elemento de verdade
(teclado, gerenciador de senhas e nova aba funcionam) e o desenho continua sendo do pygame. '''

import json
import os
import sys
import webbrowser

BROWSER = sys.platform == "emscripten"

if BROWSER:
    import platform

    window = platform.window
    window.eval("""
window.PawnDom = {
    els: {},
    canvasRect() {
        const c = document.getElementById("canvas");
        const r = c.getBoundingClientRect();
        return JSON.stringify([r.left + window.scrollX, r.top + window.scrollY, r.width, r.height]);
    },
    viewport() { return JSON.stringify([window.innerWidth, window.innerHeight, window.devicePixelRatio || 1]); },
    isTouch() { return ("ontouchstart" in window) || navigator.maxTouchPoints > 0 ? 1 : 0; },
    base(el, id) {
        el.id = id;
        Object.assign(el.style, { position: "absolute", display: "none", zIndex: 20, margin: 0,
            padding: 0, border: 0, opacity: 0, background: "transparent" });
        // o pygame (SDL) escuta o teclado na janela: impedimos que ele "roube" o que é digitado
        for (const t of ["keydown", "keyup", "keypress"]) el.addEventListener(t, (e) => {
            e.stopPropagation();
            if (t === "keydown" && e.key === "Enter") el.dataset.enter = "1";
        });
        document.body.appendChild(el);
        this.els[id] = el;
        return el;
    },
    input(id, type, autocomplete, maxlength) {
        if (this.els[id]) return;
        const el = this.base(document.createElement("input"), id);
        el.type = type; el.autocomplete = autocomplete; el.maxLength = maxlength;
        el.setAttribute("autocapitalize", "off"); el.setAttribute("spellcheck", "false");
        el.style.fontSize = "16px";  // menor que 16px faz o iPhone dar zoom na página
        el.style.caretColor = "transparent"; el.style.color = "transparent";
    },
    link(id, href, label) {
        if (this.els[id]) return;
        const el = this.base(document.createElement("a"), id);
        el.href = href; el.target = "_blank"; el.rel = "noopener noreferrer";
        el.setAttribute("aria-label", label); el.title = label;
    },
    place(id, x, y, w, h) {
        const el = this.els[id]; if (!el) return;
        Object.assign(el.style, { left: x + "px", top: y + "px", width: w + "px", height: h + "px", display: "block" });
    },
    hide(id) {
        const el = this.els[id]; if (!el) return;
        el.style.display = "none";
        if (document.activeElement === el) el.blur();
    },
    value(id) { const el = this.els[id]; return el ? el.value : ""; },
    setValue(id, v) { const el = this.els[id]; if (el) el.value = v; },
    caret(id) { const el = this.els[id]; return el && el.selectionStart != null ? el.selectionStart : -1; },
    focused() { const a = document.activeElement; return a && this.els[a.id] ? a.id : ""; },
    focus(id) { const el = this.els[id]; if (el) el.focus(); },
    takeEnter(id) { const el = this.els[id]; if (el && el.dataset.enter) { delete el.dataset.enter; return 1; } return 0; },
    cursor(c) { const el = document.getElementById("canvas"); if (el && el.style.cursor !== c) el.style.cursor = c; },
    testMode() { return location.search.indexOf("test") >= 0 ? 1 : 0; },
    publish(json) { window.PawnTest = JSON.parse(json); },
};
""")
    dom = window.PawnDom

TEST_MODE = BROWSER and int(dom.testMode()) == 1  # ?test na URL: publica onde estão os botões (testes automáticos)


# ---------- tela ----------

def viewport():
    ''' (largura, altura, devicePixelRatio) da janela do navegador, ou None no desktop '''
    if not BROWSER:
        return None
    return json.loads(str(dom.viewport()))


def isTouch():
    return BROWSER and int(dom.isTouch()) == 1


def setCursor(hand):
    if BROWSER:
        dom.cursor("pointer" if hand else "default")
    else:
        import pygame
        try:
            pygame.mouse.set_system_cursor(pygame.SYSTEM_CURSOR_HAND if hand else pygame.SYSTEM_CURSOR_ARROW)
        except pygame.error:
            pass  # sem janela de verdade (testes)


# ---------- armazenamento (token de login e sala atual) ----------

_desktopStore = os.path.join(os.path.expanduser("~"), ".pawnthon.json")


def _readDesktop():
    try:
        with open(_desktopStore, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def storageGet(key, session=False):
    if BROWSER:
        try:
            value = (window.sessionStorage if session else window.localStorage).getItem(key)
            return None if value is None or str(value) in ("null", "undefined") else str(value)
        except Exception:
            return None
    return _readDesktop().get(key)


def storageSet(key, value, session=False):
    if BROWSER:
        try:
            store = window.sessionStorage if session else window.localStorage
            if value is None:
                store.removeItem(key)
            else:
                store.setItem(key, value)
        except Exception:
            pass
        return
    data = _readDesktop()
    if value is None:
        data.pop(key, None)
    else:
        data[key] = value
    try:
        with open(_desktopStore, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


# ---------- elementos reais por cima do canvas ----------

class Overlay:
    ''' Posiciona os campos/links da página em cima dos retângulos desenhados no quadro atual
    e esconde os que não foram usados nele '''

    def __init__(self, screenSize):
        self.screenSize = screenSize
        self.placed = {}  # id -> retângulo em pixels da página (para não repetir chamadas ao JS)
        self.used = set()
        self.canvas = None
        self.frame = 0

    def begin(self):
        self.used = set()
        self.frame += 1
        if BROWSER and (self.canvas is None or self.frame % 15 == 0):
            self.canvas = json.loads(str(dom.canvasRect()))

    def _toPage(self, rect):
        left, top, width, height = self.canvas
        sx, sy = width / self.screenSize[0], height / self.screenSize[1]
        return (round(left + rect.x * sx), round(top + rect.y * sy), round(rect.w * sx), round(rect.h * sy))

    def _place(self, id, rect):
        self.used.add(id)
        page = self._toPage(rect)
        if self.placed.get(id) != page:
            self.placed[id] = page
            dom.place(id, *page)

    def input(self, id, rect, password, maxlength):
        if not BROWSER:
            return
        dom.input(id, "password" if password else "text", "current-password" if password else "username", maxlength)
        self._place(id, rect)

    def link(self, id, rect, href, label):
        if not BROWSER:
            return
        dom.link(id, href, label)
        self._place(id, rect)

    def publish(self, rects):
        # só no modo de teste: posição (em pixels da página) de cada botão desenhado neste quadro
        if TEST_MODE and self.frame % 10 == 0:
            dom.publish(json.dumps({name: self._toPage(r) for name, r in rects.items()}))

    def end(self):
        if not BROWSER:
            return
        for id in list(self.placed):
            if id not in self.used:
                dom.hide(id)
                del self.placed[id]

    # leitura dos campos
    def value(self, id):
        return str(dom.value(id))

    def setValue(self, id, value):
        if BROWSER:
            dom.setValue(id, value)

    def caret(self, id):
        return int(dom.caret(id))

    def focused(self):
        return str(dom.focused()) if BROWSER else ""

    def takeEnter(self, id):
        return BROWSER and int(dom.takeEnter(id)) == 1


def openUrl(url):
    # só usado no desktop: no navegador os links são <a target=_blank> de verdade
    webbrowser.open(url)
