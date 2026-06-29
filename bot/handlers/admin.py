"""
Full in-bot admin panel.

Access is restricted to user IDs in config.ADMIN_IDS via a custom filter applied
to every message/callback handler in this router.
"""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import config, db
from ..emojis import (
    PREMIUM_KEYS,
    e,
    effective_emoji_id,
    get_premium_overrides,
    premium,
    set_one_override,
    set_premium_overrides,
)
from ..keyboards import (
    admin_back_kb,
    admin_cats_kb,
    admin_emojis_kb,
    admin_home_kb,
    admin_order_kb,
    admin_prod_view_kb,
    admin_prods_kb,
    admin_settings_kb,
    admin_topup_kb,
    admin_users_kb,
    broadcast_confirm_kb,
    cancel_kb,
)
from ..states import (
    AdminBalance,
    AdminBroadcast,
    AdminCategory,
    AdminProduct,
    AdminSetting,
    AdminStock,
)
from ..utils import deliver_product, progress_bar, safe_edit

router = Router(name="admin")

# Restrict the whole router to admins
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))


# ---------------- Home ----------------
async def render_admin_home(target, edit: bool = False) -> None:
    s = await db.stats()
    text = (
        f"{premium('crown')} <b>Admin Control Panel</b>\n\n"
        f"{e('users')} Users: <b>{s['users']}</b>\n"
        f"{e('tag')} Products: <b>{s['products']}</b>\n"
        f"{e('receipt')} Orders: <b>{s['orders']}</b> "
        f"({s['pending_orders']} pending)\n"
        f"{e('money')} Top-ups pending: <b>{s['pending_topups']}</b>\n"
        f"{e('chart')} Revenue: <b>${s['revenue']:.2f}</b>\n\n"
        f"Select an option to manage your shop:"
    )
    kb = admin_home_kb(s["pending_orders"], s["pending_topups"])
    if edit:
        await safe_edit(target, text, kb)
    else:
        await target.answer(text, reply_markup=kb)


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await render_admin_home(message)


