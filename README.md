# 智能电商运营 Agent

基于 **LangGraph + MCP + FastAPI + Vue 3** 的执行型电商运营 Agent。用户通过自然语言下达调价、商品上架、商品下架和营销活动任务，系统完成多 Agent 路由、策略校验、人工审批、MCP 工具执行、状态回写和回滚。

> 项目使用可复现的模拟电商数据和沙箱业务系统，不连接淘宝、京东、Amazon 等真实平台。

## 核心流程

```text
自然语言任务
  -> Supervisor
  -> Catalog Agent
  -> Pricing / Listing / Marketing Agent
  -> Risk Agent
  -> LangGraph interrupt 审批断点
  -> Command(resume) 恢复执行
  -> MCP Tool Executor
  -> 业务状态回写与回执
```

## Agent 职责

| Agent | 职责 |
|---|---|
| Supervisor | 识别动作、目标商品和参数，路由专业 Agent |
| Catalog Agent | 通过 MCP 读取当前商品状态和版本 |
| Pricing Agent | 校验调价幅度、成本底线和毛利率 |
| Listing Agent | 准备上架或下架变更 |
| Marketing Agent | 生成营销活动预算和参数 |
| Risk Agent | 判断风险并生成审批原因 |
| Approval Gate | 使用 LangGraph `interrupt` 暂停任务 |
| Tool Executor | 审批后调用 MCP 写工具并生成回执 |

## MCP Server

项目使用官方 Python MCP SDK，通过持久化 stdio Session 调用独立的 `ecommerce-operations` MCP Server。

| Tool | 功能 |
|---|---|
| `get_product` | 查询商品价格、成本、状态和版本 |
| `update_product_price` | 更新商品价格 |
| `set_product_listing` | 上架或下架商品 |
| `rollback_product` | 恢复执行前快照 |
| `create_marketing_campaign` | 创建沙箱营销活动 |

所有写工具必须携带 `approved_task_id`，并使用 `expected_version` 进行乐观锁校验。MCP Client 支持会话复用、超时、自动重连、失败熔断和健康指标。

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
```

## 项目边界

- 商品、订单、库存、广告和竞品数据均为模拟数据。
- MCP Server 当前连接项目内沙箱适配器，不连接真实电商平台。
- 高风险写操作必须经过人工审批。
- 接入真实平台时需要补充 OAuth、租户隔离、平台限流、密钥托管和生产监控。
