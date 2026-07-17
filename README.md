# 智能电商运营 Agent

基于 **LangGraph + MCP + FastAPI + Vue 3** 的执行型电商运营 Agent。用户通过自然语言下达调价、商品上架、商品下架、营销活动和推广文案任务，系统完成多 Agent 路由、策略校验、人工审批、工具执行、结果交付和回滚。

> 项目使用可复现的模拟电商数据和沙箱业务系统，不连接淘宝、京东、Amazon 等真实平台。

## 核心流程

```text
用户对话 -> Intent Planner -> 参数完整性检查
  -> 信息不足：保存会话状态 -> 主动追问 -> 用户补充 -> 恢复原任务
  -> 只读分析：专业 Agent -> 沙箱数据工具 -> Evidence Critic -> 证据化报告
  -> 内容交付：商品事实 -> DeepSeek 生成 -> 失败时明确模板降级
  -> 业务写入：LangGraph 计划 -> 分级审批 -> MCP 执行 -> 验证/回滚
  -> 自动化：生成默认禁用的规则草案 -> 人工审核后再启用
```

## 支持的运营能力

| 能力 | 示例 | 行为 |
|---|---|---|
| 经营诊断 | `分析最近30天 GMV 为什么下降` | 汇总商品贡献、流量、广告和库存证据 |
| 商品运营 | `看看轻量跑步鞋的转化和库存` | 返回商品指标、风险与动作建议 |
| 竞品分析 | `给便携榨汁杯做小红书竞品分析` | 对比价格、促销和评价，不创建活动 |
| 内容运营 | `给便携榨汁杯写推广文案` | 缺渠道时追问，补充后生成渠道化内容 |
| 营销运营 | `给轻量跑步鞋做营销方案` | 输出策略；明确“创建活动”时才进入审批 |
| 广告优化 | `优化轻量跑步鞋的广告 ACOS` | 基于广告 ROI、转化和归因数据给出动作 |
| 客户运营 | `分析高价值客户复购和召回机会` | 客户分层、复购识别和召回建议 |
| 自动执行 | `调价到269元`、`下架P003` | 审批后调用 MCP 修改沙箱业务状态 |
| 自动化规则 | `每天自动检查库存风险` | 保存为禁用草案，避免未经批准自动运行 |

## 自主闭环运行

对于带有 KPI、周期和预算的复杂目标，系统进入自主闭环模式：

```text
Goal Contract
  -> Dynamic Planner
  -> Product / Competitor / Content Agents
  -> Sandbox Experiment
  -> Outcome Evaluator
  -> Evidence Critic
  -> Replan（未达标）
  -> Memory Consolidator（达标）
```

示例：

```text
用户：自主提升便携榨汁杯转化率
Agent：目标提升多少？多少天？预算上限是多少？
用户：未来 7 天提升 15%，预算 1000 元
Agent：生成动态 DAG，运行沙箱实验，评价 KPI；首轮未达标时反思并重规划，达标后停止。
```

运行时约束：

- 每次自主目标都必须包含商品、KPI 目标、观察周期和预算上限。
- 沙箱分析与实验可以自动运行；真实业务写操作仍进入角色审批和 MCP 校验。
- 每个步骤后保存 Observation 和检查点，工具中断后可在同一任务 ID 上恢复。
- 未达标时 Critic 记录差距、证据步骤和下一轮调整；达到最大轮次或预算上限时自动停止。
- 成功后写入情景记忆、成功 SOP、商品语义事实和用户预算偏好。
- 后续同商品、同 KPI 目标只召回来源可信且评价成功的 SOP，冲突或失败记忆不会进入规划。

自主实验的 KPI 变化来自项目内沙箱模拟器，用于验证 Agent 闭环，不代表真实平台的因果实验结果。

## HelloAgents 工程模式

