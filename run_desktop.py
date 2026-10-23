''' Joga o Pawnthon Chess direto no aplicativo Python (janela do pygame, sem navegador).

    python run_desktop.py                 conecta no servidor publicado (https://pawnthon-chess.onrender.com)
    python run_desktop.py --local         sobe o servidor local junto (precisa do DATABASE_URL no .env)
    python run_desktop.py https://outro   conecta em outro servidor

F11 alterna tela cheia. A janela pode ser redimensionada. '''

import os
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_DIR = os.path.join(BASE_DIR, "web", "pawnthon")


def main():
    args = sys.argv[1:]
    local = "--local" in args
    urls = [a for a in args if not a.startswith("--")]
    env = dict(os.environ)
    if local:
        env["PAWNTHON_URL"] = "ws://localhost:8080/ws"
    if urls:
        env["PAWNTHON_URL"] = urls[0]
        if urls[0].startswith("http"):
            env["PAWNTHON_URL"] = urls[0].replace("http", "ws", 1).rstrip("/") + "/ws"  # http->ws, https->wss

    server = None
    if local:
        server = subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "web", "server.py")])
        time.sleep(1.5)
    try:
        # o cliente fica na própria pasta (importa app, theme, net... de lá)
        subprocess.run([sys.executable, os.path.join(CLIENT_DIR, "main.py")], cwd=CLIENT_DIR, env=env)
    finally:
        if server:
            server.terminate()


if __name__ == "__main__":
    main()
