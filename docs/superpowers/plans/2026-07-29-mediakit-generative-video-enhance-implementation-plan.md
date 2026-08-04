# AI MediaKit 生成式视频画质增强实施计划

> 设计依据：`docs/superpowers/specs/2026-07-29-mediakit-generative-video-enhance-smart-canvas-design.md`
>
> 实施目标：在智能画布和普通画布中增加原生风格的“MediaKit 画质增强”节点。节点只在用户点击“开始增强”后创建付费任务；成功结果保存到本地、进入素材库，并输出到一个新的结果节点。

## 1. 实施边界

本次实施包含：

- 火山引擎 AI MediaKit API Key 配置、脱敏显示和清除。
- 增强视频保存目录配置、目录校验和“打开文件夹”。
- 本地视频上传到 MediaKit、创建增强任务、查询任务、下载结果、保存失败重试。
- 智能画布 `smart-video-enhance` 节点及标准 `smart-image` 视频结果节点。
- 普通画布 `mediakitEnhance` 节点及标准 `Output` 视频结果节点。
- 720p / 1080p / 2K，低 / 中 / 高码率，可选 15–120 fps。
- 默认 720p、中码率、不传 fps（保持源帧率）。
- 明确可识别 HDR、尺寸和格式的本地预检。
- 页面刷新后的任务恢复、错误重试和幂等保护。
- 中英文文案、自动测试、手工回归和跨电脑替换包。

本次实施不包含：

- MediaKit 标准版增强、图片增强或其他 MediaKit 工具。
- 自动把 SDR 转成 HDR。
- 连接节点后自动发起付费任务。
- 把 API Key、任务记录或用户生成媒体放进分发包。
- 用真实付费任务作为自动化测试。

## 2. 官方接口契约

实施时以火山引擎官方文档为准：

- 生成式视频增强：<https://www.volcengine.com/docs/6448/2464595?lang=zh>
- 获取本地媒体上传地址：<https://www.volcengine.com/docs/6448/2536891?lang=zh>
- 查询任务：<https://www.volcengine.com/docs/6448/2536893?lang=zh>

固定请求流程：

1. 本地视频先请求 `POST /api/v1/tools-sync/request-media-upload-url`，请求体为 `{}`。
2. 使用响应提供的 `method`、`upload_url` 和全部 `upload_headers`，以原始二进制流执行 `PUT`；不使用 multipart。
3. 将响应中的 `file_id` 原样作为增强接口的 `video_url`。
4. 调用 `POST /api/v1/tools/enhance-video-generative`。
5. 使用返回的远程 `task_id` 查询 `GET /api/v1/tasks/{task_id}`。
6. 完成后立即下载临时结果，先写 `.part`，再原子替换为最终文件。

增强请求字段：

- `video_url`：必填。
- `resolution`：`720p`、`1080p`、`2k`；默认 `720p`。
- `bitrate_level`：`low`、`medium`、`high`；默认 `medium`。
- `fps`：15–120；保持源帧率时完全省略该字段。
- `client_token`：不超过 64 个可打印 ASCII 字符，用于幂等。

输入限制：

- 支持 `mp4`、`flv`、`ts`、`avi`、`mov`、`wmv`、`mkv`。
- 最大 1080p，短边 360–1080，长边 360–1920。
- 只支持 SDR。
- 本地上传最大 5 GB，不支持断点续传。

## 3. 数据和安全约定

### 3.1 密钥

- 环境变量名：`MEDIAKIT_API_KEY`。
- 存储文件：`API/.env`。
- 后端和前端响应只能返回 `configured` 与脱敏值，不返回明文。
- 日志、异常、任务 JSON 和浏览器持久化数据不得包含 Key 或 Authorization 头。

### 3.2 设置

保存到 `data/mediakit_settings.json`：

```json
{
  "output_mode": "generated",
  "custom_output_dir": ""
}
```

