from enum import Enum


class ModifyScope(str, Enum):
    """Which open trade entities an UPDATE/CANCEL should affect."""

    BOTH = "both"
    POSITIONS = "positions"
    ORDERS = "orders"
