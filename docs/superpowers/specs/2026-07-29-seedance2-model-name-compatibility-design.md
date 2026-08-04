# Seedance 2.0 模型名兼容与 480P 显示设计

## 背景

智能画布已经具备 Seedance 2.0 的 480P 选项和请求透传逻辑，但当前模型识别只匹配带分隔符的 `seedance-2-0`。用户配置的 API 模型名为 `seedance2.0`，因此被误判为非 Seedance 2.0，分辨率菜单只显示自动、720P、1080P 和 4K。

## 目标

让智能画布可靠识别常见 Seedance 2.0 模型命名形式，并在受支持的 API 路径中显示 480P，同时不扩大到不支持 480P 的平台或非 Seedance 模型。

## 兼容范围

模型识别应覆盖：

- `seedance2.0`
- `seedance-2.0`
- `seedance_2.0`
- `seedance-2-0`
- `seedance_2_0`
- 带厂商或路径前缀的名称，例如 `doubao-seedance-2-0-260128`、`bytedance/seedance-2.0-global/...`
- 带版本后缀的名称，例如 Fast、VIP、Mini、Global 或日期后缀

识别时忽略大小写以及空格、点号、下划线、连字符和路径分隔符的差异，但要求核心版本是 `Seedance 2.0`，不能把其他视频模型识别为 Seedance 2.0。

## 方案

只扩展智能画布 `isSeedance2VideoModel(model)` 的模型名规范化判断：

1. 将输入转为小写并去除常见分隔符差异。
2. 判断规范化结果是否包含 Seedance 2.0 的核心标识。
3. 保留 `supportsSeedance2Video480p()` 的现有平台、协议和 Base URL 限制。

不在分辨率菜单中硬编码特定平台名称，也不为整个 API 平台无条件开启 480P。

## 数据流

受支持的 Seedance 2.0 模型被正确识别 → 分辨率菜单在“自动”和“720P”之间显示“480P” → 用户选择后 `settings.videoResolution` 保存 `480p` → `/api/canvas-video` 请求体继续发送 `"resolution": "480p"`。

## 保持不变

- 即梦和土豆 API 继续不显示 480P。
- 非 Seedance 2.0 模型不显示 480P。
- 从支持模型切换到不支持模型时，已选的 480P 继续回退为“自动”。
- 火山引擎直连、OpenAI 兼容和 APIMart 的现有请求结构不变。
- 普通画布和 MediaKit 画质增强节点不在本次修改范围内。

## 验证

1. 上述常见 Seedance 2.0 命名形式均被识别。
2. 当前 `seedance2.0` API 配置显示 480P。
3. Seedance 2.0 Fast 等后缀形式显示 480P。
4. 即梦、土豆和非 Seedance 模型仍不显示 480P。
5. 选择 480P 后请求体仍包含 `"resolution": "480p"`。
6. JavaScript 语法检查和现有自动测试通过。
7. 浏览器实际界面检查确认 480P 位于自动与 720P 之间。

