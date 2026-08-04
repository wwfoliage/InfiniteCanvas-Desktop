# InfiniteCanvas Full Upgrade Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `2026.08.05` as one complete Windows installer that supports both first installation and clean in-place upgrades while preserving all user data.

**Architecture:** Keep the existing stable Inno Setup `AppId` and per-user installation model. Before Inno copies the new PyInstaller payload, a `PrepareToInstall` handler removes only `{app}\_internal` and `{app}\InfiniteCanvas.exe`, aborting with an actionable message if either old runtime target cannot be removed. A separate smoke-test script compiles an unregistered installer variant and exercises empty installation plus an upgrade over deliberately seeded legacy runtime residue.

**Tech Stack:** Python 3.11, `unittest`, PyInstaller, PowerShell 5+, Inno Setup 6, PyWebView

## Global Constraints

- Release version is exactly `2026.08.05`.
- Keep `AppId={{61D4D665-79A6-4C85-A5D0-FE262538F79C}` unchanged.
- Keep `PrivilegesRequired=lowest`, `CloseApplications=yes`, and the per-user default installation directory.
- Delete only `{app}\_internal` and `{app}\InfiniteCanvas.exe` before copying the new runtime.
- Never delete, rewrite, or add installer cleanup rules for `%LOCALAPPDATA%\InfiniteCanvas`.
- The same complete installer must support both a new computer and an existing installation; do not produce a differential patch.
- Final release files belong in `E:\codex\发布安装包\InfiniteCanvas\2026.08.05`.

---

### Task 1: Enforce Clean Runtime Replacement

**Files:**
- Modify: `tests/test_installer_definition.py`
- Modify: `build/windows/InfiniteCanvas.iss`

**Interfaces:**
- Consumes: Inno Setup constants `{app}` and the existing `[Files]` payload declaration.
- Produces: `PrepareToInstall(var NeedsRestart: Boolean): String`, which returns an empty string on success or an error message that aborts installation.

- [ ] **Step 1: Write failing installer policy tests**

Add tests that require `DelTree(ExpandConstant('{app}\_internal'), True, True, True)`, `DeleteFile(ExpandConstant('{app}\InfiniteCanvas.exe'))`, explicit failure checks, and the absence of `localappdata` from cleanup code. Keep the stable `AppId` assertion exact.

```python
def test_upgrade_removes_only_old_runtime_before_copy(self):
    script = INSTALLER_SCRIPT.read_text(encoding="utf-8-sig")
    self.assertIn("function PrepareToInstall(var NeedsRestart: Boolean): String;", script)
    self.assertIn("DelTree(RuntimeDir, True, True, True)", script)
    self.assertIn("DeleteFile(ExecutablePath)", script)
    self.assertIn("if DirExists(RuntimeDir)", script)
    self.assertIn("if FileExists(ExecutablePath)", script)

def test_cleanup_does_not_target_user_data_or_whole_app_directory(self):
    script = INSTALLER_SCRIPT.read_text(encoding="utf-8-sig")
    cleanup = script.split("function PrepareToInstall", 1)[1]
    self.assertNotIn("localappdata", cleanup.lower())
    self.assertNotIn("DelTree(ExpandConstant('{app}')", cleanup)
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run:

```powershell
E:\codex\构建工具\InfiniteCanvas-打包环境\Scripts\python.exe -m unittest tests.test_installer_definition -v
```

Expected: the new cleanup tests fail because `PrepareToInstall` does not exist.

- [ ] **Step 3: Implement pre-copy cleanup with failure handling**

Add this logic to `[Code]`, retaining the existing WebView2 check:

```pascal
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  RuntimeDir: String;
  ExecutablePath: String;
begin
  Result := '';
  RuntimeDir := ExpandConstant('{app}\_internal');
  ExecutablePath := ExpandConstant('{app}\InfiniteCanvas.exe');

  if DirExists(RuntimeDir) and
     (not DelTree(RuntimeDir, True, True, True)) then
  begin
    Result := 'The previous InfiniteCanvas runtime could not be removed.';
    Exit;
  end;

  if FileExists(ExecutablePath) and
     (not DeleteFile(ExecutablePath)) then
  begin
    Result := 'The previous InfiniteCanvas executable could not be removed.';
    Exit;
  end;
end;
```

- [ ] **Step 4: Run the focused and full unit test suites**

Run:

```powershell
E:\codex\构建工具\InfiniteCanvas-打包环境\Scripts\python.exe -m unittest tests.test_installer_definition -v
E:\codex\构建工具\InfiniteCanvas-打包环境\Scripts\python.exe -m unittest discover -s tests -p test_*.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit the installer behavior**

```powershell
git add tests/test_installer_definition.py build/windows/InfiniteCanvas.iss
git commit -m "fix: replace legacy runtime during upgrades"
```

### Task 2: Add Repeatable Installer Smoke Coverage

**Files:**
- Create: `build/windows/test_installer_upgrade.ps1`
- Modify: `tests/test_installer_definition.py`

**Interfaces:**
- Consumes: `InfiniteCanvas.iss`, a populated `dist/InfiniteCanvas`, Inno Setup `ISCC.exe`, and a caller-provided temporary root.
- Produces: a PowerShell smoke test that exits `0` only after empty install and dirty upgrade both pass, and never deletes paths outside its verified test root.

