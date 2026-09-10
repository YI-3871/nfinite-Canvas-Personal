# IC-20260909-01 · Nano Banana 2 颜色保护与详细 API Trace

- 状态：已发布
- 日期：2026-09-09
- 版本：`2026.09.09`
- 实施分支：`codex/nanobanana2-color-logging`
- 实施提交：`0dbf2e3e2744d25deb8b08971b504387393aa507`
- 基线提交：`25d83e13fb5f6fc344cf3573566d0171b268e94c`
- 基线标签：`baseline-initial-2026-09-09`
- 变更规模：24 个文件，2340 行新增，157 行删除
- 原始方案参考任务：`codex://threads/01a0474a-46cc-7c53-a629-5f67610e5ecd`

## 用户需求与修改前现象

### Nano Banana 2 图像发粉

使用 Nano Banana 2（界面中对应 `gemini-3.1-flash-image-preview` 系列）处理换装、换姿势等任务时，API 返回图像可能出现不希望的偏粉/品红色漂移。颜色保护不得强制开启，需要由用户自由选择：

- 任务类型：换装、换姿势、场景/光线。
- 保护强度：关闭、自动、严格。
- 两组选择互相独立，并且会跟随画布保存。
- 新节点默认关闭颜色保护。

### 运行日志过于简单且终端噪声过多

修改前的终端主要显示重复的画布 `PUT`、任务轮询 `GET` 和素材预览访问，但出现上游 API 错误时缺少以下证据：

- 请求使用的提示词、模型、平台、参数和参考图元数据。
- 上游端点、请求方法、脱敏请求体、响应码、上游 Request ID 和耗时。
- 从接收、排队、执行、上游请求、保存图片、颜色保护到完成/失败的完整时间线。
- 可用于定位单次请求的 Trace ID。

同时，不应把所有详细信息长期塞入画布 JSON 和 Python 内存。

## 验收标准

- [x] 只在 `gemini-3.1-flash-image...` 模型下显示颜色保护 UI。
- [x] 任务类型和保护强度可独立选择，默认关闭。
- [x] 始终保留 API 原始图；仅在安全判定通过后生成和显示 `_colorfix` 版本。
- [x] 校正失败或低置信度时安全回退到原图，不让生图任务失败。
- [x] 详细 API 日志写盘而不在画布内存中无界累积。
- [x] 日志可从 UI 浏览、搜索、复制和清理。
- [x] 凭据和图片二进制/Base64 不写入日志。
- [x] 终端只降噪重复成功请求，4xx/5xx 仍显示。
- [x] 对内存任务、日志队列、画布摘要和日志数据库设置明确上限。

## 颜色保护实现

### 适用边界

- 后端仅对模型名以 `gemini-3.1-flash-image` 开头的请求启用颜色保护。
- 新请求字段：`task_mode`、`color_preservation`、`color_reference_url`、`source`、`canvas_id`、`node_id`。
- `task_mode` 允许 `outfit_swap` / `pose_change` / `scene_change`。
- `color_preservation` 允许 `off` / `auto` / `strict`，非法值安全回退。
- 默认参考图优先使用 `base`、`original`、`source`、`person`、`input` 等角色，否则使用第一张图。
- `scene_change` 将颜色基线视为有意改变，直接保留 API 输出，避免把用户要求的新光线强行拉回参考图。

### 自适应混合 D 方案

`color_preservation.py` 实现了一个保守的后处理管线：

1. 读取并按 EXIF 方向纠正参考图与生成图，转换到 sRGB 分析，保留尺寸、Alpha 与可用元数据。
2. 对分析缩略图做边缘对齐和平移估计，在结构可比的区域寻找颜色锚点。
3. 按空间区域和亮度平衡抽样，将锚点确定性分成拟合集与留出验证集，避免在同一数据上拟合和判定。
4. 候选 A：只校正 LAB 的 `a/b` 色度轴，不直接改变亮度。
5. 候选 B：带正则化和安全矩阵约束的 RGB 线性变换。行列式、对角线偏移、非对角混合和偏置量超界时拒绝该候选。
6. 用留出锚点的 Delta E 76 中位数、90 分位数、改善比例和变差放大等指标选择候选。
7. 按暗部、中间调和高光自适应选择强度，再与置信度、任务类型和用户模式合成遮罩。
8. 置信度由锚点覆盖、空间分布、对齐质量和留出改善组成。`auto` 阈值为 `0.48`，`strict` 阈值为 `0.38`。
9. LAB 色度偏移限制：`auto` 最多 8，`strict` 最多 12。严格模式阈值更低、强度更高，但仍受安全候选和置信度约束。
10. 未通过安全判断时不重新编码原图，不生成 `_colorfix`，在诊断中写入回退原因。

