"""User-facing order history."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import db
from ..emojis import e, premium
from ..keyboards import back_home
from ..utils import safe_edit

router = Router(name="orders")

STATUS_ICON = {
    "pending": "🕐",
    "approved": "✅",
    "delivered": "📦",
    "rejected": "❌",
}


@router.callback_query(F.data == "orders:mine")
async def cb_my_orders(call: CallbackQuery) -> None:
    orders = await db.list_orders(user_id=call.from_user.id, limit=15)
    if not orders:
        await safe_edit(
            call.message,
            f"{e('receipt')} <b>My Orders</b>\n\nYou have no orders yet. "
            f"Tap Browse Products to get started!",
            back_home(),
        )
        await call.answer()
        return

    lines = [f"{premium('receipt')} <b>My Orders</b>\n"]
    for o in orders:
        icon = STATUS_ICON.get(o["status"], "•")
        line = f"{icon} <b>{o['product_name']}</b> — ${o['price']:.2f} ({o['status']})"
        lines.append(line)
        if o["status"] == "delivered" and o.get("delivered_content"):
            lines.append(f"   {e('key')} <code>{o['delivered_content']}</code>")
    await safe_edit(call.message, "\n".join(lines), back_home())
    await call.answer()
