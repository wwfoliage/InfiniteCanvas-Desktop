# InfiniteCanvas Windows Desktop Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a clean Windows installer that opens InfiniteCanvas in a native PyWebView window without an external browser or console and preserves user data across manual upgrades.

**Architecture:** Separate immutable bundled resources from writable `%LOCALAPPDATA%\InfiniteCanvas` data through one path module. Run the existing FastAPI app in an in-process Uvicorn thread, display it through PyWebView/WebView2, and package the result with PyInstaller `onedir` plus Inno Setup. A whitelist-based release builder and secret scanner prevent local credentials and personal content from entering the installer or public repository.

**Tech Stack:** Python 3.10.11, FastAPI, Uvicorn, PyWebView 5.x, PyInstaller 6.x, Inno Setup 6, PowerShell, `unittest`.

## Global Constraints

- Target Windows 10/11 64-bit only.
- The production application must not open Chrome/Edge or display a CMD console.
- The local HTTP server must bind only to `127.0.0.1` and use a dynamically assigned port.
- Writable state must live below `%LOCALAPPDATA%\InfiniteCanvas`; program files are read-only.
- Install, upgrade, and default uninstall behavior must preserve user data.
- The release must exclude all `.env` files, secrets, current canvases, assets, outputs, history, logs, caches, and machine-specific shortcuts.
- External Codex, Antigravity, and Dreamina CLI installations/login state are not bundled.
- The version in `VERSION`, executable metadata, installer metadata, and installer filename must match.
- The derivative repository remains public, preserves `LICENSE`, and credits the upstream project.

---

## File Map

- `app_paths.py`: Resolve resource and writable data locations and create runtime directories.
- `desktop_app.py`: Own Uvicorn lifecycle, desktop window lifecycle, logging, and fatal startup reporting.
- `main.py`: Consume `AppPaths` instead of deriving writable paths from `__file__`; retain the existing FastAPI application.
- `requirements-desktop.txt`: Desktop-only build/runtime dependencies.
- `tests/test_app_paths.py`: Resource/data separation and first-run directory tests.
- `tests/test_desktop_app.py`: Port selection and server/window lifecycle tests using mocks.
- `build/windows/InfiniteCanvas.spec`: PyInstaller `onedir` definition and resource whitelist.
- `build/windows/InfiniteCanvas.iss`: Inno Setup installer and upgrade behavior.
- `build/windows/build_release.ps1`: Reproducible clean build orchestration.
- `build/windows/verify_release.py`: Artifact inventory, sensitive-data scan, version checks, and SHA256 output.
- `docs/windows-desktop-build.md`: Developer build and manual release instructions.
- `README.md`: Upstream credit, desktop build link, local data location, and upgrade notes.

---

### Task 1: Resource and User Data Path Boundary

**Files:**
- Create: `app_paths.py`
- Create: `tests/test_app_paths.py`

**Interfaces:**
- Produces: `AppPaths(resource_dir: Path, data_dir: Path)` with properties for every resource and writable location used by `main.py`.
- Produces: `resolve_app_paths(resource_dir: Path | None = None, data_dir: Path | None = None, frozen: bool | None = None) -> AppPaths`.
- Produces: `ensure_user_directories(paths: AppPaths) -> None`.

- [ ] **Step 1: Write failing development and packaged-mode path tests**

