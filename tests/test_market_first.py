import unittest
from unittest.mock import MagicMock

from ai.entry_count_normalizer import normalize_entry_count_orders
from ai.market_first_patcher import apply_market_first_policy
from ai.signal_level_detector import is_direction_only_signal, message_has_trade_levels
from config.settings import Settings
from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder


class EntryCountNormalizerTests(unittest.TestCase):
    def test_forces_count_order_one(self):
        response = AiTradeResponse(
            is_signal=True,
            symbol="XAUUSDm",
            side="sell",
            orders=[
                AiOrderAction(count_order=1, action_type="entry", order_type="limit", price=4072.0),
                AiOrderAction(count_order=2, action_type="entry", order_type="limit", price=4073.0),
                AiOrderAction(count_order=3, action_type="entry", order_type="limit", price=4074.0),
            ],
        )
        result = normalize_entry_count_orders(response)
        self.assertTrue(all(o.count_order == 1 for o in result.orders))


class MarketFirstPolicyTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            default_volume=0.01,
            min_volume=0.01,
            max_volume=0.1,
            aggressive_mode=True,
        )

    def test_case1_step1_market_only(self):
        response = AiTradeResponse(
            is_signal=True,
            symbol="XAUUSDm",
            side="sell",
            orders=[
                AiOrderAction(count_order=1, action_type="entry", order_type="limit", price=4072.0),
            ],
        )
        result = apply_market_first_policy(
            response, [], "gold sell now", self.settings,
        )
        self.assertEqual(len(result.orders), 1)
        self.assertEqual(result.orders[0].order_type, "market")
        self.assertIsNone(result.orders[0].tp)

    def test_case2_market_and_limits(self):
        text = "4072-4074 sell\n\n4075 SL"
        response = AiTradeResponse(
            is_signal=True,
            symbol="XAUUSDm",
            side="sell",
            zone_low=4072.0,
            zone_high=4074.0,
            orders=[
                AiOrderAction(count_order=1, action_type="entry", order_type="limit", price=4072.0, sl=4075.0),
                AiOrderAction(count_order=1, action_type="entry", order_type="limit", price=4073.0, sl=4075.0),
            ],
        )
        self.assertTrue(message_has_trade_levels(text, response))
        result = apply_market_first_policy(
            response, [], text, self.settings,
        )
        markets = [o for o in result.orders if o.order_type == "market"]
        limits = [o for o in result.orders if o.order_type == "limit"]
        self.assertEqual(len(markets), 1)
        self.assertEqual(len(limits), 2)
        self.assertIsNone(markets[0].tp)

    def test_case1_step2_limits_only_when_position_open(self):
        existing = [
            ExistingOrder(
                order_number="99",
                open_price=4070.0,
                volume=0.02,
                side="sell",
                order_type="market",
                symbol="XAUUSDm",
                is_position=True,
            ),
        ]
        text = "4072-4074 sell\n\n4075 SL"
        response = AiTradeResponse(
            is_signal=True,
            symbol="XAUUSDm",
            side="sell",
            orders=[
                AiOrderAction(count_order=1, action_type="entry", order_type="limit", price=4072.0, sl=4075.0),
            ],
        )
        result = apply_market_first_policy(
            response, existing, text, self.settings,
        )
        self.assertFalse(any(o.order_type == "market" for o in result.orders))
        self.assertEqual(len(result.orders), 1)


class SignalLevelDetectorTests(unittest.TestCase):
    def test_direction_only(self):
        response = AiTradeResponse(is_signal=True, symbol="XAUUSDm", side="sell")
        self.assertTrue(is_direction_only_signal("gold sell now", response))
        self.assertFalse(
            is_direction_only_signal("4072-4074 sell\n4075 sl", response),
        )


if __name__ == "__main__":
    unittest.main()
