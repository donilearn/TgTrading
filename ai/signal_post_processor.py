import logging

from ai.symbol_inference import infer_symbol, infer_symbol_from_context
from models.chat_message import ChatMessage
from models.signal import SignalAnalysis
from models.signal_type import SignalType
from trading.symbol_validator import resolve_env_symbol

logger = logging.getLogger(__name__)

_MODIFY_TYPES = {SignalType.UPDATE, SignalType.CANCEL, SignalType.CLOSE}


def resolve_signal_symbol(
    signal: SignalAnalysis,
    message: ChatMessage,
    context: list[ChatMessage],
    allowed_symbols: list[str],
    default_symbol: str | None,
) -> SignalAnalysis:
    if signal.signal_type in _MODIFY_TYPES:
        return _resolve_modify_symbol(signal, message, context, allowed_symbols)

    return _resolve_entry_symbol(
        signal, message, context, allowed_symbols, default_symbol,
    )


def _resolve_modify_symbol(
    signal: SignalAnalysis,
    message: ChatMessage,
    context: list[ChatMessage],
    allowed_symbols: list[str],
) -> SignalAnalysis:
    current_text = message.text or ""

    if signal.symbol:
        resolved = resolve_env_symbol(signal.symbol, allowed_symbols)
        if resolved and _symbol_in_text(resolved, current_text):
            signal.symbol = resolved
            return signal

    from_context = infer_symbol_from_context(context, allowed_symbols)
    if from_context:
        signal.symbol = from_context
        return signal

    combined = _build_combined_text(message, context)
    inferred = infer_symbol(signal.symbol, combined, allowed_symbols, None)
    if inferred:
        signal.symbol = inferred
        return signal

    if signal.symbol:
        resolved = resolve_env_symbol(signal.symbol, allowed_symbols)
        if resolved:
            signal.symbol = resolved
            return signal
        return SignalAnalysis(
            is_signal=False,
            reasoning=f"Symbol {signal.symbol} not in allowed list",
        )

    return signal


def _resolve_entry_symbol(
    signal: SignalAnalysis,
    message: ChatMessage,
    context: list[ChatMessage],
    allowed_symbols: list[str],
    default_symbol: str | None,
) -> SignalAnalysis:
    combined_text = _build_combined_text(message, context)

    resolved = infer_symbol(
        signal.symbol,
        combined_text,
        allowed_symbols,
        default_symbol,
    )

    if resolved:
        signal.symbol = resolved
    elif signal.is_signal and signal.symbol:
        return SignalAnalysis(
            is_signal=False,
            reasoning=f"Symbol {signal.symbol} not in allowed list",
        )

    return signal


def _symbol_in_text(symbol: str, text: str) -> bool:
    text_lower = text.lower()
    if symbol.lower() in text_lower:
        return True
    return symbol.lower().rstrip("m") in text_lower


def normalize_pip_fields(
    signal: SignalAnalysis,
    message: ChatMessage,
) -> SignalAnalysis:
    """Move pip counts out of absolute price fields when message mentions pips."""
    text = (message.text or "").lower()
    if "pip" not in text:
        return signal

    if signal.stop_loss is not None and signal.sl_pips is None:
        signal.sl_pips = signal.stop_loss
        signal.stop_loss = None
        logger.info("Corrected: moved stop_loss to sl_pips (pip distance)")

    if signal.primary_take_profit is not None and signal.tp_pips is None:
        if signal.take_profits:
            signal.tp_pips = signal.take_profits[0].price
            signal.take_profits = []
            logger.info("Corrected: moved take_profit to tp_pips (pip distance)")

    return signal


def _build_combined_text(message: ChatMessage, context: list[ChatMessage]) -> str:
    parts = [msg.text for msg in context if msg.text]
    if message.text:
        parts.append(message.text)
    return " ".join(parts)