@router.callback_query(F.data == "admin:home")
async def cb_admin_home(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await render_admin_home(call.message, edit=True)
    await call.answer()


# ---------------- Statistics ----------------
@router.callback_query(F.data == "admin:stats")
async def cb_stats(call: CallbackQuery) -> None:
    s = await db.stats()
    delivered_ratio = (s["delivered"] / s["orders"] * 100) if s["orders"] else 0
    text = (
        f"{premium('gem')} <b>Statistics</b>\n\n"
        f"{e('users')} Total users: <b>{s['users']}</b>\n"
        f"{e('tag')} Products: <b>{s['products']}</b>\n"
        f"{e('receipt')} Total orders: <b>{s['orders']}</b>\n"
        f"{e('box')} Delivered: <b>{s['delivered']}</b>\n"
        f"{e('hourglass')} Pending orders: <b>{s['pending_orders']}</b>\n"
        f"{e('money')} Pending top-ups: <b>{s['pending_topups']}</b>\n"
        f"{e('chart')} Revenue: <b>${s['revenue']:.2f}</b>\n\n"
        f"Fulfillment: {progress_bar(int(delivered_ratio), 100)} {delivered_ratio:.0f}%"
    )
    await safe_edit(call.message, text, admin_back_kb())
    await call.answer()


# ---------------- Categories ----------------
@router.callback_query(F.data == "admin:cats")
async def cb_cats(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    cats = await db.list_categories()
    text = (
        f"{premium('gem')} <b>Categories</b>\n\n"
        + (f"Tap a category to delete it, or add a new one.\n"
           if cats else "No categories yet. Add your first one.\n")
    )
    await safe_edit(call.message, text, admin_cats_kb(cats))
    await call.answer()


@router.callback_query(F.data == "admin:cat:add")
async def cb_cat_add(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminCategory.name)
    await safe_edit(call.message,
                    f"{e('pencil')} Send the <b>category name</b> (e.g. <i>AI Tools</i>):",
                    cancel_kb("admin:cats"))
    await call.answer()


@router.message(AdminCategory.name)
async def cat_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminCategory.emoji)
    await message.answer(f"{e('stars')} Send an <b>emoji</b> for this category (or send <code>-</code> to skip):")


@router.message(AdminCategory.emoji)
async def cat_emoji(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    emoji = message.text.strip()
    if emoji == "-" or len(emoji) > 4:
        emoji = "📦"
    await db.add_category(data["name"], emoji)
    await state.clear()
    await message.answer(f"{premium('check')} Category <b>{data['name']}</b> added!")
    await render_admin_home(message)


@router.callback_query(F.data.startswith("admin:cat:del:"))
async def cb_cat_del(call: CallbackQuery) -> None:
    cat_id = call.data.split(":", 3)[3]
    await db.delete_category(cat_id)
    await call.answer("Category deleted.")
    cats = await db.list_categories()
    await safe_edit(call.message, f"{premium('gem')} <b>Categories</b>\n\nDeleted.",
                    admin_cats_kb(cats))


# ---------------- Products ----------------
@router.callback_query(F.data == "admin:prods")
async def cb_prods(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    products = await db.list_products(only_active=False)
    await safe_edit(call.message,
                    f"{premium('gem')} <b>Products</b>\n\nManage your catalog:",
                    admin_prods_kb(products))
    await call.answer()


@router.callback_query(F.data == "admin:prod:add")
async def cb_prod_add(call: CallbackQuery, state: FSMContext) -> None:
    cats = await db.list_categories()
    if not cats:
        await call.answer("Create a category first.", show_alert=True)
        return
    await state.set_state(AdminProduct.category)
    lines = [f"{e('box')} <b>Select a category by number:</b>\n"]
    mapping = {}
    for i, c in enumerate(cats, 1):
        lines.append(f"<b>{i}.</b> {c.get('emoji','📦')} {c['name']}")
        mapping[str(i)] = str(c["_id"])
    await state.update_data(cat_map=mapping)
    await safe_edit(call.message, "\n".join(lines), cancel_kb("admin:prods"))
    await call.answer()


@router.message(AdminProduct.category)
async def prod_category(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    mapping = data.get("cat_map", {})
    choice = message.text.strip()
    if choice not in mapping:
        await message.answer(f"{e('warning')} Invalid number. Try again.")
        return
    await state.update_data(category_id=mapping[choice])
    await state.set_state(AdminProduct.name)
    await message.answer(f"{e('pencil')} Send the <b>product name</b> (e.g. <i>ChatGPT Plus - 1 Month</i>):")


@router.message(AdminProduct.name)
async def prod_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminProduct.description)
    await message.answer(f"{e('pencil')} Send a <b>description</b> (features, duration, etc.):")


@router.message(AdminProduct.description)
async def prod_desc(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminProduct.price)
    await message.answer(f"{e('money')} Send the <b>price</b> in USD (e.g. <code>9.99</code>):")


@router.message(AdminProduct.price)
async def prod_price(message: Message, state: FSMContext) -> None:
    try:
        price = round(float(message.text.strip()), 2)
    except ValueError:
        await message.answer(f"{e('warning')} Invalid price. Enter a number like <code>9.99</code>.")
        return
    await state.update_data(price=price)
    await state.set_state(AdminProduct.delivery_mode)
    await message.answer(
        f"{e('box')} Choose <b>delivery mode</b> — send a number:\n\n"
        f"<b>1.</b> Auto (from stock)\n"
        f"<b>2.</b> Manual (admin delivers)\n"
        f"<b>3.</b> Both (auto, manual fallback)"
    )


@router.message(AdminProduct.delivery_mode)
async def prod_delivery(message: Message, state: FSMContext) -> None:
    choice = message.text.strip()
    mode = {"1": "auto", "2": "manual", "3": "both"}.get(choice)
    if not mode:
        await message.answer(f"{e('warning')} Send 1, 2, or 3.")
        return
    data = await state.get_data()
    pid = await db.add_product(
        data["category_id"], data["name"], data["description"],
        data["price"], delivery_mode=mode,
    )
    await state.clear()
    await message.answer(
        f"{premium('check')} <b>Product created!</b>\n\n"
        f"{e('tag')} {data['name']} — ${data['price']:.2f} ({mode})\n\n"
        + (f"{e('info')} Now add stock items so it can auto-deliver."
           if mode in ("auto", "both") else "")
    )
    product = await db.get_product(pid)
    await message.answer(
        f"{premium('gem')} <b>{product['name']}</b>",
        reply_markup=admin_prod_view_kb(product),
    )


@router.callback_query(F.data.startswith("admin:prod:view:"))
async def cb_prod_view(call: CallbackQuery) -> None:
    pid = call.data.split(":", 3)[3]
    product = await db.get_product(pid)
    if not product:
        await call.answer("Not found.", show_alert=True)
        return
    sc = await db.stock_count(pid)
    cat = await db.get_category(product["category_id"])
    text = (
        f"{premium('gem')} <b>{product['name']}</b>\n\n"
        f"{e('box')} Category: {cat['name'] if cat else 'n/a'}\n"
        f"{e('money')} Price: ${product['price']:.2f}\n"
        f"{e('list')} Delivery: {product.get('delivery_mode','auto')}\n"
        f"{e('box')} Stock: {sc}\n"
        f"{e('chart')} Sold: {product.get('sold',0)}\n"
        f"{e('refresh')} Active: {'Yes' if product.get('active') else 'No'}\n\n"
        f"{product.get('description','')}"
    )
    await safe_edit(call.message, text, admin_prod_view_kb(product))
    await call.answer()


@router.callback_query(F.data.startswith("admin:prod:toggle:"))
async def cb_prod_toggle(call: CallbackQuery) -> None:
    pid = call.data.split(":", 3)[3]
    product = await db.get_product(pid)
    if not product:
        await call.answer("Not found.", show_alert=True)
        return
    await db.update_product(pid, {"active": not product.get("active", True)})
    await call.answer("Updated.")
    await cb_prod_view(call)


@router.callback_query(F.data.startswith("admin:prod:del:"))
async def cb_prod_del(call: CallbackQuery) -> None:
    pid = call.data.split(":", 3)[3]
    await db.delete_product(pid)
    await call.answer("Product deleted.")
    products = await db.list_products(only_active=False)
    await safe_edit(call.message, f"{premium('gem')} <b>Products</b>\n\nDeleted.",
                    admin_prods_kb(products))


@router.callback_query(F.data.startswith("admin:prod:editprice:"))
async def cb_prod_editprice(call: CallbackQuery, state: FSMContext) -> None:
    pid = call.data.split(":", 3)[3]
    await state.set_state(AdminSetting.value)
    await state.update_data(setting="product_price", product_id=pid)
    await safe_edit(call.message, f"{e('money')} Send the new <b>price</b> in USD:",
                    cancel_kb(f"admin:prod:view:{pid}"))
    await call.answer()


# ---------------- Stock ----------------
@router.callback_query(F.data == "admin:stock")
async def cb_stock(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    products = await db.list_products(only_active=False)
    lines = [f"{premium('gem')} <b>Stock Overview</b>\n"]
    for p in products:
        sc = await db.stock_count(str(p["_id"]))
        lines.append(f"{e('tag')} {p['name']}: <b>{sc}</b> in stock")
    if len(lines) == 1:
        lines.append("No products yet.")
    lines.append(f"\n{e('info')} Open a product to add stock.")
    await safe_edit(call.message, "\n".join(lines), admin_prods_kb(products))
    await call.answer()


@router.callback_query(F.data.startswith("admin:stock:add:"))
async def cb_stock_add(call: CallbackQuery, state: FSMContext) -> None:
    pid = call.data.split(":", 3)[3]
    await state.set_state(AdminStock.items)
    await state.update_data(product_id=pid)
    await safe_edit(
        call.message,
        f"{e('plus')} <b>Add Stock</b>\n\n"
        f"Send the stock items — <b>one per line</b>. Each line is delivered to one "
        f"buyer (e.g. <code>email:pass</code> or a redeem code).",
        cancel_kb(f"admin:prod:view:{pid}"),
    )
    await call.answer()


@router.message(AdminStock.items)
async def stock_items(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    pid = data["product_id"]
    items = [ln for ln in (message.text or "").splitlines() if ln.strip()]
    added = await db.add_stock(pid, items)
    await state.clear()
    product = await db.get_product(pid)
    await message.answer(f"{premium('check')} Added <b>{added}</b> stock items.")
    if product:
        await message.answer(f"{premium('gem')} <b>{product['name']}</b>",
                             reply_markup=admin_prod_view_kb(product))


# ---------------- Orders ----------------
@router.callback_query(F.data == "admin:orders")
async def cb_orders(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    orders = await db.list_orders(status="pending", limit=20)
    if not orders:
        await safe_edit(call.message,
                        f"{premium('receipt')} <b>Pending Orders</b>\n\nNone right now. {e('check')}",
                        admin_back_kb())
        await call.answer()
        return
    await safe_edit(call.message,
                    f"{premium('receipt')} <b>Pending Orders</b>\n\nReview each below:",
                    admin_back_kb())
    for o in orders:
        oid = str(o["_id"])
        text = (
            f"{e('receipt')} <b>Order</b> <code>{oid}</code>\n"
            f"{e('user')} User: <code>{o['user_id']}</code>\n"
            f"{e('tag')} {o['product_name']}\n"
            f"{e('money')} ${o['price']:.2f} • {o['pay_method'].upper()}"
        )
        if o.get("proof_file_id"):
            await call.message.answer_photo(o["proof_file_id"], caption=text,
                                            reply_markup=admin_order_kb(oid, o["user_id"]))
        else:
            await call.message.answer(text, reply_markup=admin_order_kb(oid, o["user_id"]))
    await call.answer()


@router.callback_query(F.data.startswith("admin:order:approve:"))
async def cb_order_approve(call: CallbackQuery, bot: Bot) -> None:
    oid = call.data.split(":", 3)[3]
    order = await db.get_order(oid)
    if not order or order["status"] not in ("pending", "approved"):
        await call.answer("Already handled.", show_alert=True)
        return
    product = await db.get_product(order["product_id"])
    if not product:
        await call.answer("Product gone.", show_alert=True)
        return
    await db.mark_user_purchase(order["user_id"], float(order["price"]))
    delivered, status = await deliver_product(bot, order["user_id"], product, oid)
    await call.answer("Approved.")
    note = (f"{e('rocket')} Auto-delivered." if delivered
            else f"{e('hourglass')} No stock — manual delivery needed.")
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer(f"{premium('check')} Order <code>{oid}</code> approved. {note}")


@router.callback_query(F.data.startswith("admin:order:reject:"))
async def cb_order_reject(call: CallbackQuery, bot: Bot) -> None:
    oid = call.data.split(":", 3)[3]
    order = await db.get_order(oid)
    if not order:
        await call.answer("Not found.", show_alert=True)
        return
    await db.update_order(oid, {"status": "rejected"})
    await call.answer("Rejected.")
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    try:
        await bot.send_message(
            order["user_id"],
            f"{e('cross')} Your order for <b>{order['product_name']}</b> was rejected. "
            f"If you believe this is a mistake, contact support.",
        )
    except Exception:
        pass
    await call.message.answer(f"{e('cross')} Order <code>{oid}</code> rejected.")


# ---------------- Top-ups ----------------
@router.callback_query(F.data == "admin:topups")
async def cb_topups(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    topups = [t async for t in db.db().topups.find({"status": "pending"}).sort("created", 1).limit(20)]
    if not topups:
        await safe_edit(call.message,
                        f"{premium('money')} <b>Pending Top-ups</b>\n\nNone right now. {e('check')}",
                        admin_back_kb())
        await call.answer()
        return
    await safe_edit(call.message,
                    f"{premium('money')} <b>Pending Top-ups</b>\n\nReview each below:",
                    admin_back_kb())
    for t in topups:
        tid = str(t["_id"])
        text = (
            f"{e('money')} <b>Top-up</b> <code>{tid}</code>\n"
            f"{e('user')} User: <code>{t['user_id']}</code>\n"
            f"{e('wallet')} Amount: ${t['amount']:.2f} • {t['method'].upper()}"
        )
        if t.get("proof_file_id"):
            await call.message.answer_photo(t["proof_file_id"], caption=text,
                                            reply_markup=admin_topup_kb(tid))
        else:
            await call.message.answer(text, reply_markup=admin_topup_kb(tid))
    await call.answer()


@router.callback_query(F.data.startswith("admin:topup:approve:"))
async def cb_topup_approve(call: CallbackQuery, bot: Bot) -> None:
    tid = call.data.split(":", 3)[3]
    topup = await db.get_topup(tid)
    if not topup or topup["status"] != "pending":
        await call.answer("Already handled.", show_alert=True)
        return
    await db.update_topup(tid, {"status": "approved"})
    await db.adjust_balance(topup["user_id"], float(topup["amount"]))
    await call.answer("Approved.")
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    user = await db.get_user(topup["user_id"])
    try:
        await bot.send_message(
            topup["user_id"],
            f"{premium('check')} <b>Top-up approved!</b>\n\n"
            f"{e('money')} Added: ${topup['amount']:.2f}\n"
            f"{e('wallet')} New balance: ${user.get('balance', 0.0):.2f}",
        )
    except Exception:
        pass
    await call.message.answer(f"{premium('check')} Top-up <code>{tid}</code> approved.")


@router.callback_query(F.data.startswith("admin:topup:reject:"))
async def cb_topup_reject(call: CallbackQuery, bot: Bot) -> None:
    tid = call.data.split(":", 3)[3]
    topup = await db.get_topup(tid)
    if not topup:
        await call.answer("Not found.", show_alert=True)
        return
    await db.update_topup(tid, {"status": "rejected"})
    await call.answer("Rejected.")
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    try:
        await bot.send_message(
            topup["user_id"],
            f"{e('cross')} Your top-up of ${topup['amount']:.2f} was rejected. "
            f"Contact support if needed.",
        )
    except Exception:
        pass
    await call.message.answer(f"{e('cross')} Top-up <code>{tid}</code> rejected.")


# ---------------- Users ----------------
@router.callback_query(F.data == "admin:users")
async def cb_users(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    total = await db.count_users()
    await safe_edit(call.message,
                    f"{premium('gem')} <b>User Management</b>\n\n"
                    f"{e('users')} Total users: <b>{total}</b>",
                    admin_users_kb())
    await call.answer()


@router.callback_query(F.data == "admin:user:top")
async def cb_user_top(call: CallbackQuery) -> None:
    top = await db.top_users(10)
    lines = [f"{premium('crown')} <b>Top Buyers</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(top):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = u.get("username") and f"@{u['username']}" or str(u["user_id"])
        lines.append(f"{medal} {name} — ${u.get('total_spent', 0.0):.2f}")
    if len(lines) == 1:
        lines.append("No data yet.")
    await safe_edit(call.message, "\n".join(lines), admin_users_kb())
    await call.answer()


@router.callback_query(F.data == "admin:user:balance")
async def cb_user_balance(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBalance.user_id)
    await safe_edit(call.message,
                    f"{e('user')} Send the <b>user ID</b> to adjust balance for:",
                    cancel_kb("admin:users"))
    await call.answer()


@router.message(AdminBalance.user_id)
async def balance_userid(message: Message, state: FSMContext) -> None:
    uid = message.text.strip()
    if not uid.isdigit():
        await message.answer(f"{e('warning')} Send a numeric user ID.")
        return
    user = await db.get_user(int(uid))
    if not user:
        await message.answer(f"{e('warning')} User not found (they must /start the bot first).")
        return
    await state.update_data(target_id=int(uid))
    await state.set_state(AdminBalance.amount)
    await message.answer(
        f"{e('money')} Current balance: ${user.get('balance', 0.0):.2f}\n\n"
        f"Send the amount to add (use a negative number to deduct, e.g. <code>-5</code>):"
    )


@router.message(AdminBalance.amount)
async def balance_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    try:
        amount = round(float(message.text.strip()), 2)
    except ValueError:
        await message.answer(f"{e('warning')} Invalid number.")
        return
    data = await state.get_data()
    target = data["target_id"]
    await db.adjust_balance(target, amount)
    await state.clear()
    user = await db.get_user(target)
    await message.answer(
        f"{premium('check')} Balance updated.\n"
        f"{e('wallet')} New balance for <code>{target}</code>: ${user.get('balance', 0.0):.2f}"
    )
    try:
        await bot.send_message(
            target,
            f"{e('bell')} Your wallet was adjusted by an admin: "
            f"{'+' if amount >= 0 else ''}{amount:.2f}\n"
            f"{e('wallet')} New balance: ${user.get('balance', 0.0):.2f}",
        )
    except Exception:
        pass
    await render_admin_home(message)


@router.message(Command("ban"))
async def cmd_ban(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer(f"{e('info')} Usage: <code>/ban &lt;user_id&gt;</code>")
        return
    await db.set_banned(int(parts[1]), True)
    await message.answer(f"{e('lock')} User <code>{parts[1]}</code> banned.")


@router.message(Command("unban"))
async def cmd_unban(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer(f"{e('info')} Usage: <code>/unban &lt;user_id&gt;</code>")
        return
    await db.set_banned(int(parts[1]), False)
    await message.answer(f"{e('check')} User <code>{parts[1]}</code> unbanned.")


# ---------------- Broadcast ----------------
@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBroadcast.message)
    await safe_edit(
        call.message,
        f"{premium('rocket')} <b>Broadcast</b>\n\n"
        f"Send the message you want to broadcast to all users. "
        f"HTML formatting is supported.",
        cancel_kb("admin:home"),
    )
    await call.answer()


@router.message(AdminBroadcast.message)
async def broadcast_preview(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.html_text)
    await state.set_state(AdminBroadcast.confirm)
    total = await db.count_users()
    await message.answer(
        f"{e('megaphone')} <b>Preview</b>\n\n{message.html_text}\n\n"
        f"{e('users')} This will be sent to <b>{total}</b> users. Confirm?",
        reply_markup=broadcast_confirm_kb(),
    )


@router.callback_query(F.data == "admin:broadcast:send")
async def cb_broadcast_send(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    text = data.get("text")
    await state.clear()
    if not text:
        await call.answer("Nothing to send.", show_alert=True)
        return
    await call.answer("Broadcasting...")
    ids = await db.all_user_ids()
    sent, failed = 0, 0
    for uid in ids:
        try:
            await bot.send_message(uid, text, disable_web_page_preview=True)
            sent += 1
        except Exception:
            failed += 1
    await call.message.answer(
        f"{premium('check')} <b>Broadcast complete!</b>\n\n"
        f"{e('check')} Sent: {sent}\n{e('cross')} Failed: {failed}"
    )
    await render_admin_home(call.message)


# ---------------- Settings ----------------
SETTING_LABELS = {
    "shop_name": "Shop Name",
    "welcome_text": "Welcome Text",
    "support_username": "Support Username (without @)",
    "usdt_trc20_address": "USDT TRC20 Address",
    "usdt_bep20_address": "USDT BEP20 Address",
    "stars_per_unit": "Stars per $1 (integer)",
    "referral_reward": "Referral Reward (USD)",
    "force_join_channel": "Force-Join Channel (username without @, or - to disable)",
}


@router.callback_query(F.data == "admin:settings")
async def cb_settings(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    s = await db.get_settings()
    text = (
        f"{premium('gem')} <b>Settings</b>\n\n"
        f"{e('tag')} Shop: <b>{s['shop_name']}</b>\n"
        f"{e('support')} Support: @{s['support_username']}\n"
        f"{e('star')} Stars/$: <b>{s['stars_per_unit']}</b>\n"
        f"{e('gift')} Referral: <b>${s['referral_reward']:.2f}</b>\n"
        f"{e('bell')} Force-join: <b>{s.get('force_join_channel') or 'off'}</b>\n"
        f"{e('lock')} Shop open: <b>{'Yes' if s.get('shop_open', True) else 'No'}</b>\n"
        f"{e('crypto')} TRC20: <code>{s.get('usdt_trc20_address') or 'not set'}</code>\n"
        f"{e('crypto')} BEP20: <code>{s.get('usdt_bep20_address') or 'not set'}</code>"
    )
    await safe_edit(call.message, text, admin_settings_kb())
    await call.answer()


# ---------------- Premium / Custom Emoji manager ----------------
async def render_emoji_manager(call: CallbackQuery) -> None:
    current = get_premium_overrides()
    lines = [
        f"{premium('stars')} <b>Premium Emoji Manager</b>\n",
        "Attach a Telegram <b>custom (premium) emoji</b> to each accent used "
        "across the bot. The chosen emoji renders for everyone, with a safe "
        "unicode fallback.\n",
        f"{e('info')} Tap a name, then simply <b>send that premium emoji</b> "
        "(or paste its numeric ID). Send <code>-</code> to clear it.\n",
    ]
    for k in PREMIUM_KEYS:
        eid = effective_emoji_id(k)
        status = f"<code>{eid}</code>" if eid else "default"
        lines.append(f"{premium(k)} <b>{k}</b> — {status}")
    await safe_edit(call.message, "\n".join(lines),
                    admin_emojis_kb(PREMIUM_KEYS, current))


@router.callback_query(F.data == "admin:emojis")
async def cb_emojis(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await render_emoji_manager(call)
    await call.answer()


@router.callback_query(F.data == "admin:emoji:reset")
async def cb_emoji_reset(call: CallbackQuery, state: FSMContext) -> None:
    await db.update_setting("custom_emojis", {})
    set_premium_overrides({})
    await call.answer("All custom emojis reset to defaults.")
    await render_emoji_manager(call)


@router.callback_query(F.data.startswith("admin:emoji:set:"))
async def cb_emoji_set(call: CallbackQuery, state: FSMContext) -> None:
    key = call.data.split(":", 3)[3]
    if key not in PREMIUM_KEYS:
        await call.answer()
        return
    await state.set_state(AdminSetting.value)
    await state.update_data(setting=f"emoji:{key}")
    await safe_edit(
        call.message,
        f"{e('stars')} Set premium emoji for <b>{key}</b>.\n\n"
        f"{e('down')} <b>Send the premium emoji</b> directly, or paste its numeric "
        f"<code>custom_emoji_id</code>.\n"
        f"{e('info')} Send <code>-</code> to clear and use the default.",
        cancel_kb("admin:emojis"),
    )
    await call.answer()


@router.callback_query(F.data == "admin:set:toggle_shop")
async def cb_toggle_shop(call: CallbackQuery, state: FSMContext) -> None:
    s = await db.get_settings()
    new_val = not s.get("shop_open", True)
    await db.update_setting("shop_open", new_val)
    await call.answer(f"Shop is now {'OPEN' if new_val else 'CLOSED'}.")
    await cb_settings(call, state)


@router.callback_query(F.data.startswith("admin:set:"))
async def cb_set_field(call: CallbackQuery, state: FSMContext) -> None:
    key = call.data.split(":", 2)[2]
    if key not in SETTING_LABELS:
        await call.answer()
        return
    await state.set_state(AdminSetting.value)
    await state.update_data(setting=key)
    await safe_edit(call.message,
                    f"{e('pencil')} Send the new value for <b>{SETTING_LABELS[key]}</b>:",
                    cancel_kb("admin:settings"))
    await call.answer()


@router.message(AdminSetting.value)
async def setting_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    key = data.get("setting")
    raw = (message.text or "").strip()

    # Special case: setting a premium/custom emoji ID for a logical accent name
    if key and key.startswith("emoji:"):
        name = key.split(":", 1)[1]
        emoji_id: str | None = None
        # Prefer extracting the custom_emoji_id from a sent premium emoji
        for ent in (message.entities or []):
            if ent.type == "custom_emoji" and ent.custom_emoji_id:
                emoji_id = ent.custom_emoji_id
                break
        if emoji_id is None:
            if raw in ("-", "off", "none", "default", ""):
                emoji_id = None
            elif raw.isdigit():
                emoji_id = raw
            else:
                await message.answer(
                    f"{e('warning')} Send a premium emoji, a numeric ID, or "
                    f"<code>-</code> to clear."
                )
                return
        set_one_override(name, emoji_id)
        await db.update_setting("custom_emojis", get_premium_overrides())
        await state.clear()
        shown = f"<code>{emoji_id}</code>" if emoji_id else "default"
        await message.answer(
            f"{premium('check')} Premium emoji for <b>{name}</b> set to {shown}.\n"
            f"Preview: {premium(name)}"
        )
        return

    # Special case: editing a product price from product view
    if key == "product_price":
        pid = data.get("product_id")
        try:
            price = round(float(raw), 2)
        except ValueError:
            await message.answer(f"{e('warning')} Invalid price.")
            return
        await db.update_product(pid, {"price": price})
        await state.clear()
        product = await db.get_product(pid)
        await message.answer(f"{premium('check')} Price updated to ${price:.2f}.")
        if product:
            await message.answer(f"{premium('gem')} <b>{product['name']}</b>",
                                 reply_markup=admin_prod_view_kb(product))
        return

    # Numeric settings
    if key == "stars_per_unit":
        if not raw.isdigit():
            await message.answer(f"{e('warning')} Send a whole number.")
            return
        await db.update_setting(key, int(raw))
    elif key == "referral_reward":
        try:
            await db.update_setting(key, round(float(raw), 2))
        except ValueError:
            await message.answer(f"{e('warning')} Send a number.")
            return
    elif key == "force_join_channel":
        val = "" if raw in ("-", "off", "none") else raw.lstrip("@")
        await db.update_setting(key, val)
    else:
        await db.update_setting(key, raw)

    await state.clear()
    await message.answer(f"{premium('check')} <b>{SETTING_LABELS.get(key, key)}</b> updated!")
    await render_admin_home(message)