- `generated`：实际目录为当前生成目录下的 `mediakit-enhance`。
- `custom`：使用经过校验的绝对目录。
- API 设置页显示最终解析后的目录，但接口不向浏览器暴露不必要的内部路径。

### 3.3 任务

保存到 `data/mediakit_tasks.json`。每条记录至少包含：

- 本地任务 ID。
- 稳定的 `client_token`。
- 画布类型、画布 ID、增强节点 ID、结果节点 ID。
- 输入媒体引用和增强参数。
- 远程任务 ID。
- `uploading`、`submitted`、`processing`、`saving`、`succeeded`、`failed`、`save_failed` 状态。
- 本地结果 URL、远程临时 URL及其有效期信息。
- 用户可读错误和更新时间。

任务记录不得包含 API Key、Authorization、上传签名头或完整自定义目录。

## 4. 分步实施

### 任务 1：先建立后端设置与类型骨架

修改：

- `main.py`
- 新建 `tests/test_mediakit.py`

步骤：

1. 在测试中建立临时 `API/.env`、数据目录、生成目录和自定义目录。
2. 添加失败测试，覆盖：
   - 未配置 Key 时返回 `configured: false`。
   - 配置 Key 后只返回脱敏值。
   - 清除 Key 后环境变量被移除。
   - 默认目录解析为 `{generated}/mediakit-enhance`。
   - 自定义目录必须是绝对路径且可创建、可写。
   - 自定义目录非法时不覆盖上一次有效设置。
3. 在 `main.py` 增加：
   - `MEDIAKIT_BASE_URL`。
   - `MEDIAKIT_SETTINGS_FILE`、`MEDIAKIT_TASKS_FILE`。
   - MediaKit 设置默认值、规范化、读取、保存和目录解析函数。
   - `provider_key_env("mediakit") -> "MEDIAKIT_API_KEY"`。
4. 在 `SUPPORTED_PROVIDER_PROTOCOLS` 和默认 Provider 中加入固定 `mediakit` 项，协议设为 `mediakit`，无生成模型。
5. 修改 `merge_default_api_providers()`、Provider 规范化与主 Provider 选择逻辑，确保固定卡可保留，同时 `mediakit` 永远不会成为通用文生图/视频主 Provider。
6. 增加：
   - `GET /api/mediakit/settings`
   - `PATCH /api/mediakit/settings`
   - `POST /api/mediakit/open-output-dir`
7. `PATCH` 支持：
   - 设置新 Key。
   - Key 留空时保留现有值。
   - 显式 `clear_api_key: true` 时清除。
   - 修改输出模式和自定义目录。
8. 运行测试并确认设置文件使用原子写入。

验证：

```powershell
.\python\python.exe -m unittest tests.test_mediakit.MediaKitSettingsTests -v
```

建议提交：

```text
feat: add MediaKit settings backend
```

### 任务 2：实现输入检查、本地上传和远程任务提交

修改：

- `main.py`
- `tests/test_mediakit.py`

步骤：

1. 先添加参数和输入预检失败测试：
   - 非法分辨率、码率和 fps 被拒绝。
   - fps 为空时远程请求体没有 `fps` 字段。
   - fps 小于 15 或大于 120 被拒绝。
   - 不支持的本地扩展名、超过 5 GB、明确超尺寸被拒绝。
   - 明确 PQ、HLG 或 Dolby Vision 标记的文件被拒绝。
   - 未标注或无法判定色彩传递特性的文件允许继续，由 MediaKit 做最终校验。
2. 添加请求模型：
   - 输入媒体 URL、名称和可选浏览器元数据。
   - `resolution`、`bitrate_level`、可空 `fps`。
   - 画布和节点关联字段。
   - 前端生成或后端补全的 `client_token`。
3. 增加输入 URL 解析：
   - 使用现有 `local_media_path_from_url()` 安全解析本站本地媒体。
   - 外部 HTTP/HTTPS URL不在本地读取，但仍校验协议。
   - 拒绝目录穿越和无法确认来源的本地路径。
