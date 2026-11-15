"""Aplicativo de janela para Windows.

Inicia o servidor local em uma thread e abre uma janela nativa com
``pywebview`` (WebView2/Edge, já presente no Windows 10/11). Sem pywebview,
abre o navegador padrão. Empacotável em um único .exe com PyInstaller
(ver ``packaging/build_windows.ps1``).
"""
from __future__ import annotations

import socket
import threading
import time
import webbrowser


def _free_port(preferred: int = 8765) -> int:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def main() -> None:
    import uvicorn

    from .server import build

    port = _free_port()
    _core, app = build()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    url = f"http://127.0.0.1:{port}/"
    try:
        import webview  # pywebview
    except ImportError:
        webbrowser.open(url)
        print(f"Interface em {url} (instale 'pywebview' para janela nativa). Ctrl+C para sair.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        webview.create_window("Xiaomi 1C Control", url, width=1360, height=880, min_size=(900, 600))
        webview.start()
    server.should_exit = True


if __name__ == "__main__":
    main()
