import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def compact(source: str) -> str:
    return re.sub(r"\s+", "", source).lower()


class CanvasListInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "static/js/canvas-list.js").read_text(encoding="utf-8")
        cls.compact = compact(cls.source)

    def test_client_coordinates_account_for_rendered_board_scale(self):
        for token in (
            "function boardDisplayMetrics()",
            "rect.width / board.clientWidth",
            "rect.height / board.clientHeight",
            "function clientToBoard(clientX, clientY)",
            "(clientX - rect.left) / scaleX",
            "(clientY - rect.top) / scaleY",
        ):
            self.assertIn(compact(token), self.compact)

    def test_empty_board_pan_suppresses_native_browser_drag(self):
        self.assertIn(compact("function isBoardInteractiveTarget(target)"), self.compact)
        pan_start = self.source[
            self.source.index("function onBoardPanStart"):
            self.source.index("function onBoardPanMove")
        ]
        self.assertIn("e.preventDefault();", pan_start)
        self.assertIn(
            compact("board.addEventListener('dragstart', suppressBoardNativeGesture)"),
            self.compact,
        )
        self.assertIn(
            compact("board.addEventListener('selectstart', suppressBoardNativeGesture)"),
            self.compact,
        )
        for selector in (
            ".ws-card",
            ".ws-create-card",
            ".ws-card-pop",
            "button",
            "input",
            "textarea",
            "select",
            '[contenteditable="true"]',
        ):
            self.assertIn(selector, self.source)

    def test_create_popup_uses_pointer_offset_and_visible_board_clamp(self):
        for token in (
            "function clampCreateCardPoint(el, worldPt)",
            "const margin = 12",
            "screenToWorld(e.clientX + 10, e.clientY + 10)",
            "const placement = clampCreateCardPoint(el, worldPt)",
            "createCanvasOnBoard(input.value.trim(), createKind, placement)",
        ):
            self.assertIn(compact(token), self.compact)


if __name__ == "__main__":
    unittest.main()
