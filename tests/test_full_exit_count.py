import unittest

from models.ai_order_action import AiOrderAction
from models.ai_trade_response import AiTradeResponse
from models.existing_order import ExistingOrder
from pipeline.orchestrator import _count_full_exits


def _order(number: str) -> ExistingOrder:
    return ExistingOrder(
        order_number=number, open_price=4100.0, side="buy",
        order_type="market", symbol="XAUUSDm", is_position=True,
    )


class FullExitCountTests(unittest.TestCase):
    def test_only_existing_unique_full_exits_counted(self):
        existing = [_order("111"), _order("112")]
        response = AiTradeResponse(
            is_signal=True,
            symbol="XAUUSDm",
            side="sell",
            orders=[
                AiOrderAction(count_order=111, action_type="close"),
                AiOrderAction(count_order=111, action_type="cancel"),
                AiOrderAction(count_order=999, action_type="close"),
                AiOrderAction(count_order=112, action_type="close", volume=0.01),
                AiOrderAction(count_order=1, action_type="entry", order_type="market"),
            ],
        )
        self.assertEqual(_count_full_exits(response, existing), 1)


if __name__ == "__main__":
    unittest.main()
