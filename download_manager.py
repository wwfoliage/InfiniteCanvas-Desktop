from __future__ import annotations

import errno
import mimetypes
import os
import re
import shutil
import threading
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO

from app_paths import AppPaths
from app_settings import AppSettingsStore, default_download_directory


CATEGORIES = {"图片", "视频", "音频", "工作流", "画布导出", "其他"}
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
IMAGE_EXTENSIONS = {".avif", ".bmp", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".svg", ".tif", ".tiff", ".webp"}
VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"}
AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".oga", ".ogg", ".opus", ".wav"}
WORKFLOW_EXTENSIONS = {".json", ".workflow"}
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
PATH_SEPARATORS = re.compile(r"[\\/]+")


class DownloadError(RuntimeError):
    code = "download_failed"


class DownloadValidationError(DownloadError):
    code = "invalid_download"


class DownloadWriteError(DownloadError):
    code = "write_failed"


class DownloadRemoteError(DownloadError):
    code = "remote_failed"


class DownloadSizeError(DownloadError):
    code = "file_too_large"


@dataclass(frozen=True)
class DownloadRequest:
    filename: str
    category: str = ""
    content_type: str = ""


@dataclass(frozen=True)
class DownloadResult:
    ok: bool
    filename: str
    category: str
    path: str
    error_code: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def sanitize_filename(name: str, fallback: str = "download") -> str:
    clean = CONTROL_CHARACTERS.sub("", str(name or "").strip())
    clean = PATH_SEPARATORS.sub("_", clean)
    clean = clean.strip(" .")
    if not clean or clean in {".", ".."}:
        clean = fallback
    suffix = Path(clean).suffix
    stem = clean[: -len(suffix)] if suffix else clean
    if stem.rstrip(" .").upper() in WINDOWS_RESERVED_NAMES:
        clean = f"_{clean}"
    clean = clean.rstrip(" .")
    if not clean:
        clean = fallback
    if len(clean) > 240:
        suffix = Path(clean).suffix[:20]
        stem = clean[: -len(suffix)] if suffix else clean
        clean = f"{stem[: 240 - len(suffix)]}{suffix}"
    return clean


def classify_download(filename: str, content_type: str = "", requested: str = "") -> str:
    if requested:
        if requested not in CATEGORIES:
            raise DownloadValidationError("Unsupported download category")
        return requested
    mime = str(content_type or "").split(";", 1)[0].strip().lower()
    if mime.startswith("image/"):
        return "图片"
    if mime.startswith("video/"):
        return "视频"
    if mime.startswith("audio/"):
        return "音频"
    extension = Path(filename).suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        return "图片"
    if extension in VIDEO_EXTENSIONS:
        return "视频"
    if extension in AUDIO_EXTENSIONS:
        return "音频"
    if extension in WORKFLOW_EXTENSIONS:
        return "工作流"
    return "其他"


def _directory_size(path: Path) -> int:
    total = 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    if not path.is_dir():
        return 0
    for root, _, files in os.walk(path):
        for filename in files:
            try:
                total += (Path(root) / filename).stat().st_size
            except OSError:
                continue
    return total


def _assert_allowed_root(path: Path, allowed_root: Path) -> Path:
    resolved = path.resolve()
    root = allowed_root.resolve()
    if resolved != root and root not in resolved.parents:
        raise DownloadValidationError("Cache target is outside the allowed root")
    return resolved


def _clear_directory(directory: Path) -> tuple[int, int]:
    root = _assert_allowed_root(directory, directory)
    removed_bytes = _directory_size(root)
    removed_items = 0
    if not root.exists():
        return 0, 0
    for child in list(root.iterdir()):
        target = _assert_allowed_root(child, root)
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
        removed_items += 1
    return removed_bytes, removed_items


def cache_cleanup_preview(paths: AppPaths) -> dict[str, Any]:
    entries = [
        {"kind": "media_previews", "path": str(paths.media_preview_dir), "bytes": _directory_size(paths.media_preview_dir)},
        {"kind": "download_temp", "path": str(paths.download_temp_dir), "bytes": _directory_size(paths.download_temp_dir)},
    ]
    return {"ok": True, "bytes": sum(item["bytes"] for item in entries), "entries": entries}


def clear_rebuildable_cache(paths: AppPaths) -> dict[str, Any]:
    removed_bytes = 0
    removed_items = 0
    for directory in (paths.media_preview_dir, paths.download_temp_dir):
        size, count = _clear_directory(directory)
        removed_bytes += size
        removed_items += count
        directory.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "removed_bytes": removed_bytes, "removed_items": removed_items}


