# Infinite Canvas 变更记录索引

在开始修改或故障排查前，先按关键词找到相关记录，不需要一次读取全部历史。

| ID | 日期 | 状态 | 主题 | 实施提交 | 关键词 |
| --- | --- | --- | --- | --- | --- |
| [IC-20260909-00](2026/2026-09-09-github-baseline-and-upload.md) | 2026-09-09 | 已完成 | 初始版 GitHub 存档、Deploy Key 和安全上传 Skill | `25d83e13fb5f6fc344cf3573566d0171b268e94c` | Git, GitHub, baseline, tag, Deploy Key, GCM, SSH 443, upload skill |
| [IC-20260909-01](2026/2026-09-09-nanobanana2-color-api-logging.md) | 2026-09-09 | 已发布 | Nano Banana 2 颜色保护、详细 API Trace、内存和终端日志优化 | `0dbf2e3e2744d25deb8b08971b504387393aa507` | 发粉, gemini-3.1-flash-image, colorfix, SQLite, Trace ID, API 详情, 500MB, 脱敏, 轮询降噪 |
| [IC-20260910-00](2026/2026-09-10-maintenance-ledger-and-skill.md) | 2026-09-10 | 已验证 | 持久维护制度、历史补录与 Infinite Canvas 维护 Skill | `c5e48696cc1628febe168418267efd884bf4f3b9` | AGENTS.md, change record, ADR, changelog, context window, maintenance skill, dirty worktree |
| [IC-20260910-01](2026/2026-09-10-classic-output-result-regression.md) | 2026-09-10 | 已验证 | 传统画布 API 生成成功但 OUTPUT 节点空白的回归修复 | `cf50ac4dfca7df9f921c36236d48d8d8829e97c4` | OUTPUT 空白, resultMediaUrls, image_items, Nano Banana 2, 传统画布, Trace ID, 回归测试 |

## 编号规则

- 格式：`IC-YYYYMMDD-NN`。
- 同一日从 `00` 递增。
- 文件名使用 `YYYY-MM-DD-short-topic.md`。
- 新记录必须同时加入本索引，关键词覆盖用户可见症状、模型名、端点和关键文件。
