import asyncio
import websockets
import ast

HOST = 'localhost'
PORT = 5556

clients = []
board = [
    ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
    ["bP", "bP", "bP", "bP", "bP", "bP", "bP", "bP"],
    ["--", "--", "--", "--", "--", "--", "--", "--"],
    ["--", "--", "--", "--", "--", "--", "--", "--"],
    ["--", "--", "--", "--", "--", "--", "--", "--"],
    ["--", "--", "--", "--", "--", "--", "--", "--"],
    ["wP", "wP", "wP", "wP", "wP", "wP", "wP", "wP"],
    ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"],
]

boolean_turn = True


async def handler(websocket):
    global boolean_turn

    clients.append(websocket)
    player_index = clients.index(websocket)

    if player_index > 1:
        await websocket.close()
        clients.remove(websocket)
        return

    await websocket.send(str(player_index))
    await asyncio.sleep(0.1)
    await websocket.send(str(board))
    print(f"Jogador {player_index} conectado")

    try:
        async for message in websocket:
            clicks = ast.literal_eval(message)
            print(f"Recebido do jogador {player_index}: {clicks}")
            await broadcast(str(clicks), websocket)
    except websockets.exceptions.ConnectionClosed:
        print(f"Jogador {player_index} desconectado")
    finally:
        if websocket in clients:
            clients.remove(websocket)


async def broadcast(data, sender):
    for client in clients:
        if client != sender:
            try:
                await client.send(data)
                print("Enviado!")
            except Exception:
                clients.remove(client)


async def main():
    print(f"Servidor WebSocket iniciado em ws://{HOST}:{PORT}")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