def storage_report(paths: AppPaths, settings: Mapping[str, Any]) -> dict[str, Any]:
    configured = str(settings.get("downloads", {}).get("directory", "")) if isinstance(settings.get("downloads"), Mapping) else ""
    download_root = Path(configured) if configured else default_download_directory()
    entries = [
        {"kind": "projects", "path": str(paths.runtime_data_dir), "bytes": _directory_size(paths.runtime_data_dir)},
        {"kind": "assets", "path": str(paths.assets_dir), "bytes": _directory_size(paths.assets_dir)},
        {"kind": "cache", "path": str(paths.media_preview_dir), "bytes": _directory_size(paths.media_preview_dir)},
        {"kind": "logs", "path": str(paths.logs_dir), "bytes": _directory_size(paths.logs_dir)},
        {"kind": "downloads", "path": str(download_root), "bytes": _directory_size(download_root)},
    ]
    return {"ok": True, "total_bytes": sum(item["bytes"] for item in entries), "entries": entries}


def iter_file_chunks(file: BinaryIO, limit: int, chunk_size: int = 1024 * 1024) -> Iterable[bytes]:
    total = 0
    while True:
        chunk = file.read(chunk_size)
        if not chunk:
            return
        total += len(chunk)
        if total > limit:
            raise DownloadSizeError(f"Download exceeds {limit} bytes")
        yield chunk


class DownloadManager:
    def __init__(
        self,
        paths: AppPaths,
        settings_store: AppSettingsStore,
        local_resolver: Callable[[str], Path | None] | None = None,
        opener: Callable[..., Any] | None = None,
    ):
        self.paths = paths
        self.settings_store = settings_store
        self.local_resolver = local_resolver
        self.opener = opener or urllib.request.urlopen
        self._lock = threading.RLock()

    def _download_root(self) -> Path:
        settings = self.settings_store.load()
        configured = str(settings["downloads"].get("directory") or "")
        root = Path(configured) if configured else default_download_directory()
        if not root.is_absolute():
            raise DownloadValidationError("Download directory must be absolute")
        if root.exists() and not root.is_dir():
            raise DownloadWriteError("Download directory is not a folder")
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise DownloadWriteError("Download directory is unavailable") from exc
        return root.resolve()

    def _destination_directory(self, category: str) -> Path:
        root = self._download_root()
        settings = self.settings_store.load()
        return root / category if settings["downloads"].get("categorize", True) else root

    @staticmethod
    def _unique_destination(directory: Path, filename: str) -> Path:
        candidate = directory / filename
        stem = candidate.stem
        suffix = candidate.suffix
        number = 1
        while candidate.exists():
            candidate = directory / f"{stem} ({number}){suffix}"
            number += 1
        return candidate

    def _commit_part(self, part: Path, destination: Path) -> None:
        try:
            os.replace(part, destination)
            return
        except OSError as exc:
            if exc.errno != errno.EXDEV:
                raise
        local_part = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.part"
        try:
            with part.open("rb") as source, local_part.open("xb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
                target.flush()
                os.fsync(target.fileno())
            os.replace(local_part, destination)
            part.unlink(missing_ok=True)
        finally:
            local_part.unlink(missing_ok=True)

    def save_stream(self, request: DownloadRequest, chunks: Iterable[bytes]) -> DownloadResult:
        filename = sanitize_filename(request.filename)
        category = classify_download(filename, request.content_type, request.category)
        with self._lock:
            directory = self._destination_directory(category)
            try:
                directory.mkdir(parents=True, exist_ok=True)
                destination = self._unique_destination(directory, filename)
                self.paths.download_temp_dir.mkdir(parents=True, exist_ok=True)
                part = self.paths.download_temp_dir / f"{uuid.uuid4().hex}.part"
                try:
                    with part.open("xb") as handle:
                        for chunk in chunks:
                            if chunk:
                                handle.write(chunk)
                        handle.flush()
                        os.fsync(handle.fileno())
                    self._commit_part(part, destination)
                finally:
                    part.unlink(missing_ok=True)
            except DownloadError:
                raise
            except OSError as exc:
                raise DownloadWriteError("Failed to save download") from exc
        return DownloadResult(True, destination.name, category, str(destination))

    def save_url(self, request: DownloadRequest, url: str) -> DownloadResult:
        parsed = urllib.parse.urlsplit(str(url or "").strip())
        if parsed.scheme in {"http", "https"}:
            try:
                request_object = urllib.request.Request(url, headers={"User-Agent": "InfiniteCanvas/1"})
                with self.opener(request_object, timeout=30) as response:
                    content_type = response.headers.get_content_type() if response.headers else ""
                    effective_request = DownloadRequest(request.filename, request.category, request.content_type or content_type)
                    return self.save_stream(effective_request, iter(lambda: response.read(1024 * 1024), b""))
            except DownloadError:
                raise
            except Exception as exc:
                raise DownloadRemoteError("Remote download failed") from exc
        if parsed.scheme == "" and str(url).startswith("/") and self.local_resolver:
            source = self.local_resolver(str(url))
            if source and source.is_file():
                guessed_type = request.content_type or mimetypes.guess_type(source.name)[0] or ""
                with source.open("rb") as handle:
                    return self.save_stream(
                        DownloadRequest(request.filename, request.category, guessed_type),
                        iter(lambda: handle.read(1024 * 1024), b""),
                    )
        raise DownloadValidationError("Unsupported download URL")