```python
def test_development_mode_keeps_data_below_resource_dir(tmp_path):
    paths = resolve_app_paths(resource_dir=tmp_path, frozen=False)
    assert paths.resource_dir == tmp_path
    assert paths.data_dir == tmp_path
    assert paths.static_dir == tmp_path / "static"
    assert paths.canvas_dir == tmp_path / "data" / "canvases"


def test_packaged_mode_uses_local_app_data(tmp_path, monkeypatch):
    local = tmp_path / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    paths = resolve_app_paths(resource_dir=tmp_path / "bundle", frozen=True)
    assert paths.resource_dir == tmp_path / "bundle"
    assert paths.data_dir == local / "InfiniteCanvas"
    assert paths.api_env_file == local / "InfiniteCanvas" / "API" / ".env"
    assert paths.assets_dir == local / "InfiniteCanvas" / "assets"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `.\python\python.exe -m unittest tests.test_app_paths -v`

Expected: `ModuleNotFoundError: No module named 'app_paths'`.

- [ ] **Step 3: Implement `AppPaths` and directory creation**

```python
@dataclass(frozen=True)
class AppPaths:
    resource_dir: Path
    data_dir: Path

    @property
    def static_dir(self) -> Path:
        return self.resource_dir / "static"

    @property
    def workflow_dir(self) -> Path:
        return self.resource_dir / "workflows"

    @property
    def api_env_file(self) -> Path:
        return self.data_dir / "API" / ".env"

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def output_dir(self) -> Path:
        return self.data_dir / "output"

    @property
    def canvas_dir(self) -> Path:
        return self.data_dir / "data" / "canvases"
```

Implement the remaining current globals (`history_file`, `conversation_dir`, `media_preview_dir`, settings files, `global_config_file`, and asset subdirectories) as properties with the same names in snake case. `INFINITE_CANVAS_DATA_DIR` overrides the packaged data root for tests and portable diagnostics.

- [ ] **Step 4: Cover first-run creation and missing `LOCALAPPDATA` fallback**

```python
def test_ensure_user_directories_creates_runtime_tree(tmp_path):
    paths = resolve_app_paths(resource_dir=tmp_path / "bundle", data_dir=tmp_path / "user", frozen=True)
    ensure_user_directories(paths)
    assert paths.canvas_dir.is_dir()
    assert paths.api_env_file.parent.is_dir()
    assert paths.assets_dir.joinpath("input").is_dir()
    assert paths.assets_dir.joinpath("output").is_dir()
    assert paths.logs_dir.is_dir()
