# InfiniteCanvas 干净 Windows 便携完整版设计

## 目标

制作一个可部署到其他 Windows 64 位电脑的 InfiniteCanvas 完整便携包。目标电脑不需要预先安装 Python；解压后运行 `run.bat` 即可启动。

部署包包含当前已完成的 Seedance 2.0 480P、AI MediaKit 画质增强、智能画布和普通画布修改，但不携带当前电脑的 API Key、个人画布、生成素材和任务历史。

## 产物

- 文件夹：`InfiniteCanvas-Windows便携完整版-20260729`
- 压缩包：`InfiniteCanvas-Windows便携完整版-20260729.zip`
- 中文部署说明：`部署说明.txt`
- 文件清单：`文件清单-SHA256.txt`
- ZIP SHA256：在交付消息和部署说明中提供

## 目标环境

- Windows 10 或 Windows 11
- 64 位系统
- 默认监听 `http://127.0.0.1:3000/`
- 使用包内 Python 3.10.11 64 位运行时

本包不是 macOS 或 Linux 的免安装运行包；其中的源码仍可供其他系统自行安装依赖使用。

## 包含内容

### 程序与前端

- `main.py`
- `static/`
- `workflows/`
- `tools/`
- `CLI/`
- `requirements.txt`
- `VERSION`
- `LICENSE`
- 项目说明和运行说明
- Windows、macOS 现有辅助脚本

### 便携运行环境

- `python/` 内置 Windows 64 位 Python 3.10.11 运行时及已安装依赖
- `packages/` 离线安装包
- `get-pip.py`

### 安全的平台配置

- `data/api_providers.json`

该文件保留当前平台名称、协议、Base URL 和模型列表，包括已配置的 Seedance 2.0 平台，但不含 API Key、Token、密码或 Secret。

### 验证文件

- `tests/`
- 新增中文部署说明
- 生成每个文件的相对路径、大小和 SHA256 清单

## 排除内容

### 密钥与本机设置

- `API/.env`
- 所有 `.env` 文件
- API Key、Token、Secret、密码
- `data/mediakit_settings.json`
- `data/storage_settings.json`
- `global_config.json`

### 个人内容和运行状态

- `assets/` 中现有文件
- `output/` 中现有文件
- `data/canvases/`
- `data/conversations/`
- `data/media_previews/`
- `data/asset_library.json`
- `data/prompt_libraries.json`
- `data/projects.json`
- `data/mediakit_tasks.json`
- `data/runninghub_workflows.json`
- `data/shared_folders.json`
- `history.json`

### 开发和无效本机文件

- `.git/`
- `__pycache__/`
- `*.pyc`
- 日志、临时文件和缓存
- 指向当前电脑路径的 `.lnk` 快捷方式

## 首次运行行为

部署包保留空的 `API`、`assets`、`output` 和 `data` 运行目录结构。应用首次启动时创建缺失的画布、素材、历史、预览和默认资源库数据。

目标电脑需要：

1. 解压到任意可写目录，例如 `D:\InfiniteCanvas`。
2. 运行 `run.bat`。
3. 打开“API 设置”，为该电脑单独填写各平台 API Key。
4. 在 AI MediaKit 设置中填写 Key，并设置该电脑的保存位置。

程序使用 `%~dp0` 和 `main.py` 所在目录解析路径，不依赖原电脑的 `E:\InfiniteCanvas`。

## 安全控制

打包前和压缩后均执行以下检查：

1. ZIP 中不存在 `.env`、`history.json` 和被排除的个人数据文件。
2. JSON 配置中不存在名为 API Key、Token、Secret 或 Password 的字段值。
3. 部署说明不包含真实 Key。
4. 解压后的文件哈希与打包源目录一致。

## 验证

1. 包内 `python\python.exe --version` 返回 Python 3.10.11。
2. 包内 Python 能导入 FastAPI、Uvicorn、HTTPX、Pydantic、Pillow 等运行依赖。
3. JavaScript 语法检查通过。
4. 包内自动测试通过。
5. 在独立解压验证目录运行 `python\python.exe main.py`。
6. `http://127.0.0.1:3000/` 返回 HTTP 200。
7. 智能画布脚本包含 Seedance 2.0 480P 兼容和 MediaKit 画质增强功能。
8. 停止验证服务后，确认未修改最终 ZIP。

## 回滚

便携包不会覆盖目标电脑数据，除非用户把文件复制进现有安装目录。推荐解压到新目录并先验证；如需回滚，关闭服务后删除新目录即可。

