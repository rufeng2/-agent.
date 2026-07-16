from dataclasses import dataclass


@dataclass(frozen=True)
class OperationScenario:
    id: str
    intent: str
    pain_point: str
    decision: str
    agents: tuple[str, ...]
    keywords: tuple[str, ...]


SCENARIOS = (
    OperationScenario("product_recommendation", "product_recommendation", "选品依赖经验，难以快速确定优先商品", "选出一个可进入主推评估的商品", ("product",), ("选一个商品", "商品推荐", "推荐商品", "推荐一个商品", "选品推荐")),
    OperationScenario("stockout_before_campaign", "inventory_risk", "活动放量前库存不足可能导致断货和流量浪费", "确定补货优先级并控制活动放量", ("product", "campaign"), ("活动前检查库存", "大促库存", "断货", "安全库存", "补货周期")),
    OperationScenario("ad_budget_waste", "ad_review", "广告持续消耗预算但未带来有效成交", "暂停低效计划并重新分配预算", ("data_analyst", "product"), ("广告烧钱", "广告花费", "ROI 太低", "ROI太低", "低效广告", "投放预算")),
    OperationScenario("review_conversion_loss", "review_conversion", "差评和商品信息问题正在拖累详情页转化", "定位问题商品并优先修复评价与内容", ("product", "data_analyst"), ("差评", "评分下降", "评价拖累", "详情页转化")),
    OperationScenario("competitor_price_cut", "competitor_analysis", "竞品降价可能造成价格竞争力和转化下降", "判断是否跟价、促销或保持价值定位", ("product",), ("竞品降价", "竞品价格", "价格竞争力", "价格指数")),
    OperationScenario("customer_churn", "customer_analysis", "高价值客户复购下降，召回资源缺少优先级", "识别流失人群并制定分层召回动作", ("customer", "campaign"), ("老客流失", "复购下降", "流失风险客户", "会员复购", "高价值用户")),
    OperationScenario("new_product_launch", "campaign_planning", "新品缺少历史销量，冷启动预算和内容容易浪费", "选择新品承接策略并设置小预算验证", ("product", "campaign"), ("新品冷启动", "新品上市", "新品推广", "新品怎么推", "从 0", "从0", "完整方案")),
    OperationScenario("campaign_selection", "campaign_planning", "活动资源有限，主推商品和优惠策略难以取舍", "确定活动选品、优惠与风险商品", ("product", "campaign"), ("参加大促", "大促选品", "活动选品", "制定大促")),
    OperationScenario("funnel_loss", "funnel_analysis", "流量进入店铺后在关键环节大量流失", "找到最大流失环节并确定优化顺序", ("data_analyst",), ("漏斗", "加购后", "没有支付", "转化环节")),
    OperationScenario("gmv_drop", "business_diagnosis", "GMV 下滑但团队无法判断是流量、转化还是客单价导致", "量化主要损失来源并安排止损动作", ("data_analyst", "product"), ("GMV为什么下降", "GMV 为什么下降", "GMV下滑", "GMV 下滑", "销售额下降", "经营异常")),
)


def detect_operation_scenario(question: str) -> OperationScenario | None:
    normalized = question.strip()
    return next((scenario for scenario in SCENARIOS if any(word.lower() in normalized.lower() for word in scenario.keywords)), None)
