"""Shared helper functions used across handlers."""
from __future__ import annotations

from typing import Any, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from . import config, db
from .emojis import e, premium


async def safe_edit(message, text: str, reply_markup=None) -> None:
    """Edit a message, ignoring 'message is not modified' errors."""
    try:
        await message.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
    except TelegramBadRequest as ex:
        if "message is not modified" in str(ex).lower():
            return
        # Fall back to sending a new message if edit fails (e.g. editing a photo caption)
        try:
            await message.answer(text, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception:
            pass


async def is_user_joined(bot: Bot, channel: str, user_id: int) -> bool:
    """Check whether a user is a member of the force-join channel."""
    if not channel:
        return True
    try:
        member = await bot.get_chat_member(f"@{channel}", user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        # If the bot can't verify (not admin / wrong username), don't block users.
        return True


async def notify_admins(bot: Bot, text: str, reply_markup=None,
                        photo: Optional[str] = None) -> None:
    for admin_id in config.ADMIN_IDS:
        try:
            if photo:
                await bot.send_photo(admin_id, photo, caption=text, reply_markup=reply_markup)
            else:
                await bot.send_message(admin_id, text, reply_markup=reply_markup,
                                       disable_web_page_preview=True)
        except Exception:
            continue


async def deliver_product(bot: Bot, user_id: int, product: dict[str, Any],
                          order_id: str) -> tuple[bool, str]:
    """
    Deliver a product to a user. Hybrid logic:
      - if auto stock available -> pop and send
      - else if delivery allows manual -> mark pending manual, notify admin
    Returns (delivered_now, content_or_status).
    """
    mode = product.get("delivery_mode", "auto")
    content = None
    if mode in ("auto", "both"):
        item = await db.pop_stock(str(product["_id"]))
        if item:
            content = item["content"]

    if content:
        await db.update_order(order_id, {"status": "delivered", "delivered_content": content})
        await db.inc_product_sold(str(product["_id"]))
        text = (
            f"{premium('check')} <b>Order Delivered!</b>\n\n"
            f"{e('tag')} <b>{product['name']}</b>\n"
            f"{e('key')} Your details:\n"
            f"<code>{content}</code>\n\n"
            f"{e('info')} Keep this safe. Need help? Use Support."
        )
        try:
            await bot.send_message(user_id, text, disable_web_page_preview=True)
        except Exception:
            pass
        return True, content

    # No auto stock -> manual fallback
    await db.update_order(order_id, {"status": "approved"})
    try:
        await bot.send_message(
            user_id,
            f"{premium('check')} <b>Payment confirmed!</b>\n\n"
            f"{e('tag')} <b>{product['name']}</b>\n"
            f"{e('hourglass')} Your order is being processed manually and will be "
            f"delivered shortly. Thank you for your patience!",
        )
    except Exception:
        pass
    return False, "manual"


def progress_bar(value: int, total: int, length: int = 10) -> str:
    if total <= 0:
        return "▱" * length
    filled = int(length * value / total)
    return "▰" * filled + "▱" * (length - filled)
