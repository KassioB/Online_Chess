''' Compila o cliente pygame (web/pawnthon) para WebAssembly com o pygbag.
O resultado fica em web/pawnthon/build/web e é servido pelo server.py. '''

import os
import shutil
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(BASE_DIR, "pawnthon")
OUT_DIR = os.path.join(APP_DIR, "build", "web")


def build():
    cmd = [
        sys.executable, "-m", "pygbag", "--build",
        "--ume_block", "0",  # não precisa de clique para começar: o jogo não usa som
        "--title", "Pawnthon Chess",
        "--template", os.path.join(BASE_DIR, "pawnthon.tmpl"),
        APP_DIR,
    ]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not os.path.isfile(os.path.join(OUT_DIR, "pawnthon.tar.gz")):
        print(result.stdout[-3000:], result.stderr[-3000:], sep="\n")
        raise SystemExit("Falha ao compilar o cliente com o pygbag")
    # a tela de carregamento do template mostra a logo enquanto o Python é baixado
    shutil.copy(os.path.join(APP_DIR, "img", "logo_mark.png"), os.path.join(OUT_DIR, "logo.png"))
    # o pygbag coloca o ícone padrão dele; usamos a logo do Pawnthon na aba do navegador
    shutil.copy(os.path.join(APP_DIR, "favicon.png"), os.path.join(OUT_DIR, "favicon.png"))
    for leftover in ("pawnthon.apk",):  # formato do itch.io, não usamos
        path = os.path.join(OUT_DIR, leftover)
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    build()
    print("Cliente compilado em", OUT_DIR)
