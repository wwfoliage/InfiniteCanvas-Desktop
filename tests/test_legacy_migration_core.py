import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.legacy_migration_core import (
    legacy_name,
    merge_asset_libraries,
    merge_history,
    merge_projects,
    merge_prompt_libraries,
    read_json,
    resolve_copy_target,
    rewrite_canvas_project,
    rewrite_asset_urls,
    sha256_file,
    stable_legacy_id,
    validate_tree,
    write_json,
)


class ProjectMergeTests(unittest.TestCase):
    def test_conflicting_default_project_is_preserved_as_legacy(self):
        current = {
            "projects": [
                {"id": "default", "name": "默认项目", "order": 0, "updated_at": 20}
            ]
        }
        legacy = {
            "projects": [
                {"id": "default", "name": "默认项目", "order": 0, "updated_at": 10},
                {"id": "ad-id", "name": "广告", "order": 1, "updated_at": 11},
            ]
        }

        merged, project_map = merge_projects(current, legacy)

        self.assertEqual(3, len(merged["projects"]))
        self.assertEqual("ad-id", project_map["ad-id"])
        self.assertNotEqual("default", project_map["default"])
        imported = next(
            item
            for item in merged["projects"]
            if item["id"] == project_map["default"]
        )
        self.assertEqual("默认项目（旧版）", imported["name"])
        rewritten = rewrite_canvas_project({"project": "default"}, project_map)
        self.assertEqual(project_map["default"], rewritten["project"])

    def test_stable_legacy_id_and_suffix_are_idempotent(self):
        first = stable_legacy_id("project", "default")
        self.assertEqual(first, stable_legacy_id("project", "default"))
        self.assertEqual("默认项目（旧版）", legacy_name("默认项目"))
        self.assertEqual("默认项目（旧版）", legacy_name("默认项目（旧版）"))

    def test_repeated_project_merge_does_not_duplicate_legacy_project(self):
        current = {
            "projects": [
                {"id": "default", "name": "默认项目", "order": 0, "updated_at": 20}
            ]
        }
        legacy = {
            "projects": [
                {"id": "default", "name": "默认项目", "order": 0, "updated_at": 10}
            ]
        }

        first, _ = merge_projects(current, legacy)
        second, project_map = merge_projects(first, legacy)

        self.assertEqual(2, len(second["projects"]))
        self.assertIn(project_map["default"], {item["id"] for item in second["projects"]})


class HistoryMergeTests(unittest.TestCase):
    def test_history_is_deduplicated_and_sorted_newest_first(self):
        current = [
            {
                "task_id": "current",
                "timestamp": 30,
                "images": ["/assets/output/c.png"],
            }
        ]
        legacy = [
            {"task_id": "old", "timestamp": 10, "images": ["/assets/output/a.png"]},
            {
                "task_id": "current",
                "timestamp": 30,
                "images": ["/assets/output/c.png"],
            },
            {
                "request_id": "request-2",
                "timestamp": 20,
                "images": ["/assets/output/b.png"],
            },
        ]

        merged = merge_history(current, legacy)

        self.assertEqual([30, 20, 10], [item["timestamp"] for item in merged])
        self.assertEqual(3, len(merged))

    def test_history_without_ids_uses_timestamp_and_images(self):
        current = [{"timestamp": 10, "images": ["a.png"]}]
        legacy = [
            {"timestamp": 10, "images": ["a.png"]},
            {"timestamp": 10, "images": ["b.png"]},
        ]

        self.assertEqual(2, len(merge_history(current, legacy)))


class LibraryMergeTests(unittest.TestCase):
    def test_legacy_asset_library_becomes_a_separate_library(self):
        current = {
            "active_library_id": "default",
            "libraries": [
                {"id": "default", "name": "默认资产库", "categories": []}
            ],
            "categories": [],
        }
        legacy = {
            "active_library_id": "default",
            "libraries": [
                {
                    "id": "default",
                    "name": "默认资产库",
                    "categories": [
                        {"id": "characters", "items": [{"id": "asset-1"}]}
                    ],
                }
            ],
        }

        merged, id_map = merge_asset_libraries(current, legacy)

        self.assertEqual("default", merged["active_library_id"])
        self.assertEqual([], merged["categories"])
        self.assertEqual(2, len(merged["libraries"]))
        imported = next(
            item for item in merged["libraries"] if item["id"] == id_map["default"]
        )
        self.assertEqual("默认资产库（旧版）", imported["name"])

        repeated, _ = merge_asset_libraries(merged, legacy)
        self.assertEqual(2, len(repeated["libraries"]))

    def test_unique_prompt_items_are_added_and_conflicts_are_preserved(self):
        current = {
            "active_library_id": "system",
            "libraries": [
                {
                    "id": "system",
                    "name": "系统提示词库",
                    "categories": [{"id": "custom", "name": "我的"}],
                    "items": [
                        {"id": "builtin", "name": "系统", "positive": "current"}
                    ],
                }
            ],
        }
        legacy = {
            "active_library_id": "system",
            "libraries": [
                {
                    "id": "system",
                    "name": "系统提示词库",
                    "categories": [{"id": "custom", "name": "我的"}],
                    "items": [
                        {"id": "builtin", "name": "系统", "positive": "legacy"},
                        {"id": "custom", "name": "角色设计", "positive": "user"},
                    ],
                }
            ],
        }

        merged, id_map = merge_prompt_libraries(current, legacy)
        items = merged["libraries"][0]["items"]

        self.assertEqual(3, len(items))
        self.assertEqual("custom", id_map["custom"])
        self.assertNotEqual("builtin", id_map["builtin"])
        imported = next(item for item in items if item["id"] == id_map["builtin"])
        self.assertEqual("系统（旧版）", imported["name"])

        repeated, _ = merge_prompt_libraries(merged, legacy)
        self.assertEqual(3, len(repeated["libraries"][0]["items"]))


