import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from app_paths import ensure_user_directories, resolve_app_paths
from app_settings import AppSettingsStore
from download_manager import DownloadManager


class SettingsDownloadApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.paths = resolve_app_paths(
            resource_dir=Path(__file__).resolve().parents[1],
            data_dir=self.root / "user",
            frozen=True,
        )
        ensure_user_directories(self.paths)
        self.settings = AppSettingsStore(self.paths.app_settings_file)
        self.downloads = self.root / "downloads"
        self.settings.update({"downloads": {"directory": str(self.downloads)}})
        self.manager = DownloadManager(
            self.paths,
            self.settings,
            local_resolver=main.download_local_path_from_url,
        )
        self.patches = [
            patch.object(main, "APP_PATHS", self.paths),
            patch.object(main, "APP_SETTINGS", self.settings),
            patch.object(main, "DOWNLOAD_MANAGER", self.manager),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temporary.cleanup()

    def test_settings_api_returns_resolved_directory_and_updates_fields(self):
        payload = main.get_app_settings()
        self.assertEqual(payload["downloads"]["resolved_directory"], str(self.downloads.resolve()))
        updated = main.put_app_settings({"appearance": {"theme": "dark"}, "api_key": "secret"})
        self.assertEqual(updated["appearance"]["theme"], "dark")
        self.assertNotIn("api_key", updated)

    def test_blob_download_returns_final_native_path(self):
        upload = UploadFile(
            filename="blob",
            file=io.BytesIO(b"{}"),
            headers={"content-type": "application/json"},
        )
        result = main.save_download_blob(upload, "board.json", "画布导出")
        self.assertTrue(result["ok"])
        self.assertEqual(result["category"], "画布导出")
        self.assertEqual(Path(result["path"]).read_bytes(), b"{}")

    def test_url_download_saves_registered_local_output(self):
        source = self.paths.output_dir / "result.png"
        source.write_bytes(b"png")
        isolated = DownloadManager(
            self.paths,
            self.settings,
            local_resolver=lambda url: source if url == "/output/result.png" else None,
        )
        with patch.object(main, "DOWNLOAD_MANAGER", isolated):
            result = main.save_download_url(
                main.DownloadUrlRequest(url="/output/result.png", filename="result.png", category="图片")
            )
        self.assertEqual(Path(result["path"]).read_bytes(), b"png")

    def test_url_download_rejects_arbitrary_local_file(self):
        with self.assertRaises(HTTPException) as raised:
            main.save_download_url(
                main.DownloadUrlRequest(
                    url="file:///C:/Windows/win.ini",
                    filename="win.ini",
                    category="其他",
                )
            )
        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail["code"], "invalid_download")

    def test_download_output_wrapper_is_unwrapped_before_saving(self):
        wrapped = "/api/download-output?url=https%3A%2F%2Fexample.com%2Fimage.png&name=image.png"
        self.assertEqual(
            main.normalized_download_source_url(wrapped),
            "https://example.com/image.png",
        )

    def test_storage_and_cache_routes_use_isolated_allowlist(self):
        self.paths.media_preview_dir.joinpath("preview.jpg").write_bytes(b"preview")
        report = main.get_storage_report()
        preview = main.get_cache_cleanup_preview()
        cleared = main.clear_app_cache()
        self.assertTrue(report["ok"])
        self.assertEqual(preview["bytes"], len(b"preview"))
        self.assertEqual(cleared["removed_items"], 1)

    def test_new_routes_are_registered(self):
        paths = {route.path for route in main.app.routes}
        for expected in (
            "/api/app-settings",
            "/api/downloads/url",
            "/api/downloads/blob",
            "/api/storage-report",
            "/api/cache-cleanup-preview",
            "/api/cache-cleanup",
        ):
            self.assertIn(expected, paths)

    def test_static_html_versioning_preserves_embedded_query(self):
        rendered = main.versioned_static_html(
            '<iframe src="/static/api-settings.html?embedded=1"></iframe>'
        )
        self.assertIn('/static/api-settings.html?embedded=1&v=', rendered)
        self.assertNotIn('?embedded=1?v=', rendered)
        self.assertNotIn('?v=', rendered.split('embedded=1', 1)[0])

    def test_static_html_versioning_replaces_existing_version_once(self):
        rendered = main.versioned_static_html(
            '<script src="/static/js/settings.js?v=old"></script>'
        )
        self.assertEqual(rendered.count('v='), 1)
        self.assertNotIn('v=old', rendered)


if __name__ == "__main__":
    unittest.main()
