from config.settings import Settings
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo


def format_analysis_context(
    existing_orders: list[ExistingOrder],
    market: list[SymbolMarketInfo],
    settings: Settings,
) -> str:
    mode_hint = ""
    if settings.aggressive_mode:
        mode_hint = (
            f" | AGGRESSIVE_MODE=ON "
            f"(limit 2x: {settings.effective_max_order_per_group}/guruh, "
            f"{settings.effective_max_order_count} global)"
        )

    lines = [
        "=== MAVJUD ORDERLAR (faqat holat — yangi entry SL/TP shu yerdan olinmasin) ===",
        _format_orders(existing_orders),
        "",
        "=== BOZOR (joriy holat — shu asosida tahlil qil) ===",
        _format_market(market),
        "",
        f"Limitlar{mode_hint}: max {settings.effective_max_order_per_group} order/guruh, "
        f"{settings.effective_max_order_count} global | "
        f"mavjud {len(existing_orders)} ta, "
        f"qolgan slot {max(0, settings.effective_max_order_per_group - len(existing_orders))} ta | "
        f"volume {settings.min_volume}..{settings.max_volume} "
        f"(default {settings.default_volume})",
    ]
    return "\n".join(lines)


def _format_orders(orders: list[ExistingOrder]) -> str:
    if not orders:
        return "(yo'q)"

    rows = []
    for item in orders:
        rows.append(
            f"orderNumber={item.order_number} | openTime={item.open_time} | "
            f"openPrice={item.open_price} | SL={item.stop_loss} | TP={item.take_profit} | "
            f"side={item.side} | orderType={item.order_type} | symbol={item.symbol}"
        )
    return "\n".join(rows)


def _format_market(market: list[SymbolMarketInfo]) -> str:
    if not market:
        return "(narxlar olinmadi)"

    rows = []
    for item in market:
        rows.append(
            f"{item.symbol}: bid={item.bid} ask={item.ask} | "
            f"digits={item.digits} tick={item.tick_size} | "
            f"volStep={item.volume_step} minVol={item.min_volume}"
        )
    return "\n".join(rows)