返回诊断包含方法、候选指标、置信度、锚点统计、对齐信息、色调强度、品红漂移指标、原图 URL、修正图 URL 与回退原因。

### 输出保护

- API 原始输出先以 `online_...` 文件保存。
- 校正成功时在同目录生成 `*_colorfix.<ext>`，画布显示该版本。
- 返回结果同时包含 `raw_images`、`image_items[].raw_url`、`color_preservation` 和 `trace_id`。
- 校正异常不向上传播，而是记录错误并显示原始图。

## 详细 API Trace 实现

### 存储模型

`task_log_store.py` 使用 `data/task_logs.sqlite3`，包含：

- `task_logs`：每个 Trace 的索引、请求、响应、错误、颜色诊断和耗时。
- `task_log_events`：按时间排序的生命周期事件。
- `task_log_meta`：上次清理提示时间等元数据。

写入使用单独守护线程与最多 1000 项的有界队列。队列已满时丢弃新事件并在应用日志警告，避免日志反向拖垮生图任务。

磁盘边界：

- 最大 500MB。
- 超限后从最旧 Trace 开始清理，目标回收到约 450MB。
- 清理后执行 WAL checkpoint 与 `VACUUM`，让文件实际缩小，而不只删除行。
- 每 30 天且存在记录时提示用户选择清理或继续保留。
- 用户可在 UI 手动清理全部详细日志。

### Trace 生命周期

画布图像任务在提交时创建 `trace_<uuid>`，并将 Trace ID 返回前端。可记录的阶段包括：

- `queued` / `accepted`
- `running`
- `provider_prepare`
- `provider_request`
- `provider_response` / `provider_error`
- `upstream_pending`
- `saving_output`
- `color_protection`
- `completed` / `failed`

Gemini 请求记录脱敏后的请求方法、端点、Headers、Body、超时设置，以及响应码、上游 Request ID、Content-Type、Content-Length 和耗时。错误时记录受限长度的响应体与 Python 堆栈。

参考图元数据包含 URL、名称、角色、类型、MIME。可解析的本地文件还记录字节数、修改时间、SHA-256、宽高和格式。计算 SHA-256 时按 1MB 分块读取，不把整个文件复制到内存。

### 脱敏与容量限制

写入队列前统一脱敏：

- 匹配 API Key、Authorization、Cookie、Token、Secret、Password、Credential、Private Key 等字段的值替换为 `[REDACTED]`。
- URL 查询中的 `key`、`apikey`、`token`、`access_token`、`auth` 等参数脱敏。
- `data:` URI、二进制字节和大段疑似 Base64 内容只保留省略说明。
- 字典嵌套深度最多 10，列表最多 200 项。
- 提示词/文本可保留到 100,000 字符，其他普通字符串最多 16,000 字符。

### 查询与管理端点

- `GET /api/task-logs/storage`：占用、上限、数量、队列和清理提示状态。
- `GET /api/task-logs`：按画布、状态、平台和搜索词分页查询。
- `GET /api/task-logs/{trace_id}`：详细请求、响应、错误、颜色诊断和事件时间线。
- `DELETE /api/task-logs?scope=all|older_than_30d`：手动清理。
- `POST /api/task-logs/reminder`：清理或延后 30 天提示。

### 画布 JSON 与 Python 内存边界

- 传统画布和智能画布前端的 `canvas.logs` 最多 100 条，新记录在前。
- 后端保存画布时再次压缩为最多 100 条摘要。每条仅保留定位字段、最多 8 个输出、600 字符提示词预览和 1200 字符错误摘要。
- `CANVAS_TASKS` 始终保留非终止任务；终止任务超过 24 小时清理，并仅保留最新 200 条。
- 详细信息通过 Trace ID 按需从 SQLite 读取，不随画布全量加载。

