from __future__ import annotations

import argparse
import csv
import io
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from tools.legacy_migration_core import (
        MigrationError,
        MigrationPaths,
        MigrationPlan,
        merge_asset_libraries,
        merge_history,
        merge_projects,
        merge_prompt_libraries,
        read_json,
        resolve_copy_target,
        sha256_file,
        validate_tree,
        write_json,
    )
except ModuleNotFoundError:
    from legacy_migration_core import (  # type: ignore[no-redef]
        MigrationError,
        MigrationPaths,
        MigrationPlan,
        merge_asset_libraries,
        merge_history,
        merge_projects,
        merge_prompt_libraries,
        read_json,
        resolve_copy_target,
        sha256_file,
        validate_tree,
        write_json,
    )


PROTECTED_RELATIVE_PATHS = (
    "API/.env",
    "data/api_providers.json",
    "global_config.json",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Safely migrate InfiniteCanvas legacy user data"
    )
    parser.add_argument("--source", type=Path, default=Path(r"E:\InfiniteCanvas"))
    parser.add_argument("--target", type=Path, default=local_app_data / "InfiniteCanvas")
    parser.add_argument("--workflow-root", type=Path, default=project_root / "workflows")
    parser.add_argument(
        "--backup-root", type=Path, default=Path(r"E:\codex\无限画布资料\迁移备份")
    )
    parser.add_argument(
        "--report-root", type=Path, default=Path(r"E:\codex\无限画布资料\迁移记录")
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply", action="store_true", help="Apply the validated plan; default is dry-run"
    )
    mode.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the current target and workflow resources without migration",
    )
    return parser.parse_args(argv)


def is_infinitecanvas_running() -> bool:
    if os.name != "nt":
        return False
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [
                "tasklist",
                "/FI",
                "IMAGENAME eq InfiniteCanvas.exe",
                "/FO",
                "CSV",
                "/NH",
            ],
            capture_output=True,
            text=True,
            check=False,
            creationflags=creation_flags,
        )
    except OSError:
        return True
    if result.returncode != 0:
        return True
    for row in csv.reader(io.StringIO(result.stdout)):
        if row and row[0].strip().casefold() == "infinitecanvas.exe":
            return True
    return False


def _required_json(root: Path) -> tuple[Path, ...]:
    return (
        root / "history.json",
        root / "data" / "projects.json",
        root / "data" / "asset_library.json",
        root / "data" / "prompt_libraries.json",
    )


def _protected_hashes(target: Path) -> dict[str, str | None]:
    hashes: dict[str, str | None] = {}
    for relative in PROTECTED_RELATIVE_PATHS:
        path = target / Path(relative)
        hashes[relative] = sha256_file(path) if path.is_file() else None
    return hashes


