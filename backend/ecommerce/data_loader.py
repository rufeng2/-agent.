import csv
import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from backend.ecommerce.schemas import (
    AdSpendRecord,
    CampaignRecord,
    CompetitorRecord,
    CustomerRecord,
    EcommerceDataset,
    InventoryRecord,
    OperationRules,
    OrderRecord,
    ProductRecord,
    ReviewRecord,
    FunnelRecord,
    TrafficRecord,
)

T = TypeVar("T", bound=BaseModel)


class EcommerceDataLoader:
    def __init__(self, root: Path | str = Path("data/ecommerce")):
        self.root = Path(root)
        self._cached_signature: tuple[tuple[str, int, int], ...] | None = None
        self._cached_dataset: EcommerceDataset | None = None

    def load_cached(self) -> EcommerceDataset:
        signature = tuple(
            (name, (self.root / name).stat().st_mtime_ns, (self.root / name).stat().st_size)
            for name in self.required_files()
        )
        if self._cached_dataset is None or signature != self._cached_signature:
            self._cached_dataset = self.load()
            self._cached_signature = signature
        return self._cached_dataset

    def load(self) -> EcommerceDataset:
        missing = [name for name in self.required_files() if not (self.root / name).exists()]
        if missing:
            raise FileNotFoundError(f"Missing ecommerce demo data files in {self.root}: {', '.join(missing)}")

        return EcommerceDataset(
            products=self._read_csv("products.csv", ProductRecord),
            orders=self._read_csv("orders.csv", OrderRecord),
            traffic=self._read_csv("traffic.csv", TrafficRecord),
            ad_spend=self._read_csv("ad_spend.csv", AdSpendRecord),
            inventory=self._read_csv("inventory.csv", InventoryRecord),
            reviews=self._read_csv("reviews.csv", ReviewRecord),
            competitors=self._read_csv("competitors.csv", CompetitorRecord),
            customers=self._read_csv("customers.csv", CustomerRecord),
            funnel=self._read_csv("funnel.csv", FunnelRecord),
            campaigns=self._read_csv("campaigns.csv", CampaignRecord),
            rules=OperationRules.model_validate(json.loads((self.root / "operation_rules.json").read_text(encoding="utf-8"))),
        )

    @staticmethod
    def required_files() -> list[str]:
        return [
            "products.csv",
            "orders.csv",
            "traffic.csv",
            "ad_spend.csv",
            "inventory.csv",
            "reviews.csv",
            "competitors.csv",
            "customers.csv",
            "funnel.csv",
            "campaigns.csv",
            "operation_rules.json",
        ]

    def _read_csv(self, filename: str, model: type[T]) -> list[T]:
        with (self.root / filename).open("r", encoding="utf-8-sig", newline="") as handle:
            return [model.model_validate(row) for row in csv.DictReader(handle)]