4. 增加不依赖 ffprobe 的“明确 HDR”扫描：
   - 对 MP4/MOV 的有限头尾区间检查 `nclx` 中 PQ/HLG 传递特性。
   - 检查 Dolby Vision 配置盒标记，如 `dvcC`、`dvvC`、`dvwC`。
   - 检测不到不等同于确认 SDR；错误文案应说明 MediaKit 仍会做最终验证。
5. 浏览器提供的 `videoWidth` / `videoHeight` 仅作快速预检；后端验证其范围和可信类型，不信任其他客户端声明。
6. 实现 MediaKit HTTP 客户端封装：
   - 所有请求使用 `Authorization: Bearer <key>`。
   - 设置连接、读取和整体超时。
   - 将上游错误转换为安全、可读的本地错误。
   - 不记录敏感请求头。
7. 本地文件提交时：
   - 请求上传 URL。
   - 保留服务端返回的全部上传头。
   - 按块流式执行原始二进制 `PUT`。
   - 使用返回的 `file_id` 提交增强任务。
8. 外部 HTTP/HTTPS 输入可直接提交，无需本地上传。
9. `client_token` 作为本地幂等索引：
   - 同一个 token 重试不能重复创建付费任务。
   - 用户明确再次点击“重新增强”时生成新 token。
10. 增加 `POST /api/mediakit/enhance-tasks`，在任何远程调用前先持久化本地记录。

验证：

```powershell
.\python\python.exe -m unittest tests.test_mediakit.MediaKitSubmitTests -v
```

自动测试只 mock HTTP，不调用真实 MediaKit。

建议提交：

```text
feat: submit MediaKit enhance tasks
```

### 任务 3：实现查询、结果保存、素材库登记和恢复

修改：

- `main.py`
- `tests/test_mediakit.py`

步骤：

1. 先添加失败测试，覆盖：
   - 查询中的任务状态正确映射。
   - 完成结果下载到 `.part` 后原子替换。
   - 多个前端轮询同一任务不会重复下载。
   - 下载失败进入 `save_failed`，保留远程结果 URL。
   - “重试保存”不重新创建增强任务。
   - 自定义目录结果可通过受限路由读取。
   - 路径穿越请求被拒绝。
   - 成功视频进入素材库的视频分类。
2. 增加任务文件锁和状态迁移保护：
   - 查询同一任务时串行更新。
   - `saving` 状态防止重复下载。
   - 写任务 JSON 使用临时文件和原子替换。
3. 增加 `GET /api/mediakit/enhance-tasks/{local_task_id}`：
   - 未完成时查询一次远程状态并持久化。
   - 完成时保存远程结果。
   - 返回统一的前端任务结构。
4. 增加 `POST /api/mediakit/enhance-tasks/{local_task_id}/retry-save`。
5. 增加安全结果 URL：
   - 默认生成目录内尽量复用现有 storage-files 路由。
   - 自定义目录使用 `GET /api/mediakit/files/{filename}`。
   - 路由必须把最终路径约束在当前已解析的 MediaKit 输出根目录内。
6. 输出文件名使用安全化源名称、时间或任务 ID，避免覆盖同名文件。
7. 素材库没有视频分类时创建 `mediakit-videos` 分类。
8. 复用素材库现有复制和广播机制登记结果；明确素材库会保留一份标准管理副本。
9. 返回结果至少包含：
   - `kind: "video"`
   - 本地可访问 URL
   - 文件名
   - 可用的尺寸、时长和缩略信息
   - 本地任务 ID

验证：

```powershell
.\python\python.exe -m unittest tests.test_mediakit.MediaKitTaskLifecycleTests -v
.\python\python.exe -m unittest tests.test_mediakit -v
```

建议提交：

```text
feat: persist MediaKit enhanced videos
```

### 任务 4：在 API 设置中加入固定 MediaKit 配置卡

修改：

- `static/api-settings.html`
- `static/js/api-settings.js`
- `static/css/api-settings.css`
- `static/js/i18n/api-settings.js`

