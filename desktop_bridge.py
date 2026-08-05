import logging
import threading
from typing import Any


LOGGER = logging.getLogger("infinitecanvas.desktop")
_LOCK = threading.RLock()
_DESKTOP_API: Any = None


def register_desktop_api(api: Any) -> None:
    global _DESKTOP_API
    with _LOCK:
        _DESKTOP_API = api
    LOGGER.info("Desktop HTTP bridge registered")


def unregister_desktop_api(api: Any = None) -> None:
    global _DESKTOP_API
    with _LOCK:
        if api is None or _DESKTOP_API is api:
            _DESKTOP_API = None


def dispatch_desktop_action(
    action: str,
    kind: str = "",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with _LOCK:
        api = _DESKTOP_API
    if api is None:
        return {"ok": False, "error_code": "desktop_api_unavailable"}

    action = str(action or "")
    kind = str(kind or "")
    payload = payload if isinstance(payload, dict) else {}
    try:
        if action == "choose-download-directory":
            return api.choose_download_directory()
        if action == "choose-directory":
            return api.choose_directory(kind)
        if action == "open-directory":
            return api.open_directory(kind)
        if action == "install-update":
            return api.install_update(
                str(payload.get("url") or ""),
                str(payload.get("version") or ""),
            )
        return {"ok": False, "error_code": "desktop_action_unknown"}
    except Exception as exc:
        LOGGER.exception("Desktop HTTP action failed: action=%s kind=%s", action, kind)
        return {
            "ok": False,
            "error_code": "desktop_action_failed",
            "message": str(exc),
        }
