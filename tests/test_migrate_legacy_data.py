import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tools.legacy_migration_core import MigrationPaths, sha256_file, write_json
from tools.migrate_legacy_data import (
    build_plan,
    execute_plan,
    is_infinitecanvas_running,
    parse_args,
    redacted_report,
    write_report,
)


def tree_manifest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class MigrationFixture:
    def __init__(self, root: Path):
        self.source = root / "source"
        self.target = root / "target"
        self.backups = root / "backups"
        self.reports = root / "reports"
        self.workflows = root / "workflows"
        self.current_secret = "CURRENT-SECRET-VALUE"
        self.legacy_secret = "LEGACY-SECRET-VALUE"
        self._build_source()
        self._build_target()
        self.workflows.mkdir()
        (self.workflows / "workflow.json").write_bytes(b'{"workflow": 1}\n')

    @property
    def paths(self) -> MigrationPaths:
        return MigrationPaths(
            source_root=self.source,
            target_root=self.target,
            backup_root=self.backups,
            report_root=self.reports,
            workflow_root=self.workflows,
        )

    def _build_source(self):
        (self.source / "assets" / "output").mkdir(parents=True)
        (self.source / "assets" / "output" / "old.png").write_bytes(b"legacy-image")
        (self.source / "data" / "canvases").mkdir(parents=True)
        (self.source / "data" / "media_previews").mkdir(parents=True)
        (self.source / "data" / "media_previews" / "old.webp").write_bytes(
            b"legacy-preview"
        )
        (self.source / "workflows").mkdir(parents=True)
        (self.source / "workflows" / "workflow.json").write_bytes(
            b'{"workflow": 1}\n'
        )
        (self.source / "API").mkdir(parents=True)
        (self.source / "API" / ".env").write_text(
            f"API_KEY={self.legacy_secret}", encoding="utf-8"
        )
        write_json(
            self.source / "data" / "api_providers.json",
            {"providers": [{"api_key": self.legacy_secret}]},
        )
        write_json(
            self.source / "global_config.json", {"secret": self.legacy_secret}
        )
        write_json(
            self.source / "data" / "mediakit_tasks.json",
            {"tasks": [{"id": "legacy-media-task"}]},
        )
        write_json(
            self.source / "data" / "projects.json",
            {
                "projects": [
                    {"id": "default", "name": "默认项目", "updated_at": 10},
                    {"id": "ad-id", "name": "广告", "updated_at": 11},
                ]
            },
        )
        write_json(
            self.source / "data" / "canvases" / "old.json",
            {
                "id": "old",
                "title": "旧画布",
                "project": "default",
                "nodes": [{"data": {"url": "/assets/output/old.png"}}],
                "edges": [],
            },
        )
        write_json(
            self.source / "data" / "asset_library.json",
            {
                "active_library_id": "default",
                "libraries": [
                    {
                        "id": "default",
                        "name": "默认资产库",
                        "categories": [
                            {
                                "id": "characters",
                                "name": "角色",
                                "items": [
                                    {
                                        "id": "old-asset",
                                        "name": "旧素材",
                                        "url": "/assets/output/old.png",
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "categories": [],
            },
        )
        write_json(
            self.source / "data" / "prompt_libraries.json",
            {
                "active_library_id": "system",
                "libraries": [
                    {
                        "id": "system",
                        "name": "系统提示词库",
                        "categories": [],
                        "items": [
                            {"id": "builtin", "name": "系统", "positive": "same"},
                            {
                                "id": "custom",
                                "name": "自定义",
                                "positive": "private prompt body",
                            },
                        ],
                    }
                ],
            },
        )
        write_json(
            self.source / "history.json",
            [{"task_id": "old-task", "timestamp": 10, "images": ["/assets/output/old.png"]}],
        )

    def _build_target(self):
        (self.target / "assets" / "output").mkdir(parents=True)
        (self.target / "assets" / "output" / "current.png").write_bytes(
            b"current-image"
        )
        (self.target / "data" / "canvases").mkdir(parents=True)
        (self.target / "data" / "media_previews").mkdir(parents=True)
        (self.target / "data" / "media_previews" / "current.webp").write_bytes(
            b"current-preview"
        )
        (self.target / "API").mkdir(parents=True)
        (self.target / "data" / "conversations").mkdir(parents=True)
        (self.target / "data" / "conversations" / "current.json").write_text(
            "current-conversation", encoding="utf-8"
        )
        (self.target / "logs").mkdir(parents=True)
        (self.target / "logs" / "current.log").write_text(
            "current-log", encoding="utf-8"
        )
        (self.target / "webview").mkdir(parents=True)
        (self.target / "webview" / "profile.dat").write_bytes(b"current-webview")
        (self.target / "API" / ".env").write_text(
            f"API_KEY={self.current_secret}", encoding="utf-8"
        )
        write_json(
            self.target / "data" / "api_providers.json",
            {"providers": [{"api_key": self.current_secret}]},
        )
        write_json(
            self.target / "global_config.json", {"secret": self.current_secret}
        )
        write_json(
            self.target / "data" / "projects.json",
            {"projects": [{"id": "default", "name": "默认项目", "updated_at": 20}]},
        )
        write_json(
            self.target / "data" / "canvases" / "current.json",
            {
                "id": "current",
                "title": "当前画布",
                "project": "default",
                "nodes": [],
                "edges": [],
            },
        )
        write_json(
            self.target / "data" / "asset_library.json",
            {
                "active_library_id": "default",
                "libraries": [
                    {"id": "default", "name": "默认资产库", "categories": []}
                ],
                "categories": [],
            },
        )
        write_json(
            self.target / "data" / "prompt_libraries.json",
            {
                "active_library_id": "system",
                "libraries": [
                    {
                        "id": "system",
                        "name": "系统提示词库",
                        "categories": [],
                        "items": [
                            {"id": "builtin", "name": "系统", "positive": "same"}
                        ],
                    }
                ],
            },
        )
        write_json(
            self.target / "history.json",
            [{"task_id": "current-task", "timestamp": 20, "images": ["/assets/output/current.png"]}],
        )


class DryRunTests(unittest.TestCase):
    def test_cli_help_runs_with_isolated_python_paths(self):
        script = Path(__file__).resolve().parents[1] / "tools" / "migrate_legacy_data.py"
        result = subprocess.run(
            [sys.executable, "-I", str(script), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--apply", result.stdout)

    def test_dry_run_report_does_not_change_target_or_include_secrets(self):
        with TemporaryDirectory() as directory:
            fixture = MigrationFixture(Path(directory))
            before = tree_manifest(fixture.target)

            plan = build_plan(fixture.paths, run_id="20260804-120000")
            report = redacted_report(plan, mode="dry-run", status="planned")
            report_path = write_report(plan, report)

            self.assertEqual(before, tree_manifest(fixture.target))
            self.assertEqual("dry-run", report["mode"])
            self.assertEqual(2, report["expected_counts"]["assets"])
            self.assertEqual(2, report["expected_counts"]["canvases"])
            self.assertEqual(2, report["expected_counts"]["history"])
            self.assertEqual(3, report["expected_counts"]["projects"])
            serialized = report_path.read_text(encoding="utf-8")
            self.assertNotIn(fixture.current_secret, serialized)
            self.assertNotIn(fixture.legacy_secret, serialized)
            self.assertNotIn("private prompt body", serialized)

    def test_parse_args_defaults_to_dry_run(self):
        with patch.dict("os.environ", {"LOCALAPPDATA": r"C:\Local"}, clear=False):
            args = parse_args([])
        self.assertFalse(args.apply)
        self.assertFalse(args.validate_only)
        self.assertEqual(Path(r"C:\Local") / "InfiniteCanvas", args.target)


class ApplyTests(unittest.TestCase):
    def test_apply_merges_data_preserves_config_and_creates_backup(self):
        with TemporaryDirectory() as directory:
            fixture = MigrationFixture(Path(directory))
            protected_before = {
                relative: sha256_file(fixture.target / Path(relative))
                for relative in (
                    "API/.env",
                    "data/api_providers.json",
                    "global_config.json",
                )
            }
            plan = build_plan(fixture.paths, run_id="20260804-apply")

            report, report_path = execute_plan(
                plan, process_checker=lambda: False
            )

            self.assertEqual("completed", report["status"])
            self.assertTrue((fixture.target / "assets" / "output" / "current.png").is_file())
            self.assertTrue((fixture.target / "assets" / "output" / "old.png").is_file())
            self.assertTrue((fixture.target / "data" / "canvases" / "current.json").is_file())
            self.assertTrue((fixture.target / "data" / "canvases" / "old.json").is_file())
            self.assertTrue(
                (fixture.target / "data" / "mediakit_tasks.json").is_file()
            )
            self.assertEqual(
                "current-conversation",
                (
                    fixture.target / "data" / "conversations" / "current.json"
                ).read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "current-log",
                (fixture.target / "logs" / "current.log").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                b"current-webview",
                (fixture.target / "webview" / "profile.dat").read_bytes(),
            )

            projects = json.loads(
                (fixture.target / "data" / "projects.json").read_text(encoding="utf-8")
            )["projects"]
            self.assertEqual(3, len(projects))
            legacy_project = next(
                item for item in projects if item["name"] == "默认项目（旧版）"
            )
            old_canvas = json.loads(
                (fixture.target / "data" / "canvases" / "old.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(legacy_project["id"], old_canvas["project"])

            history = json.loads(
                (fixture.target / "history.json").read_text(encoding="utf-8")
            )
            self.assertEqual([20, 10], [item["timestamp"] for item in history])
            assets = json.loads(
                (fixture.target / "data" / "asset_library.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("default", assets["active_library_id"])
            self.assertEqual(2, len(assets["libraries"]))
            prompts = json.loads(
                (fixture.target / "data" / "prompt_libraries.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(2, len(prompts["libraries"][0]["items"]))

            for relative, expected_hash in protected_before.items():
                self.assertEqual(
                    expected_hash, sha256_file(fixture.target / Path(relative))
                )
            backup_path = Path(report["backup_path"])
            self.assertTrue((backup_path / "history.json").is_file())
            self.assertTrue((backup_path.parent / "backup-manifest.json").is_file())
            serialized = report_path.read_text(encoding="utf-8")
            self.assertNotIn(fixture.current_secret, serialized)
            self.assertNotIn(fixture.legacy_secret, serialized)
            self.assertNotIn("private prompt body", serialized)

    def test_post_commit_failure_restores_exact_original_tree(self):
        with TemporaryDirectory() as directory:
            fixture = MigrationFixture(Path(directory))
            before = tree_manifest(fixture.target)
            plan = build_plan(fixture.paths, run_id="20260804-rollback")

            def fail_validation(*args, **kwargs):
                raise RuntimeError("injected validation failure")

            with self.assertRaisesRegex(Exception, "injected validation failure"):
                execute_plan(
                    plan,
                    process_checker=lambda: False,
                    post_commit_validator=fail_validation,
                )

            self.assertEqual(before, tree_manifest(fixture.target))
            report_path = (
                fixture.reports
                / "20260804-rollback"
                / "migration-report.json"
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual("rolled-back", report["status"])
            self.assertTrue(Path(report["backup_path"]).is_dir())
            failed = fixture.target.parent / "target-migration-failed-20260804-rollback"
            self.assertTrue(failed.is_dir())

    def test_apply_is_idempotent(self):
        with TemporaryDirectory() as directory:
            fixture = MigrationFixture(Path(directory))
            first_plan = build_plan(fixture.paths, run_id="20260804-first")
            first_report, _ = execute_plan(first_plan, process_checker=lambda: False)

            second_plan = build_plan(fixture.paths, run_id="20260804-second")
            second_report, _ = execute_plan(second_plan, process_checker=lambda: False)

            self.assertEqual(first_report["validation"], second_report["validation"])
            projects = json.loads(
                (fixture.target / "data" / "projects.json").read_text(encoding="utf-8")
            )["projects"]
            self.assertEqual(3, len(projects))
            self.assertEqual(
                1,
                sum(item["name"] == "默认项目（旧版）" for item in projects),
            )
            asset_libraries = json.loads(
                (fixture.target / "data" / "asset_library.json").read_text(
                    encoding="utf-8"
                )
            )["libraries"]
            self.assertEqual(2, len(asset_libraries))


class ProcessGuardTests(unittest.TestCase):
    @patch("tools.migrate_legacy_data.os.name", "nt")
    @patch("tools.migrate_legacy_data.subprocess.run")
    def test_process_guard_detects_running_app(self, run):
        run.return_value = subprocess.CompletedProcess(
            [], 0, '"InfiniteCanvas.exe","1234","Console","1","10,000 K"\n', ""
        )
        self.assertTrue(is_infinitecanvas_running())

    @patch("tools.migrate_legacy_data.os.name", "nt")
    @patch("tools.migrate_legacy_data.subprocess.run")
    def test_process_guard_allows_absent_app(self, run):
        run.return_value = subprocess.CompletedProcess(
            [], 0, "INFO: No tasks are running which match the specified criteria.\n", ""
        )
        self.assertFalse(is_infinitecanvas_running())

    @patch("tools.migrate_legacy_data.os.name", "nt")
    @patch("tools.migrate_legacy_data.subprocess.run")
    def test_process_guard_blocks_when_tasklist_fails(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "", "access denied")
        self.assertTrue(is_infinitecanvas_running())


if __name__ == "__main__":
    unittest.main()
