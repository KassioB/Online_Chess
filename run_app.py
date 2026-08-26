import os
import subprocess
import sys
import time
import webbrowser


def start_application():
    print("==================================================")
    print("🚀 INICIANDO APLICAÇÃO ONLINE CHESS")
    print("==================================================\n")

    processes = []

    try:
        # 1. Identifica e inicia o servidor backend
        # Ajustado para o nome correto do arquivo no projeto
        server_path = os.path.join("Servidor", "serverWebSocket.py")

        if os.path.exists(server_path):
            print("📡 [1/3] Iniciando Servidor WebSocket...")
            p_server = subprocess.Popen([sys.executable, server_path])
            processes.append(p_server)
            time.sleep(1)
        else:
            print(
                f"⚠️ Servidor não encontrado em '{server_path}'. Pulando inicialização do servidor local..."
            )

        # 2. Inicia o Pygbag para compilar e servir o jogo em WebAssembly
        print("🎮 [2/3] Iniciando Pygbag (Frontend WebAssembly)...")
        p_pygbag = subprocess.Popen([sys.executable, "-m", "pygbag", "."])
        processes.append(p_pygbag)

        # Aguarda o Pygbag inicializar
        time.sleep(3)

        # 3. Abre o navegador automaticamente
        print("🌐 [3/3] Abrindo http://localhost:8000 no navegador...")
        webbrowser.open("http://localhost:8000")

        print("\n✅ Aplicação rodando perfeitamente!")
        print("💡 Pressione CTRL + C neste terminal para encerrar tudo.\n")
        print("⚠️  Lembre-se: Para jogar multiplayer, abra mais uma aba em http://localhost:8000\n")

        # Mantém o script rodando
        for p in processes:
            p.wait()

    except KeyboardInterrupt:
        print("\n\n🛑 Encerrando aplicação e finalizando processos...")
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass
        print("✨ Aplicação encerrada com sucesso!")


if __name__ == "__main__":
    start_application()