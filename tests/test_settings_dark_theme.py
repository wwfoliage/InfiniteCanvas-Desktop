import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class SettingsDarkThemeTests(unittest.TestCase):
    def test_dark_settings_use_approved_toonflow_gray_scale(self):
        css = read("static/css/settings.css").lower()
        for token in (
            "--settings-bg:#181818",
            "--settings-surface:#242424",
            "--settings-control:#2c2c2c",
            "--settings-hover:#393939",
            "--settings-control-active:#4b4b4b",
            "--settings-switch-on:#717171",
            "--settings-text:rgba(255,255,255,.9)",
            "--settings-muted:rgba(255,255,255,.55)",
            "--settings-faint:rgba(255,255,255,.35)",
        ):
            self.assertIn(token, css)
        for old_color in ("#121411", "#181b17", "#68b999", "#203a31"):
            self.assertNotIn(old_color, css)

    def test_settings_rows_are_scoped_and_transparent(self):
        css = read("static/css/settings.css")
        self.assertRegex(css, r"\.settings-shell\s+\.setting-row\s*\{[^}]*background:transparent")
        self.assertIn("html.studio-theme-dark .settings-shell .setting-row", css)
        self.assertIn(".settings-shell .setting-group.divided .setting-row", css)
        self.assertIn(".settings-shell .switch-input:checked + .switch", css)

    def test_settings_background_fills_every_internal_layer(self):
        css = read("static/css/settings.css")
        for selector in (
            "html,body",
            "html.studio-theme-dark body",
            ".settings-shell",
            ".settings-nav",
            ".settings-content",
        ):
            self.assertIn(selector, css)
        self.assertIn("min-height:100%", css)
        self.assertIn("background:var(--settings-bg)!important", css)

    def test_settings_host_uses_gray_fallback_only_while_active(self):
        index = read("static/index.html")
        self.assertIn(".stage.settings-active", index)
        self.assertIn("#frame-settings", index)
        self.assertIn("classList.toggle('settings-active', id === 'settings')", index)

    def test_real_settings_entry_uses_gear_not_chain(self):
        index = read("static/index.html")
        match = re.search(
            r'<button class="side-pill" onclick="switchUI\(this, \'settings\'\)".*?</button>',
            index,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        button = match.group(0)
        self.assertIn('<circle cx="12" cy="12" r="3"></circle>', button)
        self.assertIn('M19.4 15', button)
        self.assertNotIn('x1="8" y1="12" x2="16" y2="12"', button)

    def test_settings_assets_use_new_cache_version(self):
        settings = read("static/settings.html")
        index = read("static/index.html")
        self.assertIn('/static/css/settings.css?v=2026.08.07.6', settings)
        self.assertIn('/static/settings.html?v=2026.08.07.6', index)

    def test_embedded_settings_share_the_gray_palette(self):
        for path in (
            "static/css/api-settings.css",
            "static/css/comfyui-settings.css",
        ):
            css = read(path).lower()
            self.assertIn("html.embedded-settings.studio-theme-dark", css)
            for token in (
                "--bg:#181818!important",
                "--panel:#242424!important",
                "--soft:#2c2c2c!important",
                "--line:#393939!important",
                "--line-strong:#4b4b4b!important",
            ):
                self.assertIn(token, css)

        self.assertIn(
            '/static/css/api-settings.css?v=2026.08.07.6',
            read("static/api-settings.html"),
        )
        self.assertIn(
            '/static/css/comfyui-settings.css?v=2026.08.07.6',
            read("static/comfyui-settings.html"),
        )

    def test_embedded_api_overrides_late_blue_dark_variables(self):
        css = read("static/css/api-settings.css").lower()
        scoped = css[css.rfind("/* settings center:") :]
        for token in (
            "--api-dark-page:#181818!important",
            "--api-dark-panel:#242424!important",
            "--api-dark-soft:#2c2c2c!important",
            "--api-dark-raised:#2c2c2c!important",
            "--api-dark-hover:#393939!important",
        ):
            self.assertIn(token, scoped)
        self.assertIn("html.embedded-settings.studio-theme-dark body .sidebar", scoped)

    def test_embedded_workflow_overrides_global_dark_form_controls(self):
        css = read("static/css/comfyui-settings.css").lower()
        self.assertIn(
            "html.embedded-settings.studio-theme-dark body input",
            css,
        )
        self.assertIn("background-color:var(--soft)!important", css)
        self.assertIn("border-color:var(--line-strong)!important", css)


if __name__ == "__main__":
    unittest.main()
