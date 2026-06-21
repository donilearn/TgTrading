import asyncio
import logging

from google.genai import types

from ai.client import GeminiClient
from ai.content_builder import build_analysis_contents
from ai.model_retry import generate_with_fallback
from ai.prompts import build_system_prompt
from config.settings import Settings
from models.ai_trade_response import AiTradeResponse
from models.chat_message import ChatMessage
from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from trading.symbol_validator import resolve_env_symbol

logger = logging.getLogger(__name__)


class SignalAnalyzer:
    def __init__(self, gemini_client: GeminiClient, settings: Settings) -> None:
        self._gemini = gemini_client
        self._settings = settings
        self._allowed_symbols = settings.parsed_allowed_symbols
        self._system_prompt = build_system_prompt(
            self._allowed_symbols,
            settings.default_symbol,
            settings.effective_max_order_per_group,
            settings.effective_max_order_count,
            settings.min_volume,
            settings.max_volume,
            settings.default_volume,
            settings.aggressive_mode,
        )

    async def analyze(
        self,
        message: ChatMessage,
        context: list[ChatMessage],
        existing_orders: list[ExistingOrder],
        market: list[SymbolMarketInfo],
    ) -> AiTradeResponse:
        if not message.text and not message.media:
            return AiTradeResponse(is_signal=False, reasoning="Empty message")

        config = types.GenerateContentConfig(
            system_instruction=self._system_prompt,
            response_mime_type="application/json",
            response_schema=AiTradeResponse,
        )
        contents = build_analysis_contents(
            message, context, existing_orders, market, self._settings,
        )

        try:
            response = await asyncio.to_thread(
                generate_with_fallback,
                self._gemini.client,
                self._gemini.model,
                self._settings.parsed_fallback_models,
                contents,
                config,
            )

            result = response.parsed or AiTradeResponse.model_validate_json(response.text)
            result = self._validate_symbol(result)
            return result

        except Exception as exc:
            logger.error("Gemini analysis failed: %s", exc)
            return AiTradeResponse(
                is_signal=False,
                reasoning=f"Analysis error: {exc}",
            )

    def _validate_symbol(self, result: AiTradeResponse) -> AiTradeResponse:
        if not result.symbol:
            return result

        resolved = resolve_env_symbol(result.symbol, self._allowed_symbols)
        if not resolved:
            return AiTradeResponse(
                is_signal=False,
                reasoning=f"Symbol {result.symbol} not in allowed list",
            )

        result.symbol = resolved
        return result
