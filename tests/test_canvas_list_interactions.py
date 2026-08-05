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
        cls.html = (ROOT / "static/canvas-list.html").read_text(encoding="utf-8")

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

    def test_node_snap_toggle_is_before_reset_view_and_remembered(self):
        self.assertLess(self.html.index('id="boardSnapToggle"'), self.html.index('id="boardResetView"'))
        for token in (
            "canvas_list_node_snap",
            "function alignBoardDrag(rawX, rawY, draggedId)",
            "NodeAlignment.findAlignment",
            "6 / viewport.scale",
            "function renderBoardAlignmentGuides(guides)",
            "function clearBoardAlignmentGuides()",
            "localStorage.setItem(CANVAS_LIST_SNAP_KEY",
        ):
            self.assertIn(compact(token), self.compact)
        self.assertNotIn("BOARD_GRID_SIZE", self.source)
        self.assertNotIn("snapBoardCoordinate", self.source)
        self.assertIn('/static/js/alignment-guides.js', self.html)

    def test_empty_board_uses_double_click_instruction_without_create_button(self):
        self.assertIn("双击空白处为当前项目创建第一块画布", self.html)
        self.assertNotIn('id="emptyCreateCanvasBtn"', self.html)
        self.assertNotIn("emptyCreateCanvasBtn", self.source)


if __name__ == "__main__":
    unittest.main()
