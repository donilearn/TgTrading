from config.settings import Settings
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo

_BROKER_NOT_LOADED = (
    "(NOT LOADED — broker snapshot unavailable for this message. "
    "Do NOT invent order_number values. Return the trade intent only; "
    "the app syncs existing orders after your answer.)"
)


def format_analysis_context(
    existing_orders: list[ExistingOrder],
    market: list[SymbolMarketInfo],
    settings: Settings,
    chat_id: int,
    magic: int,
    *,
    broker_loaded: bool = True,
) -> str:
    group_remaining = max(0, settings.max_order_count - len(existing_orders))
    mode_label = "AGGRESSIVE" if settings.aggressive_mode else "NORMAL"

    if broker_loaded:
        orders_block = _format_orders(existing_orders, chat_id, magic)
        market_block = _format_market(market)
        count_line = (
            f"Channel total: max {settings.max_order_count} | "
            f"existing {len(existing_orders)} | remaining {group_remaining}"
        )
    else:
        orders_block = _BROKER_NOT_LOADED
        market_block = "(NOT LOADED — use prices from the message/chart)"
        count_line = f"Channel total: max {settings.max_order_count}"

    lines = [
        "=== GROUPS (Telegram chat_id → MetaTrader magic) ===",
        _format_group_map(settings, chat_id),
        "",
        "=== CURRENT GROUP (source of this message) ===",
        f"chat_id={chat_id} | magic={magic}",
        "",
        "=== EXISTING ORDERS (current group only — never copy their SL/TP into new entries) ===",
        orders_block,
        "",
        "=== MARKET (live quotes) ===",
        market_block,
        "",
        f"=== LIMITS ({mode_label}) ===",
        f"Per message: max {settings.effective_max_per_message} new entries "
        f"({mode_label}: {settings.max_orders_per_message}, env max {settings.max_order_per_group})",
        count_line,
        f"ORDERS_EXPIRATION: {settings.orders_expiration_minutes} min (limit/stop)",
        f"volume {settings.min_volume}..{settings.max_volume} (default {settings.default_volume})",
    ]
    return "\n".join(lines)


def _format_group_map(settings: Settings, current_chat_id: int) -> str:
    rows = []
    for group_id, group_magic in settings.group_magic_by_id.items():
        marker = " ← CURRENT" if group_id == current_chat_id else ""
        rows.append(f"chat_id={group_id} → magic={group_magic}{marker}")
    return "\n".join(rows) if rows else "(no groups configured)"


def _format_orders(
    orders: list[ExistingOrder],
    chat_id: int,
    magic: int,
) -> str:
    if not orders:
        return "(none — no open positions or pending orders in this group)"

    rows = []
    for item in orders:
        kind = "POSITION" if item.is_position else "PENDING"
        rows.append(
            f"order_number={item.order_number} | {kind} | side={item.side} | "
            f"orderType={item.order_type} | symbol={item.symbol} | "
            f"openPrice={item.open_price} | volume={item.volume} | "
            f"SL={item.stop_loss} | TP={item.take_profit} | "
            f"openTime={item.open_time} | groupId={chat_id} | magic={magic}"
        )
    return "\n".join(rows)


def _format_market(market: list[SymbolMarketInfo]) -> str:
    if not market:
        return "(quotes unavailable)"

    rows = []
    for item in market:
        rows.append(
            f"{item.symbol}: bid={item.bid} ask={item.ask} | "
            f"digits={item.digits} tick={item.tick_size} | "
            f"volStep={item.volume_step} minVol={item.min_volume}"
        )
    return "\n".join(rows)
