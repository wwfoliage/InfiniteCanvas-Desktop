# InfiniteCanvas Settings Center and Download Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore reliable downloads in the packaged Windows app and replace the scattered sidebar controls with a persistent seven-section settings center.

**Architecture:** Add two focused Python modules: `app_settings.py` owns versioned non-secret preferences, and `download_manager.py` owns destination validation, classification, collision-safe atomic writes, storage reporting, and restricted cache cleanup. FastAPI routes in `main.py` expose those capabilities to one shared browser-side `StudioDownloads` module and the settings page; a minimal PyWebView bridge handles native folder selection and whitelisted folder opening. Existing API and ComfyUI settings pages remain the owners of their current data and run in an embedded mode inside the new settings center.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, urllib streaming, PyWebView 5.4 EdgeChromium, vanilla HTML/CSS/JavaScript, unittest, PyInstaller 6, Inno Setup 6.

## Global Constraints

- The desktop window stays at a minimum size of `1024 x 700`, opens no browser tab, and uses a windowed PyInstaller executable with no CMD console.
- Default download root is the current Windows user's `Downloads\InfiniteCanvas` directory.
- Downloads save directly without a Save As dialog, never overwrite, and use `name (1).ext`, `name (2).ext` collision suffixes.
- Download categories are exactly `图片`, `视频`, `音频`, `工作流`, `画布导出`, and `其他`; classification is enabled by default.
- General settings persist in `%LOCALAPPDATA%\InfiniteCanvas\data\app_settings.json`; API keys stay in the existing protected API configuration.
- Cache cleanup may remove only `media_previews` and the download manager's dedicated temporary directory and registry files.
- Theme modes are `system`, `light`, and `dark`; scale modes are `auto`, `80`, `90`, `100`, `110`, and `125`.
- Update checks and installation remain manual.
- Browser development mode must retain a standard browser-download fallback when the desktop save API is unavailable.
- Existing canvas, project, asset, workflow, conversation, prompt, API, log, and WebView profile formats are unchanged.

---

## File Structure

- Create `app_settings.py`: settings schema, normalization, migration input, atomic JSON persistence, and resolved default download path.
- Create `download_manager.py`: filename sanitization, category inference, collision-safe atomic saves, URL source validation/streaming, storage statistics, and restricted cache cleanup.
- Create `static/js/downloads.js`: shared `StudioDownloads.saveUrl` and `StudioDownloads.saveBlob` API, browser fallback, result notification, and native open-folder request.
- Create `static/settings.html`: the seven-section settings center and embedded API/workflow frames.
- Create `static/css/settings.css`: fixed secondary navigation, responsive settings content, theme variants, and stable controls.
- Create `static/js/settings.js`: settings loading/saving, desktop bridge messaging, storage/cache actions, update actions, embedded frame synchronization, and i18n.
- Modify `app_paths.py`: add paths for general settings and download temporary files.
- Modify `main.py`: add narrow settings/download/storage endpoints and serve the new page.
- Modify `desktop_app.py`: enable PyWebView download fallback and expose the minimal `DesktopApi` bridge.
- Modify `static/index.html`: replace the old settings controls with one settings entry and one settings frame.
- Modify `static/js/theme.js` and `static/js/i18n-core.js`: support system theme, scale propagation, and cross-frame settings messages.
- Modify `static/api-settings.html`, `static/comfyui-settings.html`, and their CSS: support `?embedded=1` without changing business logic.
- Modify all product download call sites listed in Task 5 to call `StudioDownloads`.
- Create focused Python and static-contract tests under `tests/`.
- Modify Windows packaging verification only if a test proves a new runtime file is not collected; the existing `static` directory collection should include all new front-end files automatically.

---

### Task 1: Versioned Application Settings

**Files:**
- Create: `app_settings.py`
- Modify: `app_paths.py`
- Test: `tests/test_app_settings.py`
- Test: `tests/test_app_paths.py`

**Interfaces:**
- Produces: `DEFAULT_SETTINGS: dict[str, Any]`.
- Produces: `default_download_directory() -> Path`.
- Produces: `normalize_settings(raw: Mapping[str, Any] | None, legacy: Mapping[str, str] | None = None) -> dict[str, Any]`.
- Produces: `settings_for_client(settings: Mapping[str, Any]) -> dict[str, Any]`, adding `downloads.resolved_directory` without mutating persisted data.
- Produces: `AppSettingsStore(path: Path).load(legacy=None) -> dict[str, Any]` and `.update(patch: Mapping[str, Any]) -> dict[str, Any]`.
- Produces: `AppPaths.app_settings_file` and `AppPaths.download_temp_dir`.

- [ ] **Step 1: Write failing path and settings tests**

