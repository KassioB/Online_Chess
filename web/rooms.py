''' Salas de jogo e lobby. O servidor é a autoridade: toda jogada é validada aqui pelo ChessEngine
antes de ser repassada para os jogadores e espectadores da sala '''

import asyncio
import itertools
import json
import time

from chess_engine import GameState, Move

EMPTY_ROOM_TTL = 60  # segundos que uma sala vazia espera antes de ser apagada
ROLES = ("white", "black", "spectator")


class Connection:
    ''' Uma aba do navegador conectada pelo WebSocket '''

    def __init__(self, ws, username):
        self.ws = ws
        self.username = username
        self.room = None
        self.role = None

    async def send(self, data):
        try:
            await self.ws.send_str(json.dumps(data))
        except Exception:
            pass  # conexão já fechou, o handler do servidor faz a limpeza


class Room:
    def __init__(self, room_id, name, owner):
        self.id = room_id
        self.name = name
        self.owner = owner
        self.created_at = time.time()
        # assentos guardam o nome do usuário, assim quem cair pode voltar para o mesmo lugar
        self.seats = {"white": None, "black": None}
        self.conns = set()
        self.empty_since = time.time()
        self.newGame()

    def newGame(self):
        self.gs = GameState()
        self.validMoves = self.gs.getValidMoves()
        self.lastMove = None

    @property
    def status(self):
        if self.gs.checkMate:
            return "checkmate"
        if self.gs.stalemate:
            return "stalemate"
        if self.seats["white"] and self.seats["black"]:
            return "playing"
        return "waiting"

    def online(self, username):
        return any(c.username == username and c.role != "spectator" for c in self.conns)

    def spectators(self):
        return sorted({c.username for c in self.conns if c.role == "spectator"})

    def summary(self):
        # resumo da sala mostrado na lista do lobby
        return {
            "id": self.id,
            "name": self.name,
            "owner": self.owner,
            "white": self.seats["white"],
            "black": self.seats["black"],
            "spectators": len(self.spectators()),
            "status": self.status,
        }

    def stateFor(self, conn):
        return {
            "type": "state",
            "room": self.summary(),
            "role": conn.role,
            "board": self.gs.board,
            "whiteToMove": self.gs.whiteToMove,
            "validMoves": [[m.startRow, m.startCol, m.endRow, m.endCol] for m in self.validMoves],
            "lastMove": self.lastMove,
            "online": {color: self.online(user) for color, user in self.seats.items() if user},
            "spectatorNames": self.spectators(),
        }

    async def broadcastState(self):
        await asyncio.gather(*(c.send(self.stateFor(c)) for c in list(self.conns)))

    def tryMove(self, conn, start, end):
        # retorna uma mensagem de erro ou None se a jogada foi feita
        if self.status != "playing":
            return "A partida não está em andamento"
        color = "white" if self.gs.whiteToMove else "black"
        if conn.role != color or self.seats[color] != conn.username:
            return "Não é a sua vez"
        move = Move(tuple(start), tuple(end), self.gs.board)
        for valid in self.validMoves:
            if valid == move:
                # usa o movimento gerado pelo engine, que já sabe se é en passant ou roque
                self.gs.makeMove(valid)
                self.validMoves = self.gs.getValidMoves()
                self.lastMove = {
                    "start": [valid.startRow, valid.startCol],
                    "end": [valid.endRow, valid.endCol],
                    "pieceMoved": valid.pieceMoved,
                    "pieceCaptured": valid.pieceCaptured,
                    "notation": valid.getChessNot(),
                    "id": len(self.gs.moveLog),
                }
                return None
        return "Movimento inválido"


class Lobby:
    def __init__(self):
        self.rooms = {}
        self.conns = set()
        self._ids = itertools.count(1)

    def roomList(self):
        return {"type": "rooms", "rooms": [r.summary() for r in self.rooms.values()]}

    async def broadcastRooms(self):
        msg = self.roomList()
        await asyncio.gather(*(c.send(msg) for c in list(self.conns) if c.room is None))

    def createRoom(self, name, owner):
        name = (name or "").strip()[:30] or f"Sala de {owner}"
        room = Room(next(self._ids), name, owner)
        self.rooms[room.id] = room
        return room

    async def join(self, conn, room_id, role):
        room = self.rooms.get(room_id)
        if room is None:
            return "Essa sala não existe mais"
        if role not in ROLES:
            return "Escolha brancas, pretas ou espectador"
        if role != "spectator":
            other = "black" if role == "white" else "white"
            if room.seats[role] not in (None, conn.username):
                return "Esse lado já está ocupado"
            if room.seats[other] == conn.username:
                return "Você já está jogando do outro lado nessa sala"
        if conn.room is not None:
            await self.leave(conn)
        if role != "spectator":
            room.seats[role] = conn.username
        conn.room, conn.role = room, role
        room.conns.add(conn)
        await room.broadcastState()
        await self.broadcastRooms()
        return None

    async def leave(self, conn, explicit=True):
        # explicit=True quando o jogador clica em "Sair" e libera o assento;
        # quando só a conexão cai, o assento fica guardado para ele voltar
        room = conn.room
        if room is None:
            return
        room.conns.discard(conn)
        if explicit and conn.role in room.seats and not room.online(conn.username):
            room.seats[conn.role] = None
        conn.room, conn.role = None, None
        if not room.conns:
            room.empty_since = time.time()
        await room.broadcastState()
        await self.broadcastRooms()

    async def cleanupLoop(self):
        # apaga salas que ficaram vazias por muito tempo
        while True:
            await asyncio.sleep(10)
            now = time.time()
            stale = [rid for rid, r in self.rooms.items()
                     if not r.conns and now - r.empty_since > EMPTY_ROOM_TTL]
            for rid in stale:
                del self.rooms[rid]
            if stale:
                await self.broadcastRooms()
