# InfiniteCanvas 干净 Windows 便携完整版实施计划

1. 创建全新的 `InfiniteCanvas-Windows便携完整版-20260729` 目录，若同名目录已存在则停止，避免覆盖旧产物。
2. 复制程序、静态资源、工作流、CLI、工具、测试、内置 Python 3.10.11 和离线依赖包。
3. 只复制安全的平台配置 `data/api_providers.json`，建立空的 API、素材、输出和运行数据目录。
4. 排除 `.git`、所有 `.env`、个人画布、素材、生成结果、预览、任务记录、历史、缓存、快捷方式、`__pycache__` 和 `*.pyc`。
5. 使用 `apply_patch` 添加中文 `部署说明.txt`。
6. 校验包内 Python 版本和依赖导入，执行 JavaScript 语法检查。
7. 扫描文件路径、JSON 字段和当前 `API/.env` 中的非空密钥值，确保部署包无密钥命中。
8. 生成相对路径、文件大小和 SHA256 清单，再生成 ZIP。
9. 将 ZIP 解压到独立验证目录，逐文件比较哈希并再次检查排除项。
10. 在验证目录执行自动测试，启动 `python\python.exe main.py`，确认首页 HTTP 200 后停止验证服务。
11. 确认验证过程未修改最终 ZIP，输出 ZIP 大小、SHA256 和部署步骤。

