import asyncio
import logging

from google.genai import types

from ai.gemini_client import GeminiClient
from models.chat_message import ChatMessage

logger = logging.getLogger(__name__)

_PARSE_PROMPT = """Bu Telegram trading kanalidan kelgan audio yoki video.
Vazifa: ichidagi BARCHA muhim ma'lumotni to'liq matn qilib yoz.
- Signal bo'lsa: symbol, yo'nalish, entry, SL, TP, zone, buyruqlar
- Hisobot bo'lsa: nima bo'lgani (TP hit, close va h.k.)
- Reklama/suhbat bo'lsa: qisqa mazmun
Faqat ajratilgan matn qaytar — JSON emas."""


class MediaParser:
    """Audio/video ni Gemini orqali matnga aylantiradi."""

    def __init__(self, gemini: GeminiClient) -> None:
        self._gemini = gemini

    async def parse(self, message: ChatMessage) -> str:
        if message.media is None:
            raise ValueError("No media to parse")

        parts: list = [types.Part.from_text(text=_PARSE_PROMPT)]
        if message.text:
            parts.append(types.Part.from_text(
                text=f"Xabar matni (qo'shimcha):\n{message.text}",
            ))
        parts.append(types.Part.from_bytes(
            data=message.media.data,
            mime_type=message.media.mime_type,
        ))

        config = types.GenerateContentConfig(
            temperature=0.2,
        )

        def _call():
            return self._gemini.client.models.generate_content(
                model=self._gemini.model,
                contents=parts,
                config=config,
            )

        response = await asyncio.to_thread(_call)
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini media parser returned empty text")

        logger.info(
            "Media parsed chat=%s type=%s chars=%d",
            message.chat_id,
            message.media.media_type,
            len(text),
        )
        return text