```

- [ ] **Step 5: Run path tests**

Run: `.\python\python.exe -m unittest tests.test_app_paths -v`

Expected: all tests pass.

- [ ] **Step 6: Commit the isolated path module**

```powershell
git add app_paths.py tests/test_app_paths.py
git commit -m "feat: separate bundled resources from user data"
```

---

### Task 2: Migrate FastAPI Runtime Paths

**Files:**
- Modify: `main.py:223-311`
- Modify: `main.py:1566-1579`
- Modify: existing tests that patch path globals only where required
- Create: `tests/test_packaged_runtime_paths.py`

**Interfaces:**
- Consumes: `APP_PATHS = resolve_app_paths()` and `ensure_user_directories(APP_PATHS)` from Task 1.
- Produces: Existing `main.py` global path names as strings for backward compatibility with current functions and tests.

- [ ] **Step 1: Write a failing import-time packaged-path test**

```python
def test_main_uses_user_data_root_in_packaged_mode(tmp_path):
    env = os.environ.copy()
    env["INFINITE_CANVAS_DATA_DIR"] = str(tmp_path / "user")
    result = subprocess.run(
        [sys.executable, "-c", "import main; print(main.DATA_DIR); print(main.STATIC_DIR)"],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    lines = result.stdout.strip().splitlines()
    assert str(tmp_path / "user" / "data") in lines
    assert str(PROJECT_ROOT / "static") in lines
```

- [ ] **Step 2: Run the focused test and verify the current path assertion fails**

Run: `.\python\python.exe -m unittest tests.test_packaged_runtime_paths -v`

Expected: the data path still points at `E:\InfiniteCanvas\data`.

- [ ] **Step 3: Replace the writable path constant block with `APP_PATHS` mappings**

```python
from app_paths import ensure_user_directories, resolve_app_paths

APP_PATHS = resolve_app_paths()
ensure_user_directories(APP_PATHS)
BASE_DIR = str(APP_PATHS.resource_dir)
STATIC_DIR = str(APP_PATHS.static_dir)
WORKFLOW_DIR = str(APP_PATHS.workflow_dir)
OUTPUT_DIR = str(APP_PATHS.output_dir)
ASSETS_DIR = str(APP_PATHS.assets_dir)
HISTORY_FILE = str(APP_PATHS.history_file)
API_ENV_FILE = str(APP_PATHS.api_env_file)
DATA_DIR = str(APP_PATHS.runtime_data_dir)
GLOBAL_CONFIG_FILE = str(APP_PATHS.global_config_file)
```

Map all derived globals to `APP_PATHS` and retain their current variable names so the rest of the large module and existing tests remain stable. Keep `VERSION`, `static`, `workflows`, `CLI`, and `tools` under the resource directory.

- [ ] **Step 4: Make the `/assets` and `/output` mounts use the writable directories**

Keep the public URL contracts unchanged:

```python
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
```

- [ ] **Step 5: Run path and existing regression tests**

Run: `.\python\python.exe -m unittest discover -s tests -p "test_*.py" -v`

Expected: all tests pass without writing personal data into the repository during the packaged-path test.

- [ ] **Step 6: Commit the runtime migration**

```powershell
git add main.py app_paths.py tests
git commit -m "refactor: store desktop data in LocalAppData"
```

---

### Task 3: Native Desktop Lifecycle

**Files:**
- Create: `desktop_app.py`
- Create: `tests/test_desktop_app.py`
- Create: `requirements-desktop.txt`

**Interfaces:**
- Produces: `reserve_loopback_port() -> int`.
- Produces: `UvicornRuntime(app, host="127.0.0.1", port=None)` with `start(timeout: float = 15.0) -> str` and `stop(timeout: float = 5.0) -> None`.
- Produces: `run_desktop() -> int`, the PyInstaller GUI entry point.

- [ ] **Step 1: Write failing port and lifecycle tests**

```python
def test_reserved_port_is_loopback_connectable():
    port = reserve_loopback_port()
    assert 0 < port < 65536


@patch("desktop_app.uvicorn.Server")
def test_runtime_stops_server(mock_server):
    server = mock_server.return_value
    server.started = True
    runtime = UvicornRuntime(object(), port=32123)
    runtime.start()
    runtime.stop()
    assert server.should_exit is True
```

- [ ] **Step 2: Run the test and verify the missing module failure**

Run: `.\python\python.exe -m unittest tests.test_desktop_app -v`

Expected: `ModuleNotFoundError: No module named 'desktop_app'`.

- [ ] **Step 3: Implement loopback-only Uvicorn lifecycle**

Use `uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None, ws_ping_interval=None, ws_ping_timeout=None)` and a non-daemon `threading.Thread`. Poll `server.started` until the timeout, and on failure set `should_exit`, join the thread, and raise `RuntimeError`.

- [ ] **Step 4: Implement lazy PyWebView startup and clean shutdown**

```python
def run_desktop() -> int:
    import webview
    from main import app

    configure_logging(resolve_app_paths().logs_dir)
    runtime = UvicornRuntime(app)
    url = runtime.start()
    try:
        window = webview.create_window(
            "InfiniteCanvas",
            url,
            width=1440,
            height=900,
            min_size=(1024, 700),
        )
        webview.start(gui="edgechromium", debug=False, private_mode=False)
        return 0
    finally:
        runtime.stop()
```

Wrap `run_desktop()` in `main()` that catches fatal startup errors, writes the traceback to `%LOCALAPPDATA%\InfiniteCanvas\logs\desktop.log`, and uses `ctypes.windll.user32.MessageBoxW` for a short user-facing error. Never include secret values in log messages.

- [ ] **Step 5: Add pinned desktop dependency ranges**

```text
pywebview>=5.4,<6
pyinstaller>=6.12,<7
```

- [ ] **Step 6: Test window calls and shutdown ordering with mocked `webview`**

Assert the URL starts with `http://127.0.0.1:`, `gui="edgechromium"`, `debug=False`, and `runtime.stop()` runs when `webview.start()` returns or raises.

