import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def compact(source: str) -> str:
    return re.sub(r"\s+", "", source).lower()


class SmartVideoBehaviorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "static/css/smart-canvas.css").read_text(encoding="utf-8")
        cls.html = (ROOT / "static/smart-canvas.html").read_text(encoding="utf-8")
        cls.compact = compact(cls.js)

    def test_video_preview_uses_native_muted_video_without_ffmpeg_thumbnail(self):
        block = self.js[self.js.index("function smartVideoPreviewHtml"):self.js.index("function smartVideoFallbackHtml")]
        self.assertIn("<video", block)
        self.assertIn("muted", block)
        self.assertIn('data-preview-kind="video"', block)
        self.assertNotIn("smartMediaPreviewUrl", block)

    def test_playback_state_identity_includes_node_and_media_index(self):
        self.assertIn(compact("function smartMediaPlaybackIdentity(media)"), self.compact)
        self.assertIn("dataset.imageIndex", self.js)
        self.assertIn(compact("pauseOtherCanvasMedia(video)"), self.compact)

    def test_video_play_button_tracks_real_playback_state(self):
        self.assertIn(compact("function bindSmartVideoPlaybackUi(video)"), self.compact)
        self.assertIn(".media-video-card.is-playing .smart-video-play", self.css)

    def test_video_nodes_use_contain_and_aspect_locked_resize(self):
        self.assertIn("object-fit:contain", compact(self.css))
        self.assertIn("resizeState.lockAspect", self.js)
        self.assertIn("resizeState.aspectRatio", self.js)

    def test_video_frame_toolbar_is_above_preview_stage(self):
        self.assertLess(self.html.index('id="videoFrameTools"'), self.html.index('id="imageEditStage"'))


if __name__ == "__main__":
    unittest.main()
