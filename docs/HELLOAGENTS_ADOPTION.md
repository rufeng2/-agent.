# HelloAgents 模式评估与采用记录

参考仓库：[jjyaoao/HelloAgents](https://github.com/jjyaoao/HelloAgents)。评估基于提交 `5432566d01ea1c2095c4a717fe2a010aa1c3b0bd`。

## 已采用

### GSSC 上下文工程

借鉴 `ContextBuilder` 的 Gather-Select-Structure-Compress 管线，在 `backend/ecommerce/context_engineering.py` 中实现电商领域版本：

- Gather：策略、任务状态、数据证据、长期记忆和会话历史。
- Select：将商品 ID、KPI 和渠道等结构化状态加入相关性计算，按优先级和相关性选取。
- Structure：输出 Task、Policies、State、Evidence、Memory 和 Conversation 分区。
- Compress：按 token 预算选择数据，并预留模型输出空间。
- TokenCounter：优先使用 `tiktoken`，不可用时采用字符估算降级。

### ToolRegistry 与 ToolFilter

借鉴 HelloAgents 的工具注册和子代理过滤，在 `backend/ecommerce/capability_registry.py` 中声明：

- 工具副作用：`read_only`、`sandbox_only`、`business_write`。
- 可使用该工具的 Agent。
- 允许的执行模式。
- 写工具对应的审批动作。

自主运行时在工具调用之前执行能力校验；MCP Server 在调用之后再次验证审批快照，形成规划层和执行层双重控制。

### Reflection 评分

借鉴 ReflectionAgent 的“生成-反思-改进”思想，`OperationsReflectionCritic` 对每轮结果计算：

- 目标进展
- 证据完整性
- 安全性
- 成本效率

Critic 只返回 `accept`、`replan` 或 `stop`。KPI 达标但证据不足或存在安全问题时不会被接受。

### 统一 Trace

借鉴 `TraceLogger`，自主运行记录：

- `run_started`
- `memory_recalled`
- `step_started`
- `step_completed`
- `reflection`
- `error`
- `run_succeeded` / `run_stopped`

Trace 与任务 ID、轮次、步骤、Agent 和 payload 关联，并计算步骤、错误和重规划统计。

## 已有等价能力，不重复引入

- HelloAgents `ToolResponse`：项目已有 Pydantic `ToolResponse` 和 MCP 错误协议。
- `CircuitBreaker`：MCP Client 已有超时、失败计数、熔断恢复和 Prometheus 指标。
- `SessionStore`：项目使用 SQLAlchemy 持久化会话、消息、任务和 LangGraph checkpoint。
- `PlanSolveAgent`：项目已有动态运营 DAG 和 LangGraph 写操作图。
- `TodoWrite`：动态计划步骤本身持久化状态，前端展示每步完成情况。
- 流式 SSE：当前执行规模较小，先保留请求响应和持久化查询；异步长任务队列启用后再增加 SSE。

## 明确不直接复制

- 不替换 LangGraph：现有 interrupt、checkpoint 和 Command resume 已承担图运行职责。
- 不让通用 ReAct Agent直接持有写工具：电商价格、库存和预算操作必须经过确定性策略、审批和 MCP 服务端复核。
- 不使用文件保存完整工具输出：项目使用租户隔离的数据库任务、事件和结果字段，避免文件路径泄漏与多实例不一致。
- 不复制 Skills 文件系统：电商 SOP 采用结构化 procedural memory，便于校验来源、成功评价和租户范围。
