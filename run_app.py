import os
import subprocess
import sys
import time
import webbrowser

PORT = int(os.environ.get("PORT", 8080))


def start_application():
    print("==================================================")
    print("🚀 INICIANDO PAWNTHON CHESS (navegador)")
    print("==================================================\n")

    server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "server.py")

    print("📡 [1/2] Iniciando servidor (HTTP + WebSocket)...")
    p_server = subprocess.Popen([sys.executable, server_path])
    time.sleep(1.5)

    print(f"🌐 [2/2] Abrindo http://localhost:{PORT} no navegador...")
    webbrowser.open(f"http://localhost:{PORT}")

    print("\n✅ Aplicação rodando!")
    print("💡 Pressione CTRL + C neste terminal para encerrar.\n")
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