```python
def test_packaged_paths_include_settings_and_download_temp(self):
    paths = resolve_app_paths(resource_dir="C:/bundle", data_dir="C:/user", frozen=True)
    self.assertEqual(paths.app_settings_file, Path("C:/user/data/app_settings.json"))
    self.assertEqual(paths.download_temp_dir, Path("C:/user/data/download_temp"))

def test_settings_normalize_invalid_values_and_legacy_preferences(self):
    result = normalize_settings({}, {
        "studio_theme": "dark",
        "studio_ui_scale_mode": "110",
        "studio_lang": "en",
    })
    self.assertEqual(result["appearance"], {"theme": "dark", "scale": "110"})
    self.assertEqual(result["language"], "en")
    invalid = normalize_settings({"appearance": {"theme": "purple", "scale": "500"}})
    self.assertEqual(invalid["appearance"], {"theme": "system", "scale": "auto"})

def test_settings_store_updates_whitelisted_fields_atomically(self):
    store = AppSettingsStore(Path(temp_dir) / "app_settings.json")
    saved = store.update({"downloads": {"categorize": False}, "api_key": "must-not-save"})
    self.assertFalse(saved["downloads"]["categorize"])
    self.assertNotIn("api_key", json.loads(store.path.read_text(encoding="utf-8")))
    self.assertEqual(list(store.path.parent.glob("*.tmp")), [])
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m unittest tests.test_app_paths tests.test_app_settings -v`

Expected: FAIL because the new paths and `app_settings` module do not exist.

- [ ] **Step 3: Implement settings normalization and atomic persistence**

```python
DEFAULT_SETTINGS = {
    "schema_version": 1,
    "downloads": {"directory": "", "categorize": True, "notify": True},
    "appearance": {"theme": "system", "scale": "auto"},
    "language": "zh",
}
THEMES = {"system", "light", "dark"}
SCALES = {"auto", "80", "90", "100", "110", "125"}

def default_download_directory() -> Path:
    return Path.home() / "Downloads" / "InfiniteCanvas"

class AppSettingsStore:
    def update(self, patch: Mapping[str, Any]) -> dict[str, Any]:
        current = self.load()
        merged = _merge_known_fields(current, patch)
        normalized = normalize_settings(merged)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
        return normalized
```

Add the two `AppPaths` properties and include `download_temp_dir` in `ensure_user_directories`.

- [ ] **Step 4: Run settings tests and the existing path suite**

Run: `python -m unittest tests.test_app_settings tests.test_app_paths -v`

Expected: PASS; the settings JSON contains no unknown or secret fields and no temporary file remains.

- [ ] **Step 5: Commit the settings storage unit**

```powershell
git add app_paths.py app_settings.py tests/test_app_paths.py tests/test_app_settings.py
git commit -m "feat: add persistent desktop settings"
```

---

### Task 2: Safe Native Download and Cache Core

**Files:**
- Create: `download_manager.py`
- Test: `tests/test_download_manager.py`

**Interfaces:**
- Consumes: `AppSettingsStore.load()` and `AppPaths` resource roots.
- Produces: `DownloadRequest(filename: str, category: str = "", content_type: str = "")`.
- Produces: `DownloadResult(ok: bool, filename: str, category: str, path: str, error_code: str = "")`.
- Produces: `sanitize_filename(name: str, fallback: str = "download") -> str`.
- Produces: `classify_download(filename: str, content_type: str = "", requested: str = "") -> str`.
- Produces: `DownloadManager.save_stream(request, chunks) -> DownloadResult` and `.save_url(request, url) -> DownloadResult`.
- Produces: `storage_report(paths: AppPaths, settings: Mapping[str, Any]) -> dict[str, Any]`.
- Produces: `cache_cleanup_preview(paths: AppPaths) -> dict[str, Any]` and `clear_rebuildable_cache(paths: AppPaths) -> dict[str, Any]`.

- [ ] **Step 1: Write failing safety, classification, collision, and cleanup tests**

