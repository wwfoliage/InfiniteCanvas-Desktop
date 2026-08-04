# InfiniteCanvas Legacy Data Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely merge the user data in `E:\InfiniteCanvas` into the installed desktop application's `%LOCALAPPDATA%\InfiniteCanvas` data directory without changing API configuration or losing current data.

**Architecture:** Build a standard-library-only migration tool with pure merge functions separated from filesystem transaction orchestration. The tool defaults to a read-only dry run, builds and validates a complete same-volume staging tree, backs up the current target, swaps the staged tree into place, validates the committed result, and automatically restores the backup on failure.

**Tech Stack:** Python 3.10.11 standard library, `unittest`, JSON, SHA-256, Windows `tasklist`, PyWebView desktop executable.

## Global Constraints

- Treat `E:\InfiniteCanvas` as read-only.
- Preserve all current `%LOCALAPPDATA%\InfiniteCanvas` data unless an explicit merge rule changes a duplicate record.
- Never copy `API\.env`, `data\api_providers.json`, `global_config.json`, logs, WebView data, or debug files from the legacy project.
- Never include secret values or prompt bodies in reports; configuration checks use paths and SHA-256 only.
- Keep the 7 packaged workflows unchanged because their SHA-256 values already match.
- Same-ID records with different content are both retained; the legacy record receives a deterministic new ID and the suffix `（旧版）`.
- Write backups below `E:\codex\无限画布资料\迁移备份` and reports below `E:\codex\无限画布资料\迁移记录`.
- Do not rebuild the EXE or installer.
- Do not continue an apply run while `InfiniteCanvas.exe` is running.

## File Structure

- Create `tools/legacy_migration_core.py`: dataclasses, hashing, stable ID generation, JSON merge rules, file-copy planning, reference rewriting, and static validation.
- Create `tools/migrate_legacy_data.py`: CLI parsing, process guard, dry run, backup/stage/swap/rollback orchestration, and redacted report writing.
- Create `tests/test_legacy_migration_core.py`: focused unit tests for every merge and conflict rule.
- Create `tests/test_migrate_legacy_data.py`: temporary-directory integration tests for dry run, apply, exclusions, idempotence, and rollback.
- Create `docs/legacy-data-migration.md`: safe operator instructions and recovery locations.

---

### Task 1: Core Models, Stable IDs, Projects, Canvases, and History

**Files:**
- Create: `tools/legacy_migration_core.py`
- Create: `tests/test_legacy_migration_core.py`

**Interfaces:**
- Produces: `MigrationPaths`, `MigrationPlan`, `stable_legacy_id()`, `legacy_name()`, `merge_projects()`, `rewrite_canvas_project()`, `history_key()`, and `merge_history()`.
- Consumes: Python `dataclasses`, `hashlib`, `json`, and `pathlib` only.

- [ ] **Step 1: Write failing tests for deterministic IDs and project remapping**

```python
import unittest

from tools.legacy_migration_core import (
    legacy_name,
    merge_projects,
    rewrite_canvas_project,
    stable_legacy_id,
)


class ProjectMergeTests(unittest.TestCase):
    def test_conflicting_default_project_is_preserved_as_legacy(self):
        current = {"projects": [{"id": "default", "name": "默认项目", "updated_at": 20}]}
        legacy = {"projects": [
            {"id": "default", "name": "默认项目", "updated_at": 10},
            {"id": "ad-id", "name": "广告", "updated_at": 11},
        ]}

        merged, project_map = merge_projects(current, legacy)

        self.assertEqual(3, len(merged["projects"]))
        self.assertEqual("ad-id", project_map["ad-id"])
        self.assertNotEqual("default", project_map["default"])
        imported = next(item for item in merged["projects"] if item["id"] == project_map["default"])
        self.assertEqual("默认项目（旧版）", imported["name"])
        self.assertEqual(project_map["default"], rewrite_canvas_project({"project": "default"}, project_map)["project"])

    def test_stable_legacy_id_and_suffix_are_idempotent(self):
        self.assertEqual(stable_legacy_id("project", "default"), stable_legacy_id("project", "default"))
        self.assertEqual("默认项目（旧版）", legacy_name("默认项目"))
        self.assertEqual("默认项目（旧版）", legacy_name("默认项目（旧版）"))
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m unittest discover -s tests -p "test_legacy_migration_core.py" -v`

