# Smart Canvas Visible Reference Mentions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让智能画布 `@` 弹窗的“输入源”候选与当前节点红框参考栏的可见图片和视频保持一致，同时继续排除祖先、其他分支及未连线节点媒体。

**Architecture:** 复用现有 `visibleReferenceImagesFor(node)` 作为 `inputMentionCandidateImages(node)` 的唯一画布候选来源，再沿用现有 URL 过滤、去重和别名生成。共享请求授权保持不变，继续在发送前验证当前节点自身、直接连线和资产库明确引用。

**Tech Stack:** 原生 JavaScript、HTML 缓存版本参数、Python `unittest`、Node.js 语法/行为测试、PowerShell 部署打包。

## Global Constraints

- `@` 输入源必须严格对应当前节点参考栏的当前可见素材。
- 当前节点已产出的图片和视频必须可选择。
- 祖先节点、其他分支和未连线节点媒体不得重新进入候选或 API 请求。
- 资产库标签及资产库明确 `@` 的既有行为不变。
- 候选继续按 URL 去重，不新增 UI 控件，不改变引用数量上限。
- 产出的部署文件保存到 `E:\codex`。

---

### Task 1: Add a failing visible-reference candidate regression

**Files:**
- Modify: `tests/test_smart_canvas_direct_references.py`

**Interfaces:**
- Consumes: JavaScript source function `inputMentionCandidateImages(node)` from `static/js/smart-canvas.js`.
- Produces: Regression coverage requiring `inputMentionCandidateImages(node)` to call `visibleReferenceImagesFor(node)` and to preserve current-node image/video candidates with URL deduplication.

- [ ] **Step 1: Replace the source-wiring assertion**

Change the existing candidate test to:

```python
def test_input_mention_candidates_use_visible_reference_row(self):
    body = self.function_source("inputMentionCandidateImages")
    self.assertIn("visibleReferenceImagesFor(node)", body)
    self.assertNotIn("directConnectedMediaFor(node)", body)
    self.assertNotIn("lineImagesFor(node)", body)
```

- [ ] **Step 2: Add an executable candidate behavior test**

Add this test before `test_direct_graph_asset_exception_and_media_types`:

```python
@unittest.skipUnless(shutil.which("node"), "Node.js is required")
def test_input_mention_candidates_keep_self_media_and_dedupe(self):
    function = self.function_source("inputMentionCandidateImages")
    script = function + r'''
function visibleReferenceImagesFor(){
  return [
    {url:'self.png', nodeId:'C', kind:'image', name:'当前图片'},
    {url:'self.mp4', nodeId:'C', kind:'video', name:'当前视频'},
    {url:'direct.png', nodeId:'B', kind:'image', name:'直接图片'},
    {url:'self.png', nodeId:'C', kind:'image', name:'重复图片'}
  ];
}
const items = inputMentionCandidateImages({id:'C'});
const urls = items.map(item => item.url);
if (JSON.stringify(urls) !== JSON.stringify(['self.png','self.mp4','direct.png'])) {
  throw new Error(`unexpected candidates: ${urls}`);
}
if (items[0].alias !== '当前图片' || items[1].kind !== 'video') {
  throw new Error('candidate metadata was not preserved');
}
'''
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
```

- [ ] **Step 3: Run the targeted tests to verify failure**

Run:

```powershell
python -m unittest tests.test_smart_canvas_direct_references -v
```

Expected: `test_input_mention_candidates_use_visible_reference_row` fails because the implementation still calls `directConnectedMediaFor(node)`; the executable test otherwise confirms the existing mapping/dedup structure.

- [ ] **Step 4: Commit the regression test**

```powershell
git add tests/test_smart_canvas_direct_references.py
git commit -m "test: cover visible reference mention candidates"
```

### Task 2: Reuse the visible reference row for mention candidates

