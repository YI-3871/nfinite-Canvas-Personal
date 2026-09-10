# IC-20260910-00 · 持久维护档案与 Infinite Canvas Skill

- 状态：已验证，本记录随所在提交发布
- 日期：2026-09-10
- 实施分支：`codex/maintenance-ledger`
- 维护制度实施提交：`c5e48696cc1628febe168418267efd884bf4f3b9`
- 本记录提交：使用 `git log -1 -- docs/change-records/2026/2026-09-10-maintenance-ledger-and-skill.md` 定位
- 基线提交：`0dbf2e3e2744d25deb8b08971b504387393aa507`
- 关联运行 Trace：`none`

## 用户需求

用户计划长期修改与优化画布，要求每次修改详细记录在案。发生问题时，后续 Codex 需要能查看历史修改并验证是否由某次改动引起。该方法不能依赖有限的聊天上下文。

用户同时要求首先把上次工作的全部信息补录。

## 验收标准

- [x] 仓库根目录有对后续 Codex 生效的强制维护规则。
- [x] 历史以短索引和独立记录分层，不需一次加载所有文档。
- [x] 有可复用的记录模板、故障排查流程和设计决策索引。
- [x] 补录 GitHub 初始存档、认证问题与安全上传方案。
- [x] 补录 Nano Banana 2 颜色保护、API Trace、资源上限、前端、接口、文件、测试、限制与回退信息。
- [x] 建立可自动触发的 `infinite-canvas-maintenance` Skill。
- [x] 不夹带任务开始前已存在的未提交文件或运行数据。

## 实施方案

### 仓库内持久记忆

- `AGENTS.md` 规定开始任务的读取顺序、工作树保护、分支、测试、记录、敏感信息和 Git 边界。
- `docs/change-records/INDEX.md` 只保留短索引，以用户症状、模型、端点、文件和功能为关键词。
- `docs/change-records/<year>/...` 一次变更一份文件，保存需求、原因、数据流、文件、接口、测试、限制、排查和回退。
- `docs/decisions/` 保存后续修改不应无意破坏的长期约束。
- `CHANGELOG.md` 保存用户可见版本摘要。
- `docs/maintenance-protocol.md` 解释新任务如何用少量相关文档、Git 和运行 Trace 恢复上下文。

### 补录的历史档案

- `IC-20260909-00`：初始仓库、Git 身份、基线提交/标签、GCM 登录故障、浏览器与 Git 凭据的区别、仓库专用 Deploy Key、SSH 443、凭据扫描、远程核对和 `github-safe-repo-upload` Skill。
- `IC-20260909-01`：颜色保护 UI 语义、自适应混合 D 算法、原图保留、低置信度回退、SQLite 表和上限、Trace 阶段、脱敏、日志 API/UI、内存边界、终端降噪、分块上传、24 个文件、11 项测试、未执行的付费 API 验证、已知限制和回退提交。

### 长期设计决策

- `ADR-0001`：颜色保护可选、原图保留、安全候选和 `scene_change` 边界。
- `ADR-0002`：详细 API Trace 写 SQLite，画布 JSON/内存只保留有界摘要，凭据与 Base64 不落盘。
- `ADR-0003`：可审计 Git 历史、初始版标签、`codex/` 分支、不强推和仓库专用 Deploy Key。

### 本机可复用 Skill

创建 `infinite-canvas-maintenance` Skill，存放在本机 Codex 的 Skills 目录。Skill 的核心流程：

1. 识别仓库和读取 `AGENTS.md`。
2. 从变更索引按需恢复历史，避免一次加载全部上下文。
3. 保护用户已有未提交变化。
4. 根据“诊断”或“修改”请求守住授权边界。
5. 使用分支、相关测试、精确暂存、实施提交与记录提交。
6. 发布时复用 `github-safe-repo-upload` Skill 中的仓库专用 Deploy Key 和远程核对流程。

Skill 的可选参考文件分为变更记录合同和故障/回归诊断流程，遵循按需加载。

## 本任务开始前已存在的本机改动

在创建维护分支前，工作树已存在下列未提交变化。它们被视为用户所有，本任务未编辑、未暂存、未提交、未删除：

- `.gitignore`
- `MAC-使用说明.md`
- `mac-启动服务.command`
- `mac-启动服务.sh`
- `main.py`
- `run.bat`
- `static/canvas.html`
- `static/index.html`
- `static/smart-canvas.html`
- `tools/chrome-local-asset-importer/README.md`
- `tools/chrome-local-asset-importer/popup.html`
- `tools/chrome-local-asset-importer/sidepanel.html`
- `tools/photoshop-asset-connector/README.md`
- `tools/photoshop-asset-connector/index.html`
- `tools/photoshop-asset-connector/js/app.js`
- `新手运行与使用教程.md`
- 未跟踪的 `data/projects.json`

这些文件不属于实施提交 `c5e4869...`。后续任务不得根据本记录假定它们的内容或用途，需要另行诊断或获得用户授权。

## 验证证据

| 验证 | 结果 | 备注 |
| --- | --- | --- |
| Skill 脚手架生成 | 通过 | 使用官方 `skill-creator` 初始化脚本 |
| Skill `quick_validate.py` | 通过 | Windows 下显式使用 UTF-8 |
| Skill TODO 扫描 | 通过 | 无模板 TODO 残留 |
| 文档 `git diff --check` | 通过 | 无行尾空格和多余 EOF 空行 |
| 暂存范围 | 通过 | 仅 `AGENTS.md`、`CHANGELOG.md` 和 `docs/` |
| 禁止路径检查 | 通过 | 暂存区不包含 `.env`、`data/`、`assets/`、`output/` |
| 凭据/私钥特征扫描 | 通过 | 暂存差异未发现 PAT、AWS Key 或私钥头 |
| 程序代码测试 | 不适用 | 本任务未修改画布运行代码 |

## 安全、隐私与资源影响

- 仓库内文档为静态 Markdown，不改变画布运行时性能、内存或磁盘用量。
- 不包含 API Key、Token、Cookie、私钥内容、用户图片或 API 响应体。
- 本机 Skill 不包含凭据，只记录安全流程。
- 仓库的短索引与分年单文件设计避免后续任务一次读取无界增长的历史。

## 已知限制

- `infinite-canvas-maintenance` 是本机个人 Skill，不会随 GitHub 仓库自动安装到其他人的 Codex。
- 仓库内 `AGENTS.md`、索引、记录、ADR 和 Changelog 会随 Git 传播，因此即使没有本机 Skill，其他 Codex 仍可重建核心上下文。
- 本次是根据实施提交、测试和当前对话做的历史补录；未包含付费 API 的真实生成结果，因为上次未执行该验证。

## 故障排查入口

- 后续修改前上下文不足：从 `AGENTS.md` 和 `docs/change-records/INDEX.md` 恢复，不要重述全部聊天。
- 怀疑上次修改引入故障：从症状关键词找记录，然后用其实施提交和运行 Trace 验证因果。
- Skill 未自动触发：显式调用 `$infinite-canvas-maintenance`，并确认 Skill 仍在本机 Codex Skills 目录。
- GitHub 推送认证异常：使用 `github-safe-repo-upload` Skill 的 Windows 认证回退流程，不输出凭据。

## 回退方案

- 本任务只添加文档和本机 Skill，不改变画布运行行为。
- 如需从仓库撤销维护制度，经用户授权后对 `c5e48696cc1628febe168418267efd884bf4f3b9` 和本记录所在提交创建新的 `git revert` 提交，不改写历史。
- 如需移除本机 Skill，只删除 `infinite-canvas-maintenance` Skill 目录；不删除仓库内记录。
