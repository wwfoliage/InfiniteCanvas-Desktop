from __future__ import annotations

import copy
import ctypes
import json
import os
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID


DEFAULT_SETTINGS: dict[str, Any] = {
    "schema_version": 1,
    "downloads": {
        "directory": "",
        "categorize": True,
        "notify": True,
    },
    "appearance": {
        "theme": "system",
        "scale": "auto",
    },
    "language": "zh",
}

THEMES = {"system", "light", "dark"}
SCALES = {"auto", "80", "90", "100", "110", "125"}
LANGUAGES = {"zh", "en"}
DOWNLOADS_FOLDER_ID = UUID("374DE290-123F-4565-9164-39C4925E467B")


def _windows_downloads_directory() -> Path | None:
    if os.name != "nt":
        return None
    path_pointer = ctypes.c_wchar_p()
    folder_id = (ctypes.c_byte * 16).from_buffer_copy(DOWNLOADS_FOLDER_ID.bytes_le)
    try:
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id), 0, None, ctypes.byref(path_pointer)
        )
        if result != 0 or not path_pointer.value:
            return None
        return Path(path_pointer.value)
    except (AttributeError, OSError):
        return None
    finally:
        if path_pointer.value:
            ctypes.windll.ole32.CoTaskMemFree(path_pointer)


def default_download_directory() -> Path:
    downloads = _windows_downloads_directory() or (Path.home() / "Downloads")
    return (downloads / "InfiniteCanvas").resolve()


def _string(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _normalized_directory(value: Any) -> str:
    raw = _string(value)
    if not raw:
        return ""
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        return ""
    return str(candidate.resolve())


def normalize_settings(
    raw: Mapping[str, Any] | None,
    legacy: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source = raw if isinstance(raw, Mapping) else {}
    legacy_source = legacy if isinstance(legacy, Mapping) else {}
    downloads = source.get("downloads")
    appearance = source.get("appearance")
    downloads = downloads if isinstance(downloads, Mapping) else {}
    appearance = appearance if isinstance(appearance, Mapping) else {}

    legacy_theme = _string(legacy_source.get("studio_theme") or legacy_source.get("canvas_theme"))
    theme = _string(appearance.get("theme")) or legacy_theme or "system"
    if theme not in THEMES:
        theme = "system"

    legacy_scale = _string(legacy_source.get("studio_ui_scale_mode"))
    scale = _string(appearance.get("scale")) or legacy_scale or "auto"
    if scale not in SCALES:
        scale = "auto"

    language = _string(source.get("language")) or _string(legacy_source.get("studio_lang")) or "zh"
    if language not in LANGUAGES:
        language = "zh"

    return {
        "schema_version": 1,
        "downloads": {
            "directory": _normalized_directory(downloads.get("directory")),
            "categorize": _bool(downloads.get("categorize"), True),
            "notify": _bool(downloads.get("notify"), True),
        },
        "appearance": {"theme": theme, "scale": scale},
        "language": language,
    }


def _merge_known_fields(
    current: Mapping[str, Any], patch: Mapping[str, Any]
) -> dict[str, Any]:
    merged = copy.deepcopy(dict(current))
    downloads = patch.get("downloads")
    if isinstance(downloads, Mapping):
        target = merged.setdefault("downloads", {})
        for key in ("directory", "categorize", "notify"):
            if key in downloads:
                target[key] = downloads[key]
    appearance = patch.get("appearance")
    if isinstance(appearance, Mapping):
        target = merged.setdefault("appearance", {})
        for key in ("theme", "scale"):
            if key in appearance:
                target[key] = appearance[key]
    if "language" in patch:
        merged["language"] = patch["language"]
    return merged


def settings_for_client(settings: Mapping[str, Any]) -> dict[str, Any]:
    result = normalize_settings(settings)
    result["downloads"]["resolved_directory"] = str(
        Path(result["downloads"]["directory"])
        if result["downloads"]["directory"]
        else default_download_directory()
    )
    return result


class AppSettingsStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._lock = threading.RLock()

    def load(self, legacy: Mapping[str, str] | None = None) -> dict[str, Any]:
        with self._lock:
            raw: Mapping[str, Any] | None = None
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                raw = loaded if isinstance(loaded, Mapping) else None
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                raw = None
            return normalize_settings(raw, legacy=legacy)

    def update(self, patch: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            current = self.load()
            normalized = normalize_settings(_merge_known_fields(current, patch))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
            try:
                with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                    json.dump(normalized, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            finally:
                temporary.unlink(missing_ok=True)
            return normalized
