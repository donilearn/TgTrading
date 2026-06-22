from config.settings import Settings
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo


def format_analysis_context(
    existing_orders: list[ExistingOrder],
    market: list[SymbolMarketInfo],
    settings: Settings,
    chat_id: int,
    magic: int,
) -> str:
    mode_hint = ""
    if settings.aggressive_mode:
        mode_hint = (
            f" | AGGRESSIVE_MODE=ON "
            f"(limit 2x: {settings.effective_max_order_per_group}/guruh, "
            f"{settings.effective_max_order_count} global)"
        )

    lines = [
        "=== GURUHLAR (Telegram chat_id → MetaTrader magic) ===",
        _format_group_map(settings, chat_id),
        "",
        f"=== JORIY GURUH (shu xabar manbasi) ===",
        f"chat_id={chat_id} | magic={magic}",
        "",
        "=== MAVJUD ORDERLAR (faqat joriy guruh — yangi entry SL/TP shu yerdan olinmasin) ===",
        _format_orders(existing_orders, chat_id, magic),
        "",
        "=== BOZOR (joriy holat — shu asosida tahlil qil) ===",
        _format_market(market),
        "",
        f"Limitlar{mode_hint}: max {settings.effective_max_order_per_group} order/guruh, "
        f"{settings.effective_max_order_count} global | "
        f"joriy guruhda mavjud {len(existing_orders)} ta, "
        f"qolgan slot {max(0, settings.effective_max_order_per_group - len(existing_orders))} ta | "
        f"volume {settings.min_volume}..{settings.max_volume} "
        f"(default {settings.default_volume})",
    ]
    return "\n".join(lines)


def _format_group_map(settings: Settings, current_chat_id: int) -> str:
    rows = []
    for group_id, group_magic in settings.group_magic_by_id.items():
        marker = " ← JORIY" if group_id == current_chat_id else ""
        rows.append(f"chat_id={group_id} → magic={group_magic}{marker}")
    return "\n".join(rows) if rows else "(guruhlar sozlanmagan)"


def _format_orders(
    orders: list[ExistingOrder],
    chat_id: int,
    magic: int,
) -> str:
    if not orders:
        return "(yo'q)"

    rows = []
    for item in orders:
        rows.append(
            f"orderNumber={item.order_number} | groupId={chat_id} | magic={magic} | "
            f"openTime={item.open_time} | openPrice={item.open_price} | "
            f"SL={item.stop_loss} | TP={item.take_profit} | "
            f"side={item.side} | orderType={item.order_type} | symbol={item.symbol} | "
            f"isPosition={item.is_position}"
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
