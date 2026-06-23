from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MetaApiTradingSnapshot:
    positions: list[dict]
    orders: list[dict]


class MetaApiTradingSnapshotService:
    """Positions va orders ni ketma-ket, bitta RPC sessiyada oladi."""

    async def fetch(self, connection: Any) -> MetaApiTradingSnapshot:
        positions = await connection.get_positions()
        orders = await connection.get_orders()
        return MetaApiTradingSnapshot(
            positions=list(positions or []),
            orders=list(orders or []),
        )
