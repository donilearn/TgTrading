import json
import re
import unittest

from ai.prompts import build_system_prompt
from models.ai_trade_response import AiTradeResponse


class PromptBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prompt = build_system_prompt(
            ["XAUUSDm", "BTCUSDm"], "XAUUSDm", 8, 20, 0.01, 0.1, 0.01,
            aggressive_mode=True, orders_expiration_minutes=20,
        )

    def test_key_sections_present(self):
        for section in ("REVERSAL", "EDITED MESSAGES", "DELETED MESSAGES", "CHART IMAGES"):
            self.assertIn(section, self.prompt)

    def test_examples_are_valid_schema_json(self):
        blocks = re.findall(r"^\{\n.*?\n\}$", self.prompt, flags=re.DOTALL | re.MULTILINE)
        self.assertEqual(len(blocks), 3)
        for block in blocks:
            AiTradeResponse.model_validate(json.loads(block))


if __name__ == "__main__":
    unittest.main()
