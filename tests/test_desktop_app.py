import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class DesktopAppTests(unittest.TestCase):
    def tearDown(self):
        from desktop_bridge import unregister_desktop_api

        unregister_desktop_api()

    def test_reserved_port_is_valid(self):
        from desktop_app import reserve_loopback_port

        port = reserve_loopback_port()
        self.assertGreater(port, 0)
        self.assertLess(port, 65536)

    @patch("desktop_app.uvicorn.Server")
    @patch("desktop_app.uvicorn.Config")
    def test_runtime_binds_loopback_and_stops_server(self, config_class, server_class):
        from desktop_app import UvicornRuntime

        server = server_class.return_value
        server.started = True
        server.serve.return_value = None
        runtime = UvicornRuntime(object(), port=32123)

        url = runtime.start(timeout=1)
        runtime.stop(timeout=1)

        self.assertEqual(url, "http://127.0.0.1:32123/")
        self.assertEqual(config_class.call_args.kwargs["host"], "127.0.0.1")
        self.assertTrue(server.should_exit)

    def test_window_uses_edge_webview_and_always_stops(self):
        from desktop_app import run_window

        webview = SimpleNamespace(create_window=MagicMock(), start=MagicMock())
        runtime = SimpleNamespace(stop=MagicMock())

        result = run_window(
            webview,
            runtime,
            "http://127.0.0.1:32123/",
            Path("C:/InfiniteCanvas/webview"),
        )

        self.assertEqual(result, 0)
        webview.create_window.assert_called_once_with(
            "InfiniteCanvas",
            "http://127.0.0.1:32123/",
            width=1440,
            height=900,
            min_size=(1024, 700),
        )
        webview.start.assert_called_once_with(
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path="C:\\InfiniteCanvas\\webview",
        )
        runtime.stop.assert_called_once()

    def test_window_stops_runtime_when_webview_fails(self):
        from desktop_app import run_window

        webview = SimpleNamespace(
            create_window=MagicMock(),
            start=MagicMock(side_effect=RuntimeError("WebView2 unavailable")),
        )
        runtime = SimpleNamespace(stop=MagicMock())

        with self.assertRaisesRegex(RuntimeError, "WebView2 unavailable"):
            run_window(webview, runtime, "http://127.0.0.1:32123/")

        runtime.stop.assert_called_once()

    def test_window_enables_download_fallback_and_exposes_desktop_api(self):
        from desktop_app import run_window

        window = MagicMock()
        webview = SimpleNamespace(
            settings={},
            create_window=MagicMock(return_value=window),
            start=MagicMock(),
        )
        runtime = SimpleNamespace(stop=MagicMock())
        desktop_api = MagicMock()

        run_window(
            webview,
            runtime,
            "http://127.0.0.1:32123/",
            Path("C:/InfiniteCanvas/webview"),
            desktop_api,
        )

        self.assertTrue(webview.settings["ALLOW_DOWNLOADS"])
        self.assertIs(webview.create_window.call_args.kwargs["js_api"], desktop_api)
        desktop_api.set_window.assert_called_once_with(window)

    def test_desktop_api_selects_and_persists_download_directory(self):
        from app_paths import resolve_app_paths
        from app_settings import AppSettingsStore
        from desktop_app import DesktopApi

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            chosen = root / "chosen"
            chosen.mkdir()
            paths = resolve_app_paths(resource_dir=root / "bundle", data_dir=root / "data", frozen=True)
            store = AppSettingsStore(paths.app_settings_file)
            window = MagicMock()
            window.create_file_dialog.return_value = (str(chosen),)
            api = DesktopApi(paths, store, folder_dialog_type="folder", opener=MagicMock())
            api.set_window(window)

            result = api.choose_download_directory()

            self.assertTrue(result["ok"])
            self.assertEqual(store.load()["downloads"]["directory"], str(chosen.resolve()))
            window.create_file_dialog.assert_called_once()

    def test_desktop_api_handles_cancel_and_rejects_arbitrary_open_path(self):
        from app_paths import resolve_app_paths
        from app_settings import AppSettingsStore
        from desktop_app import DesktopApi

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = resolve_app_paths(resource_dir=root / "bundle", data_dir=root / "data", frozen=True)
            store = AppSettingsStore(paths.app_settings_file)
            window = MagicMock()
            window.create_file_dialog.return_value = None
            opener = MagicMock()
            api = DesktopApi(paths, store, folder_dialog_type="folder", opener=opener)
            api.set_window(window)

            self.assertEqual(api.choose_download_directory(), {"ok": False, "cancelled": True})
            self.assertEqual(
                api.open_directory("C:/Windows"),
                {"ok": False, "error_code": "directory_not_allowed"},
            )
            opener.assert_not_called()

    def test_desktop_api_opens_only_registered_directory_kind(self):
        from app_paths import resolve_app_paths
        from app_settings import AppSettingsStore
        from desktop_app import DesktopApi

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = resolve_app_paths(resource_dir=root / "bundle", data_dir=root / "data", frozen=True)
            store = AppSettingsStore(paths.app_settings_file)
            opener = MagicMock()
            api = DesktopApi(paths, store, folder_dialog_type="folder", opener=opener)

            result = api.open_directory("logs")

            self.assertTrue(result["ok"])
            opener.assert_called_once_with(str(paths.logs_dir.resolve()))

            opener.reset_mock()
            assets_result = api.open_directory("assets")
            self.assertTrue(assets_result["ok"])
            opener.assert_called_once_with(str(paths.assets_dir.resolve()))

    @patch("desktop_app.save_path_overrides")
    def test_desktop_api_selects_storage_and_cache_directories(self, save_overrides):
        from app_paths import resolve_app_paths
        from app_settings import AppSettingsStore
        from desktop_app import DesktopApi

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = resolve_app_paths(resource_dir=root / "bundle", data_dir=root / "data", frozen=True)
            paths.data_dir.mkdir(parents=True)
            (paths.data_dir / "keep.txt").write_text("keep", encoding="utf-8")
            chosen = root / "chosen"
            chosen.mkdir()
            window = MagicMock()
            window.create_file_dialog.return_value = (str(chosen),)
            api = DesktopApi(paths, AppSettingsStore(paths.app_settings_file), folder_dialog_type="folder")
            api.set_window(window)

            storage = api.choose_directory("data")
            cache = api.choose_directory("cache")

            self.assertTrue(storage["ok"])
            self.assertTrue(storage["restart_required"])
            self.assertEqual((chosen / "keep.txt").read_text(encoding="utf-8"), "keep")
            self.assertTrue(cache["ok"])
            save_overrides.assert_any_call({"data_dir": str(chosen.resolve())})
            save_overrides.assert_any_call({"cache_dir": str(chosen.resolve())})

    def test_desktop_api_rejects_untrusted_update_installer(self):
        from app_paths import resolve_app_paths
        from app_settings import AppSettingsStore
        from desktop_app import DesktopApi

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = resolve_app_paths(resource_dir=temp_dir, data_dir=Path(temp_dir) / "data", frozen=True)
            api = DesktopApi(paths, AppSettingsStore(paths.app_settings_file))
            result = api.install_update("https://example.com/update.exe", "2026.09.01")
            self.assertFalse(result["ok"])
            self.assertEqual(result["error_code"], "untrusted_installer_url")

    def test_desktop_bridge_dispatches_only_allow_listed_actions(self):
        from desktop_bridge import dispatch_desktop_action, register_desktop_api

        api = SimpleNamespace(
            choose_download_directory=MagicMock(return_value={"ok": True, "directory": "D:/Downloads"}),
            choose_directory=MagicMock(return_value={"ok": True}),
            open_directory=MagicMock(return_value={"ok": True}),
            install_update=MagicMock(return_value={"ok": True}),
        )
        register_desktop_api(api)

        result = dispatch_desktop_action("open-directory", "downloads", {})
        rejected = dispatch_desktop_action("open-path", "C:/Windows", {})

        self.assertTrue(result["ok"])
        api.open_directory.assert_called_once_with("downloads")
        self.assertEqual(rejected["error_code"], "desktop_action_unknown")

    def test_desktop_bridge_reports_unavailable_without_registered_app(self):
        from desktop_bridge import dispatch_desktop_action, unregister_desktop_api

        unregister_desktop_api()
        result = dispatch_desktop_action("open-directory", "downloads", {})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "desktop_api_unavailable")

    def test_logging_writes_to_user_log_directory(self):
        from desktop_app import close_logging, configure_logging

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                log_file = configure_logging(Path(temp_dir))
                self.assertEqual(log_file, Path(temp_dir) / "desktop.log")
                self.assertTrue(Path(temp_dir).is_dir())
            finally:
                close_logging()

    @patch("desktop_app.os._exit")
    @patch("desktop_app.close_logging")
    def test_exit_process_closes_logs_before_forced_exit(self, close_logging, os_exit):
        from desktop_app import exit_process

        exit_process(7)

        close_logging.assert_called_once()
        os_exit.assert_called_once_with(7)


if __name__ == "__main__":
    unittest.main()