## 前端变化

### 传统画布

`static/js/canvas.js` 在 API 生成节点中增加任务类型和颜色保护两个下拉框。只有选中 Nano Banana 2 模型时该行可见，切换其他模型后隐藏，已选值仍保留在节点中。

### 智能画布

`static/js/smart-canvas.js` 在动态 API 参数区显示两个独立的 pill/popover 控件。选择会写入画布设置或节点的运行设置，重新打开后保留。

### 详细日志 UI

`static/js/task-log-ui.js` 由两种画布共用，提供：

- 磁盘日志条数和占用量。
- “浏览详细日志”与“清理详细日志”。
- 按 Trace ID、任务 ID、模型或提示词搜索，并按状态过滤。
- 单条任务的“API 详情”：摘要、完整提示词、请求、阶段时间线、颜色诊断、响应与错误。
- “复制全部”。
- 30 天清理提示。

`static/canvas.html` 和 `static/smart-canvas.html` 在主画布脚本之前引入该共享模块。

## 终端日志降噪

`QuietAccessLogFilter` 只隐藏以下且状态码小于 400 的重复请求：

- `PUT /api/canvases/{id}`
- `GET /api/canvas-image-tasks/{id}`
- `GET /api/canvas-comfy-tasks/{id}`
- 媒体预览和 `assets/input|output` 读取

对应请求的 4xx/5xx 状态仍然显示，其他端点不会因路径广泛匹配而被误隐藏。

## 上传内存优化

`POST /api/ai/upload` 从一次性 `await file.read()` 改为每次 1MB 读取并写盘：

- 继续执行单文件 50MB 上限。
- 超限时返回 413 并删除已写入的部分文件。
- 空文件不保留。
- 拒绝信息记录文件名和上限，不记录文件内容。

## 文件变更清单

| 文件 | 作用 |
| --- | --- |
| `color_preservation.py` | 新增颜色保护算法、诊断与安全回退。 |
| `task_log_store.py` | 新增有界队列、SQLite Trace、脱敏、分页和清理。 |
| `main.py` | 集成请求字段、颜色保护、Trace 生命周期、日志 API、任务剪枝、终端降噪和分块上传。 |
| `static/js/canvas.js` | 传统画布控件、请求字段、原图/修正图元数据和日志入口。 |
| `static/js/smart-canvas.js` | 智能画布动态控件、请求字段、设置持久化和日志入口。 |
| `static/js/task-log-ui.js` | 两种画布共用的磁盘日志工具栏、浏览器和详情弹层。 |
| `static/canvas.html` | 引入共享日志 UI，更新缓存版本。 |
| `static/smart-canvas.html` | 引入共享日志 UI，更新缓存版本。 |
| `README.md` | 记录个人版颜色保护、Trace、资源边界和安全行为。 |
| `VERSION` | 更新为 `2026.09.09`。 |
| `tests/test_color_preservation.py` | 验证混合校正、相同图不重编码、场景回退和换姿容忍。 |
| `tests/test_task_log_store.py` | 验证凭据/Base64 脱敏、Trace 生命周期、显式清理和磁盘硬上限真实回收。 |
| `tests/test_main_features.py` | 验证模型范围、画布摘要压缩、内存任务上限和终端日志过滤。 |
| `static/angle.html` | 统一静态资源缓存版本。 |
| `static/api-settings.html` | 统一静态资源缓存版本。 |
| `static/asset-manager.html` | 统一静态资源缓存版本。 |
| `static/canvas-list.html` | 统一静态资源缓存版本。 |
| `static/comfyui-settings.html` | 统一静态资源缓存版本。 |
| `static/enhance.html` | 统一静态资源缓存版本。 |
| `static/gpt-chat.html` | 统一静态资源缓存版本。 |
| `static/index.html` | 统一主页面 iframe 缓存版本。 |
| `static/klein.html` | 统一静态资源缓存版本。 |
| `static/online.html` | 统一静态资源缓存版本。 |
| `static/zimage.html` | 统一静态资源缓存版本。 |

## 验证证据

