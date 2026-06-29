"""Handler routers aggregation."""
from aiogram import Router

from . import start, shop, wallet, payments, orders, admin


def get_main_router() -> Router:
    router = Router(name="main")
    # Order matters: admin first so admin callbacks take priority
    router.include_router(admin.router)
    router.include_router(start.router)
    router.include_router(shop.router)
    router.include_router(wallet.router)
    router.include_router(payments.router)
    router.include_router(orders.router)
    return router
