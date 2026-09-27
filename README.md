# Infinite-Canvas

## 个人开发版与项目来源

- 本项目是个人使用的二次开发版本，基于 [wuli大雄（hero8152）的 Infinite-Canvas](https://github.com/hero8152/Infinite-Canvas)。保留原作者来源说明与 [LICENSE](LICENSE)，主侧栏不再显示作者推广和社媒入口。
- 本地修改与验证在开发版完成，稳定初始包仅在用户确认后同步；见 [工作区说明](docs/WORKSPACE-STRATEGY.md)。
- 页面底部仅显示本地版本号。已移除主页面的原项目更新入口、自动更新检查及相关调用，防止从这里覆盖个人改动。后端旧更新模块尚未移除，不要从旧页面或外部工具调用；升级由维护者核对代码后手动完成。

----

支持的功能：
1. 支持几乎所有OpenAI协议的API/异步协议/Gemini协议/方舟协议
2. RunningHub的工作流/AI应用/收费模型调用
3. 火山引擎调用（人脸认证还在修复bug）
4. Modelscope免费LLM模型和图像模型调用
5. 即梦CLI调用，可直接调用即梦高级会员的积分，支持文生图/图生图/文生视频/图生视频
6. 支持调用本地局域网的ComfyUI
7. 扩展图片/360全景图预览截图/视频帧抽取/循环节点等诸多功能
8. tools文件夹中，增加了chrome批量采集到素材库的插件，PS直连画布调用所有功能的插件

## 个人版增强：API 生成颜色保护与 API 日志

- API 生成节点固定显示两个可独立选择的选项：任务类型（换装、换姿势、场景/光线）与颜色保护（关闭、自动、严格），不依赖服务商返回的模型名称。新画布默认关闭，之后随画布记住上次选择。
- 开启颜色保护后始终保留 API 原始输出；只有安全检测通过时才生成并显示 `_colorfix` 版本。详情中会记录算法、置信度、色差指标和回退原因。
- 每次图像 API 请求都有独立 Trace ID。画布日志中的“API 详情”可查看完整提示词、请求参数、参考图尺寸与 SHA-256、上游状态、耗时、错误堆栈和颜色保护阶段。
- API Key、Authorization、Cookie、Token、密码、图片二进制和 Base64 不写入日志；这些字段只显示为脱敏占位信息。
- 详细日志保存在 `data/task_logs.sqlite3`，使用有界写入队列，不塞进画布 JSON。数据库上限 500MB，超过后自动从最旧记录清理到约 450MB；每 30 天提示是否清理，也可在日志窗口手动清理。
- 终端只隐藏重复且成功的画布保存、任务轮询和素材预览请求；任何 4xx/5xx 请求仍会显示。内存任务仅保留运行中任务与最多 200 条、24 小时内的已完成任务。
- `/api/ai/upload` 使用 1MB 分块写盘并维持 50MB 限制，避免上传时再复制一整份文件到内存。

--------

已经申请著作权，禁止商业用途

Commercial use is prohibited.


* 可以自己使用和公司使用，禁止用于任何形式的修改封装成商业产品，商用须取得授权。

* 根据代码二次开发的软件必须保持开源并注明来源作者

* This software is for personal and company use only, but is prohibited from being modified or packaged into commercial products in any way. Commercial use requires authorization.

* Software developed based on this code must remain open source and the original author must be credited.

--------


<img width="2079" height="665" alt="image" src="https://github.com/user-attachments/assets/8469923b-f7a2-403c-9c37-e6e789211f28" />

<img width="1865" height="1503" alt="image" src="https://github.com/user-attachments/assets/f4030201-67c6-4845-b08b-b6fdf304afaa" />


<img width="1696" height="1350" alt="b68e144c5b04a322bfd035da4d89aba3" src="https://github.com/user-attachments/assets/0a6090fb-a8dd-4c3d-adee-b1f9233a2d91" />

   
<img width="1525" height="1473" alt="image" src="https://github.com/user-attachments/assets/6f61fcf9-746c-425b-9e36-cfc8d252da7c" />

   <img width="1261" height="864" alt="image" src="https://github.com/user-attachments/assets/57f3e230-3134-488f-8179-d97e7d15383a" />
<img width="1530" height="858" alt="image" src="https://github.com/user-attachments/assets/9990e42d-22d5-4a10-a1e1-ad35a634edd2" />

<img width="1735" height="1400" alt="image" src="https://github.com/user-attachments/assets/d8328ff8-bbe0-4f1c-9ffa-7b56e8a1a51d" />
<img width="2258" height="969" alt="image" src="https://github.com/user-attachments/assets/4a752d99-885d-4ba9-8b86-91b495786b5c" />


<img width="1531" height="1374" alt="image" src="https://github.com/user-attachments/assets/0af79e38-0955-4740-9e65-5c9bb057f58c" />

<img width="2196" height="1040" alt="image" src="https://github.com/user-attachments/assets/6d823668-cde2-4836-8332-1858efe5f520" />
<img width="2214" height="771" alt="image" src="https://github.com/user-attachments/assets/52e10958-753f-45ba-a50e-3bbec27be436" />
