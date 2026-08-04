import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_paths import ensure_user_directories, resolve_app_paths
from app_settings import AppSettingsStore
from download_manager import (
    DownloadManager,
    DownloadRequest,
    DownloadValidationError,
    cache_cleanup_preview,
    classify_download,
    clear_rebuildable_cache,
    sanitize_filename,
    storage_report,
)


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if root.is_file():
        digest.update(root.read_bytes())
        return digest.hexdigest()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


class DownloadManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.paths = resolve_app_paths(
            resource_dir=self.root / "bundle",
            data_dir=self.root / "user",
            frozen=True,
        )
        ensure_user_directories(self.paths)
        self.downloads = self.root / "downloads"
        self.settings = AppSettingsStore(self.paths.app_settings_file)
        self.settings.update({"downloads": {"directory": str(self.downloads)}})
        self.manager = DownloadManager(self.paths, self.settings)

    def tearDown(self):
        self.temporary.cleanup()

    def test_sanitize_filename_removes_paths_controls_and_reserved_names(self):
        self.assertEqual(sanitize_filename("CON.png"), "_CON.png")
        self.assertEqual(sanitize_filename("folder/name.png"), "folder_name.png")
        self.assertEqual(sanitize_filename("bad\x00name.txt"), "badname.txt")
        self.assertEqual(sanitize_filename("..."), "download")

    def test_classification_prefers_explicit_then_mime_and_extension(self):
        self.assertEqual(classify_download("x.bin", requested="工作流"), "工作流")
        self.assertEqual(classify_download("x", "video/mp4"), "视频")
        self.assertEqual(classify_download("x.wav"), "音频")
        self.assertEqual(classify_download("notes.txt"), "其他")
        with self.assertRaises(DownloadValidationError):
            classify_download("x.bin", requested="未知")

    def test_save_stream_classifies_and_never_overwrites(self):
        first = self.manager.save_stream(DownloadRequest("图像.png", "图片"), [b"one"])
        second = self.manager.save_stream(DownloadRequest("图像.png", "图片"), [b"two"])
        self.assertEqual(Path(first.path).name, "图像.png")
        self.assertEqual(Path(second.path).name, "图像 (1).png")
        self.assertEqual(Path(first.path).read_bytes(), b"one")
        self.assertEqual(Path(second.path).read_bytes(), b"two")
        self.assertEqual(list(self.paths.download_temp_dir.glob("*.part")), [])

    def test_save_stream_removes_partial_file_after_failure(self):
        def failing_chunks():
            yield b"partial"
            raise OSError("source failed")

        with self.assertRaisesRegex(Exception, "Failed to save download"):
            self.manager.save_stream(DownloadRequest("bad.bin"), failing_chunks())
        self.assertEqual(list(self.paths.download_temp_dir.glob("*.part")), [])
        self.assertFalse((self.downloads / "其他" / "bad.bin").exists())

    def test_local_url_uses_only_registered_resolver(self):
        source = self.paths.output_dir / "sample.png"
        source.write_bytes(b"image")
        manager = DownloadManager(
            self.paths,
            self.settings,
            local_resolver=lambda url: source if url == "/output/sample.png" else None,
        )
        result = manager.save_url(DownloadRequest("sample.png"), "/output/sample.png")
        self.assertEqual(Path(result.path).read_bytes(), b"image")
        with self.assertRaises(DownloadValidationError):
            manager.save_url(DownloadRequest("win.ini"), "file:///C:/Windows/win.ini")

    def test_cache_cleanup_touches_only_allowlisted_rebuildable_content(self):
        self.paths.media_preview_dir.joinpath("preview.jpg").write_bytes(b"preview")
        self.paths.download_temp_dir.joinpath("orphan.part").write_bytes(b"partial")
        self.paths.canvas_dir.joinpath("canvas.json").write_bytes(b"canvas")
        self.paths.api_env_file.parent.mkdir(parents=True, exist_ok=True)
        self.paths.api_env_file.write_text("TOKEN=secret", encoding="utf-8")
        before = (tree_hash(self.paths.canvas_dir), tree_hash(self.paths.api_env_file.parent))
        preview = cache_cleanup_preview(self.paths)
        result = clear_rebuildable_cache(self.paths)
        self.assertEqual(preview["bytes"], len(b"previewpartial"))
        self.assertEqual(result["removed_items"], 2)
        self.assertEqual(list(self.paths.media_preview_dir.iterdir()), [])
        self.assertEqual(list(self.paths.download_temp_dir.iterdir()), [])
        self.assertEqual((tree_hash(self.paths.canvas_dir), tree_hash(self.paths.api_env_file.parent)), before)

    def test_storage_report_includes_expected_directory_kinds(self):
        report = storage_report(self.paths, self.settings.load())
        self.assertEqual(
            {entry["kind"] for entry in report["entries"]},
            {"projects", "assets", "cache", "logs", "downloads"},
        )


if __name__ == "__main__":
    unittest.main()
