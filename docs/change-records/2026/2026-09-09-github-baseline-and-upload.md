# IC-20260909-00 · 初始版 GitHub 存档与安全上传通道

- 状态：已完成
- 日期：2026-09-09
- 仓库：`YI-3871/nfinite-Canvas-Personal`
- 远程：`ssh://git@ssh.github.com:443/YI-3871/nfinite-Canvas-Personal.git`
- 初始提交：`25d83e13fb5f6fc344cf3573566d0171b268e94c`
- 初始标签：`baseline-initial-2026-09-09`
- 后续优化分支：`codex/nanobanana2-color-logging`

## 用户需求

1. 先把未使用的初始版画布上传到个人 GitHub 仓库，作为永久恢复点。
2. 修改后再上传最新版，同时保留初始版。
3. 建立一种可以长期复用、不要求 Codex 操作用户浏览器的 GitHub 上传方法。

## 身份与仓库基线

- Git 提交身份：`YI-3871 <2750330048@qq.com>`。
- `main` 的首个存档提交是初始画布，并使用注释标签 `baseline-initial-2026-09-09` 固定。
- 后续功能修改在 `codex/nanobanana2-color-logging` 上完成，验证后快进到 `main`。
- 没有使用强制推送，没有改写基线历史。

## 遇到的认证问题

### Git Credential Manager 设备登录失败

执行 GitHub 设备登录时，PowerShell 显示“由于 `Exception.ToString()` 失败，因此无法打印异常字符串”。用户已在 Chrome 登录 GitHub，但浏览器 Cookie 与 Git/GCM 凭据是两套独立状态，因此不能证明命令行已登录。

在完成网页授权后，本机仍不应依赖不稳定的账户 Token 持久化，也不应使用明文 Token 存储或关闭 TLS 验证。

### 采用仓库专用 Deploy Key

用户明确同意为这一个仓库使用带写权限的 Deploy Key。实施边界：

- 每个仓库使用独立 Ed25519 密钥。
- GitHub 只接收 `.pub` 公钥，私钥始终在仓库外，不在聊天、Git 或日志中显示。
- GitHub 仓库 `Settings -> Deploy keys` 中已开启 `Allow write access`。
- 仓库本地 `core.sshCommand` 限定只使用该仓库的私钥与已验证的 `known_hosts`。
- 因 SSH 22 端口可能受限，远程使用 GitHub 的 SSH 443 端口主机 `ssh.github.com`。
- 主机密钥必须与 GitHub 官方公布的指纹核对后才接受，不使用关闭主机验证的方式。

Deploy Key 公钥指纹只用于人工核对，不是 GitHub 的填写字段。丢失设备或不再使用时，应在仓库 `Settings -> Deploy keys` 删除该公钥来撤销权限。

## 安全上传前置检查

- `.gitignore` 排除 `.env`、密钥、运行日志、生成图片、用户素材、本地数据库和画布运行数据。
- 提交前检查暂存文件、大文件和凭据特征。
- 仅暂存用户授权的文件，不包含 `API/.env`、`data/`、`assets/` 和 `output/` 中的本机内容。
- 推送后使用 `git ls-remote` 核对远程分支和标签哈希，不只依赖推送命令的成功文字。

## 可复用 Skill

本机已创建 `github-safe-repo-upload` Skill，路径为 Codex 的个人 Skills 目录。它固化了：

- 新仓库基线和标签。
- 已有仓库的精确暂存和无关改动保护。
- 凭据和大文件检查。
- GCM/Schannel/GitHub CLI 凭据持久化故障的 Windows 规避流程。
- 仓库专用 Deploy Key、SSH 443、主机指纹校验与远程哈希验证。

## 验证结果

- `main` 初始提交远程核对：成功。
- `baseline-initial-2026-09-09` 注释标签远程核对：成功。
- 优化分支与后续 `main` 推送：成功。
- `github-safe-repo-upload` Skill 结构验证：成功。

## 回退与恢复

- 需要查看初始代码时，使用标签 `baseline-initial-2026-09-09`。
- 需要撤销后续已发布改动时，先诊断并征得用户同意，再使用新的 `git revert` 提交；不使用强制推送改写历史。
