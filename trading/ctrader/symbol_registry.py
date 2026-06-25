from typing import Any


class SymbolRegistry:
    """symbolId ↔ symbolName xaritasi."""

    def __init__(self) -> None:
        self._id_to_name: dict[int, str] = {}
        self._name_to_id: dict[str, int] = {}
        self._specs: dict[int, dict] = {}

    def register_light(self, symbol_id: int, symbol_name: str) -> None:
        self._id_to_name[symbol_id] = symbol_name
        self._name_to_id[symbol_name.upper()] = symbol_id
        self._name_to_id[_strip_suffix(symbol_name).upper()] = symbol_id

    def register_spec(self, symbol_id: int, spec: dict) -> None:
        self._specs[symbol_id] = spec
        name = spec.get("symbolName")
        if name:
            self.register_light(symbol_id, str(name))

    def resolve_id(self, symbol: str) -> int | None:
        key = symbol.upper()
        if key in self._name_to_id:
            return self._name_to_id[key]
        stripped = _strip_suffix(key)
        return self._name_to_id.get(stripped)

    def resolve_name(self, symbol_id: int) -> str:
        return self._id_to_name.get(symbol_id, str(symbol_id))

    def get_spec(self, symbol: str) -> dict | None:
        symbol_id = self.resolve_id(symbol)
        if symbol_id is None:
            return None
        return self._specs.get(symbol_id)


def _strip_suffix(name: str) -> str:
    if name.endswith("M") and len(name) > 1:
        return name[:-1]
    return name
