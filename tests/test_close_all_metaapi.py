import unittest
from unittest.mock import MagicMock

from ai.analyzer import SignalAnalyzer
from config.settings import Settings
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder


class EnrichCloseAllTests(unittest.TestCase):
    def test_close_all_even_when_llm_says_not_signal(self):
        analyzer = SignalAnalyzer(MagicMock(), Settings())
        existing = [
            ExistingOrder(
                order_number="42",
                open_price=4070.0,
                volume=0.02,
                side="sell",
                order_type="market",
                symbol="XAUUSDm",
                is_position=True,
            ),
        ]
        llm_result = AiTradeResponse(
            is_signal=False,
            reasoning="Not a signal",
        )
        result = analyzer.enrich_with_broker_context(
            llm_result, existing, [], "YOPING",
        )
        self.assertTrue(result.is_signal)
        self.assertEqual(len(result.orders), 1)
        self.assertEqual(result.orders[0].count_order, 42)
        self.assertEqual(result.orders[0].action_type, "close")


if __name__ == "__main__":
    unittest.main()