```python
def test_sanitize_filename_rejects_paths_reserved_names_and_trailing_dots(self):
    self.assertEqual(sanitize_filename(r"..\CON .png"), "_CON .png")
    self.assertNotIn("/", sanitize_filename("folder/name.png"))
    self.assertEqual(sanitize_filename("..."), "download")

def test_classification_uses_explicit_category_then_mime_and_extension(self):
    self.assertEqual(classify_download("x.bin", requested="工作流"), "工作流")
    self.assertEqual(classify_download("x", "video/mp4"), "视频")
    self.assertEqual(classify_download("canvas.json", requested="画布导出"), "画布导出")
    self.assertEqual(classify_download("notes.txt"), "其他")

def test_save_stream_never_overwrites_and_removes_failed_part(self):
    first = manager.save_stream(DownloadRequest("图像.png", "图片"), [b"one"])
    second = manager.save_stream(DownloadRequest("图像.png", "图片"), [b"two"])
    self.assertEqual(Path(first.path).name, "图像.png")
    self.assertEqual(Path(second.path).name, "图像 (1).png")
    self.assertEqual(Path(first.path).read_bytes(), b"one")
    with self.assertRaisesRegex(DownloadWriteError, "write failed"):
        manager.save_stream(DownloadRequest("bad.bin"), failing_chunks())
    self.assertEqual(list(download_temp.glob("*.part")), [])

def test_cache_cleanup_cannot_touch_user_data(self):
    before = hash_tree([paths.canvas_dir, paths.asset_library_dir, paths.api_env_file.parent])
    result = clear_rebuildable_cache(paths)
    self.assertTrue(result["ok"])
    self.assertFalse(any(paths.media_preview_dir.iterdir()))
    self.assertFalse(any(paths.download_temp_dir.iterdir()))
    self.assertEqual(hash_tree([...]), before)
```

- [ ] **Step 2: Run the download manager tests and verify they fail**

Run: `python -m unittest tests.test_download_manager -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'download_manager'`.

- [ ] **Step 3: Implement filename, category, atomic-write, URL, storage, and cleanup logic**

```python
CATEGORIES = {"图片", "视频", "音频", "工作流", "画布导出", "其他"}

def _unique_destination(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    stem, suffix = candidate.stem, candidate.suffix
    number = 1
    while candidate.exists():
        candidate = directory / f"{stem} ({number}){suffix}"
        number += 1
    return candidate

def save_stream(self, request: DownloadRequest, chunks: Iterable[bytes]) -> DownloadResult:
    destination_dir = self._destination_directory(request)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = _unique_destination(destination_dir, sanitize_filename(request.filename))
    part = self.paths.download_temp_dir / f"{uuid.uuid4().hex}.part"
    try:
        with part.open("xb") as handle:
            for chunk in chunks:
                if chunk:
                    handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(part, destination)
    except Exception as exc:
        part.unlink(missing_ok=True)
        raise DownloadWriteError("write failed") from exc
    return DownloadResult(True, destination.name, category, str(destination))
```

For `save_url`, accept only `http` and `https`; local application paths are resolved by a callback supplied from `main.py`, never from an arbitrary filesystem path. Use `urllib.request.urlopen(..., timeout=30)` and yield fixed-size chunks. Resolve every cleanup target and verify it is equal to an allowed root or a descendant before deleting children.

- [ ] **Step 4: Run the focused tests**

Run: `python -m unittest tests.test_download_manager -v`

Expected: PASS, including Unicode names, Windows reserved names, no-extension files, collision numbering, `.part` cleanup, and protected-data hashes.

- [ ] **Step 5: Commit the download core**

```powershell
git add download_manager.py tests/test_download_manager.py
git commit -m "feat: add safe native download manager"
```

---

### Task 3: FastAPI Settings, Download, Storage, and Cache Endpoints

**Files:**
- Modify: `main.py`
- Create: `tests/test_settings_download_api.py`

**Interfaces:**
- Consumes: `AppSettingsStore`, `DownloadManager`, storage and cleanup helpers.
- Produces: `GET /api/app-settings`.
- Produces: `PUT /api/app-settings` with a JSON partial settings object.
- Produces: `POST /api/downloads/url` with `{url, filename, category}`.
- Produces: `POST /api/downloads/blob` multipart fields `file`, `filename`, and `category`, with a 512 MiB request limit.
- Produces: `GET /api/storage-report`.
- Produces: `GET /api/cache-cleanup-preview` and `POST /api/cache-cleanup`.

- [ ] **Step 1: Write failing endpoint tests**

```python
def test_settings_api_returns_resolved_download_directory(client):
    payload = client.get("/api/app-settings").json()
    assert payload["downloads"]["resolved_directory"].endswith("InfiniteCanvas")
    updated = client.put("/api/app-settings", json={"appearance": {"theme": "dark"}})
    assert updated.status_code == 200
    assert updated.json()["appearance"]["theme"] == "dark"

def test_blob_download_returns_final_native_path(client, tmp_path):
    response = client.post(
        "/api/downloads/blob",
        data={"filename": "board.json", "category": "画布导出"},
        files={"file": ("blob", b"{}", "application/json")},
    )
    assert response.status_code == 200
    assert Path(response.json()["path"]).read_bytes() == b"{}"

def test_url_download_rejects_arbitrary_local_file(client):
    response = client.post("/api/downloads/url", json={
        "url": "file:///C:/Windows/win.ini", "filename": "win.ini", "category": "其他"
    })
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "unsupported_url"
```

- [ ] **Step 2: Run endpoint tests and verify they fail**

