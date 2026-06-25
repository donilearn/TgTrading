from dataclasses import dataclass


@dataclass(frozen=True)
class TradingSnapshot:
    positions: list[dict]
    orders: list[dict]
