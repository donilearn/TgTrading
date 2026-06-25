import asyncio
import logging
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from config.settings import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GrokClient:
    """Asosiy AI — text va image (Grok API)."""

    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(
            api_key=settings.xai_api_key,
            base_url="https://api.x.ai/v1",
        )
        self._model = settings.xai_model

    @property
    def model(self) -> str:
        return self._model

    async def parse_structured(
        self,
        messages: list[dict],
        response_model: type[T],
    ) -> T:
        def _call():
            completion = self._client.beta.chat.completions.parse(
                model=self._model,
                messages=messages,
                response_format=response_model,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raw = completion.choices[0].message.content or ""
                return response_model.model_validate_json(raw)
            return parsed

        return await asyncio.to_thread(_call)