Run: `python -m unittest tests.test_settings_download_api -v`

Expected: FAIL with 404 responses for the new routes.

- [ ] **Step 3: Add narrow request models, module singletons, and routes**

```python
class DownloadUrlRequest(BaseModel):
    url: str
    filename: str
    category: str = ""

@app.get("/api/app-settings")
def get_app_settings():
    return settings_for_client(APP_SETTINGS.load())

@app.put("/api/app-settings")
def put_app_settings(payload: Dict[str, Any]):
    return settings_for_client(APP_SETTINGS.update(payload))

@app.post("/api/downloads/url")
def save_download_url(payload: DownloadUrlRequest):
    return DOWNLOAD_MANAGER.save_url(
        DownloadRequest(payload.filename, payload.category), payload.url
    ).as_dict()

@app.post("/api/downloads/blob")
def save_download_blob(file: UploadFile = File(...), filename: str = Form(...), category: str = Form("")):
    return DOWNLOAD_MANAGER.save_stream(
        DownloadRequest(filename, category, file.content_type or ""),
        iter_file_chunks(file.file, limit=512 * 1024 * 1024),
    ).as_dict()
```

Map known local URLs through the existing safe output/assets resolver. Return consistent `{detail: {code, message}}` errors for invalid category, invalid filename, unsupported URL, size limit, remote failure, and write failure. The storage and cleanup routes must call only the allowlisted helpers from Task 2.

- [ ] **Step 4: Run API and existing backend tests**

Run: `python -m unittest tests.test_settings_download_api tests.test_app_settings tests.test_download_manager tests.test_mediakit -v`

Expected: PASS; local registered URLs, remote-stream stubs, generated blobs, ZIP blobs, and error mapping behave deterministically.

- [ ] **Step 5: Commit the local service API**

```powershell
git add main.py tests/test_settings_download_api.py
git commit -m "feat: expose settings and native download APIs"
```

---

### Task 4: Minimal PyWebView Desktop Bridge

**Files:**
- Modify: `desktop_app.py`
- Modify: `tests/test_desktop_app.py`

**Interfaces:**
- Produces: `DesktopApi(paths: AppPaths, settings_store: AppSettingsStore, window_getter: Callable[[], Any])`.
- Produces: `DesktopApi.choose_download_directory() -> dict[str, Any]`.
- Produces: `DesktopApi.open_directory(kind: str) -> dict[str, Any]`, where `kind` is one of `downloads`, `data`, `cache`, or `logs`.
- Changes: `run_window(..., desktop_api: Any | None = None)` supplies `js_api` and enables `webview.settings["ALLOW_DOWNLOADS"] = True` as compatibility fallback.

- [ ] **Step 1: Extend desktop tests for dialog cancellation, persistence, whitelist, and fallback flag**

```python
def test_choose_download_directory_persists_selected_folder(self):
    window.create_file_dialog.return_value = ("C:/Chosen",)
    result = api.choose_download_directory()
    self.assertTrue(result["ok"])
    settings_store.update.assert_called_once_with({"downloads": {"directory": "C:/Chosen"}})

def test_open_directory_rejects_unknown_kind(self):
    self.assertEqual(api.open_directory("C:/Windows"), {
        "ok": False, "error_code": "directory_not_allowed"
    })

def test_window_enables_download_fallback_and_exposes_api(self):
    run_window(webview, runtime, url, storage_path, desktop_api)
    self.assertTrue(webview.settings["ALLOW_DOWNLOADS"])
    self.assertIs(webview.create_window.call_args.kwargs["js_api"], desktop_api)
```

- [ ] **Step 2: Run desktop tests and verify they fail**

Run: `python -m unittest tests.test_desktop_app -v`

Expected: FAIL because `DesktopApi`, `js_api`, and the download fallback setting are missing.

- [ ] **Step 3: Implement the bridge and wire it to the created window**

```python
class DesktopApi:
    ALLOWED_KINDS = {"downloads", "data", "cache", "logs"}

    def choose_download_directory(self) -> dict[str, Any]:
        selected = self.window_getter().create_file_dialog(FOLDER_DIALOG)
        if not selected:
            return {"ok": False, "cancelled": True}
        directory = Path(selected[0]).expanduser().resolve()
        if not directory.is_dir():
            return {"ok": False, "error_code": "invalid_directory"}
        settings = self.settings_store.update({"downloads": {"directory": str(directory)}})
        return {"ok": True, "directory": str(directory), "settings": settings_for_client(settings)}

def run_window(..., desktop_api=None):
    webview_module.settings["ALLOW_DOWNLOADS"] = True
    window = webview_module.create_window(..., js_api=desktop_api)
```

