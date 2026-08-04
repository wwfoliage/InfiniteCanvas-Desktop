# Smart Canvas Direct Reference Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure smart-canvas image/video generation only offers and uploads media from directly connected upstream nodes, while still allowing explicit asset-library mentions and existing self/manual references.

**Architecture:** Add one direct-upstream boundary helper in `smart-canvas.js`, then reuse it in both mention-candidate rendering and shared request construction. Canvas-backed prompt mentions must resolve to a direct upstream node; asset-library mentions remain allowed because they have no canvas `nodeId`. Existing deduplication, reference limits, blocked references, self-edit inputs, and manual asset references remain in the shared reference pipeline.

**Tech Stack:** Vanilla JavaScript, DOM datasets, Python `unittest`, Node.js helper execution, FastAPI application test suite.

## Global Constraints

- Canvas media is allowed only from direct incoming connections; do not recursively traverse ancestors.
- Normal API generation uses direct `input` connections; workflow-input generation preserves the existing `input` plus `flow` rule.
- Asset-library media explicitly selected with `@` remains uploadable without a canvas connection.
- Existing self-edit references and manually added asset references remain supported.
- Stale ancestor or disconnected-node mention tokens remain visible as `@name` text but their media is excluded from requests.
- Image and video generation must use the same shared filtering logic.
- Final references retain the existing maximum count, blocked-reference behavior, media-kind handling, and URL deduplication.

---

### Task 1: Add executable regression coverage for direct reference boundaries

**Files:**
- Create: `tests/test_smart_canvas_direct_references.py`
- Read: `static/js/smart-canvas.js:12990-13830`

**Interfaces:**
- Consumes: JavaScript functions `directReferenceNodeIdsFor(node, ctx)`, `directConnectedMediaFor(node, consume, ctx)`, `isAllowedMentionReference(node, reference, ctx)`, and `inputMentionCandidateImages(node)` introduced in Tasks 2 and 3.
- Produces: Regression tests that enforce direct-only canvas references, asset-library exceptions, stale-token filtering, video support, and URL deduplication.

- [ ] **Step 1: Write a failing source-wiring test**

Create `tests/test_smart_canvas_direct_references.py` with a source-level test that reads `static/js/smart-canvas.js` and asserts the candidate list no longer calls recursive `lineImagesFor(node)`:

```python
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "static" / "js" / "smart-canvas.js"


class SmartCanvasDirectReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_input_mention_candidates_use_direct_media_only(self):
        match = re.search(
            r"function inputMentionCandidateImages\(node\)\{.*?\n\}",
            self.source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group(0)
        self.assertIn("directConnectedMediaFor(node)", body)
        self.assertNotIn("lineImagesFor(node)", body)
        self.assertNotIn("manualReferenceImagesFor(node)", body)
```

- [ ] **Step 2: Write a failing executable JavaScript boundary test**

Add a Node-backed test that extracts the four small boundary helpers and evaluates a graph `A → B → C`, an unconnected D, a direct video from B, and an asset reference without `nodeId`:

