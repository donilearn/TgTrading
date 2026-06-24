from google.genai import types

from ai.telegram_message_formatter import format_context_block, format_message_for_ai
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

    magic = settings.get_group_magic(message.chat_id)

    parts.append(types.Part.from_text(
        text=format_analysis_context(
            existing_orders,
            market,
            settings,
            chat_id=message.chat_id,
            magic=magic,
        ),
    ))

    context_block = format_context_block(context)
    if context_block:
        parts.append(types.Part.from_text(text=context_block))

    current_header = format_message_for_ai(message, is_current=True)
    parts.append(types.Part.from_text(
        text=f"{current_header}\n\nmagic={magic}",
    ))

    if message.media:
        parts.append(types.Part.from_bytes(
            data=message.media.data,
            mime_type=message.media.mime_type,
        ))

    return parts