| 验证 | 结果 | 备注 |
| --- | --- | --- |
| Python 语法编译 | 通过 | `main.py`、`color_preservation.py`、`task_log_store.py` |
| JavaScript 语法 | 通过 | `canvas.js`、`smart-canvas.js`、`task-log-ui.js` |
| 自动测试 | 11/11 通过 | 颜色、日志、内存、过滤和模型范围 |
| FastAPI TestClient 烟雾测试 | 通过 | Nano Banana 2 参数字段、存储上限、查询端点 |
| 传统画布浏览器联调 | 通过 | 控件可见、默认关闭、日志入口存在、无 page error |
| 智能画布浏览器联调 | 通过 | 两个独立控件、默认关闭、日志入口存在、无 page error |
| `git diff --check` | 通过 | 提交前格式检查 |
| 凭据特征扫描 | 通过 | 未发现 PAT、AWS Key 或私钥头 |
| 实际付费 API 端到端 | 未执行 | 为避免未授权消耗用户额度 |

## 已知限制

- 详细 Trace 只会记录升级后新发起的图像 API 任务，不会追溯补录旧任务。
- Gemini/Nano Banana 2 路径记录精确的上游请求和响应信息；其他协议至少记录平台、模型、请求模式、基础 URL、参数和生命周期，但不一定有同等粒度的上游 Headers/Body。
- `scene_change` 选择会保留新场景/光线，不强行修正回参考色。
- 500MB 上限只约束 API Trace 数据库，不约束 `output/` 中的原始图和修正图。
- 超限清理与 `VACUUM` 是罕见的重操作，在非常大的数据库上可能短暂占用额外 I/O。
- 详细错误堆栈可包含本机文件路径，因此 SQLite 不应传给不受信任的人。

## 故障排查入口

### 图像仍然发粉

1. 确认模型是 `gemini-3.1-flash-image...`。
2. 确认颜色保护不是“关闭”，任务类型不是“场景/光线”。
3. 在画布运行日志打开该任务的“API 详情”，查看 `color_protection` 阶段、`status`、`confidence`、`method` 和 `reason`。
4. 对比 `raw_url` 与 `corrected_url`；如果没有修正图，根据回退原因判断是低置信度、参考图不可用还是候选不安全。

### 界面不显示任务类型/颜色保护

1. 查看节点当前的实际平台和模型，不要只看用户对模型的别名。
2. 模型名必须以 `gemini-3.1-flash-image` 开头。
3. 检查浏览器缓存是否仍使用旧的 `canvas.js` / `smart-canvas.js`。

### 详细日志不见或占用异常

1. 确认请求是升级后新发起的画布图像 API 任务。
2. 检查 `GET /api/task-logs/storage` 和 `data/task_logs.sqlite3` 的写入权限。
3. 检查存储信息中的 `queue_size` 和 `dropped_events`。
4. 使用 Trace ID 请求 `GET /api/task-logs/{trace_id}`。
5. 不要用记事本直接打开 SQLite；优先使用画布界面或 SQLite 查看器，并且不要在画布运行时手动删除数据库文件。

### 终端看不到成功轮询

这是预期降噪行为。使用画布详细 Trace 查看任务生命周期；如果 4xx/5xx 也被隐藏，则检查 `QuietAccessLogFilter`。

## 回退方案

- 查看修改前状态：`baseline-initial-2026-09-09`。
- 需要仅撤销本次已发布功能时，在保护当前未提交文件的前提下，经用户授权后新建 `git revert 0dbf2e3e2744d25deb8b08971b504387393aa507` 提交。
- 不强制推送，不移动基线标签。
- 旧代码会忽略 `data/task_logs.sqlite3`；如果用户确认不再需要详细日志，关闭服务后可通过新版 UI 先清理。

## 设计参考

- [ComfyUI `server.py`](https://github.com/Comfy-Org/ComfyUI/blob/master/server.py)：任务/提示标识、事件通知和历史边界。
- [ComfyUI `main.py`](https://github.com/Comfy-Org/ComfyUI/blob/master/main.py)：启动和日志配置方式。
- [ComfyUI issue #8029](https://github.com/comfyanonymous/ComfyUI/issues/8029) 与 [issue #15965](https://github.com/Comfy-Org/ComfyUI/issues/15965)：日志噪声和历史持久化的实际需求。

本实现保留了“任务 ID + 生命周期事件 + 有界内存”的优点，并用本地 SQLite 补足重启后的详细 Trace 持久化。
