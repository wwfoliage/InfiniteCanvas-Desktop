import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class SettingsCenterStructureTests(unittest.TestCase):
    def test_settings_center_has_seven_fixed_sections_and_panels(self):
        source = read("static/settings.html")
        expected = ["downloads", "appearance", "language", "api", "workflow", "storage", "about"]
        self.assertEqual(re.findall(r'data-settings-section="([^"]+)"', source), expected)
        self.assertEqual(re.findall(r'data-settings-panel="([^"]+)"', source), expected)

    def test_download_appearance_and_language_controls_are_complete(self):
        source = read("static/settings.html")
        for token in (
            'id="downloadDirectory"',
            'id="changeDownloadDirectory"',
            'id="resetDownloadDirectory"',
            'id="downloadCategorize"',
            'id="downloadNotify"',
            'data-setting-choice="theme"',
            'data-value="system"',
            'data-setting-choice="scale"',
            'data-value="80"',
            'data-value="90"',
            'data-value="100"',
            'data-value="110"',
            'data-value="125"',
            'data-setting-choice="language"',
        ):
            self.assertIn(token, source)

    def test_api_and_workflow_pages_use_embedded_mode(self):
        settings = read("static/settings.html")
        self.assertIn('/static/api-settings.html?embedded=1', settings)
        self.assertIn('/static/comfyui-settings.html?embedded=1', settings)
        for page, stylesheet in (
            ("static/api-settings.html", "static/css/api-settings.css"),
            ("static/comfyui-settings.html", "static/css/comfyui-settings.css"),
        ):
            self.assertIn("embedded-settings", read(page))
            self.assertIn("html.embedded-settings .page-head", read(stylesheet))

    def test_storage_cache_and_updates_are_explicit_manual_actions(self):
        html = read("static/settings.html")
        script = read("static/js/settings.js")
        for token in ('id="storageList"', 'id="clearCache"', 'id="checkUpdate"', 'id="probeConnectivity"'):
            self.assertIn(token, html)
        for endpoint in (
            "/api/storage-report",
            "/api/cache-cleanup-preview",
            "/api/cache-cleanup",
            "/api/check-update",
            "/api/update-from-github",
        ):
            self.assertIn(endpoint, script)
        self.assertNotRegex(script, r"setInterval\s*\([^)]*checkUpdate")

    def test_settings_layout_has_fixed_navigation_and_responsive_rules(self):
        css = read("static/css/settings.css")
        self.assertIn("grid-template-columns:222px 1px minmax(0,1fr)", css)
        self.assertIn("@media(max-width:760px)", css)
        self.assertNotIn("letter-spacing:-", css)


if __name__ == "__main__":
    unittest.main()
