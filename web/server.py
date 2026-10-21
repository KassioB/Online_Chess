''' Servidor do Pawnthon Chess.
Uma única porta serve o cliente (o jogo em pygame compilado para WebAssembly pelo pygbag)
e o WebSocket (/ws) por onde passam o login, o lobby e as partidas em tempo real '''

import asyncio
import json
import os

from aiohttp import WSMsgType, web

import database
from rooms import Connection, Lobby

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_DIR = os.path.join(BASE_DIR, "pawnthon", "build", "web")  # saída do "pygbag --build"
PYGBAG_CDN = "https://pygame-web.github.io/cdn/"

lobby = Lobby()


async def clientFile(request):
    # index.html, pawnthon.tar.gz e favicon.png gerados pelo pygbag
    name = request.match_info.get("name") or "index.html"
    path = os.path.join(CLIENT_DIR, name)
    if os.path.dirname(os.path.abspath(path)) != CLIENT_DIR or not os.path.isfile(path):
        raise web.HTTPNotFound(text="Cliente não encontrado. Rode: python run_app.py (ele faz o build com o pygbag)")
    return web.FileResponse(path, headers={"Cache-Control": "no-cache"})


async def cdnRedirect(request):
    # quando a página é aberta em "localhost", o pygbag acha que está no servidor de testes dele
    # e busca os pacotes (ex.: pygame-ce) em /cdn/ deste mesmo endereço; mandamos para o CDN oficial
    raise web.HTTPFound(PYGBAG_CDN + request.match_info["path"])


async def wsHandler(request):
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    conn = Connection(ws, None)  # só ganha um usuário depois do login
    await conn.send({"type": "need_login"})

    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except ValueError:
                continue
            if conn.username is None:
                await handleAuth(conn, data)
                continue
            error = await handleMessage(conn, data)
            if error:
                await conn.send({"type": "error", "message": error})
    finally:
        if conn.username:
            lobby.conns.discard(conn)
            await lobby.leave(conn, explicit=False)
            print(f"{conn.username} desconectado")
    return ws


async def handleAuth(conn, data):
    # login, cadastro ou retomada de sessão (token salvo no navegador)
    kind = data.get("type")
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if kind == "auth":
        token = str(data.get("token", ""))
        user = database.get_session_user(token)
        if not user:
            await conn.send({"type": "need_login"})
            return
    elif kind == "login":
        # o hash da senha é lento de propósito: roda numa thread para não congelar as partidas
        user = await asyncio.to_thread(database.check_login, username, password)
        if not user:
            await conn.send({"type": "auth_error", "message": "Usuário ou senha incorretos"})
            return
        token = database.create_session(user)
    elif kind == "register":
        error = await asyncio.to_thread(database.create_user, username, password)
        if error:
            await conn.send({"type": "auth_error", "message": error})
            return
        user, token = username, database.create_session(username)
    else:
        await conn.send({"type": "need_login"})
        return

    conn.username, conn.token = user, token
    lobby.conns.add(conn)
    print(f"{user} conectado")
    await conn.send({"type": "hello", "username": user, "token": token})
    await conn.send(lobby.roomList())


async def handleMessage(conn, data):
    kind = data.get("type")

    if kind == "logout":
        await lobby.leave(conn)
        lobby.conns.discard(conn)
        database.delete_session(conn.token)
        print(f"{conn.username} saiu da conta")
        conn.username = conn.token = None
        await conn.send({"type": "need_login"})
        return None

    if kind == "create_room":
        room = lobby.createRoom(data.get("name"), conn.username)
        role = data.get("role", "white")
        return await lobby.join(conn, room.id, role)

    if kind == "join":
        try:
            room_id = int(data.get("room"))
        except (TypeError, ValueError):
            return "Sala inválida"
        return await lobby.join(conn, room_id, data.get("role"))

    if kind == "leave":
        await lobby.leave(conn)
        await conn.send(lobby.roomList())
        return None

    if kind == "move":
        room = conn.room
        if room is None:
            return "Você não está em uma sala"
        try:
            start = [int(x) for x in data["start"]]
            end = [int(x) for x in data["end"]]
        except (KeyError, TypeError, ValueError):
            return "Movimento inválido"
        if not all(0 <= x < 8 for x in start + end) or len(start) != 2 or len(end) != 2:
            return "Movimento inválido"
        error = room.tryMove(conn, start, end)
        if error:
            if room.status == "timeout":  # o tempo acabou antes da jogada chegar
                await room.broadcastState()
                await lobby.broadcastRooms()
            else:
                await conn.send(room.stateFor(conn))  # devolve o estado certo para o cliente se acertar
            return error
        print(f"Sala {room.id}: {conn.username} jogou {room.lastMove['notation']}")
        await room.broadcastState()
        await lobby.broadcastRooms()
        return None

    if kind == "ready":
        room = conn.room
        if room is None:
            return "Você não está em uma sala"
        error = room.setReady(conn, data.get("ready"))
        if error:
            return error
        if room.started:
            print(f"Sala {room.id}: partida iniciada")
        await room.broadcastState()
        await lobby.broadcastRooms()
        return None

    if kind == "kick":
        return await lobby.kick(conn, str(data.get("username", "")))

    if kind == "restart":
        room = conn.room
        if room is None or conn.role == "spectator":
            return "Só os jogadores podem pedir uma nova partida"
        if room.status not in ("checkmate", "stalemate", "timeout"):
            return "A partida ainda não terminou"
        room.newGame()
        await room.broadcastState()
        await lobby.broadcastRooms()
        return None

    return "Mensagem desconhecida"


async def startBackground(app):
    app["cleanup"] = asyncio.create_task(lobby.cleanupLoop())
    app["clock"] = asyncio.create_task(lobby.clockLoop())


async def stopBackground(app):
    app["cleanup"].cancel()
    app["clock"].cancel()


def createApp():
    database.init_db()
    app = web.Application()
    app.add_routes([
        web.get("/ws", wsHandler),
        web.get("/cdn/{path:.+}", cdnRedirect),
        web.get("/", clientFile),
        web.get("/{name}", clientFile),
    ])
    app.on_startup.append(startBackground)
    app.on_cleanup.append(stopBackground)
    return app


if __name__ == "__main__":
    print(f"Servidor iniciado em http://localhost:{PORT}")
    web.run_app(createApp(), host=HOST, port=PORT, print=None)
