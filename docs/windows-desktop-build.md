# Windows 桌面版构建与发布

## 环境要求

- Windows 10/11 64 位
- Python 3.10 或更高版本
- Inno Setup 6
- Microsoft Edge WebView2 Runtime（用于运行桌面窗口）

建议在独立虚拟环境中安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-desktop.txt
```

构建脚本会依次运行测试、生成图标、执行 PyInstaller、扫描发布目录，并调用 Inno
Setup 生成安装包。脚本只收录明确允许的程序资源，不收录 `.env`、用户数据目录、
日志或构建机上的运行状态。

## 本地构建

如果 Python 或 Inno Setup 不在默认位置，先设置构建变量：

```powershell
$env:INFINITE_CANVAS_PYTHON = "C:\path\to\python.exe"
$env:INNO_SETUP_ISCC = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

执行完整构建：

```powershell
.\build\windows\build_release.ps1
```

要额外用本机开发配置中的非空值检查是否误打包密钥，可传入配置文件。扫描器只比较
值，不会在输出中打印密钥：

```powershell
.\build\windows\build_release.ps1 -SecretFile "C:\path\to\API\.env"
```

输出文件：

- `dist\InfiniteCanvas\`：PyInstaller 目录版应用
- `dist\installer\InfiniteCanvas-Setup-<版本>.exe`：安装包
- `dist\installer\SHA256SUMS.txt`：安装包 SHA256
- `dist\release-manifest.json`：应用目录文件清单和哈希

## 发布新版本

1. 修改代码并补充相应测试。
2. 将 `VERSION` 改为更高的三段式版本号，例如 `2026.08.05`。
3. 运行完整构建，并确认测试和敏感信息扫描全部通过。
4. 安装并启动新包，检查主界面、关键功能、窗口关闭和进程退出。
5. 提交并推送源代码，创建与版本一致的 Git 标签和 GitHub Release。
6. 上传安装包及 `SHA256SUMS.txt`，在发布说明中列出变更和已知限制。

安装程序的 `AppId` 必须保持不变。用户运行更高版本的安装包时，程序文件会被覆盖，
而 `%LOCALAPPDATA%\InfiniteCanvas` 中的 API 配置、画布、素材、历史记录和日志不会被
删除。不要在安装脚本中添加针对该用户数据目录的卸载删除规则。

## 运行结构

- `desktop_app.py` 在进程内启动 Uvicorn，并只绑定动态 `127.0.0.1` 端口。
- PyWebView 使用 Edge Chromium 创建原生窗口，不打开默认浏览器。
- `console=False` 隐藏控制台窗口。
- 打包资源为只读；可写状态统一位于 `%LOCALAPPDATA%\InfiniteCanvas`。
- 卸载程序只移除安装目录和快捷方式，保留用户数据以支持重装和手动升级。

## 上游与许可

桌面版基于 `https://github.com/hero8152/Infinite-Canvas.git`。发布派生版本时必须保留
原作者署名、仓库来源和 `LICENSE`，继续公开源代码，并遵守禁止未经授权商业封装的
条款。
