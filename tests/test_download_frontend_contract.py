import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_SURFACES = (
    "static/index.html",
    "static/canvas.html",
    "static/smart-canvas.html",
    "static/canvas-list.html",
    "static/asset-manager.html",
    "static/angle.html",
    "static/enhance.html",
    "static/klein.html",
    "static/online.html",
    "static/zimage.html",
)
PRODUCT_SCRIPTS = (
    "static/js/canvas.js",
    "static/js/smart-canvas.js",
    "static/js/canvas-list.js",
    "static/js/asset-manager.js",
    "static/js/ltx-director-timeline.js",
)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class DownloadFrontendContractTests(unittest.TestCase):
    def test_shared_module_exposes_url_blob_native_open_and_browser_fallback(self):
        source = read("static/js/downloads.js")
        for token in (
            "saveUrl",
            "saveBlob",
            "openFolder",
            "/api/downloads/url",
            "/api/downloads/blob",
            "studio-download-complete",
            "browserUrl",
            "browserBlob",
        ):
            self.assertIn(token, source)

    def test_every_download_surface_loads_shared_module_after_theme(self):
        for path in DOWNLOAD_SURFACES:
            source = read(path)
            self.assertIn('/static/js/downloads.js', source, path)
            self.assertLess(source.index('/static/js/theme.js'), source.index('/static/js/downloads.js'), path)

    def test_product_scripts_do_not_create_download_anchors(self):
        for path in PRODUCT_SCRIPTS:
            source = read(path)
            self.assertNotRegex(source, r"createElement\s*\(\s*['\"]a['\"]\s*\)", path)
            self.assertNotRegex(source, r"\.download\s*=", path)
            self.assertIn("StudioDownloads", source, path)

    def test_generator_pages_have_no_native_download_attribute(self):
        for path in DOWNLOAD_SURFACES[5:]:
            source = read(path)
            self.assertIsNone(
                re.search(r"<a\b[^>]*\sdownload(?:\s|=|>)", source, flags=re.IGNORECASE),
                path,
            )
            self.assertIn("StudioDownloads.saveUrl", source, path)

    def test_only_shared_module_implements_browser_anchor_fallback(self):
        matches = []
        for path in (ROOT / "static").rglob("*.js"):
            if "vendor" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            if re.search(r"createElement\s*\(\s*['\"]a['\"]\s*\)", source):
                matches.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(matches, ["static/js/downloads.js"])


if __name__ == "__main__":
    unittest.main()
