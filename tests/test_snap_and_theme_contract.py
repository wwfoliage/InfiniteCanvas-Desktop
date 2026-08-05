import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def compact(source: str) -> str:
    return re.sub(r"\s+", "", source).lower()


class SnapAndThemeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell = (ROOT / "static/index.html").read_text(encoding="utf-8")
        cls.smart_html = (ROOT / "static/smart-canvas.html").read_text(encoding="utf-8")
        cls.smart_js = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
        cls.smart_compact = compact(cls.smart_js)

    def test_shell_bootstraps_cached_and_server_preferences_before_reveal(self):
        for token in (
            "studio_app_settings_cache",
            "async function bootstrapAppPreferences()",
            "await bootstrapAppPreferences()",
        ):
            self.assertIn(token, self.shell)

    def test_smart_snap_toggle_is_before_workflow_and_remembered(self):
        self.assertLess(self.smart_html.index('id="smartSnapToggle"'), self.smart_html.index('id="smartWorkflowToggle"'))
        for token in (
            "smart_canvas_grid_snap",
            "function snapSmartCoordinate(value)",
            "localStorage.setItem(SMART_SNAP_KEY",
        ):
            self.assertIn(compact(token), self.smart_compact)


if __name__ == "__main__":
    unittest.main()