```python
    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_direct_graph_and_asset_exception(self):
        required = [
            "directReferenceNodeIdsFor",
            "directConnectedMediaFor",
            "isAssetMentionReference",
            "isAllowedMentionReference",
        ]
        functions = []
        for name in required:
            match = re.search(
                rf"function {name}\([^)]*\)\{{.*?\n\}}",
                self.source,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(match, f"{name} was not found")
            functions.append(match.group(0))

        script = "\n".join(functions) + r'''
const nodes = [
  {id:'A', images:[{url:'a.png', kind:'image'}]},
  {id:'B', images:[{url:'b.png', kind:'image'}, {url:'b.mp4', kind:'video'}]},
  {id:'C', images:[]},
  {id:'D', images:[{url:'d.png', kind:'image'}]},
];
const canvas = {connections:[
  {from:'A', to:'B', kind:'input'},
  {from:'B', to:'C', kind:'input'},
]};
const smartLoopContext = null;
function smartImageUsesWorkflowInput(){ return false; }
function inputNodesFor(node){
  return canvas.connections.filter(c => c.to === node.id && (c.kind || 'flow') === 'input')
    .map(c => nodes.find(n => n.id === c.from)).filter(Boolean);
}
function workflowInputNodesFor(node){ return inputNodesFor(node); }
function imagesForNode(node){
  return (node.images || []).map((item, imageIndex) => ({...item, nodeId:node.id, imageIndex}));
}
function outputImagesForNode(node){ return imagesForNode(node); }
const c = nodes.find(n => n.id === 'C');
const ids = [...directReferenceNodeIdsFor(c)];
if (JSON.stringify(ids) !== JSON.stringify(['B'])) throw new Error(`unexpected ids: ${ids}`);
const urls = directConnectedMediaFor(c).map(item => item.url);
if (JSON.stringify(urls) !== JSON.stringify(['b.png','b.mp4'])) throw new Error(`unexpected media: ${urls}`);
if (!isAllowedMentionReference(c, {url:'b.png', nodeId:'B'})) throw new Error('direct reference rejected');
if (isAllowedMentionReference(c, {url:'a.png', nodeId:'A'})) throw new Error('ancestor reference allowed');
if (isAllowedMentionReference(c, {url:'d.png', nodeId:'D'})) throw new Error('unconnected reference allowed');
if (!isAllowedMentionReference(c, {url:'asset.png', nodeId:'', asset_uris:{}})) throw new Error('asset reference rejected');
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
```

- [ ] **Step 3: Run the new tests and verify they fail**

Run:

```powershell
.\python\python.exe -m unittest discover -s tests -p 'test_smart_canvas_direct_references.py' -v
```

Expected: FAIL because `directReferenceNodeIdsFor`, `directConnectedMediaFor`, `isAssetMentionReference`, and `isAllowedMentionReference` do not exist and `inputMentionCandidateImages` still calls `lineImagesFor(node)`.

- [ ] **Step 4: Commit the failing tests**

```powershell
git add tests/test_smart_canvas_direct_references.py
git commit -m "test: cover direct smart canvas references"
```

### Task 2: Replace recursive mention candidates with direct connected media

**Files:**
- Modify: `static/js/smart-canvas.js:13283-13370`
- Test: `tests/test_smart_canvas_direct_references.py`

**Interfaces:**
- Consumes: Existing `inputNodesFor(node)`, `workflowInputNodesFor(node)`, `outputImagesForNode(node, consume, ctx)`, `smartImageUsesWorkflowInput(node, ctx)`, and `uniqueReferenceImages(images)`.
- Produces:
  - `directReferenceNodesFor(node, ctx) -> Array<Node>`
  - `directReferenceNodeIdsFor(node, ctx) -> Set<string>`
  - `directConnectedMediaFor(node, consume, ctx) -> Array<MediaReference>`
  - `inputMentionCandidateImages(node) -> Array<MentionCandidate>` containing only direct connected media.

- [ ] **Step 1: Add direct-boundary helper functions**

Insert immediately before the existing line-connection traversal helpers:

```javascript
function directReferenceNodesFor(node, ctx=smartLoopContext){
    if(!node) return [];
    return smartImageUsesWorkflowInput(node, ctx)
        ? workflowInputNodesFor(node)
        : inputNodesFor(node);
}
function directReferenceNodeIdsFor(node, ctx=smartLoopContext){
    return new Set(directReferenceNodesFor(node, ctx).map(input => input.id).filter(Boolean));
}
function directConnectedMediaFor(node, consume=false, ctx=smartLoopContext){
    return directReferenceNodesFor(node, ctx)
        .flatMap(input => outputImagesForNode(input, consume, ctx))
        .filter(item => item?.url);
}
```

Do not remove `connectedLineNodeIds`, `upstreamLineNodeIds`, or `lineImagesFor`; other canvas features may still use those traversal functions.

- [ ] **Step 2: Switch the input mention candidate list to the new boundary**

Replace the first line of `inputMentionCandidateImages`:

```javascript
function inputMentionCandidateImages(node){
    const current = node ? directConnectedMediaFor(node) : [];
```

The asset-library tab remains backed by `assetMentionCandidateImages`, so removing `manualReferenceImagesFor(node)` here does not disable asset-library `@` selection.

- [ ] **Step 3: Run the candidate and graph tests**

Run:

```powershell
.\python\python.exe -m unittest discover -s tests -p 'test_smart_canvas_direct_references.py' -v
```

Expected: the source-wiring test passes; the executable test still fails until Task 3 adds mention authorization helpers.

- [ ] **Step 4: Commit the direct-candidate implementation**

```powershell
git add static/js/smart-canvas.js tests/test_smart_canvas_direct_references.py
git commit -m "fix: limit mention candidates to direct inputs"
```

### Task 3: Enforce the same boundary in visible references and API requests

**Files:**
- Modify: `static/js/smart-canvas.js:13332-13358`
- Modify: `static/js/smart-canvas.js:13746-13815`
- Test: `tests/test_smart_canvas_direct_references.py`

**Interfaces:**
- Consumes: `directReferenceNodeIdsFor(node, ctx)`, `collectPromptParts()`, `collectMentionedImagesFromPrompt()`, `defaultReferenceImagesFor(node, consume, ctx)`, `uniqueReferenceImages(images)`, and `inputRefKey(img)`.
- Produces:
  - `isAssetMentionReference(reference) -> boolean`
  - `isAllowedMentionReference(node, reference, ctx) -> boolean`
  - `allowedMentionedImagesFromPrompt(node, ctx) -> Array<MediaReference>`
  - `buildPromptRequest(...)` with filtered prompt-token media.

- [ ] **Step 1: Add shared mention authorization helpers**

Insert after `collectMentionedImagesFromPrompt`:

```javascript
function isAssetMentionReference(reference){
    return Boolean(reference?.url && !reference.nodeId);
}
function isAllowedMentionReference(node, reference, ctx=smartLoopContext){
    if(!node || !reference?.url) return false;
    if(isAssetMentionReference(reference)) return true;
    if(directReferenceNodeIdsFor(node, ctx).has(reference.nodeId)) return true;
    if(imagesForNode(node).some(item => item?.url === reference.url)) return true;
    return directConnectedMediaFor(node, false, ctx).some(item => item?.url === reference.url);
}
function allowedMentionedImagesFromPrompt(node, ctx=smartLoopContext){
    return collectMentionedImagesFromPrompt().filter(reference => isAllowedMentionReference(node, reference, ctx));
}
```

The `!reference.nodeId` rule preserves old asset tokens that were saved before asset registration metadata existed. Canvas-generated references always receive `nodeId` from `imagesForNode`.

- [ ] **Step 2: Filter the visible reference row**

Replace `visibleReferenceImagesFor` with:

```javascript
function visibleReferenceImagesFor(node){
    const base = defaultReferenceImagesFor(node);
    return uniqueReferenceImages([...base, ...allowedMentionedImagesFromPrompt(node)]);
}
```

This removes stale ancestor and disconnected tokens from frame 1 while retaining direct references, self/manual references already in `base`, and asset-library mentions.

- [ ] **Step 3: Filter prompt tokens during shared request construction**

In `buildPromptRequest`, calculate authorization before processing parts and reject unauthorized canvas media before adding it to `refs`:

```javascript
    parts.forEach(part => {
        if(part.type === 'text'){
            body += part.text;
            return;
        }
        if(!part.url) return;
        const mentionName = part.name || '图片';
        if(!isAllowedMentionReference(node, part, ctx)){
            body += `@${mentionName}`;
            return;
        }
        hasMentionToken = true;
        const mentionedKey = inputRefKey(part);
        if(blockedRefs.has(mentionedKey)){
            body += `@${mentionName}`;
            return;
        }
        if(!refMap.has(part.url)){
            if(refs.length >= SMART_REFERENCE_IMAGE_MAX){
                body += `@${mentionName}`;
                return;
            }
            refMap.set(part.url, refs.length + 1);
            refs.push({
                url:part.url,
                name:mentionName,
                nodeId:part.nodeId,
                imageIndex:part.imageIndex,
                kind:part.kind || 'image',
                asset_uris:part.asset_uris || {},
                role:`image_${refs.length + 1}`
            });
        }
        body += `图${refMap.get(part.url)}`;
    });
```