Use `os.startfile` only after resolving the directory selected by `kind`; do not expose an arbitrary path argument. Set the bridge's window getter after `create_window` so folder dialogs use the actual window instance.

- [ ] **Step 4: Run desktop tests**

Run: `python -m unittest tests.test_desktop_app -v`

Expected: PASS, and the pre-existing start/stop/error handling assertions still pass.

- [ ] **Step 5: Commit the native bridge**

```powershell
git add desktop_app.py tests/test_desktop_app.py
git commit -m "feat: add desktop settings bridge"
```

---

### Task 5: Shared Front-End Download Client and Call-Site Migration

**Files:**
- Create: `static/js/downloads.js`
- Modify: `static/index.html`
- Modify: `static/canvas.html`
- Modify: `static/smart-canvas.html`
- Modify: `static/canvas-list.html`
- Modify: `static/asset-manager.html`
- Modify: `static/angle.html`
- Modify: `static/enhance.html`
- Modify: `static/klein.html`
- Modify: `static/online.html`
- Modify: `static/zimage.html`
- Modify: `static/js/canvas.js`
- Modify: `static/js/smart-canvas.js`
- Modify: `static/js/canvas-list.js`
- Modify: `static/js/asset-manager.js`
- Modify: `static/js/ltx-director-timeline.js`
- Create: `tests/test_download_frontend_contract.py`

**Interfaces:**
- Produces: `window.StudioDownloads.saveUrl(url, filename, category) -> Promise<DownloadResult>`.
- Produces: `window.StudioDownloads.saveBlob(blob, filename, category) -> Promise<DownloadResult>`.
- Produces: `window.StudioDownloads.openFolder(kind = "downloads") -> Promise<object>`.
- Produces: a `studio-download-complete` event whose detail contains the real `filename`, `category`, and `path`.

- [ ] **Step 1: Write failing static contract tests for the shared module and every known call site**

```python
DOWNLOAD_SURFACES = [
    "static/js/canvas.js", "static/js/smart-canvas.js", "static/js/canvas-list.js",
    "static/js/asset-manager.js", "static/js/ltx-director-timeline.js",
    "static/angle.html", "static/enhance.html", "static/klein.html",
    "static/online.html", "static/zimage.html",
]

def test_download_module_exposes_url_blob_and_browser_fallback(self):
    source = read("static/js/downloads.js")
    for token in ("saveUrl", "saveBlob", "/api/downloads/url", "/api/downloads/blob", "studio-download-complete"):
        self.assertIn(token, source)

def test_product_downloads_use_shared_client(self):
    for path in DOWNLOAD_SURFACES:
        source = read(path)
        self.assertNotRegex(source, r"\.download\s*=|createElement\(['\"]a['\"]\)")
```

Exclude object URLs used only for previews/uploads from this assertion by narrowing checks to named download functions. Require each HTML surface to load `/static/js/downloads.js` before its product script.

- [ ] **Step 2: Run the front-end contract tests and verify they fail**

Run: `python -m unittest tests.test_download_frontend_contract -v`

Expected: FAIL because `downloads.js` is absent and direct anchor download paths remain.

- [ ] **Step 3: Implement the shared desktop-first client with browser fallback**

```javascript
(function(){
  async function saveUrl(url, filename, category='其他'){
    try {
      const response = await fetch('/api/downloads/url', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({url, filename, category})
      });
      if(response.status === 404) return browserUrl(url, filename);
      return finish(await parseResult(response));
    } catch(error) {
      if(location.hostname !== '127.0.0.1' && location.hostname !== 'localhost') return browserUrl(url, filename);
      throw error;
    }
  }

  async function saveBlob(blob, filename, category='其他'){
    const form = new FormData();
    form.append('file', blob, filename); form.append('filename', filename); form.append('category', category);
    const response = await fetch('/api/downloads/blob', {method:'POST', body:form});
    if(response.status === 404) return browserBlob(blob, filename);
    return finish(await parseResult(response));
  }

  window.StudioDownloads = {saveUrl, saveBlob, openFolder};
})();
```

`finish` dispatches the completion event only after a successful server response and shows the existing toast style with file name, saved path, and an open-folder action when notifications are enabled. The browser fallback alone may create a temporary anchor.

- [ ] **Step 4: Migrate each product download function to the shared API**

Use exact category mappings:

```javascript
StudioDownloads.saveUrl(mediaUrl, mediaFilename, mediaKind === 'video' ? '视频' : mediaKind === 'audio' ? '音频' : '图片');
StudioDownloads.saveBlob(jsonBlob, workflowFilename, '工作流');
StudioDownloads.saveBlob(canvasJsonBlob, canvasFilename, '画布导出');
StudioDownloads.saveBlob(zipBlob, archiveFilename, archiveContainsWorkflow ? '工作流' : '画布导出');
```

