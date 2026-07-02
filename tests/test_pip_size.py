import unittest

from trading.pip_size import pip_size_from_spec
from trading.sltp_price_resolver import resolve_default_sltp_prices


class PipSizeTests(unittest.TestCase):
    def test_digits_2_no_multiply(self):
        self.assertEqual(pip_size_from_spec({"digits": 2, "tickSize": 0.01}), 0.01)

    def test_digits_3_multiply_by_10(self):
        self.assertEqual(pip_size_from_spec({"digits": 3, "tickSize": 0.001}), 0.01)

    def test_digits_4_forex(self):
        self.assertEqual(pip_size_from_spec({"digits": 4, "tickSize": 0.0001}), 0.0001)

    def test_digits_5_forex(self):
        self.assertEqual(pip_size_from_spec({"digits": 5, "tickSize": 0.00001}), 0.0001)

    def test_broker_pip_size_priority(self):
        self.assertEqual(
            pip_size_from_spec({"digits": 5, "tickSize": 0.00001, "pipSize": 0.0002}),
            0.0002,
        )

    def test_default_sltp_xau_100_50_pips(self):
        spec = {"digits": 3, "tickSize": 0.001}
        sl, tp = resolve_default_sltp_prices(
            side="buy",
            entry_price=2650.0,
            spec=spec,
            default_sl_pips=100,
            default_tp_pips=50,
        )
        self.assertEqual(sl, 2649.0)
        self.assertEqual(tp, 2650.5)


if __name__ == "__main__":
    unittest.main()
