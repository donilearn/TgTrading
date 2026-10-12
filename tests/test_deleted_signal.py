import tempfile
import unittest
from pathlib import Path

from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo
from pipeline.deleted_signal_planner import plan_deleted_signal_actions
from trading.signal_order_registry import SignalOrderRegistry


def _position(number: str, side: str, sl: float | None = None) -> ExistingOrder:
    return ExistingOrder(
        order_number=number,
        open_price=4100.0,
        volume=0.01,
        stop_loss=sl,
        side=side,
        order_type="market",
        symbol="XAUUSDm",
        is_position=True,
    )


_QUOTE = SymbolMarketInfo(symbol="XAUUSDm", bid=4110.0, ask=4110.3)


class DeletedSignalPlannerTests(unittest.TestCase):
    def test_pending_cancelled(self):
        pending = ExistingOrder(
            order_number="5", open_price=4090.0, side="buy",
            order_type="limit", symbol="XAUUSDm", is_position=False,
        )
        actions = plan_deleted_signal_actions([pending], [_QUOTE])
        self.assertEqual([(a.action_type, a.count_order) for a in actions], [("cancel", 5)])

    def test_profitable_position_moved_to_breakeven(self):
        actions = plan_deleted_signal_actions([_position("7", "buy")], [_QUOTE])
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action_type, "modify")
        self.assertEqual(actions[0].sl, 4100.0)

    def test_losing_position_untouched(self):
        actions = plan_deleted_signal_actions([_position("8", "sell")], [_QUOTE])
        self.assertEqual(actions, [])

    def test_already_protected_position_untouched(self):
        actions = plan_deleted_signal_actions([_position("9", "buy", sl=4105.0)], [_QUOTE])
        self.assertEqual(actions, [])


class SignalOrderRegistryTests(unittest.TestCase):
    def test_record_persist_and_forget(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            registry = SignalOrderRegistry(path)
            registry.record(-100, 42, ["1001", "1002"])
            registry.record(-100, 42, ["1002", "1003"])

            reloaded = SignalOrderRegistry(path)
            self.assertEqual(reloaded.tickets_for(-100, [42]), {"1001", "1002", "1003"})

            reloaded.forget(-100, [42])
            self.assertEqual(SignalOrderRegistry(path).tickets_for(-100, [42]), set())


if __name__ == "__main__":
    unittest.main()
