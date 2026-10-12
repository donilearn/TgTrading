import unittest

from ai.reversal_patcher import apply_reversal, find_opposite_orders, without_orders
from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder


def _order(number: str, side: str, *, position: bool, symbol: str = "XAUUSDm") -> ExistingOrder:
    return ExistingOrder(
        order_number=number,
        open_price=4100.0,
        volume=0.01,
        side=side,
        order_type="market" if position else "limit",
        symbol=symbol,
        is_position=position,
    )


def _sell_market_response() -> AiTradeResponse:
    return AiTradeResponse(
        is_signal=True,
        symbol="XAUUSDm",
        side="sell",
        orders=[AiOrderAction(
            count_order=1, action_type="entry", order_type="market",
        )],
    )


class ReversalPatcherTests(unittest.TestCase):
    def test_opposite_positions_closed_and_pending_cancelled_first(self):
        existing = [
            _order("111", "buy", position=True),
            _order("112", "buy", position=False),
            _order("113", "sell", position=True),
            _order("114", "buy", position=True, symbol="BTCUSDm"),
        ]
        response = _sell_market_response()

        opposite = find_opposite_orders(response, existing)
        patched = apply_reversal(response, opposite)

        self.assertEqual({o.order_number for o in opposite}, {"111", "112"})
        self.assertEqual(
            [(o.action_type, o.count_order) for o in patched.orders],
            [("close", 111), ("cancel", 112), ("entry", 1)],
        )

    def test_no_entries_means_no_reversal(self):
        existing = [_order("111", "buy", position=True)]
        response = AiTradeResponse(
            is_signal=True, symbol="XAUUSDm", side="sell", orders=[],
        )
        patched = apply_reversal(response, find_opposite_orders(response, existing))
        self.assertEqual(patched.orders, [])

    def test_ai_close_not_duplicated(self):
        existing = [_order("111", "buy", position=True)]
        response = _sell_market_response()
        response.orders.insert(0, AiOrderAction(count_order=111, action_type="close"))

        patched = apply_reversal(response, find_opposite_orders(response, existing))

        closes = [o for o in patched.orders if o.action_type == "close"]
        self.assertEqual(len(closes), 1)

    def test_modify_on_opposite_order_dropped(self):
        existing = [_order("111", "buy", position=True)]
        response = _sell_market_response()
        response.orders.append(AiOrderAction(
            count_order=111, action_type="modify", sl=4100.0,
        ))

        patched = apply_reversal(response, find_opposite_orders(response, existing))

        self.assertNotIn("modify", [o.action_type for o in patched.orders])

    def test_without_orders_excludes_opposite(self):
        existing = [_order("111", "buy", position=True), _order("113", "sell", position=True)]
        remaining = without_orders(existing, [existing[0]])
        self.assertEqual([o.order_number for o in remaining], ["113"])


if __name__ == "__main__":
    unittest.main()
