from uuid import NAMESPACE_URL, uuid5

from backend.ecommerce.competitors import analyze_competitor_prices
from backend.ecommerce.schemas import EcommerceDataset
from backend.ecommerce.segmentation import build_product_analysis


class GrowthWorkflowService:
    def __init__(self, dataset: EcommerceDataset):
        self.dataset = dataset

    def generate(self, product_id: str, platform: str, market_keyword: str) -> dict:
        product = next((item for item in self.dataset.products if item.product_id == product_id), None)
        if product is None:
            raise KeyError(product_id)
        analysis = next(item for item in build_product_analysis(self.dataset) if item.product_id == product_id)
        competitor = next(item for item in analyze_competitor_prices(self.dataset) if item.product_id == product_id)
        review_topics = [item.topic for item in self.dataset.reviews if item.product_id == product_id]
        research = {
            "agent": "market_research",
            "keyword": market_keyword.strip() or product.category,
            "opportunity_score": round(max(1, min(100, 62 + analysis.conversion_rate * 80 + analysis.average_rating * 3 - max(0, competitor.price_index - 100) / 2))),
            "price_position": "advantage" if competitor.price_index <= 100 else "premium",
            "competitor_price": competitor.competitor_price,
            "customer_signals": list(dict.fromkeys(review_topics))[:4],
            "insight": f"{product.name} has a {competitor.price_index} price index and {analysis.average_rating} rating in the simulated market.",
        }
        listing = self._write_listing(product, platform, research)
        compliance = self.review_compliance(listing)
        return {
            "product_id": product_id,
            "product_name": product.name,
            "platform": platform,
            "market_research": research,
            "listing": listing,
            "compliance": compliance,
            "dag": self._dag(compliance["status"]),
        }

    def _write_listing(self, product, platform: str, research: dict) -> dict:
        keyword = research["keyword"]
        return {
            "agent": "listing_writer",
            "platform": platform,
            "title": f"{product.name} | {keyword} Essential for Everyday Use",
            "bullet_points": [
                f"Designed for {keyword} use with practical everyday performance",
                f"Built for shoppers comparing products in the {product.category} category",
                "Clear product information supports confident purchase decisions",
                "Compact presentation works for home, travel, and gifting scenarios",
                "Package includes the product and a straightforward usage guide",
            ],
            "search_terms": list(dict.fromkeys([keyword, product.category, product.name, "everyday essential"])),
            "description": f"A data-informed listing draft for {product.name}, generated from simulated product and competitor signals.",
        }

    def review_compliance(self, listing: dict) -> dict:
        text = " ".join([listing.get("title", ""), *listing.get("bullet_points", [])]).lower()
        rules = {
            "absolute_claim": ("best", "no.1", "guaranteed", "100%"),
            "medical_claim": ("cure", "treat disease", "medical treatment"),
        }
        issues = [
            {"rule": rule, "severity": "high", "message": f"Restricted claim detected: {word}"}
            for rule, words in rules.items() for word in words if word in text
        ]
        if len(listing.get("title", "")) > 180:
            issues.append({"rule": "title_length", "severity": "medium", "message": "Title exceeds 180 characters"})
        return {"agent": "compliance_reviewer", "status": "blocked" if issues else "passed", "issues": issues, "checked_rules": [*rules, "title_length"]}

    def publish(self, workflow: dict, recommendation_status: str, recommendation_id: str) -> dict:
        if recommendation_status != "approved":
            raise PermissionError("Human approval is required before publishing")
        if workflow.get("compliance", {}).get("status") != "passed":
            raise PermissionError("Compliance review must pass before publishing")
        receipt_id = str(uuid5(NAMESPACE_URL, f"ecommerce-sandbox:{recommendation_id}:{workflow['platform']}"))
        return {
            "receipt_id": receipt_id,
            "environment": "sandbox",
            "platform": workflow["platform"],
            "external_listing_id": f"DEMO-{receipt_id[:8].upper()}",
            "status": "published",
            "message": "Simulated publish completed; no external commerce platform was called.",
        }

    @staticmethod
    def _dag(compliance_status: str) -> list[dict]:
        return [
            {"agent": "market_research", "status": "completed"},
            {"agent": "listing_writer", "status": "completed"},
            {"agent": "compliance_reviewer", "status": compliance_status},
            {"agent": "human_approval", "status": "pending" if compliance_status == "passed" else "blocked"},
            {"agent": "sandbox_publisher", "status": "waiting" if compliance_status == "passed" else "blocked"},
        ]