Expected: FAIL because `tools.legacy_migration_core` does not exist.

- [ ] **Step 3: Add dataclasses and deterministic project merge implementation**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

LEGACY_SUFFIX = "（旧版）"


@dataclass(frozen=True)
class MigrationPaths:
    source_root: Path
    target_root: Path
    backup_root: Path
    report_root: Path


@dataclass
class MigrationPlan:
    run_id: str
    paths: MigrationPaths
    project_id_map: dict[str, str] = field(default_factory=dict)
    asset_library_id_map: dict[str, str] = field(default_factory=dict)
    prompt_id_map: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def stable_legacy_id(kind: str, original_id: str) -> str:
    digest = sha256(f"InfiniteCanvas:{kind}:{original_id}".encode("utf-8")).hexdigest()[:24]
    return f"legacy_{kind}_{digest}"


def legacy_name(name: str) -> str:
    clean = str(name or "旧版数据").strip()
    return clean if clean.endswith(LEGACY_SUFFIX) else f"{clean}{LEGACY_SUFFIX}"


def merge_projects(current: dict[str, Any], legacy: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    merged = [dict(item) for item in current.get("projects", [])]
    by_id = {str(item.get("id")): item for item in merged}
    id_map: dict[str, str] = {}
    for item in legacy.get("projects", []):
        old_id = str(item.get("id"))
        candidate = dict(item)
        if old_id in by_id and by_id[old_id] != candidate:
            candidate["id"] = stable_legacy_id("project", old_id)
            candidate["name"] = legacy_name(candidate.get("name", ""))
        id_map[old_id] = str(candidate["id"])
        if str(candidate["id"]) not in by_id:
            merged.append(candidate)
            by_id[str(candidate["id"])] = candidate
    for order, item in enumerate(merged):
        item["order"] = order
    return {"projects": merged}, id_map


def rewrite_canvas_project(canvas: dict[str, Any], project_id_map: dict[str, str]) -> dict[str, Any]:
    result = dict(canvas)
    project = str(result.get("project", "default"))
    result["project"] = project_id_map.get(project, project)
    return result
```

- [ ] **Step 4: Add failing history merge tests**

```python
from tools.legacy_migration_core import merge_history


class HistoryMergeTests(unittest.TestCase):
    def test_history_is_deduplicated_and_sorted_newest_first(self):
        current = [{"task_id": "current", "timestamp": 30, "images": ["/assets/output/c.png"]}]
        legacy = [
            {"task_id": "old", "timestamp": 10, "images": ["/assets/output/a.png"]},
            {"task_id": "current", "timestamp": 30, "images": ["/assets/output/c.png"]},
            {"request_id": "request-2", "timestamp": 20, "images": ["/assets/output/b.png"]},
        ]
        merged = merge_history(current, legacy)
        self.assertEqual([30, 20, 10], [item["timestamp"] for item in merged])
        self.assertEqual(3, len(merged))
```

- [ ] **Step 5: Implement history keys and merge**

```python
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


def merge_history(current: list[dict[str, Any]], legacy: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in [*current, *legacy]:
        records.setdefault(history_key(item), dict(item))
    return sorted(records.values(), key=lambda item: float(item.get("timestamp", 0)), reverse=True)
```

- [ ] **Step 6: Run tests and commit the core merge foundation**

Run: `python -m unittest discover -s tests -p "test_legacy_migration_core.py" -v`

Expected: all project, canvas, and history tests PASS.

```powershell
git add tools/legacy_migration_core.py tests/test_legacy_migration_core.py
git commit -m "feat: add legacy migration merge foundation"
```

### Task 2: Asset Library, Prompt Library, File Conflicts, and Validation

**Files:**
- Modify: `tools/legacy_migration_core.py`
- Modify: `tests/test_legacy_migration_core.py`

**Interfaces:**
- Consumes: `stable_legacy_id()` and `legacy_name()` from Task 1.
- Produces: `merge_asset_libraries()`, `merge_prompt_libraries()`, `sha256_file()`, `resolve_copy_target()`, `rewrite_asset_urls()`, `read_json()`, `write_json()`, and `validate_tree()`.

- [ ] **Step 1: Add failing tests for asset and prompt library preservation**

```python
from tools.legacy_migration_core import merge_asset_libraries, merge_prompt_libraries


class LibraryMergeTests(unittest.TestCase):
    def test_legacy_asset_library_becomes_a_separate_library(self):
        current = {"active_library_id": "default", "libraries": [{"id": "default", "name": "默认资产库", "categories": []}], "categories": []}
        legacy = {"active_library_id": "default", "libraries": [{"id": "default", "name": "默认资产库", "categories": [{"id": "characters", "items": [{"id": "asset-1"}]}]}]}
        merged, id_map = merge_asset_libraries(current, legacy)
        self.assertEqual("default", merged["active_library_id"])
        self.assertEqual(2, len(merged["libraries"]))
        imported = next(item for item in merged["libraries"] if item["id"] == id_map["default"])
        self.assertEqual("默认资产库（旧版）", imported["name"])

    def test_only_unique_legacy_prompt_items_are_added(self):
        current = {"active_library_id": "system", "libraries": [{"id": "system", "name": "系统提示词库", "items": [{"id": "builtin", "name": "系统"}]}]}
        legacy = {"active_library_id": "system", "libraries": [{"id": "system", "name": "系统提示词库", "items": [{"id": "builtin", "name": "系统"}, {"id": "custom", "name": "角色设计"}]}]}
        merged, id_map = merge_prompt_libraries(current, legacy)
        self.assertEqual(["builtin", "custom"], [item["id"] for item in merged["libraries"][0]["items"]])
        self.assertEqual("custom", id_map["custom"])
```

- [ ] **Step 2: Run the library tests and verify they fail**

Run: `python -m unittest discover -s tests -p "test_legacy_migration_core.py" -v`

Expected: FAIL because both library merge functions are missing.

- [ ] **Step 3: Implement semantic library merges**

Implement `merge_asset_libraries()` so a colliding legacy library receives `stable_legacy_id("asset_library", old_id)`, a suffixed name, intact categories, and no change to the current `active_library_id` or top-level current categories. Make repeated imports replace or skip the same deterministic legacy library instead of adding another copy.

Implement `merge_prompt_libraries()` by matching libraries by ID, preserving current items, appending unique legacy items, and using `stable_legacy_id("prompt", item_id)` plus `legacy_name()` only when the same item ID has different content. Preserve the current active library and category definitions.

- [ ] **Step 4: Add failing tests for file conflicts and URL rewriting**

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.legacy_migration_core import resolve_copy_target, rewrite_asset_urls


class FileConflictTests(unittest.TestCase):
    def test_different_same_name_file_gets_stable_legacy_name(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            target = root / "assets" / "source.png"
            source.write_bytes(b"legacy")
            target.parent.mkdir()
            target.write_bytes(b"current")
            relative, changed = resolve_copy_target(source, Path("assets/source.png"), root)
            self.assertTrue(changed)
            self.assertRegex(relative.name, r"source（旧版-[0-9a-f]{8}）\.png")

    def test_asset_urls_are_rewritten_recursively(self):
        mapping = {"/assets/output/a.png": "/assets/output/a（旧版-12345678）.png"}
        value = {"nodes": [{"data": {"url": "/assets/output/a.png"}}]}
        self.assertEqual(mapping["/assets/output/a.png"], rewrite_asset_urls(value, mapping)["nodes"][0]["data"]["url"])
```

- [ ] **Step 5: Implement hashing, conflict resolution, recursive URL rewriting, and JSON helpers**

`sha256_file()` must stream 1 MiB chunks. `resolve_copy_target()` must skip identical files and otherwise produce `stem + （旧版-<first 8 sha256>） + suffix`, adding a numeric suffix only if that deterministic path contains different bytes. `rewrite_asset_urls()` must recursively traverse dictionaries and lists and replace exact string values from the supplied URL mapping.

`read_json()` must decode UTF-8 and raise a path-specific `MigrationError` on malformed data. `write_json()` must write UTF-8, `ensure_ascii=False`, indent two spaces, flush, `fsync`, and replace the destination through a sibling temporary file.

- [ ] **Step 6: Add and implement static tree validation**

Tests must prove `validate_tree()` rejects malformed JSON, a canvas whose `project` ID is missing from `projects.json`, an asset-library URL whose file is missing, and any staged legacy `API/.env`, `data/api_providers.json`, or `global_config.json` overwrite. The function returns a count dictionary for assets, canvases, history, previews, projects, asset items, prompt items, and workflows when all checks pass.

- [ ] **Step 7: Run focused tests and commit**

Run: `python -m unittest discover -s tests -p "test_legacy_migration_core.py" -v`

Expected: all core tests PASS.

```powershell
git add tools/legacy_migration_core.py tests/test_legacy_migration_core.py
git commit -m "feat: add migration library and file validation"
```

### Task 3: Dry-Run CLI and Redacted Reporting

**Files:**
- Create: `tools/migrate_legacy_data.py`
- Create: `tests/test_migrate_legacy_data.py`

**Interfaces:**
- Consumes: all pure functions and models from `tools.legacy_migration_core`.
- Produces: `parse_args()`, `is_infinitecanvas_running()`, `build_plan()`, `redacted_report()`, `write_report()`, and `main() -> int`, including dry-run, apply, and validation-only modes.

- [ ] **Step 1: Write a failing dry-run integration test**

Build a minimal source tree and target tree inside `TemporaryDirectory`. Include one source asset, one current asset, one legacy canvas, one current canvas, valid project/library/prompt/history JSON, a legacy `API/.env`, and a current `API/.env`. Call `build_plan()` and `write_report()` without applying.

Assert that the target tree is byte-for-byte unchanged, the report has `mode: "dry-run"`, the planned counts are present, and neither the current nor legacy secret string appears anywhere in the serialized report.

- [ ] **Step 2: Run the integration test and verify it fails**

Run: `python -m unittest discover -s tests -p "test_migrate_legacy_data.py" -v`

Expected: FAIL because the CLI module does not exist.

- [ ] **Step 3: Implement safe defaults and argument parsing**

```python
def parse_args(argv=None):
    local_app_data = Path(os.environ["LOCALAPPDATA"])
    parser = argparse.ArgumentParser(description="Safely migrate InfiniteCanvas legacy user data")
    parser.add_argument("--source", type=Path, default=Path(r"E:\InfiniteCanvas"))
    parser.add_argument("--target", type=Path, default=local_app_data / "InfiniteCanvas")
    parser.add_argument("--workflow-root", type=Path, default=Path(__file__).resolve().parents[1] / "workflows")
    parser.add_argument("--backup-root", type=Path, default=Path(r"E:\codex\无限画布资料\迁移备份"))
    parser.add_argument("--report-root", type=Path, default=Path(r"E:\codex\无限画布资料\迁移记录"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Apply the validated plan; default is dry-run")
    mode.add_argument("--validate-only", action="store_true", help="Validate the current target and workflow resources without migration")
    return parser.parse_args(argv)
```

`main()` must return nonzero for invalid source data, missing target data, a running app during `--apply`, backup failure, staged validation failure, commit failure, or post-commit validation failure. The default invocation performs no target writes. `--validate-only` checks the target JSON/references and compares the 7 workflow files against the source workflow hashes without creating a backup or migration stage.

- [ ] **Step 4: Implement the Windows process guard**

Use `subprocess.run(["tasklist", "/FI", "IMAGENAME eq InfiniteCanvas.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True, check=False, creationflags=CREATE_NO_WINDOW)` on Windows. Parse CSV rows rather than substring matching. Tests patch `subprocess.run` for present, absent, and command-failure cases; command failure must block apply conservatively.

- [ ] **Step 5: Implement a redacted plan report**

The report may contain run ID, mode, normalized source/target paths, planned counts, conflict counts, ID maps, SHA-256 values, warnings, status, backup path, and validation results. It must never serialize JSON payloads, prompts, provider objects, environment variable values, request headers, or file contents.

- [ ] **Step 6: Run tests and commit the dry-run CLI**

Run: `python -m unittest discover -s tests -p "test_migrate_legacy_data.py" -v`

Expected: all dry-run, process-guard, and redaction tests PASS.

```powershell
git add tools/migrate_legacy_data.py tests/test_migrate_legacy_data.py
git commit -m "feat: add safe legacy migration dry run"
```

### Task 4: Transactional Apply, Backup, Idempotence, and Rollback

**Files:**
- Modify: `tools/migrate_legacy_data.py`
- Modify: `tests/test_migrate_legacy_data.py`
- Create: `docs/legacy-data-migration.md`

**Interfaces:**
- Consumes: `build_plan()`, merge functions, file plans, `validate_tree()`, and report helpers.
- Produces: `create_backup()`, `build_staging_tree()`, `commit_staging_tree()`, `restore_backup()`, and `execute_plan()`.

- [ ] **Step 1: Write failing apply and exclusion tests**

The integration fixture must assert after `execute_plan()`:

- current and legacy assets both exist;
- current and legacy canvases both exist;
- the legacy default project has a deterministic new ID and its canvas points to it;
- history is merged and sorted;
- a separate legacy asset library exists and current active library remains active;
- unique legacy prompt items were appended;
- current `API/.env`, `data/api_providers.json`, and `global_config.json` hashes are unchanged;
- legacy secret/config files are absent from the committed target;
- the timestamped backup and manifest exist;
- the report contains no fixture secret strings.

- [ ] **Step 2: Implement full backup and manifest verification**

`create_backup()` copies the complete current target into `<backup_root>/<run_id>/InfiniteCanvas`, including current secrets and WebView state, then writes a manifest containing relative path, byte size, and SHA-256. Re-enumerate the backup and require the same path set, sizes, and hashes as the target snapshot before allowing staging to commit.

- [ ] **Step 3: Implement staging tree construction**

Create a sibling directory `<target-name>-migration-stage-<run_id>` on the target volume. Copy the complete current target there, merge source assets and previews, write remapped legacy canvases, write merged JSON, optionally add legacy `mediakit_tasks.json` only when absent, and leave current config, conversations, logs, WebView, and canvas-media tasks untouched. Validate the stage before commit.

- [ ] **Step 4: Implement recoverable same-volume swap and rollback**

Rename the current target to `<target-name>-migration-original-<run_id>`, rename the stage to the target path, and run post-commit validation. If any rename or validation fails, preserve the failed tree as `<target-name>-migration-failed-<run_id>` when possible and rename the original tree back. Delete the temporary original only after post-commit validation and backup-manifest validation both pass.

- [ ] **Step 5: Add failure-injection rollback tests**

Patch post-commit validation to raise `MigrationError`. Assert `execute_plan()` returns or raises a failure, the target manifest exactly matches its pre-migration manifest, the backup remains intact, the report status is `rolled-back`, and the failed migrated tree is preserved for diagnosis without exposing secrets in the report.

- [ ] **Step 6: Add an idempotence test**

Run the apply operation twice against the same fixture. Assert the second run does not increase project, canvas, history, library, prompt, asset, or preview counts and produces the same deterministic legacy IDs.

- [ ] **Step 7: Write operator documentation**

Document the default dry run, explicit `--apply`, required application shutdown, source/target defaults, backup/report locations, expected real-data counts, exit-code behavior, and manual recovery procedure. State clearly that the script never changes the packaged workflows or installer.

- [ ] **Step 8: Run migration tests and the complete suite**

Run: `python -m unittest discover -s tests -p "test_*migration*.py" -v`

Expected: all migration tests PASS.

Run: `python -m unittest discover -s tests -v`

Expected: the complete existing suite PASS with no new failures.

- [ ] **Step 9: Commit the transactional migration tool**

```powershell
git add tools/migrate_legacy_data.py tests/test_migrate_legacy_data.py docs/legacy-data-migration.md
git commit -m "feat: add transactional legacy data migration"
```

### Task 5: Real Dry Run and Reviewed Migration

**Files:**
- Read only: `E:\InfiniteCanvas`
- Write data: `%LOCALAPPDATA%\InfiniteCanvas`
- Create outside repository: `E:\codex\无限画布资料\迁移备份\<run-id>\`
- Create outside repository: `E:\codex\无限画布资料\迁移记录\<run-id>\`

**Interfaces:**
- Consumes: the tested CLI from Task 4.
- Produces: migrated desktop user data, verified backup, redacted report, manifest, and ID maps.

- [ ] **Step 1: Confirm the application is closed**

Run: `Get-Process -Name InfiniteCanvas -ErrorAction SilentlyContinue`

Expected: no process output. If a process is listed, stop and ask the user to close the application manually.

- [ ] **Step 2: Record pre-migration Git and data state**

Run `git status --short`, record current target counts, and hash current `API/.env`, `data/api_providers.json`, and `global_config.json` when each exists. Do not print or read their contents.

- [ ] **Step 3: Execute the real dry run**

```powershell
python tools\migrate_legacy_data.py `
  --source 'E:\InfiniteCanvas' `
  --target "$env:LOCALAPPDATA\InfiniteCanvas" `
  --backup-root 'E:\codex\无限画布资料\迁移备份' `
  --report-root 'E:\codex\无限画布资料\迁移记录'
```

Expected: exit code 0, report mode `dry-run`, no target changes, 161 legacy assets, 21 legacy canvases, 29 legacy history entries, 282 legacy previews, 52 legacy asset-library items, and 2 unique legacy prompts planned.

- [ ] **Step 4: Review dry-run conflicts and sensitive exclusions**

Verify the report contains no unexpected collisions and no secret values. Verify the planned project map remaps only the conflicting legacy `default`, keeps the unique advertising project ID, and leaves all workflow hashes unchanged.

- [ ] **Step 5: Apply the reviewed migration**

Run the same command with `--apply` appended.

Expected: exit code 0, report status `completed`, a verified backup exists, and no rollback directory remains.

- [ ] **Step 6: Verify exact real-data outcomes**

Run the CLI's validation mode against the committed target and independently enumerate files. Expected stable totals are 166 assets, 22 canvases, 34 history records, 294 previews, 3 projects, 52 items in the legacy asset library, 12 prompt templates, and 7 unchanged workflows. If live data changed after planning, explain the count delta in the report rather than forcing the stale total.

- [ ] **Step 7: Verify sensitive configuration hashes**

Recompute hashes for the current API and global configuration files and compare with Step 2. Expected: every existing protected file hash is identical.

### Task 6: Desktop Application Acceptance Check

**Files:**
- Read only: `%LOCALAPPDATA%\Programs\InfiniteCanvas\InfiniteCanvas.exe`
- Read only: `%LOCALAPPDATA%\InfiniteCanvas`
- Modify: the migration report's validation status only through the report writer.

**Interfaces:**
- Consumes: migrated data and report from Task 5.
- Produces: final UI validation results recorded without screenshots containing secrets.

- [ ] **Step 1: Start the installed executable**

Run the installed `%LOCALAPPDATA%\Programs\InfiniteCanvas\InfiniteCanvas.exe`. Confirm one PyWebView application window appears and no CMD window or external Edge/Chrome browser window is launched.

- [ ] **Step 2: Verify current data remains available**

Open the current default project and current canvas. Confirm it loads, its nodes and media remain visible, and the current conversation and application state were not removed.

- [ ] **Step 3: Verify imported projects and canvases**

Switch to “默认项目（旧版）” and confirm its 20 canvases appear. Switch to “广告” and confirm the “去油膜” canvas appears. Open at least one small and one media-heavy old canvas and confirm node/media references resolve.

- [ ] **Step 4: Verify assets, history, prompts, and workflows**

Switch to “默认资产库（旧版）”, confirm its 52 registered items and thumbnail samples load, confirm old and current history entries appear, confirm the 2 imported custom prompt templates are present, and confirm all 7 workflows are available.

- [ ] **Step 5: Close the application and finalize the report**

Close the PyWebView window and confirm `Get-Process -Name InfiniteCanvas -ErrorAction SilentlyContinue` returns no process. Append only pass/fail checks and observed counts to the migration report; do not include API values, provider objects, prompt bodies, or sensitive screenshots.

- [ ] **Step 6: Final repository and artifact check**

Run `git status --short` and verify only intentional tool/test/doc commits exist. Report the backup path, report path, commit hashes, test results, protected configuration hash result, and UI acceptance result to the user.
