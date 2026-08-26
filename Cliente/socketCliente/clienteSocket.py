import asyncio
import ast

HOST = 'localhost'
PORT = 5556


class socketClient:

    def __init__(self) -> None:
        self.board = [
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
        ]
        self.whiteToMove = True
        self.player = ''
        self.turn = True
        self.playerClicks = []
        self._ws = None
        self.connected = False
        self._message_buffer = []
        self.is_wasm = False

    async def connect(self):
        import platform
        if hasattr(platform, 'window'):
            self.is_wasm = True
            from platform import window

            js_code = f"""
            (function() {{
                var ws = new WebSocket('ws://{HOST}:{PORT}');
                ws.onopen = function(e) {{
                    window._chess_ws_open = true;
                }};
                ws.onmessage = function(e) {{
                    if (!window._chess_ws_messages) window._chess_ws_messages = [];
                    window._chess_ws_messages.push(e.data);
                }};
                ws.onclose = function(e) {{
                    window._chess_ws_open = false;
                }};
                window._chess_ws = ws;
                window._chess_ws_open = false;
                window._chess_ws_messages = [];
            }})();
            """
            window.eval(js_code)
            self._ws = window.eval("window._chess_ws")

            while not window.eval("window._chess_ws_open"):
                await asyncio.sleep(0.1)

            self.connected = True

        else:
            import websockets
            self._ws = await websockets.connect(f"ws://{HOST}:{PORT}")
            self.connected = True

            async def recv_loop():
                try:
                    async for message in self._ws:
                        self._message_buffer.append(message)
                except Exception as e:
                    print("WS loop encerrado:", e)

            asyncio.ensure_future(recv_loop())

        print("Conectado ao Jogo!")

        self.player = await self._recv()
        if self.player != '0':
            self.turn = False

        board_str = await self._recv()
        self.board = ast.literal_eval(board_str)

        asyncio.ensure_future(self._receiveMessages())

    async def _recv(self):
        while True:
            if self.is_wasm:
                from platform import window
                msgs = window.eval("window._chess_ws_messages")
                if msgs and len(msgs) > 0:
                    msg = str(msgs[0])
                    window.eval("window._chess_ws_messages.shift()")
                    return msg
            else:
                if self._message_buffer:
                    return self._message_buffer.pop(0)
            await asyncio.sleep(0.05)

    async def _receiveMessages(self):
        try:
            while True:
                message = await self._recv()
                self.playerClicks = ast.literal_eval(message)
                print('recebido')
        except Exception:
            print('Desconectado do servidor.')
            self.close()

    def clicks(self, board):
        asyncio.ensure_future(self._send(str(board)))

    async def _send(self, data):
        try:
            if self.is_wasm:
                self._ws.send(data)
            else:
                await self._ws.send(data)
            print('Enviado')
        except Exception as e:
            print(f"Erro ao enviar: {e}")

    def close(self):
        try:
            if self.is_wasm:
                self._ws.close()
            else:
                asyncio.ensure_future(self._ws.close())
        except Exception:
            pass
