''' Servidor do Pawnthon Chess para navegador.
Uma única porta serve as páginas (HTTP), as rotas de conta (/api/...) e o jogo em tempo real (/ws) '''

import asyncio
import json
import os

from aiohttp import WSMsgType, web

import database
from rooms import Connection, Lobby

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
IMAGES_DIR = os.path.join(BASE_DIR, "..", "Cliente", "images")
COOKIE = "chess_session"

lobby = Lobby()


def setSessionCookie(response, token):
    response.set_cookie(COOKIE, token, max_age=database.SESSION_TTL, httponly=True, samesite="Lax")


async def readCredentials(request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    return str(data.get("username", "")).strip(), str(data.get("password", ""))


async def register(request):
    username, password = await readCredentials(request)
    error = database.create_user(username, password)
    if error:
        return web.json_response({"error": error}, status=400)
    response = web.json_response({"username": username})
    setSessionCookie(response, database.create_session(username))
    return response


async def login(request):
    username, password = await readCredentials(request)
    user = database.check_login(username, password)
    if not user:
        return web.json_response({"error": "Usuário ou senha incorretos"}, status=401)
    response = web.json_response({"username": user})
    setSessionCookie(response, database.create_session(user))
    return response


async def logout(request):
    database.delete_session(request.cookies.get(COOKIE))
    response = web.json_response({"ok": True})
    response.del_cookie(COOKIE)
    return response


async def me(request):
    return web.json_response({"username": database.get_session_user(request.cookies.get(COOKIE))})


async def index(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))


async def wsHandler(request):
    username = database.get_session_user(request.cookies.get(COOKIE))
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)
    if not username:
        await ws.close(code=4001, message=b"login required")
        return ws

    conn = Connection(ws, username)
    lobby.conns.add(conn)
    print(f"{username} conectado")
    await conn.send({"type": "hello", "username": username})
    await conn.send(lobby.roomList())

    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except ValueError:
                continue
            error = await handleMessage(conn, data)
            if error:
                await conn.send({"type": "error", "message": error})
    finally:
        lobby.conns.discard(conn)
        await lobby.leave(conn, explicit=False)
        print(f"{username} desconectado")
    return ws


async def handleMessage(conn, data):
    kind = data.get("type")

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
        web.get("/", index),
        web.get("/ws", wsHandler),
        web.post("/api/register", register),
        web.post("/api/login", login),
        web.post("/api/logout", logout),
        web.get("/api/me", me),
        web.static("/static", STATIC_DIR),
        web.static("/images", IMAGES_DIR),
    ])
    app.on_startup.append(startBackground)
    app.on_cleanup.append(stopBackground)
    return app


if __name__ == "__main__":
    print(f"Servidor iniciado em http://localhost:{PORT}")
    web.run_app(createApp(), host=HOST, port=PORT, print=None)