步骤：

1. 在固定 Provider 判定中加入 `mediakit`，沿用火山引擎视觉标识并显示 `MediaKit` 标签。
2. 增加专用编辑区：
   - API Key 输入框。
   - 已配置状态和脱敏提示。
   - 保存 Key、清除 Key。
   - “跟随生成文件目录”开关，默认打开。
   - 自定义绝对目录输入框。
   - 已解析保存位置。
   - 保存设置和打开文件夹按钮。
3. MediaKit 卡不显示通用模型列表、主 Provider 开关或模型同步入口。
4. 加载卡片时调用 `GET /api/mediakit/settings`。
5. 保存时调用 `PATCH /api/mediakit/settings`；绝不把脱敏占位符写回 Key。
6. 服务器校验失败时保留用户输入并在卡内显示原生错误状态。
7. 为中文和英文补齐：
   - 服务名称。
   - Key 状态。
   - 输出目录模式。
   - 保存、清除、打开目录和错误文案。
8. 使用现有卡片、按钮、输入框和响应式断点，不引入新的视觉体系。

验证：

```powershell
node --check static/js/api-settings.js
```

手工检查：

- 刷新页面后只显示脱敏 Key。
- 空 Key 保存不会误清除。
- 清除按钮需要二次确认。
- 默认/自定义目录切换和打开目录有效。
- 小屏幕布局不横向溢出。

建议提交：

```text
feat: add MediaKit API settings card
```

### 任务 5：增加两套画布共用的浏览器端 MediaKit 客户端

新建：

- `static/js/mediakit-client.js`

修改：

- `static/canvas.html`
- `static/smart-canvas.html`

步骤：

1. 在两个画布主脚本之前加载 `mediakit-client.js`。
2. 暴露精简的 `window.MediaKitClient`：
   - 参数默认值与规范化。
   - 读取设置状态。
   - 创建任务。
   - 查询任务。
   - 重试保存。
   - 支持 AbortSignal 的轮询。
   - 安全错误文案归一化。
3. 增加浏览器视频元数据辅助函数：
   - 只读取浏览器可靠提供的宽高和时长。
   - 不伪造浏览器无法可靠提供的帧率或 HDR 信息。
4. 轮询采用有上限的递增间隔；页面隐藏时降低频率，恢复显示后继续。
5. 客户端不保存 API Key，不直接调用火山引擎域名。
6. 两套画布只复用通信和参数逻辑，各自保留原生节点 DOM 与状态管理。

验证：

```powershell
node --check static/js/mediakit-client.js
```

建议提交：

```text
feat: add shared MediaKit browser client
```

### 任务 6：实现智能画布增强节点和结果节点

修改：

- `static/smart-canvas.html`
- `static/js/smart-canvas.js`
- `static/css/smart-canvas.css`
- `static/js/i18n/smart-canvas.js`

步骤：

1. 增加节点类型 `smart-video-enhance`。
2. 在智能画布空白创建菜单加入“MediaKit 画质增强”。
3. 在视频 `smart-image` 节点工具栏加入“增强画质”动作：
   - 仅当节点媒体类型为视频时可用。
   - 创建增强节点并自动连接视频源。
4. 节点遵循智能画布原生结构：
   - 标题、输入缩略图、端口、运行状态和错误区域。
   - 720p / 1080p / 2K 分段选项。
   - 低 / 中 / 高码率分段选项。
   - “保持源帧率”默认开；关闭后显示 15–120 fps 输入。
   - 原生主按钮“开始增强”。
5. 连接本身只更新节点状态，不调用任务接口。
6. 点击开始时依次检查：
   - MediaKit Key 已配置。
   - 只有一个有效视频输入。
   - 参数有效。
   - 本地视频浏览器元数据没有明确超出输入范围。
7. 开始后立即创建一个标准 `smart-image` 结果节点：
   - `kind` 为视频。
   - 显示原生等待状态。
   - 从增强节点连接到结果节点。
   - 保存本地任务 ID、token 和关联节点 ID。
