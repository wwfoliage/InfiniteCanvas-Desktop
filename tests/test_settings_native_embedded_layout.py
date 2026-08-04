import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class SettingsNativeEmbeddedLayoutTests(unittest.TestCase):
    def test_parent_uses_one_scroll_surface_and_content_driven_frame_height(self):
        css = read("static/css/settings.css").lower()
        settings = read("static/settings.html")
        self.assertEqual(settings.count('scrolling="no"'), 2)
        self.assertIn(".settings-panel.embedded-panel{width:min(1180px,100%)}", css)
        self.assertRegex(
            css,
            r"\.settings-panel\.embedded-panel\.active\s*\{[^}]*height:auto[^}]*display:block",
        )
        self.assertRegex(css, r"\.embedded-frame-wrap\s*\{[^}]*overflow:visible")
        self.assertRegex(
            css,
            r"\.embedded-frame-wrap iframe\s*\{[^}]*height:var\(--embedded-frame-height,640px\)",
        )

    def test_parent_accepts_height_only_from_a_known_embedded_frame(self):
        script = read("static/js/settings.js")
        self.assertIn("event.data?.type === 'studio-embedded-size'", script)
        self.assertIn("frame.contentWindow === event.source", script)
        self.assertIn("--embedded-frame-height", script)
        self.assertIn("Math.min(24000, Math.max(320", script)

    def test_shared_resize_script_is_loaded_by_both_embedded_pages(self):
        for page in ("static/api-settings.html", "static/comfyui-settings.html"):
            source = read(page)
            self.assertIn("document.documentElement.dataset.studioScale='off'", source)
            self.assertIn(
                '/static/js/embedded-settings-resize.js?v=2026.08.07.6',
                source,
            )
        script = read("static/js/embedded-settings-resize.js")
        self.assertIn("new ResizeObserver", script)
        self.assertIn("type: 'studio-embedded-size'", script)
        self.assertIn("embedded=1", script)

    def test_api_embedded_mode_uses_native_rows_without_changing_standalone_layout(self):
        css = read("static/css/api-settings.css").lower()
        scoped = css[css.rfind("/* settings center native rows */") :]
        self.assertTrue(scoped)
        for token in (
            "html.embedded-settings .layout",
            "html.embedded-settings .sidebar",
            "html.embedded-settings .provider-list",
            "html.embedded-settings .content-head",
            "html.embedded-settings .block",
            "html.embedded-settings .field.full",
        ):
            self.assertIn(token, scoped)
        self.assertIn("grid-template-columns:minmax(190px,.8fr) minmax(280px,1.2fr)", scoped)
        self.assertIn("border-radius:0!important", scoped)
        self.assertIn("background:transparent!important", scoped)

    def test_workflow_embedded_mode_uses_native_rows_without_inner_scroll(self):
        css = read("static/css/comfyui-settings.css").lower()
        scoped = css[css.rfind("/* settings center native rows */") :]
        self.assertTrue(scoped)
        for token in (
            "html.embedded-settings .layout",
            "html.embedded-settings .sidebar",
            "html.embedded-settings .side-card",
            "html.embedded-settings .content-head",
            "html.embedded-settings .graph-card",
            "html.embedded-settings .input-row",
        ):
            self.assertIn(token, scoped)
        self.assertIn("max-height:none!important", scoped)
        self.assertIn("overflow:visible!important", scoped)
        self.assertIn("background:transparent!important", scoped)

    def test_native_embedded_assets_use_next_cache_version(self):
        settings = read("static/settings.html")
        index = read("static/index.html")
        self.assertIn('/static/css/settings.css?v=2026.08.07.6', settings)
        self.assertIn('/static/js/settings.js?v=2026.08.07.6', settings)
        self.assertIn('/static/settings.html?v=2026.08.07.6', index)
        self.assertIn('/static/css/api-settings.css?v=2026.08.07.6', read("static/api-settings.html"))
        self.assertIn('/static/css/comfyui-settings.css?v=2026.08.07.6', read("static/comfyui-settings.html"))


if __name__ == "__main__":
    unittest.main()
