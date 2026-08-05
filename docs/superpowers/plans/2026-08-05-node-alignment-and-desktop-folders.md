# Node Alignment And Desktop Folders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace grid snapping with nearby-node alignment guides and make every desktop folder action reliable in the packaged application.

**Architecture:** Both canvases compute alignment from world-space rectangles using a six-screen-pixel threshold converted by viewport scale. Each axis independently picks the nearest left/center/right or top/center/bottom candidate and renders a short guide spanning the dragged and target bounds. Desktop folder actions use a same-origin HTTP bridge backed by the existing `DesktopApi`, with the PyWebView JavaScript API retained as a fallback.

**Tech Stack:** Vanilla JavaScript, CSS, FastAPI, PyWebView, Python unittest, PyInstaller, Inno Setup.

## Global Constraints

- Nearby nodes are the only snapping targets; the background grid is visual only.
- New nodes are placed freely and only dragging can snap.
- Multi-selection snaps by its overall bounding rectangle and preserves relative positions.
- Disabled snapping shows no guides and changes no coordinates.
- Folder routes accept only the existing allow-listed directory kinds.
- The packaged Windows app must be tested, not only mocked Python methods.

---

### Task 1: Behavior contracts

**Files:**
- Modify: `tests/test_canvas_list_interactions.py`
- Modify: `tests/test_snap_and_theme_contract.py`
- Modify: `tests/test_desktop_app.py`
- Modify: `tests/test_settings_behavior_contract.py`

**Interfaces:**
- Consumes: existing static source contract tests and `DesktopApi` mocks.
- Produces: failing tests for node-only snapping, guide lifecycle, HTTP bridge registration, and actionable errors.

- [ ] Add assertions that no grid constants or coordinate-rounding snap functions remain.
- [ ] Add assertions for six-pixel scaled threshold, edge/center candidates, and guide clearing.
- [ ] Add a FastAPI route test with a registered fake desktop API.
- [ ] Run `python -m unittest tests.test_canvas_list_interactions tests.test_snap_and_theme_contract tests.test_desktop_app tests.test_settings_behavior_contract -v` and confirm the new assertions fail.

### Task 2: Canvas-list alignment

**Files:**
- Modify: `static/js/canvas-list.js`
- Modify: `static/css/canvas-list.css`
- Modify: `static/canvas-list.html`

**Interfaces:**
- Consumes: canvas card positions, fixed card size, and `viewport.scale`.
- Produces: `alignBoardDrag(rawX, rawY, draggedId)` returning aligned coordinates and guide descriptors.

- [ ] Add one non-interactive guide layer inside the board world.
- [ ] Compute left/center/right and top/center/bottom candidates against all other cards.
- [ ] Apply the nearest candidate independently per axis only within `6 / viewport.scale` world units.
- [ ] Render guide segments spanning dragged and target rectangles and clear them on mouseup, rerender, toggle-off, and cancellation.
- [ ] Keep new-card coordinates free from alignment.
- [ ] Run the canvas-list contract tests.

### Task 3: Smart-canvas alignment

**Files:**
- Modify: `static/js/smart-canvas.js`
- Modify: `static/css/smart-canvas.css`
- Modify: `static/smart-canvas.html`

**Interfaces:**
- Consumes: `nodeRect(node)`, drag group snapshots, all nodes, and `viewport.scale`.
- Produces: `alignSmartDrag(rawDx, rawDy, dragState)` returning aligned deltas and guide descriptors.

- [ ] Build the dragged selection bounding rectangle from snapshot positions and current node sizes.
- [ ] Exclude all dragged IDs from candidate targets.
- [ ] Pick nearest axis candidates within the scaled threshold and apply the result to every dragged node.
- [ ] Render at most one vertical and one horizontal guide segment.
- [ ] Clear guides on mouseup, rerender, disabled toggle, asset drop, and aborted drag.
- [ ] Remove snapping from node creation helpers.
- [ ] Run smart-canvas contract tests.

### Task 4: Desktop folder bridge

**Files:**
- Create: `desktop_bridge.py`
- Modify: `main.py`
- Modify: `desktop_app.py`
- Modify: `static/js/settings.js`
- Modify: `static/js/downloads.js`

**Interfaces:**
- Consumes: registered `DesktopApi`, same-origin JSON requests, and allow-listed action names.
- Produces: `POST /api/desktop-action` with `{action, kind, payload}` and structured `{ok, error_code, message}` responses.

- [ ] Register the live `DesktopApi` before opening the window and unregister it during shutdown.
- [ ] Dispatch only choose-download-directory, choose-directory, open-directory, and install-update.
- [ ] Add start/success/cancel/failure logs to every desktop folder operation.
- [ ] Make settings and downloads call the HTTP bridge first and retain the PyWebView bridge as fallback for older builds.
- [ ] Surface returned error codes in the settings status instead of swallowing exceptions.
- [ ] Run desktop API and settings contract tests.

### Task 5: Verification and release

**Files:**
- Modify: `VERSION`
- Modify: installer/build metadata that embeds the version.

**Interfaces:**
- Consumes: passing test suite and release scripts already in `tools/` or `build/`.
- Produces: `InfiniteCanvas-Setup-2026.08.10.exe` and GitHub Release `v2026.08.10`.

- [ ] Run the complete unittest suite.
- [ ] Start the local UI and verify both canvases at desktop and narrow viewport sizes.
- [ ] Build the windowed PyInstaller executable and Inno Setup installer.
- [ ] Install over the current version and verify choose/open for downloads, data, cache, assets, and logs.
- [ ] Verify near-node edge/center snapping, no-target free dragging, toggle-off behavior, zoom behavior, and multi-select behavior.
- [ ] Commit, push `main`, create `v2026.08.10`, and upload the installer.
