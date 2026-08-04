import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SidebarFooterCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "static/index.html").read_text(encoding="utf-8")

    def test_project_update_and_author_footer_is_removed(self):
        for token in (
            'id="github-entry-btn"',
            'id="update-now-btn"',
            'id="project-version-badge"',
            'class="author-box"',
            'class="author-name-lite"',
            "wuli大雄",
            "space.bilibili.com/78652351",
            "xiaohongshu.com/user/profile/6433c34c000000001a023538",
            "youtube.com/@%E5%A4%A7%E9%9B%84dx",
            "x.com/dx8152",
        ):
            self.assertNotIn(token, self.source)

    def test_required_settings_controls_remain(self):
        for token in (
            "switchUI(this, 'api-settings')",
            'id="settings-fold-toggle"',
            'id="theme-toggle-btn"',
            'id="lang-toggle-btn"',
            "switchUI(this, 'comfyui-settings')",
        ):
            self.assertIn(token, self.source)

    def test_startup_no_longer_checks_for_updates(self):
        self.assertNotIn("\n            checkForUpdates();\n", self.source)


if __name__ == "__main__":
    unittest.main()
