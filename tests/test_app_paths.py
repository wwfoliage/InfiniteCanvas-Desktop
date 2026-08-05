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
        from app_paths import resolve_app_paths, save_path_overrides

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local = root / "Local"
            with patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(local),
                    "INFINITE_CANVAS_DATA_DIR": str(root / "ignored"),
                },
                clear=False,
            ):
                save_path_overrides(
                    {
                        "projects_dir": str(root / "stored-projects"),
                        "assets_dir": str(root / "stored-assets"),
                        "cache_dir": str(root / "stored-cache"),
                        "logs_dir": str(root / "stored-logs"),
                    }
                )
                paths = resolve_app_paths(
                    resource_dir=root / "bundle",
                    data_dir=root / "explicit",
                    frozen=True,
                )

            self.assertEqual(paths.data_dir, root / "explicit")
            self.assertEqual(paths.runtime_data_dir, root / "explicit" / "data")
            self.assertEqual(paths.assets_dir, root / "explicit" / "assets")
            self.assertEqual(paths.media_preview_dir, root / "explicit" / "data" / "media_previews")
            self.assertEqual(paths.logs_dir, root / "explicit" / "logs")

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

    def test_packaged_mode_applies_independent_directory_overrides(self):
        from app_paths import resolve_app_paths, save_path_overrides

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local = root / "Local"
            projects = root / "Projects"
            assets = root / "Assets"
            cache = root / "RelocatedCache"
            logs = root / "Logs"
            with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=False):
                save_path_overrides(
                    {
                        "projects_dir": str(projects),
                        "assets_dir": str(assets),
                        "cache_dir": str(cache),
                        "logs_dir": str(logs),
                    }
                )
                paths = resolve_app_paths(resource_dir=root / "bundle", frozen=True)

            self.assertEqual(paths.data_dir, local / "InfiniteCanvas")
            self.assertEqual(paths.runtime_data_dir, projects.resolve())
            self.assertEqual(paths.assets_dir, assets.resolve())
            self.assertEqual(paths.media_preview_dir, cache.resolve())
            self.assertEqual(paths.logs_dir, logs.resolve())
            self.assertEqual(paths.webview_data_dir, local / "InfiniteCanvas" / "webview")

    def test_moving_projects_does_not_move_default_webview_or_cache(self):
        from app_paths import resolve_app_paths, save_path_overrides

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local = root / "Local"
            projects = root / "Projects"
            with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}, clear=False):
                save_path_overrides({"projects_dir": str(projects)})
                paths = resolve_app_paths(resource_dir=root / "bundle", frozen=True)

            self.assertEqual(paths.runtime_data_dir, projects.resolve())
            self.assertEqual(paths.media_preview_dir, local / "InfiniteCanvas" / "data" / "media_previews")
            self.assertEqual(paths.webview_data_dir, local / "InfiniteCanvas" / "webview")


if __name__ == "__main__":
    unittest.main()
