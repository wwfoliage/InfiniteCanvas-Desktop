# MediaKit 画质增强计时徽标位置实施计划

1. 修改 `static/js/smart-canvas.js` 的 `runTimePillHtml(node)`，排除 `smart-video-enhance` 类型。
2. 更新 `static/smart-canvas.html` 中 `smart-canvas.js` 的缓存版本，确保浏览器加载新脚本。
3. 运行 JavaScript 语法检查和 MediaKit 自动测试。
4. 更新跨电脑替换包为 v4，并在说明中记录本次界面调整。
5. 校验 ZIP 文件清单和哈希值。