- [ ] **Step 7: Run desktop and full regression tests**

Run: `.\python\python.exe -m unittest tests.test_desktop_app -v`

Run: `.\python\python.exe -m unittest discover -s tests -p "test_*.py" -v`

Expected: all tests pass.

- [ ] **Step 8: Commit the desktop entry point**

```powershell
git add desktop_app.py requirements-desktop.txt tests/test_desktop_app.py
git commit -m "feat: add native Windows desktop shell"
```

---

### Task 4: PyInstaller Clean Build

**Files:**
- Create: `build/windows/InfiniteCanvas.spec`
- Create: `build/windows/build_release.ps1`
- Create: `build/windows/make_icon.py`
- Create: `build/windows/verify_release.py`
- Create: `tests/test_release_verifier.py`

**Interfaces:**
- Consumes: `desktop_app.py`, resource whitelist, and `VERSION`.
- Produces: `dist/InfiniteCanvas/InfiniteCanvas.exe` and `dist/release-manifest.json`.
- Produces: `verify_release.scan_tree(root: Path, forbidden_values: Iterable[str]) -> list[str]`.

- [ ] **Step 1: Write failing secret and personal-file scanner tests**

```python
def test_scan_tree_rejects_env_and_personal_runtime_files(tmp_path):
    (tmp_path / "API").mkdir()
    (tmp_path / "API" / ".env").write_text("KEY=secret", encoding="utf-8")
    (tmp_path / "history.json").write_text("[]", encoding="utf-8")
    findings = scan_tree(tmp_path, ["secret"])
    assert any(".env" in item for item in findings)
    assert any("history.json" in item for item in findings)
    assert any("known secret value" in item for item in findings)
```

- [ ] **Step 2: Run the scanner test and verify it fails**

Run: `.\python\python.exe -m unittest tests.test_release_verifier -v`

Expected: import failure for `build.windows.verify_release`.

- [ ] **Step 3: Implement the whitelist PyInstaller spec**

Include only:

```python
datas = [
    ("static", "static"),
    ("workflows", "workflows"),
    ("CLI", "CLI"),
    ("tools", "tools"),
    ("VERSION", "."),
    ("LICENSE", "."),
]
```

Build `desktop_app.py` as `InfiniteCanvas`, set `console=False`, set the generated ICO, collect PyWebView hidden imports, and do not include repository `data`, `API`, `assets`, `output`, or `history.json`.

- [ ] **Step 4: Implement icon generation from the existing logo**

Use Pillow to read `static/images/logo.png`, composite transparency correctly, and save `build/windows/InfiniteCanvas.ico` with 16, 32, 48, 64, 128, and 256 pixel sizes.

- [ ] **Step 5: Implement clean build orchestration**

`build_release.ps1` must:

1. Resolve the repository root from the script location.
2. Read and validate `VERSION` against `^[0-9]+\.[0-9]+\.[0-9]+$`.
3. Install `requirements.txt` and `requirements-desktop.txt` into the embedded Python only when `-InstallDependencies` is passed.
4. Remove only the explicit `build/pyinstaller` and `dist/InfiniteCanvas` build outputs after resolving and checking they remain inside the repository.
5. Generate the ICO, run all tests, invoke PyInstaller with `--distpath dist` and `--workpath build/pyinstaller`, and run `verify_release.py`.
6. Exit nonzero on any failed command.

- [ ] **Step 6: Implement release verification**

The verifier must reject forbidden paths and extensions, scan text/JSON files for key-like fields with non-empty values, compare against non-empty values read from the development `API/.env` without printing those values, verify executable/resource presence, and write a JSON manifest containing relative path, size, SHA256, and version.