def _workflow_hashes(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise MigrationError(f"Workflow directory is missing: {root}")
    return {
        path.name: sha256_file(path)
        for path in sorted(root.glob("*.json"))
        if path.is_file()
    }


def _count_files(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file())


def _count_asset_items(value: dict[str, Any]) -> int:
    return sum(
        len(category.get("items", []) or [])
        for library in value.get("libraries", [])
        for category in library.get("categories", [])
    )


def _count_prompt_items(value: dict[str, Any]) -> int:
    return sum(
        len(library.get("items", []) or []) for library in value.get("libraries", [])
    )


def _planned_file_total(source: Path, target: Path) -> tuple[int, int]:
    total = _count_files(target)
    conflicts = 0
    if not source.exists():
        return total, conflicts
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        planned_relative, renamed = resolve_copy_target(path, relative, target)
        if renamed:
            conflicts += 1
        if not (target / planned_relative).is_file():
            total += 1
    return total, conflicts


def _assert_required_data(root: Path, label: str) -> None:
    if not root.is_dir():
        raise MigrationError(f"{label} directory is missing: {root}")
    missing = [str(path) for path in _required_json(root) if not path.is_file()]
    if missing:
        raise MigrationError(f"{label} required files are missing: {', '.join(missing)}")


def build_plan(paths: MigrationPaths, run_id: str | None = None) -> MigrationPlan:
    source = paths.source_root.resolve()
    target = paths.target_root.resolve()
    workflow_root = (paths.workflow_root or source / "workflows").resolve()
    normalized_paths = MigrationPaths(
        source_root=source,
        target_root=target,
        backup_root=paths.backup_root.resolve(),
        report_root=paths.report_root.resolve(),
        workflow_root=workflow_root,
    )
    _assert_required_data(source, "Legacy source")
    _assert_required_data(target, "Desktop target")

    protected = _protected_hashes(target)
    source_workflows = _workflow_hashes(source / "workflows")
    current_workflows = _workflow_hashes(workflow_root)
    if source_workflows != current_workflows:
        raise MigrationError("Legacy and desktop workflow hashes do not match")

    validate_tree(source, workflow_root=source / "workflows")
    current_counts = validate_tree(
        target, workflow_root=workflow_root, protected_hashes=protected
    )

    current_projects = read_json(target / "data" / "projects.json")
    legacy_projects = read_json(source / "data" / "projects.json")
    merged_projects, project_map = merge_projects(current_projects, legacy_projects)

    current_assets = read_json(target / "data" / "asset_library.json")
    legacy_assets = read_json(source / "data" / "asset_library.json")
    merged_assets, asset_library_map = merge_asset_libraries(
        current_assets, legacy_assets
    )

    current_prompts = read_json(target / "data" / "prompt_libraries.json")
    legacy_prompts = read_json(source / "data" / "prompt_libraries.json")
    merged_prompts, prompt_map = merge_prompt_libraries(current_prompts, legacy_prompts)

    current_history = read_json(target / "history.json")
    legacy_history = read_json(source / "history.json")
    merged_history = merge_history(current_history, legacy_history)

    asset_total, asset_conflicts = _planned_file_total(
        source / "assets", target / "assets"
    )
    preview_total, preview_conflicts = _planned_file_total(
        source / "data" / "media_previews", target / "data" / "media_previews"
    )
    canvas_total, canvas_conflicts = _planned_file_total(
        source / "data" / "canvases", target / "data" / "canvases"
    )

    plan = MigrationPlan(
        run_id=run_id or datetime.now().strftime("%Y%m%d-%H%M%S"),
        paths=normalized_paths,
        project_id_map=project_map,
        asset_library_id_map=asset_library_map,
        prompt_id_map=prompt_map,
        protected_hashes=protected,
        workflow_hashes=current_workflows,
    )
    plan.counts = {
        "legacy_assets": _count_files(source / "assets"),
        "legacy_canvases": _count_files(source / "data" / "canvases"),
        "legacy_history": len(legacy_history),
        "legacy_previews": _count_files(source / "data" / "media_previews"),
        "legacy_asset_items": _count_asset_items(legacy_assets),
        "legacy_unique_prompts": _count_prompt_items(merged_prompts)
        - _count_prompt_items(current_prompts),
    }
    plan.expected_counts = {
        **current_counts,
        "assets": asset_total,
        "canvases": canvas_total,
        "history": len(merged_history),
        "previews": preview_total,
        "projects": len(merged_projects.get("projects", [])),
        "asset_items": _count_asset_items(merged_assets),
        "prompt_items": _count_prompt_items(merged_prompts),
        "workflows": len(current_workflows),
    }
    plan.conflicts = {
        "asset_files": asset_conflicts,
        "canvas_files": canvas_conflicts,
        "preview_files": preview_conflicts,
    }
    return plan


def redacted_report(
    plan: MigrationPlan,
    *,
    mode: str,
    status: str,
    backup_path: Path | None = None,
    validation: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "run_id": plan.run_id,
        "mode": mode,
        "status": status,
        "source": str(plan.paths.source_root),
        "target": str(plan.paths.target_root),
        "counts": dict(plan.counts),
        "expected_counts": dict(plan.expected_counts),
        "conflicts": dict(plan.conflicts),
        "id_maps": {
            "projects": dict(plan.project_id_map),
            "asset_libraries": dict(plan.asset_library_id_map),
            "prompts": dict(plan.prompt_id_map),
        },
        "protected_hashes": dict(plan.protected_hashes),
        "workflow_hashes": dict(plan.workflow_hashes),
        "warnings": list(plan.warnings),
        "backup_path": str(backup_path) if backup_path else None,
        "validation": dict(validation or {}),
    }


def write_report(plan: MigrationPlan, report: dict[str, Any]) -> Path:
    report_path = plan.paths.report_root / plan.run_id / "migration-report.json"
    write_json(report_path, report)
    return report_path


def _validate_workflows(source: Path, workflow_root: Path) -> dict[str, str]:
    source_hashes = _workflow_hashes(source / "workflows")
    target_hashes = _workflow_hashes(workflow_root)
    if source_hashes != target_hashes:
        raise MigrationError("Legacy and desktop workflow hashes do not match")
    return target_hashes


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = MigrationPaths(
        source_root=args.source,
        target_root=args.target,
        backup_root=args.backup_root,
        report_root=args.report_root,
        workflow_root=args.workflow_root,
    )
    try:
        if args.validate_only:
            protected = _protected_hashes(args.target)
            validation = validate_tree(
                args.target,
                workflow_root=args.workflow_root,
                protected_hashes=protected,
            )
            _validate_workflows(args.source, args.workflow_root)
            print(f"Validated InfiniteCanvas data: {validation}")
            return 0

        plan = build_plan(paths)
        if args.apply:
            if is_infinitecanvas_running():
                raise MigrationError(
                    "InfiniteCanvas.exe is running; close it before applying migration"
                )
            raise MigrationError("Apply mode is not available until transaction support is loaded")

        report = redacted_report(plan, mode="dry-run", status="planned")
        report_path = write_report(plan, report)
        print(f"Dry run completed: {report_path}")
        return 0
    except MigrationError as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
