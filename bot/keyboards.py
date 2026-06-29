"""
Inline keyboard builders. Telegram inline buttons cannot be individually
colored, but we create a vivid, "colorful" feel using consistent emoji accents,
clear grouping, and well-structured layouts.
"""
from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .emojis import e


# ---------------- User keyboards ----------------
def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('bag')} Browse Products", callback_data="shop:home")
    b.button(text=f"{e('wallet')} My Wallet", callback_data="wallet:home")
    b.button(text=f"{e('receipt')} My Orders", callback_data="orders:mine")
    b.button(text=f"{e('gift')} Refer & Earn", callback_data="ref:home")
    b.button(text=f"{e('support')} Support", callback_data="misc:support")
    b.button(text=f"{e('info')} About", callback_data="misc:about")
    if is_admin:
        b.button(text=f"{e('admin')} Admin Panel", callback_data="admin:home")
    b.adjust(1, 2, 2, 1)
    return b.as_markup()


def back_home() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('home')} Main Menu", callback_data="nav:home")
    return b.as_markup()


def categories_kb(categories: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in categories:
        b.button(text=f"{c.get('emoji', '📦')} {c['name']}",
                 callback_data=f"shop:cat:{c['_id']}")
    b.button(text=f"{e('home')} Main Menu", callback_data="nav:home")
    b.adjust(2)
    # ensure last (home) on its own row
    rows = [2] * (len(categories) // 2)
    if len(categories) % 2:
        rows.append(1)
    rows.append(1)
    b.adjust(*rows)
    return b.as_markup()


def products_kb(products: list[dict[str, Any]], cat_id: str,
                stock_map: dict[str, int]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in products:
        pid = str(p["_id"])
        sc = stock_map.get(pid, 0)
        tag = "" if (p.get("delivery_mode") != "auto" or sc > 0) else f" {e('cross')}"
        b.button(
            text=f"{e('tag')} {p['name']} — ${p['price']:.2f}{tag}",
            callback_data=f"shop:prod:{pid}",
        )
    b.button(text=f"{e('back')} Categories", callback_data="shop:home")
    b.button(text=f"{e('home')} Main Menu", callback_data="nav:home")
    b.adjust(1)
    return b.as_markup()


def product_view_kb(product_id: str, cat_id: str, can_buy: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if can_buy:
        b.button(text=f"{e('cart')} Buy Now", callback_data=f"buy:start:{product_id}")
    b.button(text=f"{e('back')} Back", callback_data=f"shop:cat:{cat_id}")
    b.button(text=f"{e('home')} Main Menu", callback_data="nav:home")
    b.adjust(1, 2)
    return b.as_markup()


def pay_methods_kb(product_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('wallet')} Pay with Wallet", callback_data=f"buy:pay:wallet:{product_id}")
    b.button(text=f"{e('star')} Pay with Telegram Stars", callback_data=f"buy:pay:stars:{product_id}")
    b.button(text=f"{e('crypto')} Pay with USDT", callback_data=f"buy:pay:usdt:{product_id}")
    b.button(text=f"{e('cross')} Cancel", callback_data=f"shop:prod:{product_id}")
    b.adjust(1)
    return b.as_markup()


def wallet_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('plus')} Top Up (USDT)", callback_data="wallet:topup:usdt")
    b.button(text=f"{e('star')} Top Up (Stars)", callback_data="wallet:topup:stars")
    b.button(text=f"{e('receipt')} Top-up History", callback_data="wallet:history")
    b.button(text=f"{e('home')} Main Menu", callback_data="nav:home")
    b.adjust(2, 1, 1)
    return b.as_markup()


def cancel_kb(cb: str = "nav:home") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('cross')} Cancel", callback_data=cb)
    return b.as_markup()


def confirm_topup_proof_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('cross')} Cancel", callback_data="wallet:home")
    return b.as_markup()


def referral_kb(link: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('link')} Share My Link", switch_inline_query=f"\nJoin me here: {link}")
    b.button(text=f"{e('home')} Main Menu", callback_data="nav:home")
    b.adjust(1)
    return b.as_markup()


def force_join_kb(channel: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('bell')} Join Channel", url=f"https://t.me/{channel}")
    b.button(text=f"{e('check')} I've Joined", callback_data="misc:checkjoin")
    b.adjust(1)
    return b.as_markup()


# ---------------- Admin keyboards ----------------
def admin_home_kb(pending_orders: int = 0, pending_topups: int = 0) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('chart')} Statistics", callback_data="admin:stats")
    b.button(text=f"{e('box')} Categories", callback_data="admin:cats")
    b.button(text=f"{e('tag')} Products", callback_data="admin:prods")
    b.button(text=f"{e('list')} Stock", callback_data="admin:stock")
    o = f" ({pending_orders})" if pending_orders else ""
    t = f" ({pending_topups})" if pending_topups else ""
    b.button(text=f"{e('receipt')} Orders{o}", callback_data="admin:orders")
    b.button(text=f"{e('money')} Top-ups{t}", callback_data="admin:topups")
    b.button(text=f"{e('users')} Users", callback_data="admin:users")
    b.button(text=f"{e('megaphone')} Broadcast", callback_data="admin:broadcast")
    b.button(text=f"{e('settings')} Settings", callback_data="admin:settings")
    b.button(text=f"{e('home')} Main Menu", callback_data="nav:home")
    b.adjust(2, 2, 2, 2, 1, 1)
    return b.as_markup()


