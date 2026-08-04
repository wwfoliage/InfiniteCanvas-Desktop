# InfiniteCanvas Toonflow Dark Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the InfiniteCanvas settings center's mixed blue/green dark styling with the approved Toonflow-derived neutral black-gray theme, restore the gear entry icon, eliminate uncovered host strips, and publish the complete `2026.08.06` Windows upgrade installer.

**Architecture:** Keep `static/css/settings.css` as the owner of settings-center appearance and override legacy global `.setting-row` rules through the existing `.settings-shell` root instead of changing shared theme behavior. Mark the main `.stage` as settings-active in `switchUI` so the host and iframe share the same fallback background, while the existing theme, scale, language, settings persistence, and download logic remain unchanged.

**Tech Stack:** HTML5, CSS, vanilla JavaScript, Python `unittest`, PyWebView, PyInstaller, Inno Setup 6, PowerShell, GitHub CLI.

## Global Constraints

- Dark palette values are fixed at `#181818`, `#242424`, `#2c2c2c`, `#393939`, `#4b4b4b`, white text at `0.9`, `0.55`, and `0.35` alpha, and enabled switch track `#717171`.
- Do not use blue or green for large dark-settings fills, selected navigation, segmented controls, or switches.
- Keep the existing warm-gray light mode unchanged.
- Change only the settings center, its host-stage fallback, resource cache versions, the real settings entry icon, and release metadata; do not recolor other product pages.
- Do not modify any file under `E:\Toonflow`.
- Do not add or migrate application settings fields; preserve all current theme, scale, language, download, API, workflow, storage, and update behavior.
- Version all release artifacts as `2026.08.06`; do not rewrite tag `v2026.08.05` or alter its build contents.
- Never delete or rewrite `%LOCALAPPDATA%\InfiniteCanvas`; the complete installer must support both clean installation and in-place upgrade.
- Continue using a windowed PyWebView build with no browser tab, CMD window, or residual process.
- Publish a full installer, not a differential patch.

---

### Task 1: Dark Settings Contract Tests

**Files:**
- Create: `tests/test_settings_dark_theme.py`
- Read: `static/css/settings.css`
- Read: `static/settings.html`
- Read: `static/index.html`

**Interfaces:**
- Consumes: existing settings CSS variables, `.settings-shell`, `.stage`, `switchUI`, and the real `switchUI(this, 'settings')` button.
- Produces: static contracts for the approved palette, scoped row ownership, continuous host background, cache versions, and gear icon.

- [ ] **Step 1: Add failing palette and scoped-row tests**

Create `tests/test_settings_dark_theme.py` with UTF-8 reads and these assertions:

