"""Shop browsing: categories -> products -> product view -> choose payment."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import db
from ..emojis import e, premium
from ..keyboards import (
    categories_kb,
    pay_methods_kb,
    product_view_kb,
    products_kb,
    back_home,
)
from ..utils import safe_edit

router = Router(name="shop")


@router.callback_query(F.data == "shop:home")
async def cb_shop_home(call: CallbackQuery) -> None:
    settings = await db.get_settings()
    if not settings.get("shop_open", True):
        await safe_edit(
            call.message,
            f"{e('lock')} <b>Shop is temporarily closed.</b>\n\nPlease check back soon!",
            back_home(),
        )
        await call.answer()
        return

    cats = await db.list_categories()
    if not cats:
        await safe_edit(
            call.message,
            f"{e('box')} <b>No products yet.</b>\n\nOur catalog is being stocked — "
            f"please check back shortly!",
            back_home(),
        )
        await call.answer()
        return

    text = (
        f"{premium('fire')} <b>Browse Categories</b>\n\n"
        f"Pick a category to explore our premium subscriptions."
    )
    await safe_edit(call.message, text, categories_kb(cats))
    await call.answer()


@router.callback_query(F.data.startswith("shop:cat:"))
async def cb_category(call: CallbackQuery) -> None:
    cat_id = call.data.split(":", 2)[2]
    cat = await db.get_category(cat_id)
    if not cat:
        await call.answer("Category not found.", show_alert=True)
        return

    products = await db.list_products(category_id=cat_id, only_active=True)
    if not products:
        await safe_edit(
            call.message,
            f"{cat.get('emoji','📦')} <b>{cat['name']}</b>\n\n"
            f"{e('info')} No products in this category yet.",
            categories_kb(await db.list_categories()),
        )
        await call.answer()
        return

    stock_map = {}
    for p in products:
        stock_map[str(p["_id"])] = await db.stock_count(str(p["_id"]))

    text = (
        f"{cat.get('emoji','📦')} <b>{cat['name']}</b>\n\n"
        f"{e('tag')} Select a product to view details:"
    )
    await safe_edit(call.message, text, products_kb(products, cat_id, stock_map))
    await call.answer()


@router.callback_query(F.data.startswith("shop:prod:"))
async def cb_product(call: CallbackQuery) -> None:
    pid = call.data.split(":", 2)[2]
    product = await db.get_product(pid)
    if not product:
        await call.answer("Product not found.", show_alert=True)
        return

    sc = await db.stock_count(pid)
    mode = product.get("delivery_mode", "auto")

    if mode == "auto":
        avail = sc > 0
        stock_line = (
            f"{premium('check')} <b>In stock:</b> {sc}" if avail
            else f"{e('cross')} <b>Out of stock</b>"
        )
    elif mode == "manual":
        avail = True
        stock_line = f"{e('clock')} <b>Manual delivery</b> (after approval)"
    else:  # both
        avail = True
        stock_line = (
            f"{premium('check')} <b>In stock:</b> {sc}" if sc > 0
            else f"{e('clock')} <b>Manual delivery</b> (after approval)"
        )

    text = (
        f"{premium('gem')} <b>{product['name']}</b>\n\n"
        f"{product.get('description','')}\n\n"
        f"{e('money')} <b>Price:</b> ${product['price']:.2f}\n"
        f"{e('box')} {stock_line}\n"
        f"{e('chart')} <b>Sold:</b> {product.get('sold', 0)}"
    )
    await safe_edit(call.message, text,
                    product_view_kb(pid, product["category_id"], can_buy=avail))
    await call.answer()


@router.callback_query(F.data.startswith("buy:start:"))
async def cb_buy_start(call: CallbackQuery) -> None:
    pid = call.data.split(":", 2)[2]
    product = await db.get_product(pid)
    if not product:
        await call.answer("Product not found.", show_alert=True)
        return

    settings = await db.get_settings()
    if not settings.get("shop_open", True):
        await call.answer("Shop is currently closed.", show_alert=True)
        return

    # Validate availability for auto-only products
    if product.get("delivery_mode") == "auto" and await db.stock_count(pid) <= 0:
        await call.answer("This item is out of stock.", show_alert=True)
        return

    user = await db.get_user(call.from_user.id)
    text = (
        f"{e('cart')} <b>Checkout</b>\n\n"
        f"{e('tag')} <b>{product['name']}</b>\n"
        f"{e('money')} <b>Total:</b> ${product['price']:.2f}\n"
        f"{e('wallet')} <b>Your balance:</b> ${user.get('balance', 0.0):.2f}\n\n"
        f"Choose how you'd like to pay:"
    )
    await safe_edit(call.message, text, pay_methods_kb(pid))
    await call.answer()
