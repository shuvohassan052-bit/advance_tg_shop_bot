"""
Payment processing for product purchases:
  - wallet  : instant, deducts balance, delivers immediately
  - stars   : Telegram Stars invoice (XTR), delivers on successful_payment
  - usdt    : manual crypto proof -> admin approval -> delivery
"""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from .. import config, db
from ..emojis import e, premium
from ..keyboards import back_home, cancel_kb
from ..states import BuyProof
from ..utils import deliver_product, notify_admins, safe_edit
from ..keyboards import admin_order_kb

router = Router(name="payments")


def _stars_amount(price: float, settings: dict) -> int:
    per_unit = int(settings.get("stars_per_unit", 50))
    return max(1, int(round(price * per_unit)))


# ---------------- Wallet payment ----------------
@router.callback_query(F.data.startswith("buy:pay:wallet:"))
async def cb_pay_wallet(call: CallbackQuery, bot: Bot) -> None:
    pid = call.data.split(":", 3)[3]
    product = await db.get_product(pid)
    if not product:
        await call.answer("Product not found.", show_alert=True)
        return

    user = await db.get_user(call.from_user.id)
    price = float(product["price"])
    if user.get("balance", 0.0) < price:
        await call.answer("Insufficient wallet balance. Please top up.", show_alert=True)
        return

    if product.get("delivery_mode") == "auto" and await db.stock_count(pid) <= 0:
        await call.answer("This item just went out of stock.", show_alert=True)
        return

    # Deduct and create order
    await db.adjust_balance(call.from_user.id, -price)
    order_id = await db.create_order(call.from_user.id, product, "wallet", status="approved")
    await db.mark_user_purchase(call.from_user.id, price)
    await _handle_referral_reward(bot, call.from_user.id)

    delivered, _ = await deliver_product(bot, call.from_user.id, product, order_id)

    await safe_edit(
        call.message,
        f"{premium('check')} <b>Purchase successful!</b>\n\n"
        f"{e('tag')} {product['name']}\n"
        f"{e('money')} Paid: ${price:.2f} (wallet)\n\n"
        + (f"{e('rocket')} Delivered above {premium('fire')}"
           if delivered else f"{e('hourglass')} Manual delivery in progress."),
        back_home(),
    )
    await call.answer("Done!")

    await notify_admins(
        bot,
        f"{e('money')} <b>New Wallet Sale</b>\n"
        f"User: <code>{call.from_user.id}</code>\n"
        f"Product: {product['name']}\n"
        f"Amount: ${price:.2f}\n"
        f"Status: {'Delivered' if delivered else 'Manual pending'}",
    )


# ---------------- Telegram Stars payment ----------------
@router.callback_query(F.data.startswith("buy:pay:stars:"))
async def cb_pay_stars(call: CallbackQuery, bot: Bot) -> None:
    pid = call.data.split(":", 3)[3]
    product = await db.get_product(pid)
    if not product:
        await call.answer("Product not found.", show_alert=True)
        return

    if product.get("delivery_mode") == "auto" and await db.stock_count(pid) <= 0:
        await call.answer("This item just went out of stock.", show_alert=True)
        return

    settings = await db.get_settings()
    stars = _stars_amount(float(product["price"]), settings)

    await call.answer()
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=product["name"][:32],
        description=(product.get("description") or product["name"])[:255],
        # payload encodes purchase intent: prod|<product_id>
        payload=f"prod|{pid}",
        currency=config.STARS_CURRENCY,
        prices=[LabeledPrice(label=product["name"][:32], amount=stars)],
        start_parameter="buy",
    )


# ---------------- USDT manual payment ----------------
@router.callback_query(F.data.startswith("buy:pay:usdt:"))
async def cb_pay_usdt(call: CallbackQuery, state: FSMContext) -> None:
    pid = call.data.split(":", 3)[3]
    product = await db.get_product(pid)
    if not product:
        await call.answer("Product not found.", show_alert=True)
        return

    settings = await db.get_settings()
    trc = settings.get("usdt_trc20_address", "") or "Not configured"
    bep = settings.get("usdt_bep20_address", "") or "Not configured"

    await state.set_state(BuyProof.proof)
    await state.update_data(product_id=pid)

    text = (
        f"{e('crypto')} <b>Pay with USDT</b>\n\n"
        f"{e('tag')} {product['name']}\n"
        f"{e('money')} Amount: <b>${product['price']:.2f}</b> (in USDT)\n\n"
        f"{e('down')} <b>Send to one of these addresses:</b>\n"
        f"<b>TRC20:</b> <code>{trc}</code>\n"
        f"<b>BEP20:</b> <code>{bep}</code>\n\n"
        f"{e('receipt')} After paying, <b>send a screenshot</b> of the transaction "
        f"here as proof. An admin will verify and deliver your order."
    )
    await safe_edit(call.message, text, cancel_kb(f"shop:prod:{pid}"))
    await call.answer()