项目参考 [HelloAgents](https://github.com/jjyaoao/HelloAgents) 的工程实践，并按电商领域约束完成以下适配：

- GSSC 上下文管线与 token 预算，替代简单字符截断。
- Agent 工具能力注册、只读/沙箱/业务写入分级和审批范围过滤。
- Critic 对目标进展、证据、安全和成本效率进行量化评分。
- 统一运行 Trace，记录步骤、错误、重规划、模型和工具事件。

完整采用与取舍记录见 `docs/HELLOAGENTS_ADOPTION.md`。项目没有替换已有 LangGraph、MCP、ToolResponse、熔断和 SQL 持久化，也没有让通用 ReAct Agent 绕过审批直接持有业务写工具。

## Agent 职责

| Agent | 职责 |
|---|---|
| Supervisor | 通过 Pydantic 结构化输出识别动作、商品和参数；LLM 不可用时确定性降级 |
| Catalog Agent | 通过 MCP 读取当前商品状态和版本 |
| Pricing Agent | 校验调价幅度、成本底线和毛利率 |
| Listing Agent | 准备上架或下架变更 |
| Marketing Agent | 生成营销活动预算和参数 |
| Content Agent | 调用 DeepSeek 生成渠道化推广文案；失败时提供明确标识的模板降级结果 |
| Risk Agent | 判断风险并生成 user/editor/admin 分级审批要求 |
| Approval Gate | 使用 LangGraph `interrupt` 暂停任务 |
| Tool Executor | 审批后执行 MCP 工具或复合任务 DAG，失败时执行补偿动作 |

复合指令（例如“调价并创建推广活动”）会被拆成有依赖关系的步骤：先调价，再创建活动；后置步骤失败时通过 MCP 恢复商品快照。每个步骤状态、工具名和执行回执都会写入任务结果。

## MCP Server

项目使用官方 Python MCP SDK，通过隔离的 stdio Session 调用独立 `ecommerce-operations` MCP Server。每次工具调用拥有独立会话，避免 MCP SDK 的 AnyIO cancel scope 跨 FastAPI 请求任务共享。

| Tool | 功能 |
|---|---|
| `get_product` | 查询商品价格、成本、状态和版本 |
| `update_product_price` | 更新商品价格 |
| `set_product_listing` | 上架或下架商品 |
| `rollback_product` | 恢复执行前快照 |
| `create_marketing_campaign` | 创建沙箱营销活动 |

所有写工具必须携带 `approved_task_id`，并使用 `expected_version` 进行乐观锁校验。MCP Server 会再次校验任务租户、运行状态、审批状态、动作类型、商品和参数，防止客户端篡改。工具统一返回 `ToolResponse`，包含状态、错误码、可重试标记和结构化数据。MCP Client 支持超时、失败熔断及 Prometheus 调用次数和延迟指标。

## 工程能力

- **多租户与 RBAC**：JWT 携带 `workspace_id` 和角色；任务查询按租户隔离，只读角色禁止写操作。
- **分级审批**：普通变更由 user 批准，10% 以上调价需要 editor，15% 以上需要 admin。
- **持久化恢复**：任务、事件、活动和商品状态写入 SQL 数据库；LangGraph 使用 `AsyncSqliteSaver` 保存执行检查点，可在进程重启后恢复。
- **上下文工程**：Supervisor 读取当前工作区最近任务，并按字符与估算 token 预算裁剪，避免历史无限增长。
- **多轮澄清**：会话持久化待补充目标与参数，用户回答后恢复原始任务，而不是重新猜测意图。
- **证据约束**：分析报告中的指标附带数据源、周期和样本量；不允许虚构竞品品牌、促销、认证或功效。
- **可观测性**：`/metrics` 暴露 MCP 调用状态和延迟；任务事件记录规划、审批、工具调用和回滚轨迹。
- **意图边界**：推广文案路由到 Content Agent 并交付标题、正文、卖点、CTA 和标签；只有明确要求创建活动时才写入营销活动与预算。
- **并发一致性**：商品写入使用版本号乐观锁；审批接口要求任务版本，重复提交会得到冲突响应。

## 页面

- **执行型 Agent**：创建任务、查看多 Agent 轨迹、审批、执行、查看 MCP 回执和回滚。
- **经营数据**：GMV、漏斗、趋势预测和经营异常。
- **商品分析**：价格、毛利、库存、广告、评价、竞品价格和模拟变化。

## 技术栈

- Agent：LangGraph 1.x
- 协议：Model Context Protocol Python SDK
- 后端：FastAPI、Pydantic、SQLAlchemy Async
- 数据库：SQLite（本地）/ PostgreSQL（可配置）
- 前端：Vue 3、TypeScript、Element Plus、Vite
- 测试：pytest、Playwright、vue-tsc

## 启动

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.venv\Scripts\python.exe -m pip install -r backend\requirements-langchain.txt

.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

```powershell
cd frontend
npm install
$env:VITE_API_TARGET="http://127.0.0.1:8001"
npm run dev -- --host 127.0.0.1 --port 5173
```

访问 `http://127.0.0.1:5173/agent`。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
npm run test:e2e
```

## 项目边界

- 商品、订单、库存、广告和竞品数据均为模拟数据。
- MCP Server 当前连接项目内沙箱适配器，不连接真实电商平台。
- 所有业务写操作都经过人工审批，高风险操作要求更高角色。
- 当前 LLM 可通过配置接入，未配置或调用失败时由确定性 Supervisor 保证演示可运行。
- 接入真实平台时仍需要实现平台 OAuth、真实适配器、限流与幂等键、密钥托管、告警和灾备；本项目不声称已直接控制生产店铺。