- [ ] **Step 1: Write a failing contract test for the smoke script**

```python
INSTALLER_SMOKE_SCRIPT = Path(__file__).resolve().parents[1] / "build" / "windows" / "test_installer_upgrade.ps1"

def test_upgrade_smoke_script_covers_clean_install_and_legacy_residue(self):
    script = INSTALLER_SMOKE_SCRIPT.read_text(encoding="utf-8-sig")
    self.assertIn("/DSmokeTestRoot=", script)
    self.assertIn("legacy-speedups.cp310-win_amd64.pyd", script)
    self.assertIn("/VERYSILENT", script)
    self.assertIn("InfiniteCanvas.exe", script)
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```powershell
E:\codex\构建工具\InfiniteCanvas-打包环境\Scripts\python.exe -m unittest tests.test_installer_definition.InstallerDefinitionTests.test_upgrade_smoke_script_covers_clean_install_and_legacy_residue -v
```

Expected: FAIL because `test_installer_upgrade.ps1` does not exist.

- [ ] **Step 3: Implement the isolated smoke test**

The script must resolve and validate its caller-provided root, compile with `Uninstallable=no` through `/DSmokeTestRoot=...`, install silently into an empty directory, assert `InfiniteCanvas.exe` exists, seed `_internal\websockets\legacy-speedups.cp310-win_amd64.pyd` plus `_internal\websockets-16.1.1.dist-info\legacy.txt`, reinstall the same package, and assert both sentinel residues are gone. It must use only `Remove-Item -LiteralPath` after verifying each resolved path starts with the smoke root.

- [ ] **Step 4: Run unit tests and the real smoke test**

Run:

```powershell
E:\codex\构建工具\InfiniteCanvas-打包环境\Scripts\python.exe -m unittest tests.test_installer_definition -v
powershell -ExecutionPolicy Bypass -File build\windows\test_installer_upgrade.ps1 -SourceDir dist\InfiniteCanvas -TestRoot E:\codex\临时构建\InfiniteCanvas-2026.08.05-安装测试
```

Expected: the script reports successful clean install and clean upgrade, and exits `0`.

- [ ] **Step 5: Commit smoke coverage**

```powershell
git add build/windows/test_installer_upgrade.ps1 tests/test_installer_definition.py
git commit -m "test: cover clean install and runtime upgrade"
```

### Task 3: Build, Validate, and Publish 2026.08.05

**Files:**
- Modify: `VERSION`
- Create: `E:\codex\发布安装包\InfiniteCanvas\2026.08.05\InfiniteCanvas-Setup-2026.08.05.exe`
- Create: `E:\codex\发布安装包\InfiniteCanvas\2026.08.05\SHA256SUMS.txt`
- Create: `E:\codex\发布安装包\InfiniteCanvas\2026.08.05\release-manifest.json`

**Interfaces:**
- Consumes: the packaging environment at `E:\codex\构建工具\InfiniteCanvas-打包环境\Scripts\python.exe` and Inno Setup 6.
- Produces: complete install/upgrade artifacts, Git tag `v2026.08.05`, and the matching GitHub release source state.

- [ ] **Step 1: Update and verify the release version**

Change `VERSION` to:

```text
2026.08.05
```

Run the complete unit suite and expect all tests to pass.

- [ ] **Step 2: Build the full desktop distribution and installer**

Run:

```powershell
$env:INFINITE_CANVAS_PYTHON='E:\codex\构建工具\InfiniteCanvas-打包环境\Scripts\python.exe'
$env:INNO_SETUP_ISCC='C:\Users\xzh45\AppData\Local\Programs\Inno Setup 6\ISCC.exe'
powershell -ExecutionPolicy Bypass -File build\windows\build_release.ps1
```

Expected: `dist\InfiniteCanvas`, `dist\installer\InfiniteCanvas-Setup-2026.08.05.exe`, `SHA256SUMS.txt`, and `dist\release-manifest.json` exist.

- [ ] **Step 3: Run isolated install and dirty-upgrade smoke tests**

Run the Task 2 smoke script against the newly built `dist\InfiniteCanvas`. Confirm the seeded Python 3.10 `websockets` residue is absent after the second installation.

- [ ] **Step 4: Perform real GUI acceptance**

Record a hash of `%LOCALAPPDATA%\InfiniteCanvas\app_settings.json` when present, install over `E:\app\InfiniteCanvas`, launch the desktop executable, and verify the PyWebView settings center opens without a browser or CMD window. Close it, confirm no `InfiniteCanvas` process remains, confirm the old `speedups.cp310-win_amd64.pyd` and `websockets-16.1.1.dist-info` residue is gone, and confirm the user-data hash is unchanged.

- [ ] **Step 5: Assemble and verify release files**

Copy only the installer, checksum file, and release manifest to `E:\codex\发布安装包\InfiniteCanvas\2026.08.05`. Recompute SHA-256 and require it to match `SHA256SUMS.txt` before release.

- [ ] **Step 6: Commit, tag, and publish**

```powershell
git add VERSION
git commit -m "chore: release InfiniteCanvas 2026.08.05"
git push origin main
git tag -a v2026.08.05 -m "InfiniteCanvas Desktop 2026.08.05"
git push origin v2026.08.05
```

Expected: `origin/main` contains the installer fix and GitHub lists tag `v2026.08.05`.
