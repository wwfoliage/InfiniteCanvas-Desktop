import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class FakeResponse:
    def __init__(self, payload=None, status_code=200, body=b"", headers=None):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}

    def json(self):
        return self._payload

    async def aiter_bytes(self, chunk_size=1024 * 1024):
        for start in range(0, len(self._body), max(1, chunk_size)):
            yield self._body[start:start + chunk_size]


class FakeStreamContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeMediaKitClient:
    def __init__(self, post_responses=None, get_response=None, stream_response=None):
        self.post_responses = list(post_responses or [])
        self.get_response = get_response or FakeResponse()
        self.stream_response = stream_response or FakeResponse(body=b"enhanced-video", headers={"content-type": "video/mp4"})
        self.post_calls = []
        self.request_calls = []
        self.get_calls = []
        self.stream_calls = []
        self.uploaded = b""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        if not self.post_responses:
            raise AssertionError(f"Unexpected POST: {url}")
        return self.post_responses.pop(0)

    async def request(self, method, url, **kwargs):
        self.request_calls.append((method, url, kwargs))
        content = kwargs.get("content")
        if hasattr(content, "__aiter__"):
            chunks = []
            async for chunk in content:
                chunks.append(chunk)
            self.uploaded = b"".join(chunks)
        return FakeResponse(status_code=200)

    async def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self.get_response

    def stream(self, method, url, **kwargs):
        self.stream_calls.append((method, url, kwargs))
        return FakeStreamContext(self.stream_response)