8. 轮询成功后把本地视频 URL 写入结果节点；失败保留结果节点并显示重试。
9. 区分两种重试：
   - 远程任务失败：用户再次增强时创建新 token。
   - 仅本地保存失败：调用 retry-save，不重复计费。
10. 扩展保存/加载与 `resumeSmartPendingTasks()`：
    - 刷新后根据本地任务 ID恢复轮询。
    - 已完成任务直接补回结果。
    - 删除增强或结果节点时停止对应浏览器轮询，但不删除后端任务或已保存文件。
11. 扩展连接规则：
    - 增强节点只接受能解析为视频的输入。
    - 结果仍使用标准视频节点，可继续连接已有视频消费者。
    - 保持现有循环检测。
12. 为节点补充中英文名称、帮助、参数、状态和错误文案。

验证：

```powershell
node --check static/js/smart-canvas.js
```

手工检查：

- 创建菜单与视频工具栏两种入口。
- 连线不发请求。
- 点击开始才出现结果节点并发起任务。
- 默认值正确。
- 断开输入、非法 fps、未配置 Key均在节点内提示。
- 刷新后继续显示进度。
- 成功结果可播放、可继续连线。

建议提交：

```text
feat: add MediaKit enhancement to smart canvas
```

### 任务 7：实现普通画布原生增强节点和级联执行

修改：

- `static/canvas.html`
- `static/js/canvas.js`
- `static/css/canvas.css`
- `static/js/i18n/canvas.js`

步骤：

1. 增加节点类型 `mediakitEnhance` 和工厂 `addMediaKitEnhanceNode()`。
2. 在普通画布空白创建菜单增加节点入口。
3. 在视频上传、视频生成器、视频 Output 的连线创建菜单增加增强节点。
4. 在视频生成器右键输出菜单增加“连接到 MediaKit 画质增强”。
5. 节点 UI严格复用普通画布：
   - `.node`、`.node-head`。
   - `.gen-settings`、`.gen-settings-row`。
   - 原生输入/输出端口。
   - 原生 `.gen-btn` 开始按钮。
   - 原生状态、错误和重试区域。
6. 参数、默认值和点击行为与智能画布一致。
7. 点击开始时创建标准 `Output` 节点并自动连接：
   - 先显示视频等待项。
   - 成功后替换为可播放的本地视频。
   - 保存 MediaKit 任务关联信息。
8. 将 `mediakitEnhance` 加入适当类型集合：
   - 作为视频处理生成节点。
   - 作为媒体输出源。
   - 不加入图片输出类型。
9. 在 `runCascadeNodeByType()` 和 `canvasRunTypes` 中增加分派，使以下链路可运行：

```text
视频生成 → MediaKit 画质增强 → Output
```

10. 收紧 `canConnect()` 对增强节点的规则：
    - 目标为增强节点时，来源必须声明或可解析为视频。
    - 增强节点输出可连接 Output 和已有视频消费者。
    - 在实际运行时再次检查来源是否确实包含视频。
    - 保留循环检测和现有合法连接。
11. 扩展 `mergeGeneratedOutputs()`、`generatedImageRefs()` 和 pending 输出恢复逻辑，使增强结果不会在重渲染或刷新时丢失。
12. 为 pending 数据增加 `canvasTaskType: "mediakit-enhance"` 与本地任务 ID。
13. 页面恢复时：
    - 查询未完成任务。
    - 补回完成结果。
    - 本地保存失败仅提供 retry-save。
14. 补充中英文节点名称、参数、状态、错误和菜单文案。

验证：

```powershell
node --check static/js/canvas.js
```

手工检查：

- 空白菜单创建。
- 从视频上传、视频生成器和视频 Output 自动创建并连线。
- 节点视觉与普通画布其他生成节点一致。
- 连线不发请求，点击按钮才执行。
- 级联执行只运行一次增强任务。
- 刷新后 pending 和成功视频不丢失。

建议提交：

