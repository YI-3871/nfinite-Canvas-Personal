# IC-20260927-01 · 个人仓库迁移与推广清理

- 状态：本地修改与自动验证通过；界面实测受限
- 日期：2026-09-27
- 负责方：Codex；个人版维护者 YI-3871
- 实施分支：`codex/personal-repository-migration`
- 实施提交：`cf2e5de4458eb08b125239889ba2a4ca2db8a844`
- 基线提交：`ca723319c693dfb5e50a3db6164cb4c0902d392e`
- 版本：沿用 `2026.09.10`，本次未改变 VERSION
- 关联 Trace ID / 任务 ID：`none`
- 工作区：仅开发版；没有同步初始包
- 发布目标：`YI-3871/nfinite-Canvas-Personal` 的 `main`
- 远程更新前提交：`2e9be7a16aeee9fb70c74b4ebac47adc2ba114cd`

## 用户需求与授权

用户确认原项目是本人原团队项目，确认新账号与现有仓库为 YI-3871/nfinite-Canvas-Personal，授权迁移署名与许可证、清理旧 README 和赞赏内容，并更新该远程仓库。用户同时反馈 Nano Banana 2 单轮及多轮图生图编辑的偏粉问题已经解决。

本次将旧 README 整体替换为简短个人版说明，保留已经实现的颜色保护功能介绍，不清空必要的操作入口。使用许可改为个人项目署名，保留原有非商业使用、商业授权及衍生代码署名/开放源代码要求；第三方组件许可证不动。

## 原因、范围与验收

旧团队信息分散在 README、赞赏图片、推荐 API 的私信推广、邀请参数、两种配套插件和教程。GitHub 账号或远程地址的改变不会自动修改这些内容。

- [x] 新 README/LICENSE/运行说明使用新账号及仓库地址，删除旧外链截图。
- [x] 删除根目录赞赏图片、旧私信推广、注册链接邀请参数和配套的专属折扣承诺。
- [x] 两种插件的显示名称及 GitHub 链接迁移，保留内部身份与用户设置。
- [x] 不修改颜色修正算法、生图请求协议、模型预设或用户 API 配置。
- [x] 原有未提交差异保留，不夹带到提交或发布。
- [ ] 浏览器、Chrome 扩展和 Photoshop 实际交互验收：未完成。

## 实施方案与文件清单

采用精确字符串及 DOM 片段修改，不做全局账号替换。特别保留真实 ModelScope 模型资源标识、插件 ID、存储键和程序命名空间，防止把依赖地址当作署名误改。

| 文件 | 本次变化 |
| --- | --- |
| `README.md` | 重写个人版介绍、已完成功能、运行和维护入口，移除 11 张旧外链截图 |
| `LICENSE` | 重写个人署名及授权联系方式，保留原使用限制、说明第三方许可独立 |
| `运行说明.txt` | 用简短本地运行指引替换旧视频和推广说明 |
| `赞赏.png` | 删除 517714 字节的旧赞赏码；删除前确认与已跟踪版本哈希一致 |
| `新手运行与使用教程.md` | 替换旧视频入口，移除注册链接邀请参数 |
| `static/api-settings.html` | 移除 RunningHub 入口的 4 处邀请参数 |
| `static/js/api-settings.js` | 移除 10 处邀请参数、私信推广和旧专属优惠文字；服务地址/协议/模型不变 |
| `static/js/i18n/api-settings.js` | 删除私信翻译、改为中性服务说明 |
| `tools/chrome-local-asset-importer/README.md` | 增加个人维护者和仓库地址 |
| `tools/chrome-local-asset-importer/popup.html` | 显示 YI 标识及个人仓库提示 |
| `tools/chrome-local-asset-importer/sidepanel.html` | 同步侧边栏显示信息 |
| `tools/chrome-local-asset-importer/popup.js` | 仅更换 GitHub 跳转；保留原文件其他内容和 NUL 字符 |
| `tools/photoshop-asset-connector/README.md` | 更新显示名称及个人仓库说明 |
| `tools/photoshop-asset-connector/index.html` | 更新标题、标识和页脚显示名称 |
| `tools/photoshop-asset-connector/js/app.js` | 仅更换 GitHub 跳转 |
| `tools/photoshop-asset-connector/manifest.json` | 更新名称和菜单标签，不改变插件 ID |
| `tests/test_personal_api_links.js` | 5 项推荐服务/链接/模型与协议不变测试 |
| `tests/test_personal_branding.js` | 5 项署名/赞赏删除/插件兼容/真实模型标识测试 |

