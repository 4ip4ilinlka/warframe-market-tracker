"""Entry point: start the local server and open the browser tab."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from . import config

URL = f"http://{config.HOST}:{config.PORT}"


def port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((config.HOST, config.PORT)) == 0


def open_browser_later() -> None:
    if os.environ.get("WFMT_NO_BROWSER") == "1":  # used by smoke tests
        return

    def run():
        for _ in range(50):
            if port_in_use():
                break
            time.sleep(0.2)
        webbrowser.open(URL)

    threading.Thread(target=run, daemon=True).start()


def main() -> None:
    # Windowed .exe has no console: give stray writes somewhere to go.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    if port_in_use():  # already running: just open the tab
        webbrowser.open(URL)
        return
    log_file = config.data_dir() / "wfmt.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=2, encoding="utf-8")],
    )
    from .server import create_app

    open_browser_later()
    app = create_app()
    server = uvicorn.Server(
        uvicorn.Config(app, host=config.HOST, port=config.PORT, log_config=None, access_log=False)
    )
    app.state.server = server  # lets the quit button stop the program
    server.run()


if __name__ == "__main__":
    main()