```text
feat: add MediaKit enhancement to canvas
```

### 任务 8：整体验证与回归

修改：

- 只修复验证中发现的本功能问题。

自动验证：

```powershell
.\python\python.exe -m unittest tests.test_mediakit -v
.\python\python.exe -m unittest tests.test_canvas_log_cleanup -v
node --check static/js/mediakit-client.js
node --check static/js/api-settings.js
node --check static/js/smart-canvas.js
node --check static/js/canvas.js
git diff --check
```

安全检查：

```powershell
rg -n "MEDIAKIT_API_KEY|Authorization.*Bearer|api_key" data static tests main.py
```

逐项确认：

- 测试数据中只有假 Key。
- 前端文件、任务 JSON 和浏览器持久化状态没有真实 Key。
- 日志不包含签名上传 URL的敏感查询参数或上传头。
- `API/.env`、`data/mediakit_settings.json`、`data/mediakit_tasks.json` 不进入提交。
- 自定义文件路由无法读取目录外文件。
- 同一 `client_token` 不会重复提交。

手工端到端验证分两级：

1. 默认只使用 mock 后端或已有测试夹具，验证 UI、连线、刷新恢复和错误状态，不产生费用。
2. 只有用户明确提供可用 Key并同意付费验证时，才运行一条短 SDR 视频真实任务；记录任务 ID，不记录 Key。

回归范围：

- 普通画布现有图片/视频生成和 Output。
- 智能画布现有视频节点、工具栏、保存/加载。
- API 设置中的 ModelScope、RunningHub、火山引擎现有卡片。
- 自定义生成目录和素材库。

建议提交：

```text
test: cover MediaKit video enhancement
```

### 任务 9：生成其他电脑可用的替换包

输出到 Codex 交付目录，不写进项目仓库：

- `outputs/InfiniteCanvas-MediaKit画质增强-替换包/`
- `outputs/InfiniteCanvas-MediaKit画质增强-替换包.zip`

包内只包含本次实际修改或新增的程序文件，并保留项目相对目录，例如：

```text
main.py
static/
  api-settings.html
  canvas.html
  smart-canvas.html
  css/...
  js/...
tests/
  test_mediakit.py
README-替换说明.txt
```

`README-替换说明.txt` 写明：

1. 关闭 InfiniteCanvas。
2. 备份目标电脑原目录。
3. 将替换包内容复制到目标项目根目录，按相同相对路径覆盖。
4. 不覆盖目标电脑原有 `API/.env` 和 `data/` 用户数据。
5. 启动后进入 API 设置 → AI MediaKit，填写各电脑自己的 Key。
6. 选择默认或自定义保存位置并保存。
7. 用短 SDR 视频做一次测试。
8. 如需回滚，用第 2 步备份覆盖回来。

分发包明确排除：

- `API/.env`
- `data/mediakit_settings.json`
- `data/mediakit_tasks.json`
- `data/asset_library.json`
- `assets/`
- 用户画布、生成视频、缓存、日志
- Python 运行环境和依赖缓存

最终检查 ZIP中的路径、文件清单和说明文档，并给用户提供可点击下载链接。

## 5. 完成标准

满足以下全部条件才算实施完成：

- API 设置页可以安全配置 Key 和输出目录。
- 两套画布都有符合各自原生规则的增强节点。
- 连接节点不会产生费用；只有点击“开始增强”才提交。
- 默认参数为 720p、中码率、保持源帧率。
- 普通画布支持视频生成 → 增强 → Output 级联。
- 智能画布把成功视频放入新的标准视频结果节点。
- 成功结果本地保存并登记素材库。
- 页面刷新后任务可恢复，保存失败可无计费重试。
- 明确 HDR和超限输入在提交前被阻止，未知色彩信息交由 MediaKit 最终校验。
- 自动测试、JS 语法检查和回归检查通过。
- 没有提交或打包用户 Key、任务记录、媒体和无关工作区改动。
- 已生成带替换说明的跨电脑分发 ZIP。
