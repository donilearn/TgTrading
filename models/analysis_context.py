from models.existing_order import ExistingOrder
from models.symbol_market_info import SymbolMarketInfo


class AnalysisContext(BaseModel):
    existing_orders: list[ExistingOrder]
    market: list[SymbolMarketInfo]
