from collections import Counter, defaultdict

from backend.ecommerce.intent_planner import IntentPlan
from backend.ecommerce.operations_tools import SandboxOperationsTools
from backend.ecommerce.schemas import EcommerceDataset


class OperationsSpecialistTeam:
    def __init__(self, dataset: EcommerceDataset):
        self.dataset = dataset
        self.tools = SandboxOperationsTools(dataset)

    def run(self, plan: IntentPlan) -> dict:
        handler = getattr(self, f"_{plan.intent}")
        report = handler(plan)
        report.setdefault("intent", plan.intent)
        report.setdefault("generation_mode", "analytics")
        report.setdefault("risks", [])
        return report

    def _competitive_analysis(self, plan: IntentPlan) -> dict:
        data = self.tools.competitor_snapshot(plan.product_id, plan.slots.get("days", 30), plan.slots.get("channel", "全渠道"))
        gap = data["price_comparison"]["price_gap_pct"]
        opportunities = ["围绕高频评价主题制作场景化内容", "对竞品常见促销机制进行小预算 A/B 测试"]
        if gap > 5:
            opportunities.insert(0, f"当前价格高于竞品均价 {gap:.2f}%，需要强化差异化卖点或测试价格带")
        else:
            opportunities.insert(0, f"当前价格相对竞品均价差异 {gap:.2f}%，具备价格沟通空间")
        return {
            "title": f"{data['product']['name']} · {data['channel']}竞品分析",
            "summary": f"基于近 {data['period_days']} 天竞品价格、促销与用户评价数据完成对比，未创建任何营销活动。",
            "findings": [f"自有售价 ¥{data['price_comparison']['own_price']}，竞品均价 ¥{data['price_comparison']['competitor_price']}，价差 {gap}%", *[f"评价关注：{item['topic']}" for item in data["review_signals"][:3]]],
            "price_comparison": data["price_comparison"], "review_signals": data["review_signals"], "competitor_promotions": data["competitor_promotions"],
            "opportunities": opportunities,
            "actions": ["先产出 3 组差异化内容进行点击率测试", "监控竞品价格与促销频次，每周更新对比", "以转化率和收藏率验证卖点，而不是直接创建活动"],
            "evidence": data["evidence"],
        }

    def _product_analysis(self, plan: IntentPlan) -> dict:
        data = self.tools.product_snapshot(plan.product_id, plan.slots.get("days", 30))
        metrics = data["metrics"]
        risks = []
        if metrics["stock"] <= metrics["safety_stock"]:
            risks.append("库存已接近或低于安全库存")
        return {"title": f"{data['product']['name']}商品分析", "summary": f"近 {data['period_days']} 天 GMV ¥{metrics['gmv']}，转化率 {metrics['conversion_rate_pct']}%，广告 ROI {metrics['ad_roi']}。", "findings": [f"销量 {metrics['units']} 件", f"库存 {metrics['stock']}，安全库存 {metrics['safety_stock']}"], "opportunities": ["按流量-加购-支付漏斗定位损失环节"], "actions": ["优先处理库存风险", "对低转化流量来源调整商品页卖点"], "risks": risks, "evidence": data["evidence"]}

    def _business_diagnosis(self, plan: IntentPlan) -> dict:
        snapshots = [self.tools.product_snapshot(item.product_id, plan.slots.get("days", 30)) for item in self.dataset.products]
        total_gmv = round(sum(item["metrics"]["gmv"] for item in snapshots), 2)
        ranked = sorted(snapshots, key=lambda item: item["metrics"]["gmv"], reverse=True)
        evidence = [entry for item in snapshots for entry in item["evidence"]]
        return {"title": "店铺经营诊断", "summary": f"近 {plan.slots.get('days', 30)} 天模拟店铺 GMV 为 ¥{total_gmv}，已完成商品贡献、流量、广告和库存联合诊断。", "findings": [f"GMV 最高商品：{ranked[0]['product']['name']} ¥{ranked[0]['metrics']['gmv']}", f"GMV 最低商品：{ranked[-1]['product']['name']} ¥{ranked[-1]['metrics']['gmv']}"], "opportunities": ["将预算向高 ROI 且库存健康的商品倾斜", "对低转化商品拆解流量与详情页问题"], "actions": ["先处理安全库存风险", "建立按商品监控的 GMV、CVR、ROI 日报"], "evidence": evidence}

    def _ad_optimization(self, plan: IntentPlan) -> dict:
        product_id = plan.product_id or self.dataset.products[0].product_id
        data = self.tools.product_snapshot(product_id, plan.slots.get("days", 30))
        roi = data["metrics"]["ad_roi"]
        return {"title": f"{data['product']['name']}广告优化", "summary": f"近 {data['period_days']} 天归因广告 ROI 为 {roi}。", "findings": [f"当前广告 ROI：{roi}", f"同期转化率：{data['metrics']['conversion_rate_pct']}%"], "opportunities": ["按渠道与关键词拆分高低转化流量"], "actions": ["保留高转化词并降低无转化词出价", "连续 3 天无转化的广告组降预算 20%", "预算调整后观察至少一个完整归因周期"], "evidence": data["evidence"]}

    def _customer_operations(self, plan: IntentPlan) -> dict:
        levels = Counter(item.member_level for item in self.dataset.customers)
        regions = Counter(item.region for item in self.dataset.customers)
        orders = defaultdict(int)
        for item in self.dataset.orders:
            if item.customer_id:
                orders[item.customer_id] += item.orders
        repeat = sum(1 for count in orders.values() if count > 1)
        evidence = [{"metric": "member_levels", "value": dict(levels), "period": "all", "source": "customers.csv", "sample_size": len(self.dataset.customers)}, {"metric": "repeat_customers", "value": repeat, "period": "all", "source": "orders.csv", "sample_size": len(orders)}]
        return {"title": "客户分层与复购机会", "summary": f"分析 {len(self.dataset.customers)} 名模拟客户，识别出 {repeat} 名重复购买客户。", "findings": [f"主要会员层级：{levels.most_common(1)[0][0]}", f"客户最多地区：{regions.most_common(1)[0][0]}"], "opportunities": ["对高价值未复购客户进行分层召回", "按地区和会员等级设计差异化权益"], "actions": ["建立 RFM 人群包", "对 30 天未复购高价值用户发送召回内容", "跟踪召回转化和退订率"], "evidence": evidence}

    def _marketing_strategy(self, plan: IntentPlan) -> dict:
        data = self.tools.product_snapshot(plan.product_id, plan.slots.get("days", 30))
        return {"title": f"{data['product']['name']}营销策略", "summary": "根据商品表现、库存和广告回报生成策略建议；本报告不会自动创建活动。", "findings": [f"GMV ¥{data['metrics']['gmv']}", f"库存 {data['metrics']['stock']}"], "opportunities": ["围绕核心使用场景建立内容矩阵", "先验证素材点击率，再扩大活动预算"], "actions": ["制作 3 套渠道化素材", "设置小预算测试组", "以转化率和 ROI 作为扩量门槛"], "evidence": data["evidence"]}

    def _content_generation(self, plan: IntentPlan) -> dict:
        product = next(item for item in self.dataset.products if item.product_id == plan.product_id)
        channel = plan.slots["channel"]
        return {"title": f"{product.name}{channel}推广文案", "channel": channel, "summary": f"已根据真实商品定位生成 {channel} 文案草稿。", "headline": f"{product.name}，让日常使用更轻松", "body": f"面向{channel}用户，突出“{product.positioning}”的真实定位，不虚构促销、认证或功效。", "selling_points": [product.positioning, "适合日常真实场景", f"当前售价 ¥{product.price}"], "opportunities": ["用两版标题进行点击率测试"], "actions": ["审核事实与平台合规性", "发布前补充真实产品图片"], "evidence": [{"metric": "product_positioning", "value": product.positioning, "period": "current", "source": "products.csv", "sample_size": 1}], "generation_mode": "template"}
