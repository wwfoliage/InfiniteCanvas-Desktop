from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any


LEGACY_SUFFIX = "（旧版）"


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class MigrationPaths:
    source_root: Path
    target_root: Path
    backup_root: Path
    report_root: Path
    workflow_root: Path | None = None


@dataclass
class MigrationPlan:
    run_id: str
    paths: MigrationPaths
    project_id_map: dict[str, str] = field(default_factory=dict)
    asset_library_id_map: dict[str, str] = field(default_factory=dict)
    prompt_id_map: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    conflicts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def stable_legacy_id(kind: str, original_id: str) -> str:
    value = f"InfiniteCanvas:{kind}:{original_id}".encode("utf-8")
    return f"legacy_{kind}_{sha256(value).hexdigest()[:24]}"


def legacy_name(name: str) -> str:
    clean = str(name or "旧版数据").strip()
    return clean if clean.endswith(LEGACY_SUFFIX) else f"{clean}{LEGACY_SUFFIX}"


def merge_projects(
    current: dict[str, Any], legacy: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    merged = [dict(item) for item in current.get("projects", [])]
    by_id = {str(item.get("id")): item for item in merged}
    id_map: dict[str, str] = {}

    for item in legacy.get("projects", []):
        old_id = str(item.get("id"))
        candidate = dict(item)
        existing = by_id.get(old_id)
        if existing is not None and existing != candidate:
            candidate["id"] = stable_legacy_id("project", old_id)
            candidate["name"] = legacy_name(candidate.get("name", ""))

        candidate_id = str(candidate["id"])
        id_map[old_id] = candidate_id
        if candidate_id not in by_id:
            merged.append(candidate)
            by_id[candidate_id] = candidate

    for order, item in enumerate(merged):
        item["order"] = order
    return {"projects": merged}, id_map


def rewrite_canvas_project(
    canvas: dict[str, Any], project_id_map: dict[str, str]
) -> dict[str, Any]:
    result = dict(canvas)
    project = str(result.get("project", "default"))
    result["project"] = project_id_map.get(project, project)
    return result


def history_key(item: dict[str, Any]) -> tuple[Any, ...]:
    if item.get("task_id"):
        return ("task", str(item["task_id"]))
    if item.get("request_id"):
        return ("request", str(item["request_id"]))
    return (
        "fallback",
        float(item.get("timestamp", 0)),
        tuple(str(value) for value in item.get("images", [])),
    )


def merge_history(
    current: list[dict[str, Any]], legacy: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    records: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in [*current, *legacy]:
        records.setdefault(history_key(item), dict(item))
    return sorted(
        records.values(),
        key=lambda item: float(item.get("timestamp", 0)),
        reverse=True,
    )
