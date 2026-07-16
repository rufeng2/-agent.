from collections import Counter, defaultdict

from backend.ecommerce.metrics import latest_date, safe_div
from backend.ecommerce.schemas import EcommerceDataset, RfmAnalysis, RfmCustomer


def analyze_rfm(dataset: EcommerceDataset) -> RfmAnalysis:
    end = latest_date(dataset)
    last_order = {}
    frequency = Counter()
    monetary = defaultdict(float)
    for row in dataset.orders:
        if not row.customer_id:
            continue
        last_order[row.customer_id] = max(last_order.get(row.customer_id, row.date), row.date)
        frequency[row.customer_id] += row.orders
        monetary[row.customer_id] += row.gmv

    customers = []
    for customer_id in sorted(last_order):
        recency = (end - last_order[customer_id]).days
        freq = frequency[customer_id]
        amount = round(monetary[customer_id], 2)
        if recency <= 14 and freq >= 80:
            segment = "高价值"
        elif recency <= 30 and freq >= 30:
            segment = "潜力"
        elif recency > 45:
            segment = "流失风险"
        else:
            segment = "一般"
        customers.append(RfmCustomer(customer_id=customer_id, recency_days=recency, frequency=freq, monetary=amount, segment=segment))
    counts = Counter(item.segment for item in customers)
    repeat = sum(1 for item in customers if item.frequency > 1)
    return RfmAnalysis(
        customers=customers,
        segment_counts=dict(counts),
        repeat_purchase_rate=round(safe_div(repeat, len(customers)) * 100, 2),
        average_ltv=round(safe_div(sum(item.monetary for item in customers), len(customers)), 2),
    )
