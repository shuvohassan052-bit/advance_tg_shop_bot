"""
Central configuration for the OTT Subscription Shop Bot.
All secrets are read from environment variables (.env.development.local or system env).
"""
from __future__ import annotations

import os
from dotenv import load_dotenv

# Load env from local file when present (does not override real env vars)
load_dotenv(".env.development.local")
load_dotenv(".env")


def _get_admin_ids() -> set[int]:
    raw = os.getenv("ADMIN_IDS", "")
    ids: set[int] = set()
    for part in raw.replace(" ", "").split(","):
        if part.isdigit():
            ids.add(int(part))
    return ids


# ---- Core credentials ----
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME: str = os.getenv("DB_NAME", "ott_shop_bot")
ADMIN_IDS: set[int] = _get_admin_ids()

# ---- Branding / defaults (editable in-bot from Admin > Settings) ----
DEFAULTS = {
    "shop_name": "Premium OTT Store",
    "welcome_text": (
        "<b>Welcome to {shop_name}</b>\n\n"
        "Your one-stop store for premium <b>OTT & AI subscriptions</b> "
        "— ChatGPT Plus, Netflix, Spotify, YouTube Premium and more.\n\n"
        "Tap <b>Browse Products</b> to get started."
    ),
    "support_username": "YourSupport",
    "currency": "USD",
    # Telegram Stars conversion: how many Stars per 1 unit of currency (e.g. 1 USD = 50 Stars)
    "stars_per_unit": 50,
    # USDT wallet details for manual crypto payments
    "usdt_trc20_address": "",
    "usdt_bep20_address": "",
    # Minimum wallet top-up
    "min_topup": 1.0,
    # Referral reward (currency) granted to referrer on referred user's first purchase
    "referral_reward": 0.5,
    # Whether the shop is open
    "shop_open": True,
    # Force-join channel (username without @) — empty disables it
    "force_join_channel": "",
}

# Telegram Stars currency code
STARS_CURRENCY = "XTR"


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
