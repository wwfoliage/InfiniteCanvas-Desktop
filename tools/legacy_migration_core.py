from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


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
    expected_counts: dict[str, int] = field(default_factory=dict)
    conflicts: dict[str, int] = field(default_factory=dict)
    protected_hashes: dict[str, str | None] = field(default_factory=dict)
    workflow_hashes: dict[str, str] = field(default_factory=dict)
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


def merge_asset_libraries(
    current: dict[str, Any], legacy: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    merged = copy.deepcopy(current)
    libraries = merged.setdefault("libraries", [])
    by_id = {str(item.get("id")): item for item in libraries}
    id_map: dict[str, str] = {}

    for item in legacy.get("libraries", []):
        old_id = str(item.get("id"))
        candidate = copy.deepcopy(item)
        existing = by_id.get(old_id)
        if existing is not None and existing != candidate:
            candidate["id"] = stable_legacy_id("asset_library", old_id)
            candidate["name"] = legacy_name(candidate.get("name", ""))

        candidate_id = str(candidate["id"])
        id_map[old_id] = candidate_id
        if candidate_id not in by_id:
            libraries.append(candidate)
            by_id[candidate_id] = candidate

    return merged, id_map


def _semantic_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in {"created_at", "updated_at"}
    }


def merge_prompt_libraries(
    current: dict[str, Any], legacy: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    merged = copy.deepcopy(current)
    libraries = merged.setdefault("libraries", [])
    libraries_by_id = {str(item.get("id")): item for item in libraries}
    id_map: dict[str, str] = {}

    for legacy_library in legacy.get("libraries", []):
        library_id = str(legacy_library.get("id"))
        current_library = libraries_by_id.get(library_id)
        if current_library is None:
            candidate_library = copy.deepcopy(legacy_library)
            libraries.append(candidate_library)
            libraries_by_id[library_id] = candidate_library
            for item in candidate_library.get("items", []):
                item_id = str(item.get("id"))
                id_map[item_id] = item_id
            continue

        current_items = current_library.setdefault("items", [])
        items_by_id = {str(item.get("id")): item for item in current_items}
        for legacy_item in legacy_library.get("items", []):
            old_id = str(legacy_item.get("id"))
            candidate = copy.deepcopy(legacy_item)
            existing = items_by_id.get(old_id)
            if existing is not None and _semantic_record(existing) != _semantic_record(candidate):
                candidate["id"] = stable_legacy_id("prompt", old_id)
                candidate["name"] = legacy_name(candidate.get("name", ""))

            candidate_id = str(candidate["id"])
            id_map[old_id] = candidate_id
            if candidate_id not in items_by_id:
                current_items.append(candidate)
                items_by_id[candidate_id] = candidate

        current_categories = current_library.setdefault("categories", [])
        category_ids = {str(item.get("id")) for item in current_categories}
        for category in legacy_library.get("categories", []):
            if str(category.get("id")) not in category_ids:
                current_categories.append(copy.deepcopy(category))
                category_ids.add(str(category.get("id")))

    return merged, id_map


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_copy_target(
    source: Path, relative_target: Path, target_root: Path
) -> tuple[Path, bool]:
    destination = target_root / relative_target
    if not destination.exists() or sha256_file(source) == sha256_file(destination):
        return relative_target, False

    digest = sha256_file(source)[:8]
    base_name = f"{relative_target.stem}（旧版-{digest}）"
    candidate = relative_target.with_name(f"{base_name}{relative_target.suffix}")
    counter = 2
    while (target_root / candidate).exists():
        if sha256_file(source) == sha256_file(target_root / candidate):
            return candidate, True
        candidate = relative_target.with_name(
            f"{base_name}-{counter}{relative_target.suffix}"
        )
        counter += 1
    return candidate, True


def rewrite_asset_urls(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: rewrite_asset_urls(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_asset_urls(item, mapping) for item in value]
    if isinstance(value, str):
        return mapping.get(value, value)
    return value


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationError(f"Unable to read JSON {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _library_items(library_data: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for library in library_data.get("libraries", []):
        for category in library.get("categories", []):
            items.extend(category.get("items", []) or [])
    return items


def _prompt_items(prompt_data: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for library in prompt_data.get("libraries", []):
        items.extend(library.get("items", []) or [])
    return items


def _asset_path_from_url(root: Path, url: str) -> Path | None:
    clean_path = unquote(urlsplit(str(url)).path)
    if not clean_path.startswith("/assets/"):
        return None
    return root / clean_path.lstrip("/")


def _count_files(path: Path, pattern: str = "*") -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob(pattern) if item.is_file())


def validate_tree(
    root: Path,
    *,
    workflow_root: Path | None = None,
    protected_hashes: dict[str, str | None] | None = None,
) -> dict[str, int]:
    root = root.resolve()
    projects = read_json(root / "data" / "projects.json")
    history = read_json(root / "history.json")
    asset_library = read_json(root / "data" / "asset_library.json")
    prompt_library = read_json(root / "data" / "prompt_libraries.json")

    project_ids = {str(item.get("id")) for item in projects.get("projects", [])}
    canvas_files = sorted((root / "data" / "canvases").glob("*.json"))
    for canvas_file in canvas_files:
        canvas = read_json(canvas_file)
        project_id = str(canvas.get("project", "default"))
        if project_id not in project_ids:
            raise MigrationError(
                f"Canvas {canvas_file.name} references missing project {project_id}"
            )

    asset_items = _library_items(asset_library)
    for item in asset_items:
        asset_path = _asset_path_from_url(root, str(item.get("url", "")))
        if asset_path is not None and not asset_path.is_file():
            raise MigrationError(
                f"Asset library item {item.get('id')} references missing asset {asset_path}"
            )

    for relative, expected_hash in (protected_hashes or {}).items():
        protected_path = root / Path(relative)
        if expected_hash is None:
            if protected_path.exists():
                raise MigrationError(f"unexpected protected file appeared: {relative}")
            continue
        if not protected_path.is_file() or sha256_file(protected_path) != expected_hash:
            raise MigrationError(f"protected file changed: {relative}")

    workflows = 0
    if workflow_root is not None:
        workflows = _count_files(workflow_root, "*.json")

    return {
        "assets": _count_files(root / "assets"),
        "canvases": len(canvas_files),
        "history": len(history) if isinstance(history, list) else 0,
        "previews": _count_files(root / "data" / "media_previews"),
        "projects": len(projects.get("projects", [])),
        "asset_items": len(asset_items),
        "prompt_items": len(_prompt_items(prompt_library)),
        "workflows": workflows,
    }
