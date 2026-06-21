import logging

from config.settings import Settings
from models.order_plan import OrderPlan
from models.order_type import OrderType
from models.signal import SignalAnalysis
from trading.volume_normalizer import split_volume_for_zone
from trading.zone_order_type import resolve_zone_order_type
from trading.zone_price_distribution import evenly_spaced_prices
from trading.zone_resolver import resolve_zone

logger = logging.getLogger(__name__)


class ZoneOrderPlanner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, signal: SignalAnalysis) -> list[OrderPlan]:
        zone = resolve_zone(signal)
        if zone:
            return self._build_zone_plan(signal, zone)

        return self._build_standard_plan(signal)

    def _build_zone_plan(
        self,
        signal: SignalAnalysis,
        zone: tuple[float, float],
    ) -> list[OrderPlan]:
        zone_low, zone_high = zone
        total_volume = signal.volume or self._settings.default_volume
        order_type = resolve_zone_order_type(signal.order_type)

        volumes, order_count = split_volume_for_zone(
            total_volume,
            self._settings.max_order_per_group,
            self._settings.min_volume,
            self._settings.max_volume,
        )
        prices = evenly_spaced_prices(zone_low, zone_high, order_count)

        plans: list[OrderPlan] = []
        for index, volume in enumerate(volumes):
            plans.append(self._make_plan(
                signal,
                volume,
                prices[index],
                order_type,
            ))

        logger.info(
            "Zone plan %s-%s: %d %s order(s) at %s, vol each=%s",
            zone_low,
            zone_high,
            len(plans),
            order_type.value,
            prices,
            [plan.volume for plan in plans],
        )
        return plans

    def _build_standard_plan(self, signal: SignalAnalysis) -> list[OrderPlan]:
        total_volume = signal.volume or self._settings.default_volume
        entries = self._resolve_entries(signal, total_volume)
        tp_splits = self._resolve_tp_splits(signal, total_volume)
        plans: list[OrderPlan] = []

        for entry in entries:
            entry_vol = entry["volume"]
            entry_price = entry["price"]

            if not tp_splits:
                plans.append(self._make_plan(
                    signal, entry_vol, entry_price, signal.order_type,
                ))
                continue

            entry_share = entry_vol / total_volume if total_volume else 1.0
            for tp in tp_splits:
                plans.append(OrderPlan(
                    volume=_round_volume(tp["volume"] * entry_share),
                    entry_price=entry_price,
                    order_type=signal.order_type,
                    stop_loss=signal.stop_loss,
                    take_profit=tp["price"],
                    sl_pips=signal.sl_pips,
                    tp_pips=signal.tp_pips,
                ))

        return plans

    def _make_plan(
        self,
        signal: SignalAnalysis,
        volume: float,
        entry_price: float | None,
        order_type: OrderType,
    ) -> OrderPlan:
        return OrderPlan(
            volume=volume,
            entry_price=entry_price,
            order_type=order_type,
            stop_loss=signal.stop_loss,
            take_profit=signal.primary_take_profit,
            sl_pips=signal.sl_pips,
            tp_pips=signal.tp_pips,
        )

    def _resolve_entries(
        self,
        signal: SignalAnalysis,
        total_volume: float,
    ) -> list[dict]:
        if signal.entry_levels:
            defined_vol = sum(level.volume or 0 for level in signal.entry_levels)
            undefined_count = sum(1 for level in signal.entry_levels if level.volume is None)
            remaining = total_volume - defined_vol
            default_each = remaining / undefined_count if undefined_count else 0

            entries = []
            for level in sorted(signal.entry_levels, key=lambda item: item.level):
                volume = level.volume if level.volume is not None else default_each
                entries.append({
                    "price": level.price,
                    "volume": _round_volume(volume),
                })
            return entries

        return [{
            "price": signal.entry_price,
            "volume": _round_volume(total_volume),
        }]

    def _resolve_tp_splits(
        self,
        signal: SignalAnalysis,
        total_volume: float,
    ) -> list[dict]:
        if not signal.take_profits:
            return []

        sorted_tps = sorted(signal.take_profits, key=lambda tp: tp.level)
        defined_pct = sum(tp.volume_percent or 0 for tp in sorted_tps)
        undefined_count = sum(1 for tp in sorted_tps if tp.volume_percent is None)
        remaining_pct = 100.0 - defined_pct
        default_pct = remaining_pct / undefined_count if undefined_count else 0

        splits = []
        for tp in sorted_tps:
            pct = tp.volume_percent if tp.volume_percent is not None else default_pct
            splits.append({
                "price": tp.price,
                "volume": _round_volume(total_volume * pct / 100.0),
            })
        return splits


def _round_volume(value: float) -> float:
    return round(value, 2)