class MediaKitTestBase:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.assets = self.root / "assets"
        self.generated = self.assets / "output"
        self.inputs = self.assets / "input"
        self.library = self.assets / "library"
        self.custom = self.root / "custom-output"
        self.api_dir = self.root / "API"
        for path in (self.data, self.generated, self.inputs, self.library, self.api_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.env_file = self.api_dir / ".env"
        self.settings_file = self.data / "mediakit_settings.json"
        self.tasks_file = self.data / "mediakit_tasks.json"
        self.asset_library_file = self.data / "asset_library.json"
        self.patches = [
            patch.object(main, "BASE_DIR", str(self.root)),
            patch.object(main, "DATA_DIR", str(self.data)),
            patch.object(main, "ASSETS_DIR", str(self.assets)),
            patch.object(main, "ASSET_LIBRARY_DIR", str(self.library)),
            patch.object(main, "ASSET_LIBRARY_PATH", str(self.asset_library_file)),
            patch.object(main, "OUTPUT_OUTPUT_DIR", str(self.generated)),
            patch.object(main, "OUTPUT_INPUT_DIR", str(self.inputs)),
            patch.object(main, "API_ENV_FILE", str(self.env_file)),
            patch.object(main, "MEDIAKIT_SETTINGS_FILE", str(self.settings_file)),
            patch.object(main, "MEDIAKIT_TASKS_FILE", str(self.tasks_file)),
            patch.dict(os.environ, {"MEDIAKIT_API_KEY": "test-mediakit-key"}, clear=False),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def video_file(self, name="source.mp4", content=b"plain-sdr-video"):
        path = self.inputs / name
        path.write_bytes(content)
        return path, f"/api/storage-files/upload/{name}"

    def request_payload(self, url="https://example.com/source.mp4", token="test-token", fps=None):
        return main.MediaKitEnhanceRequest(
            video=main.MediaKitVideoInput(url=url, name="source.mp4", width=1280, height=720),
            resolution="720p",
            bitrate_level="medium",
            fps=fps,
            client_token=token,
            canvas_surface="smart",
            canvas_id="canvas-1",
            enhance_node_id="enhance-1",
            result_node_id="result-1",
        )


class MediaKitSettingsTests(MediaKitTestBase, unittest.IsolatedAsyncioTestCase):
    def test_default_and_custom_output_directory(self):
        default_dir = main.mediakit_output_dir()
        self.assertEqual(Path(default_dir), self.generated / "mediakit-enhance")
        saved = main.save_mediakit_settings({
            "output_mode": "custom",
            "custom_output_dir": str(self.custom),
        })
        self.assertEqual(saved["output_mode"], "custom")
        self.assertEqual(Path(main.mediakit_output_dir()), self.custom)
        self.assertTrue(self.custom.is_dir())

    def test_custom_output_directory_must_be_absolute(self):
        with self.assertRaises(main.HTTPException) as raised:
            main.save_mediakit_settings({
                "output_mode": "custom",
                "custom_output_dir": "",
            })
        self.assertEqual(raised.exception.status_code, 400)

    async def test_key_is_masked_and_can_be_cleared(self):
        public = main.public_mediakit_settings()
        self.assertTrue(public["configured"])
        self.assertNotIn("test-mediakit-key", public["key_preview"])

        await main.update_mediakit_settings({"clear_api_key": True})

        self.assertEqual(os.environ.get("MEDIAKIT_API_KEY"), "")
        self.assertNotIn("test-mediakit-key", self.env_file.read_text(encoding="utf-8"))


class MediaKitSubmitTests(MediaKitTestBase, unittest.IsolatedAsyncioTestCase):
    def test_defaults_and_fps_validation(self):
        params = main.mediakit_validate_request(self.request_payload())
        self.assertEqual(params, {"resolution": "720p", "bitrate_level": "medium", "fps": None})
        with self.assertRaises(main.HTTPException):
            main.mediakit_validate_request(self.request_payload(fps=121))

    def test_known_hdr_markers_are_blocked_but_unknown_is_allowed(self):
        pq, _ = self.video_file("pq.mp4", b"prefixnclx\x00\x01\x00\x10\x00\x01suffix")
        self.assertIn("PQ", main.mediakit_detect_hdr_marker(str(pq)))
        with self.assertRaises(main.HTTPException):
            main.mediakit_validate_local_input(str(pq))

        hlg, _ = self.video_file("hlg.mp4", b"prefixnclx\x00\x01\x00\x12\x00\x01suffix")
        self.assertIn("HLG", main.mediakit_detect_hdr_marker(str(hlg)))

        dolby, _ = self.video_file("dolby.mp4", b"prefixdvcCsuffix")
        self.assertEqual(main.mediakit_detect_hdr_marker(str(dolby)), "Dolby Vision")

        unknown, _ = self.video_file("unknown.mp4", b"no-color-metadata")
        self.assertEqual(main.mediakit_validate_local_input(str(unknown)), str(unknown))

    async def test_local_upload_uses_raw_put_and_returned_headers(self):
        path, _ = self.video_file(content=b"binary-video-content")
        fake = FakeMediaKitClient(post_responses=[
            FakeResponse({
                "code": 0,
                "result": {
                    "file_id": "mediakit://uploaded-file",
                    "method": "PUT",
                    "upload_url": "https://upload.example/signed",
                    "upload_headers": [
                        {"key": "Content-Type", "value": "video/mp4"},
                        {"key": "X-Upload-Token", "value": "signed-token"},
                    ],
                },
            })
        ])

        file_id = await main.mediakit_upload_local_video(fake, "fake-key", str(path))

        self.assertEqual(file_id, "mediakit://uploaded-file")
        self.assertEqual(fake.uploaded, b"binary-video-content")
        method, _, kwargs = fake.request_calls[0]
        self.assertEqual(method, "PUT")
        self.assertEqual(kwargs["headers"]["X-Upload-Token"], "signed-token")

    async def test_submit_omits_fps_and_is_idempotent(self):
        fake = FakeMediaKitClient(post_responses=[
            FakeResponse({"code": 0, "result": {"task_id": "remote-1"}})
        ])
        with patch.object(main.httpx, "AsyncClient", return_value=fake) as client_factory:
            first = await main.submit_mediakit_enhance_task(self.request_payload())
            second = await main.submit_mediakit_enhance_task(self.request_payload())

        self.assertEqual(first["task_id"], second["task_id"])
        self.assertEqual(client_factory.call_count, 1)
        body = fake.post_calls[0][1]["json"]
        self.assertNotIn("fps", body)
        self.assertEqual(body["video_url"], "https://example.com/source.mp4")
        self.assertEqual(body["client_token"], "test-token")

    async def test_submit_accepts_top_level_task_id(self):
        fake = FakeMediaKitClient(post_responses=[
            FakeResponse({
                "success": True,
                "task_id": "amk-tool-enhance-video-generative-1",
                "request_id": "request-1",
            })
        ])
        with patch.object(main.httpx, "AsyncClient", return_value=fake):
            result = await main.submit_mediakit_enhance_task(
                self.request_payload(token="top-level-token")
            )

        self.assertEqual(result["status"], "submitted")
        stored = main.mediakit_find_task(local_task_id=result["task_id"])
        self.assertEqual(stored["remote_task_id"], "amk-tool-enhance-video-generative-1")
        self.assertEqual(stored["remote_request_id"], "request-1")

    def test_response_payload_uses_business_error_message(self):
        response = FakeResponse({
            "success": False,
            "task_id": "",
            "error": {
                "code": "InvalidParameter",
                "message": "resolution is not supported",
            },
        })

        with self.assertRaises(main.HTTPException) as raised:
            main.mediakit_response_payload(response, "创建 MediaKit 增强任务")

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(raised.exception.detail, "resolution is not supported")

    async def test_parser_failure_retries_with_same_client_token(self):
        local_task_id = "mk_parser_failure"
        main.save_mediakit_tasks({"tasks": [{
            "id": local_task_id,
            "client_token": "retry-token",
            "status": "failed",
            "message": "",
            "error": "创建 MediaKit 增强任务响应缺少 result",
            "input_url": "https://example.com/source.mp4",
            "input_name": "source.mp4",
            "params": {"resolution": "720p", "bitrate_level": "medium", "fps": None},
            "remote_task_id": "",
            "remote_result_url": "",
            "created_at": main.now_ms(),
            "updated_at": main.now_ms(),
        }]})
        fake = FakeMediaKitClient(post_responses=[
            FakeResponse({"success": True, "task_id": "remote-recovered"})
        ])

        with patch.object(main.httpx, "AsyncClient", return_value=fake):
            result = await main.submit_mediakit_enhance_task(
                self.request_payload(token="retry-token")
            )

        self.assertEqual(result["task_id"], local_task_id)
        self.assertEqual(result["remote_task_id"], "remote-recovered")
        self.assertEqual(fake.post_calls[0][1]["json"]["client_token"], "retry-token")
        self.assertEqual(len(main.load_mediakit_tasks()["tasks"]), 1)

    async def test_other_failed_task_is_not_resubmitted(self):
        local_task_id = "mk_invalid_parameter"
        main.save_mediakit_tasks({"tasks": [{
            "id": local_task_id,
            "client_token": "invalid-token",
            "status": "failed",
            "message": "",
            "error": "resolution is not supported",
            "remote_task_id": "",
            "created_at": main.now_ms(),
            "updated_at": main.now_ms(),
        }]})

        with patch.object(main.httpx, "AsyncClient") as client_factory:
            result = await main.submit_mediakit_enhance_task(
                self.request_payload(token="invalid-token")
            )

        self.assertEqual(result["task_id"], local_task_id)
        self.assertEqual(result["status"], "failed")
        client_factory.assert_not_called()

    async def test_submit_local_video_uploads_before_enhance(self):
        _, url = self.video_file(content=b"local-video")
        fake = FakeMediaKitClient(post_responses=[
            FakeResponse({
                "code": 0,
                "result": {
                    "file_id": "mediakit://local-file",
                    "method": "PUT",
                    "upload_url": "https://upload.example/signed",
                    "upload_headers": [],
                },
            }),
            FakeResponse({"code": 0, "result": {"task_id": "remote-local"}}),
        ])
        with patch.object(main.httpx, "AsyncClient", return_value=fake):
            result = await main.submit_mediakit_enhance_task(self.request_payload(url=url, token="local-token"))

        self.assertEqual(result["status"], "submitted")
        self.assertEqual(fake.post_calls[1][1]["json"]["video_url"], "mediakit://local-file")
        self.assertEqual(fake.uploaded, b"local-video")


class MediaKitTaskLifecycleTests(MediaKitTestBase, unittest.IsolatedAsyncioTestCase):
    def seed_task(self, status="submitted", **extra):
        timestamp = main.now_ms()
        task = {
            "id": "mk_local",
            "client_token": "token",
            "status": status,
            "message": "",
            "error": "",
            "input_url": "https://example.com/source.mp4",
            "input_name": "source.mp4",
            "params": {"resolution": "720p", "bitrate_level": "medium", "fps": None},
            "remote_task_id": "remote-1",
            "remote_result_url": "",
            "created_at": timestamp,
            "updated_at": timestamp,
            **extra,
        }
        main.save_mediakit_tasks({"tasks": [task]})
        return task

    async def test_completed_task_is_saved_and_persisted(self):
        self.seed_task()
        fake = FakeMediaKitClient(get_response=FakeResponse({
            "code": 0,
            "result": {
                "status": "completed",
                "video_url": "https://result.example/enhanced.mp4",
            },
        }))
        saved = {
            "result_name": "enhanced.mp4",
            "result_url": "/api/storage-files/generated/mediakit-enhance/enhanced.mp4",
            "asset_url": "/assets/library/MediaKit/enhanced.mp4",
            "asset_id": "asset-1",
            "asset_error": "",
        }
        with patch.object(main.httpx, "AsyncClient", return_value=fake), patch.object(
            main, "mediakit_download_result", new=AsyncMock(return_value=saved)
        ) as download:
            result = await main.query_mediakit_enhance_task("mk_local")

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["result"]["url"], saved["asset_url"])
        download.assert_awaited_once()
        stored = main.mediakit_find_task(local_task_id="mk_local")
        self.assertEqual(stored["status"], "succeeded")

    async def test_top_level_query_status_with_nested_result_is_saved(self):
        self.seed_task()
        fake = FakeMediaKitClient(get_response=FakeResponse({
            "success": True,
            "task_id": "remote-1",
            "status": "completed",
            "result": {
                "video_url": "https://result.example/top-level.mp4",
            },
        }))
        saved = {
            "result_name": "top-level.mp4",
            "result_url": "/api/storage-files/generated/mediakit-enhance/top-level.mp4",
            "asset_url": "/assets/library/MediaKit/top-level.mp4",
            "asset_id": "asset-top-level",
            "asset_error": "",
        }
        with patch.object(main.httpx, "AsyncClient", return_value=fake), patch.object(
            main, "mediakit_download_result", new=AsyncMock(return_value=saved)
        ) as download:
            result = await main.query_mediakit_enhance_task("mk_local")

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["result"]["url"], saved["asset_url"])
        download.assert_awaited_once()

    async def test_save_failure_can_retry_without_new_enhance_submission(self):
        self.seed_task(status="save_failed", remote_result_url="https://result.example/enhanced.mp4")
        fake = FakeMediaKitClient()
        saved = {
            "result_name": "enhanced.mp4",
            "result_url": "/api/storage-files/generated/mediakit-enhance/enhanced.mp4",
            "asset_url": "",
            "asset_id": "",
            "asset_error": "",
        }
        with patch.object(main.httpx, "AsyncClient", return_value=fake), patch.object(
            main, "mediakit_download_result", new=AsyncMock(return_value=saved)
        ):
            result = await main.retry_mediakit_result_save("mk_local")

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(fake.post_calls, [])

    async def test_saving_task_recovers_after_backend_restart(self):
        self.seed_task(
            status="saving",
            remote_result_url="https://result.example/enhanced.mp4",
            saving_owner="previous-process",
        )
        fake = FakeMediaKitClient()
        saved = {
            "result_name": "enhanced.mp4",
            "result_url": "/api/storage-files/generated/mediakit-enhance/enhanced.mp4",
            "asset_url": "",
            "asset_id": "",
            "asset_error": "",
        }
        with patch.object(main.httpx, "AsyncClient", return_value=fake), patch.object(
            main, "mediakit_download_result", new=AsyncMock(return_value=saved)
        ) as download:
            result = await main.query_mediakit_enhance_task("mk_local")

        self.assertEqual(result["status"], "succeeded")
        download.assert_awaited_once()
        self.assertEqual(main.mediakit_find_task(local_task_id="mk_local")["saving_owner"], "")

    async def test_download_is_atomic_and_registers_asset(self):
        self.seed_task()
        fake = FakeMediaKitClient(
            stream_response=FakeResponse(
                body=b"enhanced-content",
                headers={"content-type": "video/mp4"},
            )
        )
        with patch.object(
            main,
            "register_mediakit_asset",
            return_value={"id": "asset-1", "url": "/assets/library/enhanced.mp4"},
        ):
            saved = await main.mediakit_download_result(fake, self.seed_task(), "https://result.example/video.mp4")

        final_path = self.generated / "mediakit-enhance" / saved["result_name"]
        self.assertEqual(final_path.read_bytes(), b"enhanced-content")
        self.assertFalse(Path(str(final_path) + ".part").exists())

    def test_result_route_rejects_path_traversal(self):
        main.save_mediakit_settings({
            "output_mode": "custom",
            "custom_output_dir": str(self.custom),
        })
        with self.assertRaises(main.HTTPException):
            main.mediakit_file_path("../secret.txt")

    def test_asset_registration_creates_video_category(self):
        source = self.root / "enhanced.mp4"
        source.write_bytes(b"video")

        item = main.register_mediakit_asset(str(source), "enhanced.mp4", "mk-1")

        self.assertEqual(item["kind"], "video")
        library = main.load_asset_library()
        category = next(cat for cat in library["categories"] if cat["id"] == "mediakit-videos")
        self.assertEqual(category["type"], "video")
        self.assertEqual(category["items"][0]["mediakit_task_id"], "mk-1")


if __name__ == "__main__":
    unittest.main()