Replace direct downloads in `canvas.js`, `smart-canvas.js`, `canvas-list.js`, `asset-manager.js`, timeline frame export, and the five generator pages. Keep preview-only `URL.createObjectURL` calls unchanged. Preserve existing requested filenames.

- [ ] **Step 5: Run static contracts and download backend tests**

Run: `python -m unittest tests.test_download_frontend_contract tests.test_settings_download_api tests.test_download_manager -v`

Expected: PASS; all known product download functions route through `StudioDownloads`, while browser fallback remains present only in `downloads.js`.

- [ ] **Step 6: Commit the shared download client migration**

```powershell
git add static tests/test_download_frontend_contract.py
git commit -m "fix: route product downloads through desktop manager"
```

---

### Task 6: Seven-Section Settings Center and Single Sidebar Entry

**Files:**
- Create: `static/settings.html`
- Create: `static/css/settings.css`
- Create: `static/js/settings.js`
- Modify: `static/index.html`
- Modify: `static/api-settings.html`
- Modify: `static/comfyui-settings.html`
- Modify: `static/css/api-settings.css`
- Modify: `static/css/comfyui-settings.css`
- Modify: `tests/test_sidebar_footer_cleanup.py`
- Create: `tests/test_settings_center_structure.py`

**Interfaces:**
- Consumes: Task 3 API routes and `window.pywebview.api` through top-frame messages.
- Produces: one sidebar control calling `switchUI(this, 'settings')`.
- Produces: seven `[data-settings-section]` navigation buttons and seven matching `[data-settings-panel]` regions.
- Produces: embedded `/static/api-settings.html?embedded=1` and `/static/comfyui-settings.html?embedded=1` frames.
- Produces: same-origin messages `settings-native-request` and `settings-native-response` between settings iframe and top window.

- [ ] **Step 1: Replace old structure expectations with failing settings-center tests**

```python
def test_sidebar_has_one_settings_entry_and_no_legacy_controls(self):
    source = read("static/index.html")
    self.assertEqual(source.count("switchUI(this, 'settings')"), 1)
    for token in ("settings-fold-toggle", "theme-toggle-btn", "lang-toggle-btn", "switchUI(this, 'api-settings')", "switchUI(this, 'comfyui-settings')"):
        self.assertNotIn(token, source)

def test_settings_center_has_seven_fixed_sections(self):
    source = read("static/settings.html")
    expected = ["downloads", "appearance", "language", "api", "workflow", "storage", "about"]
    self.assertEqual(re.findall(r'data-settings-section="([^"]+)"', source), expected)
    self.assertEqual(sorted(re.findall(r'data-settings-panel="([^"]+)"', source)), sorted(expected))
```

- [ ] **Step 2: Run settings structure tests and verify they fail**

Run: `python -m unittest tests.test_sidebar_footer_cleanup tests.test_settings_center_structure -v`

Expected: FAIL because the old separate controls remain and `settings.html` does not exist.

- [ ] **Step 3: Build the fixed secondary navigation and complete controls**

```html
<main class="settings-shell">
  <nav class="settings-nav" aria-label="设置分类">
    <button data-settings-section="downloads"><i data-lucide="download"></i><span data-i18n="settings.downloads">下载设置</span></button>
    <button data-settings-section="appearance"><i data-lucide="palette"></i><span data-i18n="settings.appearance">界面设置</span></button>
    <button data-settings-section="language"><i data-lucide="languages"></i><span data-i18n="settings.language">语言设置</span></button>
    <button data-settings-section="api"><i data-lucide="key-round"></i><span>API 设置</span></button>
    <button data-settings-section="workflow"><i data-lucide="workflow"></i><span data-i18n="settings.workflow">工作流设置</span></button>
    <button data-settings-section="storage"><i data-lucide="hard-drive"></i><span data-i18n="settings.storage">存储与缓存</span></button>
    <button data-settings-section="about"><i data-lucide="info"></i><span data-i18n="settings.about">关于与更新</span></button>
  </nav>
  <div class="settings-divider"></div>
  <section class="settings-content"><!-- seven unframed panels --></section>
</main>
```

Implement directory value/change/reset, categorize and notify toggles, three theme choices, six scale choices, two languages, embedded frames, storage rows/open buttons, cache preview/confirmation/clear, current version/update notes/check button/connectivity/log button. Remember the last section in `localStorage.settings_active_section`.

- [ ] **Step 4: Add embedded mode and top-frame native request routing**

```javascript
window.addEventListener('message', async event => {
  if(event.origin !== location.origin || event.data?.type !== 'settings-native-request') return;
  const {id, action, kind} = event.data;
  let result = {ok:false, error_code:'desktop_api_unavailable'};
  if(window.pywebview?.api){
    if(action === 'choose-download-directory') result = await window.pywebview.api.choose_download_directory();
    if(action === 'open-directory') result = await window.pywebview.api.open_directory(kind);
  }
  event.source?.postMessage({type:'settings-native-response', id, result}, event.origin);
});
```

