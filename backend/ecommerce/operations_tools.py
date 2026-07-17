from collections import Counter
from datetime import timedelta

from backend.ecommerce.schemas import EcommerceDataset


class SandboxOperationsTools:
    def __init__(self, dataset: EcommerceDataset):
        self.dataset = dataset

    def competitor_snapshot(self, product_id: str, days: int = 30, channel: str = "全渠道") -> dict:
        product = next(item for item in self.dataset.products if item.product_id == product_id)
        rows = [item for item in self.dataset.competitors if item.product_id == product_id]
        latest = max(item.date for item in rows)
        period = [item for item in rows if item.date >= latest - timedelta(days=days - 1)]
        competitor_price = round(sum(item.competitor_price for item in period) / len(period), 2)
        gap = round((product.price - competitor_price) / competitor_price * 100, 2)
        reviews = [item for item in self.dataset.reviews if item.product_id == product_id and item.date >= latest - timedelta(days=days - 1)]
        topics = Counter(item.topic for item in reviews)
        promos = Counter(item.competitor_promo for item in period)
        evidence = [
            {"metric": "own_price", "value": product.price, "period": "current", "source": "products.csv", "sample_size": 1},
            {"metric": "competitor_avg_price", "value": competitor_price, "period": f"last_{days}_days", "source": "competitors.csv", "sample_size": len(period)},
            {"metric": "review_topics", "value": dict(topics), "period": f"last_{days}_days", "source": "reviews.csv", "sample_size": len(reviews)},
        ]
        return {
            "product": product.model_dump(mode="json"),
            "channel": channel,
            "period_days": days,
            "price_comparison": {"own_price": product.price, "competitor_price": competitor_price, "price_gap_pct": gap},
            "competitor_promotions": [{"promotion": key, "observations": value} for key, value in promos.most_common(5)],
            "review_signals": [{"topic": key, "comment_count": value} for key, value in topics.most_common(5)],
            "evidence": evidence,
        }

    def product_snapshot(self, product_id: str, days: int = 30) -> dict:
        product = next(item for item in self.dataset.products if item.product_id == product_id)
        latest = max(item.date for item in self.dataset.orders)
        start = latest - timedelta(days=days - 1)
        orders = [item for item in self.dataset.orders if item.product_id == product_id and item.date >= start]
        traffic = [item for item in self.dataset.traffic if item.product_id == product_id and item.date >= start]
        ads = [item for item in self.dataset.ad_spend if item.product_id == product_id and item.date >= start]
        inventory = next(item for item in self.dataset.inventory if item.product_id == product_id)
        gmv = sum(item.gmv for item in orders)
        visitors = sum(item.visitors for item in traffic)
        units = sum(item.units for item in orders)
        spend = sum(item.spend for item in ads)
        attributed = sum(item.attributed_gmv for item in ads)
        return {
            "product": product.model_dump(mode="json"), "period_days": days,
            "metrics": {"gmv": round(gmv, 2), "units": units, "conversion_rate_pct": round(len(orders) / visitors * 100, 2) if visitors else 0, "ad_roi": round(attributed / spend, 2) if spend else 0, "stock": inventory.stock, "safety_stock": inventory.safety_stock},
            "evidence": [
                {"metric": "orders", "value": len(orders), "period": f"last_{days}_days", "source": "orders.csv", "sample_size": len(orders)},
                {"metric": "traffic", "value": visitors, "period": f"last_{days}_days", "source": "traffic.csv", "sample_size": len(traffic)},
                {"metric": "ad_spend", "value": round(spend, 2), "period": f"last_{days}_days", "source": "ad_spend.csv", "sample_size": len(ads)},
            ],
        }
