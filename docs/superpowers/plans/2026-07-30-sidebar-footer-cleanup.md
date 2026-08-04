# Sidebar Footer Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the user-marked project/update/author block from the shared left sidebar while retaining all settings controls.

**Architecture:** Remove only the shared shell markup that renders the unwanted footer and the startup call that automatically checks for updates. Keep dormant update functions, modal markup, and backend APIs intact to minimize risk.

**Tech Stack:** HTML, inline JavaScript, Python `unittest` static regression tests.

## Global Constraints

- Remove project home, update/version UI, `DX`, author name, and all four social links.
- Preserve API 设置, 更多设置, theme, language, and 工作流设置.
- Stop the startup-time update check because no visible update entry remains.
- Keep update implementation functions, update modal markup, and backend update APIs unchanged.
- Do not change workflow import/export behavior.
- Preserve all existing user modifications in the dirty `E:\InfiniteCanvas` worktree.

---

### Task 1: Add sidebar cleanup regression tests

**Files:**
- Create: `tests/test_sidebar_footer_cleanup.py`
- Read: `static/index.html`

**Interfaces:**
- Consumes: Shared sidebar markup in `static/index.html`.
- Produces: Regression checks for removed and retained controls.

- [ ] **Step 1: Write the failing tests**

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SidebarFooterCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "static/index.html").read_text(encoding="utf-8")

    def test_project_update_and_author_footer_is_removed(self):
        for token in (
            'id="github-entry-btn"',
            'id="update-now-btn"',
            'id="project-version-badge"',
            'class="author-box"',
            'class="author-name-lite"',
            "wuli大雄",
            "space.bilibili.com/78652351",
            "xiaohongshu.com/user/profile/6433c34c000000001a023538",
            "youtube.com/@%E5%A4%A7%E9%9B%84dx",
            "x.com/dx8152",
        ):
            self.assertNotIn(token, self.source)

    def test_required_settings_controls_remain(self):
        for token in (
            "switchUI(this, 'api-settings')",
            'id="settings-fold-toggle"',
            'id="theme-toggle-btn"',
            'id="lang-toggle-btn"',
            "switchUI(this, 'comfyui-settings')",
        ):
            self.assertIn(token, self.source)

    def test_startup_no_longer_checks_for_updates(self):
        self.assertNotIn("\n            checkForUpdates();\n", self.source)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
.\python\python.exe -m unittest tests.test_sidebar_footer_cleanup -v
```

Expected: the removal tests FAIL because the sidebar footer and startup update call still exist; the retained-control test PASSes.

- [ ] **Step 3: Commit the failing test**

```powershell
git add -- tests/test_sidebar_footer_cleanup.py
git commit -m "test: cover sidebar footer cleanup"
```

### Task 2: Remove the shared sidebar footer UI

**Files:**
- Modify: `static/index.html:1611-1660`
- Modify: `static/index.html:2120`
- Test: `tests/test_sidebar_footer_cleanup.py`

**Interfaces:**
- Consumes: Existing `.side-actions` container and shared sidebar shell.
- Produces: A sidebar whose last visible controls are API 设置 and the 更多设置 group.

- [ ] **Step 1: Remove project/update markup from `.side-actions`**

Delete the three elements beginning with:

```html
<button id="github-entry-btn" ...>
<button id="update-now-btn" ...>
<div id="project-version-badge" ...>
```

Keep the closing `</div>` for `.side-actions`.

- [ ] **Step 2: Remove the author block**

Delete the entire block:

```html
<div class="author-box">
    ...
</div>
```

This removes `DX`, `wuli大雄`, Bilibili, Xiaohongshu, YouTube, and X links.

- [ ] **Step 3: Stop the startup update check**

Inside the existing `DOMContentLoaded` callback, delete only:

```javascript
checkForUpdates();
```

Do not delete `checkForUpdates`, `runProjectUpdate`, modal functions, modal markup, or backend endpoints.

- [ ] **Step 4: Run the focused tests**

Run:

```powershell
.\python\python.exe -m unittest tests.test_sidebar_footer_cleanup -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit the sidebar cleanup**

```powershell
git add -- static/index.html tests/test_sidebar_footer_cleanup.py
git commit -m "refactor: remove sidebar project footer"
```

### Task 3: Visual and full-suite verification

**Files:**
- Verify: `static/index.html`
- Verify: existing project tests

**Interfaces:**
- Consumes: Completed Tasks 1-2.
- Produces: Verified sidebar layout across shared pages.

- [ ] **Step 1: Run the project test suite**

Run:

```powershell
.\python\python.exe -m pytest tests -q
```

Expected: all tests PASS.

- [ ] **Step 2: Verify the expanded sidebar**

Open the canvas list, ordinary canvas, and smart canvas through the shared shell.

Expected:

- No 项目主页, update/version, `DX`, author, or social-link UI appears.
- API 设置 and 更多设置 remain aligned at the bottom.

- [ ] **Step 3: Verify the collapsed sidebar**

Collapse the sidebar and switch among the same pages.

Expected: no empty footer artifact or unused vertical gap appears; retained controls remain clickable.

- [ ] **Step 4: Verify retained settings**

Open API 设置, expand 更多设置, toggle theme/language, and open 工作流设置.

Expected: all retained controls still navigate or toggle normally.
