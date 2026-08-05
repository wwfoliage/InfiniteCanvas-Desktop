import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def compact(source: str) -> str:
    return re.sub(r"\s+", "", source).lower()


class SmartMediaKitBatchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
        cls.i18n = (ROOT / "static/js/i18n/smart-canvas.js").read_text(encoding="utf-8")
        cls.compact = compact(cls.js)

    def test_video_enhance_connections_allow_more_than_one_video_node(self):
        block = self.js[self.js.index("function connectInputNode"):self.js.index("function upstreamNodesForKinds")]
        self.assertIn(compact("if(!hasVideo) return false"), compact(block))
        self.assertNotIn("existingInputs.length", block)

    def test_all_sources_are_rendered_as_video_numbered_thumbnails(self):
        self.assertIn(compact("smartNodeInputThumbsHtml(sourceItems, {labelPrefix"), self.compact)
        self.assertIn("视频", self.js)

    def test_batch_runs_sequentially_and_collects_successes_in_group(self):
        for token in (
            "async function runSmartMediaKitBatch",
            "for(const entry of entries)",
            "await runSmartMediaKitSource",
            "createSmartGroupNode",
            "addNodeToSmartGroup",
            "mediakitBatchGroupId",
        ):
            self.assertIn(compact(token), self.compact)

    def test_failed_batch_item_can_be_retried_individually(self):
        self.assertIn("data-mediakit-batch-retry", self.js)
        self.assertIn(compact("startSmartMediaKitEnhance(btn.dataset.mediakitBatchRetry"), self.compact)

    def test_copy_mentions_multiple_video_support(self):
        self.assertIn("连接一个或多个视频", self.i18n)


if __name__ == "__main__":
    unittest.main()