class FileHelperTests(unittest.TestCase):
    def test_different_same_name_file_gets_stable_legacy_name(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            target = root / "assets" / "source.png"
            source.write_bytes(b"legacy")
            target.parent.mkdir()
            target.write_bytes(b"current")

            relative, changed = resolve_copy_target(
                source, Path("assets/source.png"), root
            )

            self.assertTrue(changed)
            self.assertRegex(relative.name, r"source（旧版-[0-9a-f]{8}）\.png")

    def test_identical_file_keeps_original_target(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            target = root / "assets" / "source.png"
            source.write_bytes(b"same")
            target.parent.mkdir()
            target.write_bytes(b"same")

            relative, changed = resolve_copy_target(
                source, Path("assets/source.png"), root
            )

            self.assertEqual(Path("assets/source.png"), relative)
            self.assertFalse(changed)

    def test_asset_urls_are_rewritten_recursively(self):
        mapping = {
            "/assets/output/a.png": "/assets/output/a（旧版-12345678）.png"
        }
        value = {
            "nodes": [{"data": {"url": "/assets/output/a.png"}}],
            "other": "/assets/output/other.png",
        }

        rewritten = rewrite_asset_urls(value, mapping)

        self.assertEqual(
            mapping["/assets/output/a.png"], rewritten["nodes"][0]["data"]["url"]
        )
        self.assertEqual("/assets/output/other.png", rewritten["other"])

    def test_json_helpers_round_trip_utf8(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "value.json"
            write_json(path, {"name": "默认项目"})
            self.assertEqual({"name": "默认项目"}, read_json(path))
            self.assertFalse(path.with_suffix(".json.tmp").exists())


class ValidationTests(unittest.TestCase):
    def _make_valid_tree(self, root: Path) -> tuple[Path, dict[str, str]]:
        (root / "assets" / "library" / "角色").mkdir(parents=True)
        (root / "assets" / "library" / "角色" / "person.png").write_bytes(b"png")
        (root / "data" / "canvases").mkdir(parents=True)
        (root / "data" / "media_previews").mkdir(parents=True)
        (root / "API").mkdir(parents=True)
        (root / "API" / ".env").write_text("API_KEY=current", encoding="utf-8")
        write_json(
            root / "data" / "projects.json",
            {"projects": [{"id": "default", "name": "默认项目"}]},
        )
        write_json(
            root / "data" / "canvases" / "canvas.json",
            {"id": "canvas", "project": "default", "nodes": [], "edges": []},
        )
        write_json(
            root / "data" / "asset_library.json",
            {
                "active_library_id": "default",
                "libraries": [
                    {
                        "id": "default",
                        "categories": [
                            {
                                "id": "characters",
                                "items": [
                                    {
                                        "id": "asset",
                                        "url": "/assets/library/%E8%A7%92%E8%89%B2/person.png",
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
            root / "data" / "prompt_libraries.json",
            {
                "active_library_id": "system",
                "libraries": [{"id": "system", "categories": [], "items": []}],
            },
        )
        write_json(root / "history.json", [])
        protected = {"API/.env": sha256_file(root / "API" / ".env")}
        return root, protected

    def test_valid_tree_returns_counts(self):
        with TemporaryDirectory() as directory:
            root, protected = self._make_valid_tree(Path(directory))
            counts = validate_tree(root, protected_hashes=protected)
            self.assertEqual(1, counts["assets"])
            self.assertEqual(1, counts["canvases"])
            self.assertEqual(1, counts["projects"])
            self.assertEqual(1, counts["asset_items"])

    def test_missing_canvas_project_is_rejected(self):
        with TemporaryDirectory() as directory:
            root, protected = self._make_valid_tree(Path(directory))
            write_json(
                root / "data" / "canvases" / "canvas.json",
                {"id": "canvas", "project": "missing", "nodes": []},
            )
            with self.assertRaisesRegex(Exception, "missing project"):
                validate_tree(root, protected_hashes=protected)

    def test_missing_asset_library_file_is_rejected(self):
        with TemporaryDirectory() as directory:
            root, protected = self._make_valid_tree(Path(directory))
            (root / "assets" / "library" / "角色" / "person.png").unlink()
            with self.assertRaisesRegex(Exception, "missing asset"):
                validate_tree(root, protected_hashes=protected)

    def test_protected_file_change_is_rejected(self):
        with TemporaryDirectory() as directory:
            root, protected = self._make_valid_tree(Path(directory))
            (root / "API" / ".env").write_text("API_KEY=legacy", encoding="utf-8")
            with self.assertRaisesRegex(Exception, "protected file changed"):
                validate_tree(root, protected_hashes=protected)

    def test_malformed_json_has_path_in_error(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(Exception, "broken.json"):
                read_json(path)


if __name__ == "__main__":
    unittest.main()
