from metaapi_cloud_sdk.metaapi.models import StopOptions


def build_stop_options(
    price: float | None,
    pips: float | None,
) -> StopOptions | float | None:
    if pips is not None:
        return StopOptions(value=pips, units="RELATIVE_PIPS")
    return price
