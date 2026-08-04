"""Durable task records for smart-canvas image and video generation."""

from __future__ import annotations

import copy
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


_SECRET_KEYS = {
    "api_key",
    "apikey",
    "api-key",
    "authorization",
    "access_token",
    "refresh_token",
    "secret",
    "password",
}


def strip_secrets(value: Any) -> Any:
    """Return a deep copy with credentials removed from mappings."""
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in _SECRET_KEYS or normalized.endswith("_api_key"):
                continue
            cleaned[str(key)] = strip_secrets(child)
        return cleaned
    if isinstance(value, list):
        return [strip_secrets(item) for item in value]
    if isinstance(value, tuple):
        return [strip_secrets(item) for item in value]
    return copy.deepcopy(value)


class CanvasMediaTaskStore:
    """Thread-safe, atomically persisted image/video task store."""

    TERMINAL = {"succeeded", "failed"}

    def __init__(
        self, path: Union[str, Path], recovery_seconds: int = 86400
    ) -> None:
        self.path = Path(path)
        self.recovery_seconds = int(recovery_seconds)
        self._lock = threading.RLock()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.path.exists():
                return
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                return
            raw_tasks = payload.get("tasks", payload) if isinstance(payload, dict) else {}
            if isinstance(raw_tasks, dict):
                self._tasks = {
                    str(task_id): strip_secrets(record)
                    for task_id, record in raw_tasks.items()
                    if isinstance(record, dict)
                }

    def _save_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = Path(str(self.path) + ".tmp")
        serialized = json.dumps(
            {"version": 1, "tasks": self._tasks},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, self.path)

    def _copy(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return copy.deepcopy(record)

    def create(
        self,
        kind: str,
        provider_id: str,
        model: str,
        payload: Dict[str, Any],
        canvas_id: str = "",
        node_id: str = "",
    ) -> Dict[str, Any]:
        now = time.time()
        task_id = f"canvas_media_{uuid.uuid4().hex}"
        record = {
            "id": task_id,
            "kind": str(kind),
            "provider_id": str(provider_id),
            "model": str(model),
            "payload": strip_secrets(payload or {}),
            "canvas_id": str(canvas_id or ""),
            "node_id": str(node_id or ""),
            "status": "queued",
            "upstream_task_id": "",
            "idempotency_key": f"infinitecanvas:{task_id}",
            "created_at": now,
            "updated_at": now,
            "recovery_deadline": now + self.recovery_seconds,
            "result": None,
            "error": "",
            "attempt": 0,
        }
        with self._lock:
            self._tasks[task_id] = record
            self._save_locked()
            return self._copy(record)

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._tasks.get(str(task_id))
            return self._copy(record) if record is not None else None

    def list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [self._copy(record) for record in self._tasks.values()]

    def patch(self, task_id: str, **changes: Any) -> Dict[str, Any]:
        with self._lock:
            record = self._tasks.get(str(task_id))
            if record is None:
                raise KeyError(task_id)
            safe_changes = strip_secrets(changes)
            record.update(safe_changes)
            if "updated_at" not in changes:
                record["updated_at"] = time.time()
            self._save_locked()
            return self._copy(record)

    def recoverable(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        current = time.time() if now is None else float(now)
        with self._lock:
            return [
                self._copy(record)
                for record in self._tasks.values()
                if record.get("status") not in self.TERMINAL | {"manual"}
                and float(record.get("recovery_deadline") or 0) >= current
            ]

    def mark_expired(self, now: Optional[float] = None) -> List[str]:
        current = time.time() if now is None else float(now)
        expired: List[str] = []
        with self._lock:
            for task_id, record in self._tasks.items():
                if record.get("status") in self.TERMINAL | {"manual"}:
                    continue
                if float(record.get("recovery_deadline") or 0) < current:
                    record["status"] = "manual"
                    record["updated_at"] = current
                    expired.append(task_id)
            if expired:
                self._save_locked()
        return expired

    def cleanup(
        self, now: Optional[float] = None, retention_seconds: int = 604800
    ) -> List[str]:
        current = time.time() if now is None else float(now)
        cutoff = current - float(retention_seconds)
        removed: List[str] = []
        with self._lock:
            for task_id, record in list(self._tasks.items()):
                if (
                    record.get("status") in self.TERMINAL
                    and float(record.get("updated_at") or 0) < cutoff
                ):
                    removed.append(task_id)
                    del self._tasks[task_id]
            if removed:
                self._save_locked()
        return removed
