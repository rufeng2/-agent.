from backend.ecommerce.metrics import latest_date, safe_div
from backend.ecommerce.schemas import CompetitorPriceAnalysis, EcommerceDataset


def analyze_competitor_prices(dataset: EcommerceDataset) -> list[CompetitorPriceAnalysis]:
    target = latest_date(dataset)
    latest = {row.product_id: row for row in dataset.competitors if row.date == target}
    results = []
    for product in dataset.products:
        row = latest[product.product_id]
        results.append(CompetitorPriceAnalysis(
            product_id=product.product_id,
            name=product.name,
            own_price=product.price,
            competitor_price=row.competitor_price,
            price_gap=round(product.price - row.competitor_price, 2),
            price_index=round(safe_div(product.price, row.competitor_price) * 100, 2),
            competitor_promo=row.competitor_promo,
        ))
    return results
