__all__ = ["transmit_sale_dte"]


def transmit_sale_dte(*args, **kwargs):
    from .orchestrator import transmit_sale_dte as _transmit_sale_dte

    return _transmit_sale_dte(*args, **kwargs)