In API and ComfyUI settings pages, detect `new URLSearchParams(location.search).get('embedded') === '1'`, add `embedded-settings` to the root/body, and use CSS to remove duplicated page backgrounds, outer framing, and oversized margins. Do not change their fetch/save/model/workflow logic.

- [ ] **Step 5: Run settings and sidebar tests**

Run: `python -m unittest tests.test_settings_center_structure tests.test_sidebar_footer_cleanup -v`

Expected: PASS; only one main settings entry remains and all seven panels and two embedded pages are present.

- [ ] **Step 6: Commit the settings center UI**

```powershell
git add static tests/test_sidebar_footer_cleanup.py tests/test_settings_center_structure.py
git commit -m "feat: add seven-section settings center"
```

---

### Task 7: Theme, Scale, Language, Storage, and Manual Update Behavior

**Files:**
- Modify: `static/js/theme.js`
- Modify: `static/js/i18n-core.js`
- Modify: `static/js/i18n/common.js`
- Modify: `static/js/i18n/studio.js`
- Modify: `static/index.html`
- Modify: `static/js/settings.js`
- Create: `tests/test_settings_behavior_contract.py`

**Interfaces:**
- Produces: `StudioTheme.set('system' | 'light' | 'dark')` and `StudioTheme.getMode()`.
- Produces: `StudioTheme.setScale('auto' | '80' | '90' | '100' | '110' | '125')`.
- Produces: root CSS variable `--studio-ui-scale` without changing canvas document coordinates or export resolution.
- Produces: immediate same-origin `studio-theme`, `studio-scale`, and `studio-lang` messages to loaded frames.

- [ ] **Step 1: Write failing behavior contract tests**

```python
def test_theme_supports_system_mode_and_media_change_listener(self):
    source = read("static/js/theme.js")
    for token in ("prefers-color-scheme", "getMode", "studio-scale", "--studio-ui-scale"):
        self.assertIn(token, source)

def test_settings_loads_and_saves_all_non_secret_preferences(self):
    source = read("static/js/settings.js")
    for token in ("/api/app-settings", "resolved_directory", "categorize", "notify", "appearance", "language"):
        self.assertIn(token, source)
    self.assertNotRegex(source, r"api[_-]?key\s*[:=]")

def test_update_is_manual(self):
    index = read("static/index.html")
    settings = read("static/js/settings.js")
    self.assertNotIn("checkForUpdates();", index)
    self.assertIn("/api/check-update", settings)
    self.assertIn("/api/update-from-github", settings)
```

- [ ] **Step 2: Run behavior tests and verify they fail**

Run: `python -m unittest tests.test_settings_behavior_contract -v`

Expected: FAIL because system theme, centralized scale, and settings-driven actions are incomplete.

- [ ] **Step 3: Implement authoritative settings sync and system theme**

```javascript
const systemQuery = matchMedia('(prefers-color-scheme: dark)');
function resolvedTheme(mode){ return mode === 'system' ? (systemQuery.matches ? 'dark' : 'light') : mode; }
function applyMode(mode){
  const resolved = resolvedTheme(mode);
  applyTheme(resolved);
  localStorage.setItem('studio_theme', mode);
  broadcast({type:'studio-theme', theme:resolved, mode});
}
systemQuery.addEventListener('change', () => {
  if(getMode() === 'system') applyMode('system');
});

function applyScale(mode){
  const percent = mode === 'auto' ? autoScaleForViewport() : Number(mode);
  document.documentElement.style.setProperty('--studio-ui-scale', String(percent / 100));
  broadcast({type:'studio-scale', mode, percent});
}
```

On settings startup, read `/api/app-settings`, seed the localStorage fast cache, and apply theme/scale/language before rendering controls. On each change, update local UI immediately, persist via `PUT /api/app-settings`, and revert with a visible error if persistence fails. Keep i18n's current dictionary and event model.

- [ ] **Step 4: Implement storage/cache/manual-update actions**

```javascript
async function refreshStorage(){ renderStorage(await requestJson('/api/storage-report')); }
async function clearCache(){
  const preview = await requestJson('/api/cache-cleanup-preview');
  if(!confirm(t('settings.cacheConfirm', {size:formatBytes(preview.bytes)}))) return;
  await requestJson('/api/cache-cleanup', {method:'POST'});
  await refreshStorage();
}
async function checkForUpdateManually(){ renderUpdate(await requestJson('/api/check-update')); }
```

Wire update installation only to an explicit click after the check result indicates an available update. Do not add startup polling or background timers.

