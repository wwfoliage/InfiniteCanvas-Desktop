# Canvas List Interaction Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent Edge native text-search dragging on the canvas list and make double-click creation/card dragging accurate under UI scaling.

**Architecture:** Keep all behavior inside `canvas-list.js`. Introduce one display-coordinate conversion layer shared by panning, wheel zoom, card dragging, and popup placement; suppress native drag/select only for non-interactive board targets; clamp the create popup in world coordinates after measuring its rendered size.

**Tech Stack:** Vanilla JavaScript, DOM events, CSS transforms/zoom, Python `unittest` static regression tests.

## Global Constraints

- Apply changes only to the canvas list; do not change normal-canvas or smart-canvas node interactions.
- Preserve card clicks, menus, title editing, buttons, form controls, and editable text.
- Keep the create popup near the pointer with a 10-screen-pixel offset and a 12-CSS-pixel visible-board margin.
- Do not change workflow import/export behavior.
- Preserve all existing user modifications in the dirty `E:\InfiniteCanvas` worktree.

---

### Task 1: Add coordinate and native-drag regression tests

**Files:**
- Create: `tests/test_canvas_list_interactions.py`
- Read: `static/js/canvas-list.js`

**Interfaces:**
- Consumes: Existing `screenToWorld(clientX, clientY)`, `onBoardPanStart(event)`, `openCreateCard(worldPoint)`, and board event bindings.
- Produces: Static regression expectations for `boardDisplayMetrics()`, `clientToBoard()`, `isBoardInteractiveTarget()`, `clampCreateCardPoint()`, and native-event suppression.

- [ ] **Step 1: Write the failing tests**

```python
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
        self.assertIn(compact("e.preventDefault();"), compact(self.source[self.source.index("function onBoardPanStart"):]))
        self.assertIn(compact("board.addEventListener('dragstart', suppressBoardNativeGesture)"), self.compact)
        self.assertIn(compact("board.addEventListener('selectstart', suppressBoardNativeGesture)"), self.compact)
        for selector in (
            ".ws-card",
            ".ws-create-card",
            ".ws-card-pop",
            "button",
            "input",
            "textarea",
            "select",
            "[contenteditable=\"true\"]",
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
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
.\python\python.exe -m unittest tests.test_canvas_list_interactions -v
```

Expected: FAIL because the display-coordinate helpers, native gesture listeners, and clamping helper do not yet exist.

- [ ] **Step 3: Commit the failing test**

```powershell
git add -- tests/test_canvas_list_interactions.py
git commit -m "test: cover canvas list pointer interactions"
```

### Task 2: Normalize canvas-list pointer coordinates

**Files:**
- Modify: `static/js/canvas-list.js:90-173`
- Test: `tests/test_canvas_list_interactions.py`

**Interfaces:**
- Consumes: `board`, `viewport`, `MIN_SCALE`, and `MAX_SCALE`.
- Produces:
  - `boardDisplayMetrics() -> { rect: DOMRect, scaleX: number, scaleY: number }`
  - `clientToBoard(clientX: number, clientY: number) -> { x: number, y: number }`
  - `screenToWorld(clientX: number, clientY: number) -> { x: number, y: number }`

- [ ] **Step 1: Implement rendered-scale-aware coordinate helpers**

Replace the current `screenToWorld()` with:

```javascript
function boardDisplayMetrics(){
    const rect = board.getBoundingClientRect();
    const scaleX = board.clientWidth > 0 && rect.width > 0 ? rect.width / board.clientWidth : 1;
    const scaleY = board.clientHeight > 0 && rect.height > 0 ? rect.height / board.clientHeight : 1;
    return {
        rect,
        scaleX: Number.isFinite(scaleX) && scaleX > 0 ? scaleX : 1,
        scaleY: Number.isFinite(scaleY) && scaleY > 0 ? scaleY : 1
    };
}
function clientToBoard(clientX, clientY){
    const { rect, scaleX, scaleY } = boardDisplayMetrics();
    return {
        x: (clientX - rect.left) / scaleX,
        y: (clientY - rect.top) / scaleY
    };
}
function screenToWorld(clientX, clientY){
    const point = clientToBoard(clientX, clientY);
    return {
        x: (point.x - viewport.x) / viewport.scale,
        y: (point.y - viewport.y) / viewport.scale
    };
}
```

- [ ] **Step 2: Make panning and wheel zoom use board-local deltas**

Store `scaleX`/`scaleY` in `panState` at pan start, divide mouse deltas by them in `onBoardPanMove()`, and replace the wheel handler’s raw `clientX - rect.left` math with:

```javascript
const point = clientToBoard(e.clientX, e.clientY);
const px = point.x, py = point.y;
```

Expected behavior: a 100-screen-pixel movement follows the pointer correctly even when the shell uses CSS `zoom`.

- [ ] **Step 3: Run the focused coordinate test**

Run:

```powershell
.\python\python.exe -m unittest tests.test_canvas_list_interactions.CanvasListInteractionTests.test_client_coordinates_account_for_rendered_board_scale -v
```

Expected: PASS.

- [ ] **Step 4: Commit coordinate normalization**

```powershell
git add -- static/js/canvas-list.js tests/test_canvas_list_interactions.py
git commit -m "fix: normalize canvas list pointer coordinates"
```

### Task 3: Suppress Edge native search gestures on empty board space

**Files:**
- Modify: `static/js/canvas-list.js:138-158,982-990`
- Test: `tests/test_canvas_list_interactions.py`

