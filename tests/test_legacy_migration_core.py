import unittest

from tools.legacy_migration_core import (
    legacy_name,
    merge_history,
    merge_projects,
    rewrite_canvas_project,
    stable_legacy_id,
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


if __name__ == "__main__":
    unittest.main()
