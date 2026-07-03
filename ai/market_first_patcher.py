import logging

from ai.signal_level_detector import (
    is_direction_only_signal,
    message_has_trade_levels,
)
from ai.sl_level_parser import parse_sl_level
from ai.tp_order_count import reference_price_from_market
from config.settings import Settings
from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo

logger = logging.getLogger(__name__)

_MANAGEMENT = frozenset({"close", "cancel", "modify"})


def apply_market_first_policy(
    response: AiTradeResponse,
    existing: list[ExistingOrder],
    message_text: str | None,
    settings: Settings,
    market: list[SymbolMarketInfo] | None = None,
) -> AiTradeResponse:
    """
    MARKET-FIRST siyosati:
    - Case #1 qadam 1: faqat 1 ta market (joriy narx)
    - Case #1 qadam 2 / Case #2: 1 market + limitlar (market pozitsiya yo'q bo'lsa)
    - Market: SL signaldan/default, TP=null (trailing / Auto-BE)
    """
    if not response.is_signal or not response.symbol:
        return response

    side = response.side.lower()
    if side not in ("buy", "sell"):
        return response

    ref_price = reference_price_from_market(response.symbol, market)
    management = [
        o for o in response.orders if o.action_type.lower() in _MANAGEMENT
    ]
    entries = [o for o in response.orders if o.action_type.lower() == "entry"]

    if not entries and not management:
        return response

    has_position = _has_open_position(existing, response.symbol, side)
    has_levels = message_has_trade_levels(
        message_text, response, reference_price=ref_price,
    )
    direction_only = is_direction_only_signal(
        message_text, response, reference_price=ref_price,
    )

    sl = _resolve_signal_sl(message_text, response, ref_price)
    market_volume = _market_volume(settings)

    # Case #1 qadam 1 — faqat market
    if direction_only:
        if has_position:
            logger.info(
                "Market-first: direction-only but %s %s position exists — no new entry",
                response.symbol,
                side,
            )
            return response.model_copy(update={"orders": management})

        market_order = _build_market_entry(
            side, sl, market_volume, settings,
        )
        logger.info("Market-first Case #1 step 1: market only %s %s", side, response.symbol)
        return response.model_copy(update={"orders": management + [market_order]})

    # Case #2 yoki Case #1 qadam 2 — market + limitlar
    if not has_levels:
        return response

    limits = [
        o.model_copy(update={"count_order": 1})
        for o in entries
        if o.order_type.lower() in ("limit", "stop")
    ]

    new_entries: list[AiOrderAction] = []
    if not has_position:
        new_entries.append(_build_market_entry(side, sl, market_volume, settings))
        logger.info(
            "Market-first: 1 market + %d limit(s) for %s %s",
            len(limits),
            response.symbol,
            side,
        )
    else:
        logger.info(
            "Market-first Case #1 step 2: %d limit(s) only (market position open)",
            len(limits),
        )

    new_entries.extend(limits)
    return response.model_copy(
        update={"orders": management + new_entries},
    )


def _has_open_position(
    existing: list[ExistingOrder],
    symbol: str,
    side: str,
) -> bool:
    return any(
        item.is_position
        and item.symbol == symbol
        and item.side.lower() == side
        for item in existing
    )


def _market_volume(settings: Settings) -> float:
    if settings.aggressive_mode:
        return round(settings.min_volume * 2, 2)
    return settings.default_volume


def _build_market_entry(
    side: str,
    sl: float | None,
    volume: float,
    settings: Settings,
) -> AiOrderAction:
    return AiOrderAction(
        count_order=1,
        action_type="entry",
        price=None,
        sl=sl,
        tp=None,
        order_type="market",
        volume=min(max(volume, settings.min_volume), settings.max_volume),
    )


def _resolve_signal_sl(
    message_text: str | None,
    response: AiTradeResponse,
    reference_price: float | None,
) -> float | None:
    parsed = parse_sl_level(message_text, reference_price)
    if parsed is not None:
        return parsed
    for item in response.orders:
        if item.sl is not None:
            return item.sl
    return None
