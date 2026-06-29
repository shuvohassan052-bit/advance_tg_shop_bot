"""
Bot entrypoint. Run with:  python -m bot.main
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from . import config, db
from .emojis import set_premium_overrides
from .handlers import get_main_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("ott-bot")


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Open the shop"),
        BotCommand(command="admin", description="🛠 Admin panel (admins only)"),
    ])


async def main() -> None:
    if not config.BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not set. Add it to .env.development.local or your environment."
        )
    if not config.ADMIN_IDS:
        log.warning("ADMIN_IDS is empty — no one will have admin access.")

    # Connect DB
    await db.init_db()
    log.info("Connected to MongoDB: %s", config.DB_NAME)

    # Load premium emoji overrides from settings
    settings = await db.get_settings()
    set_premium_overrides(settings.get("custom_emojis", {}))

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(get_main_router())

    await set_commands(bot)
    me = await bot.get_me()
    log.info("Starting @%s (%s)", me.username, me.id)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await db.close_db()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped.")