**Files:**
- Modify: `static/js/smart-canvas.js:13386`
- Modify: `static/smart-canvas.html:448`
- Test: `tests/test_smart_canvas_direct_references.py`

**Interfaces:**
- Consumes: `visibleReferenceImagesFor(node) -> Array<MediaReference>`.
- Produces: `inputMentionCandidateImages(node) -> Array<MediaReference>` using exactly the visible reference row as its source.

- [ ] **Step 1: Make the minimal candidate-source change**

Change only the first line inside `inputMentionCandidateImages`:

```javascript
function inputMentionCandidateImages(node){
    const current = node ? visibleReferenceImagesFor(node) : [];
    const seen = new Set();
    return current.filter(img => {
        if(!img?.url || seen.has(img.url)) return false;
        seen.add(img.url);
        return true;
    }).map((img, index) => ({
        ...img,
        mentionId:`mention_${index}_${Math.random().toString(36).slice(2, 7)}`,
        alias:img.name || `图片${index + 1}`
    }));
}
```

- [ ] **Step 2: Bump the smart-canvas script cache version**

Change the script tag to:

```html
<script src="/static/js/smart-canvas.js?v=2026.08.02.visible-reference-mentions.1"></script>
```

- [ ] **Step 3: Run syntax and targeted tests**

Run:

```powershell
node --check static/js/smart-canvas.js
python -m unittest tests.test_smart_canvas_direct_references -v
```

Expected: JavaScript syntax check succeeds and all direct-reference tests pass.

- [ ] **Step 4: Run the complete regression suite**

Run:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected: All tests pass, including existing API request-boundary, asset-library exception, Seedance 480p, MediaKit, theme and upload-node tests.

- [ ] **Step 5: Review the scoped diff**

Run:

```powershell
git diff --check -- static/js/smart-canvas.js static/smart-canvas.html tests/test_smart_canvas_direct_references.py
git diff --stat -- static/js/smart-canvas.js static/smart-canvas.html tests/test_smart_canvas_direct_references.py
```

Expected: No whitespace errors; functional edits are limited to the candidate source, cache version and regression tests.

### Task 3: Build and verify the incremental deployment package

**Files:**
- Package: `E:\codex\InfiniteCanvas-智能画布可见参考素材@修复-增量替换包-20260802-v1.zip`
- Include: `static/js/smart-canvas.js`
- Include: `static/smart-canvas.html`
- Include: `本次修复替换说明.txt`

**Interfaces:**
- Consumes: Fully tested files from Task 2.
- Produces: A replace-in-place deployment archive and SHA256 checksum for other InfiniteCanvas computers.

- [ ] **Step 1: Write the package note**

The note must state:

```text
本包让智能画布 @ 输入源与红框参考栏当前可见素材保持一致。
当前节点自产图片/视频和直接连线素材可以 @；祖先、其他分支和未连线节点仍不可用。
复制 static 文件夹到目标 InfiniteCanvas 根目录并替换同名文件，重启后按 Ctrl+F5。
```

- [ ] **Step 2: Create the archive in `E:\codex`**

Use PowerShell `Compress-Archive` with only the two runtime files and the package note. Do not include API keys, canvas data, asset files, Python runtime or test caches.

- [ ] **Step 3: Verify archive entries and checksum**

Run:

```powershell
tar -tf E:\codex\InfiniteCanvas-智能画布可见参考素材@修复-增量替换包-20260802-v1.zip
Get-FileHash -Algorithm SHA256 E:\codex\InfiniteCanvas-智能画布可见参考素材@修复-增量替换包-20260802-v1.zip
```

Expected entries:

```text
static/smart-canvas.html
static/js/smart-canvas.js
本次修复替换说明.txt
```

- [ ] **Step 4: Report deployment instructions**

Provide the clickable absolute package path, SHA256 value, passed test count and the four replacement steps: close service, back up matching files, replace the `static` folder, restart and press `Ctrl+F5`.
