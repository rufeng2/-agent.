from collections import defaultdict
from datetime import timedelta

from backend.ecommerce.metrics import latest_date, safe_div
from backend.ecommerce.schemas import EcommerceDataset, ForecastPoint, GmvForecast


def forecast_gmv(dataset: EcommerceDataset, horizon: int = 7) -> GmvForecast:
    daily = defaultdict(float)
    for row in dataset.orders:
        daily[row.date] += row.gmv
    series = sorted(daily.items())
    recent = series[-28:]
    n = len(recent)
    x_mean = (n - 1) / 2
    y_mean = safe_div(sum(value for _, value in recent), n)
    denominator = sum((index - x_mean) ** 2 for index in range(n))
    slope = safe_div(sum((index - x_mean) * (value - y_mean) for index, (_, value) in enumerate(recent)), denominator)
    weekday_average = defaultdict(list)
    for day, value in recent:
        weekday_average[day.weekday()].append(value)
    overall = y_mean or 1
    factors = {key: safe_div(sum(values) / len(values), overall) for key, values in weekday_average.items()}
    residual = sum(abs(value - (y_mean + slope * (index - x_mean))) for index, (_, value) in enumerate(recent)) / max(n, 1)
    last = latest_date(dataset)
    points = []
    for offset in range(1, horizon + 1):
        target = last + timedelta(days=offset)
        predicted = max(0, (y_mean + slope * (n - 1 + offset - x_mean)) * factors.get(target.weekday(), 1))
        points.append(ForecastPoint(
            date=target.isoformat(), predicted_gmv=round(predicted, 2),
            lower=round(max(0, predicted - residual), 2), upper=round(predicted + residual, 2),
        ))
    return GmvForecast(method="linear_trend_7d_seasonality", points=points)
