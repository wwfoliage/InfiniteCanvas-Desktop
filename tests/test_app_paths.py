import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class AppPathsTests(unittest.TestCase):
    def test_development_mode_keeps_data_below_resource_dir(self):
        from app_paths import resolve_app_paths

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = resolve_app_paths(resource_dir=root, frozen=False)

            self.assertEqual(paths.resource_dir, root)
            self.assertEqual(paths.data_dir, root)
            self.assertEqual(paths.static_dir, root / "static")
            self.assertEqual(paths.canvas_dir, root / "data" / "canvases")

    def test_packaged_mode_uses_local_app_data(self):
        from app_paths import resolve_app_paths

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local = root / "Local"
            with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=False):
                paths = resolve_app_paths(resource_dir=root / "bundle", frozen=True)

            self.assertEqual(paths.resource_dir, root / "bundle")
            self.assertEqual(paths.data_dir, local / "InfiniteCanvas")
            self.assertEqual(paths.api_env_file, local / "InfiniteCanvas" / "API" / ".env")
            self.assertEqual(paths.assets_dir, local / "InfiniteCanvas" / "assets")

    def test_explicit_data_directory_has_priority(self):
        from app_paths import resolve_app_paths

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.dict(os.environ, {"INFINITE_CANVAS_DATA_DIR": str(root / "ignored")}, clear=False):
                paths = resolve_app_paths(
                    resource_dir=root / "bundle",
                    data_dir=root / "explicit",
                    frozen=True,
                )

            self.assertEqual(paths.data_dir, root / "explicit")

    def test_ensure_user_directories_creates_runtime_tree(self):
        from app_paths import ensure_user_directories, resolve_app_paths

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = resolve_app_paths(
                resource_dir=root / "bundle",
                data_dir=root / "user",
                frozen=True,
            )
            ensure_user_directories(paths)

            self.assertTrue(paths.canvas_dir.is_dir())
            self.assertTrue(paths.api_env_file.parent.is_dir())
            self.assertTrue((paths.assets_dir / "input").is_dir())
            self.assertTrue((paths.assets_dir / "output").is_dir())
            self.assertTrue(paths.logs_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
