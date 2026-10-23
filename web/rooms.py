''' Salas de jogo e lobby. O servidor é a autoridade: toda jogada é validada aqui pelo ChessEngine
antes de ser repassada para os jogadores e espectadores da sala '''

import asyncio
import itertools
import json
import os
import time

from chess_engine import GameState, Move

EMPTY_ROOM_TTL = 60  # segundos que uma sala vazia espera antes de ser apagada
ROLES = ("white", "black", "spectator")
TOTAL_TIME = float(os.environ.get("CHESS_TOTAL_TIME", 600))  # tempo total de cada jogador (segundos)
MOVE_LIMIT = float(os.environ.get("CHESS_MOVE_LIMIT", 60))  # tempo máximo para fazer uma jogada


class Connection:
    ''' Uma aba do navegador conectada pelo WebSocket '''

    def __init__(self, ws, username):
        self.ws = ws
        self.username = username
        self.token = None  # sessão do login, apagada no logout
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
        self.banned = set()  # usuários removidos pelo dono não podem voltar
        self.empty_since = time.time()
        self.newGame()

    def newGame(self):
        self.gs = GameState()
        self.validMoves = self.gs.getValidMoves()
        self.inCheck = False  # o jogador da vez está em xeque
        self.lastMove = None
        self.clock = {"white": TOTAL_TIME, "black": TOTAL_TIME}
        self.turnStart = None  # quando a jogada atual começou; None com o relógio parado
        self.timeout = None  # {"loser": cor, "reason": "total" | "move"} quando alguém perde por tempo
        # a partida só começa quando os dois jogadores marcam "pronto" na sala de espera
        self.ready = {"white": False, "black": False}
        self.started = False
        self.syncClock()

    @property
    def toMove(self):
        return "white" if self.gs.whiteToMove else "black"

    def elapsed(self):
        return time.time() - self.turnStart if self.turnStart is not None else 0.0

    def syncClock(self):
        # o relógio só corre com os dois jogadores sentados e a partida em andamento
        playing = self.status == "playing"
        if playing and self.turnStart is None:
            self.turnStart = time.time()
        elif not playing and self.turnStart is not None:
            self.clock[self.toMove] -= self.elapsed()
            self.turnStart = None

    def checkTimeout(self):
        # retorna True se o jogador da vez acabou de perder por tempo
        if self.status != "playing":
            return False
        elapsed = self.elapsed()
        color = self.toMove
        if self.clock[color] - elapsed <= 0:
            reason = "total"
        elif elapsed >= MOVE_LIMIT:
            reason = "move"
        else:
            return False
        self.clock[color] = max(0.0, self.clock[color] - elapsed)
        self.turnStart = None
        self.timeout = {"loser": color, "reason": reason}
        return True

    @property
    def status(self):
        if self.timeout:
            return "timeout"
        if self.gs.checkMate:
            return "checkmate"
        if self.gs.stalemate:
            return "stalemate"
        if self.started and self.seats["white"] and self.seats["black"]:
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
            "started": self.started,
            "ready": dict(self.ready),
        }

    def clockState(self):
        elapsed = self.elapsed()
        clock = dict(self.clock)
        clock[self.toMove] = max(0.0, clock[self.toMove] - elapsed)
        return {
            "white": clock["white"],
            "black": clock["black"],
            "moveLeft": max(0.0, MOVE_LIMIT - elapsed),
            "moveLimit": MOVE_LIMIT,
            "running": self.turnStart is not None,
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
            "clock": self.clockState(),
            "timeout": self.timeout,
            "inCheck": self.inCheck,
        }

    async def broadcastState(self):
        self.syncClock()
        await asyncio.gather(*(c.send(self.stateFor(c)) for c in list(self.conns)))

    def freeSeat(self, color):
        self.seats[color] = None
        self.ready[color] = False

    def setReady(self, conn, value):
        # retorna uma mensagem de erro ou None
        if conn.role not in self.seats or self.seats[conn.role] != conn.username:
            return "Só os jogadores podem marcar pronto"
        if self.started:
            return "A partida já começou"
        self.ready[conn.role] = bool(value)
        if self.seats["white"] and self.seats["black"] and all(self.ready.values()):
            self.started = True
        return None

    def tryMove(self, conn, start, end, promotion="Q"):
        # retorna uma mensagem de erro ou None se a jogada foi feita
        # promotion é a peça escolhida quando um peão chega na última fileira
        if self.checkTimeout() or self.status != "playing":
            return "A partida não está em andamento"
        color = self.toMove
        if conn.role != color or self.seats[color] != conn.username:
            return "Não é a sua vez"
        move = Move(tuple(start), tuple(end), self.gs.board)
        for valid in self.validMoves:
            if valid == move:
                # usa o movimento gerado pelo engine, que já sabe se é en passant ou roque
                if valid.isPawnPromotion:
                    if promotion not in Move.PROMOTION_PIECES:
                        return "Escolha rainha, torre, bispo ou cavalo para a promoção"
                    valid.promotionChoice = promotion
                self.clock[color] -= self.elapsed()
                self.gs.makeMove(valid)
                self.turnStart = time.time()
                self.validMoves = self.gs.getValidMoves()
                self.inCheck = self.gs.inCheck()
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
        if conn.username in room.banned:
            return "Você foi removido dessa sala pelo dono"
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

    async def sit(self, conn, color):
        # na sala de espera: escolher um lado, trocar de lado ou levantar (color = "spectator")
        room = conn.room
        if room is None:
            return "Você não está em uma sala"
        if room.started:
            return "A partida já começou"
        if color not in ROLES:
            return "Escolha brancas, pretas ou espectador"
        if color == conn.role:
            return None
        if color != "spectator" and room.seats[color] not in (None, conn.username):
            return "Esse lado já está ocupado"
        if conn.role in room.seats:
            room.freeSeat(conn.role)
        if color != "spectator":
            room.seats[color] = conn.username
            room.ready[color] = False
        conn.role = color
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
            room.freeSeat(conn.role)
        conn.room, conn.role = None, None
        if not room.conns:
            room.empty_since = time.time()
        await room.broadcastState()
        await self.broadcastRooms()

    async def kick(self, conn, username):
        # o dono da sala tira alguém (jogador ou espectador) e impede que volte
        room = conn.room
        if room is None:
            return "Você não está em uma sala"
        if conn.username != room.owner:
            return "Só quem criou a sala pode remover pessoas"
        if username == room.owner:
            return "Você não pode remover a si mesmo"
        seats = [color for color, user in room.seats.items() if user == username]
        targets = [c for c in room.conns if c.username == username]
        if not seats and not targets:
            return "Essa pessoa não está na sala"
        if seats and room.started:
            return "Não dá para remover um jogador com a partida em andamento"
        room.banned.add(username)
        for color in seats:
            room.freeSeat(color)
        for target in targets:
            room.conns.discard(target)
            target.room, target.role = None, None
            await target.send({"type": "kicked", "room": room.name})
            await target.send(self.roomList())
        await room.broadcastState()
        await self.broadcastRooms()
        return None

    async def clockLoop(self):
        # encerra as partidas em que o jogador da vez estourou o tempo
        while True:
            await asyncio.sleep(0.2)
            flagged = [r for r in self.rooms.values() if r.checkTimeout()]
            for room in flagged:
                print(f"Sala {room.id}: {room.seats[room.timeout['loser']]} perdeu por tempo ({room.timeout['reason']})")
                await room.broadcastState()
            if flagged:
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
