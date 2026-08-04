import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def compact(source: str) -> str:
    return re.sub(r"\s+", "", source).lower()


class WarmBeigeLightThemeTests(unittest.TestCase):
    def read_compact(self, relative: str) -> str:
        return compact((ROOT / relative).read_text(encoding="utf-8"))

    def assert_tokens(self, relative: str, tokens: list[str]) -> None:
        source = self.read_compact(relative)
        for token in tokens:
            self.assertIn(token.lower(), source, f"{relative} is missing {token}")

    def test_core_canvases_use_warm_beige_palette(self):
        shared = [
            "--page:#e0ddd4",
            "--grid:rgba(183,174,161,.55)",
            "--text:#3b3935",
            "--muted:#746f66",
            "--faint:#928a7e",
            "--line:#c5beb2",
            "--soft:#e5e0d7",
            "--shadow:rgba(73,64,54,.10)",
            "--strong:#625548",
            "--strong-text:#f7f4ee",
        ]
        self.assert_tokens(
            "static/css/smart-canvas.css",
            shared
            + [
                "--panel:rgba(239,236,229,.94)",
                "--card:#f3f0e9",
            ],
        )
        self.assert_tokens(
            "static/css/canvas.css",
            shared
            + [
                "--panel:rgba(239,236,229,.94)",
                "--card:rgba(243,240,233,.96)",
                "--card-solid:#f3f0e9",
                "--soft-2:#d8d2c8",
                "--line-2:#b0a89b",
            ],
        )

    def test_core_canvas_dark_palettes_remain_unchanged(self):
        smart = self.read_compact("static/css/smart-canvas.css")
        normal = self.read_compact("static/css/canvas.css")
        self.assertIn(".theme-dark{--page:#0f141d", smart)
        self.assertIn("--card:#171d29", smart)
        self.assertIn(".theme-dark{--page:#0b1020", normal)
        self.assertIn("--card-solid:#111827", normal)

    def test_support_pages_use_warm_beige_palette(self):
        common = [
            "--text:#3b3935",
            "--muted:#746f66",
            "--faint:#928a7e",
        ]
        self.assert_tokens(
            "static/css/canvas-list.css",
            common
            + [
                "--page:#e0ddd4",
                "--panel-solid:#efece5",
                "--card-solid:#f3f0e9",
                "--soft:#e5e0d7",
                "--line:#c5beb2",
                "--line-2:#b0a89b",
                "--strong:#625548",
                "--strong-text:#f7f4ee",
                "--accent:#786b5c",
            ],
        )
        self.assert_tokens(
            "static/css/asset-manager.css",
            common
            + [
                "--page:#e0ddd4",
                "--card:#f3f0e9",
                "--soft:#e5e0d7",
                "--line:#c5beb2",
                "--line-2:#b0a89b",
                "--strong:#625548",
                "--strong-text:#f7f4ee",
            ],
        )
        for relative in (
            "static/css/api-settings.css",
            "static/css/comfyui-settings.css",
        ):
            self.assert_tokens(
                relative,
                common
                + [
                    "--bg:#e0ddd4",
                    "--panel:#f3f0e9",
                    "--soft:#e5e0d7",
                    "--line:#c5beb2",
                    "--line-strong:#b0a89b",
                    "--accent:#625548",
                ],
            )

    def test_support_page_dark_palettes_remain_unchanged(self):
        self.assert_tokens(
            "static/css/canvas-list.css",
            [
                ".theme-dark{--page:#10141d",
                "--card-solid:#151b26",
            ],
        )
        self.assert_tokens(
            "static/css/asset-manager.css",
            [
                ".theme-dark{--page:#08090c",
                "--card:#11141a",
            ],
        )
        self.assert_tokens(
            "static/css/api-settings.css",
            [
                "body.studio-theme-dark,html.studio-theme-darkbody{--bg:#11161d",
                "--panel:#1b222c",
            ],
        )
        self.assert_tokens(
            "static/css/comfyui-settings.css",
            [
                "body.studio-theme-dark,html.studio-theme-darkbody{--bg:#0e1014",
                "--panel:#1c1e26",
            ],
        )

    def test_shared_light_theme_is_component_scoped(self):
        theme = (ROOT / "static/css/theme.css").read_text(encoding="utf-8")
        lower = theme.lower()
        marker = "/* warm beige daylight theme */"
        self.assertIn(marker, lower)
        light_block = lower[lower.index(marker):]
        compact_block = compact(light_block)
        self.assertIn("html:not(.studio-theme-dark):not(.theme-dark)", compact_block)
        self.assertIn("--warm-page:#e0ddd4", compact_block)
        self.assertIn("--warm-card:#f3f0e9", compact_block)
        self.assertIn("--warm-strong:#625548", compact_block)
        self.assertNotRegex(light_block, r"(^|[\s,{>])(img|video)([\s,{.:>#]|$)")
        self.assertNotIn("filter:", light_block)

    def test_shell_and_chat_use_warm_beige_palette(self):
        self.assert_tokens(
            "static/index.html",
            [
                "--bg:#e0ddd4",
                "--sidebar-bg:#e9e5dc",
                "--stage-bg:#efece5",
                "--border:#c5beb2",
                "--stage-border:#b0a89b",
                "--text:#3b3935",
                "--muted:#746f66",
                "--nav-hover-bg:#e5e0d7",
            ],
        )
        self.assert_tokens(
            "static/gpt-chat.html",
            [
                "--chat-bg:#e0ddd4",
                "--chat-panel:#f3f0e9",
                "--chat-panel-2:#efece5",
                "--chat-soft:#e5e0d7",
                "--chat-line:#c5beb2",
                "--chat-line-2:#b0a89b",
                "--chat-text:#3b3935",
                "--chat-muted:#746f66",
                "--chat-faint:#928a7e",
                "--chat-strong:#625548",
                "--chat-strong-text:#f7f4ee",
                "--chat-user-bg:#786b5c",
            ],
        )

    def test_shell_and_chat_dark_palettes_remain_unchanged(self):
        self.assert_tokens(
            "static/index.html",
            [
                "html.theme-dark,body.theme-dark{--bg:#0f141d",
                "--stage-bg:#111722",
            ],
        )
        self.assert_tokens(
            "static/gpt-chat.html",
            [
                "--chat-bg:#0f141d",
                "--chat-panel:#171d29",
                "--chat-user-bg:#2f3b52",
            ],
        )

    def test_warm_theme_stylesheet_versions_are_bumped(self):
        expected = {
            "static/smart-canvas.html": ["smart-canvas.css"],
            "static/canvas.html": ["canvas.css", "theme.css"],
            "static/canvas-list.html": ["canvas-list.css", "theme.css"],
            "static/api-settings.html": ["api-settings.css", "theme.css"],
            "static/asset-manager.html": ["asset-manager.css", "theme.css"],
            "static/comfyui-settings.html": ["comfyui-settings.css", "theme.css"],
            "static/angle.html": ["theme.css"],
            "static/enhance.html": ["theme.css"],
            "static/gpt-chat.html": ["theme.css"],
            "static/klein.html": ["theme.css"],
            "static/online.html": ["theme.css"],
            "static/zimage.html": ["theme.css"],
        }
        legacy_versions = {
            "smart-canvas.css": "2026.07.23.1785327292",
            "canvas.css": "2026.07.23.1785326698",
            "canvas-list.css": "2026.07.23.1785077995",
            "api-settings.css": "2026.07.23.1785328662",
            "asset-manager.css": "2026.07.23.1785077995",
            "comfyui-settings.css": "2026.07.23.1785077995",
            "theme.css": "2026.07.23.1785077995",
        }
        for relative, stylesheets in expected.items():
            source = (ROOT / relative).read_text(encoding="utf-8")
            for stylesheet in stylesheets:
                match = re.search(
                    rf"/static/css/{re.escape(stylesheet)}\?v=([^\"']+)",
                    source,
                )
                self.assertIsNotNone(match, f"{relative} has no cache version for {stylesheet}")
                self.assertNotEqual(
                    match.group(1),
                    legacy_versions[stylesheet],
                    f"{relative} still uses the pre-theme cache version for {stylesheet}",
                )


if __name__ == "__main__":
    unittest.main()
