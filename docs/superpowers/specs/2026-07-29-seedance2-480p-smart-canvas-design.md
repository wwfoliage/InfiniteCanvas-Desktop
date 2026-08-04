# Seedance 2.0 智能画布 480p 选项设计

## 目标

在智能画布的视频分辨率控件中，当火山引擎直连或 API 生成使用 Seedance 2.0/2.0 Fast 时显示 `480p`，并排除会将 480p 强制转换为 720p 的 API 后端。

## 设计

- 保留当前通用选项：自动、720p、1080p、4K。
- 在渲染视频分辨率控件时，根据 `settings.engine`、`settings.videoProvider`、提供商协议/Base URL 和 `settings.videoModel` 判断当前路径是否真正支持 Seedance 2.0 的 480p。
- 支持火山引擎直连，以及 API 生成中的标准/OpenAI 兼容与 APIMart Seedance 2.0 路径。
- 排除即梦和土豆 API；这两条后端路径不接受 480p，当前实现会将它归一化为 720p。
- 命中时在自动与 720p 之间插入 `480p`；未命中时保持原选项不变。
- 使用现有后端的 `480p` 归一化或透传逻辑，不修改接口请求结构。

## 数据流

用户选择 480p → `settings.videoResolution` 保存 `480p` → 智能画布请求体的 `resolution` 字段传入 `/api/canvas-video` → 对应的火山直连或 API 请求体透传 `480p`。

## 边界与兼容性

- 仅影响火山引擎直连或受支持 API 路径中的 Seedance 2.0/2.0 Fast 选项展示。
- 识别模型名中的点号、下划线和连字符差异，例如 `doubao-seedance-2-0-*`、`doubao-seedance-2.0` 和 `seedance-2.0-global/*`。
- 即梦和土豆 API 不显示 480p。
- 其他不受支持的平台路径和非 Seedance 2.0 模型不新增 480p，现有选择与默认行为保持不变。
- 若从 Seedance 2.0 切换到其他模型时已选择 480p，前端应回退到自动，防止隐藏值继续提交。

## 验证

- 火山方舟 Seedance 2.0 与 Seedance 2.0 Fast 显示 480p。
- API 生成中的 Seedance 2.0 与 Seedance 2.0 Fast 显示 480p。
- 即梦和土豆 API 的 Seedance 2.0 不显示 480p。
- 其他视频模型及不受支持的平台路径不显示 480p。
- 选择 480p 后请求体包含 `"resolution": "480p"`。
- 从 Seedance 2.0 切换到不支持的模型后，分辨率回退为自动。
- JavaScript 语法检查通过。
