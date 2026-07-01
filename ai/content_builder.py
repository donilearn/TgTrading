from google.genai import types

from ai.analysis_text_builder import build_analysis_user_text
from config.settings import Settings
from models.chat_message import ChatMessage
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo


def build_gemini_contents(
    message: ChatMessage,
    context: list[ChatMessage],
    existing_orders: list[ExistingOrder],
    market: list[SymbolMarketInfo],
    settings: Settings,
    *,
    is_edit: bool = False,
) -> list:
    user_text = build_analysis_user_text(
        message, context, existing_orders, market, settings,
        is_edit=is_edit,
    )
    parts: list = [types.Part.from_text(text=user_text)]

    if message.media:
        parts.append(types.Part.from_bytes(
            data=message.media.data,
            mime_type=message.media.mime_type,
        ))

    return parts
