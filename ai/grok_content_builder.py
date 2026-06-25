import base64

from config.settings import Settings
from models.chat_message import ChatMessage
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from ai.analysis_text_builder import build_analysis_user_text
from ai.message_media import is_image


def build_grok_messages(
    system_prompt: str,
    message: ChatMessage,
    context: list[ChatMessage],
    existing_orders: list[ExistingOrder],
    market: list[SymbolMarketInfo],
    settings: Settings,
    *,
    media_note: str | None = None,
    image_source: ChatMessage | None = None,
) -> list[dict]:
    user_text = build_analysis_user_text(
        message,
        context,
        existing_orders,
        market,
        settings,
        media_note=media_note,
    )

    source = image_source or message
    if is_image(source.media):
        image_b64 = base64.standard_b64encode(source.media.data).decode("ascii")
        mime = source.media.mime_type or "image/jpeg"
        user_content: list[dict] | str = [
            {"type": "text", "text": user_text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{image_b64}"},
            },
        ]
    else:
        user_content = user_text

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
