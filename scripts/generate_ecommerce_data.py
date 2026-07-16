import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path


PRODUCTS = [
    ("P001", "云感防晒衣", "服饰", 199, 92, "2026-05-01", "hero"),
    ("P002", "轻量跑步鞋", "鞋包", 329, 168, "2026-04-18", "profit"),
    ("P003", "便携榨汁杯", "小家电", 149, 78, "2026-03-20", "traffic"),
    ("P004", "智能体脂秤", "数码健康", 129, 64, "2026-02-10", "profit"),
    ("P005", "露营折叠椅", "户外", 89, 48, "2026-01-25", "clearance"),
    ("P006", "抗菌保温杯", "日用", 79, 35, "2026-06-12", "new"),
    ("P007", "儿童护眼台灯", "家居", 259, 136, "2026-04-03", "hero"),
    ("P008", "真无线降噪耳机", "数码", 399, 235, "2026-05-28", "risk"),
]


def _write(root: Path, name: str, headers: list[str], rows: list[tuple]) -> None:
    with (root / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)


def generate_dataset(output: Path, days: int = 90, seed: int = 20260716) -> None:
    rng = random.Random(seed)
    output.mkdir(parents=True, exist_ok=True)
    end = date(2026, 7, 15)
    dates = [end - timedelta(days=offset) for offset in reversed(range(days))]
    customers = [
        (f"C{i:04d}", (end - timedelta(days=rng.randint(20, 500))).isoformat(), rng.choice(["华东", "华南", "华北", "西南"]), rng.choice(["普通", "银卡", "金卡"]))
        for i in range(1, 241)
    ]

    orders, traffic, funnel, ads, reviews, competitors, campaigns = [], [], [], [], [], [], []
    for day_index, current in enumerate(dates):
        weekend = 1.16 if current.weekday() >= 5 else 1.0
        trend = 0.9 + day_index / max(days, 1) * 0.18
        for index, product in enumerate(PRODUCTS):
            product_id, _name, _category, price, _cost, *_ = product
            visitors = max(80, int((520 - index * 38) * weekend * trend + rng.randint(-35, 35)))
            conversion = max(0.015, 0.067 - index * 0.004 + rng.uniform(-0.008, 0.008))
            count = max(1, int(visitors * conversion))
            units = count + rng.randint(0, max(1, count // 5))
            gmv = round(units * price * rng.uniform(0.92, 1.0), 2)
            refund = round(price * rng.randint(0, 2), 2)
            customer_id = customers[(day_index * len(PRODUCTS) + index) % len(customers)][0]
            orders.append((current.isoformat(), product_id, count, units, gmv, refund, customer_id))
            impressions = visitors * rng.randint(7, 12)
            clicks = int(impressions * rng.uniform(0.07, 0.13))
            carts = min(visitors, int(visitors * rng.uniform(0.09, 0.18)))
            checkout = min(carts, int(carts * rng.uniform(0.62, 0.84)))
            refunded = min(count, int(refund > 0))
            traffic.append((current.isoformat(), product_id, impressions, visitors, carts))
            funnel.append((current.isoformat(), product_id, impressions, clicks, visitors, carts, checkout, count, refunded))
            spend = round(120 + index * 18 + rng.uniform(-20, 30), 2)
            attributed = round(spend * rng.uniform(1.35 if index == 7 else 1.9, 3.1), 2)
            ads.append((current.isoformat(), f"AD-{product_id}", product_id, rng.choice(["搜索", "信息流", "内容种草"]), spend, attributed, clicks))
            reviews.append((current.isoformat(), product_id, round(rng.uniform(3.4 if index == 7 else 4.1, 4.95), 1), rng.choice(["质量", "物流", "尺码", "使用体验"]), rng.randint(2, 18)))
            competitors.append((current.isoformat(), product_id, round(price * rng.uniform(0.86, 1.12), 2), rng.choice(["无", "满减", "平台券"])))
            if day_index % 14 in {5, 6}:
                baseline = round(gmv / rng.uniform(1.05, 1.22), 2)
                campaigns.append((f"CMP-{current:%Y%m%d}", current.isoformat(), product_id, "周末增长", round(gmv * 0.06, 2), gmv, baseline))

    # Keep the latest day as a stable diagnosis scenario for demos and regression tests.
    latest = end.isoformat()
    orders = [row for row in orders if row[0] != latest]
    orders.extend([
        (latest, "P001", 24, 27, 5373, 398, "C0001"),
        (latest, "P002", 18, 18, 5922, 0, "C0002"),
        (latest, "P003", 27, 27, 4023, 149, "C0003"),
        (latest, "P004", 14, 14, 1806, 0, "C0004"),
        (latest, "P005", 9, 12, 1068, 0, "C0005"),
        (latest, "P006", 15, 15, 1185, 0, "C0006"),
        (latest, "P007", 8, 8, 2072, 259, "C0007"),
        (latest, "P008", 6, 6, 2394, 798, "C0008"),
    ])
    traffic = [row for row in traffic if row[0] != latest]
    traffic.extend([
        (latest, "P001", 16950, 2125, 128), (latest, "P002", 10250, 1170, 113),
        (latest, "P003", 13100, 1530, 141), (latest, "P004", 7200, 760, 62),
        (latest, "P005", 5600, 590, 42), (latest, "P006", 8400, 1180, 74),
        (latest, "P007", 8050, 845, 48), (latest, "P008", 9200, 980, 53),
    ])
    ads = [row for row in ads if row[0] != latest]
    ads.extend([
        (latest, "C001", "P001", "搜索广告", 2600, 5200, 710),
        (latest, "C002", "P003", "信息流", 980, 4500, 455),
        (latest, "C003", "P008", "搜索广告", 1850, 3200, 420),
        (latest, "C004", "P006", "达人短视频", 760, 1800, 390),
        (latest, "C005", "P007", "信息流", 1100, 2400, 330),
    ])
    reviews = [row for row in reviews if row[0] != latest]
    reviews.extend([
        (latest, "P001", 3.6, "尺码偏小", 21), (latest, "P001", 3.8, "物流慢", 15),
        (latest, "P007", 3.5, "包装破损", 12), (latest, "P008", 3.4, "降噪不稳定", 17),
        (latest, "P003", 4.5, "便携好清洗", 29), (latest, "P006", 4.4, "保温效果好", 14),
    ])

    _write(output, "products.csv", ["product_id", "name", "category", "price", "cost", "launch_date", "positioning"], PRODUCTS)
    _write(output, "customers.csv", ["customer_id", "registered_at", "region", "member_level"], customers)
    _write(output, "orders.csv", ["date", "product_id", "orders", "units", "gmv", "refund_amount", "customer_id"], orders)
    _write(output, "traffic.csv", ["date", "product_id", "impressions", "visitors", "add_to_cart"], traffic)
    _write(output, "funnel.csv", ["date", "product_id", "impressions", "clicks", "visitors", "add_to_cart", "checkout", "paid_orders", "refunded_orders"], funnel)
    _write(output, "ad_spend.csv", ["date", "campaign_id", "product_id", "channel", "spend", "attributed_gmv", "clicks"], ads)
    _write(output, "inventory.csv", ["product_id", "stock", "safety_stock", "inbound_units", "lead_time_days"], [
        ("P001", 62, 80, 120, 3), ("P002", 210, 90, 0, 5),
        ("P003", 340, 120, 0, 4), ("P004", 160, 70, 80, 6),
        ("P005", 520, 100, 0, 2), ("P006", 48, 60, 160, 7),
        ("P007", 38, 75, 90, 4), ("P008", 95, 80, 0, 6),
    ])
    _write(output, "reviews.csv", ["date", "product_id", "rating", "topic", "comment_count"], reviews)
    _write(output, "competitors.csv", ["date", "product_id", "competitor_price", "competitor_promo"], competitors)
    _write(output, "campaigns.csv", ["campaign_id", "date", "product_id", "campaign_type", "discount_cost", "attributed_gmv", "baseline_gmv"], campaigns)
    rules = {"thresholds": {"gmv_drop_pct": -15, "low_roi": 1.8, "critical_stock_ratio": 1.0, "bad_rating": 3.8}, "risk_actions": {"high": "approval_required", "medium": "review_recommended", "low": "auto_allowed"}}
    (output / "operation_rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/ecommerce"))
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--seed", type=int, default=20260716)
    args = parser.parse_args()
    generate_dataset(args.output, args.days, args.seed)
