from config.settings import Settings
from models.chat_message import ChatMessage
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from ai.telegram_message_formatter import format_context_block, format_message_for_ai
from ai.trading_context_formatter import format_analysis_context


def build_analysis_user_text(
    message: ChatMessage,
    context: list[ChatMessage],
    existing_orders: list[ExistingOrder],
    market: list[SymbolMarketInfo],
    settings: Settings,
    *,
    media_note: str | None = None,
) -> str:
    magic = settings.get_group_magic(message.chat_id)
    blocks = [
        format_analysis_context(
            existing_orders,
            market,
            settings,
            chat_id=message.chat_id,
            magic=magic,
        ),
    ]

    context_block = format_context_block(context)
    if context_block:
        blocks.append(context_block)

    current = format_message_for_ai(message, is_current=True)
    blocks.append(f"{current}\n\nmagic={magic}")

    if media_note:
        blocks.append(media_note)

    return "\n\n".join(blocks)
