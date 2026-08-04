import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class APIMartLocalVideoUploadTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_video_url_is_returned_without_upload(self):
        with patch.object(main, "upload_local_video_to_cloud", new=AsyncMock()) as upload:
            result = await main.upload_video_for_apimart(
                object(), {"base_url": "https://api.apimart.ai"}, "https://media.example/reference.mp4"
            )

        self.assertEqual(result, "https://media.example/reference.mp4")
        upload.assert_not_awaited()

    async def test_configured_public_media_url_takes_precedence(self):
        with patch.object(
            main, "local_asset_public_url", return_value="https://canvas.example/assets/input/reference.mp4"
        ), patch.object(main, "upload_local_video_to_cloud", new=AsyncMock()) as upload:
            result = await main.upload_video_for_apimart(
                object(), {"base_url": "https://api.apimart.ai"}, "/assets/input/reference.mp4"
            )

        self.assertEqual(result, "https://canvas.example/assets/input/reference.mp4")
        upload.assert_not_awaited()

    async def test_local_video_is_uploaded_to_temporary_cloud(self):
        cloud_upload = AsyncMock(
            return_value={
                "url": "https://temp.example/reference.mp4",
                "service": "temp.sh",
            }
        )
        with patch.object(main, "local_asset_public_url", return_value=""), patch.object(
            main, "output_file_from_url", return_value=r"C:\temp\reference.mp4"
        ), patch.object(main, "content_type_for_path", return_value="video/mp4"), patch.object(
            main, "upload_local_video_to_cloud", new=cloud_upload
        ), patch.dict(os.environ, {"APIMART_TRY_VIDEO_UPLOAD": "0"}, clear=False):
            result = await main.upload_video_for_apimart(
                object(), {"base_url": "https://api.apimart.ai"}, "/assets/input/reference.mp4"
            )

        self.assertEqual(result, "https://temp.example/reference.mp4")
        cloud_upload.assert_awaited_once_with("/assets/input/reference.mp4", "auto")

    async def test_cloud_upload_failure_returns_original_reason(self):
        cloud_upload = AsyncMock(
            side_effect=main.HTTPException(status_code=502, detail="临时存储不可用")
        )
        with patch.object(main, "local_asset_public_url", return_value=""), patch.object(
            main, "output_file_from_url", return_value=r"C:\temp\reference.mp4"
        ), patch.object(main, "content_type_for_path", return_value="video/mp4"), patch.object(
            main, "upload_local_video_to_cloud", new=cloud_upload
        ), patch.dict(os.environ, {"APIMART_TRY_VIDEO_UPLOAD": "0"}, clear=False):
            result = await main.upload_video_for_apimart(
                object(), {"base_url": "https://api.apimart.ai"}, "/assets/input/reference.mp4"
            )

        self.assertTrue(result.startswith("ERR:"), result)
        self.assertIn("临时存储不可用", result)


if __name__ == "__main__":
    unittest.main()
