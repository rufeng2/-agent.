from backend.ecommerce.anomaly import detect_anomalies
from backend.ecommerce.customers import analyze_rfm
from backend.ecommerce.metrics import build_dashboard, latest_date
from backend.ecommerce.schemas import EcommerceDataset
from backend.ecommerce.segmentation import build_product_analysis


DOMAINS = (
    ("store_product", "店铺与商品", "商品信息、价格、陈列与库存"),
    ("marketing", "营销与推广", "广告、自然流量与活动执行"),
    ("analytics", "数据分析", "监控指标、定位原因与复盘"),
    ("customer_service", "客户服务", "售后、满意度与用户召回"),
    ("team", "团队协同", "任务分工、进度与跨部门协作"),
    ("supply_chain", "供应链", "补货、库存结构与交付风险"),
    ("platform_incident", "平台与应急", "异常响应、止损与恢复"),
)


def build_operations_center(dataset: EcommerceDataset) -> dict:
    dashboard = build_dashboard(dataset)
    anomalies = detect_anomalies(dataset)
    products = build_product_analysis(dataset)
    rfm = analyze_rfm(dataset)
    day = latest_date(dataset)
    high_anomalies = [item for item in anomalies if item.severity == "high"]
    low_stock = [item for item in dataset.inventory if item.stock <= item.safety_stock]
    low_roi = [item for item in anomalies if item.metric == "ad_roi"]
    reviews = [item for item in dataset.reviews if item.date == day]
    negative_reviews = [item for item in reviews if item.rating < 4]
    refund_rate = dashboard.kpis["refund_rate"].value
    top_product = products[0]
    risk_product = next((item for item in products if item.risk_tags), top_product)

    tasks = [
        _task("analytics-daily", "analytics", "复盘今日 GMV 波动并确认主要损失来源", "数据运营", "P0" if high_anomalies else "P1", "今日 10:00", [f"GMV 环比 {dashboard.kpis['gmv'].delta_pct}%", f"发现 {len(anomalies)} 项经营异常"], "输出流量、转化率、客单价贡献和第一止损动作"),
        _task("product-content", "store_product", f"检查 {risk_product.name} 的价格、详情页和风险标签", "商品运营", "P1", "今日 14:00", [f"商品分层 {risk_product.segment}", f"风险标签：{'、'.join(risk_product.risk_tags) or '无'}"], "商品信息完整率 100%，明确继续主推或降权"),
        _task("marketing-roi", "marketing", "处理低 ROI 广告并重排今日预算", "投放运营", "P0" if low_roi else "P2", "今日 11:00", [f"广告 ROI {dashboard.kpis['ad_roi'].value}", f"低效计划 {len(low_roi)} 个"], "低效计划完成暂停或降预算，预算调整有审批记录"),
        _task("customer-voice", "customer_service", "处理退款与低评分反馈并回传商品问题", "客服主管", "P1" if negative_reviews or refund_rate > 5 else "P2", "今日 16:00", [f"退款率 {refund_rate}%", f"低评分主题 {len(negative_reviews)} 个"], "高优先级售后当日闭环，形成问题主题清单"),
        _task("team-sync", "team", "召开运营晨会并确认跨部门任务负责人", "运营负责人", "P1", "今日 09:30", [f"今日待办 {7} 项", "涉及商品、投放、客服、仓储"], "所有 P0/P1 任务均有负责人、截止时间和验收指标"),
        _task("supply-replenish", "supply_chain", "确认低库存 SKU 的补货量与到仓时间", "供应链运营", "P0" if low_stock else "P2", "今日 12:00", [f"低于安全库存 SKU {len(low_stock)} 个", f"最长补货周期 {max((item.lead_time_days for item in dataset.inventory), default=0)} 天"], "高风险 SKU 给出补货量、到仓日期和活动限量"),
        _task("incident-response", "platform_incident", "检查经营异常并更新应急处置状态", "值班运营", "P0" if high_anomalies else "P2", "持续监控", [f"高危异常 {len(high_anomalies)} 项", f"系统数据日期 {day.isoformat()}"], "高危异常 30 分钟内确认影响范围和止损方案"),
    ]
    workload = []
    for owner in dict.fromkeys(task["owner"] for task in tasks):
        owned = [task for task in tasks if task["owner"] == owner]
        workload.append({"owner": owner, "tasks": len(owned), "urgent": sum(task["priority"] == "P0" for task in owned)})

    incident_status = "critical" if len(high_anomalies) >= 2 else "attention" if anomalies else "normal"
    return {
        "date": day.isoformat(),
        "domains": [{"id": key, "name": name, "scope": scope} for key, name, scope in DOMAINS],
        "tasks": tasks,
        "customer_service": {"refund_rate": refund_rate, "negative_review_topics": len(negative_reviews), "rfm_customers": len(rfm.customers)},
        "supply_chain": {"low_stock_skus": len(low_stock), "average_lead_time_days": round(sum(item.lead_time_days for item in dataset.inventory) / max(len(dataset.inventory), 1), 1)},
        "incident": {"status": incident_status, "active_anomalies": len(anomalies), "high_severity": len(high_anomalies)},
        "team_workload": workload,
    }


def _task(task_id: str, domain: str, title: str, owner: str, priority: str, deadline: str, evidence: list[str], acceptance_metric: str) -> dict:
    return {"id": task_id, "domain": domain, "title": title, "owner": owner, "priority": priority, "deadline": deadline, "evidence": evidence, "acceptance_metric": acceptance_metric, "status": "todo"}
