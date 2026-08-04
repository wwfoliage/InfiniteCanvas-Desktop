# InfiniteCanvas 暖米灰白天模式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 InfiniteCanvas 所有白天模式页面统一为低眩光“暖米灰”配色，同时保持深色模式、媒体原色、功能和布局不变。

**Architecture:** 保留现有 `light` / `dark` 双主题机制，不改 JavaScript 主题状态。核心画布和独立设置页通过各自 CSS 根变量换色，共享工具页通过 `theme.css` 的白天模式高特异性变量与组件级覆盖换色；HTML 只更新样式缓存版本。

**Tech Stack:** HTML、CSS 自定义属性、原生 JavaScript 主题切换、Python `unittest` 静态回归测试、Codex 内置浏览器视觉验证、PowerShell 增量打包。

## Global Constraints

- 白天模式页面/画布背景必须使用 `#E0DDD4`。
- 白天模式节点/卡片背景必须使用 `#F3F0E9` 或对应的半透明等价值。
- 主文字使用 `#3B3935`，次文字使用 `#746F66`，弱文字使用 `#928A7E`。
- 主操作使用 `#625548`，主操作文字使用 `#F7F4EE`。
- 不修改任何现有深色模式变量值。
- 不修改 `static/js/theme.js`，不迁移或清除 `studio_theme`。
- 不对 `img`、`video`、媒体预览或媒体画布应用滤镜、混合模式或颜色叠层。
- 不改变页面布局、节点位置、节点尺寸、连线逻辑、API 或生成行为。
- 错误、警告、成功和处理中状态保留原有语义色。
- 只提交本主题相关文件，不包含用户工作区的其他未提交改动。
- 最终增量替换包和验证截图保存到 `E:\codex`。

---

## File Structure

- `tests/test_warm_beige_light_theme.py`：对白天模式关键色板、深色模式签名、共享覆盖和缓存版本进行静态回归检查。
- `static/css/smart-canvas.css`：智能画布白天模式根变量。
- `static/css/canvas.css`：普通画布白天模式根变量。
- `static/css/canvas-list.css`：画布列表白天模式根变量。
- `static/css/asset-manager.css`：素材库白天模式根变量。
- `static/css/api-settings.css`：API 设置最终生效的白天模式变量块。
- `static/css/comfyui-settings.css`：ComfyUI 工作流设置白天模式根变量。
- `static/css/theme.css`：共享工具页的暖米灰变量、表面、输入控件和主操作覆盖。
- `static/index.html`：应用外壳、侧栏和舞台的白天模式变量。
- `static/gpt-chat.html`：对话页独立 `--chat-*` 白天模式变量。
- 受影响的 `static/*.html`：仅更新 CSS 查询版本为 `2026.07.29.warm1`。

---

### Task 1: 智能画布和普通画布基础色板

**Files:**
- Create: `tests/test_warm_beige_light_theme.py`
- Modify: `static/css/smart-canvas.css:2-10`
- Modify: `static/css/canvas.css:2-3`

**Interfaces:**
- Consumes: 现有 `.theme-dark` 深色变量块和 CSS 自定义属性命名。
- Produces: 两种画布共同使用的 `--page`、`--grid`、`--panel`、`--card`、`--soft`、`--line`、`--text`、`--strong` 白天模式语义。

- [ ] **Step 1: 写入失败的核心画布色板测试**

