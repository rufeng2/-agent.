# 电商运营多 Agent 协作设计

## 目标

将单一执行节点升级为 Supervisor 驱动的多 Agent 协作图，同时保持现有 API、Job、Celery、持久化和前端结果协议兼容。

## 角色

- Supervisor Agent：根据问题选择 2-4 个专家，不直接访问分析工具。
- Data Analyst Agent：GMV、异常、漏斗和预测。
- Product Agent：商品分层、库存和竞品价格。
- Customer Agent：RFM、复购和客户价值。
- Campaign Agent：活动方案和活动效果。
- Risk Agent：检查证据覆盖、高风险动作和冲突。
- Report Agent：合并专家报告，生成最终 `AgentAnalysis`。

## 协作协议

每个专家具有独立名称、职责、工具白名单和结构化 `SpecialistReport` 输出。Supervisor 最少选择 Data Analyst 和一个业务专家；专家节点可并行执行。Risk Agent 接收全部专家报告，Report Agent 汇总工具轨迹、证据、警告和建议。最终结果增加 `agent_trace`，原字段保持不变。

## 可靠性

专家只调用白名单工具；单个专家失败不会阻断其他专家；无模型时使用确定性路由和总结；取消任务时停止进入专家节点。多 Agent 结果仍通过原有 Job/Celery 链路交付。

## 验收

- 综合经营问题至少调用两个专家。
- 不同业务问题路由到对应专家。
- 越权工具调用被拒绝。
- 输出包含 Supervisor、专家、Risk 和 Report 协作轨迹。
- 现有 API 和完整测试保持通过。