**Interfaces:**
- Consumes: Canvas-list DOM event targets.
- Produces:
  - `isBoardInteractiveTarget(target: EventTarget) -> boolean`
  - `suppressBoardNativeGesture(event: Event) -> void`

- [ ] **Step 1: Add a shared interactive-target predicate**

```javascript
function isBoardInteractiveTarget(target){
    return target instanceof Element && Boolean(target.closest(
        '.ws-card,.ws-create-card,.ws-card-pop,button,input,textarea,select,[contenteditable="true"]'
    ));
}
```

- [ ] **Step 2: Prevent native behavior only when an empty-board pan starts**

Change `onBoardPanStart()` to return for `isBoardInteractiveTarget(e.target)` and call `e.preventDefault()` immediately before initializing `panState`.

Add:

```javascript
function suppressBoardNativeGesture(e){
    if(!isBoardInteractiveTarget(e.target)) e.preventDefault();
}
```

Bind it only on the canvas-list board:

```javascript
board.addEventListener('dragstart', suppressBoardNativeGesture);
board.addEventListener('selectstart', suppressBoardNativeGesture);
```

- [ ] **Step 3: Run the native-gesture regression test**

Run:

```powershell
.\python\python.exe -m unittest tests.test_canvas_list_interactions.CanvasListInteractionTests.test_empty_board_pan_suppresses_native_browser_drag -v
```

Expected: PASS.

- [ ] **Step 4: Commit native gesture suppression**

```powershell
git add -- static/js/canvas-list.js tests/test_canvas_list_interactions.py
git commit -m "fix: stop native search drag on canvas list"
```

### Task 4: Position the create popup near the pointer and inside the board

**Files:**
- Modify: `static/js/canvas-list.js:474-516,987-990`
- Modify: `static/canvas-list.html:93`
- Test: `tests/test_canvas_list_interactions.py`

**Interfaces:**
- Consumes: A desired world point, measured `.ws-create-card` dimensions, `board.clientWidth`, `board.clientHeight`, and `viewport`.
- Produces: `clampCreateCardPoint(el: HTMLElement, worldPt: {x:number,y:number}) -> {x:number,y:number}`.

- [ ] **Step 1: Add world-space clamping**

Insert before `openCreateCard()`:

```javascript
function clampCreateCardPoint(el, worldPt){
    const margin = 12;
    const minX = (margin - viewport.x) / viewport.scale;
    const minY = (margin - viewport.y) / viewport.scale;
    const right = (board.clientWidth - margin - viewport.x) / viewport.scale;
    const bottom = (board.clientHeight - margin - viewport.y) / viewport.scale;
    const maxX = right - (el.offsetWidth || 230);
    const maxY = bottom - (el.offsetHeight || 150);
    return {
        x: maxX >= minX ? Math.min(Math.max(worldPt.x, minX), maxX) : minX,
        y: maxY >= minY ? Math.min(Math.max(worldPt.y, minY), maxY) : minY
    };
}
```

- [ ] **Step 2: Clamp after mounting and persist the final placement**

In `openCreateCard()`:

1. Append the element to `boardWorld`.
2. Compute `const placement = clampCreateCardPoint(el, worldPt)`.
3. Set `left` and `top` from `placement`.
4. Pass `placement` to `createCanvasOnBoard()` in the confirm closure.

Change the double-click binding to:

```javascript
board.addEventListener('dblclick', e => {
    if(e.target.closest('.ws-card') || e.target.closest('.ws-create-card')) return;
    openCreateCard(screenToWorld(e.clientX + 10, e.clientY + 10));
});
```

- [ ] **Step 3: Bump the canvas-list script cache key**

Change the query string in `static/canvas-list.html` to:

```html
<script src="/static/js/canvas-list.js?v=2026.07.30.canvas-list-pointer-fix"></script>
```

- [ ] **Step 4: Run the complete focused test file**

Run:

```powershell
.\python\python.exe -m unittest tests.test_canvas_list_interactions -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit popup positioning and cache bust**

```powershell
git add -- static/js/canvas-list.js static/canvas-list.html tests/test_canvas_list_interactions.py
git commit -m "fix: place canvas creation popup by pointer"
```

### Task 5: Browser verification and regression suite

**Files:**
- Verify: `static/js/canvas-list.js`
- Verify: `static/canvas-list.html`
- Verify: existing project tests

**Interfaces:**
- Consumes: Completed Tasks 1-4.
- Produces: Verified canvas-list interaction behavior.

- [ ] **Step 1: Run the project test suite**

Run:

```powershell
.\python\python.exe -m pytest tests -q
```

Expected: all tests PASS, including warm-theme, Seedance 480p, and MediaKit tests.

- [ ] **Step 2: Verify empty-board panning in Microsoft Edge**

Open the canvas list, press and drag on empty board space in several directions, and release.

Expected:

- Board pans continuously.
- No text highlight appears.
- Edge does not show “松开鼠标以搜索文本”.

- [ ] **Step 3: Verify interactive elements remain usable**

Click a canvas card, open its menu, edit a title if available, and interact with the new-canvas input.

Expected: clicks, menu actions, typing, and text selection inside the input still work.

- [ ] **Step 4: Verify double-click placement at center and four edges**

Double-click near the center, left, top, right, and bottom edges under the configured UI scale.

Expected: the popup appears about 10 screen pixels from the pointer and remains fully inside the visible board.

- [ ] **Step 5: Verify card dragging under UI scaling**

Drag an existing card by at least 200 screen pixels horizontally and vertically.

Expected: the card stays under the pointer without increasing positional drift.

