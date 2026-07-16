import random
from datetime import date, timedelta

from pydantic import BaseModel

from backend.ecommerce.metrics import safe_div
from backend.ecommerce.schemas import (
    AdSpendRecord,
    CompetitorRecord,
    EcommerceDataset,
    FunnelRecord,
    OrderRecord,
    ReviewRecord,
    TrafficRecord,
)
from backend.ecommerce.segmentation import build_product_analysis


class SimulationSnapshot(BaseModel):
    step: int
    current_date: date
    seed: int
    version: int = 1
    events: list[str] = []


class SimulationResult(BaseModel):
    state: SimulationSnapshot
    dataset: EcommerceDataset
    deltas: dict[str, dict[str, float]]


class SimulationEngine:
    EVENT_TYPES = ("promotion", "negative_review", "low_stock", "replenishment", "competitor_cut", "ad_improvement")

    @classmethod
    def events_for_step(cls, dataset: EcommerceDataset, step: int, seed: int) -> list[str]:
        if step <= 0:
            return []
        rng = random.Random(seed + step * 1009)
        products = rng.sample(dataset.products, 2)
        event_types = rng.sample(cls.EVENT_TYPES, 2)
        labels = {
            "promotion": "大促流量上涨",
            "negative_review": "差评导致转化下降",
            "low_stock": "低库存限制销量",
            "replenishment": "补货到仓",
            "competitor_cut": "竞品降价",
            "ad_improvement": "广告素材优化",
        }
        return [f"{products[index].name}：{labels[event_type]}" for index, event_type in enumerate(event_types)]

    @classmethod
    def apply(cls, baseline: EcommerceDataset, step: int, seed: int = 20260716, version: int = 1) -> SimulationResult:
        dataset = baseline.model_copy(deep=True)
        initial = {item.product_id: item for item in build_product_analysis(dataset)}
        baseline_date = max(row.date for row in dataset.orders)
        events: list[str] = []
        for current_step in range(1, max(0, step) + 1):
            events = cls._advance(dataset, baseline_date + timedelta(days=current_step), current_step, seed)
        final = {item.product_id: item for item in build_product_analysis(dataset)}
        fields = ("gmv", "orders", "conversion_rate", "stock", "ad_roi", "average_rating", "competitor_price")
        competitor_initial = _competitor_prices(baseline)
        competitor_final = _competitor_prices(dataset)
        deltas = {}
        for product_id, item in final.items():
            before = initial[product_id]
            values = {
                "gmv": item.gmv - before.gmv,
                "orders": item.orders - before.orders,
                "conversion_rate": item.conversion_rate - before.conversion_rate,
                "stock": item.stock - before.stock,
                "ad_roi": item.ad_roi - before.ad_roi,
                "average_rating": item.average_rating - before.average_rating,
                "competitor_price": competitor_final[product_id] - competitor_initial[product_id],
            }
            deltas[product_id] = {field: round(float(values[field]), 2) for field in fields}
        return SimulationResult(
            state=SimulationSnapshot(step=step, current_date=baseline_date + timedelta(days=step), seed=seed, version=version, events=events),
            dataset=dataset,
            deltas=deltas,
        )

    @classmethod
    def _advance(cls, dataset: EcommerceDataset, current_date: date, step: int, seed: int) -> list[str]:
        rng = random.Random(seed + step * 1009)
        products = rng.sample(dataset.products, 2)
        event_types = rng.sample(cls.EVENT_TYPES, 2)
        event_by_product = {products[index].product_id: event_type for index, event_type in enumerate(event_types)}
        events = cls.events_for_step(dataset, step, seed)
        previous_orders = _latest_by_product(dataset.orders)
        previous_traffic = _latest_by_product(dataset.traffic)
        previous_ads = _latest_by_product(dataset.ad_spend)
        previous_reviews = _latest_by_product(dataset.reviews)
        previous_competitors = _latest_by_product(dataset.competitors)
        inventory = {row.product_id: row for row in dataset.inventory}

        for index, product in enumerate(dataset.products):
            product_id = product.product_id
            event = event_by_product.get(product_id, "")
            old_order = previous_orders[product_id]
            old_traffic = previous_traffic[product_id]
            visitor_factor = rng.uniform(0.9, 1.12) * (1.3 if event == "promotion" else 1)
            visitors = max(20, int(old_traffic.visitors * visitor_factor))
            conversion = safe_div(old_order.orders, old_traffic.visitors) * rng.uniform(0.92, 1.08)
            if event == "negative_review":
                conversion *= 0.72
            if event == "ad_improvement":
                conversion *= 1.12
            orders = max(1, int(visitors * conversion))
            inv = inventory[product_id]
            if event == "replenishment":
                inv.stock += max(inv.inbound_units, inv.safety_stock)
                inv.inbound_units = 0
            if event == "low_stock":
                orders = min(orders, max(1, inv.stock // 3))
            units = min(inv.stock, max(orders, int(orders * rng.uniform(1.0, 1.18))))
            inv.stock = max(0, inv.stock - units)
            gmv = round(units * product.price * rng.uniform(0.92, 1.0), 2)
            refund_amount = round(product.price * (1 if event == "negative_review" else rng.choice([0, 0, 0, 1])), 2)
            customer_id = f"C{((step * 8 + index) % max(len(dataset.customers), 1)) + 1:04d}"
            dataset.orders.append(OrderRecord(date=current_date, product_id=product_id, orders=orders, units=units, gmv=gmv, refund_amount=refund_amount, customer_id=customer_id))
            impressions = max(visitors, int(visitors * rng.uniform(7, 11)))
            clicks = max(visitors, int(impressions * rng.uniform(0.1, 0.16)))
            carts = min(visitors, max(orders, int(visitors * rng.uniform(0.08, 0.18))))
            checkout = min(carts, max(orders, int(carts * rng.uniform(0.65, 0.9))))
            dataset.traffic.append(TrafficRecord(date=current_date, product_id=product_id, impressions=impressions, visitors=visitors, add_to_cart=carts))
            dataset.funnel.append(FunnelRecord(date=current_date, product_id=product_id, impressions=impressions, clicks=clicks, visitors=visitors, add_to_cart=carts, checkout=checkout, paid_orders=orders, refunded_orders=int(refund_amount > 0)))
            old_ad = previous_ads.get(product_id)
            spend = round((old_ad.spend if old_ad else 200) * rng.uniform(0.9, 1.1), 2)
            roi_factor = rng.uniform(1.8, 3.2) * (1.25 if event == "ad_improvement" else 1)
            dataset.ad_spend.append(AdSpendRecord(date=current_date, campaign_id=f"SIM-{step}-{product_id}", product_id=product_id, channel=old_ad.channel if old_ad else "搜索", spend=spend, attributed_gmv=round(spend * roi_factor, 2), clicks=clicks))
            old_review = previous_reviews.get(product_id)
            rating = old_review.rating if old_review else 4.5
            rating += -0.7 if event == "negative_review" else rng.uniform(-0.1, 0.12)
            dataset.reviews.append(ReviewRecord(date=current_date, product_id=product_id, rating=round(min(5, max(1, rating)), 1), topic="模拟经营事件", comment_count=rng.randint(5, 24)))
            old_competitor = previous_competitors[product_id]
            competitor_price = old_competitor.competitor_price * (0.88 if event == "competitor_cut" else rng.uniform(0.98, 1.02))
            dataset.competitors.append(CompetitorRecord(date=current_date, product_id=product_id, competitor_price=round(max(1, competitor_price), 2), competitor_promo="模拟降价" if event == "competitor_cut" else "无"))
        return events


def _latest_by_product(rows):
    latest = {}
    for row in sorted(rows, key=lambda item: item.date):
        latest[row.product_id] = row
    return latest


def _competitor_prices(dataset: EcommerceDataset) -> dict[str, float]:
    return {product_id: row.competitor_price for product_id, row in _latest_by_product(dataset.competitors).items()}