Keep construction of `defaultRefs` unchanged: it already contains mode-appropriate direct upstream media plus existing self/manual references and performs URL deduplication through `uniqueReferenceImages`.

- [ ] **Step 4: Extend the executable test to cover stale tokens and duplicate URLs**

Add assertions that:

```javascript
if (isAllowedMentionReference(c, {url:'a.png', nodeId:'A'})) throw new Error('stale ancestor token allowed');
if (!isAllowedMentionReference(c, {url:'asset-local.png', nodeId:''})) throw new Error('legacy asset token rejected');
```

Add a source assertion that the shared `buildPromptRequest` body calls `isAllowedMentionReference(node, part, ctx)` before `refs.push`, and that `visibleReferenceImagesFor` calls `allowedMentionedImagesFromPrompt(node)`.

- [ ] **Step 5: Run direct-reference tests**

Run:

```powershell
.\python\python.exe -m unittest discover -s tests -p 'test_smart_canvas_direct_references.py' -v
```

Expected: PASS for direct image/video, ancestor exclusion, unconnected exclusion, legacy asset allowance, and request wiring.

- [ ] **Step 6: Commit request-boundary enforcement**

```powershell
git add static/js/smart-canvas.js tests/test_smart_canvas_direct_references.py
git commit -m "fix: filter smart generation references at request boundary"
```

### Task 4: Bust browser cache and run the full regression suite

**Files:**
- Modify: `static/smart-canvas.html:448`
- Test: `tests/test_smart_canvas_direct_references.py`
- Test: all files matching `tests/test_*.py`

**Interfaces:**
- Consumes: Completed smart-canvas reference filtering from Tasks 2 and 3.
- Produces: A browser-visible build that loads the corrected JavaScript and passes the full project suite.

- [ ] **Step 1: Update the smart-canvas script cache key**

Change only the query value on the runtime script tag:

```html
<script src="/static/js/smart-canvas.js?v=2026.08.02.direct-references.1"></script>
```

- [ ] **Step 2: Run JavaScript syntax validation**

Run:

```powershell
node --check static/js/smart-canvas.js
```

Expected: exit code 0 with no syntax error.

- [ ] **Step 3: Run the complete test suite**

Run:

```powershell
.\python\python.exe -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: all existing MediaKit, Seedance 480p, upload-node, canvas-list, theme, endpoint, and new direct-reference tests pass.

- [ ] **Step 4: Verify runtime behavior in the browser**

Open a smart canvas containing `A → B → C` and an unconnected D, then confirm:

1. C's input `@` tab contains only B's image/video.
2. The asset-library tab still inserts an unconnected asset.
3. Frame 1 excludes A and D but includes B and the manually selected asset.
4. Generation logs/request metadata contain B and the asset once each, with no A or D URL.

- [ ] **Step 5: Commit cache key and verification state**

```powershell
git add static/smart-canvas.html tests/test_smart_canvas_direct_references.py
git commit -m "test: verify direct smart canvas references"
```

## Plan Self-Review

- Spec coverage: direct inputs, workflow input kinds, asset-library exception, self/manual references, stale tokens, images, videos, URL deduplication, shared image/video request path, and browser cache invalidation are covered.
- Placeholder scan: every step contains concrete files, commands, expected outcomes, and implementation code.
- Interface consistency: Tasks 2 and 3 consistently use `directReferenceNodesFor`, `directReferenceNodeIdsFor`, `directConnectedMediaFor`, `isAssetMentionReference`, `isAllowedMentionReference`, and `allowedMentionedImagesFromPrompt` with matching signatures.