- [ ] **Step 7: Run unit tests and build the `onedir` application**

Run: `powershell -ExecutionPolicy Bypass -File build\windows\build_release.ps1 -InstallDependencies -SkipInstaller`

Expected: `dist\InfiniteCanvas\InfiniteCanvas.exe` exists, the scanner reports zero findings, and no `.env`, personal data, or history file exists below `dist\InfiniteCanvas`.

- [ ] **Step 8: Launch and visually verify the packaged desktop app**

Start `dist\InfiniteCanvas\InfiniteCanvas.exe`, verify no external browser or CMD appears, exercise the home page and canvas, close the window, then confirm no `InfiniteCanvas.exe` process remains. Verify `%LOCALAPPDATA%\InfiniteCanvas` contains newly created runtime directories.

- [ ] **Step 9: Commit the PyInstaller build**

```powershell
git add build/windows tests/test_release_verifier.py
git commit -m "build: add clean PyInstaller desktop build"
```

---

### Task 5: Inno Setup Installer and Manual Upgrade

**Files:**
- Create: `build/windows/InfiniteCanvas.iss`
- Modify: `build/windows/build_release.ps1`
- Create: `tests/test_installer_definition.py`

**Interfaces:**
- Consumes: `dist/InfiniteCanvas` and `VERSION`.
- Produces: `dist/installer/InfiniteCanvas-Setup-<VERSION>.exe`.

- [ ] **Step 1: Write a failing installer policy test**

```python
def test_installer_preserves_local_app_data():
    script = INSTALLER_SCRIPT.read_text(encoding="utf-8-sig")
    assert "AppId={{" in script
    assert "PrivilegesRequired=lowest" in script
    assert "%LOCALAPPDATA%" not in script
    assert "uninsdelete" not in script.lower()
    assert "OutputBaseFilename=InfiniteCanvas-Setup-{#AppVersion}" in script
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `.\python\python.exe -m unittest tests.test_installer_definition -v`

Expected: installer script is missing.

- [ ] **Step 3: Implement the installer**

Use a stable GUID in `AppId`, `DefaultDirName={localappdata}\Programs\InfiniteCanvas`, `PrivilegesRequired=lowest`, `ArchitecturesAllowed=x64compatible`, and `ArchitecturesInstallIn64BitMode=x64compatible`. Install the entire `dist\InfiniteCanvas` directory, create Start Menu and optional desktop shortcuts, and do not add delete rules for `%LOCALAPPDATA%\InfiniteCanvas`.

- [ ] **Step 4: Add WebView2 detection**

At installer completion, detect the Edge WebView2 Runtime registry keys. If absent, show a Chinese message that includes the official runtime download URL. Do not silently download or execute another installer in the first release.

- [ ] **Step 5: Add Inno Setup invocation and artifact verification**

Resolve `ISCC.exe` from `PATH` or the standard Inno Setup 6 install location. Fail with a clear installation command when missing. Pass `/DAppVersion=<VERSION>` and `/DSourceDir=<absolute dist directory>` and rerun the verifier against the produced installer.

- [ ] **Step 6: Build and test install/upgrade/uninstall**

Run: `powershell -ExecutionPolicy Bypass -File build\windows\build_release.ps1`

Install version A, create a test canvas, install version B with a higher temporary version, and verify the canvas remains. Uninstall and verify program files are removed while `%LOCALAPPDATA%\InfiniteCanvas` remains.

- [ ] **Step 7: Generate final hash**

Run: `Get-FileHash dist\installer\InfiniteCanvas-Setup-*.exe -Algorithm SHA256`

Record the hash in `dist\installer\SHA256SUMS.txt` and rerun `verify_release.py`.

- [ ] **Step 8: Commit the installer**

```powershell
git add build/windows/InfiniteCanvas.iss build/windows/build_release.ps1 tests/test_installer_definition.py
git commit -m "build: add Windows installer and upgrade path"
```

---

### Task 6: Documentation, Public Repository, and Release

**Files:**
- Modify: `README.md`
- Create: `docs/windows-desktop-build.md`
- Create in clean publishing checkout: `.gitignore`

**Interfaces:**
- Consumes: verified clean source, installer, manifest, SHA256, and upstream attribution.
- Produces: public `wwfoliage/InfiniteCanvas-Desktop` source and a tagged GitHub Release.

- [ ] **Step 1: Document user-visible desktop behavior**

Add concise sections covering:

- Desktop launch with no browser/CMD.
- `%LOCALAPPDATA%\InfiniteCanvas` data location.
- Manual update by installing a higher version over the existing version.
- External CLI prerequisites.
- Upstream source link, original author credit, license restrictions, and non-commercial-use notice.

- [ ] **Step 2: Document the reproducible build**

Include exact prerequisites and commands:

```powershell
.\python\python.exe -m pip install -r requirements.txt -r requirements-desktop.txt
powershell -ExecutionPolicy Bypass -File build\windows\build_release.ps1
```

Explain test, scan, PyInstaller, Inno Setup, artifact, and version-bump steps.

- [ ] **Step 3: Run final repository and artifact checks**

Run the full test suite, `git diff --check`, the clean release verifier, and a recursive check that no tracked path matches `.env`, personal runtime directories, `*.pyc`, or generated installer contents.

- [ ] **Step 4: Create a clean publishing checkout**

Clone `https://github.com/wwfoliage/InfiniteCanvas-Desktop.git` into a new verified workspace directory. Copy only Git-tracked source plus the reviewed desktop packaging files. Preserve `LICENSE`; add `.gitignore` rules for secrets, runtime data, caches, `build/pyinstaller`, and `dist`.

