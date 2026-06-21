from typing import Any


class SymbolSpecCache:
    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}

    async def get(self, connection: Any, symbol: str) -> dict:
        if symbol not in self._cache:
            self._cache[symbol] = await connection.get_symbol_specification(
                symbol=symbol,
            )
        return self._cache[symbol]

    async def get_price(self, connection: Any, symbol: str) -> dict:
        return await connection.get_symbol_price(symbol=symbol)