def admin_back_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('admin')} Admin Home", callback_data="admin:home")
    return b.as_markup()


def admin_cats_kb(categories: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('plus')} Add Category", callback_data="admin:cat:add")
    for c in categories:
        b.button(text=f"{e('trash')} {c.get('emoji','📦')} {c['name']}",
                 callback_data=f"admin:cat:del:{c['_id']}")
    b.button(text=f"{e('admin')} Admin Home", callback_data="admin:home")
    b.adjust(1)
    return b.as_markup()


def admin_prods_kb(products: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('plus')} Add Product", callback_data="admin:prod:add")
    for p in products:
        status = e("check") if p.get("active") else e("cross")
        b.button(text=f"{status} {p['name']} (${p['price']:.2f})",
                 callback_data=f"admin:prod:view:{p['_id']}")
    b.button(text=f"{e('admin')} Admin Home", callback_data="admin:home")
    b.adjust(1)
    return b.as_markup()


def admin_prod_view_kb(product: dict[str, Any]) -> InlineKeyboardMarkup:
    pid = str(product["_id"])
    b = InlineKeyboardBuilder()
    toggle = "Deactivate" if product.get("active") else "Activate"
    b.button(text=f"{e('refresh')} {toggle}", callback_data=f"admin:prod:toggle:{pid}")
    b.button(text=f"{e('plus')} Add Stock", callback_data=f"admin:stock:add:{pid}")
    b.button(text=f"{e('pencil')} Edit Price", callback_data=f"admin:prod:editprice:{pid}")
    b.button(text=f"{e('trash')} Delete", callback_data=f"admin:prod:del:{pid}")
    b.button(text=f"{e('back')} Products", callback_data="admin:prods")
    b.adjust(2, 2, 1)
    return b.as_markup()


def admin_order_kb(order_id: str, user_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('check')} Approve & Deliver", callback_data=f"admin:order:approve:{order_id}")
    b.button(text=f"{e('cross')} Reject", callback_data=f"admin:order:reject:{order_id}")
    b.adjust(2)
    return b.as_markup()


def admin_topup_kb(topup_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('check')} Approve", callback_data=f"admin:topup:approve:{topup_id}")
    b.button(text=f"{e('cross')} Reject", callback_data=f"admin:topup:reject:{topup_id}")
    b.adjust(2)
    return b.as_markup()


def admin_settings_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('pencil')} Shop Name", callback_data="admin:set:shop_name")
    b.button(text=f"{e('pencil')} Welcome Text", callback_data="admin:set:welcome_text")
    b.button(text=f"{e('support')} Support User", callback_data="admin:set:support_username")
    b.button(text=f"{e('crypto')} USDT TRC20", callback_data="admin:set:usdt_trc20_address")
    b.button(text=f"{e('crypto')} USDT BEP20", callback_data="admin:set:usdt_bep20_address")
    b.button(text=f"{e('star')} Stars / Unit", callback_data="admin:set:stars_per_unit")
    b.button(text=f"{e('gift')} Referral Reward", callback_data="admin:set:referral_reward")
    b.button(text=f"{e('bell')} Force-Join Channel", callback_data="admin:set:force_join_channel")
    b.button(text=f"{e('stars')} Premium Emojis", callback_data="admin:emojis")
    b.button(text=f"{e('lock')} Toggle Shop Open", callback_data="admin:set:toggle_shop")
    b.button(text=f"{e('admin')} Admin Home", callback_data="admin:home")
    b.adjust(2, 1, 2, 1, 1, 1, 1, 1)
    return b.as_markup()


def admin_emojis_kb(keys: list[str], current: dict[str, str]) -> InlineKeyboardMarkup:
    """Manager for premium/custom emoji ID overrides — one button per logical name."""
    b = InlineKeyboardBuilder()
    for k in keys:
        mark = e("check") if current.get(k) else e("pencil")
        b.button(text=f"{mark} {k}", callback_data=f"admin:emoji:set:{k}")
    b.button(text=f"{e('trash')} Reset All", callback_data="admin:emoji:reset")
    b.button(text=f"{e('settings')} Settings", callback_data="admin:settings")
    b.button(text=f"{e('admin')} Admin Home", callback_data="admin:home")
    b.adjust(2, 2, 2, 2, 1, 1)
    return b.as_markup()


def admin_users_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('money')} Adjust Balance", callback_data="admin:user:balance")
    b.button(text=f"{e('chart')} Top Buyers", callback_data="admin:user:top")
    b.button(text=f"{e('admin')} Admin Home", callback_data="admin:home")
    b.adjust(2, 1)
    return b.as_markup()


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"{e('check')} Send to All", callback_data="admin:broadcast:send")
    b.button(text=f"{e('cross')} Cancel", callback_data="admin:home")
    b.adjust(2)
    return b.as_markup()
