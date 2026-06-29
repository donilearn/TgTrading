import asyncio
import logging

from google.genai import types

from ai.request_logger import log_gemini_error, log_gemini_request, log_gemini_response
from ai.client import GeminiClient
from ai.content_builder import build_analysis_contents
from ai.model_retry import generate_with_fallback
from ai.prompts import build_system_prompt
from ai.default_sltp_patcher import apply_default_sltp_to_entries
from ai.existing_position_sltp_patcher import patch_existing_positions_sltp
from ai.redundant_market_guard import remove_redundant_market_entries
from ai.zone_grid_expander import expand_zone_grid_orders
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
            settings.max_order_per_group,
            settings.max_order_count,
            settings.min_volume,
            settings.max_volume,
            settings.default_volume,
            settings.aggressive_mode,
            settings.orders_expiration_minutes,
        )

    async def analyze(
        self,
        message: ChatMessage,
        context: list[ChatMessage],
        existing_orders: list[ExistingOrder] | None = None,
        market: list[SymbolMarketInfo] | None = None,
    ) -> AiTradeResponse:
        """Gemini tahlil + ixtiyoriy post-process (broker konteksti bilan)."""
        result = await self.analyze_message(message, context)
        if existing_orders is None and market is None:
            return result
        return self.enrich_with_broker_context(
            result,
            existing_orders or [],
            market or [],
            message.text,
        )

    async def analyze_message(
        self,
        message: ChatMessage,
        context: list[ChatMessage],
    ) -> AiTradeResponse:
        """Faqat Gemini — MetaAPI ulanishsiz."""
        if not message.text and not message.media:
            return AiTradeResponse(is_signal=False, reasoning="Empty message")

        config = types.GenerateContentConfig(
            system_instruction=self._system_prompt,
            response_mime_type="application/json",
            response_schema=AiTradeResponse,
        )
        contents = build_analysis_contents(
            message, context, [], [], self._settings,
        )

        primary_model = self._gemini.model
        log_gemini_request(
            message.chat_id,
            primary_model,
            contents,
            len(self._system_prompt),
        )

        try:
            response = await asyncio.to_thread(
                generate_with_fallback,
                self._gemini.client,
                primary_model,
                self._settings.parsed_fallback_models,
                contents,
                config,
            )

            used_model = _response_model(response, primary_model)
            log_gemini_response(message.chat_id, used_model, response)

            result = response.parsed or AiTradeResponse.model_validate_json(response.text)
            return self._validate_symbol(result)

        except Exception as exc:
            log_gemini_error(message.chat_id, primary_model, exc)
            logger.error("Gemini analysis failed: %s", exc)
            return AiTradeResponse(
                is_signal=False,
                reasoning=f"Analysis error: {exc}",
            )

    def enrich_with_broker_context(
        self,
        result: AiTradeResponse,
        existing_orders: list[ExistingOrder],
        market: list[SymbolMarketInfo],
        message_text: str | None,
    ) -> AiTradeResponse:
        """Broker snapshot bilan post-process (MetaAPI ulanishdan keyin)."""
        if not result.is_signal:
            return result

        result = remove_redundant_market_entries(result, existing_orders)
        result = patch_existing_positions_sltp(result, existing_orders)
        result = apply_default_sltp_to_entries(result, self._settings, market)
        result = expand_zone_grid_orders(
            result,
            self._settings,
            len(existing_orders),
            message_text=message_text,
            market=market,
        )
        return result

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


def _response_model(response, default: str) -> str:
    model_version = getattr(response, "model_version", None)
    if model_version:
        return str(model_version)
    return default