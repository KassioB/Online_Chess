''' Gera o aplicativo baixável (um único arquivo) do Pawnthon Chess com o PyInstaller.
Roda no sistema em que for executado: no Windows sai dist/PawnthonChess.exe, no Linux dist/PawnthonChess.
O jogo de quem baixar conecta sozinho no servidor publicado (veja DEFAULT_SERVER em pawnthon/net.py). '''

import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(BASE_DIR, "pawnthon")
SEP = ";" if sys.platform == "win32" else ":"


def build():
    data = [("fonts", "fonts"), ("images", "images"), ("img", "img"), ("favicon.png", ".")]
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "PawnthonChess",
        "--distpath", os.path.join(BASE_DIR, "..", "dist"),
        "--workpath", os.path.join(BASE_DIR, "..", "build_desktop"),
        "--specpath", os.path.join(BASE_DIR, "..", "build_desktop"),
        "--paths", APP_DIR,
        # o net.py importa o aiohttp de um jeito "escondido" (por causa do pygbag): o PyInstaller não o vê
        "--hidden-import", "aiohttp",
        "--icon", os.path.join(APP_DIR, "favicon.png"),
    ]
    for src, dest in data:
        cmd += ["--add-data", os.path.join(APP_DIR, src) + SEP + dest]
    cmd.append(os.path.join(APP_DIR, "main.py"))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    build()
