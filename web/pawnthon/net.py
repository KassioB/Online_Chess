''' Conexão do cliente com o servidor pelo WebSocket.

No navegador (pygbag/WebAssembly) o Python não tem socket TCP: ele usa o WebSocket do próprio
navegador através do módulo "platform" do pygbag, o mesmo jeito que o pygbag faz no aio.fetch.
No desktop (python main.py) a conexão é feita com o aiohttp, então o jogo roda igual nos dois. '''

import asyncio
import importlib
import json
import os
import sys

BROWSER = sys.platform == "emscripten"
DEFAULT_SERVER = "wss://pawnthon-chess.onrender.com/ws"

# ponte mínima: guarda as mensagens que chegam numa fila que o Python lê a cada quadro
JS_BRIDGE = """
window.PawnNet = {
    ws: null, inbox: [], status: "closed",
    connect(url) {
        this.status = "connecting";
        const ws = new WebSocket(url);
        this.ws = ws;
        ws.onopen = () => { if (this.ws === ws) this.status = "open"; };
        ws.onmessage = (e) => { if (this.ws === ws) this.inbox.push(e.data); };
        ws.onclose = () => { if (this.ws === ws) this.status = "closed"; };
    },
    send(text) { if (this.ws && this.ws.readyState === 1) this.ws.send(text); },
    poll() { const out = JSON.stringify(this.inbox); this.inbox = []; return out; },
    state() { return this.status; },
};
"""


class BrowserSocket:
    def __init__(self):
        import platform
        self.window = platform.window
        self.window.eval(JS_BRIDGE)

    def defaultUrl(self):
        loc = self.window.location
        proto = "wss" if str(loc.protocol) == "https:" else "ws"
        return f"{proto}://{loc.host}/ws"

    def connect(self, url):
        self.window.PawnNet.connect(url)

    @property
    def status(self):
        return str(self.window.PawnNet.state())

    def send(self, text):
        self.window.PawnNet.send(text)

    def poll(self):
        return json.loads(str(self.window.PawnNet.poll()))


class DesktopSocket:
    def __init__(self):
        # import "escondido" para o pygbag não tentar empacotar o aiohttp no navegador
        try:
            self.aiohttp = importlib.import_module("aiohttp")
        except ImportError:
            self.aiohttp = None  # Android: sem aiohttp (difícil de compilar), usa o "websockets", em Python puro
        self.inbox = []
        self.outbox = asyncio.Queue()
        self.status = "closed"
        self.task = None

    def defaultUrl(self):
        # o aplicativo baixado joga no mesmo servidor do site; PAWNTHON_URL aponta para outro (ex.: local)
        return os.environ.get("PAWNTHON_URL", DEFAULT_SERVER)

    def connect(self, url):
        self.status = "connecting"
        self.task = asyncio.get_event_loop().create_task(self._run(url))

    async def _runWebsockets(self, url):
        import ssl
        import websockets
        context = None
        if url.startswith("wss"):
            # o Android não traz certificados do sistema para o Python: usa os do certifi
            import certifi
            context = ssl.create_default_context(cafile=certifi.where())
        async with websockets.connect(url, ssl=context, ping_interval=20) as ws:
            self.status = "open"

            async def sendLoop():
                while True:
                    await ws.send(await self.outbox.get())

            sender = asyncio.ensure_future(sendLoop())
            try:
                async for msg in ws:
                    self.inbox.append(msg)
            finally:
                sender.cancel()

    async def _run(self, url):
        try:
            if self.aiohttp is None:
                await self._runWebsockets(url)
                self.status = "closed"
                return
            async with self.aiohttp.ClientSession() as session:
                async with session.ws_connect(url, heartbeat=20) as ws:
                    self.status = "open"
                    sender = asyncio.ensure_future(self._sendLoop(ws))
                    try:
                        async for msg in ws:
                            if msg.type == self.aiohttp.WSMsgType.TEXT:
                                self.inbox.append(msg.data)
                    finally:
                        sender.cancel()
        except Exception as e:
            print("conexão falhou:", e)
        self.status = "closed"

    async def _sendLoop(self, ws):
        while True:
            await ws.send_str(await self.outbox.get())

    def send(self, text):
        if self.status == "open":
            self.outbox.put_nowait(text)

    def poll(self):
        out, self.inbox = self.inbox, []
        return out


class Client:
    ''' Reconecta sozinho quando a conexão cai e entrega as mensagens já como dicionários '''

    def __init__(self, url=None):
        self.sock = BrowserSocket() if BROWSER else DesktopSocket()
        self.url = url or self.sock.defaultUrl()
        self.retryAt = 0
        self.delay = 0.5
        self.wasOpen = False

    def update(self, now):
        # chamado a cada quadro: reconecta se preciso e devolve as mensagens novas
        status = self.sock.status
        if status == "open" and not self.wasOpen:
            self.wasOpen = True
            self.delay = 0.5
        if status == "closed" and now >= self.retryAt:
            self.wasOpen = False
            self.sock.connect(self.url)
            self.retryAt = now + self.delay
            self.delay = min(self.delay * 2, 8)
        msgs = []
        for raw in self.sock.poll():
            try:
                msgs.append(json.loads(raw))
            except ValueError:
                pass
        return msgs

    @property
    def online(self):
        return self.sock.status == "open"

    def send(self, data):
        self.sock.send(json.dumps(data))
