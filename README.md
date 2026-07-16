# 智能电商运营 Agent 平台

基于 FastAPI、Vue 3、DeepSeek 和确定性经营分析工具构建的混合 AI Agent。系统面向电商运营诊断、商品与客户分析、活动策略和审批风控，在没有真实电商平台或企业内部数据时仍可完整本地演示。

项目未对接淘宝、京东等真实平台，当前也不是生产系统。所有经营数据和策略收益均为可复现的模拟结果。

## 核心能力

- **混合 Agent**：DeepSeek 负责结构化规划和结果解释，Python 工具负责指标、证据和风险决策；无 API Key 或模型异常时自动进入确定性降级。
- **90 天经营数据**：固定随机种子生成订单、流量、广告、库存、评价、客户、活动和竞品价格数据。
- **数据分析**：GMV 归因、转化漏斗、ABC 商品分层、RFM 客户分层、复购率、模拟 LTV、活动增量 ROI、竞品价格指数和 7 天 GMV 预测。
- **多轮会话**：保存 Agent 会话和消息，支持后续问题引用同一经营上下文。
- **审批审计**：建议、审批意见、版本和审计记录持久化；高风险动作不会由模型直接执行。
- **运行可观测性**：记录执行模式、模型、耗时、Token、降级原因和工具轨迹，并统计成功率、降级率和 P95 延迟。
- **Agent 评测**：40 条标准问题覆盖 8 类场景，评估意图、工具、参数、证据和风险准确率。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python、FastAPI、Pydantic、SQLAlchemy asyncio |
| Agent | DeepSeek OpenAI-compatible API、结构化计划、确定性工具注册表 |
| 数据 | 90 天 CSV/JSON 模拟数据、SQLite 开发存储、PostgreSQL 生产配置 |
| 前端 | Vue 3、TypeScript、Element Plus、Pinia、Vite |
| 验证 | pytest、Playwright、vue-tsc、Docker Compose |

## 运行链路

```text
用户问题 + 会话历史
  -> DeepSeek 结构化计划（可选）
  -> 白名单与最多 6 步校验
  -> 确定性分析工具
  -> 数据证据与风险策略
  -> DeepSeek 解释或确定性总结
  -> 建议持久化与人工审批
```

模型不能执行任意代码、修改指标、直接访问数据库或绕过审批。

## 主要页面

- 运营驾驶舱：90 天趋势、GMV 归因、漏斗和模拟预测
- 运营 Agent：多轮会话、执行模式、工具轨迹、证据和建议
- 商品分析：ABC、毛利、周转、投放、评价和竞品价差
- 客户分析：RFM、复购率和模拟 LTV
- 活动策略：目标化选品、打法和模拟收益
- 建议审批：意见、版本与审批审计
- 运行中心：耗时、Token、降级率和工具明细
- Agent 评测：质量指标与失败样例
- 运营知识库：作为商品资料、品牌规则和 SOP 的辅助模块

## 本地运行

项目本地可演示，不要求启动 Redis、PostgreSQL 或配置 DeepSeek API Key。

```powershell
# 安装依赖
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd frontend
npm install
cd ..

# 可选：重新生成 90 天数据
.venv\Scripts\python.exe scripts\generate_ecommerce_data.py --output data\ecommerce

# 后端
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001

# 前端（新终端）
cd frontend
$env:VITE_API_TARGET="http://127.0.0.1:8001"
npm run dev -- --host 127.0.0.1 --port 5173
```

打开 `http://127.0.0.1:5173/`。不配置 `DEEPSEEK_API_KEY` 时完整使用确定性降级；配置后启用真实结构化规划。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\evaluate_ecommerce_agent.py
cd frontend
npm run build
npm run test:e2e
```

## Demo 与生产边界

- `development`：SQLite 保存电商会话和审批，本地账号在 PostgreSQL 不可用时可降级，电商分析不依赖 Redis。
- `production`：可通过 `ECOMMERCE_DATABASE_URL` 切换 PostgreSQL；认证、限流和高风险动作继续 fail-closed。
- 活动收益与 GMV 预测均标注为“模拟测算”，不能作为真实商业承诺。

详细组件和数据流见 [架构文档](docs/architecture.md)，简历写法见 [简历项目描述](docs/resume.md)。
