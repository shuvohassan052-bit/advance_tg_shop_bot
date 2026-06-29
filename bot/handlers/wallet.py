"""Wallet: view balance, top up via USDT (manual proof) or Telegram Stars."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message

from .. import config, db
from ..emojis import e, premium
from ..keyboards import (
    admin_topup_kb,
    back_home,
    cancel_kb,
    wallet_kb,
)
from ..states import TopUp
from ..utils import notify_admins, safe_edit

router = Router(name="wallet")


@router.callback_query(F.data == "wallet:home")
async def cb_wallet_home(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(call.from_user.id)
    text = (
        f"{premium('money')} <b>My Wallet</b>\n\n"
        f"{e('wallet')} <b>Balance:</b> ${user.get('balance', 0.0):.2f}\n"
        f"{e('chart')} <b>Total spent:</b> ${user.get('total_spent', 0.0):.2f}\n"
        f"{e('receipt')} <b>Orders:</b> {user.get('orders_count', 0)}\n\n"
        f"Top up your wallet to buy instantly with one tap."
    )
    await safe_edit(call.message, text, wallet_kb())
    await call.answer()


# ---------------- USDT top-up ----------------
@router.callback_query(F.data == "wallet:topup:usdt")
async def cb_topup_usdt(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TopUp.amount)
    await state.update_data(method="usdt")
    settings = await db.get_settings()
    await safe_edit(
        call.message,
        f"{e('crypto')} <b>USDT Top-Up</b>\n\n"
        f"Enter the amount (in USD) you want to add.\n"
        f"{e('info')} Minimum: ${settings.get('min_topup', 1.0):.2f}",
        cancel_kb("wallet:home"),
    )
    await call.answer()


# ---------------- Stars top-up ----------------
@router.callback_query(F.data == "wallet:topup:stars")
async def cb_topup_stars(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TopUp.amount)
    await state.update_data(method="stars")
    settings = await db.get_settings()
    await safe_edit(
        call.message,
        f"{e('star')} <b>Stars Top-Up</b>\n\n"
        f"Enter the amount (in USD) you want to add. You'll pay with Telegram Stars.\n"
        f"{e('info')} Rate: {int(settings.get('stars_per_unit', 50))} Stars = $1.00",
        cancel_kb("wallet:home"),
    )
    await call.answer()


@router.message(TopUp.amount)
async def topup_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    settings = await db.get_settings()
    try:
        amount = round(float(message.text.strip()), 2)
    except (ValueError, AttributeError):
        await message.answer(f"{e('warning')} Please enter a valid number, e.g. <code>10</code>.")
        return
    min_topup = float(settings.get("min_topup", 1.0))
    if amount < min_topup:
        await message.answer(f"{e('warning')} Minimum top-up is ${min_topup:.2f}.")
        return

    data = await state.get_data()
    method = data.get("method", "usdt")

    if method == "stars":
        await state.clear()
        stars = max(1, int(round(amount * int(settings.get("stars_per_unit", 50)))))
        await bot.send_invoice(
            chat_id=message.from_user.id,
            title="Wallet Top-Up",
            description=f"Add ${amount:.2f} to your wallet balance.",
            payload=f"topup|{amount}",
            currency=config.STARS_CURRENCY,
            prices=[LabeledPrice(label=f"Top up ${amount:.2f}", amount=stars)],
            start_parameter="topup",
        )
        return

    # USDT: ask for proof
    await state.update_data(amount=amount)
    await state.set_state(TopUp.proof)
    trc = settings.get("usdt_trc20_address", "") or "Not configured"
    bep = settings.get("usdt_bep20_address", "") or "Not configured"
    await message.answer(
        f"{e('crypto')} <b>Send ${amount:.2f} in USDT to:</b>\n\n"
        f"<b>TRC20:</b> <code>{trc}</code>\n"
        f"<b>BEP20:</b> <code>{bep}</code>\n\n"
        f"{e('receipt')} Then send a <b>screenshot</b> of the transaction here.",
        reply_markup=cancel_kb("wallet:home"),
    )


@router.message(TopUp.proof, F.photo)
async def topup_proof(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    amount = float(data.get("amount", 0.0))
    await state.clear()

    file_id = message.photo[-1].file_id
    topup_id = await db.create_topup(message.from_user.id, amount, "usdt", status="pending")
    await db.update_topup(topup_id, {"proof_file_id": file_id})

    await message.answer(
        f"{premium('check')} <b>Top-up request submitted!</b>\n\n"
        f"{e('money')} Amount: ${amount:.2f}\n"
        f"{e('hourglass')} Pending admin approval. You'll be notified once confirmed.",
        reply_markup=back_home(),
    )

    caption = (
        f"{e('money')} <b>New USDT Top-Up</b>\n"
        f"ID: <code>{topup_id}</code>\n"
        f"User: <code>{message.from_user.id}</code> (@{message.from_user.username or 'n/a'})\n"
        f"Amount: ${amount:.2f}"
    )
    await notify_admins(bot, caption, reply_markup=admin_topup_kb(topup_id), photo=file_id)


@router.message(TopUp.proof)
async def topup_proof_invalid(message: Message) -> None:
    await message.answer(f"{e('warning')} Please send a <b>screenshot (photo)</b> or tap Cancel.")


# ---------------- History ----------------
@router.callback_query(F.data == "wallet:history")
async def cb_history(call: CallbackQuery) -> None:
    topups = [t async for t in db.db().topups.find(
        {"user_id": call.from_user.id}).sort("created", -1).limit(10)]
    if not topups:
        await safe_edit(call.message,
                        f"{e('receipt')} <b>Top-up History</b>\n\nNo top-ups yet.",
                        wallet_kb())
        await call.answer()
        return
    lines = [f"{premium('money')} <b>Top-up History</b>\n"]
    icons = {"pending": e("hourglass"), "approved": e("check"), "rejected": e("cross")}
    for t in topups:
        lines.append(
            f"{icons.get(t['status'], '')} ${t['amount']:.2f} • {t['method'].upper()} • "
            f"{t['status']}"
        )
    await safe_edit(call.message, "\n".join(lines), wallet_kb())
    await call.answer()
