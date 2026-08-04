import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class DesktopAppTests(unittest.TestCase):
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

        result = run_window(webview, runtime, "http://127.0.0.1:32123/")

        self.assertEqual(result, 0)
        webview.create_window.assert_called_once_with(
            "InfiniteCanvas",
            "http://127.0.0.1:32123/",
            width=1440,
            height=900,
            min_size=(1024, 700),
        )
        webview.start.assert_called_once_with(gui="edgechromium", debug=False, private_mode=False)
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

    def test_logging_writes_to_user_log_directory(self):
        from desktop_app import close_logging, configure_logging

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                log_file = configure_logging(Path(temp_dir))
                self.assertEqual(log_file, Path(temp_dir) / "desktop.log")
                self.assertTrue(Path(temp_dir).is_dir())
            finally:
                close_logging()


if __name__ == "__main__":
    unittest.main()
