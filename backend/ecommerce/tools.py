from backend.ecommerce.metrics import build_dashboard
from backend.ecommerce.schemas import EcommerceDataset, ProductAnalysis, ProductRecord, ToolTraceStep
from backend.ecommerce.segmentation import build_product_analysis


class EcommerceTools:
    def __init__(self, dataset: EcommerceDataset):
        self.dataset = dataset

    def get_kpi_snapshot(self):
        dashboard = build_dashboard(self.dataset)
        return dashboard, ToolTraceStep(
            tool_name="get_kpi_snapshot",
            step_title="读取经营指标快照",
            input={"range": "latest_vs_previous"},
            output_summary=f"GMV {dashboard.kpis['gmv'].value} 元，环比 {dashboard.kpis['gmv'].delta_pct}%。",
        )

    def explain_gmv_attribution(self):
        dashboard = build_dashboard(self.dataset)
        strongest = min(dashboard.gmv_attribution, key=lambda item: item.delta_value)
        return dashboard.gmv_attribution, ToolTraceStep(
            tool_name="explain_gmv_attribution",
            step_title="拆解 GMV 变化归因",
            input={"factors": "traffic,conversion,aov"},
            output_summary=f"{strongest.label}贡献 {strongest.delta_value} 元，是本次 GMV 下滑的主要解释项。",
        )

    def detect_anomalies(self):
        dashboard = build_dashboard(self.dataset)
        return dashboard.anomalies, ToolTraceStep(
            tool_name="detect_anomalies",
            step_title="识别经营异常",
            input={"scope": "sales_ads_inventory_reviews"},
            output_summary=f"识别 {len(dashboard.anomalies)} 个经营异常。",
        )

    def rank_products(self):
        products = build_product_analysis(self.dataset)
        return products, ToolTraceStep(
            tool_name="rank_products",
            step_title="商品分层与风险排序",
            input={"sort": "gmv_desc", "signals": "abc,margin,conversion,inventory,review,roi"},
            output_summary=f"完成 {len(products)} 个商品分层，最高 GMV 商品为 {products[0].name}。",
        )

    def generate_campaign_plan(self, goal: str = "大促增长"):
        normalized_goal = goal.strip() or "大促增长"
        products = build_product_analysis(self.dataset)
        product_records = {item.product_id: item for item in self.dataset.products}
        hero, clearance = _campaign_products(normalized_goal, products, product_records)
        plan = {
            "theme": _campaign_theme(normalized_goal),
            "hero_products": [item.model_dump() for item in hero],
            "clearance_products": [item.model_dump() for item in clearance],
            "strategy": _campaign_strategy(normalized_goal),
        }
        return plan, ToolTraceStep(
            tool_name="generate_campaign_plan",
            step_title="生成活动选品策略",
            input={"goal": normalized_goal},
            output_summary=f"围绕{normalized_goal}推荐 {len(hero)} 个主推商品和 {len(clearance)} 个补充商品。",
        )


def _campaign_theme(goal: str) -> str:
    if goal.endswith(("策略", "活动", "方案")):
        return goal
    return f"{goal}策略"


def _campaign_strategy(goal: str) -> list[str]:
    if any(keyword in goal for keyword in ("新品", "冷启动", "上新")):
        return ["新品先用低门槛券获取首批转化", "用高意图搜索词承接种草流量", "控制预算验证点击率和收藏加购"]
    if any(keyword in goal for keyword in ("清仓", "库存", "尾货")):
        return ["高库存商品配置阶梯满减", "风险商品先处理评价和售后解释", "清仓预算按库存周转天数排序"]
    if any(keyword in goal for keyword in ("复购", "会员", "老客")):
        return ["利润款绑定会员券提升复购", "主推款做加购提醒和短信召回", "低毛利商品不参与深折扣"]
    return ["主推款承接搜索流量", "利润款配置满减", "风险商品先处理评价和库存"]


def _campaign_products(
    goal: str,
    products: list[ProductAnalysis],
    product_records: dict[str, ProductRecord],
) -> tuple[list[ProductAnalysis], list[ProductAnalysis]]:
    if any(keyword in goal for keyword in ("新品", "冷启动", "上新")):
        hero = _top_products(products, lambda item: _launch_score(item, product_records), limit=3)
        clearance = _inventory_backups(products, exclude={item.product_id for item in hero}, limit=2)
        return hero, clearance

    if any(keyword in goal for keyword in ("清仓", "库存", "尾货")):
        hero = _top_products(products, lambda item: _clearance_score(item, product_records), limit=3)
        clearance = _inventory_backups(products, exclude={item.product_id for item in hero}, limit=2)
        return hero, clearance

    if any(keyword in goal for keyword in ("复购", "会员", "老客")):
        hero = _top_products(products, _repurchase_score, limit=3)
        clearance = _inventory_backups(products, exclude={item.product_id for item in hero}, limit=2)
        return hero, clearance

    hero = [item for item in products if item.segment in {"hero", "profit"} and not item.risk_tags][:3]
    clearance = _inventory_backups(products, exclude={item.product_id for item in hero}, limit=2)
    return hero, clearance


def _top_products(products: list[ProductAnalysis], score, limit: int) -> list[ProductAnalysis]:
    return sorted(products, key=lambda item: (score(item), item.gmv), reverse=True)[:limit]


def _inventory_backups(products: list[ProductAnalysis], exclude: set[str], limit: int) -> list[ProductAnalysis]:
    candidates = [item for item in products if item.product_id not in exclude]
    return _top_products(candidates, _clearance_inventory_score, limit)


def _launch_score(item: ProductAnalysis, product_records: dict[str, ProductRecord]) -> float:
    record = product_records[item.product_id]
    risk_penalty = 500 if "差评风险" in item.risk_tags or "投放低效" in item.risk_tags else 0
    return (
        (10000 if record.positioning == "new" else 0)
        + record.launch_date.toordinal() / 100
        + item.gross_margin_rate * 10
        + item.conversion_rate * 100
        - risk_penalty
    )


def _clearance_score(item: ProductAnalysis, product_records: dict[str, ProductRecord]) -> float:
    record = product_records[item.product_id]
    return (10000 if record.positioning == "clearance" else 0) + _clearance_inventory_score(item)


def _clearance_inventory_score(item: ProductAnalysis) -> float:
    stock_ratio = item.stock / item.safety_stock if item.safety_stock else 0
    return stock_ratio * 1000 + item.stock + item.inventory_turnover_days * 10


def _repurchase_score(item: ProductAnalysis) -> float:
    daily_use_bonus = 2000 if item.category in {"日用", "小家电", "服饰"} else 0
    risk_penalty = 4000 if "差评风险" in item.risk_tags or "投放低效" in item.risk_tags else 800 if item.risk_tags else 0
    return daily_use_bonus + item.gross_margin_rate * 100 + item.average_rating * 100 + item.orders * 10 - risk_penalty
