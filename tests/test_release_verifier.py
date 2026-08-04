import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build.windows.verify_release import scan_tree


class ReleaseVerifierTests(unittest.TestCase):
    def test_scan_tree_rejects_env_history_and_known_secret(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "API").mkdir()
            (root / "API" / ".env").write_text("KEY=private-value-123", encoding="utf-8")
            (root / "history.json").write_text("[]", encoding="utf-8")

            findings = scan_tree(root, ["private-value-123"])

            self.assertTrue(any(".env" in finding for finding in findings))
            self.assertTrue(any("history.json" in finding for finding in findings))
            self.assertTrue(any("known secret value" in finding for finding in findings))

    def test_scan_tree_rejects_non_empty_secret_json_field(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "settings.json").write_text(
                '{"name":"demo","api_key":"should-not-ship"}',
                encoding="utf-8",
            )

            findings = scan_tree(root, [])

            self.assertTrue(any("sensitive JSON field api_key" in finding for finding in findings))

    def test_scan_tree_accepts_clean_runtime_bundle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "static").mkdir()
            (root / "static" / "index.html").write_text("<h1>InfiniteCanvas</h1>", encoding="utf-8")
            (root / "VERSION").write_text("2026.07.23", encoding="ascii")

            self.assertEqual(scan_tree(root, []), [])


if __name__ == "__main__":
    unittest.main()