审计文档：CHANGELOG、变更索引、本记录，以及 IC-20260927-00 的后续身份澄清。

## 存储、兼容性、安全与资源

无接口、数据库、画布 JSON 或配置格式迁移，没有新增依赖。未读写 API 密钥、用户素材、生成图片或本机日志。未启动真实后端，未请求收费 API。已完成的颜色保护算法未修改；多轮实际使用结论来自用户反馈，不冒充本次付费端到端测试结果。

旧内部插件 ID/存储键/命名空间和实际模型资源保留；历史审计及测试中也保留必要旧标识。后端旧更新模块仍保留，但主页面更新入口已关闭，本次没有恢复或重定向后台更新能力。

删除只作用于最新文件树；历史版本仍可找回赞赏图片，不改写已发布历史或删除标签。注册邀请参数删除后，不再承诺原专属优惠；未验证服务商注册活动。

## 验证证据

| 项目 | 结果 |
| --- | --- |
| `python/python.exe -B -m unittest discover -s tests -p test_color_preservation.py` | 4/4 通过，使用测试图与临时输出 |
| `node --test tests/test_personal_branding.js tests/test_personal_api_links.js tests/test_sidebar_personal_build.js tests/test_canvas_result_media_urls.js` | 19/19 通过 |
| 修改 JS 语法、候选发布 HTML 内联脚本编译 | 通过 |
| `git diff --check` 与暂存区检查 | 通过；未批量转换用户文件换行符 |
| 候选上传路径/大小/凭据扫描 | 实施时 35 个新增或修改文本文件，共 2939932 字节；无保护路径和常见密钥特征命中；不含删除的赞赏图片，最终发布前再扫描记录文档 |
| 已有用户差异 | 精确暂存后，与任务前逐变更行核对一致；端口和资源版本变化没有提交 |
| 独立复核 | 检查并修正了邀请参数删除后的旧折扣宣传；未发现模型协议或插件身份误改 |
| 浏览器实测 | 无法进行：工具无法验证已保存的站点权限并拒绝打开本机预览，没有绕过安全检查 |

只读假数据预览进程已停止。没有运行 Photoshop 宿主、扩展实际导入、真实付费生图或完整后端集成测试。

## 发布与回退

已读取并比较远程历史：远程 main 是当前开发链的祖先，可使用普通快进推送。此次发布会包含远程尚未收到的既有 OUTPUT 修复、模型别名颜色保护、工作区说明及侧栏清理提交，不会包含当前未提交的个人运行调整。

使用现有仓库专用 SSH 配置，不创建密钥、不降低主机校验、不强制推送。推送后必须用 `git ls-remote` 核对远程 main 与发布提交相同；发布结果以交付时回执和远程引用为准。

若需要回退，先保护当前未提交文件，再经用户授权对实施提交创建可审计的 revert 提交；不要整文件覆盖、删除仓库或移动基线标签。赞赏图片可从实施提交的父版本找回。

## 故障排查入口

- 页面仍显示旧文字：确认运行的是开发版并强制刷新；已安装插件需要重新加载本目录版本。
- 插件连接失效：先核对服务地址及已有设置，不能因显示名迁移而重建插件 ID。
- 颜色保护疑问：沿用既有颜色保护记录和 Trace 排查，本次没有改变算法。
