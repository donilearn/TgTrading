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
    group_remaining = max(0, settings.max_order_count - len(existing_orders))
    mode_label = "AGGRESSIVE" if settings.aggressive_mode else "NORMAL"

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
        f"=== LIMITLAR ({mode_label}) ===",
        f"Bitta xabar (1 signal): max {settings.effective_max_per_message} ta yangi entry "
        f"({mode_label}: {settings.max_orders_per_message}, env max {settings.max_order_per_group})",
        f"Kanal/guruh jami: max {settings.max_order_count} ta | "
        f"mavjud {len(existing_orders)} | qolgan {group_remaining}",
        f"ORDERS_EXPIRATION: {settings.orders_expiration_minutes} min (limit/stop)",
        f"volume {settings.min_volume}..{settings.max_volume} (default {settings.default_volume})",
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
            f"volume={item.volume} | "
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