```python
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class SettingsDarkThemeTests(unittest.TestCase):
    def test_dark_settings_use_approved_toonflow_gray_scale(self):
        css = read("static/css/settings.css").lower()
        for token in (
            "--settings-bg:#181818",
            "--settings-surface:#242424",
            "--settings-control:#2c2c2c",
            "--settings-hover:#393939",
            "--settings-control-active:#4b4b4b",
            "--settings-switch-on:#717171",
            "--settings-text:rgba(255,255,255,.9)",
            "--settings-muted:rgba(255,255,255,.55)",
            "--settings-faint:rgba(255,255,255,.35)",
        ):
            self.assertIn(token, css)
        for old_color in ("#121411", "#181b17", "#68b999", "#203a31"):
            self.assertNotIn(old_color, css)

    def test_settings_rows_are_scoped_and_transparent(self):
        css = read("static/css/settings.css")
        self.assertRegex(css, r"\.settings-shell\s+\.setting-row\s*\{[^}]*background:transparent")
        self.assertIn(".settings-shell .setting-group.divided .setting-row", css)
        self.assertIn(".settings-shell .switch-input:checked + .switch", css)

    def test_settings_background_fills_every_internal_layer(self):
        css = read("static/css/settings.css")
        for selector in (
            "html,body",
            ".settings-shell",
            ".settings-nav",
            ".settings-content",
        ):
            self.assertIn(selector, css)
        self.assertIn("min-height:100%", css)

    def test_settings_host_uses_gray_fallback_only_while_active(self):
        index = read("static/index.html")
        self.assertIn(".stage.settings-active", index)
        self.assertIn("#frame-settings", index)
        self.assertIn("classList.toggle('settings-active', id === 'settings')", index)

    def test_real_settings_entry_uses_gear_not_chain(self):
        index = read("static/index.html")
        match = re.search(
            r'<button class="side-pill" onclick="switchUI\(this, \'settings\'\)".*?</button>',
            index,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        button = match.group(0)
        self.assertIn('<circle cx="12" cy="12" r="3"></circle>', button)
        self.assertIn('M19.4 15', button)
        self.assertNotIn('x1="8" y1="12" x2="16" y2="12"', button)

    def test_settings_assets_use_new_cache_version(self):
        settings = read("static/settings.html")
        index = read("static/index.html")
        self.assertIn('/static/css/settings.css?v=2026.08.06.1', settings)
        self.assertIn('/static/settings.html?v=2026.08.06.1', index)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new tests and verify the old UI fails every new contract**

Run:

```powershell
python -m unittest tests.test_settings_dark_theme -v
```

Expected: FAIL because the old black-green tokens, unscoped row styles, blue host stage, chain icon, and `2026.08.04.1` cache versions are still present.

- [ ] **Step 3: Commit the failing contract tests**

```powershell
git add tests/test_settings_dark_theme.py
git commit -m "test: define dark settings theme contract"
```

---

### Task 2: Toonflow Gray Settings Surface

**Files:**
- Modify: `static/css/settings.css:1-92`
- Test: `tests/test_settings_dark_theme.py`
- Test: `tests/test_settings_center_structure.py`
- Test: `tests/test_warm_beige_light_theme.py`

**Interfaces:**
- Consumes: `html.studio-theme-dark`, `.settings-shell`, existing `--settings-*` tokens, and unchanged settings markup.
- Produces: approved black-gray variables and settings-root-scoped styles that supersede `static/css/theme.css` without changing that shared file.

- [ ] **Step 1: Replace only the dark settings variables with the approved palette**

Keep the light `:root` block unchanged. Replace the dark block with explicit surface levels:

```css
html.studio-theme-dark{
    --settings-bg:#181818;
    --settings-surface:#242424;
    --settings-control:#2c2c2c;
    --settings-hover:#393939;
    --settings-control-active:#4b4b4b;
    --settings-line:#393939;
    --settings-line-soft:rgba(255,255,255,.08);
    --settings-text:rgba(255,255,255,.9);
    --settings-muted:rgba(255,255,255,.55);
    --settings-faint:rgba(255,255,255,.35);
    --settings-switch-on:#717171;
    --settings-accent:#717171;
    --settings-accent-soft:#303030;
    --settings-danger:#ef8178;
}
```

Add light-theme fallback definitions for every newly introduced token so selectors can use the same variables in both modes:

```css
:root{
    --settings-control:var(--settings-surface);
    --settings-hover:var(--settings-line-soft);
    --settings-control-active:var(--settings-line);
    --settings-switch-on:var(--settings-accent);
}
```

Place those fallback declarations directly in the existing root block rather than creating a second `:root` block.

- [ ] **Step 2: Make all internal layout layers continuously fill the iframe**

Change the root sizing and explicitly inherit the page background:

```css
html,body{margin:0;width:100%;height:100%;min-height:100%;background:var(--settings-bg);color:var(--settings-text);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:0}
body{overflow:hidden}
.settings-shell{width:100%;height:100%;min-height:100%;display:grid;grid-template-columns:222px 1px minmax(0,1fr);background:var(--settings-bg)}
.settings-nav,.settings-content{background:var(--settings-bg)}
```

Retain the existing content scrolling and responsive grid behavior.

- [ ] **Step 3: Scope row and control appearance under `.settings-shell`**

Increase specificity over legacy `theme.css` without using `!important`:

```css
.settings-shell .setting-row{background:transparent;color:var(--settings-text)}
.settings-shell .setting-group.divided .setting-row{background:transparent;border-bottom:1px solid var(--settings-line-soft)}
.settings-shell .directory-control output,
.settings-shell .command,
.settings-shell .icon-command{background:var(--settings-control)}
.settings-shell .command:hover,
.settings-shell .icon-command:hover{background:var(--settings-hover)}
.settings-shell .settings-nav-item.active{background:#303030;color:var(--settings-text)}
.settings-shell .switch-input:checked + .switch{background:var(--settings-switch-on)}
.settings-shell .segmented{background:var(--settings-control)}
.settings-shell .segmented button:hover{background:var(--settings-hover);color:var(--settings-text)}
.settings-shell .segmented button.active{background:var(--settings-control-active);color:var(--settings-text)}
```

Keep ordinary row fills transparent. Do not introduce cards around sections or use blue/green active states.

- [ ] **Step 4: Run dark-theme, settings-structure, and light-theme regression tests**

Run only the contracts owned by this task, plus the existing settings and light-theme suites:

```powershell
python -m unittest `
  tests.test_settings_dark_theme.SettingsDarkThemeTests.test_dark_settings_use_approved_toonflow_gray_scale `
  tests.test_settings_dark_theme.SettingsDarkThemeTests.test_settings_rows_are_scoped_and_transparent `
  tests.test_settings_dark_theme.SettingsDarkThemeTests.test_settings_background_fills_every_internal_layer `
  tests.test_settings_center_structure `
  tests.test_warm_beige_light_theme -v
```

Expected: PASS; existing warm-gray light-theme tests remain green. The host, icon, and cache contracts are run after their implementation in Task 3.

- [ ] **Step 5: Commit the settings surface**

```powershell
git add static/css/settings.css
git commit -m "style: apply neutral dark settings palette"
```

---

### Task 3: Host Coverage, Gear Icon, and Cache Busting

**Files:**
- Modify: `static/index.html:385-408`
- Modify: `static/index.html:1557-1574`
- Modify: `static/index.html:1639`
- Modify: `static/index.html:1837-1865`
- Modify: `static/settings.html:12`
- Test: `tests/test_settings_dark_theme.py`
- Test: `tests/test_sidebar_footer_cleanup.py`

**Interfaces:**
- Consumes: `switchUI(el, id, options)`, `.stage`, `#frame-settings`, and the hidden legacy gear SVG.
- Produces: `.stage.settings-active`, an opaque `#frame-settings` fallback, the restored real gear button, and cache key `2026.08.06.1`.

- [ ] **Step 1: Give the settings host a matching fallback surface**

Add these scoped rules beside the existing `.stage` and iframe rules:

```css
.stage.settings-active{
    background:#181818;
    border-color:#393939;
}
#frame-settings{background:#181818}
```

Do not change `--stage-bg` or the normal dark palette because every non-settings page must retain its existing appearance.

- [ ] **Step 2: Toggle the host state in the existing page switch**

Immediately after resolving the valid page id in `switchUI`, add:

```javascript
const stage = document.querySelector('.stage');
stage?.classList.toggle('settings-active', id === 'settings');
```

The existing startup restoration already calls `switchUI(trigger, id, {skipRemember:true})`. Keep the class toggle before iframe activation inside `switchUI`, so startup restoration and later navigation use one state mechanism. Do not modify the pre-DOM sidebar-selection script.

- [ ] **Step 3: Restore the original line gear on the real settings button**

Replace the chain SVG inside the one visible `switchUI(this, 'settings')` button with the circle-and-cog-path SVG currently stored in the adjacent hidden button. Leave the visible button label, click behavior, dimensions, and accessibility attributes unchanged. The hidden compatibility group remains hidden.

- [ ] **Step 4: Increment settings cache versions**

Change:

```html
<link rel="stylesheet" href="/static/css/settings.css?v=2026.08.06.1">
```

and:

```html
<iframe id="frame-settings" data-src="/static/settings.html?v=2026.08.06.1" scrolling="yes"></iframe>
```

No JavaScript setting logic changed, so retain the current `settings.js`, `theme.js`, `i18n.js`, and `downloads.js` query values.

- [ ] **Step 5: Run the complete settings contracts**

Run:

```powershell
python -m unittest tests.test_settings_dark_theme tests.test_settings_center_structure tests.test_settings_behavior_contract tests.test_sidebar_footer_cleanup tests.test_warm_beige_light_theme -v
```

Expected: PASS with no failures; the light palette and existing settings behavior remain unchanged.

- [ ] **Step 6: Commit host and icon fixes**

```powershell
git add static/index.html static/settings.html tests/test_settings_dark_theme.py
git commit -m "fix: unify settings host and restore gear icon"
```

---

### Task 4: Desktop and Responsive Visual Acceptance

**Files:**
- Verify: `static/index.html`
- Verify: `static/settings.html`
- Verify: `static/css/settings.css`
- Output: `work/settings-dark-1440x900.png`
- Output: `work/settings-dark-1024x700.png`
- Output: `work/settings-dark-390x844.png`

**Interfaces:**
- Consumes: the completed static settings UI and existing local application server.
- Produces: evidence that the approved gray hierarchy renders continuously at desktop and narrow widths with functional section switching.

- [ ] **Step 1: Start the source application without opening a browser**

Run:

```powershell
python main.py
```

Wait until `http://127.0.0.1:3000` responds. Keep this process attached to a managed terminal cell and stop it after screenshots.

- [ ] **Step 2: Capture the settings route at three viewport sizes**

Use Playwright with installed Edge and open `http://127.0.0.1:3000/static/index.html`. Before reload set `studio_theme=dark` and `studio_active_page=settings` in local storage, then capture `1440x900`, `1024x700`, and `390x844` screenshots. At each size inspect both `downloads` and `appearance` sections.

Expected:

```text
- The stage, iframe, navigation, content, scrollbar track, and bottom edge are continuously black-gray.
- No #0f141d/#111722 strip is visible around or below settings.
- Download rows are transparent; only inputs and buttons use a raised surface.
- Active navigation, switches, and segmented choices are gray rather than blue or green.
- The left-bottom settings entry is a line gear.
- At 390px no text, path, button, switch, or navigation icon overlaps or produces horizontal overflow.
```

- [ ] **Step 3: Exercise settings interactions before accepting the screenshots**

Click every secondary navigation entry, switch between light and dark and back to dark, click the three appearance modes without persisting a different final theme, and toggle the two download switches. Confirm there are no JavaScript console errors and embedded API/workflow pages still load.

- [ ] **Step 4: Run CSS and HTML source scans**

Run:

```powershell
rg -n "#121411|#181b17|#68b999|#203a31" static/css/settings.css
rg -n "#0f141d|#111722|#2a3444" static/css/settings.css
git diff --check
```

Expected: no matches in `settings.css`; `git diff --check` exits successfully.

- [ ] **Step 5: Fix any visual failure in the owning file and rerun Tasks 3 and 4 checks**

Only adjust `static/css/settings.css`, `static/settings.html`, or the settings-scoped rules/state in `static/index.html`. Do not change unrelated page colors or settings behavior. Commit a visual correction only if this step produces changes:

```powershell
git add static/css/settings.css static/settings.html static/index.html
git commit -m "fix: refine dark settings layout"
```

---

### Task 5: Version 2026.08.06 and Full Regression

**Files:**
- Modify: `VERSION`
- Regenerate: `build/windows/version_info.txt`
- Regenerate: `build/windows/InfiniteCanvas.ico`
- Test: all `tests/test_*.py`

**Interfaces:**
- Consumes: the accepted settings UI and `build/windows/make_icon.py`.
- Produces: consistent source, executable metadata, and installer version `2026.08.06`.

- [ ] **Step 1: Set the release version**

Replace the only line in `VERSION`:

```text
2026.08.06
```

- [ ] **Step 2: Regenerate icon and Windows version metadata**

Run:

```powershell
python build/windows/make_icon.py --root .
```

Expected: `build/windows/version_info.txt` contains both `FileVersion` and `ProductVersion` as `2026.08.06`, and the generated tuple is `(2026, 8, 6, 0)`.

- [ ] **Step 3: Run the full test suite**

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected: zero failures and zero errors.

- [ ] **Step 4: Verify version and source integrity**

```powershell
rg -n "2026\.08\.05" VERSION build/windows/version_info.txt
git diff --check
git status --short
```

Expected: no old-version match in the two release metadata files, no whitespace errors, and only intended release files are modified.

- [ ] **Step 5: Commit the release version**

```powershell
git add VERSION build/windows/version_info.txt build/windows/InfiniteCanvas.ico
git commit -m "chore: prepare InfiniteCanvas 2026.08.06"
```

---

### Task 6: Build, Installer Upgrade Tests, and Real Desktop Acceptance

**Files:**
- Verify: `build/windows/build_release.ps1`
- Verify: `build/windows/InfiniteCanvas.iss`
- Verify: `build/windows/test_installer_upgrade.ps1`
- Output: `dist/InfiniteCanvas/InfiniteCanvas.exe`
- Output: `dist/release-manifest.json`
- Output: `dist/installer/InfiniteCanvas-Setup-2026.08.06.exe`
- Output: `dist/installer/SHA256SUMS.txt`
- Output: `E:\codex\发布安装包\InfiniteCanvas\2026.08.06\*`

**Interfaces:**
- Consumes: source version `2026.08.06`, PyInstaller, Inno Setup 6, stable installer `AppId`, and the complete regression suite.
- Produces: one complete installer that supports clean install and upgrade while preserving user data.

- [ ] **Step 1: Build the windowed app and installer through the canonical script**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File build/windows/build_release.ps1
```

Expected: tests pass; PyInstaller creates a windowed app; release verification passes; Inno Setup creates `InfiniteCanvas-Setup-2026.08.06.exe`; and `SHA256SUMS.txt` contains its lowercase SHA-256.

- [ ] **Step 2: Run isolated clean-install and legacy-runtime upgrade smoke tests**

Use an explicit non-root test directory:

```powershell
powershell -ExecutionPolicy Bypass -File build/windows/test_installer_upgrade.ps1 `
  -SourceDir "E:\codex\项目源码\InfiniteCanvas-Desktop\source\dist\InfiniteCanvas" `
  -TestRoot "E:\codex\临时测试\InfiniteCanvas-2026.08.06"
```

Expected: clean installation succeeds, a synthetic old `websockets` runtime is removed on upgrade, the executable is restored, and the test user-data sentinel remains unchanged.

- [ ] **Step 3: Snapshot real user data before upgrading the existing installation**

Create a sorted SHA-256 inventory of every file under `%LOCALAPPDATA%\InfiniteCanvas` in the release working directory. Record path, length, and hash. Exclude nothing; do not modify the user-data tree.

- [ ] **Step 4: Install the new complete package over the current real installation**

Run `InfiniteCanvas-Setup-2026.08.06.exe` normally and let the stable `AppId` select the existing install location. Close the running app if prompted. Do not uninstall the old version first.

- [ ] **Step 5: Compare the real user-data inventory after upgrade**

Generate the same sorted path/length/hash inventory and compare it with the pre-upgrade snapshot.

Expected: no file is missing or changed. Files created by the first post-upgrade launch are inventoried separately and must be limited to expected logs or caches; canvases, assets, API configuration, application settings, language, theme, scale, and download settings remain byte-identical.

- [ ] **Step 6: Launch and inspect the installed PyWebView application**

Verify:

```text
1. About & Updates reports 2026.08.06.
2. Only the InfiniteCanvas desktop window opens; no browser or CMD appears.
3. The settings center matches the approved black-gray preview at normal and maximized sizes.
4. Download settings still choose/open/reset the directory and both switches persist.
5. Closing the window leaves no InfiniteCanvas, Python, Uvicorn, or child runtime process.
```

- [ ] **Step 7: Copy verified release materials to the organized release folder**

Create `E:\codex\发布安装包\InfiniteCanvas\2026.08.06` and copy exactly:

```text
InfiniteCanvas-Setup-2026.08.06.exe
SHA256SUMS.txt
release-manifest.json
```

Recompute the installer hash in the destination and require it to match `SHA256SUMS.txt`.

---

### Task 7: Git and GitHub Release

**Files:**
- Verify: all tracked source and documentation files
- Upload: `E:\codex\发布安装包\InfiniteCanvas\2026.08.06\InfiniteCanvas-Setup-2026.08.06.exe`
- Upload: `E:\codex\发布安装包\InfiniteCanvas\2026.08.06\SHA256SUMS.txt`
- Upload: `E:\codex\发布安装包\InfiniteCanvas\2026.08.06\release-manifest.json`

**Interfaces:**
- Consumes: clean `main`, verified `2026.08.06` artifacts, authenticated `gh`, and remote `origin` at `wwfoliage/InfiniteCanvas-Desktop`.
- Produces: pushed source commit, immutable `v2026.08.06` tag, and a new GitHub Release with three verified files.

- [ ] **Step 1: Verify local repository and artifact identity**

Run:

```powershell
git status --short --branch
git log -6 --oneline
Get-FileHash "E:\codex\发布安装包\InfiniteCanvas\2026.08.06\InfiniteCanvas-Setup-2026.08.06.exe" -Algorithm SHA256
Get-Content "E:\codex\发布安装包\InfiniteCanvas\2026.08.06\SHA256SUMS.txt"
```

Expected: working tree clean, intended commits are on `main`, and installer hashes match exactly.

- [ ] **Step 2: Push main and create the new version tag**

```powershell
git push origin main
git tag -a v2026.08.06 -m "InfiniteCanvas 2026.08.06"
git push origin v2026.08.06
```

Do not force-push and do not move or delete `v2026.08.05`.

- [ ] **Step 3: Create the GitHub Release with the complete installer**

Create release `v2026.08.06` in `wwfoliage/InfiniteCanvas-Desktop` with title `InfiniteCanvas 2026.08.06` and these concise notes:

```markdown
## 更新内容

- 设置界面深色模式改为 Toonflow 风格的中性黑灰配色。
- 修复下载设置行、底部和外围容器颜色不一致的问题。
- 恢复左下角线框齿轮设置图标。
- 继续提供完整安装包，支持新电脑安装和旧版本直接覆盖升级。

升级不会清理 `%LOCALAPPDATA%\InfiniteCanvas` 中的画布、素材、API 配置和应用设置。
```

Attach the installer, `SHA256SUMS.txt`, and `release-manifest.json`. Do not edit, publish, or delete the old `2026.08.05` draft as part of this task.

- [ ] **Step 4: Verify the published release**

```powershell
gh release view v2026.08.06 --repo wwfoliage/InfiniteCanvas-Desktop
git status --short --branch
```

Expected: release is published with exactly the three intended assets, `main` tracks `origin/main`, and the working tree is clean.
