# Infinite Canvas 设计决策索引

| ADR | 状态 | 决策 | 关键词 |
| --- | --- | --- | --- |
| [ADR-0001](0001-opt-in-nanobanana2-color-protection.md) | 已接受 | API 生成颜色保护固定可用、默认关闭、保留原图并低置信度回退 | API 生成, 模型别名, colorfix, auto, strict, task mode, raw output |
| [ADR-0002](0002-bounded-disk-api-tracing.md) | 已接受 | 详细 API Trace 存 SQLite，画布与内存只保留有界摘要 | SQLite, Trace ID, 500MB, redaction, canvas logs |
| [ADR-0003](0003-repository-versioning-and-auth.md) | 已接受 | 使用可审计 Git 历史、基线标签和仓库专用 Deploy Key | Git, baseline tag, Deploy Key, SSH 443, no force push |
