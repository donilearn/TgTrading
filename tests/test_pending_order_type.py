import unittest

from trading.pending_order_type_resolver import resolve_pending_order_type


class PendingOrderTypeResolverTests(unittest.TestCase):
    def test_sell_limit_above_bid(self):
        self.assertEqual(
            resolve_pending_order_type("sell", 4156.0, bid=4154.0, ask=4154.5),
            "limit",
        )

    def test_sell_stop_below_bid(self):
        self.assertEqual(
            resolve_pending_order_type("sell", 4155.0, bid=4160.0, ask=4160.5),
            "stop",
        )

    def test_buy_limit_below_ask(self):
        self.assertEqual(
            resolve_pending_order_type("buy", 4150.0, bid=4154.0, ask=4154.5),
            "limit",
        )

    def test_buy_stop_above_ask(self):
        self.assertEqual(
            resolve_pending_order_type("buy", 4160.0, bid=4154.0, ask=4154.5),
            "stop",
        )


if __name__ == "__main__":
    unittest.main()
