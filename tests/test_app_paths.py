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
            self.assertEqual(
                paths.app_settings_file,
                local / "InfiniteCanvas" / "data" / "app_settings.json",
            )
            self.assertEqual(
                paths.download_temp_dir,
                local / "InfiniteCanvas" / "data" / "download_temp",
            )

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

    def test_frozen_mode_reads_resources_from_pyinstaller_bundle(self):
        from app_paths import resolve_app_paths

        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = Path(temp_dir) / "_internal"
            with patch.object(sys, "frozen", True, create=True), patch.object(
                sys, "_MEIPASS", str(bundle), create=True
            ):
                paths = resolve_app_paths(data_dir=Path(temp_dir) / "user")

            self.assertEqual(paths.resource_dir, bundle.resolve())

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
            self.assertTrue(paths.download_temp_dir.is_dir())

    def test_packaged_mode_applies_persisted_data_and_cache_overrides(self):
        from app_paths import resolve_app_paths, save_path_overrides

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local = root / "Local"
            data = root / "RelocatedData"
            cache = root / "RelocatedCache"
            with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=False):
                save_path_overrides({"data_dir": str(data), "cache_dir": str(cache)})
                paths = resolve_app_paths(resource_dir=root / "bundle", frozen=True)

            self.assertEqual(paths.data_dir, data.resolve())
            self.assertEqual(paths.media_preview_dir, cache.resolve())


if __name__ == "__main__":
    unittest.main()
