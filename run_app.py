import os
import subprocess
import sys
import time
import webbrowser

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# os emojis abaixo quebram o print em terminais sem UTF-8 (ex.: saída redirecionada no Windows)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def start_application():
    print("==================================================")
    print("🚀 INICIANDO PAWNTHON CHESS (Python no navegador)")
    print("==================================================\n")

    print("🐍 [1/3] Compilando o cliente pygame para WebAssembly (pygbag)...")
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "web", "build_client.py")], check=True)

    print("📡 [2/3] Iniciando servidor (HTTP + WebSocket)...")
    p_server = subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "web", "server.py")])
    time.sleep(1.5)

    print(f"🌐 [3/3] Abrindo http://localhost:{PORT} no navegador...")
    webbrowser.open(f"http://localhost:{PORT}")

    print("\n✅ Aplicação rodando!")
    print("💡 Pressione CTRL + C neste terminal para encerrar.")
    print("⏳ A primeira visita baixa o Python em WebAssembly (alguns segundos); depois fica em cache.")
    print("⚠️  Para testar sozinho, abra outra janela anônima (outra conta) em "
          f"http://localhost:{PORT}\n")

    try:
        p_server.wait()
    except KeyboardInterrupt:
        print("\n\n🛑 Encerrando servidor...")
        p_server.terminate()
        print("✨ Aplicação encerrada com sucesso!")


if __name__ == "__main__":
    start_application()
