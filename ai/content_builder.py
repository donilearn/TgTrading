from google.genai import types

from ai.trading_context_formatter import format_analysis_context
from config.settings import Settings
from models.chat_message import ChatMessage
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo


def build_analysis_contents(
    message: ChatMessage,
    context: list[ChatMessage],
    existing_orders: list[ExistingOrder],
    market: list[SymbolMarketInfo],
    settings: Settings,
) -> list:
    parts: list = []

    parts.append(types.Part.from_text(
        text=format_analysis_context(
            existing_orders,
            market,
            settings,
        ),
    ))

    if context:
        context_lines = [
            f"{i + 1}. {msg.format_for_context()}"
            for i, msg in enumerate(context)
        ]
        parts.append(types.Part.from_text(
            text="Oxirgi guruh xabarlari (kontekst):\n" + "\n".join(context_lines),
        ))

    current_label = f"Joriy xabar [{message.sender}]"
    if message.text:
        parts.append(types.Part.from_text(
            text=f"{current_label}:\n{message.text}",
        ))
    else:
        parts.append(types.Part.from_text(
            text=f"{current_label}: (matn yo'q, media bor)",
        ))

    if message.media:
        parts.append(types.Part.from_bytes(
            data=message.media.data,
            mime_type=message.media.mime_type,
        ))

    return parts
