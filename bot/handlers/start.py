"""Start command, main menu navigation, misc (about/support/referral/force-join)."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import config, db
from ..emojis import e, premium
from ..keyboards import back_home, force_join_kb, main_menu, referral_kb
from ..utils import is_user_joined, safe_edit

router = Router(name="start")


async def render_home(target: Message, user_id: int, settings: dict, edit: bool = False) -> None:
    text = (
        f"{premium('crown')} <b>{settings['shop_name']}</b>\n\n"
        + settings["welcome_text"].format(shop_name=settings["shop_name"])
        + f"\n\n{premium('fire')} <i>Fast delivery • Trusted • 24/7</i>"
    )
    kb = main_menu(is_admin=config.is_admin(user_id))
    if edit:
        await safe_edit(target, text, kb)
    else:
        await target.answer(text, reply_markup=kb, disable_web_page_preview=True)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    settings = await db.get_settings()

    # Referral parsing: /start ref_123456
    ref_by = None
    if command.args and command.args.startswith("ref_"):
        tail = command.args[4:]
        if tail.isdigit():
            ref_by = int(tail)

    u = message.from_user
    await db.get_or_create_user(
        u.id, u.username or "", u.full_name or "", ref_by=ref_by
    )

    user_doc = await db.get_user(u.id)
    if user_doc and user_doc.get("banned"):
        await message.answer(f"{e('lock')} You are banned from using this bot.")
        return

    # Force-join gate
    channel = settings.get("force_join_channel", "")
    if channel and not config.is_admin(u.id):
        joined = await is_user_joined(bot, channel, u.id)
        if not joined:
            await message.answer(
                f"{e('bell')} <b>One step away!</b>\n\n"
                f"Please join our channel to use the bot, then tap "
                f"<b>I've Joined</b>.",
                reply_markup=force_join_kb(channel),
            )
            return

    await render_home(message, u.id, settings)


@router.callback_query(F.data == "nav:home")
async def cb_home(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    settings = await db.get_settings()
    await render_home(call.message, call.from_user.id, settings, edit=True)
    await call.answer()


@router.callback_query(F.data == "misc:checkjoin")
async def cb_checkjoin(call: CallbackQuery, bot: Bot) -> None:
    settings = await db.get_settings()
    channel = settings.get("force_join_channel", "")
    if await is_user_joined(bot, channel, call.from_user.id):
        await render_home(call.message, call.from_user.id, settings, edit=True)
        await call.answer("Welcome!")
    else:
        await call.answer("You haven't joined yet.", show_alert=True)


@router.callback_query(F.data == "misc:about")
async def cb_about(call: CallbackQuery) -> None:
    settings = await db.get_settings()
    text = (
        f"{premium('gem')} <b>About {settings['shop_name']}</b>\n\n"
        f"{e('tv')} Premium OTT & AI subscriptions at the best prices.\n"
        f"{e('rocket')} Instant automated delivery for in-stock items.\n"
        f"{e('lock')} Secure payments via USDT & Telegram Stars.\n"
        f"{e('wallet')} Reloadable wallet for one-tap purchases.\n"
        f"{e('gift')} Earn rewards by referring friends.\n\n"
        f"{e('support')} Support: @{settings['support_username']}"
    )
    await safe_edit(call.message, text, back_home())
    await call.answer()


@router.callback_query(F.data == "misc:support")
async def cb_support(call: CallbackQuery) -> None:
    settings = await db.get_settings()
    text = (
        f"{e('support')} <b>Need help?</b>\n\n"
        f"Contact our support team and we'll assist you as fast as possible.\n\n"
        f"{e('user')} <b>Support:</b> @{settings['support_username']}"
    )
    await safe_edit(call.message, text, back_home())
    await call.answer()


@router.callback_query(F.data == "ref:home")
async def cb_referral(call: CallbackQuery, bot: Bot) -> None:
    settings = await db.get_settings()
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{call.from_user.id}"
    user = await db.get_user(call.from_user.id)
    reward = settings.get("referral_reward", 0.0)
    text = (
        f"{premium('gem')} <b>Refer & Earn</b>\n\n"
        f"Invite friends and earn <b>${reward:.2f}</b> when they make their "
        f"first purchase!\n\n"
        f"{e('users')} Referrals: <b>{user.get('ref_count', 0)}</b>\n"
        f"{e('money')} Earned: <b>${user.get('ref_earned', 0.0):.2f}</b>\n\n"
        f"{e('link')} <b>Your link:</b>\n<code>{link}</code>"
    )
    await safe_edit(call.message, text, referral_kb(link))
    await call.answer()