- [ ] **Step 5: Configure repository provenance**

Set `origin` to `https://github.com/wwfoliage/InfiniteCanvas-Desktop.git` and add `upstream` as `https://github.com/hero8152/Infinite-Canvas.git`. Verify both with `git remote -v` without changing the original dirty working tree.

- [ ] **Step 6: Commit and push clean source**

```powershell
git add .
git commit -m "feat: publish InfiniteCanvas Windows desktop edition"
git push -u origin main
```

Before pushing, verify `git status --short`, `git ls-files`, and the secret scan output. The push must contain source and build definitions, not local user data or generated build directories.

- [ ] **Step 7: Publish the manual-update release**

Create tag `v<VERSION>` and a GitHub Release containing:

- `InfiniteCanvas-Setup-<VERSION>.exe`
- `SHA256SUMS.txt`
- Release notes listing fixes/features, supported Windows versions, WebView2 requirement, external CLI requirements, manual update steps, and the data-preservation guarantee.

- [ ] **Step 8: Verify the public result**

Confirm the repository is public, the default branch contains `LICENSE` and attribution, the release tag matches `VERSION`, both release assets download, and the downloaded installer hash matches `SHA256SUMS.txt`.

- [ ] **Step 9: Commit documentation changes in the source repository**

```powershell
git add README.md docs/windows-desktop-build.md
git commit -m "docs: explain desktop builds and manual updates"
```

---

## Final Verification Checklist

- [ ] Full Python test suite passes.
- [ ] Packaged application opens only a native PyWebView window.
- [ ] No CMD or external browser appears.
- [ ] Server listens only on a dynamic `127.0.0.1` port.
- [ ] Closing the window ends the server process.
- [ ] Fresh install creates `%LOCALAPPDATA%\InfiniteCanvas` state.
- [ ] Manual upgrade preserves settings, canvases, assets, output, and history.
- [ ] Default uninstall preserves user data.
- [ ] Installer expansion and public repository contain no secrets or personal runtime data.
- [ ] Installer version and tag match `VERSION`.
- [ ] SHA256 matches the uploaded installer.
- [ ] Public repository preserves license and upstream attribution.
