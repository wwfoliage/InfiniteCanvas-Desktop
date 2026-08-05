import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class SettingsBehaviorContractTests(unittest.TestCase):
    def test_theme_supports_system_mode_and_media_change_listener(self):
        source = read("static/js/theme.js")
        for token in (
            "prefers-color-scheme: dark",
            "getMode",
            "getResolved",
            "systemThemeQuery",
            "studio-theme-change",
            "--studio-ui-scale",
        ):
            self.assertIn(token, source)
        self.assertIn("['auto', '80', '90', '100', '110', '125']", source)

    def test_language_listens_for_cross_frame_messages(self):
        source = read("static/js/i18n-core.js")
        self.assertIn("event.data?.type === 'studio-lang'", source)
        self.assertIn("studio-lang-change", source)

    def test_settings_loads_and_saves_only_non_secret_preferences(self):
        source = read("static/js/settings.js")
        for token in (
            "/api/app-settings",
            "resolved_directory",
            "categorize",
            "notify",
            "appearance",
            "language",
            "migration_needed",
            "studio_app_settings_cache",
        ):
            self.assertIn(token, source)
        self.assertNotRegex(source, re.compile(r"api[_-]?key\s*[:=]", re.IGNORECASE))

    def test_update_is_manual_and_has_separate_install_confirmation(self):
        index = read("static/index.html")
        settings = read("static/js/settings.js")
        self.assertNotIn("\n            checkForUpdates();\n", index)
        self.assertIn("document.getElementById('checkUpdate').addEventListener('click', checkUpdate)", settings)
        self.assertIn("confirm(t('installConfirm'", settings)
        self.assertNotRegex(settings, r"DOMContentLoaded[^\n]+checkUpdate")

    def test_native_requests_are_same_origin_and_kind_based(self):
        index = read("static/index.html")
        settings = read("static/js/settings.js")
        self.assertIn("event.origin !== location.origin", settings)
        self.assertIn("fetch('/api/desktop-action'", settings)
        self.assertIn("nativeFailureMessage", settings)
        self.assertIn("settings-native-request", index)
        self.assertIn("open_directory(kind)", index)
        self.assertNotIn("open_directory(path)", index)

    def test_download_folder_open_uses_desktop_http_bridge(self):
        source = read("static/js/downloads.js")
        self.assertIn("fetch('/api/desktop-action'", source)
        self.assertIn("requestNative('open-directory', kind)", source)

    def test_updates_use_full_installer_from_project_release(self):
        main = read("main.py")
        desktop = read("desktop_app.py")
        settings = read("static/js/settings.js")
        self.assertIn("wwfoliage/InfiniteCanvas-Desktop", main)
        self.assertIn("install_update", desktop)
        self.assertIn("install-update", settings)
        self.assertNotIn("/api/update-from-github", settings)

    def test_settings_can_choose_storage_and_cache_locations(self):
        html = read("static/settings.html")
        source = read("static/js/settings.js")
        self.assertIn('data-choose-directory="data"', html)
        self.assertIn('data-choose-directory="cache"', html)
        self.assertIn("choose-directory", source)


if __name__ == "__main__":
    unittest.main()