@router.message(BuyProof.proof, F.photo)
async def buy_proof_received(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    pid = data.get("product_id")
    await state.clear()
    product = await db.get_product(pid) if pid else None
    if not product:
        await message.answer("Product no longer available.", reply_markup=back_home())
        return

    file_id = message.photo[-1].file_id
    order_id = await db.create_order(message.from_user.id, product, "usdt", status="pending")
    await db.update_order(order_id, {"proof_file_id": file_id})

    await message.answer(
        f"{premium('check')} <b>Proof submitted!</b>\n\n"
        f"{e('tag')} {product['name']}\n"
        f"{e('hourglass')} Your order is pending admin verification. "
        f"You'll be notified once approved.",
        reply_markup=back_home(),
    )

    caption = (
        f"{e('crypto')} <b>New USDT Order</b>\n"
        f"Order: <code>{order_id}</code>\n"
        f"User: <code>{message.from_user.id}</code> (@{message.from_user.username or 'n/a'})\n"
        f"Product: {product['name']}\n"
        f"Amount: ${product['price']:.2f}"
    )
    await notify_admins(bot, caption, reply_markup=admin_order_kb(order_id, message.from_user.id),
                        photo=file_id)


@router.message(BuyProof.proof)
async def buy_proof_invalid(message: Message) -> None:
    await message.answer(
        f"{e('warning')} Please send a <b>screenshot (photo)</b> of your payment, "
        f"or tap Cancel."
    )


# ---------------- Stars: pre-checkout + success (shared for product & topup) ----------------
@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, bot: Bot) -> None:
    sp = message.successful_payment
    payload = sp.invoice_payload or ""
    settings = await db.get_settings()

    if payload.startswith("prod|"):
        pid = payload.split("|", 1)[1]
        product = await db.get_product(pid)
        if not product:
            await message.answer(f"{e('warning')} Product not found. Contact support.")
            return
        order_id = await db.create_order(message.from_user.id, product, "stars",
                                         status="approved")
        await db.mark_user_purchase(message.from_user.id, float(product["price"]))
        await _handle_referral_reward(bot, message.from_user.id)
        delivered, _ = await deliver_product(bot, message.from_user.id, product, order_id)
        await message.answer(
            f"{premium('check')} <b>Payment received via Stars!</b>\n"
            + (f"{e('rocket')} Your order has been delivered."
               if delivered else f"{e('hourglass')} Manual delivery in progress."),
            reply_markup=back_home(),
        )
        await notify_admins(
            bot,
            f"{e('star')} <b>New Stars Sale</b>\n"
            f"User: <code>{message.from_user.id}</code>\n"
            f"Product: {product['name']}\n"
            f"Stars: {sp.total_amount}",
        )

    elif payload.startswith("topup|"):
        # topup|<amount>
        try:
            amount = float(payload.split("|", 1)[1])
        except ValueError:
            amount = 0.0
        await db.adjust_balance(message.from_user.id, amount)
        await db.create_topup(message.from_user.id, amount, "stars", status="approved")
        user = await db.get_user(message.from_user.id)
        await message.answer(
            f"{premium('check')} <b>Wallet topped up!</b>\n\n"
            f"{e('money')} Added: ${amount:.2f}\n"
            f"{e('wallet')} New balance: ${user.get('balance', 0.0):.2f}",
            reply_markup=back_home(),
        )


async def _handle_referral_reward(bot: Bot, user_id: int) -> None:
    """Grant a one-time referral reward to the referrer on the user's first purchase."""
    user = await db.get_user(user_id)
    if not user:
        return
    # Only on first purchase
    if user.get("orders_count", 0) != 1:
        return
    ref_by = user.get("ref_by")
    if not ref_by:
        return
    settings = await db.get_settings()
    reward = float(settings.get("referral_reward", 0.0))
    if reward <= 0:
        return
    await db.adjust_balance(ref_by, reward)
    await db.db().users.update_one({"user_id": ref_by}, {"$inc": {"ref_earned": reward}})
    try:
        await bot.send_message(
            ref_by,
            f"{premium('gem')} <b>Referral reward!</b>\n\n"
            f"You earned <b>${reward:.2f}</b> because someone you referred made "
            f"their first purchase. {premium('fire')}",
        )
    except Exception:
        pass