- [ ] **Step 5: Run settings behavior and legacy theme/i18n tests**

Run: `python -m unittest tests.test_settings_behavior_contract tests.test_warm_beige_light_theme tests.test_sidebar_footer_cleanup -v`

Expected: PASS; existing light/dark theme contracts remain valid and no automatic update check is introduced.

- [ ] **Step 6: Commit integrated settings behavior**

```powershell
git add static tests/test_settings_behavior_contract.py
git commit -m "feat: synchronize appearance language and maintenance settings"
```

---

### Task 8: Full Regression, Packaged Build, and Desktop Acceptance

**Files:**
- Modify if required by failing verification: `build/windows/InfiniteCanvas.spec`
- Modify if required by failing verification: `build/windows/verify_release.py`
- Modify: `docs/windows-desktop-build.md`
- Test: all `tests/test_*.py`
- Output: `dist/installer/InfiniteCanvas-Setup-<VERSION>.exe`
- Output: `dist/installer/SHA256SUMS.txt`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: a clean installer that upgrades the same application ID and preserves `%LOCALAPPDATA%\InfiniteCanvas`.

- [ ] **Step 1: Run the complete automated suite**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: PASS with zero failures and zero errors.

- [ ] **Step 2: Run source scans for missed download paths and placeholders**

Run: `rg -n --glob "!static/vendor/**" --glob "*.js" --glob "*.html" "\.download\s*=|createElement\(['\"]a['\"]\)" static`

Expected: matches only browser fallback code in `static/js/downloads.js` and preview-only object URL code; no product download handler bypasses `StudioDownloads`.

Run: `rg -n "TO[D]O|TB[D]|implement la[t]er|fill in deta[i]ls" app_settings.py download_manager.py static/settings.html static/css/settings.css static/js/settings.js static/js/downloads.js`

Expected: no output.

- [ ] **Step 3: Build and verify the windowed application and clean installer**

Run: `powershell -ExecutionPolicy Bypass -File build/windows/build_release.ps1`

Expected: tests pass, `dist/InfiniteCanvas/InfiniteCanvas.exe` is produced with `console=False`, release verification passes, and `dist/installer/InfiniteCanvas-Setup-<VERSION>.exe` plus its SHA-256 file are created.

- [ ] **Step 4: Perform real Windows desktop acceptance in an isolated test data directory**

Launch the built EXE with `INFINITE_CANVAS_DATA_DIR` set to a temporary acceptance directory and verify:

```text
1. Exactly one InfiniteCanvas desktop window appears; no browser tab and no CMD window opens.
2. The sidebar contains one Settings entry; each of the seven secondary sections opens without overlap at 1024x700 and 1440x900.
3. API and workflow embedded pages load and retain their existing save/test/import functions.
4. Theme system/light/dark, scale auto/80/90/100/110/125, and Chinese/English update all loaded frames immediately.
5. First image, video, audio, workflow, canvas JSON, and ZIP downloads create the correct category folders below Downloads\InfiniteCanvas.
6. Repeating one download creates the (1) file and leaves the original hash unchanged.
7. Changing and resetting the download directory persists across restart; completion shows the real path and Open Folder works.
8. Cache cleanup removes previews and partial downloads only; before/after hashes for canvases, projects, assets, workflows, API configuration, and logs remain equal.
9. Check for Updates runs only after clicking the button; installation is a separate explicit action.
```

Expected: every item passes; capture any failure in the desktop log and fix before continuing.

- [ ] **Step 5: Document the release and manual-update workflow**

Add to `docs/windows-desktop-build.md`:

```text
- Settings and downloads are preserved under %LOCALAPPDATA%\InfiniteCanvas during installer upgrades.
- Publish each new installer and SHA256SUMS.txt to the existing GitHub release/download source.
- Users install the newer package over the current version; the stable Inno Setup AppId upgrades in place.
- The application checks and installs updates only when the user clicks the corresponding settings action.
```

- [ ] **Step 6: Run the verifier against the final artifact**

Run: `python build/windows/verify_release.py dist/InfiniteCanvas --version-file VERSION --manifest dist/release-manifest.json`

Expected: PASS, including all new Python modules and front-end settings/download assets collected by PyInstaller.

- [ ] **Step 7: Commit documentation and any packaging fixes**

```powershell
git add build/windows docs/windows-desktop-build.md
git commit -m "build: package settings and download manager"
```

- [ ] **Step 8: Record final artifact identities**

Run: `Get-ChildItem dist/installer/InfiniteCanvas-Setup-*.exe | Select-Object FullName,Length,LastWriteTime; Get-Content dist/installer/SHA256SUMS.txt; git status --short --branch`

Expected: one current-version installer is reported with its exact size and hash, and the working tree is clean.