```python
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def compact(source: str) -> str:
    return re.sub(r"\s+", "", source).lower()


class WarmBeigeLightThemeTests(unittest.TestCase):
    def read_compact(self, relative: str) -> str:
        return compact((ROOT / relative).read_text(encoding="utf-8"))

    def assert_tokens(self, relative: str, tokens: list[str]) -> None:
        source = self.read_compact(relative)
        for token in tokens:
            self.assertIn(token.lower(), source, f"{relative} is missing {token}")

    def test_core_canvases_use_warm_beige_palette(self):
        shared = [
            "--page:#e0ddd4",
            "--grid:rgba(183,174,161,.55)",
            "--text:#3b3935",
            "--muted:#746f66",
            "--faint:#928a7e",
            "--line:#c5beb2",
            "--soft:#e5e0d7",
            "--shadow:rgba(73,64,54,.10)",
            "--strong:#625548",
            "--strong-text:#f7f4ee",
        ]
        self.assert_tokens("static/css/smart-canvas.css", shared + [
            "--panel:rgba(239,236,229,.94)",
            "--card:#f3f0e9",
        ])
        self.assert_tokens("static/css/canvas.css", shared + [
            "--panel:rgba(239,236,229,.94)",
            "--card:rgba(243,240,233,.96)",
            "--card-solid:#f3f0e9",
            "--soft-2:#d8d2c8",
            "--line-2:#b0a89b",
        ])

    def test_core_canvas_dark_palettes_remain_unchanged(self):
        smart = self.read_compact("static/css/smart-canvas.css")
        normal = self.read_compact("static/css/canvas.css")
        self.assertIn(".theme-dark{--page:#0f141d", smart)
        self.assertIn("--card:#171d29", smart)
        self.assertIn(".theme-dark{--page:#0b1020", normal)
        self.assertIn("--card-solid:#111827", normal)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认白天色板断言失败**

Run:

```powershell
python\python.exe -m unittest discover -s tests -p "test_warm_beige_light_theme.py" -v
```

Expected: `test_core_canvases_use_warm_beige_palette` 失败；深色模式签名测试通过。

- [ ] **Step 3: 修改智能画布白天模式根变量**

将 `static/css/smart-canvas.css` 顶部 `:root` 替换为：

```css
:root {
    --page:#e0ddd4; --grid:rgba(183,174,161,.55); --panel:rgba(239,236,229,.94); --card:#f3f0e9;
    --text:#3b3935; --muted:#746f66; --faint:#928a7e; --line:#c5beb2; --soft:#e5e0d7;
    --shadow:rgba(73,64,54,.10); --strong:#625548; --strong-text:#f7f4ee;
}
```

保留紧随其后的 `.theme-dark` 原文。

- [ ] **Step 4: 修改普通画布白天模式根变量**

将 `static/css/canvas.css` 顶部 `:root` 替换为：

```css
:root { --ease:cubic-bezier(.4,0,.2,1); --page:#e0ddd4; --grid:rgba(183,174,161,.55); --panel:rgba(239,236,229,.94); --card:rgba(243,240,233,.96); --card-solid:#f3f0e9; --soft:#e5e0d7; --soft-2:#d8d2c8; --line:#c5beb2; --line-2:#b0a89b; --text:#3b3935; --muted:#746f66; --faint:#928a7e; --shadow:rgba(73,64,54,.10); --strong:#625548; --strong-text:#f7f4ee; }
```

保留 `.theme-dark` 原文。

- [ ] **Step 5: 运行核心画布测试并确认通过**

Run:

```powershell
python\python.exe -m unittest discover -s tests -p "test_warm_beige_light_theme.py" -v
```

Expected: 2 tests passed。

- [ ] **Step 6: 提交核心画布色板**

```powershell
git add tests/test_warm_beige_light_theme.py static/css/smart-canvas.css static/css/canvas.css
git commit -m "style: apply warm beige palette to canvases"
```

---

### Task 2: 画布列表、素材库和设置页色板

**Files:**
- Modify: `tests/test_warm_beige_light_theme.py`
- Modify: `static/css/canvas-list.css:4-24`
- Modify: `static/css/asset-manager.css:2-18`
- Modify: `static/css/api-settings.css:4475-4484`
- Modify: `static/css/comfyui-settings.css:1-2`

**Interfaces:**
- Consumes: Task 1 的暖米灰语义色。
- Produces: 列表、素材和设置页面一致的页面、面板、卡片、边框、文字和主操作变量。

- [ ] **Step 1: 增加失败的支持页面色板测试**

在测试类中加入：

```python
    def test_support_pages_use_warm_beige_palette(self):
        common = [
            "--text:#3b3935",
            "--muted:#746f66",
            "--faint:#928a7e",
        ]
        self.assert_tokens("static/css/canvas-list.css", common + [
            "--page:#e0ddd4",
            "--panel-solid:#efece5",
            "--card-solid:#f3f0e9",
            "--soft:#e5e0d7",
            "--line:#c5beb2",
            "--line-2:#b0a89b",
            "--strong:#625548",
            "--strong-text:#f7f4ee",
            "--accent:#786b5c",
        ])
        self.assert_tokens("static/css/asset-manager.css", common + [
            "--page:#e0ddd4",
            "--card:#f3f0e9",
            "--soft:#e5e0d7",
            "--line:#c5beb2",
            "--line-2:#b0a89b",
            "--strong:#625548",
            "--strong-text:#f7f4ee",
        ])
        for relative in (
            "static/css/api-settings.css",
            "static/css/comfyui-settings.css",
        ):
            self.assert_tokens(relative, common + [
                "--bg:#e0ddd4",
                "--panel:#f3f0e9",
                "--soft:#e5e0d7",
                "--line:#c5beb2",
                "--line-strong:#b0a89b",
                "--accent:#625548",
            ])

    def test_support_page_dark_palettes_remain_unchanged(self):
        self.assert_tokens("static/css/canvas-list.css", [
            ".theme-dark{--page:#10141d",
            "--card-solid:#151b26",
        ])
        self.assert_tokens("static/css/asset-manager.css", [
            ".theme-dark{--page:#08090c",
            "--card:#11141a",
        ])
        self.assert_tokens("static/css/api-settings.css", [
            "body.studio-theme-dark,html.studio-theme-darkbody{--bg:#11161d",
            "--panel:#1b222c",
        ])
        self.assert_tokens("static/css/comfyui-settings.css", [
            "body.studio-theme-dark,html.studio-theme-darkbody{--bg:#0e1014",
            "--panel:#1c1e26",
        ])
```

- [ ] **Step 2: 运行测试并确认支持页面断言失败**

Run:

```powershell
python\python.exe tests\test_warm_beige_light_theme.py WarmBeigeLightThemeTests.test_support_pages_use_warm_beige_palette -v
```

Expected: FAIL，首个缺失值为暖米灰页面或面板变量。

- [ ] **Step 3: 更新画布列表和素材库根变量**

画布列表白天模式使用：

```css
--page:#e0ddd4;
--grid:rgba(183,174,161,.55);
--panel:rgba(239,236,229,.92);
--panel-solid:#efece5;
--card:rgba(243,240,233,.98);
--card-solid:#f3f0e9;
--soft:#e5e0d7;
--soft-2:#d8d2c8;
--line:#c5beb2;
--line-2:#b0a89b;
--text:#3b3935;
--muted:#746f66;
--faint:#928a7e;
--shadow:rgba(73,64,54,.10);
--shadow-strong:rgba(73,64,54,.16);
--strong:#625548;
--strong-text:#f7f4ee;
--accent:#786b5c;
```

素材库白天模式使用：

```css
--page:#e0ddd4;
--panel:rgba(239,236,229,.94);
--card:#f3f0e9;
--soft:#e5e0d7;
--soft-2:#d8d2c8;
--line:#c5beb2;
--line-2:#b0a89b;
--text:#3b3935;
--muted:#746f66;
--faint:#928a7e;
--strong:#625548;
--strong-text:#f7f4ee;
```

保留两份文件的深色模式、危险色和成功色原文。

- [ ] **Step 4: 更新 API 设置最终变量块**

将 `static/css/api-settings.css` 文件末段的最终白天变量块改为：

```css
:root {
    --bg:#e0ddd4;
    --panel:#f3f0e9;
    --soft:#e5e0d7;
    --line:#c5beb2;
    --line-strong:#b0a89b;
    --text:#3b3935;
    --muted:#746f66;
    --faint:#928a7e;
    --accent:#625548;
}
```

不修改紧邻的 `body.studio-theme-dark, html.studio-theme-dark body` 块。

- [ ] **Step 5: 更新 ComfyUI 设置根变量**

将第一行白天变量改为：

```css
:root { --bg:#e0ddd4; --panel:#f3f0e9; --soft:#e5e0d7; --line:#c5beb2; --line-strong:#b0a89b; --text:#3b3935; --muted:#746f66; --faint:#928a7e; --accent:#625548; }
```

保留第二行深色变量原文。

- [ ] **Step 6: 运行测试并确认通过**

Run:

```powershell
python\python.exe -m unittest discover -s tests -p "test_warm_beige_light_theme.py" -v
```

Expected: 4 tests passed。

- [ ] **Step 7: 提交支持页面色板**

```powershell
git add tests/test_warm_beige_light_theme.py static/css/canvas-list.css static/css/asset-manager.css static/css/api-settings.css static/css/comfyui-settings.css
git commit -m "style: unify warm beige settings surfaces"
```

---

### Task 3: 共享工具页、应用外壳和对话页

**Files:**
- Modify: `tests/test_warm_beige_light_theme.py`
- Modify: `static/css/theme.css:1652`
- Modify: `static/index.html:47-69`
- Modify: `static/gpt-chat.html:26-45`
- Modify: `static/gpt-chat.html:79,108,118,157-171`

**Interfaces:**
- Consumes: 现有共享组件类和 `studio-theme-dark` / `theme-dark` 类。
- Produces: `theme.css` 的白天模式共享变量与组件覆盖、首页外壳变量、对话页 `--chat-*` 变量。

- [ ] **Step 1: 增加失败的共享页面测试**

在测试类中加入：

```python
    def test_shared_light_theme_is_component_scoped(self):
        theme = (ROOT / "static/css/theme.css").read_text(encoding="utf-8")
        lower = theme.lower()
        marker = "/* warm beige daylight theme */"
        self.assertIn(marker, lower)
        light_block = lower[lower.index(marker):]
        compact_block = compact(light_block)
        self.assertIn("html:not(.studio-theme-dark):not(.theme-dark)", compact_block)
        self.assertIn("--warm-page:#e0ddd4", compact_block)
        self.assertIn("--warm-card:#f3f0e9", compact_block)
        self.assertIn("--warm-strong:#625548", compact_block)
        self.assertNotRegex(light_block, r"(^|[\s,{>])(img|video)([\s,{.:>#]|$)")
        self.assertNotIn("filter:", light_block)

    def test_shell_and_chat_use_warm_beige_palette(self):
        self.assert_tokens("static/index.html", [
            "--bg:#e0ddd4",
            "--sidebar-bg:#e9e5dc",
            "--stage-bg:#efece5",
            "--border:#c5beb2",
            "--stage-border:#b0a89b",
            "--text:#3b3935",
            "--muted:#746f66",
            "--nav-hover-bg:#e5e0d7",
        ])
        self.assert_tokens("static/gpt-chat.html", [
            "--chat-bg:#e0ddd4",
            "--chat-panel:#f3f0e9",
            "--chat-panel-2:#efece5",
            "--chat-soft:#e5e0d7",
            "--chat-line:#c5beb2",
            "--chat-line-2:#b0a89b",
            "--chat-text:#3b3935",
            "--chat-muted:#746f66",
            "--chat-faint:#928a7e",
            "--chat-strong:#625548",
            "--chat-strong-text:#f7f4ee",
            "--chat-user-bg:#786b5c",
        ])

    def test_shell_and_chat_dark_palettes_remain_unchanged(self):
        self.assert_tokens("static/index.html", [
            "html.theme-dark,body.theme-dark{--bg:#0f141d",
            "--stage-bg:#111722",
        ])
        self.assert_tokens("static/gpt-chat.html", [
            "--chat-bg:#0f141d",
            "--chat-panel:#171d29",
            "--chat-user-bg:#2f3b52",
        ])
```

- [ ] **Step 2: 运行测试并确认共享页面断言失败**

Run:

```powershell
python\python.exe -m unittest discover -s tests -p "test_warm_beige_light_theme.py" -v
```

Expected: 新增的共享主题、首页和对话页测试失败。

- [ ] **Step 3: 在 `theme.css` 文件末尾加入白天模式共享变量**

追加以下变量块：

```css
/* Warm beige daylight theme */
html:not(.studio-theme-dark):not(.theme-dark) {
    --warm-page:#e0ddd4;
    --warm-sidebar:#e9e5dc;
    --warm-panel:#efece5;
    --warm-card:#f3f0e9;
    --warm-soft:#e5e0d7;
    --warm-line:#c5beb2;
    --warm-line-strong:#b0a89b;
    --warm-text:#3b3935;
    --warm-muted:#746f66;
    --warm-faint:#928a7e;
    --warm-accent:#786b5c;
    --warm-strong:#625548;
    --warm-strong-text:#f7f4ee;
    --warm-shadow:rgba(73,64,54,.10);
    --bg:#e0ddd4;
    --bg-base:#e0ddd4;
    --page:#e0ddd4;
    --panel:#efece5;
    --card:#f3f0e9;
    --card-solid:#f3f0e9;
    --soft:#e5e0d7;
    --soft-2:#d8d2c8;
    --line:#c5beb2;
    --line-2:#b0a89b;
    --text:#3b3935;
    --text-main:#3b3935;
    --muted:#746f66;
    --faint:#928a7e;
    --accent:#786b5c;
    --strong:#625548;
    --strong-text:#f7f4ee;
    --shadow:rgba(73,64,54,.10);
}
```

- [ ] **Step 4: 在同一白天主题标记后加入组件级覆盖**

加入应用外壳、卡片、次级表面、输入控件和主按钮覆盖：

```css
html:not(.studio-theme-dark):not(.theme-dark) body {
    background:var(--warm-page) !important;
    color:var(--warm-text);
}

html:not(.studio-theme-dark):not(.theme-dark) body .app-shell,
html:not(.studio-theme-dark):not(.theme-dark) body .stage,
html:not(.studio-theme-dark):not(.theme-dark) body .shell {
    background-color:var(--warm-page);
    border-color:var(--warm-line);
}

html:not(.studio-theme-dark):not(.theme-dark) body .console-card,
html:not(.studio-theme-dark):not(.theme-dark) body .nano-input,
html:not(.studio-theme-dark):not(.theme-dark) body .upload-item,
html:not(.studio-theme-dark):not(.theme-dark) body .result-frame,
html:not(.studio-theme-dark):not(.theme-dark) body .masonry-item,
html:not(.studio-theme-dark):not(.theme-dark) body .engine-panel,
html:not(.studio-theme-dark):not(.theme-dark) body .tool-panel,
html:not(.studio-theme-dark):not(.theme-dark) body .control-panel,
html:not(.studio-theme-dark):not(.theme-dark) body .composer,
html:not(.studio-theme-dark):not(.theme-dark) body .history-popover,
html:not(.studio-theme-dark):not(.theme-dark) body .model-panel,
html:not(.studio-theme-dark):not(.theme-dark) body .gate-panel,
html:not(.studio-theme-dark):not(.theme-dark) body .bg-white {
    background-color:var(--warm-card) !important;
    border-color:var(--warm-line) !important;
    color:var(--warm-text) !important;
}

html:not(.studio-theme-dark):not(.theme-dark) body .bg-gray-50,
html:not(.studio-theme-dark):not(.theme-dark) body .bg-slate-50,
html:not(.studio-theme-dark):not(.theme-dark) body .bg-gray-100,
html:not(.studio-theme-dark):not(.theme-dark) body .bg-slate-100,
html:not(.studio-theme-dark):not(.theme-dark) body .engine-switch,
html:not(.studio-theme-dark):not(.theme-dark) body .model-pill,
html:not(.studio-theme-dark):not(.theme-dark) body .ratio-grid,
html:not(.studio-theme-dark):not(.theme-dark) body .resolution-toggle,
html:not(.studio-theme-dark):not(.theme-dark) body .mode-switch,
html:not(.studio-theme-dark):not(.theme-dark) body .mini-ratio {
    background-color:var(--warm-soft) !important;
    border-color:var(--warm-line) !important;
}

html:not(.studio-theme-dark):not(.theme-dark) body input,
html:not(.studio-theme-dark):not(.theme-dark) body textarea,
html:not(.studio-theme-dark):not(.theme-dark) body select {
    background-color:var(--warm-card);
    border-color:var(--warm-line);
    color:var(--warm-text);
}

html:not(.studio-theme-dark):not(.theme-dark) body .glass-btn,
html:not(.studio-theme-dark):not(.theme-dark) body .btn-action-dark,
html:not(.studio-theme-dark):not(.theme-dark) body .send-btn,
html:not(.studio-theme-dark):not(.theme-dark) body .gen-btn,
html:not(.studio-theme-dark):not(.theme-dark) body .comfy-run,
html:not(.studio-theme-dark):not(.theme-dark) body .llm-run,
html:not(.studio-theme-dark):not(.theme-dark) body .primary-btn,
html:not(.studio-theme-dark):not(.theme-dark) body .bg-black {
    background-color:var(--warm-strong) !important;
    border-color:var(--warm-strong) !important;
    color:var(--warm-strong-text) !important;
}
```

不要在该标记之后添加媒体选择器或 `filter` 属性。

- [ ] **Step 5: 更新首页外壳白天模式变量**

将 `static/index.html` 的白天 `:root` 变量改为：

```css
--accent:#625548;
--bg:#e0ddd4;
--sidebar-bg:#e9e5dc;
--stage-bg:#efece5;
--border:#c5beb2;
--stage-border:#b0a89b;
--text:#3b3935;
--muted:#746f66;
--nav-hover-bg:#e5e0d7;
--monitor-bg:rgba(243,240,233,.78);
--monitor-border:rgba(98,85,72,.10);
--monitor-shadow:rgba(73,64,54,.10);
--divider:rgba(98,85,72,.18);
--scrollbar:#b8b0a4;
--scrollbar-hover:#9f9689;
--author-name:#3b3935;
--social-icon:#928a7e;
```

不修改 `html.theme-dark, body.theme-dark` 变量块。

- [ ] **Step 6: 更新 GPT 对话页白天变量和半透明表面**

白天 `--chat-*` 使用：

```css
--chat-bg:#e0ddd4;
--chat-panel:#f3f0e9;
--chat-panel-2:#efece5;
--chat-soft:#e5e0d7;
--chat-line:#c5beb2;
--chat-line-2:#b0a89b;
--chat-text:#3b3935;
--chat-muted:#746f66;
--chat-faint:#928a7e;
--chat-strong:#625548;
--chat-strong-text:#f7f4ee;
--chat-strong-hover:#786b5c;
--chat-active-bg:#ddd7cd;
--chat-active-text:#3b3935;
--chat-active-border:#c5beb2;
--chat-user-bg:#786b5c;
--chat-user-text:#f7f4ee;
--chat-shadow:rgba(73,64,54,.10);
```

同时执行以下白天表面替换，深色覆盖保持原文：

```css
rgba(248,250,252,.97) -> rgba(243,240,233,.97)
rgba(238,242,246,.72) -> rgba(224,221,212,.72)
rgba(238,242,246,0)   -> rgba(224,221,212,0)
rgba(248,250,252,.94) -> rgba(243,240,233,.94)
rgba(248,250,252,.86) -> rgba(243,240,233,.86)
```

- [ ] **Step 7: 运行测试并确认通过**

Run:

```powershell
python\python.exe -m unittest discover -s tests -p "test_warm_beige_light_theme.py" -v
```

Expected: 7 tests passed。

- [ ] **Step 8: 提交共享页面主题**

```powershell
git add tests/test_warm_beige_light_theme.py static/css/theme.css static/index.html static/gpt-chat.html
git commit -m "style: extend warm beige theme across studio"
```

---

### Task 4: CSS 缓存版本

**Files:**
- Modify: `tests/test_warm_beige_light_theme.py`
- Modify: `static/smart-canvas.html`
- Modify: `static/canvas.html`
- Modify: `static/canvas-list.html`
- Modify: `static/api-settings.html`
- Modify: `static/asset-manager.html`
- Modify: `static/comfyui-settings.html`
- Modify: `static/angle.html`
- Modify: `static/enhance.html`
- Modify: `static/gpt-chat.html`
- Modify: `static/klein.html`
- Modify: `static/online.html`
- Modify: `static/zimage.html`

**Interfaces:**
- Consumes: Tasks 1-3 修改的 CSS 文件。
- Produces: 所有引用页面统一使用 `2026.07.29.warm1`，确保普通刷新加载新样式。

- [ ] **Step 1: 增加失败的缓存版本测试**

在测试类中加入：

```python
    def test_warm_theme_stylesheet_versions_are_bumped(self):
        version = "2026.07.29.warm1"
        expected = {
            "static/smart-canvas.html": ["smart-canvas.css"],
            "static/canvas.html": ["canvas.css", "theme.css"],
            "static/canvas-list.html": ["canvas-list.css", "theme.css"],
            "static/api-settings.html": ["api-settings.css", "theme.css"],
            "static/asset-manager.html": ["asset-manager.css", "theme.css"],
            "static/comfyui-settings.html": ["comfyui-settings.css", "theme.css"],
            "static/angle.html": ["theme.css"],
            "static/enhance.html": ["theme.css"],
            "static/gpt-chat.html": ["theme.css"],
            "static/klein.html": ["theme.css"],
            "static/online.html": ["theme.css"],
            "static/zimage.html": ["theme.css"],
        }
        for relative, stylesheets in expected.items():
            source = (ROOT / relative).read_text(encoding="utf-8")
            for stylesheet in stylesheets:
                self.assertIn(
                    f"/static/css/{stylesheet}?v={version}",
                    source,
                    f"{relative} did not bump {stylesheet}",
                )
```

- [ ] **Step 2: 运行缓存版本测试并确认失败**

Run:

```powershell
python\python.exe tests\test_warm_beige_light_theme.py WarmBeigeLightThemeTests.test_warm_theme_stylesheet_versions_are_bumped -v
```

Expected: FAIL，报告首个仍使用旧版本的样式链接。

- [ ] **Step 3: 更新所有受影响 CSS 查询版本**

只修改上面测试列出的 `<link rel="stylesheet">`，将查询参数统一改为：

```text
?v=2026.07.29.warm1
```

不要修改 JavaScript、字体或第三方库的版本。

- [ ] **Step 4: 运行主题测试和现有测试**

Run:

```powershell
python\python.exe -m unittest discover -s tests -p "test_warm_beige_light_theme.py" -v
python\python.exe -m unittest discover -s tests -v
```

Expected: 暖米灰主题测试全部通过；现有测试无新增失败。

- [ ] **Step 5: 提交缓存版本**

```powershell
git add tests/test_warm_beige_light_theme.py static/smart-canvas.html static/canvas.html static/canvas-list.html static/api-settings.html static/asset-manager.html static/comfyui-settings.html static/angle.html static/enhance.html static/gpt-chat.html static/klein.html static/online.html static/zimage.html
git commit -m "chore: refresh warm theme stylesheet cache"
```

---

### Task 5: 浏览器视觉和主题切换验证

**Files:**
- Read: `static/css/*.css`
- Read: `static/*.html`
- Create outside repository: task `outputs/暖米灰白天模式-智能画布.png`
- Create outside repository: task `outputs/暖米灰白天模式-普通画布.png`
- Create outside repository: task `outputs/暖米灰白天模式-API设置.png`

**Interfaces:**
- Consumes: Tasks 1-4 的最终页面和 CSS。
- Produces: 可审阅截图、计算样式结果和深色模式无回归结论。

- [ ] **Step 1: 确认服务可访问**

Run:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:3000/" -UseBasicParsing -TimeoutSec 5
```

Expected: HTTP 200。若服务未运行，使用 `E:\InfiniteCanvas\run.bat` 启动后重试。

- [ ] **Step 2: 验证智能画布白天模式**

打开：

```text
http://127.0.0.1:3000/static/smart-canvas.html?id=117acd358c4c44c5a6787c945a6505a7&v=2026.07.29.warm1
```

通过可见主题按钮切换到白天模式并普通刷新。读取计算样式并确认：

```text
.shell background-color = rgb(224, 221, 212)
第一张可见 img 的 filter = none
```

保存当前视口截图为 `outputs/暖米灰白天模式-智能画布.png`。

- [ ] **Step 3: 验证普通画布和设置页**

依次打开并检查：

```text
http://127.0.0.1:3000/static/canvas.html?id=117acd358c4c44c5a6787c945a6505a7
http://127.0.0.1:3000/static/api-settings.html
http://127.0.0.1:3000/static/asset-manager.html
http://127.0.0.1:3000/static/canvas-list.html
```

确认大面积背景为暖米灰、卡片比背景亮一个层级、主按钮为暖深灰棕、错误和成功提示仍保留语义色。保存普通画布和 API 设置截图。

- [ ] **Step 4: 验证深色模式无回归**

在智能画布和 API 设置页切换到深色模式，普通刷新后确认：

```text
智能画布 .shell background-color = rgb(15, 20, 29)
API 设置 body background-color = rgb(17, 22, 29)
```

再切回白天模式，避免改变用户最终偏好。

- [ ] **Step 5: 检查控制台和最终差异**

确认浏览器控制台没有新增 CSS/JavaScript 错误，然后运行：

```powershell
git diff --check
git status --short
git diff -- static/css static/*.html tests/test_warm_beige_light_theme.py
```

Expected: 无空白错误；差异仅包含主题、缓存版本和测试。

---

### Task 6: 增量替换包

**Files:**
- Create outside repository: `E:\codex\InfiniteCanvas-暖米灰白天模式-增量替换包-20260729.zip`
- Create outside repository: `E:\codex\InfiniteCanvas-暖米灰白天模式-替换说明.txt`
- Create outside repository: `E:\codex\InfiniteCanvas-暖米灰白天模式-文件清单-SHA256.txt`
- Copy outside repository: 三张验证截图

**Interfaces:**
- Consumes: 已验证的最终主题文件。
- Produces: 可在其他部署电脑上按相对路径覆盖的增量包和校验清单。

- [ ] **Step 1: 建立独立暂存目录**

在任务工作目录创建 `work/warm-beige-theme-package/InfiniteCanvas`，保持项目相对路径复制以下文件：

```text
static/css/smart-canvas.css
static/css/canvas.css
static/css/canvas-list.css
static/css/asset-manager.css
static/css/api-settings.css
static/css/comfyui-settings.css
static/css/theme.css
static/smart-canvas.html
static/canvas.html
static/canvas-list.html
static/api-settings.html
static/asset-manager.html
static/comfyui-settings.html
static/angle.html
static/enhance.html
static/gpt-chat.html
static/klein.html
static/online.html
static/zimage.html
static/index.html
```

- [ ] **Step 2: 写入替换说明**

说明文件包含以下内容：

```text
InfiniteCanvas 暖米灰白天模式增量替换说明

1. 关闭 InfiniteCanvas 服务。
2. 备份目标电脑原安装目录中的 static 文件夹。
3. 打开压缩包内 InfiniteCanvas 文件夹。
4. 将其中的 static 文件夹复制到目标电脑的 InfiniteCanvas 安装目录。
5. Windows 提示同名文件时选择“替换目标中的文件”。
6. 重新运行 run.bat。
7. 浏览器普通刷新；若仍显示旧颜色，按 Ctrl+F5 强制刷新一次。

本包只修改白天模式配色和 CSS 缓存版本，不包含 API Key、个人画布、素材、历史记录或 MediaKit 设置。
深色模式、Seedance 2.0、480P 和画质增强功能保持不变。
```

- [ ] **Step 3: 生成 SHA256 清单和 ZIP**

使用 PowerShell 对暂存目录中的每个文件生成相对路径、字节数和 SHA256，然后执行：

```powershell
Compress-Archive -LiteralPath "work\warm-beige-theme-package\InfiniteCanvas" -DestinationPath "outputs\InfiniteCanvas-暖米灰白天模式-增量替换包-20260729.zip"
Get-FileHash -Algorithm SHA256 "outputs\InfiniteCanvas-暖米灰白天模式-增量替换包-20260729.zip"
```

- [ ] **Step 4: 验证增量包内容**

解压到新的临时目录并确认：

```text
ZIP 内不存在 API/.env
ZIP 内不存在 data/
ZIP 内不存在 assets/
ZIP 内不存在 history.json
ZIP 内只包含清单中的 static 文件和替换说明
```

对解压后的文件重新计算 SHA256，结果必须与清单一致。

- [ ] **Step 5: 复制最终产物到 `E:\codex`**

复制 ZIP、替换说明、SHA256 清单和三张验证截图到 `E:\codex`，同时在当前任务 `outputs` 保留可点击副本。

- [ ] **Step 6: 最终报告**

报告：

```text
代码提交号
主题自动化测试结果
完整测试结果
浏览器验证页面和结果
增量 ZIP 路径、大小和 SHA256
其他电脑替换步骤
```
