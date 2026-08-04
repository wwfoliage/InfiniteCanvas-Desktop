# InfiniteCanvas 旧版数据迁移

迁移工具把旧项目的用户数据合并到已安装桌面版的数据目录。它不会修改旧项目，不会改变安装包或内置工作流，也不会复制旧 API 密钥和服务商配置。

## 默认位置

- 旧项目：`E:\InfiniteCanvas`
- 桌面版数据：`%LOCALAPPDATA%\InfiniteCanvas`
- 备份：`E:\codex\无限画布资料\迁移备份\<运行编号>`
- 报告：`E:\codex\无限画布资料\迁移记录\<运行编号>`

## 安全预检

先关闭 InfiniteCanvas。默认命令只读取源数据和桌面版数据，并生成脱敏报告，不修改桌面版数据：

```powershell
python tools\migrate_legacy_data.py
```

预检成功后检查最新 `migration-report.json` 中的计数、冲突和 ID 映射。报告只记录路径、计数和 SHA-256，不包含密钥或提示词正文。

## 正式迁移

确认预检结果后执行：

```powershell
python tools\migrate_legacy_data.py --apply
```

工具在正式写入前完整备份当前数据，在目标磁盘创建暂存副本，并只在暂存副本中合并。暂存校验通过后才切换目录，提交后还会再次检查 JSON、画布项目关联、素材引用、受保护配置哈希和工作流哈希。

提交后校验失败时，工具会恢复原目录，并把失败树保留为 `InfiniteCanvas-migration-failed-<运行编号>`。

## 独立验证

```powershell
python tools\migrate_legacy_data.py --validate-only
```

真实数据在迁移期间没有变化时，预期为 166 个素材文件、22 个画布、34 条历史、294 个媒体预览、3 个项目、旧版素材库 52 条登记资源、12 个提示词模板和 7 个工作流。

## 退出码

- `0`：预检、迁移或验证成功。
- `2`：数据或迁移规则校验失败。
- `3`：意外的文件系统或运行时错误。

## 手动恢复

自动回滚失败时，保持 InfiniteCanvas 关闭，把当前 `%LOCALAPPDATA%\InfiniteCanvas` 改名留存，然后将对应备份目录中的 `InfiniteCanvas` 文件夹复制回 `%LOCALAPPDATA%`。恢复后用 `backup-manifest.json` 核对相对路径、大小和 SHA-256。
