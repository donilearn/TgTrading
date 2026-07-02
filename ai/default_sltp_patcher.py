import logging

from config.settings import Settings
from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.symbol_market_info import SymbolMarketInfo
from trading.sltp_price_resolver import market_entry_price, resolve_default_sltp_prices

logger = logging.getLogger(__name__)


def apply_default_sltp_to_entries(
    response: AiTradeResponse,
    settings: Settings,
    market: list[SymbolMarketInfo],
) -> AiTradeResponse:
    """Entry orderlarga signalda SL/TP yo'q bo'lsa default qo'yadi."""
    if not response.is_signal or not response.symbol:
        return response
    if settings.default_sl_pips <= 0 and settings.default_tp_pips <= 0:
        return response

    market_info = _find_market(response.symbol, market)
    spec = _market_as_spec(market_info)
    if spec is None:
        logger.warning(
            "Default SL/TP skipped — no market spec for %s",
            response.symbol,
        )
        return response

    side = response.side.lower()
    updated: list[AiOrderAction] = []
    changed = False

    for item in response.orders:
        if item.action_type.lower() != "entry":
            updated.append(item)
            continue

        if item.sl is not None and item.tp is not None:
            updated.append(item)
            continue

        entry_price = item.price
        if entry_price is None and market_info is not None:
            entry_price = market_entry_price(
                side,
                {"bid": market_info.bid, "ask": market_info.ask},
            )

        sl, tp = resolve_default_sltp_prices(
            side=side,
            entry_price=entry_price,
            spec=spec,
            default_sl_pips=settings.default_sl_pips,
            default_tp_pips=settings.default_tp_pips,
            existing_sl=item.sl,
            existing_tp=item.tp,
        )

        if sl == item.sl and tp == item.tp:
            updated.append(item)
            continue

        changed = True
        updated.append(item.model_copy(update={"sl": sl, "tp": tp}))

    if not changed:
        return response

    logger.info(
        "Default SL/TP applied to entries for %s (sl_pips=%s tp_pips=%s)",
        response.symbol,
        settings.default_sl_pips,
        settings.default_tp_pips,
    )
    return response.model_copy(update={"orders": updated})


def _find_market(
    symbol: str,
    market: list[SymbolMarketInfo],
) -> SymbolMarketInfo | None:
    for item in market:
        if item.symbol == symbol:
            return item
    return None


def _market_as_spec(market_info: SymbolMarketInfo | None) -> dict | None:
    if market_info is None or market_info.tick_size is None:
        return None

    return {
        "tickSize": market_info.tick_size,
        "digits": market_info.digits,
        "pipSize": market_info.pip_size,
    }
