import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_settings import AppSettingsStore, normalize_settings, settings_for_client


class AppSettingsTests(unittest.TestCase):
    def test_defaults_and_legacy_preferences_are_normalized(self):
        settings = normalize_settings(
            {},
            {
                "studio_theme": "dark",
                "studio_ui_scale_mode": "110",
                "studio_lang": "en",
            },
        )
        self.assertEqual(settings["appearance"], {"theme": "dark", "scale": "110"})
        self.assertEqual(settings["language"], "en")
        self.assertTrue(settings["downloads"]["categorize"])
        self.assertTrue(settings["downloads"]["notify"])

    def test_invalid_values_fall_back_without_copying_unknown_fields(self):
        settings = normalize_settings(
            {
                "appearance": {"theme": "purple", "scale": "500"},
                "language": "jp",
                "api_key": "secret",
            }
        )
        self.assertEqual(settings["appearance"], {"theme": "system", "scale": "auto"})
        self.assertEqual(settings["language"], "zh")
        self.assertNotIn("api_key", settings)

    def test_store_updates_whitelisted_fields_atomically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "data" / "app_settings.json"
            store = AppSettingsStore(path)
            saved = store.update(
                {
                    "downloads": {"categorize": False},
                    "appearance": {"theme": "dark"},
                    "api_key": "must-not-save",
                }
            )
            self.assertFalse(saved["downloads"]["categorize"])
            self.assertEqual(saved["appearance"]["theme"], "dark")
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("api_key", persisted)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_client_settings_resolve_default_download_directory(self):
        with patch("app_settings.default_download_directory", return_value=Path("C:/Downloads/InfiniteCanvas")):
            payload = settings_for_client(normalize_settings({}))
        self.assertEqual(payload["downloads"]["resolved_directory"], "C:\\Downloads\\InfiniteCanvas")
        self.assertEqual(payload["downloads"]["directory"], "")

    def test_relative_download_directory_is_rejected(self):
        settings = normalize_settings({"downloads": {"directory": "relative/path"}})
        self.assertEqual(settings["downloads"]["directory"], "")


if __name__ == "__main__":
    unittest.main()
