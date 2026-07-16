from backend.ecommerce.schemas import Evidence, ToolResult
from backend.ecommerce.tools import EcommerceTools


class EcommerceToolRegistry:
    def __init__(self, tools: EcommerceTools):
        self.tools = tools

    def execute(self, name: str, arguments: dict):
        if name == "generate_campaign_plan":
            value, trace = self.tools.generate_campaign_plan(str(arguments.get("goal", "大促增长")))
            evidence = [
                Evidence(label="主推商品", value=item["name"], rule=f"goal={arguments.get('goal', '大促增长')}")
                for item in value["hero_products"]
            ]
            return ToolResult(tool_name=name, input=arguments, metrics={"hero_products": len(value["hero_products"]), "clearance_products": len(value["clearance_products"])}, evidence=evidence, summary=trace.output_summary), trace
        if name in {"analyze_conversion_funnel", "analyze_customer_rfm", "analyze_campaign_effect", "analyze_competitor_price", "forecast_gmv"}:
            return getattr(self.tools, name)()
        if name == "get_kpi_snapshot":
            value, trace = self.tools.get_kpi_snapshot()
            evidence = [Evidence(label=item.label, value=f"{item.value}{item.unit}", baseline=f"环比 {item.delta_pct}%") for item in value.kpis.values()]
            return ToolResult(tool_name=name, input=arguments, metrics={key: item.value for key, item in value.kpis.items()}, evidence=evidence, summary=trace.output_summary), trace
        if name == "explain_gmv_attribution":
            value, trace = self.tools.explain_gmv_attribution()
            evidence = [Evidence(label=item.label, value=f"{item.delta_value} 元", baseline=f"贡献度 {item.contribution_pct}%", rule=item.insight) for item in value]
            return ToolResult(tool_name=name, input=arguments, metrics={item.factor: item.delta_value for item in value}, evidence=evidence, summary=trace.output_summary), trace
        if name == "detect_anomalies":
            value, trace = self.tools.detect_anomalies()
            evidence = [item for anomaly in value for item in anomaly.evidence]
            return ToolResult(tool_name=name, input=arguments, metrics={"anomalies": len(value)}, evidence=evidence, summary=trace.output_summary), trace
        if name == "rank_products":
            value, trace = self.tools.rank_products()
            evidence = [Evidence(label=item.name, value=f"GMV {item.gmv} 元", rule=",".join(item.risk_tags) or item.segment) for item in value[:5]]
            return ToolResult(tool_name=name, input=arguments, metrics={"products": len(value)}, evidence=evidence, summary=trace.output_summary), trace
        raise ValueError(f"Tool is not registered: {name}")
