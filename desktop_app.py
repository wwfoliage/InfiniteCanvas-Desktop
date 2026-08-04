from __future__ import annotations

import ctypes
import logging
import multiprocessing
import socket
import sys
import threading
import time
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import uvicorn

from app_paths import ensure_user_directories, resolve_app_paths


LOGGER = logging.getLogger("infinitecanvas.desktop")


def reserve_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def configure_logging(logs_dir: Path) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "desktop.log"
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
    for handler in list(LOGGER.handlers):
        handler.close()
        LOGGER.removeHandler(handler)
    handler = RotatingFileHandler(
        log_file,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)
    return log_file


def close_logging() -> None:
    for handler in list(LOGGER.handlers):
        handler.flush()
        handler.close()
        LOGGER.removeHandler(handler)


class UvicornRuntime:
    def __init__(self, app: Any, host: str = "127.0.0.1", port: int | None = None):
        if host != "127.0.0.1":
            raise ValueError("The desktop server must bind to 127.0.0.1")
        self.app = app
        self.host = host
        self.port = port or reserve_loopback_port()
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None
        self.error: BaseException | None = None

    def _serve(self) -> None:
        try:
            assert self.server is not None
            self.server.run()
        except BaseException as exc:
            self.error = exc
            LOGGER.exception("Desktop server stopped unexpectedly")

    def start(self, timeout: float = 15.0) -> str:
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_config=None,
            access_log=False,
            ws_ping_interval=None,
            ws_ping_timeout=None,
        )
        self.server = uvicorn.Server(config)
        self.server.should_exit = False
        self.thread = threading.Thread(
            target=self._serve,
            name="InfiniteCanvasServer",
            daemon=False,
        )
        self.thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if bool(getattr(self.server, "started", False)):
                LOGGER.info("Desktop server started on %s:%s", self.host, self.port)
                return f"http://{self.host}:{self.port}/"
            if self.error is not None:
                raise RuntimeError("InfiniteCanvas local service failed to start") from self.error
            if not self.thread.is_alive():
                raise RuntimeError("InfiniteCanvas local service exited during startup")
            time.sleep(0.05)
        self.stop()
        raise RuntimeError("InfiniteCanvas local service did not become ready in time")

    def stop(self, timeout: float = 5.0) -> None:
        if self.server is not None:
            self.server.should_exit = True
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout)
            if self.thread.is_alive() and self.server is not None:
                self.server.force_exit = True
                self.thread.join(1.0)
        LOGGER.info("Desktop server stopped")


def run_window(webview_module: Any, runtime: UvicornRuntime, url: str) -> int:
    try:
        webview_module.create_window(
            "InfiniteCanvas",
            url,
            width=1440,
            height=900,
            min_size=(1024, 700),
        )
        webview_module.start(gui="edgechromium", debug=False, private_mode=False)
        return 0
    finally:
        runtime.stop()


def run_desktop() -> int:
    import webview
    from main import app

    paths = resolve_app_paths()
    ensure_user_directories(paths)
    configure_logging(paths.logs_dir)
    runtime = UvicornRuntime(app)
    url = runtime.start()
    try:
        return run_window(webview, runtime, url)
    finally:
        close_logging()


def show_fatal_error(message: str) -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(
            0,
            message,
            "InfiniteCanvas startup error",
            0x10,
        )


def main() -> int:
    try:
        return run_desktop()
    except BaseException:
        paths = resolve_app_paths()
        log_file = configure_logging(paths.logs_dir)
        LOGGER.error("Fatal desktop startup error\n%s", traceback.format_exc())
        show_fatal_error(
            "InfiniteCanvas failed to start.\n\n"
            f"See the log for details:\n{log_file}"
        )
        return 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
