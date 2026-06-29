"""
╔══════════════════════════════════════════════════════════════╗
║   LUFFY STORE APEX ULTRA V26 — Final Premium UI Commerce OS  ║
║   Version 26.0 FINAL PREMIUM UI COMMERCE OS     ║
║   Final Premium UI — AI Brain Ultra — Smart Pay — Low RAM Smooth Core  ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import csv
import html
import io
import json
import logging
import os
import re
import random
import secrets
import string
import time
from dataclasses import dataclass
from typing import Any, Optional, Iterable

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter, TelegramServerError, TelegramNetworkError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except Exception:  # Motor is optional; SQLite fallback stays active.
    AsyncIOMotorClient = None


load_dotenv()

# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════

def env_int(name: str, default: int = 0) -> int:
    """Read .env integer safely. Accepts decimal text like 0.10 by converting to int fallback."""
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        try:
            return int(float(raw))
        except ValueError:
            return default

def env_float(name: str, default: float = 0.0) -> float:
    """Read .env float safely. Works for USDT values like 0.10, 2.50, etc."""
    raw = os.getenv(name, str(default)).strip()
    try:
        return float(raw)
    except ValueError:
        return default

def parse_amount(value, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return default

BOT_TOKEN      = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS      = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.strip().isdigit()]
DYNAMIC_ADMIN_IDS = set()  # admins granted from bot panel, loaded from database
SHOP_NAME      = os.getenv("SHOP_NAME", "LUFFY APEX AI STORE").strip()
SUPPORT_USER   = os.getenv("SUPPORT_USERNAME", "support").replace("@", "").strip()
CURRENCY       = os.getenv("DEFAULT_CURRENCY", "BDT").strip()
DB_PATH        = os.getenv("DB_PATH", "luffy_apex_v25_hypernova.db").strip()
MONGO_ENABLED  = os.getenv("MONGO_ENABLED", "0").strip() == "1"
MONGO_URI      = os.getenv("MONGO_URI", "").strip()
MONGO_DB_NAME  = os.getenv("MONGO_DB_NAME", "luffy_store_apex_v25").strip()
MONGO_AUTOSYNC = os.getenv("MONGO_AUTOSYNC", "0").strip() == "1"
MONGO_STARTUP_SYNC = os.getenv("MONGO_STARTUP_SYNC", "0").strip() == "1"
MONGO_SYNC_LIMIT = env_int("MONGO_SYNC_LIMIT", 300)
LOW_STOCK      = env_int("LOW_STOCK_ALERT", 3)
REFERRAL_BONUS = env_float("REFERRAL_BONUS", 20.0)
VIP_THRESHOLD  = env_int("VIP_THRESHOLD", 5)   # orders to become VIP
WALLET_ENABLED = os.getenv("WALLET_ENABLED", "1") == "1"
PAYMENT_WEBAPP_URL = os.getenv("PAYMENT_WEBAPP_URL", "").strip()  # Optional hosted HTML/WebApp payment page

# V22 Premium Motion UI + Speed Core
ANIMATION_ENABLED = os.getenv("ANIMATION_ENABLED", "1").strip() == "1"
ANIMATION_SPEED_MS = max(70, min(env_int("ANIMATION_SPEED_MS", 140), 450))
FAST_MODE = os.getenv("FAST_MODE", "1").strip() == "1"
HOME_STYLE = os.getenv("HOME_STYLE", "premium").strip().lower()
V25_UI_MODE = os.getenv("V25_UI_MODE", "balanced").strip().lower()  # turbo | balanced | luxury
V25_MAX_HOME_LINES = max(5, min(env_int("V25_MAX_HOME_LINES", 8), 12))
V25_CLEANUP_DAYS = max(1, min(env_int("V25_CLEANUP_DAYS", 14), 90))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing in .env")
if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS missing in .env")

router = Router()
APP_VERSION = "25.0 HYPERNOVA AI COMMERCE OS — WELCOME STUDIO 2.0 + AI BRAIN ULTRA + TURBO/SAFE MODE"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | LuffyStoreV26 | %(message)s",
)
logger = logging.getLogger("LuffyStoreV26")

# ═══════════════════════════════════════════════════════════════
#  UI HELPERS
# ═══════════════════════════════════════════════════════════════

def now() -> int:
    return int(time.time())

def esc(x) -> str:
    return html.escape(str(x or ""))

def money(amount) -> str:
    try:
        return f"{float(amount):,.2f} {CURRENCY}"
    except Exception:
        return f"{amount} {CURRENCY}"

def payment_ref_code(seed: str = "") -> str:
    """Short human-friendly reference/note for smart manual payment matching."""
    raw = re.sub(r"[^A-Z0-9]", "", str(seed or secrets.token_hex(4)).upper())
    raw = (raw[-8:] if raw else secrets.token_hex(4).upper()).ljust(8, "X")
    prefix = re.sub(r"[^A-Z]", "", SHOP_NAME.upper())[:4] or "SHOP"
    return f"{prefix}-{raw[:4]}-{raw[4:8]}"

def method_icon(title: str, method_id: str = "") -> str:
    t = f"{title} {method_id}".lower()
    if "binance" in t: return "🟡"
    if "bybit" in t or "bybit" in t: return "⚫"
    if "trc" in t or "tron" in t: return "🔺"
    if "bep" in t or "bsc" in t: return "🟨"
    if "usdt" in t: return "💲"
    if "bkash" in t or "বিকাশ" in t: return "🌸"
    if "nagad" in t or "নগদ" in t: return "🔴"
    if "rocket" in t: return "🚀"
    return "💳"

def code(prefix: str) -> str:
    return f"{prefix}-{time.strftime('%m%d%H%M')}-{secrets.token_hex(3).upper()}"


async def safe_edit(message: Message, text: str, **kwargs):
    """Fast safe edit: prevents common Telegram UI crashes and keeps callbacks smooth."""
    try:
        return await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        err = str(e).lower()
        if ("message is not modified" in err or "message to edit not found" in err
                or "there is no text in the message" in err or "query is too old" in err):
            return None
        # Fallback: send a fresh message when edit is impossible.
        if "message can't be edited" in err or "message to delete not found" in err:
            try:
                return await message.answer(text, **kwargs)
            except Exception:
                return None
        raise

def stars(rating: float) -> str:
    full = int(rating)
    half = 1 if rating - full >= 0.5 else 0
    empty = 5 - full - half
    return "★" * full + "½" * half + "☆" * empty

def progress_bar(val: int, total: int, width: int = 10) -> str:
    if total <= 0:
        return "░" * width
    filled = round((val / total) * width)
    return "█" * filled + "░" * (width - filled)

def header_box(title: str) -> str:
    return f"<b>『 {esc(title)} 』</b>"

def divider() -> str:
    return "┄" * 20

def preview_text(text: str, max_lines: int = 5, max_chars: int = 260) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    s = "\n".join(lines[:max_lines])
    if len(s) > max_chars:
        s = s[:max_chars].rstrip() + "…"
    return s

def card(title: str, body: str = "", footer: str = "") -> str:
    lines = [f"<blockquote>{header_box(title)}</blockquote>"]
    if body:
        lines.append(body)
    if footer:
        lines += [f"\n{divider()}", f"<i>{footer}</i>"]
    return "\n".join(lines)

def mini_card(title: str, body: str = "", footer: str = "") -> str:
    """Tiny mobile-first message card. Keeps Telegram chat screen clean."""
    parts = [f"<b>{esc(title)}</b>"]
    if body:
        parts.append(body)
    if footer:
        parts.append(f"<i>{esc(preview_text(footer, max_lines=1, max_chars=80))}</i>")
    return "\n".join(parts)

def status_badge(status: str) -> str:
    badges = {
        "WAITING_PROOF": "⏳ Waiting Proof",
        "PENDING":       "🔄 Pending Review",
        "PROCESSING":    "🛠 Processing",
        "DELIVERED":     "✅ Delivered",
        "COMPLETED":     "🏁 Completed",
        "REJECTED":      "❌ Rejected",
        "CANCELLED":     "🚫 Cancelled",
        "REFUNDED":      "💸 Refunded",
    }
    return badges.get(status, status)

def role_badge(role: str) -> str:
    return {"admin": "👑 Admin", "vendor": "🏪 Vendor", "vip": "💎 VIP", "user": "👤 User"}.get(role, role)

def glow_line(label: str, value: str) -> str:
    return f"<b>{esc(label)}</b> <code>{esc(value)}</code>"

def premium_card(title: str, subtitle: str = "", lines: list[str] | None = None, footer: str = "") -> str:
    """Premium mobile card: richer than mini_card but still short enough for Telegram screens."""
    out = [f"<b>╭─ {esc(title)}</b>"]
    if subtitle:
        out.append(f"<i>│ {esc(preview_text(subtitle, max_lines=1, max_chars=90))}</i>")
    if lines:
        out.append("│")
        for line in lines[:7]:
            out.append(f"│ {line}")
    out.append("<b>╰──────────────</b>")
    if footer:
        out.append(f"<i>{esc(preview_text(footer, max_lines=1, max_chars=90))}</i>")
    return "\n".join(out)

def admin_pulse_card(title: str, lines: list[str], footer: str = "") -> str:
    return premium_card(title, "Premium Control Center", lines, footer)

def neon_card(title: str, subtitle: str = "", lines: list[str] | None = None, footer: str = "") -> str:
    """V23 richer Telegram-safe design. No colors in Telegram buttons, so premium feel comes from spacing, icons and typography."""
    out = [f"<blockquote><b>✧ {esc(title)} ✧</b>"]
    if subtitle:
        out.append(f"<i>{esc(preview_text(subtitle, max_lines=2, max_chars=140))}</i>")
    out.append("</blockquote>")
    if lines:
        out.append("╭────────────────")
        for line in lines[:9]:
            out.append(f"│ {line}")
        out.append("╰────────────────")
    if footer:
        out.append(f"\n<i>{esc(preview_text(footer, max_lines=2, max_chars=160))}</i>")
    return "\n".join(out)

def feature_line(icon: str, label: str, value: str) -> str:
    return f"{esc(icon)} <b>{esc(label)}</b> <code>{esc(value)}</code>"

QUANTUM_THEMES = {
    "luxury_dark": {"icon": "🌌", "name": "Luxury Dark", "accent": "Noir premium / glass OS"},
    "neon_premium": {"icon": "🟣", "name": "Neon Premium", "accent": "Glow cyber / gamer store"},
    "clean_white": {"icon": "🤍", "name": "Clean White", "accent": "Minimal pro / readable"},
    "minimal_pro": {"icon": "⚪", "name": "Minimal Pro", "accent": "Short, sharp, fast"},
    "gaming_style": {"icon": "🎮", "name": "Gaming Style", "accent": "Game shop energy"},
}

async def active_theme() -> dict:
    key = await db.get("v24_theme") if 'db' in globals() else "luxury_dark"
    return QUANTUM_THEMES.get(key or "luxury_dark", QUANTUM_THEMES["luxury_dark"])

def quantum_card(title: str, subtitle: str = "", lines: list[str] | None = None, footer: str = "", theme_key: str = "luxury_dark") -> str:
    """V24 premium Telegram-safe card. Bigger and richer than V23, but still screen-friendly."""
    theme = QUANTUM_THEMES.get(theme_key or "luxury_dark", QUANTUM_THEMES["luxury_dark"])
    icon = theme["icon"]
    out = [f"<blockquote><b>{icon} {esc(title)} {icon}</b>"]
    if subtitle:
        out.append(f"<i>{esc(preview_text(subtitle, max_lines=2, max_chars=170))}</i>")
    out.append("</blockquote>")
    if lines:
        out.append("╭─✦ Quantum Panel ✦─")
        for line in lines[:10]:
            out.append(f"│ {line}")
        out.append("╰────────────────")
    if footer:
        out.append(f"\n<blockquote><i>{esc(preview_text(footer, max_lines=2, max_chars=170))}</i></blockquote>")
    return "\n".join(out)


V25_MODES = {
    "turbo": {"icon": "⚡", "name": "Turbo Mode", "desc": "fastest low-RAM response, minimal animation"},
    "balanced": {"icon": "🧬", "name": "Balanced Mode", "desc": "premium look with smooth performance"},
    "luxury": {"icon": "💎", "name": "Luxury Mode", "desc": "richer text and motion, best for stronger VPS"},
}

def v25_mode_meta(mode: str = "") -> dict:
    key = (mode or V25_UI_MODE or "balanced").lower()
    return V25_MODES.get(key, V25_MODES["balanced"])

def hypernova_card(title: str, subtitle: str = "", lines: list[str] | None = None, footer: str = "", mode: str = "") -> str:
    """V26 final premium card: clean hero, clear sections, no bullet-wall, no box overflow."""
    sub = esc(preview_text(subtitle, max_lines=2, max_chars=145)) if subtitle else ""
    out = [f"<b>{esc(title)}</b>"]
    if sub:
        out.append(f"<blockquote>{sub}</blockquote>")
    if lines:
        out.append("")
        for raw in lines[:18]:
            if raw is None:
                continue
            line = str(raw).rstrip()
            out.append(line if line else "")
    if footer:
        out.append(f"\n<i>{esc(preview_text(footer, max_lines=1, max_chars=95))}</i>")
    return "\n".join(out)

def v25_chip(label: str, value: str) -> str:
    return f"<b>{esc(label)}</b> <code>{esc(value)}</code>"

async def v25_home_footer() -> str:
    mode = await db.get("v25_safe_turbo_mode") or V25_UI_MODE or "balanced"
    footer = await db.get("shop_footer") or "HyperNova AI Store OS • smooth • smart • safe"
    return f"{footer} • {v25_mode_meta(mode)['name']}"

async def v25_autocleanup_once():
    """Small safe cleanup for 1GB VPS. Keeps logs light without touching users/orders/products."""
    if str(await db.get("v25_auto_cleanup_enabled") or "1") != "1":
        return
    cutoff = now() - V25_CLEANUP_DAYS * 86400
    jobs = [
        ("ai_logs", "created_at"),
        ("alert_logs", "created_at"),
        ("plugin_logs", "created_at"),
        ("security_events", "created_at"),
        ("gateway_attempts", "created_at"),
        ("autopay_logs", "created_at"),
    ]
    try:
        for table, col in jobs:
            if await db._table_exists(table):
                await db.conn.execute(f"DELETE FROM {table} WHERE {col} < ?", (cutoff,))
        await db.conn.commit()
        logger.info("V25 auto cleanup completed; cutoff=%s", cutoff)
    except Exception as e:
        logger.warning("V25 auto cleanup skipped: %s", e)

def receipt_card(order, extra: str = "") -> str:
    lines = [
        f"🧾 Order ID: <code>{esc(order['id'])}</code>",
        f"🛍 Product: <b>{esc(order['name'])}</b>",
        f"🔢 Qty: <b>{int(order['qty'] or 1)}</b>",
        f"💰 Amount: <b>{money(float(order['amount'] or 0) - float(order['discount'] or 0))}</b>",
        f"💳 Payment: <b>{esc(order['payment_method'] or 'N/A')}</b>",
        f"🚚 Status: <b>{esc(status_badge(order['status']))}</b>",
    ]
    if extra:
        lines.append(extra)
    return quantum_card("Smart Receipt", "Premium invoice generated from your order timeline", lines, "Save this order ID for support.")


async def motion(call_or_message, title: str = "Loading", final: str = "Ready"):
    """V26 premium journey animation. Turbo/FAST mode keeps it tiny."""
    if not ANIMATION_ENABLED:
        return None
    stages = ["⚡ Loading dashboard..."] if FAST_MODE else ["🌌 Opening store...", "🔍 Checking account...", "⚡ Loading smart dashboard..."]
    target_msg = getattr(call_or_message, "message", call_or_message)
    last = None
    for text_line in stages:
        text = f"<b>{esc(text_line)}</b>"
        try:
            if hasattr(call_or_message, "message"):
                last = await safe_edit(target_msg, text)
            else:
                last = await target_msg.answer(text)
            await asyncio.sleep(ANIMATION_SPEED_MS / 1000)
        except Exception:
            break
    return last


def btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data[:64])

def url_btn(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, url=url)

def kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)

def back_main() -> InlineKeyboardMarkup:
    return kb([[btn("🏠 Main Menu", "menu:main")]])

def cancel_kb() -> InlineKeyboardMarkup:
    return kb([[btn("❌ Cancel", "state:cancel")]])

def is_admin(uid: int) -> bool:
    return int(uid) in ADMIN_IDS or int(uid) in DYNAMIC_ADMIN_IDS

def all_admin_ids() -> list[int]:
    return sorted(set(int(x) for x in ADMIN_IDS) | set(int(x) for x in DYNAMIC_ADMIN_IDS))

async def stock_alert_threshold() -> int:
    raw = await db.get("stock_alert_low")
    return max(0, int(parse_amount(raw, LOW_STOCK)))

async def stock_alert_enabled(kind: str = "all") -> bool:
    if str(await db.get("stock_alerts_enabled") or "1") != "1":
        return False
    if kind == "added":
        return str(await db.get("stock_alert_added") or "1") == "1"
    if kind == "low":
        return str(await db.get("stock_alert_low_enabled") or "1") == "1"
    if kind == "out":
        return str(await db.get("stock_alert_out_enabled") or "1") == "1"
    return True

async def notify_stock_event(bot: Bot, product_id: str, event: str, added: int = 0, actor: str = "System"):
    """User-facing stock notifications.

    This is intentionally NOT admin-only. Users who subscribed to a product,
    added it to wishlist, or previously ordered it can receive alerts.
    Admin can switch audience to ALL users from Stock Alert Settings.
    """
    if not await stock_alert_enabled(event):
        return
    p = await db.fetchone("SELECT * FROM products WHERE id=? AND active=1", (product_id,))
    if not p:
        return
    sc = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE product_id=? AND used=0", (product_id,))
    avail = int(sc["n"] if sc else 0)
    threshold = await stock_alert_threshold()

    if event == "low" and avail == 0:
        return
    if event == "low" and avail > threshold:
        return
    if event == "out" and avail != 0:
        return

    audience = str(await db.get("stock_alert_audience") or "subscribers")
    if audience == "all":
        targets = await db.fetchall("SELECT id AS user_id FROM users WHERE is_banned=0")
    else:
        targets = await db.fetchall("""
            SELECT user_id FROM stock_watch WHERE product_id=?
            UNION SELECT user_id FROM wishlist WHERE product_id=?
            UNION SELECT user_id FROM orders WHERE product_id=?
        """, (product_id, product_id, product_id))

    title_map = {
        "added": "📦 Stock Available Now!",
        "low": "⚠️ Almost Sold Out!",
        "out": "🚫 Stock Out Update",
    }
    if event == "added":
        body = (
            f"💠 <b>{esc(p['name'])}</b>\n"
            f"💰 Price: <b>{money(p['price'])}</b>\n"
            f"📦 Available now: <b>{avail}</b> item(s)\n"
        )
        if added:
            body += f"➕ New stock added: <b>{added}</b>\n"
        body += "\nTap below to buy before it sells out."
    elif event == "low":
        body = (
            f"💠 <b>{esc(p['name'])}</b>\n"
            f"💰 Price: <b>{money(p['price'])}</b>\n"
            f"📦 Only <b>{avail}</b> left.\n\n"
            "Fast buyers may get it first."
        )
    else:
        body = (
            f"💠 <b>{esc(p['name'])}</b>\n"
            f"📦 Current stock: <b>0</b>\n\n"
            "You can keep notification ON. I will alert you when it restocks."
        )

    user_markup = kb([
        [btn("🛒 View Product", f"prod:{product_id}")],
        [btn("🔕 Stop Alerts", f"stock:unwatch:{product_id}"), btn("🏠 Menu", "menu:main")],
    ])
    sent = failed = 0
    seen = set()
    for row in targets:
        uid = int(row["user_id"])
        if uid in seen:
            continue
        seen.add(uid)
        try:
            await bot.send_message(uid, card(title_map.get(event, "🔔 Stock Alert"), body), reply_markup=user_markup)
            sent += 1
        except Exception:
            failed += 1

    # Small admin summary only, so owner knows alerts went out.
    summary = (
        f"Product: <b>{esc(p['name'])}</b>\n"
        f"Event: <b>{esc(event)}</b>\n"
        f"Current stock: <b>{avail}</b>\n"
        f"Audience: <b>{esc(audience)}</b>\n"
        f"Users notified: <b>{sent}</b>"
    )
    for aid in all_admin_ids():
        try:
            await bot.send_message(aid, card("📣 User Stock Alert Sent", summary), reply_markup=kb([
                [btn("⚙️ Alert Settings", "admin:stockalerts"), btn("🔐 Stock Panel", "admin:stock")]
            ]))
        except Exception:
            pass

# ── Keyboards ──────────────────────────────────────────────────

def main_menu(uid: int, role: str = "user") -> InlineKeyboardMarkup:
    """V26 Smart Button Layout Engine: 6 main actions only, admin separated."""
    rows = []
    if is_admin(uid):
        rows.append([btn("👑 Admin Studio", "admin:v25os")])
    rows += [
        [btn("🛍 Open Store", "shop:home"), btn("🤖 Ask AI", "ai:ask")],
        [btn("💳 Payments", "pay:hub"), btn("📦 Orders", "orders:mine")],
        [btn("👤 Account", "menu:account"), btn("⚙️ More Options", "menu:more")],
    ]
    return kb(rows)


def user_more_kb(uid: int, role: str = "user") -> InlineKeyboardMarkup:
    """V26 secondary features live here, keeping /start clean."""
    return kb([
        [btn("🧺 Cart", "cart:view"), btn("🎁 Rewards", "menu:rewards")],
        [btn("💎 VIP", "vip:plans"), btn("🛟 Support", "menu:support")],
        [btn("📢 Notice", "menu:info"), btn("🚀 Performance", "v25:mode")],
        [btn("🔎 Discover", "menu:discover"), btn("🏠 Back Home", "menu:main")],
    ])


def user_discover_kb(uid: int, role: str = "user") -> InlineKeyboardMarkup:
    return kb([
        [btn("🔎 Smart Search", "shop:search"), btn("🛍 Categories", "shop:cats")],
        [btn("🤖 AI Suggest", "ai:ask"), btn("🚚 Track Order", "track:ask")],
        [btn("⬅️ Control Hub", "menu:more"), btn("🏠 Home", "menu:main")],
    ])

def user_money_kb(uid: int, role: str = "user") -> InlineKeyboardMarkup:
    return kb([
        [btn("💰 Add Balance", "wallet:topup"), btn("💳 Pay OS", "pay:hub")],
        [btn("🎟 Coupon", "coupon:ask"), btn("💎 VIP Plans", "vip:plans")],
        [btn("👤 Account", "profile:me"), btn("🏠 Home", "menu:main")],
    ])

def user_rewards_kb(uid: int, role: str = "user") -> InlineKeyboardMarkup:
    return kb([
        [btn("🎁 Invite & Earn", "ref:info"), btn("🎫 Redeem Code", "redeem:ask")],
        [btn("🔔 Stock Watch", "wish:view"), btn("💎 VIP Lounge", "vip:plans")],
        [btn("⬅️ Hub", "menu:more"), btn("🏠 Home", "menu:main")],
    ])

def user_support_kb(uid: int, role: str = "user") -> InlineKeyboardMarkup:
    return kb([
        [btn("🛟 New Ticket", "ticket:new"), btn("🚚 Track Order", "track:ask")],
        [btn("📦 My Orders", "orders:mine"), btn("🏪 Seller/Vendor", "vendor:home")],
        [btn("⬅️ Hub", "menu:more"), btn("🏠 Home", "menu:main")],
    ])

def user_info_kb(uid: int, role: str = "user") -> InlineKeyboardMarkup:
    return kb([
        [btn("📢 Live Notice", "info:notice"), btn("📜 Shop Policy", "info:policy")],
        [btn("💳 Payment Rules", "info:pay"), btn("🛟 Support", "ticket:new")],
        [btn("⬅️ Hub", "menu:more"), btn("🏠 Home", "menu:main")],
    ])

def user_account_kb(uid: int, role: str = "user") -> InlineKeyboardMarkup:
    return kb([
        [btn("👤 Profile Card", "profile:me"), btn("📦 Order History", "orders:mine")],
        [btn("💰 Wallet", "wallet:topup"), btn("💎 VIP Status", "vip:plans")],
        [btn("☰ Hub", "menu:more"), btn("🏠 Home", "menu:main")],
    ])

def admin_home_kb() -> InlineKeyboardMarkup:
    """V26 Admin Studio: page-based command center, no button wall."""
    return kb([
        [btn("📊 Dashboard", "admin:v25os"), btn("📦 Orders", "admin:sec:orders")],
        [btn("🛍 Products", "admin:v24products"), btn("💳 Payments", "admin:v25pay")],
        [btn("👥 Users", "admin:sec:users"), btn("🚨 Alerts", "admin:v24alerts")],
        [btn("🤖 AI Control", "admin:v25ai"), btn("⚙️ System", "admin:sec:system")],
        [btn("🎨 Style Studio", "admin:v25welcome")],
        [btn("🏠 User Menu", "menu:main")],
    ])


def admin_section_kb(section: str) -> InlineKeyboardMarkup:
    pages = {
        "dash": [
            [btn("🚀 Executive Pulse", "admin:v14dash"), btn("📊 Live Metrics", "admin:dash")],
            [btn("📈 Analytics", "admin:analytics"), btn("🧬 Smart Insights", "admin:insights")],
            [btn("🛡 Fraud", "admin:fraudpro"), btn("🧺 Cart Stats", "admin:cartstats")],
        ],
        "orders": [
            [btn("🧾 Order Board", "admin:orders"), btn("📸 Proof Queue", "admin:payments")],
            [btn("💎 VIP Requests", "admin:vipreqs"), btn("🎫 Support", "admin:tickets")],
            [btn("🏪 Vendors", "admin:vendors"), btn("🚨 Alerts", "admin:v14alerts")],
        ],
        "catalog": [
            [btn("📁 Categories", "admin:cats"), btn("🛒 Product Studio", "admin:products")],
            [btn("🔐 Delivery Vault", "admin:vault"), btn("💳 Pay Methods", "admin:paymethods")],
            [btn("💳 Pay Text", "admin:setpay"), btn("📜 Policy", "admin:setpolicy")],
        ],
        "users": [
            [btn("👥 Users", "admin:users"), btn("👑 Admins", "admin:admins")],
            [btn("🚫 Ban/Unban", "admin:bans"), btn("💰 Wallet", "admin:walletcfg")],
            [btn("🏪 Vendor Queue", "admin:vendors"), btn("🎫 Tickets", "admin:tickets")],
        ],
        "growth": [
            [btn("🎟 Coupons", "admin:coupons"), btn("🎁 Redeem", "admin:redeems")],
            [btn("🤖 AI Sales", "admin:ai"), btn("📣 Broadcast Studio", "admin:broadcast")],
            [btn("📢 Notice", "admin:setnotice"), btn("🚨 Alerts", "admin:v14alerts")],
        ],
        "system": [
            [btn("🗄 Backup", "admin:backup"), btn("📤 Export", "admin:export")],
            [btn("🛠 Maintenance", "admin:maintenance"), btn("🧩 Feature Switches", "admin:plugins")],
            [btn("🍃 MongoDB", "admin:mongodb"), btn("⚡ Sync", "mongo:sync")],
        ],
    }
    rows = pages.get(section, [])
    rows += [[btn("⬅️ Quantum OS", "admin:v24os"), btn("🏠 User Home", "menu:main")]]
    return kb(rows)

# ═══════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════

class DB:
    def __init__(self, path: str):
        self.path = path
        self.conn: Optional[aiosqlite.Connection] = None
        self._settings_cache: dict[str, tuple[float, str]] = {}
        self.cache_seconds = max(5, min(env_int("SPEED_CORE_CACHE_SECONDS", 30), 180))

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self._init()
        if MONGO_ENABLED:
            await mongo.connect()
            # Low-RAM safe: do not run a huge MongoDB full sync during startup.
            # Manual sync is available from Admin Panel -> MongoDB/Cloud DB.
            if mongo.ready and MONGO_AUTOSYNC and MONGO_STARTUP_SYNC:
                asyncio.create_task(mongo.full_sync_from_sqlite(self, reason="startup_background"))

    async def _table_exists(self, name: str) -> bool:
        cur = await self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        )
        return await cur.fetchone() is not None

    async def _table_columns(self, name: str) -> set[str]:
        cur = await self.conn.execute(f"PRAGMA table_info({name})")
        return {str(row[1]) for row in await cur.fetchall()}

    async def _repair_legacy_users_table(self):
        """Repair older DB files where users table used user_id instead of id.

        This prevents: sqlite3.OperationalError: table users has no column named id
        when an older digital-shop DB is reused with this newer bot.
        """
        if not await self._table_exists("users"):
            return
        cols = await self._table_columns("users")
        if "id" in cols:
            return

        legacy_name = f"users_legacy_{now()}"
        logger.warning("Legacy users table detected; renaming to %s and rebuilding schema", legacy_name)
        await self.conn.execute(f"ALTER TABLE users RENAME TO {legacy_name}")
        await self.conn.commit()
        self._legacy_users_table = legacy_name

    async def _copy_legacy_users(self):
        legacy = getattr(self, "_legacy_users_table", None)
        if not legacy or not await self._table_exists(legacy):
            return
        cols = await self._table_columns(legacy)
        uid_col = "user_id" if "user_id" in cols else None
        if not uid_col:
            return

        def col(name: str, default: str) -> str:
            return name if name in cols else default

        q = f"""
        INSERT OR IGNORE INTO users(
            id, username, first_name, joined_at, role, is_banned, wallet,
            orders_count, total_spent, referrer_id, ref_code, vip_expires
        )
        SELECT
            {uid_col},
            {col('username', "''")},
            {col('first_name', "''")},
            {col('joined_at', str(now()))},
            {col('role', "'user'")},
            {col('is_banned', '0')},
            {col('wallet', '0')},
            {col('orders_count', '0')},
            {col('total_spent', '0')},
            {col('referrer_id', 'NULL')},
            COALESCE({col('ref_code', 'NULL')}, hex(randomblob(4))),
            {col('vip_expires', '0')}
        FROM {legacy}
        WHERE {uid_col} IS NOT NULL
        """
        await self.conn.execute(q)
        await self.conn.commit()
        logger.info("Legacy users copied from %s", legacy)

    async def _ensure_column(self, table: str, column: str, ddl: str):
        cols = await self._table_columns(table) if await self._table_exists(table) else set()
        if column not in cols:
            logger.info("Migrating DB: adding %s.%s", table, column)
            await self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
            await self.conn.commit()

    async def _migrate_columns(self):
        """Add safe columns when upgrading from older bot versions."""
        await self._ensure_column("users", "wallet", "wallet REAL DEFAULT 0")
        await self._ensure_column("users", "orders_count", "orders_count INTEGER DEFAULT 0")
        await self._ensure_column("users", "total_spent", "total_spent REAL DEFAULT 0")
        await self._ensure_column("users", "referrer_id", "referrer_id INTEGER DEFAULT NULL")
        await self._ensure_column("users", "ref_code", "ref_code TEXT")
        await self._ensure_column("users", "vip_expires", "vip_expires INTEGER DEFAULT 0")
        await self._ensure_column("users", "is_banned", "is_banned INTEGER DEFAULT 0")
        await self._ensure_column("categories", "emoji", "emoji TEXT DEFAULT '📦'")
        await self._ensure_column("categories", "active", "active INTEGER DEFAULT 1")
        await self._ensure_column("categories", "sort_order", "sort_order INTEGER DEFAULT 0")
        await self._ensure_column("products", "category_id", "category_id TEXT")
        await self._ensure_column("products", "delivery_mode", "delivery_mode TEXT DEFAULT 'STOCK'")
        await self._ensure_column("products", "featured", "featured INTEGER DEFAULT 0")
        await self._ensure_column("products", "sold", "sold INTEGER DEFAULT 0")
        await self._ensure_column("products", "rating_sum", "rating_sum REAL DEFAULT 0")
        await self._ensure_column("products", "rating_count", "rating_count INTEGER DEFAULT 0")
        await self._ensure_column("products", "sort_order", "sort_order INTEGER DEFAULT 0")
        await self._ensure_column("orders", "qty", "qty INTEGER DEFAULT 1")
        await self._ensure_column("orders", "wallet_used", "wallet_used REAL DEFAULT 0")
        await self._ensure_column("orders", "coupon_code", "coupon_code TEXT")
        await self._ensure_column("orders", "discount", "discount REAL DEFAULT 0")
        await self._ensure_column("orders", "delivered_text", "delivered_text TEXT")
        await self._ensure_column("orders", "admin_note", "admin_note TEXT")
        await self._ensure_column("orders", "rated", "rated INTEGER DEFAULT 0")
        await self._ensure_column("orders", "risk_score", "risk_score INTEGER DEFAULT 0")
        await self._ensure_column("orders", "risk_note", "risk_note TEXT")
        await self._ensure_column("orders", "payment_method", "payment_method TEXT")
        await self._ensure_column("orders", "payment_status", "payment_status TEXT DEFAULT 'UNPAID'")
        await self._ensure_column("orders", "payment_ref", "payment_ref TEXT")
        await self._ensure_column("orders", "autopay", "autopay INTEGER DEFAULT 0")
        await self._ensure_column("payment_methods", "instructions", "instructions TEXT")
        await self._ensure_column("payment_methods", "active", "active INTEGER DEFAULT 1")
        await self._ensure_column("payment_methods", "sort_order", "sort_order INTEGER DEFAULT 0")
        await self._ensure_column("fraud_flags", "status", "status TEXT DEFAULT 'OPEN'")
        await self.conn.execute("UPDATE fraud_flags SET status='OPEN' WHERE status IS NULL OR status=''")
        await self.conn.execute("UPDATE fraud_flags SET status='RESOLVED' WHERE resolved=1 AND (status IS NULL OR status='' OR status='OPEN')")
        await self.conn.commit()

    async def _init(self):
        # Speed Core: WAL + safer concurrency for busy Telegram callback traffic.
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA synchronous=NORMAL")
        await self.conn.execute("PRAGMA temp_store=MEMORY")
        await self.conn.execute("PRAGMA cache_size=-20000")
        await self.conn.execute("PRAGMA busy_timeout=5000")
        await self.conn.execute("PRAGMA foreign_keys=ON")
        await self._repair_legacy_users_table()
        await self.conn.executescript("""
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS users(
            id           INTEGER PRIMARY KEY,
            username     TEXT,
            first_name   TEXT,
            joined_at    INTEGER,
            role         TEXT    DEFAULT 'user',
            is_banned    INTEGER DEFAULT 0,
            wallet       REAL    DEFAULT 0,
            orders_count INTEGER DEFAULT 0,
            total_spent  REAL    DEFAULT 0,
            referrer_id  INTEGER DEFAULT NULL,
            ref_code     TEXT    UNIQUE,
            vip_expires  INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS settings(
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS categories(
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            emoji      TEXT DEFAULT '📦',
            active     INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS products(
            id             TEXT PRIMARY KEY,
            category_id    TEXT,
            name           TEXT NOT NULL,
            price          REAL NOT NULL,
            original_price REAL DEFAULT 0,
            description    TEXT,
            delivery_mode  TEXT DEFAULT 'STOCK',
            active         INTEGER DEFAULT 1,
            featured       INTEGER DEFAULT 0,
            created_at     INTEGER,
            sold           INTEGER DEFAULT 0,
            rating_sum     REAL    DEFAULT 0,
            rating_count   INTEGER DEFAULT 0,
            sort_order     INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS stock(
            id         TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            content    TEXT NOT NULL,
            used       INTEGER DEFAULT 0,
            order_id   TEXT,
            created_at INTEGER,
            used_at    INTEGER
        );
        CREATE TABLE IF NOT EXISTS cart(
            user_id    INTEGER,
            product_id TEXT,
            qty        INTEGER DEFAULT 1,
            PRIMARY KEY(user_id, product_id)
        );
        CREATE TABLE IF NOT EXISTS wishlist(
            user_id    INTEGER,
            product_id TEXT,
            added_at   INTEGER,
            PRIMARY KEY(user_id, product_id)
        );
        CREATE TABLE IF NOT EXISTS stock_watch(
            user_id    INTEGER,
            product_id TEXT,
            created_at INTEGER,
            PRIMARY KEY(user_id, product_id)
        );
        CREATE TABLE IF NOT EXISTS orders(
            id             TEXT PRIMARY KEY,
            user_id        INTEGER,
            product_id     TEXT,
            qty            INTEGER DEFAULT 1,
            amount         REAL,
            wallet_used    REAL    DEFAULT 0,
            status         TEXT    DEFAULT 'WAITING_PROOF',
            proof_file_id  TEXT,
            coupon_code    TEXT,
            discount       REAL    DEFAULT 0,
            created_at     INTEGER,
            updated_at     INTEGER,
            delivered_text TEXT,
            admin_note     TEXT,
            rated          INTEGER DEFAULT 0,
            payment_method TEXT,
            payment_status TEXT DEFAULT 'UNPAID',
            payment_ref    TEXT,
            autopay        INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS reviews(
            id         TEXT PRIMARY KEY,
            order_id   TEXT,
            product_id TEXT,
            user_id    INTEGER,
            rating     INTEGER,
            comment    TEXT,
            created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS coupons(
            code          TEXT PRIMARY KEY,
            discount_type TEXT,
            value         REAL,
            min_order     REAL    DEFAULT 0,
            max_uses      INTEGER DEFAULT 1,
            used          INTEGER DEFAULT 0,
            active        INTEGER DEFAULT 1,
            vip_only      INTEGER DEFAULT 0,
            created_at    INTEGER,
            expires_at    INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS tickets(
            id         TEXT PRIMARY KEY,
            user_id    INTEGER,
            message    TEXT,
            status     TEXT    DEFAULT 'OPEN',
            reply      TEXT,
            created_at INTEGER,
            updated_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS wallet_txns(
            id         TEXT PRIMARY KEY,
            user_id    INTEGER,
            amount     REAL,
            type       TEXT,
            note       TEXT,
            created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS referrals(
            id          TEXT PRIMARY KEY,
            referrer_id INTEGER,
            referee_id  INTEGER,
            bonus_paid  INTEGER DEFAULT 0,
            created_at  INTEGER
        );
        CREATE TABLE IF NOT EXISTS redeem_codes(
            code        TEXT PRIMARY KEY,
            reward_type TEXT NOT NULL,
            value       TEXT NOT NULL,
            max_uses    INTEGER DEFAULT 1,
            used        INTEGER DEFAULT 0,
            active      INTEGER DEFAULT 1,
            created_at  INTEGER,
            expires_at  INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS redeem_logs(
            id          TEXT PRIMARY KEY,
            code        TEXT,
            user_id     INTEGER,
            reward_type TEXT,
            value       TEXT,
            created_at  INTEGER,
            UNIQUE(code, user_id)
        );
        CREATE TABLE IF NOT EXISTS order_events(
            id         TEXT PRIMARY KEY,
            order_id   TEXT,
            status     TEXT,
            note       TEXT,
            actor_id   INTEGER,
            created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS alert_logs(
            id         TEXT PRIMARY KEY,
            audience   TEXT,
            message    TEXT,
            sent_count INTEGER DEFAULT 0,
            failed     INTEGER DEFAULT 0,
            actor_id   INTEGER,
            created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS ai_logs(
            id         TEXT PRIMARY KEY,
            user_id    INTEGER,
            query      TEXT,
            matched    TEXT,
            created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS fraud_flags(
            id         TEXT PRIMARY KEY,
            user_id    INTEGER,
            order_id   TEXT,
            score      INTEGER,
            reason     TEXT,
            created_at INTEGER,
            resolved   INTEGER DEFAULT 0,
            status     TEXT DEFAULT 'OPEN'
        );
        CREATE TABLE IF NOT EXISTS payment_methods(
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            account     TEXT NOT NULL,
            instructions TEXT,
            active      INTEGER DEFAULT 1,
            sort_order  INTEGER DEFAULT 0,
            created_at  INTEGER
        );
        CREATE TABLE IF NOT EXISTS payment_intents(
            id          TEXT PRIMARY KEY,
            user_id     INTEGER,
            amount      REAL,
            currency    TEXT,
            purpose     TEXT,
            method      TEXT,
            related_ids TEXT,
            status      TEXT DEFAULT 'CREATED',
            created_at  INTEGER,
            updated_at  INTEGER
        );
        CREATE TABLE IF NOT EXISTS external_payment_requests(
            id          TEXT PRIMARY KEY,
            user_id     INTEGER,
            amount      REAL,
            currency    TEXT,
            purpose     TEXT,
            method      TEXT,
            related_ids TEXT,
            trx_id      TEXT,
            proof_file_id TEXT,
            status      TEXT DEFAULT 'PENDING',
            admin_id    INTEGER DEFAULT 0,
            note        TEXT,
            created_at  INTEGER,
            updated_at  INTEGER
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_external_payment_trx_method ON external_payment_requests(method, trx_id) WHERE trx_id IS NOT NULL AND trx_id != '';
        CREATE TABLE IF NOT EXISTS autopay_logs(
            id          TEXT PRIMARY KEY,
            user_id     INTEGER,
            intent_id   TEXT,
            amount      REAL,
            result      TEXT,
            note        TEXT,
            created_at  INTEGER
        );
        CREATE TABLE IF NOT EXISTS vendor_requests(
            id          TEXT PRIMARY KEY,
            user_id     INTEGER,
            message     TEXT,
            status      TEXT DEFAULT 'PENDING',
            admin_note  TEXT,
            created_at  INTEGER,
            updated_at  INTEGER
        );
        CREATE TABLE IF NOT EXISTS plugin_logs(
            id          TEXT PRIMARY KEY,
            key         TEXT,
            old_value   TEXT,
            new_value   TEXT,
            actor_id    INTEGER,
            created_at  INTEGER
        );
        CREATE TABLE IF NOT EXISTS cart_checkouts(
            id          TEXT PRIMARY KEY,
            user_id     INTEGER,
            order_ids   TEXT,
            total       REAL,
            proof_file_id TEXT,
            status      TEXT DEFAULT 'WAITING_PROOF',
            created_at  INTEGER,
            updated_at  INTEGER
        );
        CREATE TABLE IF NOT EXISTS fraud_blacklist(
            user_id     INTEGER PRIMARY KEY,
            reason      TEXT,
            actor_id    INTEGER,
            created_at  INTEGER
        );
        CREATE TABLE IF NOT EXISTS admin_action_logs(
            id          TEXT PRIMARY KEY,
            actor_id    INTEGER,
            action      TEXT,
            target      TEXT,
            note        TEXT,
            created_at  INTEGER
        );
        CREATE TABLE IF NOT EXISTS invoice_receipts(
            id          TEXT PRIMARY KEY,
            order_id    TEXT,
            user_id     INTEGER,
            amount      REAL,
            status      TEXT,
            payload     TEXT,
            created_at  INTEGER
        );
        CREATE TABLE IF NOT EXISTS gateway_attempts(
            id          TEXT PRIMARY KEY,
            user_id     INTEGER,
            method      TEXT,
            amount      REAL,
            status      TEXT,
            gateway_ref TEXT,
            note        TEXT,
            created_at  INTEGER
        );
        CREATE TABLE IF NOT EXISTS security_events(
            id          TEXT PRIMARY KEY,
            user_id     INTEGER,
            level       TEXT,
            event       TEXT,
            note        TEXT,
            created_at  INTEGER
        );
        """)
        await self._copy_legacy_users()
        await self._migrate_columns()
        await self.conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_products_active_category ON products(active, category_id, sort_order);
        CREATE INDEX IF NOT EXISTS idx_products_featured_sold ON products(active, featured, sold);
        CREATE INDEX IF NOT EXISTS idx_stock_product_used ON stock(product_id, used);
        CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status, updated_at);
        CREATE INDEX IF NOT EXISTS idx_orders_status_updated ON orders(status, updated_at);
        CREATE INDEX IF NOT EXISTS idx_cart_user ON cart(user_id);
        CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status, updated_at);
        CREATE INDEX IF NOT EXISTS idx_wallet_user_time ON wallet_txns(user_id, created_at);
        """)

        defaults = {
            "payment_text":   f"💳 <b>Payment Methods</b>\n\nBkash: 01XXXXXXXXX\nNagad: 01XXXXXXXXX\nRocket: 01XXXXXXXXX\n\nSend the exact amount, then upload payment screenshot here.",
            "notice":         "📢 Welcome to " + SHOP_NAME + "! No special notice right now.",
            "policy":         "📜 <b>Shop Policy</b>\n\nAll digital products are delivered after payment verification. No refund after delivery. Contact support for any issues within 24 hours.",
            "maintenance":    "0",
            "wallet_topup_text": "💰 <b>Wallet Top-Up</b>\n\nSend money to:\n\nBkash: 01XXXXXXXXX\nNagad: 01XXXXXXXXX\n\nThen send screenshot to admin. Min top-up: 50 BDT",
            "referral_bonus": str(REFERRAL_BONUS),
            "vip_discount":   "20",
            "vip_price":      "Monthly: 500 BDT | Lifetime: 1500 BDT",
            "vip_text":       "💎 <b>VIP Membership Center</b>\n\nChoose a VIP plan, pay using the shop payment method, then send your payment screenshot. Admin will activate VIP after verification.",
            "vip_plans":      "🥈 <b>Monthly VIP</b> — 500 BDT / 30 days\n• 20% discount on eligible products\n• VIP-only coupons\n• Priority support\n\n💎 <b>Lifetime VIP</b> — 1500 BDT one-time\n• Lifetime VIP access\n• Bigger priority for limited stock\n• VIP coupon access\n• Premium support",
            "vip_benefits":   "🎁 <b>VIP Benefits</b>\n\n✅ 20% discount on eligible orders\n✅ VIP-only coupon codes\n✅ Faster support reply priority\n✅ Early access to premium products\n✅ Special offers and bundle deals\n✅ Auto VIP badge on your profile",
            "vip_buy_steps":  "🛒 <b>How to buy VIP</b>\n\n1️⃣ Choose Monthly or Lifetime plan.\n2️⃣ Send payment to the shop payment number.\n3️⃣ Send screenshot/proof in VIP request.\n4️⃣ Admin verifies and activates your VIP.\n\nNeed help? Open Support Ticket.",
            "stock_alerts_enabled": "1",
            "stock_alert_low": str(LOW_STOCK),
            "stock_alert_added": "1",
            "stock_alert_low_enabled": "1",
            "stock_alert_out_enabled": "1",
            "stock_alert_audience": "subscribers",
            "shop_footer": "NeoLux AI Store OS • Smooth shopping • Wallet autopay • Instant digital delivery",
            "premium_home_title": "🌌 LUFFY STORE APEX ULTRA",
            "max_per_order": "25",
            "support_mode": "ticket",
            "auto_delivery_enabled": "1",
            "redeem_help": "🎁 <b>Redeem Center</b>\n\nSend your redeem code here. Codes can unlock wallet balance, VIP days or instant digital stock reward.",
            "ai_assistant_enabled": "1",
            "ai_assistant_intro": "🤖 <b>AI Shop Assistant</b>\n\nTell me what you need. Example: cheap Netflix, VIP offer, order help, coupon, wallet topup, gaming account.",
            "ai_no_result_text": "I could not find a perfect match. Try product name, budget, category, or open Support Ticket.",
            "alert_center_enabled": "1",
            "fraud_guard_enabled": "1",
            "fraud_order_limit": "3",
            "fraud_window_min": "10",
            "auto_status_processing": "1",
            "shop_open": "1",
            "cart_enabled": "1",
            "vendor_enabled": "1",
            "coupon_enabled": "1",
            "redeem_enabled": "1",
            "vip_enabled": "1",
            "payment_proof_required": "1",
            "super_alert_new_order": "1",
            "super_alert_payment_proof": "1",
            "super_alert_low_stock": "1",
            "super_alert_fraud": "1",
            "super_alert_vendor": "1",
            "v14_welcome_badge": "RichPay Smart Store OS • Wallet Autopay • Crypto Ready",
            "mongodb_mirror_enabled": "1",
            "mongodb_last_sync": "Never",
            "mongodb_sync_tables": "users,settings,categories,products,stock,orders,coupons,tickets,wallet_txns,referrals,redeem_codes,redeem_logs,order_events,alert_logs,ai_logs,fraud_flags,payment_methods,payment_intents,external_payment_requests,autopay_logs,vendor_requests,plugin_logs,cart_checkouts,fraud_blacklist,admin_action_logs,invoice_receipts,gateway_attempts,security_events,cart,wishlist,stock_watch,reviews",
            "alert_sound_style": "premium",
            "alert_priority_mode": "smart",
            "neostore_compact_home": "1",
            "wallet_autopay_enabled": "1",
            "wallet_auto_delivery_enabled": "1",
            "exact_amount_buttons": "50,100,200,500,1000,2000",
            "external_gateway_mode": "MANUAL_PROOF",
            "smart_payment_note": "Wallet payment verifies instantly inside the bot and can auto-deliver stock. External mobile banking/crypto payments use exact amount + unique reference note + Transaction ID smart queue; official gateway API can be plugged in later for full automatic external verification.",
            "autopay_brand": SHOP_NAME,
            "autopay_note": "টাকা পাঠানোর ৫-১০ সেকেন্ড পর Transaction ID দিন।",
            "autopay_strict_trx_duplicate": "1",
            "autopay_auto_credit_external": "0",
            "autopay_webapp_url": PAYMENT_WEBAPP_URL,
            "premium_ui_enabled": "1",
            "premium_animation_enabled": "1",
            "premium_home_subtitle": "Premium digital shop experience — smart AI, exact payment, wallet autopay, instant stock delivery",
            "premium_reply_style": "luxury_motion",
            "speed_core_cache_seconds": "30",
            "ai_budget_parser_enabled": "1",
            "ai_intent_engine": "PRO_LOCAL_SEMANTIC",
            "ai_answer_style": "premium_compact",
            "v24_theme": "luxury_dark",
            "v24_ui_density": "premium_balanced",
            "v24_smart_journey": "1",
            "v24_product_showcase": "1",
            "v24_ai_brain_pro": "1",
            "v24_gateway_ready": "1",
            "v24_speed_engine": "1",
            "v24_receipts_enabled": "1",
            "v24_invoice_prefix": "LUFFY",
            "v24_security_shield": "1",
            "v24_analytics_pro": "1",
            "v24_admin_action_log": "1",
            "v24_welcome_journey_text": "Your premium AI store is ready. Browse products, ask AI, pay exact amount, and receive digital stock smoothly.",
            "v25_home_title": "🌌 LUFFY HYPERNOVA AI STORE",
            "v25_home_subtitle": "Premium digital shop experience — beautiful UI, smart AI, exact payment, instant delivery",
            "v25_welcome_studio_2": "1",
            "v25_journey_steps": "Loading Store → Checking Account → Opening Dashboard → Ready to Shop",
            "v25_button_layout_engine": "smart_grouped",
            "v25_ai_brain_ultra": "1",
            "v25_smart_product_ranking": "1",
            "v25_speed_core_lowram": "1",
            "v25_payment_intelligence_2": "1",
            "v25_admin_control_center_pro": "1",
            "v25_alert_automation_pro": "1",
            "v25_receipt_invoice_pro": "1",
            "v25_auto_cleanup_enabled": "1",
            "v25_safe_turbo_mode": "balanced",
            "v25_cleanup_days": "14",
            "v26_final_premium_ui": "1",
            "v26_button_layout_engine": "1",
            "v26_welcome_blueprint": "1",
        }
        for k, v in defaults.items():
            cur = await self.conn.execute("SELECT value FROM settings WHERE key=?", (k,))
            if not await cur.fetchone():
                await self.conn.execute("INSERT INTO settings(key,value) VALUES(?,?)", (k, v))

        # V15 default payment method seeds. Admin can edit/add/remove from bot panel.
        cur = await self.conn.execute("SELECT COUNT(*) AS n FROM payment_methods")
        pm_count = await cur.fetchone()
        if not pm_count or int(pm_count["n"] or 0) == 0:
            seeds = [
                ("PAY-BINANCE", "Binance Pay", "UID: SET_BY_ADMIN", "Open Binance app → Pay → Send. Send exact amount and add the bot reference note exactly.", 1),
                ("PAY-BYBIT", "ByBit Pay", "UID: SET_BY_ADMIN", "Open ByBit app → Pay/Transfer. Send exact amount and add the bot reference note exactly.", 2),
                ("PAY-USDT-BEP20", "USDT (BEP20 - BSC)", "Wallet: SET_BY_ADMIN", "Send only BEP20/BSC USDT. Wrong network cannot be auto-matched.", 3),
                ("PAY-USDT-TRC20", "USDT (TRC20 - Tron)", "Wallet: SET_BY_ADMIN", "Send only TRC20/Tron USDT. Paste the TXID after payment.", 4),
                ("PAY-BKASH", "bKash Personal", "01XXXXXXXXX", "Send Money only. Send exact amount, then submit Transaction ID.", 5),
                ("PAY-NAGAD", "Nagad Personal", "01XXXXXXXXX", "Send Money only. Send exact amount, then submit Transaction ID.", 6),
            ]
            for pid, title, account, inst, order in seeds:
                await self.conn.execute(
                    "INSERT OR IGNORE INTO payment_methods(id,title,account,instructions,active,sort_order,created_at) VALUES(?,?,?,?,?,?,?)",
                    (pid, title, account, inst, 1, order, now())
                )

        # VIP Pro migration: upgrade unclear old defaults but keep admin custom edits.
        legacy_vip_text = "💎 <b>VIP Membership</b>\n\nBenefits:\n• Extra discount on every eligible order\n• VIP-only coupons\n• Faster support priority\n• Special offers and premium products\n\nTap Request VIP and admin will contact you."
        cur = await self.conn.execute("SELECT value FROM settings WHERE key='vip_text'")
        row = await cur.fetchone()
        if row and row["value"] == legacy_vip_text:
            await self.conn.execute("UPDATE settings SET value=? WHERE key='vip_text'", (defaults["vip_text"],))
        cur = await self.conn.execute("SELECT value FROM settings WHERE key='vip_price'")
        row = await cur.fetchone()
        if row and row["value"] in ("Custom / Contact Admin", "Contact Admin", ""):
            await self.conn.execute("UPDATE settings SET value=? WHERE key='vip_price'", (defaults["vip_price"],))
        cur = await self.conn.execute("SELECT value FROM settings WHERE key='vip_discount'")
        row = await cur.fetchone()
        if row and row["value"] in ("10", "10.0", ""):
            await self.conn.execute("UPDATE settings SET value=? WHERE key='vip_discount'", (defaults["vip_discount"],))
        await self.conn.commit()

        rows = await self.conn.execute("SELECT id FROM users WHERE role='admin'")
        for r in await rows.fetchall():
            DYNAMIC_ADMIN_IDS.add(int(r["id"]))
        await self.conn.commit()

    async def get(self, key: str) -> str:
        # Speed Core settings cache: prevents repeated SELECTs on every callback/home render.
        cached = self._settings_cache.get(key)
        t = time.time()
        if cached and t - cached[0] <= self.cache_seconds:
            return cached[1]
        cur = await self.conn.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        value = row["value"] if row else ""
        self._settings_cache[key] = (t, value)
        return value

    async def set(self, key: str, value: str):
        await self.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
        await self.conn.commit()
        if key == "speed_core_cache_seconds":
            self.cache_seconds = max(5, min(int(parse_amount(value, 30)), 180))
        self._settings_cache.pop(key, None)
        await mongo.mirror_setting(key, value)

    async def add_user(self, m: Message):
        u = m.from_user
        ref_code = secrets.token_hex(4).upper()
        await self.conn.execute(
            "INSERT OR IGNORE INTO users(id,username,first_name,joined_at,role,ref_code) VALUES(?,?,?,?,?,?)",
            (u.id, u.username, u.first_name, now(), "admin" if is_admin(u.id) else "user", ref_code),
        )
        await self.conn.execute(
            "UPDATE users SET username=?, first_name=? WHERE id=?",
            (u.username, u.first_name, u.id),
        )
        await self.conn.commit()
        await mongo.mirror_row(self, "users", "id", u.id)

    async def get_user(self, uid: int):
        return await self.fetchone("SELECT * FROM users WHERE id=?", (uid,))

    async def fetchall(self, q, params=()):
        cur = await self.conn.execute(q, params)
        return await cur.fetchall()

    async def fetchone(self, q, params=()):
        cur = await self.conn.execute(q, params)
        return await cur.fetchone()

    async def execute(self, q, params=()):
        await self.conn.execute(q, params)
        await self.conn.commit()
        if "settings" in str(q).lower():
            self._settings_cache.clear()
        await mongo.sync_touched_tables(self, q)

    async def wallet_add(self, uid: int, amount: float, type_: str, note: str = ""):
        await self.execute("UPDATE users SET wallet=wallet+? WHERE id=?", (amount, uid))
        await self.execute(
            "INSERT INTO wallet_txns(id,user_id,amount,type,note,created_at) VALUES(?,?,?,?,?,?)",
            (code("WTX"), uid, amount, type_, note, now())
        )

    async def check_vip(self, uid: int) -> bool:
        u = await self.get_user(uid)
        if not u:
            return False
        if u["role"] == "admin":
            return True
        if u["role"] == "vip" and (u["vip_expires"] == 0 or u["vip_expires"] > now()):
            return True
        if u["orders_count"] >= VIP_THRESHOLD:
            await self.execute("UPDATE users SET role='vip' WHERE id=?", (uid,))
            return True
        return False


class MongoBridge:
    """Optional MongoDB Atlas/Server sync engine for the digital shop.

    The existing SQLite core remains the safest local transaction store, while this
    bridge mirrors business data into MongoDB collections for cloud backup,
    analytics dashboards, restore/export workflows and multi-panel reporting.
    """
    CORE_TABLES = [
        "users", "settings", "categories", "products", "stock", "orders", "reviews",
        "coupons", "tickets", "wallet_txns", "referrals", "redeem_codes", "redeem_logs",
        "order_events", "alert_logs", "ai_logs", "fraud_flags", "payment_methods", "payment_intents", "autopay_logs",
        "vendor_requests", "plugin_logs", "cart_checkouts", "fraud_blacklist", "external_payment_requests",
        "admin_action_logs", "invoice_receipts", "gateway_attempts", "security_events", "cart", "wishlist", "stock_watch",
    ]
    KEY_MAP = {
        "users": "id", "settings": "key", "categories": "id", "products": "id", "stock": "id",
        "orders": "id", "reviews": "id", "coupons": "code", "tickets": "id", "wallet_txns": "id",
        "redeem_codes": "code", "redeem_logs": "id", "order_events": "id", "alert_logs": "id",
        "ai_logs": "id", "fraud_flags": "id", "payment_methods": "id", "payment_intents": "id", "external_payment_requests": "id", "autopay_logs": "id", "vendor_requests": "id",
        "plugin_logs": "id", "cart_checkouts": "id", "fraud_blacklist": "user_id", "admin_action_logs": "id", "invoice_receipts": "id", "gateway_attempts": "id", "security_events": "id",
    }
    COMPOSITE_KEYS = {
        "referrals": ("referrer_id", "referred_id"),
        "cart": ("user_id", "product_id"),
        "wishlist": ("user_id", "product_id"),
        "stock_watch": ("user_id", "product_id"),
    }

    def __init__(self):
        self.client = None
        self.database = None
        self.ready = False
        self.error = ""
        self.last_sync = "Never"

    def _mask_uri(self) -> str:
        if not MONGO_URI:
            return "Not set"
        return re.sub(r"//([^:/@]+):([^@]+)@", r"//\1:***@", MONGO_URI)

    async def connect(self) -> bool:
        if not MONGO_ENABLED:
            self.ready = False
            self.error = "MONGO_ENABLED=0"
            return False
        if not MONGO_URI:
            self.ready = False
            self.error = "MONGO_URI missing"
            logger.warning("MongoDB enabled but MONGO_URI is empty")
            return False
        if AsyncIOMotorClient is None:
            self.ready = False
            self.error = "motor package missing; run pip install -r requirements.txt"
            logger.warning("MongoDB enabled but motor is not installed")
            return False
        try:
            self.client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=6000, connectTimeoutMS=6000, socketTimeoutMS=12000, maxPoolSize=5, minPoolSize=0)
            self.database = self.client[MONGO_DB_NAME]
            await self.client.admin.command("ping")
            await self._ensure_indexes()
            self.ready = True
            self.error = ""
            logger.info("MongoDB connected: %s", MONGO_DB_NAME)
            return True
        except Exception as e:
            self.ready = False
            self.error = str(e)
            logger.warning("MongoDB connection failed: %s", e)
            return False

    async def _ensure_indexes(self):
        if self.database is None:
            return
        await self.database.users.create_index("id", unique=True)
        await self.database.orders.create_index("id", unique=True)
        await self.database.orders.create_index([("user_id", 1), ("created_at", -1)])
        await self.database.products.create_index("id", unique=True)
        await self.database.stock.create_index([("product_id", 1), ("used", 1)])
        await self.database.settings.create_index("key", unique=True)
        await self.database.alert_logs.create_index("created_at")
        await self.database.bot_sync_logs.create_index("created_at")

    def _row_to_doc(self, row: Any, table: str) -> dict:
        if row is None:
            return {}
        if isinstance(row, dict):
            doc = dict(row)
        else:
            doc = {k: row[k] for k in row.keys()}
        doc["_table"] = table
        doc["_synced_at"] = now()
        return doc

    def _doc_key(self, table: str, doc: dict) -> tuple[str, Any]:
        if table in self.KEY_MAP:
            key = self.KEY_MAP[table]
            return key, doc.get(key)
        if table in self.COMPOSITE_KEYS:
            parts = self.COMPOSITE_KEYS[table]
            val = "::".join(str(doc.get(x, "")) for x in parts)
            doc["_sync_key"] = val
            return "_sync_key", val
        key = "_sync_key"
        doc[key] = secrets.token_hex(8)
        return key, doc[key]

    async def upsert_doc(self, table: str, doc: dict):
        if not self.ready or not doc:
            return
        key, val = self._doc_key(table, doc)
        if val is None or val == "":
            return
        try:
            await self.database[table].update_one({key: val}, {"$set": doc}, upsert=True)
        except Exception as e:
            self.error = str(e)
            logger.warning("Mongo upsert failed for %s: %s", table, e)

    async def mirror_setting(self, key: str, value: str):
        if self.ready:
            await self.upsert_doc("settings", {"key": key, "value": value, "_table": "settings", "_synced_at": now()})

    async def mirror_row(self, sqlite_db: DB, table: str, key: str, value: Any):
        if not self.ready or not MONGO_AUTOSYNC:
            return
        try:
            row = await sqlite_db.fetchone(f"SELECT * FROM {table} WHERE {key}=?", (value,))
            if row:
                await self.upsert_doc(table, self._row_to_doc(row, table))
        except Exception as e:
            self.error = str(e)
            logger.debug("Mongo mirror_row skipped for %s: %s", table, e)

    def touched_tables(self, q: str) -> list[str]:
        ql = " ".join(str(q or "").lower().split())
        found: list[str] = []
        patterns = [r"insert\s+(?:or\s+\w+\s+)?into\s+([a-z_]+)", r"update\s+([a-z_]+)", r"delete\s+from\s+([a-z_]+)"]
        for pat in patterns:
            for m in re.finditer(pat, ql):
                t = m.group(1)
                if t in self.CORE_TABLES and t not in found:
                    found.append(t)
        return found[:4]

    async def sync_touched_tables(self, sqlite_db: DB, q: str):
        if not self.ready or not MONGO_AUTOSYNC:
            return
        for table in self.touched_tables(q):
            await self.sync_table(sqlite_db, table, limit=min(MONGO_SYNC_LIMIT, 50))

    async def sync_table(self, sqlite_db: DB, table: str, limit: int | None = None) -> int:
        if not self.ready:
            return 0
        if table not in self.CORE_TABLES:
            return 0
        limit = max(1, min(limit or MONGO_SYNC_LIMIT, MONGO_SYNC_LIMIT))
        try:
            rows = await sqlite_db.fetchall(f"SELECT * FROM {table} LIMIT ?", (limit,))
            count = 0
            for row in rows:
                await self.upsert_doc(table, self._row_to_doc(row, table))
                count += 1
            return count
        except Exception as e:
            self.error = str(e)
            logger.debug("Mongo sync_table skipped for %s: %s", table, e)
            return 0

    async def full_sync_from_sqlite(self, sqlite_db: DB, reason: str = "manual") -> dict:
        if not self.ready:
            if MONGO_ENABLED and not self.client:
                await self.connect()
            if not self.ready:
                return {"ok": False, "error": self.error or "MongoDB not connected"}
        summary: dict[str, int] = {}
        for table in self.CORE_TABLES:
            summary[table] = await self.sync_table(sqlite_db, table)
        self.last_sync = time.strftime("%Y-%m-%d %H:%M:%S")
        await self.database.bot_sync_logs.insert_one({
            "reason": reason,
            "summary": summary,
            "created_at": now(),
            "version": APP_VERSION,
        })
        try:
            await sqlite_db.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", ("mongodb_last_sync", self.last_sync))
            await sqlite_db.conn.commit()
        except Exception:
            pass
        return {"ok": True, "summary": summary, "last_sync": self.last_sync}

    async def collection_counts(self) -> dict:
        if not self.ready:
            return {}
        out = {}
        for name in ["users", "products", "orders", "stock", "payment_methods", "redeem_codes", "alert_logs", "tickets"]:
            try:
                out[name] = await self.database[name].count_documents({})
            except Exception:
                out[name] = 0
        return out

    async def log_event(self, kind: str, title: str, data: dict | None = None):
        if not self.ready:
            return
        try:
            await self.database.mongo_events.insert_one({
                "kind": kind,
                "title": title,
                "data": data or {},
                "created_at": now(),
                "version": APP_VERSION,
            })
        except Exception as e:
            self.error = str(e)

    async def status_text(self) -> str:
        counts = await self.collection_counts()
        lines = [
            f"Mode: <b>{'Connected ✅' if self.ready else 'Offline/Fallback ⚠️'}</b>",
            f"Enabled: <b>{'YES' if MONGO_ENABLED else 'NO'}</b>",
            f"Database: <code>{esc(MONGO_DB_NAME)}</code>",
            f"URI: <code>{esc(self._mask_uri())}</code>",
            f"Auto Sync: <b>{'ON' if MONGO_AUTOSYNC else 'OFF'}</b>",
            f"Last Sync: <b>{esc(self.last_sync)}</b>",
        ]
        if self.error and not self.ready:
            lines.append(f"Error: <code>{esc(preview_text(self.error, max_lines=2, max_chars=180))}</code>")
        if counts:
            lines.append("\n🍃 <b>Mongo Collections</b>")
            lines.extend([f"• {esc(k)}: <b>{v}</b>" for k, v in counts.items()])
        return "\n".join(lines)

mongo = MongoBridge()


db = DB(DB_PATH)

async def notify_admins(bot: Bot, text: str, reply_markup: InlineKeyboardMarkup | None = None, exclude: int | None = None):
    admin_ids = list(dict.fromkeys([*ADMIN_IDS, *DYNAMIC_ADMIN_IDS]))
    for admin_id in admin_ids:
        if exclude is not None and int(admin_id) == int(exclude):
            continue
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_markup)
            await asyncio.sleep(0.03)
        except Exception:
            pass

async def ensure_user(user):
    ref_code = secrets.token_hex(4).upper()
    await db.execute(
        "INSERT OR IGNORE INTO users(id,username,first_name,joined_at,role,ref_code) VALUES(?,?,?,?,?,?)",
        (user.id, user.username, user.first_name, now(), "admin" if is_admin(user.id) else "user", ref_code),
    )
    await db.execute("UPDATE users SET username=?, first_name=? WHERE id=?", (user.username, user.first_name, user.id))

# ═══════════════════════════════════════════════════════════════
#  FSM STATES
# ═══════════════════════════════════════════════════════════════

class AddCategory(StatesGroup):
    name = State()
    emoji = State()

class AddProduct(StatesGroup):
    name = State()
    price = State()
    orig_price = State()
    category = State()
    mode = State()
    desc = State()
    featured = State()

class EditProduct(StatesGroup):
    field = State()
    value = State()

class AddStock(StatesGroup):
    product = State()
    lines = State()

class SearchState(StatesGroup):
    query = State()

class PaymentProof(StatesGroup):
    proof = State()
    trx_id = State()
    coupon = State()

class SmartBuyState(StatesGroup):
    custom_qty = State()

class TextEdit(StatesGroup):
    payment = State()
    notice = State()
    policy = State()
    broadcast = State()
    ticket_message = State()
    coupon_code = State()      # user-side: check/redeem coupon
    coupon_value = State()     # admin-side: create coupon details
    redeem_code = State()      # user-side redeem code
    redeem_create = State()    # admin-side redeem code create
    reject_reason = State()
    ticket_reply = State()
    wallet_topup_text = State()
    vip_discount = State()
    vip_text = State()
    vip_price = State()
    ref_bonus = State()
    cat_emoji = State()
    alert_message = State()
    ai_intro = State()
    ai_no_result = State()
    fraud_limit = State()
    home_title = State()
    home_subtitle = State()
    home_footer = State()

class AIAssistantState(StatesGroup):
    query = State()

class TrackState(StatesGroup):
    order_id = State()

class WalletState(StatesGroup):
    custom_amount = State()
    topup_proof = State()
    topup_trx_id = State()

class ReviewState(StatesGroup):
    rating = State()
    comment = State()

class AdminWalletState(StatesGroup):
    user_id = State()
    amount = State()
    note = State()

class UserBanState(StatesGroup):
    user_id = State()

class AdminRoleState(StatesGroup):
    user_id = State()

class VipRequestState(StatesGroup):
    message = State()

# ═══════════════════════════════════════════════════════════════
#  MIDDLEWARE
# ═══════════════════════════════════════════════════════════════

class ThrottleMiddleware(BaseMiddleware):
    def __init__(self, rate=0.25):
        self.rate = rate
        self._last = {}

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)
        if is_admin(user.id):
            return await handler(event, data)
        t = time.time()
        if t - self._last.get(user.id, 0) < self.rate:
            return
        self._last[user.id] = t
        return await handler(event, data)

class BanCheckMiddleware(BaseMiddleware):
    def __init__(self, ttl: int = 30):
        self.ttl = ttl
        self._cache: dict[int, tuple[float, bool]] = {}

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user and not is_admin(user.id):
            t = time.time()
            cached = self._cache.get(user.id)
            if cached and t - cached[0] < self.ttl:
                banned = cached[1]
            else:
                u = await db.fetchone("SELECT is_banned FROM users WHERE id=?", (user.id,))
                banned = bool(u and u["is_banned"])
                self._cache[user.id] = (t, banned)
            if banned:
                if isinstance(event, Message):
                    await event.answer("🚫 Your access is limited. Contact support if this is a mistake.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Access limited.", show_alert=True)
                return
        return await handler(event, data)

router.message.middleware(ThrottleMiddleware())
router.message.middleware(BanCheckMiddleware())
router.callback_query.middleware(BanCheckMiddleware())

# ═══════════════════════════════════════════════════════════════
#  COMMANDS
# ═══════════════════════════════════════════════════════════════

async def send_home(target, text: str = None):
    """V26 final /start: premium entrance, not a feature dump."""
    user = target.from_user
    u = await db.get_user(user.id)
    role = u["role"] if u else "user"
    is_vip = await db.check_vip(user.id)
    role_text = "VIP" if is_vip and role != "admin" else ("Admin" if is_admin(user.id) else role.title())

    total_products = await db.fetchone("SELECT COUNT(*) n FROM products WHERE active=1")
    stock_items = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE used=0")
    sold_items = await db.fetchone("SELECT COALESCE(SUM(sold),0) n FROM products WHERE active=1")
    order_count = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE user_id=?", (user.id,))
    cart_items = await db.fetchone("SELECT COALESCE(SUM(qty),0) n FROM cart WHERE user_id=?", (user.id,))
    pending_orders = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE user_id=? AND status IN ('WAITING_PROOF','PENDING','PROCESSING')", (user.id,))

    notice = preview_text(await db.get("notice") or "Welcome back. Your store is ready.", max_lines=1, max_chars=74)
    bal = money(u['wallet'] if u else 0) if WALLET_ENABLED else "Disabled"
    title = await db.get("v25_home_title") or await db.get("premium_home_title") or "🌌 LUFFY HYPERNOVA AI STORE"
    subtitle = await db.get("v25_home_subtitle") or "Premium AI commerce experience for instant digital delivery."
    mode = await db.get("v25_safe_turbo_mode") or V25_UI_MODE or "balanced"
    meta = v25_mode_meta(mode)

    lines = [
        "<b>👤 Account Overview</b>",
        f"Role: <b>{esc(role_text)}</b>  •  Wallet: <b>{bal}</b>",
        f"Orders: <b>{order_count['n'] if order_count else 0}</b>  •  Cart: <b>{cart_items['n'] if cart_items else 0}</b>",
        "",
        "<b>🛍 Store Status</b>",
        f"Products: <b>{total_products['n'] if total_products else 0}</b>  •  Stock: <b>{stock_items['n'] if stock_items else 0}</b>  •  Sold: <b>{sold_items['n'] if sold_items else 0}</b>",
        "",
        "<b>⚡ Smart System</b>",
        f"AI Guide: <b>Ready</b>  •  Smart Pay: <b>Ready</b>  •  Pending: <b>{pending_orders['n'] if pending_orders else 0}</b>",
        "",
        "<b>📢 Notice</b>",
        esc(notice),
    ]
    footer = f"Luffy Store Apex • Smart Pay • Instant Delivery • {meta['name']}"
    msg = hypernova_card(title, subtitle, lines, footer, mode)
    markup = main_menu(user.id, role)
    if isinstance(target, Message):
        if ANIMATION_ENABLED and not FAST_MODE and mode != "turbo":
            await motion(target, "Opening store", "checking account")
        await target.answer(msg, reply_markup=markup)
    else:
        try:
            await safe_edit(target.message, msg, reply_markup=markup)
        except TelegramBadRequest:
            pass


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await db.add_user(message)

    # Handle referral
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_code = args[1][4:]
        referrer = await db.fetchone("SELECT * FROM users WHERE ref_code=?", (ref_code,))
        if referrer and referrer["id"] != message.from_user.id:
            existing = await db.fetchone("SELECT id FROM referrals WHERE referee_id=?", (message.from_user.id,))
            if not existing:
                bonus = parse_amount(await db.get("referral_bonus") or REFERRAL_BONUS)
                await db.execute("INSERT INTO referrals(id,referrer_id,referee_id,bonus_paid,created_at) VALUES(?,?,?,?,?)",
                    (code("REF"), referrer["id"], message.from_user.id, 1, now()))
                await db.wallet_add(referrer["id"], bonus, "REFERRAL", f"Referral bonus for inviting {message.from_user.first_name}")
                await db.execute("UPDATE users SET referrer_id=? WHERE id=?", (referrer["id"], message.from_user.id))
                try:
                    from aiogram import Bot as _B
                    # Will be injected via DI
                    pass
                except Exception:
                    pass

    maint = await db.get("maintenance")
    if maint == "1" and not is_admin(message.from_user.id):
        return await message.answer(card("🛠 Maintenance", "Shop is temporarily offline for updates. Please try again later.", "We'll be back soon!"))

    await send_home(message)


@router.message(Command("panel", "admin", "pannel", "v26"))
async def admin_panel(message: Message, state: FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ Access denied.")
    lines = [
        "Today sales, pending orders and payment queue are separated into clean pages.",
        "Products, users, AI, alerts and system tools are controlled from this studio.",
        "Use Style Studio to change welcome title, subtitle, footer and theme without editing code.",
    ]
    await message.answer(hypernova_card("👑 Admin Studio", "Your premium store command center is ready.", lines, f"Admin {esc(message.from_user.first_name)} • V26 Final Premium UI", await db.get("v25_safe_turbo_mode") or V25_UI_MODE), reply_markup=admin_home_kb())


@router.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Cancelled.", reply_markup=main_menu(message.from_user.id))

@router.message(Command("menu", "home", "compact"))
async def menu_cmd(message: Message, state: FSMContext):
    await state.clear()
    await db.add_user(message)
    await send_home(message)


# ═══════════════════════════════════════════════════════════════
#  GENERAL CALLBACKS
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "state:cancel")
async def cancel_cb(call: CallbackQuery, state: FSMContext):
    await state.clear()
    u = await db.get_user(call.from_user.id)
    role = u["role"] if u else "user"
    await safe_edit(call.message, "✅ Cancelled.", reply_markup=main_menu(call.from_user.id, role))
    await call.answer()


@router.callback_query(F.data == "menu:main")
async def cb_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_home(call)
    await call.answer()


@router.callback_query(F.data == "menu:more")
async def cb_more(call: CallbackQuery, state: FSMContext):
    await state.clear()
    u = await db.get_user(call.from_user.id)
    role = u["role"] if u else "user"
    lines = [
        "Choose a section below.",
        "Cart, rewards, VIP, support, notice and performance are grouped here so the home screen stays clean.",
    ]
    await safe_edit(call.message, hypernova_card("⚙️ More Options", "Advanced tools without crowding your display.", lines, "Clean menu • premium flow • mobile safe", await db.get("v25_safe_turbo_mode") or V25_UI_MODE), reply_markup=user_more_kb(call.from_user.id, role))
    await call.answer()


@router.callback_query(F.data == "menu:discover")
async def cb_discover(call: CallbackQuery, state: FSMContext):
    await state.clear()
    u = await db.get_user(call.from_user.id)
    role = u["role"] if u else "user"
    await safe_edit(call.message, neon_card("🔎 Discover Lab", "Search, browse and let AI find the right product", ["🔎 Smart search by keyword", "🛍 Category-based browsing", "🧠 AI suggestion with budget understanding", "🚚 Quick order tracking"], "Fast path from idea to checkout"), reply_markup=user_discover_kb(call.from_user.id, role))
    await call.answer()

@router.callback_query(F.data == "menu:money")
async def cb_money(call: CallbackQuery, state: FSMContext):
    await state.clear()
    u = await db.get_user(call.from_user.id)
    role = u["role"] if u else "user"
    await safe_edit(call.message, neon_card("💳 Payment Zone", "Wallet autopay, exact amount and premium checkout", ["💰 Add balance with amount selector", "✅ Wallet purchases verify instantly", "💳 External payments use exact amount + TRX", "💎 VIP and coupon tools"], "Smart Pay OS keeps orders clean"), reply_markup=user_money_kb(call.from_user.id, role))
    await call.answer()

@router.callback_query(F.data == "menu:rewards")
async def cb_rewards(call: CallbackQuery, state: FSMContext):
    await state.clear()
    u = await db.get_user(call.from_user.id)
    role = u["role"] if u else "user"
    await safe_edit(call.message, neon_card("🎁 Rewards Nexus", "Earn more, unlock VIP and never miss stock", ["🎁 Invite & earn wallet bonus", "🎫 Redeem secret reward codes", "🔔 Watch product restock alerts", "💎 VIP lounge and premium offers"], "Reward system stays simple for users"), reply_markup=user_rewards_kb(call.from_user.id, role))
    await call.answer()

@router.callback_query(F.data == "menu:support")
async def cb_support(call: CallbackQuery, state: FSMContext):
    await state.clear()
    u = await db.get_user(call.from_user.id)
    role = u["role"] if u else "user"
    await safe_edit(call.message, neon_card("🛟 Support Desk Pro", "Order, payment and product help in one place", ["🎫 Open a support ticket", "📦 Review your orders", "🚚 Track live delivery status", "🏪 Seller/vendor request"], "Clear support flow for customers"), reply_markup=user_support_kb(call.from_user.id, role))
    await call.answer()

@router.callback_query(F.data == "menu:info")
async def cb_info(call: CallbackQuery, state: FSMContext):
    await state.clear()
    u = await db.get_user(call.from_user.id)
    role = u["role"] if u else "user"
    await safe_edit(call.message, neon_card("📢 Info Center", "Notice, policy and payment guide", ["📢 Live shop notice", "📜 Refund and delivery policy", "💳 Payment rules and exact amount guide", "🛟 Contact support if confused"], "Professional text builds buyer trust"), reply_markup=user_info_kb(call.from_user.id, role))
    await call.answer()


@router.callback_query(F.data == "menu:account")
async def cb_account(call: CallbackQuery, state: FSMContext):
    await state.clear()
    u = await db.get_user(call.from_user.id)
    role = u["role"] if u else "user"
    body = "Your profile, wallet, orders and VIP status in one premium control card."
    await safe_edit(call.message, neon_card("👤 Account Suite", "Your personal digital-shop control room", ["👤 Profile and role badge", "📦 Order history and delivery status", "💰 Wallet balance and transactions", "💎 VIP status and upgrades"], "Everything personal stays in one clean page"), reply_markup=user_account_kb(call.from_user.id, role))
    await call.answer()

# ═══════════════════════════════════════════════════════════════
#  ULTRA UX SHORTCUTS
# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
#  ULTRA UX SHORTCUTS
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "clear:chat")
async def clear_chat_hint(call: CallbackQuery):
    await call.answer("Telegram bots cannot delete all old messages automatically. I cleaned this screen with a fresh menu ✅", show_alert=True)
    await send_home(call)

@router.callback_query(F.data == "shop:hot")
async def shop_hot(call: CallbackQuery):
    if not await v14_setting_on("shop_open", "1") and not is_admin(call.from_user.id):
        return await safe_edit(call.message, await v14_shop_closed_text(), reply_markup=back_main())
    prods = await db.fetchall("SELECT * FROM products WHERE active=1 ORDER BY featured DESC, sold DESC, created_at DESC LIMIT 10")
    if not prods:
        return await safe_edit(call.message, card("🔥 Hot Deals", "No active products yet."), reply_markup=back_main())
    body = "🔥 <b>Trending & featured products</b>\n\n"
    rows = []
    for p in prods:
        sc = "∞"
        if p["delivery_mode"] == "STOCK":
            sr = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE product_id=? AND used=0", (p["id"],))
            sc = sr["n"] if sr else 0
        badge = "⭐" if p["featured"] else "🔥"
        body += f"{badge} <b>{esc(p['name'])}</b> — {money(p['price'])} | 📦 {sc} | 🚀 {p['sold']} sold\n"
        rows.append([btn(f"{badge} {p['name'][:24]} | {money(p['price'])} | 📦 {sc}", f"prod:{p['id']}")])
    rows.append([btn("🛍 All Categories", "shop:cats"), btn("🏠 Menu", "menu:main")])
    await safe_edit(call.message, card("🔥 Hot Deals", body), reply_markup=kb(rows))
    await call.answer()

# ═══════════════════════════════════════════════════════════════
#  SHOP — BROWSE
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "shop:cats")
async def shop_cats(call: CallbackQuery):
    if not await v14_setting_on("shop_open", "1") and not is_admin(call.from_user.id):
        return await safe_edit(call.message, await v14_shop_closed_text(), reply_markup=back_main())
    cats = await db.fetchall("SELECT * FROM categories WHERE active=1 ORDER BY sort_order, created_at DESC")
    if not cats:
        return await safe_edit(call.message, card("🛒 Store", "No categories yet. Admin can add categories from the control center."), reply_markup=back_main())

    featured = await db.fetchall("SELECT p.*, c.name cat FROM products p JOIN categories c ON c.id=p.category_id WHERE p.active=1 AND p.featured=1 LIMIT 4")

    body = "🌌 <b>ORION CATALOG</b>\n<i>Choose a zone below — every button shows a clean premium path.</i>\n\n"
    if featured:
        body += "⚡ <b>Prime Picks</b>\n"
        for fp in featured:
            disc = ""
            if fp["original_price"] and fp["original_price"] > fp["price"]:
                pct = round((1 - fp["price"] / fp["original_price"]) * 100)
                disc = f"  🔻{pct}%"
            body += f"  ✦ {esc(fp['name'])} — <b>{money(fp['price'])}</b>{disc}\n"
        body += f"\n{divider()}\n\n"

    body += "🧭 <b>Product Zones</b>\n"
    rows = []
    for c in cats:
        cnt = await db.fetchone("SELECT COUNT(*) n FROM products WHERE category_id=? AND active=1", (c["id"],))
        body += f"  {esc(c['emoji'])} <b>{esc(c['name'])}</b> — {cnt['n']} item(s)\n"
        rows.append([btn(f"{c['emoji']} {c['name']}  •  {cnt['n']} items", f"cat:{c['id']}")])

    rows.append([btn("⚡ Hot Drop", "shop:hot"), btn("🔎 Search", "shop:search")])
    rows.append([btn("🏠 Main Menu", "menu:main")])
    await safe_edit(call.message, card("🛒 Premium Store", body, "Clean catalog • Live product count • Instant flow"), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("cat:"))
async def shop_products(call: CallbackQuery):
    cid = call.data.split(":", 1)[1]
    cat = await db.fetchone("SELECT * FROM categories WHERE id=?", (cid,))
    prods = await db.fetchall(
        "SELECT * FROM products WHERE category_id=? AND active=1 ORDER BY featured DESC, price ASC, created_at DESC",
        (cid,)
    )
    if not prods:
        return await safe_edit(call.message,
            mini_card(f"{cat['emoji'] if cat else '📁'} {cat['name'] if cat else 'Category'}", "No products available yet."),
            reply_markup=kb([[btn("⬅️ Categories", "shop:cats")], [btn("🏠 Main Menu", "menu:main")]])
        )

    # V20: screen stays clean — product names are the menu, no long description wall.
    body = (
        f"<b>{esc(cat['name'] if cat else 'Products')}</b>\n"
        "Tap a product to choose quantity and pay."
    )
    rows = []
    for p in prods:
        sc = "∞"
        if p["delivery_mode"] == "STOCK":
            sc_row = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE product_id=? AND used=0", (p["id"],))
            sc = sc_row["n"] if sc_row else 0
        soldout = p["delivery_mode"] == "STOCK" and int(sc or 0) <= 0
        icon = p["description"].strip()[:1] if p["description"] and len(p["description"].strip()) == 1 else (cat["emoji"] if cat else "📦")
        label = f"{'🚫' if soldout else icon} {p['name'][:30]}  •  {money(p['price'])}  •  Stock {sc}"
        rows.append([btn(label, "noop" if soldout else f"prod:{p['id']}")])
    rows.append([btn("📋 My Orders", "orders:mine")])
    rows.append([btn("⬅️ Categories", "shop:cats"), btn("🏠 Main Menu", "menu:main")])
    await safe_edit(call.message, mini_card(f"{cat['emoji'] if cat else '🛍'} Product Menu", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("prod:"))
async def product_view(call: CallbackQuery):
    pid = call.data.split(":", 1)[1]
    p = await db.fetchone(
        "SELECT p.*, c.name cat_name, c.emoji cat_emoji FROM products p "
        "LEFT JOIN categories c ON c.id=p.category_id WHERE p.id=?",
        (pid,)
    )
    if not p:
        return await call.answer("Product not found.", show_alert=True)

    sc_count = 999
    if p["delivery_mode"] == "STOCK":
        sc = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE product_id=? AND used=0", (pid,))
        sc_count = sc["n"] if sc else 0

    max_order_cfg = env_int("MAX_PER_ORDER", 0) or int(await db.get("max_per_order") or 5)
    max_per_order = max(0, min(max_order_cfg, sc_count if p["delivery_mode"] == "STOCK" else max_order_cfg))
    warranty = preview_text(await db.get("holding_warranty") or "6h holding warranty\n2-month shop warranty after activation", max_lines=2, max_chars=90)
    bulk = preview_text(await db.get("bulk_discount_text") or "1-9 -> regular price\n10+ -> reseller price", max_lines=2, max_chars=90)
    auto_note = preview_text(await db.get("auto_delivery_note") or "Instant auto-delivery after payment confirmation.", max_lines=1, max_chars=70)

    rating_line = "No reviews yet"
    if p["rating_count"] > 0:
        avg = p["rating_sum"] / p["rating_count"]
        rating_line = f"{stars(avg)} {avg:.1f}/5"

    desc = preview_text(p["description"] or "Premium digital product.", max_lines=6, max_chars=300)
    stock_label = sc_count if p['delivery_mode'] == 'STOCK' else 'Unlimited'
    price_gap = ""
    try:
        if float(p['original_price'] or 0) > float(p['price'] or 0):
            price_gap = f"  •  🔥 Save {money(float(p['original_price']) - float(p['price']))}"
    except Exception:
        price_gap = ""
    stock_mood = "🟢 Ready" if (p["delivery_mode"] != "STOCK" or int(sc_count or 0) > 3) else ("🟡 Low" if int(sc_count or 0) > 0 else "🔴 Out")
    body = (
        f"<blockquote><b>💎 {esc(p['name'])}</b>\n"
        f"<i>{esc(p['cat_name'] or 'Premium Digital Product')}</i></blockquote>\n"
        f"💰 Price: <b>{money(p['price'])}</b>{price_gap}\n"
        f"📦 Stock: <b>{stock_label}</b>  •  {stock_mood}  •  🧺 Max <b>{max_per_order}</b>\n"
        f"⭐ Rating: {rating_line}  •  🚀 Sold <b>{p['sold']}</b>\n\n"
        f"╭─✦ Product Showcase 2.0 ✦─\n"
        f"│ {esc(desc)}\n"
        f"│ 🛡 Warranty: {esc(warranty)}\n"
        f"│ ⚡ Bulk: {esc(bulk)}\n"
        f"│ ✅ {esc(auto_note)}\n"
        f"╰────────────────"
    )

    if p["delivery_mode"] == "STOCK" and sc_count == 0:
        rows = [
            [btn("🔔 Notify When Available", f"stock:watch:{pid}")],
            [btn("🔄 Refresh", f"prod:{pid}"), btn("⬅️ Back", f"cat:{p['category_id']}")],
        ]
    else:
        rows = [
            [btn("⚡ Buy Now", f"buy:{pid}"), btn("➕ Cart", f"cart:add:{pid}")],
            [btn("🔔 Alert", f"stock:watch:{pid}"), btn("⭐ Reviews", f"reviews:{pid}")],
            [btn("❤️ Save", f"wish:add:{pid}"), btn("⬅️ Back", f"cat:{p['category_id']}")],
        ]
    await safe_edit(call.message, quantum_card(f"{esc(p['cat_emoji'] or '📦')} Product View", "Smart product card with exact checkout actions", body.split("\n"), "Wallet AutoPay = instant verify • external pay = exact TRX queue", await db.get("v24_theme") or "luxury_dark"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer("This product is currently out of stock.", show_alert=True)

# ═══════════════════════════════════════════════════════════════
#  REVIEWS
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("reviews:"))
async def show_reviews(call: CallbackQuery):
    pid = call.data.split(":")[-1]
    p = await db.fetchone("SELECT * FROM products WHERE id=?", (pid,))
    revs = await db.fetchall(
        "SELECT r.*, u.first_name FROM reviews r JOIN users u ON u.id=r.user_id WHERE r.product_id=? ORDER BY r.created_at DESC LIMIT 10",
        (pid,)
    )
    if not revs:
        body = "No reviews yet. Be the first to review!"
    else:
        avg = p["rating_sum"] / p["rating_count"] if p["rating_count"] else 0
        body = f"Overall: {stars(avg)} {avg:.1f}/5\n\n"
        for r in revs:
            body += f"{stars(r['rating'])} — <b>{esc(r['first_name'])}</b>\n"
            if r["comment"]:
                body += f"<i>{esc(r['comment'])}</i>\n"
            body += "\n"
    await safe_edit(call.message, card(f"📜 Reviews: {esc(p['name'])}", body), reply_markup=kb([[btn("⬅️ Back", f"prod:{pid}")]]))
    await call.answer()


@router.callback_query(F.data.startswith("rate:"))
async def rate_order(call: CallbackQuery, state: FSMContext):
    oid = call.data.split(":")[-1]
    o = await db.fetchone("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, call.from_user.id))
    if not o or o["rated"]:
        return await call.answer("Already rated or not found.", show_alert=True)
    await state.set_state(ReviewState.rating)
    await state.update_data(order_id=oid, product_id=o["product_id"])
    await safe_edit(call.message, 
        card("⭐ Rate Product", "Choose your rating:"),
        reply_markup=kb([
            [btn("⭐ 1", "rating:1"), btn("⭐⭐ 2", "rating:2"), btn("⭐⭐⭐ 3", "rating:3")],
            [btn("⭐⭐⭐⭐ 4", "rating:4"), btn("⭐⭐⭐⭐⭐ 5", "rating:5")],
            [btn("❌ Cancel", "state:cancel")],
        ])
    )
    await call.answer()


@router.callback_query(ReviewState.rating, F.data.startswith("rating:"))
async def rating_chosen(call: CallbackQuery, state: FSMContext):
    rating = int(call.data.split(":")[-1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewState.comment)
    await safe_edit(call.message, 
        card("💬 Add Comment", f"You gave {stars(rating)} {rating}/5\n\nWrite a short review (or send 'skip' to skip):"),
        reply_markup=cancel_kb()
    )
    await call.answer()


@router.message(ReviewState.comment)
async def save_review(message: Message, state: FSMContext):
    data = await state.get_data()
    comment = "" if message.text.lower() == "skip" else message.text.strip()
    await db.execute(
        "INSERT INTO reviews(id,order_id,product_id,user_id,rating,comment,created_at) VALUES(?,?,?,?,?,?,?)",
        (code("REV"), data["order_id"], data["product_id"], message.from_user.id, data["rating"], comment, now())
    )
    await db.execute("UPDATE orders SET rated=1 WHERE id=?", (data["order_id"],))
    await db.execute(
        "UPDATE products SET rating_sum=rating_sum+?, rating_count=rating_count+1 WHERE id=?",
        (data["rating"], data["product_id"])
    )
    await state.clear()
    await message.answer(card("✅ Review Submitted", f"Thank you for your {stars(data['rating'])} rating!"), reply_markup=main_menu(message.from_user.id))

# ═══════════════════════════════════════════════════════════════
#  CART
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("cart:add:"))
async def cart_add(call: CallbackQuery):
    pid = call.data.split(":")[-1]
    p = await db.fetchone("SELECT * FROM products WHERE id=? AND active=1", (pid,))
    if not p:
        return await call.answer("Product not found.", show_alert=True)
    existing = await db.fetchone("SELECT qty FROM cart WHERE user_id=? AND product_id=?", (call.from_user.id, pid))
    if existing:
        await db.execute("UPDATE cart SET qty=qty+1 WHERE user_id=? AND product_id=?", (call.from_user.id, pid))
    else:
        await db.execute("INSERT INTO cart(user_id,product_id,qty) VALUES(?,?,1)", (call.from_user.id, pid))
    await call.answer(f"✅ {p['name']} added to cart!", show_alert=False)


@router.callback_query(F.data == "cart:view")
async def cart_view(call: CallbackQuery):
    items = await db.fetchall(
        "SELECT cart.*, products.name, products.price FROM cart "
        "JOIN products ON products.id=cart.product_id WHERE cart.user_id=?",
        (call.from_user.id,)
    )
    if not items:
        return await safe_edit(call.message, card("🧺 My Cart", "Your cart is empty.\n\nBrowse shop to add items!"), reply_markup=kb([
            [btn("🛍 Browse Shop", "shop:cats")],
            [btn("🏠 Main Menu", "menu:main")]
        ]))

    total = sum(float(i["price"]) * int(i["qty"]) for i in items)
    body = ""
    for i in items:
        sub = float(i["price"]) * int(i["qty"])
        body += f"• {esc(i['name'])} × {i['qty']} = {money(sub)}\n"
    body += f"\n{divider()}\n💰 <b>Total: {money(total)}</b>"

    rows = []
    for i in items:
        rows.append([
            btn(f"⚡ Buy {i['name'][:18]}", f"buy:{i['product_id']}"),
            btn("➖", f"cart:dec:{i['product_id']}"),
            btn("🗑", f"cart:rm:{i['product_id']}")
        ])
    rows.append([btn("⚡ Smart Pay All", "cart:smartpay"), btn("🗑 Clear All", "cart:clear")])
    rows.append([btn("🏠 Menu", "menu:main")])
    await safe_edit(call.message, card("🧺 My Cart", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("cart:dec:"))
async def cart_dec(call: CallbackQuery):
    pid = call.data.split(":")[-1]
    existing = await db.fetchone("SELECT qty FROM cart WHERE user_id=? AND product_id=?", (call.from_user.id, pid))
    if existing and existing["qty"] > 1:
        await db.execute("UPDATE cart SET qty=qty-1 WHERE user_id=? AND product_id=?", (call.from_user.id, pid))
    else:
        await db.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (call.from_user.id, pid))
    await cart_view(call)


@router.callback_query(F.data.startswith("cart:rm:"))
async def cart_rm(call: CallbackQuery):
    pid = call.data.split(":")[-1]
    await db.execute("DELETE FROM cart WHERE user_id=? AND product_id=?", (call.from_user.id, pid))
    await cart_view(call)


@router.callback_query(F.data == "cart:clear")
async def cart_clear(call: CallbackQuery):
    await db.execute("DELETE FROM cart WHERE user_id=?", (call.from_user.id,))
    await safe_edit(call.message, card("🧺 Cart", "Cart cleared."), reply_markup=back_main())
    await call.answer()

# ═══════════════════════════════════════════════════════════════
#  WISHLIST
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("wish:add:"))
async def wish_add(call: CallbackQuery):
    pid = call.data.split(":")[-1]
    p = await db.fetchone("SELECT * FROM products WHERE id=?", (pid,))
    if not p:
        return await call.answer("Not found.", show_alert=True)
    existing = await db.fetchone("SELECT * FROM wishlist WHERE user_id=? AND product_id=?", (call.from_user.id, pid))
    if existing:
        await db.execute("DELETE FROM wishlist WHERE user_id=? AND product_id=?", (call.from_user.id, pid))
        await call.answer("💔 Removed from wishlist.", show_alert=False)
    else:
        await db.execute("INSERT INTO wishlist(user_id,product_id,added_at) VALUES(?,?,?)", (call.from_user.id, pid, now()))
        await call.answer("❤️ Added to wishlist!", show_alert=False)


@router.callback_query(F.data == "wish:view")
async def wish_view(call: CallbackQuery):
    items = await db.fetchall(
        "SELECT w.*, p.name, p.price FROM wishlist w JOIN products p ON p.id=w.product_id WHERE w.user_id=? ORDER BY w.added_at DESC",
        (call.from_user.id,)
    )
    if not items:
        return await safe_edit(call.message, card("❤️ Wishlist", "Your wishlist is empty."), reply_markup=back_main())
    body = "\n".join([f"• {esc(i['name'])} — {money(i['price'])}" for i in items])
    rows = [[btn(f"🛒 {i['name'][:22]}", f"prod:{i['product_id']}")] for i in items]
    rows.append([btn("🏠 Menu", "menu:main")])
    await safe_edit(call.message, card("❤️ My Wishlist", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("stock:watch:"))
async def stock_watch(call: CallbackQuery):
    pid = call.data.split(":", 2)[2]
    p = await db.fetchone("SELECT * FROM products WHERE id=? AND active=1", (pid,))
    if not p:
        return await call.answer("Product not found.", show_alert=True)
    await db.execute(
        "INSERT OR REPLACE INTO stock_watch(user_id, product_id, created_at) VALUES(?,?,?)",
        (call.from_user.id, pid, now())
    )
    await call.answer("🔔 Stock alert ON. You will get restock/low/out updates.", show_alert=True)


@router.callback_query(F.data.startswith("stock:unwatch:"))
async def stock_unwatch(call: CallbackQuery):
    pid = call.data.split(":", 2)[2]
    await db.execute("DELETE FROM stock_watch WHERE user_id=? AND product_id=?", (call.from_user.id, pid))
    await call.answer("🔕 Stock alerts OFF for this product.", show_alert=True)


# ═══════════════════════════════════════════════════════════════
#  BUY FLOW
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("buy:"))
async def buy_now(call: CallbackQuery, state: FSMContext):
    """V20 RichPay quantity selector: fixed quick amounts + custom quantity."""
    await state.clear()
    pid = call.data.split(":", 1)[1]
    p = await db.fetchone("SELECT * FROM products WHERE id=? AND active=1", (pid,))
    if not p:
        return await call.answer("Product unavailable.", show_alert=True)

    stock_count = 999999
    if p["delivery_mode"] == "STOCK":
        sc = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE product_id=? AND used=0", (pid,))
        stock_count = int(sc["n"] if sc else 0)
        if stock_count <= 0:
            return await call.answer("Out of stock! Turn on stock alert.", show_alert=True)

    max_cfg = env_int("MAX_PER_ORDER", 0) or int(await db.get("max_per_order") or 25)
    max_qty = min(max_cfg, stock_count) if p["delivery_mode"] == "STOCK" else max_cfg
    quick = [1, 2, 3, 5, 10, 15, 20, 25]
    allowed = [q for q in quick if q <= max_qty]
    if not allowed:
        allowed = [1]
    body = (
        f"{esc(p['name'])}\n"
        f"<b>{money(p['price'])}</b> / code\n\n"
        "How many codes do you want?"
    )
    rows = []
    for i in range(0, len(allowed), 4):
        rows.append([btn(f"🔢 {q}", f"buyq:{pid}:{q}") for q in allowed[i:i+4]])
    rows.append([btn("✏️ Custom Quantity", f"buycustom:{pid}")])
    rows.append([btn("⬅️ Back to Product", f"prod:{pid}")])
    rows.append([btn("🏠 Main Menu", "menu:main")])
    await safe_edit(call.message, mini_card("Select Quantity", body), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data.startswith("buycustom:"))
async def buy_custom_qty_ask(call: CallbackQuery, state: FSMContext):
    pid = call.data.split(":", 1)[1]
    p = await db.fetchone("SELECT * FROM products WHERE id=? AND active=1", (pid,))
    if not p:
        return await call.answer("Product unavailable.", show_alert=True)
    await state.set_state(SmartBuyState.custom_qty)
    await state.update_data(product_id=pid)
    await safe_edit(call.message, mini_card("Custom Quantity", f"Send quantity for:\n<b>{esc(p['name'])}</b>\n\nExample: <code>7</code>"), reply_markup=kb([[btn("⬅️ Back", f"buy:{pid}")], [btn("❌ Cancel", "state:cancel")]]))
    await call.answer()

@router.message(SmartBuyState.custom_qty)
async def buy_custom_qty_receive(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    pid = data.get("product_id")
    try:
        qty = int(str(message.text or "").strip())
    except Exception:
        return await message.answer("❌ Send only number. Example: 5", reply_markup=cancel_kb())
    if qty <= 0 or qty > 999:
        return await message.answer("❌ Quantity must be between 1 and 999.", reply_markup=cancel_kb())
    # Reuse same checkout engine by simulating selected quantity through a light internal call is risky, so call helper.
    await create_order_from_quantity(message, state, bot, pid, qty)


async def create_order_from_quantity(target, state: FSMContext, bot: Bot, pid: str, qty: int):
    user_id = target.from_user.id if isinstance(target, Message) else target.from_user.id
    p = await db.fetchone("SELECT * FROM products WHERE id=? AND active=1", (pid,))
    if not p:
        if isinstance(target, Message):
            return await target.answer("Product unavailable.", reply_markup=back_main())
        return await target.answer("Product unavailable.", show_alert=True)
    max_cfg = env_int("MAX_PER_ORDER", 0) or int(await db.get("max_per_order") or 25)
    if qty > max_cfg:
        msg = f"Max per order is {max_cfg}."
        if isinstance(target, Message):
            return await target.answer(msg, reply_markup=cancel_kb())
        return await target.answer(msg, show_alert=True)
    if p["delivery_mode"] == "STOCK":
        sc = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE product_id=? AND used=0", (pid,))
        stock_count = int(sc["n"] if sc else 0)
        if stock_count < qty:
            msg = f"Only {stock_count} item(s) left."
            if isinstance(target, Message):
                return await target.answer(msg, reply_markup=kb([[btn("⬅️ Quantity", f"buy:{pid}")]]))
            return await target.answer(msg, show_alert=True)

    u = await db.get_user(user_id)
    is_vip = await db.check_vip(user_id)
    subtotal = round(float(p["price"]) * qty, 2)
    vip_disc = 0.0
    if is_vip and u and u["role"] != "admin":
        vip_pct = float(await db.get("vip_discount") or "10")
        vip_disc = round(subtotal * vip_pct / 100, 2)
    final_price = round(subtotal - vip_disc, 2)

    oid = code("ORD")
    await db.execute(
        "INSERT INTO orders(id,user_id,product_id,qty,amount,discount,status,created_at,updated_at,payment_status) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (oid, user_id, pid, qty, subtotal, vip_disc, "WAITING_CONFIRM", now(), now(), "UNPAID")
    )
    await log_order_event(oid, "WAITING_CONFIRM", "V20 order summary created", user_id)
    await maybe_flag_order(bot, user_id, oid)
    await state.set_state(PaymentProof.coupon)
    await state.update_data(order_id=oid, product_id=pid, qty=qty, base_price=subtotal, vip_disc=vip_disc)

    vip_line = f"\nVIP Discount: <b>-{money(vip_disc)}</b>" if vip_disc > 0 else ""
    body = (
        f"🎨 <b>{esc(p['name'])}</b>\n"
        f"Quantity: <b>{qty}</b>\n\n"
        f"<b>Total: {money(final_price)}</b>{vip_line}\n\n"
        f"Order: <code>{oid}</code>"
    )
    markup = kb([
        [btn("✅ Confirm & Choose Payment", f"skipcoupon:{oid}")],
        [btn("🎟 Apply Coupon", "coupon:orderhint"), btn("⬅️ Change Quantity", f"buy:{pid}")],
        [btn("🏠 Main Menu", "menu:main")],
    ])
    if isinstance(target, Message):
        await state.set_state(PaymentProof.coupon)
        return await target.answer(mini_card("Order Summary", body), reply_markup=markup)
    await safe_edit(target.message, mini_card("Order Summary", body), reply_markup=markup)
    await target.answer()

@router.callback_query(F.data == "coupon:orderhint")
async def coupon_order_hint(call: CallbackQuery):
    await call.answer("Send your coupon code as a normal message now, or tap Confirm to skip.", show_alert=True)

@router.callback_query(F.data.startswith("buyq:"))
async def buy_quantity(call: CallbackQuery, state: FSMContext, bot: Bot):
    _, pid, qty_s = call.data.split(":", 2)
    qty = max(1, min(999, int(qty_s)))
    await create_order_from_quantity(call, state, bot, pid, qty)


@router.callback_query(F.data.startswith("skipcoupon:"))
async def skip_coupon(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await show_payment_page(call, state, data, coupon=None)


@router.message(PaymentProof.coupon)
async def coupon_in_order(message: Message, state: FSMContext):
    data = await state.get_data()
    code_str = message.text.strip().upper()
    c = await db.fetchone("SELECT * FROM coupons WHERE code=? AND active=1", (code_str,))
    discount_amount = 0
    if not c or c["used"] >= c["max_uses"]:
        await message.answer("❌ Invalid or expired coupon. Continuing without discount...")
    elif c["expires_at"] and c["expires_at"] < now():
        await message.answer("⌛ Coupon expired. Continuing without discount...")
    else:
        base = data["base_price"]
        if c["discount_type"] == "percent":
            discount_amount = round(base * c["value"] / 100, 2)
        else:
            discount_amount = min(c["value"], base)

        is_vip = await db.check_vip(message.from_user.id)
        if c["vip_only"] and not is_vip:
            await message.answer("💎 This coupon is for VIP members only.")
            discount_amount = 0
        else:
            await db.execute("UPDATE coupons SET used=used+1 WHERE code=?", (c["code"],))
            await db.execute("UPDATE orders SET coupon_code=?, discount=discount+? WHERE id=?",
                (c["code"], discount_amount, data["order_id"]))
            await state.update_data(coupon_code=c["code"], coupon_disc=discount_amount)
            await message.answer(f"✅ Coupon applied! Discount: -{money(discount_amount)}")

    await show_payment_page(message, state, data, coupon=None)


async def show_payment_page(target, state: FSMContext, data: dict, coupon=None):
    data = await state.get_data()
    oid = data["order_id"]
    o = await db.fetchone("SELECT * FROM orders WHERE id=?", (oid,))
    p = await db.fetchone("SELECT * FROM products WHERE id=?", (data["product_id"],))
    uid = target.from_user.id if hasattr(target, "from_user") else target.message.from_user.id
    u = await db.get_user(uid)

    final = round(max(0, float(o["amount"] or 0) - float(o["discount"] or 0)), 2)
    balance = float(u["wallet"] if u else 0)
    rows = []
    if WALLET_ENABLED and await v14_setting_on("wallet_autopay_enabled", "1") and balance >= final:
        rows.append([btn(f"⚡ Wallet AutoPay • {money(final)}", f"paywallet:{oid}")])
    elif WALLET_ENABLED:
        need = round(max(0, final - balance), 2)
        rows.append([btn(f"➕ Add Balance • Need {money(need)}", f"wallet:topup:{need:g}")])
    rows += await smart_payment_method_kb(f"extpay:{oid}")
    rows.append([btn("⬅️ Change Quantity", f"buy:{data['product_id']}")])
    rows.append([btn("🏠 Main Menu", "menu:main")])

    body = (
        f"🎨 {esc(p['name'])} × <b>{o['qty']}</b>\n"
        f"Total: <b>{money(final)}</b>"
    )
    await state.set_state(PaymentProof.proof)
    await state.update_data(order_id=oid, expected_amount=final)
    await db.execute("UPDATE orders SET status='WAITING_PAYMENT', payment_status='WAITING_METHOD', updated_at=? WHERE id=?", (now(), oid))
    if isinstance(target, Message):
        await target.answer(mini_card("Select Payment Method", body), reply_markup=kb(rows))
    else:
        await safe_edit(target.message, mini_card("Select Payment Method", body), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("paywallet:"))
async def pay_wallet(call: CallbackQuery, state: FSMContext, bot: Bot):
    oid = call.data.split(":")[-1]
    o = await db.fetchone("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, call.from_user.id))
    if not o:
        return await call.answer("Order not found.", show_alert=True)
    if o["status"] in ("DELIVERED", "COMPLETED"):
        return await call.answer("Already paid/delivered.", show_alert=True)
    if not await v14_setting_on("wallet_autopay_enabled", "1"):
        return await call.answer("Wallet autopay is disabled by admin.", show_alert=True)
    u = await db.get_user(call.from_user.id)
    final = round(max(0, float(o["amount"] or 0) - float(o["discount"] or 0)), 2)
    if float(u["wallet"] if u else 0) < final:
        return await call.answer(f"Need {money(final - float(u['wallet'] if u else 0))} more.", show_alert=True)

    intent_id = code("PAY")
    await db.execute(
        "INSERT INTO payment_intents(id,user_id,amount,currency,purpose,method,related_ids,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (intent_id, call.from_user.id, final, CURRENCY, "ORDER", "WALLET", oid, "VERIFIED", now(), now())
    )
    await db.execute("UPDATE users SET wallet=wallet-? WHERE id=?", (final, call.from_user.id))
    await db.execute(
        "UPDATE orders SET wallet_used=?, status='PROCESSING', proof_file_id=?, payment_method='WALLET', payment_status='VERIFIED', payment_ref=?, autopay=1, updated_at=? WHERE id=?",
        (final, f"WALLET:{intent_id}", intent_id, now(), oid)
    )
    await db.execute(
        "INSERT INTO wallet_txns(id,user_id,amount,type,note,created_at) VALUES(?,?,?,?,?,?)",
        (code("WTX"), call.from_user.id, -final, "AUTOPAY_PURCHASE", f"Order {oid} / {intent_id}", now())
    )
    await db.execute(
        "INSERT INTO autopay_logs(id,user_id,intent_id,amount,result,note,created_at) VALUES(?,?,?,?,?,?,?)",
        (code("APL"), call.from_user.id, intent_id, final, "VERIFIED", f"Wallet auto payment for order {oid}", now())
    )
    await log_order_event(oid, "PROCESSING", f"Wallet verified instantly ({intent_id})", call.from_user.id)
    await state.clear()

    ok, msg = (False, "Auto delivery disabled")
    if await v14_setting_on("wallet_auto_delivery_enabled", "1"):
        ok, msg = await deliver_order(bot, oid)
    else:
        await log_order_event(oid, "PROCESSING", "Wallet paid, auto delivery disabled by admin", 0)

    title = "✅ Paid & Auto Delivered" if ok else "✅ Wallet Verified"
    body = f"Order <code>{oid}</code>\nPaid: <b>{money(final)}</b>\nPayment Ref: <code>{intent_id}</code>\nStatus: <b>{esc(msg)}</b>"
    await safe_edit(call.message, card(title, body), reply_markup=kb([[btn("📦 View Order", f"order:view:{oid}"), btn("🏠 Home", "menu:main")]]))
    await notify_admins(bot, card("⚡ Wallet Autopay", f"Order <code>{oid}</code> paid by wallet and {'delivered' if ok else 'waiting delivery'}.\nAmount: <b>{money(final)}</b>\nRef: <code>{intent_id}</code>"), reply_markup=kb([[btn("🧾 Order Board", "admin:orders")]]))
    await call.answer("Wallet verified instantly ✅", show_alert=False)


@router.callback_query(F.data.startswith("manualpay:"))
async def manual_pay_exact(call: CallbackQuery, state: FSMContext):
    oid = call.data.split(":")[-1]
    o = await db.fetchone("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, call.from_user.id))
    if not o:
        return await call.answer("Order not found.", show_alert=True)
    final = round(max(0, float(o["amount"] or 0) - float(o["discount"] or 0)), 2)
    await state.update_data(order_id=oid, expected_amount=final, pay_purpose="ORDER")
    await db.execute("UPDATE orders SET payment_method='EXTERNAL_TRX', payment_status='WAITING_METHOD', updated_at=? WHERE id=?", (now(), oid))
    rows = await smart_payment_method_kb(f"extpay:{oid}")
    rows.append([btn("📸 Upload Screenshot/Text Instead", f"manualproof:{oid}")])
    if PAYMENT_WEBAPP_URL or (await db.get("autopay_webapp_url")):
        rows.append([url_btn("🌐 Open Web Payment Page", PAYMENT_WEBAPP_URL or await db.get("autopay_webapp_url"))])
    rows.append([btn("❌ Cancel", "state:cancel")])
    body = (
        f"Order: <code>{oid}</code>\n"
        f"Exact amount: <b>{money(final)}</b>\n\n"
        "Select payment method, send exact amount, then submit only the Transaction ID.\n"
        "<blockquote>🧠 Smart TRX queue checks duplicate Transaction ID + exact amount and sends it to admin approval/API gateway.</blockquote>"
    )
    await safe_edit(call.message, card("⚡ NeoPay Exact Payment", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("manualproof:"))
async def manual_proof_fallback(call: CallbackQuery, state: FSMContext):
    oid = call.data.split(":")[-1]
    o = await db.fetchone("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, call.from_user.id))
    if not o:
        return await call.answer("Order not found.", show_alert=True)
    final = round(max(0, float(o["amount"] or 0) - float(o["discount"] or 0)), 2)
    await state.set_state(PaymentProof.proof)
    await state.update_data(order_id=oid, expected_amount=final, pay_purpose="ORDER")
    await db.execute("UPDATE orders SET payment_method='EXTERNAL_PROOF', payment_status='WAITING_PROOF', updated_at=? WHERE id=?", (now(), oid))
    body = f"Order: <code>{oid}</code>\nExact amount: <b>{money(final)}</b>\n\n{await payment_methods_text()}\n\n📸 Now send screenshot/photo/document or transaction text."
    await safe_edit(call.message, card("📸 Manual Exact Payment", body), reply_markup=cancel_kb())
    await call.answer()


@router.callback_query(F.data.startswith("extpay:"))
async def external_order_method(call: CallbackQuery, state: FSMContext):
    _, oid, method_id = call.data.split(":", 2)
    o = await db.fetchone("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, call.from_user.id))
    if not o:
        return await call.answer("Order not found.", show_alert=True)
    final = round(max(0, float(o["amount"] or 0) - float(o["discount"] or 0)), 2)
    m = await db.fetchone("SELECT * FROM payment_methods WHERE id=? AND active=1", (method_id,))
    if not m:
        return await call.answer("Payment method unavailable.", show_alert=True)
    pay_ref = o["payment_ref"] or payment_ref_code(oid)
    await state.set_state(PaymentProof.trx_id)
    await state.update_data(order_id=oid, expected_amount=final, pay_purpose="ORDER", payment_method=method_id, pay_ref=pay_ref)
    await db.execute("UPDATE orders SET payment_method=?, payment_status='WAITING_TRX', payment_ref=?, updated_at=? WHERE id=?", (method_id, pay_ref, now(), oid))
    body = await smart_payment_instruction(method_id, final, f"Order {oid}")
    body = body.replace(payment_ref_code(f"Order {oid}"), pay_ref)
    title = f"Pay via {esc(m['title'])}"
    await safe_edit(call.message, mini_card(title, body), reply_markup=kb([
        [btn("🔄 Check Status", f"pay:status:{oid}")],
        [btn("📸 Upload Screenshot Instead", f"manualproof:{oid}")],
        [btn("❌ Cancel Order", f"order:cancel:{oid}")],
        [btn("🏠 Main Menu", "menu:main")],
    ]))
    await call.answer()



@router.callback_query(F.data.startswith("pay:status:"))
async def payment_status_check(call: CallbackQuery):
    oid = call.data.split(":")[-1]
    o = await db.fetchone("SELECT o.*, p.name FROM orders o JOIN products p ON p.id=o.product_id WHERE o.id=? AND o.user_id=?", (oid, call.from_user.id))
    if not o:
        return await call.answer("Order not found.", show_alert=True)
    req = await db.fetchone("SELECT * FROM external_payment_requests WHERE related_ids=? ORDER BY created_at DESC LIMIT 1", (oid,))
    status = o["payment_status"] or o["status"]
    if req:
        status = req["status"]
    await call.answer(f"Payment status: {status}", show_alert=True)

@router.callback_query(F.data.startswith("order:cancel:"))
async def user_cancel_order(call: CallbackQuery, state: FSMContext):
    oid = call.data.split(":")[-1]
    o = await db.fetchone("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, call.from_user.id))
    if not o:
        return await call.answer("Order not found.", show_alert=True)
    if o["status"] in ("DELIVERED", "COMPLETED"):
        return await call.answer("Delivered order cannot be cancelled.", show_alert=True)
    await db.execute("UPDATE orders SET status='CANCELLED', payment_status='CANCELLED', updated_at=? WHERE id=?", (now(), oid))
    await log_order_event(oid, "CANCELLED", "User cancelled order", call.from_user.id)
    await state.clear()
    await safe_edit(call.message, mini_card("Order Cancelled", "Your order has been cancelled."), reply_markup=kb([[btn("🛍 Shop", "shop:cats")], [btn("🏠 Main Menu", "menu:main")]]))
    await call.answer("Order cancelled.", show_alert=False)

@router.message(PaymentProof.trx_id)
async def external_payment_trx_receive(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    trx = normalize_trx_id(message.text or "")
    if not trx:
        return await message.answer("❌ Invalid Transaction ID. Send only the TRX ID, example: <code>ABC123XYZ</code>", reply_markup=cancel_kb())
    method_id = data.get("payment_method") or "EXTERNAL"
    if await trx_is_duplicate(method_id, trx):
        return await message.answer("⚠️ This Transaction ID was already submitted. Please send the correct/new TRX ID or contact support.", reply_markup=cancel_kb())
    purpose = data.get("pay_purpose") or "ORDER"
    amount = round(float(data.get("expected_amount") or 0), 2)
    related = data.get("order_id") or data.get("checkout_id") or ""
    req_id = await create_external_payment_request(message.from_user.id, amount, purpose, method_id, related, trx, "TEXT:" + trx, "TRX_SUBMITTED")

    if purpose == "ORDER":
        oid = data.get("order_id")
        await db.execute("UPDATE orders SET proof_file_id=?, status='PENDING', payment_method=?, payment_status='TRX_SUBMITTED', payment_ref=?, updated_at=? WHERE id=?", ("TEXT:" + trx, method_id, trx, now(), oid))
        await log_order_event(oid, "PENDING", f"TRX submitted via {method_id}: {trx}", message.from_user.id)
        admin_text = (
            f"Req: <code>{req_id}</code>\n"
            f"Order: <code>{oid}</code>\n"
            f"Amount: <b>{money(amount)}</b>\n"
            f"Method: <b>{esc(method_id)}</b>\n"
            f"Ref: <code>{esc(data.get('pay_ref') or '')}</code>\n"
            f"TRX: <code>{esc(trx)}</code>"
        )
    else:
        checkout_id = data.get("checkout_id")
        order_ids = [x for x in str(data.get("order_ids") or "").split(',') if x]
        await db.execute("UPDATE cart_checkouts SET status='PENDING_TRX', updated_at=? WHERE id=?", (now(), checkout_id))
        for oid in order_ids:
            await db.execute("UPDATE orders SET proof_file_id=?, status='PENDING', payment_method=?, payment_status='TRX_SUBMITTED', payment_ref=?, updated_at=? WHERE id=?", ("TEXT:" + trx, method_id, trx, now(), oid))
            await log_order_event(oid, "PENDING", f"Cart TRX submitted via {method_id}: {trx}", message.from_user.id)
        admin_text = f"Req: <code>{req_id}</code>\nCart: <code>{checkout_id}</code>\nOrders: <b>{len(order_ids)}</b>\nAmount: <b>{money(amount)}</b>\nMethod: <b>{esc(method_id)}</b>\nTRX: <code>{esc(trx)}</code>"

    await state.clear()
    if purpose == "ORDER":
        user_rows = [[btn("🔄 Check Status", f"pay:status:{related}")], [btn("📦 My Orders", "orders:mine"), btn("🏠 Home", "menu:main")]]
    else:
        user_rows = [[btn("📦 My Orders", "orders:mine"), btn("🏠 Home", "menu:main")]]
    await message.answer(mini_card("✅ Transaction ID Submitted", f"Request: <code>{req_id}</code>\nAmount: <b>{money(amount)}</b>\nStatus: Pending smart verification."), reply_markup=kb(user_rows))
    await notify_admins(bot, card("🔐 RichPay TRX Request", admin_text), reply_markup=kb([[btn("✅ Approve & Auto Deliver", f"admin:payreq:approve:{req_id}")], [btn("❌ Reject", f"admin:payreq:reject:{req_id}"), btn("🧾 Order Board", "admin:orders")]]))


@router.message(PaymentProof.proof)
async def proof_receive(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    oid = data.get("order_id")
    file_id = None

    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    elif message.text:
        file_id = "TEXT:" + message.text[:800]
    else:
        return await message.answer("Please send screenshot, photo, or transaction text.", reply_markup=cancel_kb())

    await db.execute("UPDATE orders SET proof_file_id=?, status='PENDING', payment_method=COALESCE(payment_method,'EXTERNAL_PROOF'), payment_status='PROOF_SUBMITTED', updated_at=? WHERE id=?", (file_id, now(), oid))
    await log_order_event(oid, "PENDING", "Payment proof submitted by user", message.from_user.id)
    await state.clear()

    await message.answer(
        card("✅ Proof Submitted!", f"Order <code>{oid}</code> is pending review.\n\nYou'll be notified once approved."),
        reply_markup=main_menu(message.from_user.id)
    )
    for aid in all_admin_ids():
        try:
            await bot.send_message(
                aid,
                card("🧾 New Pending Order", f"Order: <code>{oid}</code>\nUser: {esc(message.from_user.first_name)} (<code>{message.from_user.id}</code>)"),
                reply_markup=kb([[btn("📸 Proof Queue", "admin:payments"), btn("🧾 Review Orders", "admin:orders")]])
            )
        except Exception:
            pass
    try:
        await v14_super_alert(bot, "payment_proof", "Payment Proof Submitted", f"Proof received for order <code>{oid}</code>.", user_id=message.from_user.id, order_id=oid)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
#  ORDERS
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("orders:mine"))
async def my_orders(call: CallbackQuery):
    page = int(call.data.split(":")[-1]) if ":" in call.data[7:] else 0
    per = 5
    total = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE user_id=?", (call.from_user.id,))
    orders = await db.fetchall(
        "SELECT o.*, p.name FROM orders o JOIN products p ON p.id=o.product_id WHERE o.user_id=? ORDER BY o.created_at DESC LIMIT ? OFFSET ?",
        (call.from_user.id, per, page * per)
    )
    if not orders:
        return await safe_edit(call.message, card("📦 My Orders", "No orders yet."), reply_markup=back_main())

    body = ""
    rows = []
    for o in orders:
        body += f"<code>{o['id']}</code> — {esc(o['name'])}\n  {status_badge(o['status'])}\n\n"
        rows.append([btn(f"📦 {o['id']} | {status_badge(o['status'])}", f"order:view:{o['id']}")])

    nav = []
    if page > 0:
        nav.append(btn("⬅️ Prev", f"orders:mine:{page-1}"))
    if (page + 1) * per < total["n"]:
        nav.append(btn("Next ➡️", f"orders:mine:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([btn("🏠 Main Menu", "menu:main")])

    await safe_edit(call.message, 
        card("📦 My Orders", body, f"Page {page+1} of {max(1, -(-total['n']//per))}"),
        reply_markup=kb(rows)
    )
    await call.answer()


@router.callback_query(F.data.startswith("order:view:"))
async def order_view(call: CallbackQuery):
    oid = call.data.split(":")[-1]
    o = await db.fetchone(
        "SELECT o.*, p.name FROM orders o JOIN products p ON p.id=o.product_id WHERE o.id=? AND o.user_id=?",
        (oid, call.from_user.id)
    )
    if not o:
        return await call.answer("Not found.", show_alert=True)

    disc_line = f"🎟 Coupon: -{money(o['discount'])}\n" if o["discount"] > 0 else ""
    wallet_line = f"💰 Wallet Used: {money(o['wallet_used'])}\n" if o["wallet_used"] > 0 else ""

    body = (
        f"🧾 <b>Order:</b> <code>{o['id']}</code>\n"
        f"🛒 <b>Product:</b> {esc(o['name'])}\n"
        f"💰 <b>Amount:</b> {money(o['amount'])}\n"
        f"{disc_line}{wallet_line}"
        f"📋 <b>Status:</b> {status_badge(o['status'])}\n"
    )
    if o["status"] == "DELIVERED" and o["delivered_text"]:
        body += f"\n<blockquote>📦 <b>Your Delivery</b>\n{esc(o['delivered_text'])}</blockquote>"

    timeline = await order_timeline(o["id"])
    body += f"\n\n<blockquote>🚚 <b>Timeline</b>\n{timeline}</blockquote>"

    rows = [[btn("🏠 Menu", "menu:main"), btn("📦 All Orders", "orders:mine")]]
    if o["status"] == "DELIVERED" and not o["rated"]:
        rows.insert(0, [btn("⭐ Rate This Order", f"rate:{oid}")])

    await safe_edit(call.message, card(f"📦 Order Details", body), reply_markup=kb(rows))
    await call.answer()

# ═══════════════════════════════════════════════════════════════
#  SEARCH
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "shop:search")
async def search_ask(call: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.query)
    await safe_edit(call.message, card("🔎 Search Products", "Type a product name or keyword:"), reply_markup=cancel_kb())
    await call.answer()


@router.message(SearchState.query)
async def search_do(message: Message, state: FSMContext):
    q = f"%{message.text.strip()}%"
    rows = await db.fetchall(
        "SELECT p.*, c.name cat FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1 AND p.name LIKE ? ORDER BY p.featured DESC, p.created_at DESC LIMIT 10",
        (q,)
    )
    await state.clear()
    if not rows:
        return await message.answer(card("🔎 Search", "No products found. Try different keywords."), reply_markup=main_menu(message.from_user.id))
    body = "\n".join([f"• {esc(r['name'])} — {money(r['price'])} [{esc(r['cat'])}]" for r in rows])
    buttons = [[btn(f"🛒 {r['name'][:22]} — {money(r['price'])}", f"prod:{r['id']}")] for r in rows]
    buttons.append([btn("🏠 Menu", "menu:main")])
    await message.answer(card(f"🔎 Results for '{esc(message.text)}'", body), reply_markup=kb(buttons))

# ═══════════════════════════════════════════════════════════════
#  PROFILE
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
#  USER — VIP MEMBERSHIP CENTER / PLANS / REQUESTS
# ═══════════════════════════════════════════════════════════════

def vip_menu_kb(is_vip_user: bool = False, is_admin_user: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [btn("💎 View VIP Plans", "vip:plans"), btn("🎁 VIP Benefits", "vip:benefits")],
        [btn("🛒 How to Buy VIP", "vip:how"), btn("💳 Payment Info", "info:pay")],
    ]
    if not is_vip_user and not is_admin_user:
        rows.append([btn("🥈 Request Monthly VIP", "vip:request:monthly"), btn("💎 Request Lifetime VIP", "vip:request:lifetime")])
        rows.append([btn("✍️ Custom VIP Request", "vip:request")])
    rows.append([btn("👤 My Profile", "profile:me"), btn("🏠 Main Menu", "menu:main")])
    return kb(rows)

async def vip_status_text(uid: int) -> tuple[str, bool, bool, str]:
    u = await db.get_user(uid)
    active_vip = await db.check_vip(uid)
    admin_user = is_admin(uid)
    if active_vip and u and u["role"] != "admin":
        status = "✅ Active VIP"
    elif admin_user:
        status = "👑 Admin Access"
    else:
        status = "⏳ Not VIP yet"
    progress = ""
    if u and u["role"] not in ("admin", "vip"):
        progress = f"\n📊 Auto VIP Progress: {progress_bar(u['orders_count'], VIP_THRESHOLD)} {u['orders_count']}/{VIP_THRESHOLD} orders"
    return status, active_vip, admin_user, progress

@router.callback_query(F.data.in_({"vip:info", "vip:plans"}))
async def vip_plans(call: CallbackQuery):
    await ensure_user(call.from_user)
    status, active_vip, admin_user, progress = await vip_status_text(call.from_user.id)
    vip_discount = await db.get("vip_discount") or "20"
    vip_price = await db.get("vip_price") or "Monthly: 500 BDT | Lifetime: 1500 BDT"
    vip_text = await db.get("vip_text") or "💎 VIP Membership Center"
    plans = await db.get("vip_plans") or "🥈 Monthly VIP — 500 BDT\n💎 Lifetime VIP — 1500 BDT"
    body = (
        f"{vip_text}\n\n"
        f"🏷 Your status: <b>{status}</b>\n"
        f"💸 VIP discount: <b>{esc(vip_discount)}%</b>\n"
        f"💰 Price summary: <b>{esc(vip_price)}</b>\n"
        f"{progress}\n\n"
        f"{plans}\n\n"
        f"👇 Select a VIP plan below to request activation."
    )
    await safe_edit(call.message, card("💎 VIP Plans & Membership", body, "Clear price • Easy request • Admin verification"), reply_markup=vip_menu_kb(active_vip, admin_user))
    await call.answer()

@router.callback_query(F.data == "vip:benefits")
async def vip_benefits(call: CallbackQuery):
    await ensure_user(call.from_user)
    status, active_vip, admin_user, progress = await vip_status_text(call.from_user.id)
    vip_discount = await db.get("vip_discount") or "20"
    benefits = await db.get("vip_benefits") or "🎁 VIP Benefits\n\n✅ Discount\n✅ VIP coupons\n✅ Priority support"
    body = (
        f"{benefits}\n\n"
        f"🏷 Your status: <b>{status}</b>\n"
        f"💸 Active VIP discount: <b>{esc(vip_discount)}%</b>"
        f"{progress}\n\n"
        f"Tap <b>View VIP Plans</b> to see prices and request VIP."
    )
    await safe_edit(call.message, card("🎁 VIP Benefits", body, "VIP unlocks discount, coupons and priority support"), reply_markup=vip_menu_kb(active_vip, admin_user))
    await call.answer()

@router.callback_query(F.data == "vip:how")
async def vip_how_to_buy(call: CallbackQuery):
    await ensure_user(call.from_user)
    status, active_vip, admin_user, progress = await vip_status_text(call.from_user.id)
    steps = await db.get("vip_buy_steps") or "1. Choose plan\n2. Pay\n3. Send proof\n4. Admin activates VIP"
    payment_text = await db.get("payment_text") or "Payment info not set yet."
    body = (
        f"{steps}\n\n"
        f"💳 <b>Payment info:</b>\n{payment_text}\n\n"
        f"🏷 Your status: <b>{status}</b>{progress}"
    )
    await safe_edit(call.message, card("🛒 How to Buy VIP", body, "Choose plan • Pay • Send proof • Get VIP"), reply_markup=vip_menu_kb(active_vip, admin_user))
    await call.answer()

@router.callback_query(F.data.startswith("vip:request:"))
async def vip_request_plan(call: CallbackQuery, bot: Bot):
    await ensure_user(call.from_user)
    plan_key = call.data.split(":", 2)[2]
    plans_map = {
        "monthly": "🥈 Monthly VIP — 500 BDT / 30 days",
        "lifetime": "💎 Lifetime VIP — 1500 BDT one-time",
    }
    plan = plans_map.get(plan_key, "VIP Plan")
    req_id = code("VIP")
    msg = f"VIP REQUEST: Plan: {plan}. User selected plan from VIP menu. Admin should send/verify payment and activate VIP."
    await db.execute("INSERT INTO tickets(id,user_id,message,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
        (req_id, call.from_user.id, msg, "OPEN", now(), now()))
    await notify_admins(bot, card("💎 New VIP Plan Request",
        f"Request: <code>{req_id}</code>\n"
        f"Plan: <b>{esc(plan)}</b>\n"
        f"User: <b>{esc(call.from_user.first_name)}</b> (<code>{call.from_user.id}</code>)\n"
        f"Username: @{esc(call.from_user.username or 'N/A')}\n\n"
        f"Action: Contact user / verify payment, then grant VIP."),
        reply_markup=kb([[btn("💎 Grant VIP", f"admin:vipgrant:{call.from_user.id}"), btn("💎 VIP Requests", "admin:vipreqs")]]))
    await safe_edit(call.message, card("✅ VIP Request Submitted",
        f"Your request has been sent to admin.\n\n"
        f"Request ID: <code>{req_id}</code>\n"
        f"Selected plan: <b>{esc(plan)}</b>\n\n"
        f"Now pay using <b>Payment Info</b> and send proof in Support Ticket, or wait for admin to contact you."),
        reply_markup=kb([[btn("💳 Payment Info", "info:pay"), btn("🎫 Support Ticket", "ticket:new")], [btn("🏠 Main Menu", "menu:main")]]))
    await call.answer("VIP request sent ✅", show_alert=True)

@router.callback_query(F.data == "vip:request")
async def vip_request_start(call: CallbackQuery, state: FSMContext):
    await ensure_user(call.from_user)
    await state.set_state(VipRequestState.message)
    plans = await db.get("vip_price") or "Monthly: 500 BDT | Lifetime: 1500 BDT"
    await safe_edit(call.message, card("✍️ Custom VIP Request",
        f"VIP price/options: <b>{esc(plans)}</b>\n\n"
        f"Write which VIP plan you want, or ask admin for help.\n\n"
        f"Example: <code>I want Monthly VIP. I will pay now, please send payment details.</code>"), reply_markup=cancel_kb())
    await call.answer()

@router.message(VipRequestState.message)
async def vip_request_send(message: Message, state: FSMContext, bot: Bot):
    await db.add_user(message)
    await state.clear()
    req_id = code("VIP")
    text = message.html_text or esc(message.text or "VIP request")
    await db.execute("INSERT INTO tickets(id,user_id,message,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
        (req_id, message.from_user.id, "VIP REQUEST: " + (message.text or "VIP request"), "OPEN", now(), now()))
    await notify_admins(bot, card("💎 New Custom VIP Request",
        f"Request: <code>{req_id}</code>\n"
        f"User: <b>{esc(message.from_user.first_name)}</b> (<code>{message.from_user.id}</code>)\n"
        f"Username: @{esc(message.from_user.username or 'N/A')}\n\n"
        f"Message:\n{text}"),
        reply_markup=kb([[btn("💎 Grant VIP", f"admin:vipgrant:{message.from_user.id}"), btn("🎫 Open Tickets", "admin:tickets")]]))
    await message.answer(card("✅ VIP Request Sent", f"Request ID: <code>{req_id}</code>\nAdmin has been notified. You will get a message after activation."), reply_markup=main_menu(message.from_user.id))

@router.callback_query(F.data == "profile:me")
async def profile(call: CallbackQuery):
    u = await db.fetchone("SELECT * FROM users WHERE id=?", (call.from_user.id,))
    is_vip = await db.check_vip(call.from_user.id)
    ref_count = await db.fetchone("SELECT COUNT(*) n FROM referrals WHERE referrer_id=?", (call.from_user.id,))
    role_str = role_badge("vip" if is_vip and u["role"] != "admin" else u["role"])

    vip_bar = ""
    if u["role"] not in ("admin", "vip"):
        orders = u["orders_count"]
        vip_bar = f"\n📊 VIP: {progress_bar(orders, VIP_THRESHOLD)} {orders}/{VIP_THRESHOLD}"

    body = (
        f"🆔 <code>{call.from_user.id}</code>\n"
        f"👤 {esc(call.from_user.first_name)}\n"
        f"👑 {role_str}\n"
        f"💼 Balance: <b>{money(u['wallet'])}</b>\n"
        f"📦 Orders: <b>{u['orders_count']}</b>  |  💸 Spent: <b>{money(u['total_spent'])}</b>\n"
        f"🎁 Refs: <b>{ref_count['n']}</b>  |  🔗 Code: <code>{u['ref_code']}</code>{vip_bar}"
    )
    await safe_edit(call.message, card("👤 My Profile", body), reply_markup=kb([
        [btn("💼 Wallet", "wallet:view"), btn("📦 Orders", "orders:mine")],
        [btn("🎁 Referral", "ref:info"), btn("💎 VIP", "vip:plans")],
        [btn("🏠 Menu", "menu:main")]
    ]))
    await call.answer()

# ═══════════════════════════════════════════════════════════════
#  WALLET
# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
#  WALLET
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "wallet:view")
async def wallet_view(call: CallbackQuery):
    if not WALLET_ENABLED:
        return await call.answer("Wallet is disabled.", show_alert=True)
    u = await db.get_user(call.from_user.id)
    txns = await db.fetchall(
        "SELECT * FROM wallet_txns WHERE user_id=? ORDER BY created_at DESC LIMIT 8",
        (call.from_user.id,)
    )
    body = f"💰 <b>Balance: {money(u['wallet'])}</b>\n\n<b>Recent Transactions:</b>\n"
    for t in txns:
        sign = "+" if t["amount"] > 0 else ""
        body += f"{'🟢' if t['amount']>0 else '🔴'} {sign}{money(t['amount'])} — {esc(t['type'])} — {esc(t['note'])}\n"
    if not txns:
        body += "No transactions yet."
    await safe_edit(call.message, card("💰 My Wallet", body), reply_markup=kb([
        [btn("➕ Top Up Wallet", "wallet:topup")],
        [btn("🏠 Menu", "menu:main")]
    ]))
    await call.answer()


@router.callback_query(F.data == "wallet:topup")
async def wallet_topup(call: CallbackQuery, state: FSMContext):
    if not WALLET_ENABLED:
        return await call.answer("Wallet disabled.", show_alert=True)
    amounts_raw = await db.get("exact_amount_buttons") or "50,100,200,500,1000,2000"
    amounts = []
    for part in amounts_raw.split(','):
        try:
            val = float(part.strip())
            if val > 0:
                amounts.append(val)
        except Exception:
            pass
    if not amounts:
        amounts = [50, 100, 200, 500, 1000]
    rows = []
    line = []
    for amount in amounts[:8]:
        line.append(btn(money(amount), f"wallet:topup:{amount:g}"))
        if len(line) == 2:
            rows.append(line); line = []
    if line:
        rows.append(line)
    rows.append([btn("✍️ Custom Amount", "wallet:topup:custom")])
    rows.append([btn("⬅️ Money", "menu:money"), btn("🏠 Home", "menu:main")])
    body = (
        "Select the exact amount first. Then pay that exact amount and upload proof.\n\n"
        "💡 Wallet balance is the bot's real internal payment system: after admin/API credit, wallet purchases are verified instantly and auto-delivered."
    )
    await safe_edit(call.message, card("💳 Add Wallet Balance", body), reply_markup=kb(rows))
    await state.clear()
    await call.answer()


@router.callback_query(F.data == "wallet:topup:custom")
async def wallet_topup_custom(call: CallbackQuery, state: FSMContext):
    await state.set_state(WalletState.custom_amount)
    await safe_edit(call.message, card("✍️ Custom Top-Up", "Send the amount you want to add to wallet. Example: <code>250</code>"), reply_markup=cancel_kb())
    await call.answer()


@router.message(WalletState.custom_amount)
async def wallet_topup_custom_amount(message: Message, state: FSMContext):
    try:
        amount = round(float(message.text.strip()), 2)
    except Exception:
        return await message.answer("❌ Invalid amount. Send only number, example: 250", reply_markup=cancel_kb())
    if amount <= 0:
        return await message.answer("❌ Amount must be greater than 0.", reply_markup=cancel_kb())
    await state.update_data(expected_amount=amount)
    body = (
        f"Exact amount: <b>{money(amount)}</b>\n\n"
        "Select method, send exact amount, then submit Transaction ID. Admin/API will credit this exact amount."
    )
    rows = await wallet_payment_rows(amount)
    await message.answer(card("💳 NeoPay Wallet Top-Up", body), reply_markup=kb(rows))


@router.callback_query(F.data.startswith("wallet:topup:"))
async def wallet_topup_amount(call: CallbackQuery, state: FSMContext):
    raw = call.data.split(":")[-1]
    try:
        amount = round(float(raw), 2)
    except Exception:
        return await call.answer("Invalid amount.", show_alert=True)
    if amount <= 0:
        return await call.answer("Invalid amount.", show_alert=True)
    await state.update_data(expected_amount=amount)
    rows = await wallet_payment_rows(amount)
    body = (
        f"Exact amount: <b>{money(amount)}</b>\n\n"
        "Select method, send exact amount, then submit Transaction ID. Admin/API will credit this exact amount."
    )
    await safe_edit(call.message, card("💳 NeoPay Wallet Top-Up", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("walletpay:"))
async def wallet_topup_method(call: CallbackQuery, state: FSMContext):
    _, amount_raw, method_id = call.data.split(":", 2)
    amount = round(float(amount_raw), 2)
    m = await db.fetchone("SELECT * FROM payment_methods WHERE id=? AND active=1", (method_id,))
    if not m:
        return await call.answer("Payment method unavailable.", show_alert=True)
    await state.set_state(WalletState.topup_trx_id)
    await state.update_data(expected_amount=amount, payment_method=method_id)
    body = await smart_payment_instruction(method_id, amount, "Wallet top-up")
    await safe_edit(call.message, card("🔐 Wallet Transaction ID", body), reply_markup=kb([[btn("📸 Upload Screenshot/Text Instead", f"walletproof:{amount:g}")], [btn("❌ Cancel", "state:cancel")]]))
    await call.answer()


@router.callback_query(F.data.startswith("walletproof:"))
async def wallet_topup_proof_fallback(call: CallbackQuery, state: FSMContext):
    amount = round(float(call.data.split(":")[-1]), 2)
    await state.set_state(WalletState.topup_proof)
    await state.update_data(expected_amount=amount)
    topup_text = await db.get("wallet_topup_text")
    body = (
        f"Exact amount: <b>{money(amount)}</b>\n\n"
        f"{topup_text}\n\n"
        "<blockquote>📸 Send screenshot/photo/document or transaction text now. Admin/API will verify and credit this exact amount.</blockquote>"
    )
    await safe_edit(call.message, card("💳 Exact Amount Top-Up", body), reply_markup=cancel_kb())
    await call.answer()


@router.message(WalletState.topup_trx_id)
async def wallet_topup_trx_receive(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    trx = normalize_trx_id(message.text or "")
    if not trx:
        return await message.answer("❌ Invalid Transaction ID. Send only the TRX ID.", reply_markup=cancel_kb())
    method_id = data.get("payment_method") or "EXTERNAL"
    if await trx_is_duplicate(method_id, trx):
        return await message.answer("⚠️ This Transaction ID was already submitted. Send a new/correct TRX ID.", reply_markup=cancel_kb())
    amount = round(float(data.get("expected_amount") or 0), 2)
    req_id = await create_external_payment_request(message.from_user.id, amount, "WALLET", method_id, "WALLET_TOPUP", trx, "TEXT:" + trx, "TRX_SUBMITTED")
    await state.clear()
    await message.answer(card("✅ Top-Up TRX Submitted", f"Request: <code>{req_id}</code>\nAmount: <b>{money(amount)}</b>\nStatus: Pending smart verification."), reply_markup=main_menu(message.from_user.id))
    await notify_admins(bot, card("💳 Wallet Top-Up TRX", f"Req: <code>{req_id}</code>\nUser: <code>{message.from_user.id}</code>\nAmount: <b>{money(amount)}</b>\nMethod: <b>{esc(method_id)}</b>\nTRX: <code>{esc(trx)}</code>"), reply_markup=kb([[btn(f"✅ Credit Exact {money(amount)}", f"admin:payreq:approve:{req_id}")], [btn("❌ Reject", f"admin:payreq:reject:{req_id}")]]))


@router.message(WalletState.topup_proof)
async def wallet_topup_proof(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    expected_amount = round(float(data.get("expected_amount") or 0), 2)
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    elif message.text:
        file_id = "TEXT:" + message.text[:500]
    else:
        return await message.answer("Please send screenshot or text.", reply_markup=cancel_kb())

    req_id = code("WTR")
    if expected_amount > 0:
        await create_external_payment_request(message.from_user.id, expected_amount, "WALLET", "PROOF", req_id, "", file_id, "PROOF_SUBMITTED")
    await state.clear()
    await message.answer(card("✅ Top-Up Request Sent", f"Request ID: <code>{req_id}</code>\nAmount: <b>{money(expected_amount)}</b>\nAdmin will credit your wallet shortly."), reply_markup=main_menu(message.from_user.id))

    for aid in all_admin_ids():
        try:
            buttons = [[btn(f"✅ Credit Exact {money(expected_amount)}", f"admin:creditexact:{message.from_user.id}:{expected_amount:g}")]] if expected_amount > 0 else []
            buttons.append([btn(f"➕ Add Wallet Balance", f"admin:addwallet:{message.from_user.id}")])
            await bot.send_message(
                aid,
                card("💰 Wallet Top-Up Request",
                    f"Req: <code>{req_id}</code>\nUser: {esc(message.from_user.first_name)} (<code>{message.from_user.id}</code>)\nAmount: <b>{money(expected_amount)}</b>"),
                reply_markup=kb(buttons)
            )
            if file_id and not file_id.startswith("TEXT:"):
                try:
                    await bot.send_photo(aid, file_id, caption=f"Top-up proof for {message.from_user.id}")
                except Exception:
                    await bot.send_document(aid, file_id, caption=f"Top-up proof for {message.from_user.id}")
            elif file_id:
                await bot.send_message(aid, f"Text proof: {esc(file_id[5:])}")
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════
#  REFERRAL
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "ref:info")
async def ref_info(call: CallbackQuery):
    bonus = await db.get("referral_bonus")
    u = await db.get_user(call.from_user.id)
    count = await db.fetchone("SELECT COUNT(*) n FROM referrals WHERE referrer_id=?", (call.from_user.id,))
    body = (
        f"🎁 Earn <b>{money(parse_amount(bonus or 0))}</b> wallet bonus for each friend you invite!\n\n"
        f"👥 <b>Your Referrals:</b> {count['n']}\n"
        f"💰 <b>Total Earned:</b> {money(int(count['n']) * parse_amount(bonus or 0))}\n\n"
        f"🔗 <b>Your Referral Link:</b>\n"
        f"<code>https://t.me/YourBotUsername?start=ref_{u['ref_code']}</code>\n\n"
        "Share this link with friends. When they join & make their first order, you earn!"
    )
    await safe_edit(call.message, card("🎁 PRIME REFERRAL", body, "Unique invite code • Wallet reward • Growth system"), reply_markup=back_main())
    await call.answer()

# ═══════════════════════════════════════════════════════════════
#  INFO PAGES
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data.in_({"info:pay", "info:notice", "info:policy"}))
async def info_pages(call: CallbackQuery):
    key = call.data.split(":")[1]
    map_key = {"pay": "payment_text", "notice": "notice", "policy": "policy"}[key]
    title = {"pay": "💳 Payment Info", "notice": "📢 Notice Board", "policy": "📜 Shop Policy"}[key]
    await safe_edit(call.message, card(title, await db.get(map_key)), reply_markup=back_main())
    await call.answer()

# ═══════════════════════════════════════════════════════════════
#  TICKETS & COUPONS
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "ticket:new")
async def ticket_new(call: CallbackQuery, state: FSMContext):
    open_tickets = await db.fetchone("SELECT COUNT(*) n FROM tickets WHERE user_id=? AND status='OPEN'", (call.from_user.id,))
    if open_tickets["n"] >= 3:
        return await safe_edit(call.message, card("⚠️ Ticket Limit", "You have 3 open tickets. Please wait for replies before creating more."), reply_markup=back_main())
    await state.set_state(TextEdit.ticket_message)
    await safe_edit(call.message, card("🎫 Support Ticket", "Write your problem briefly. If needed, include your order ID."), reply_markup=cancel_kb())
    await call.answer()


@router.message(TextEdit.ticket_message)
async def ticket_save(message: Message, state: FSMContext, bot: Bot):
    tid = code("TKT")
    await db.execute("INSERT INTO tickets(id,user_id,message,created_at,updated_at) VALUES(?,?,?,?,?)",
        (tid, message.from_user.id, message.text, now(), now()))
    await state.clear()
    await message.answer(card("✅ Ticket Created", f"Ticket ID: <code>{tid}</code>\nSupport will reply soon."), reply_markup=main_menu(message.from_user.id))
    for aid in all_admin_ids():
        try:
            await bot.send_message(aid, card("🎫 New Support Ticket", f"<code>{tid}</code>\nUser: {esc(message.from_user.first_name)} (<code>{message.from_user.id}</code>)\n\n{esc(message.text)}"),
                reply_markup=kb([[btn("🎫 Reply Tickets", "admin:tickets")]]))
        except Exception:
            pass


@router.callback_query(F.data == "coupon:ask")
async def coupon_ask(call: CallbackQuery, state: FSMContext):
    await state.set_state(TextEdit.coupon_code)
    await safe_edit(call.message, card("🎟 Redeem Coupon", "Send your coupon code to check validity:"), reply_markup=cancel_kb())
    await call.answer()


@router.message(TextEdit.coupon_code)
async def coupon_check(message: Message, state: FSMContext):
    c = await db.fetchone("SELECT * FROM coupons WHERE code=? AND active=1", (message.text.strip().upper(),))
    await state.clear()
    if not c or c["used"] >= c["max_uses"] or (c["expires_at"] and c["expires_at"] < now()):
        return await message.answer(card("❌ Coupon", "Invalid or expired coupon."), reply_markup=main_menu(message.from_user.id))

    disc_str = f"{c['value']}%" if c["discount_type"] == "percent" else money(c["value"])
    vip_str = " (VIP Only 💎)" if c["vip_only"] else ""
    min_str = f"\n💰 Min order: {money(c['min_order'])}" if c["min_order"] > 0 else ""
    body = f"Code: <code>{esc(c['code'])}</code>\n🎁 Discount: <b>{disc_str}</b>{vip_str}{min_str}\n✅ Uses left: {c['max_uses'] - c['used']}\n\nApply this coupon at checkout!"
    await message.answer(card("✅ Valid Coupon!", body), reply_markup=main_menu(message.from_user.id))

# ═══════════════════════════════════════════════════════════════
#  ADMIN — DASHBOARD & ANALYTICS
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
#  REDEEM CENTER — USER + ADMIN
# ═══════════════════════════════════════════════════════════════

@router.message(Command("redeem"))
async def redeem_cmd(message: Message, state: FSMContext):
    await db.add_user(message)
    await state.set_state(TextEdit.redeem_code)
    help_text = await db.get("redeem_help") or "Send your redeem code."
    await message.answer(card("🎁 Redeem Center", help_text), reply_markup=cancel_kb())

@router.callback_query(F.data == "redeem:ask")
async def redeem_ask(call: CallbackQuery, state: FSMContext):
    await ensure_user(call.from_user)
    await state.set_state(TextEdit.redeem_code)
    help_text = await db.get("redeem_help") or "Send your redeem code."
    await safe_edit(call.message, card("🎁 Redeem Center", help_text, "Wallet • VIP • Product rewards"), reply_markup=cancel_kb())
    await call.answer()

async def _redeem_product_reward(user_id: int, product_id: str) -> tuple[bool, str]:
    product = await db.fetchone("SELECT * FROM products WHERE id=?", (product_id,))
    if not product:
        return False, "Product reward is invalid. Contact admin."
    stock = await db.fetchone("SELECT * FROM stock WHERE product_id=? AND used=0 ORDER BY created_at ASC LIMIT 1", (product_id,))
    if not stock:
        return False, "Reward stock is currently empty. Admin has been notified; please try later."
    oid = code("RDM-ORDER")
    await db.execute("INSERT INTO orders(id,user_id,product_id,qty,amount,status,created_at,updated_at,delivered_text,admin_note) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (oid, user_id, product_id, 1, 0, "DELIVERED", now(), now(), stock["content"], "Redeem code product reward"))
    await db.execute("UPDATE stock SET used=1, order_id=?, used_at=? WHERE id=?", (oid, now(), stock["id"]))
    await db.execute("UPDATE products SET sold=sold+1 WHERE id=?", (product_id,))
    await db.execute("UPDATE users SET orders_count=orders_count+1 WHERE id=?", (user_id,))
    body = f"Product: <b>{esc(product['name'])}</b>\nOrder: <code>{oid}</code>\n\n<blockquote>{esc(stock['content'])}</blockquote>"
    return True, body

@router.message(TextEdit.redeem_code)
async def redeem_apply(message: Message, state: FSMContext, bot: Bot):
    await db.add_user(message)
    raw_code = message.text.strip().upper().replace(" ", "")
    c = await db.fetchone("SELECT * FROM redeem_codes WHERE code=? AND active=1", (raw_code,))
    if not c:
        return await message.answer(card("❌ Invalid Code", "This redeem code was not found or is inactive."), reply_markup=main_menu(message.from_user.id))
    if c["expires_at"] and c["expires_at"] < now():
        return await message.answer(card("⌛ Expired Code", "This redeem code has expired."), reply_markup=main_menu(message.from_user.id))
    if c["max_uses"] > 0 and c["used"] >= c["max_uses"]:
        return await message.answer(card("⚠️ Limit Finished", "This code has reached its maximum usage limit."), reply_markup=main_menu(message.from_user.id))
    already = await db.fetchone("SELECT id FROM redeem_logs WHERE code=? AND user_id=?", (raw_code, message.from_user.id))
    if already:
        return await message.answer(card("⚠️ Already Redeemed", "You have already used this code."), reply_markup=main_menu(message.from_user.id))

    reward_type = str(c["reward_type"]).upper().strip()
    value = str(c["value"]).strip()
    ok, result = True, ""

    if reward_type == "WALLET":
        amount = parse_amount(value, 0)
        if amount <= 0:
            ok, result = False, "Invalid wallet amount in this code."
        else:
            await db.wallet_add(message.from_user.id, amount, "REDEEM", f"Redeem code {raw_code}")
            result = f"Wallet credited: <b>{money(amount)}</b>"
    elif reward_type == "VIP":
        days = int(parse_amount(value, 0))
        vip_expires = 0 if days <= 0 else now() + days * 86400
        await db.execute("UPDATE users SET role='vip', vip_expires=? WHERE id=?", (vip_expires, message.from_user.id))
        result = "VIP activated: <b>Lifetime</b>" if days <= 0 else f"VIP activated for <b>{days} days</b>"
    elif reward_type == "PRODUCT":
        ok, result = await _redeem_product_reward(message.from_user.id, value)
    elif reward_type == "COUPON":
        cp = await db.fetchone("SELECT code FROM coupons WHERE code=? AND active=1", (value.upper(),))
        if cp:
            result = f"Coupon unlocked: <code>{esc(value.upper())}</code>\nUse this at checkout."
        else:
            ok, result = False, "Linked coupon is inactive or missing."
    else:
        ok, result = False, "Unknown reward type. Contact admin."

    if not ok:
        try:
            await notify_admins(bot, card("⚠️ Redeem Failed", f"Code: <code>{esc(raw_code)}</code>\nUser: <code>{message.from_user.id}</code>\nReason: {esc(result)}"))
        except Exception:
            pass
        return await message.answer(card("❌ Redeem Failed", esc(result)), reply_markup=main_menu(message.from_user.id))

    await db.execute("UPDATE redeem_codes SET used=used+1 WHERE code=?", (raw_code,))
    await db.execute("INSERT INTO redeem_logs(id,code,user_id,reward_type,value,created_at) VALUES(?,?,?,?,?,?)",
        (code("RLOG"), raw_code, message.from_user.id, reward_type, value, now()))
    await state.clear()
    await message.answer(card("✅ Redeem Successful", result, "Thanks for using redeem center"), reply_markup=main_menu(message.from_user.id))
    await notify_admins(bot, card("🎁 Code Redeemed", f"Code: <code>{esc(raw_code)}</code>\nUser: <code>{message.from_user.id}</code>\nReward: <b>{esc(reward_type)}</b> → <code>{esc(value)}</code>"), exclude=message.from_user.id)

@router.callback_query(F.data == "admin:redeems")
async def admin_redeems(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    codes = await db.fetchall("SELECT * FROM redeem_codes ORDER BY created_at DESC LIMIT 12")
    body = ""
    if not codes:
        body = "No redeem codes yet. Create one from the button below."
    for c in codes:
        status = "✅" if c["active"] else "⛔"
        left = "∞" if c["max_uses"] <= 0 else str(max(0, c["max_uses"] - c["used"]))
        body += f"{status} <code>{esc(c['code'])}</code> — {esc(c['reward_type'])}:{esc(c['value'])} | left {left}\n"
    rows = [
        [btn("➕ Create Redeem Code", "admin:redeem:create")],
        [btn("📜 Recent Redeem Logs", "admin:redeem:logs")],
        [btn("⬅️ Admin Home", "admin:home")]
    ]
    await safe_edit(call.message, card("🎁 Redeem Code Manager", body, "Supports WALLET, VIP, PRODUCT, COUPON rewards"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:redeem:create")
async def redeem_create_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(TextEdit.redeem_create)
    await safe_edit(call.message, card("➕ Create Redeem Code",
        "Send in this format:\n\n"
        "<code>CODE | TYPE | VALUE | MAX_USES | EXPIRE_DAYS</code>\n\n"
        "Examples:\n"
        "<code>LUFFY50 | WALLET | 50 | 100 | 0</code>\n"
        "<code>VIP30 | VIP | 30 | 10 | 7</code>\n"
        "<code>FREEACC | PRODUCT | PROD-123 | 1 | 0</code>\n"
        "<code>SALE2026 | COUPON | OFF20 | 500 | 30</code>\n\n"
        "EXPIRE_DAYS 0 = no expiry. VIP value 0 = lifetime."), reply_markup=cancel_kb())
    await call.answer()

@router.message(TextEdit.redeem_create)
async def redeem_create_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 5:
        return await message.answer("❌ Wrong format. Use: CODE | TYPE | VALUE | MAX_USES | EXPIRE_DAYS")
    code_str, reward_type, value, max_uses, expire_days = parts
    code_str = code_str.upper().replace(" ", "")
    reward_type = reward_type.upper()
    if reward_type not in {"WALLET", "VIP", "PRODUCT", "COUPON"}:
        return await message.answer("❌ TYPE must be WALLET, VIP, PRODUCT, or COUPON")
    try:
        max_uses_i = int(float(max_uses))
        expire_days_i = int(float(expire_days))
    except ValueError:
        return await message.answer("❌ MAX_USES and EXPIRE_DAYS must be numbers.")
    expires_at = 0 if expire_days_i <= 0 else now() + expire_days_i * 86400
    await db.execute("INSERT OR REPLACE INTO redeem_codes(code,reward_type,value,max_uses,used,active,created_at,expires_at) VALUES(?,?,?,?,COALESCE((SELECT used FROM redeem_codes WHERE code=?),0),1,?,?)",
        (code_str, reward_type, value, max_uses_i, code_str, now(), expires_at))
    await state.clear()
    await message.answer(card("✅ Redeem Code Created", f"Code: <code>{esc(code_str)}</code>\nReward: <b>{esc(reward_type)}</b> → <code>{esc(value)}</code>\nMax uses: <b>{max_uses_i if max_uses_i > 0 else 'Unlimited'}</b>\nExpiry: <b>{expire_days_i if expire_days_i > 0 else 'No expiry'}</b> days"), reply_markup=admin_home_kb())

@router.callback_query(F.data == "admin:redeem:logs")
async def redeem_logs(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    logs = await db.fetchall("SELECT * FROM redeem_logs ORDER BY created_at DESC LIMIT 20")
    if not logs:
        return await safe_edit(call.message, card("📜 Redeem Logs", "No redeem activity yet."), reply_markup=kb([[btn("⬅️ Redeem Manager", "admin:redeems")]]))
    body = ""
    for r in logs:
        body += f"• <code>{esc(r['code'])}</code> by <code>{r['user_id']}</code> — {esc(r['reward_type'])}:{esc(r['value'])}\n"
    await safe_edit(call.message, card("📜 Recent Redeem Logs", body), reply_markup=kb([[btn("⬅️ Redeem Manager", "admin:redeems")]]))
    await call.answer()

@router.callback_query(F.data == "admin:home")
async def admin_home(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Access Denied", show_alert=True)
    body = f"Admin: <b>{esc(call.from_user.first_name)}</b>\nChoose one section. Every tool stays inside pages."
    await safe_edit(call.message, quantum_card("🚀 Admin Quantum OS", "Everything controlled from the bot — no code edit needed", [body, "🎨 Theme • 🧠 AI • 💳 Payment • ⚡ Speed • 🛡 Security"], "V24 final premium command center", await db.get("v24_theme") or "luxury_dark"), reply_markup=admin_home_kb())
    await call.answer()


@router.callback_query(F.data.startswith("admin:sec:"))
async def admin_section(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Access Denied", show_alert=True)
    section = call.data.split(":", 2)[2]
    names = {
        "dash": "📊 Pulse Dashboard",
        "orders": "🧾 Orders Command Hub",
        "catalog": "🛍 Store Engine",
        "users": "👥 People CRM",
        "growth": "📣 Growth Studio",
        "system": "⚙️ System Core",
    }
    hints = {
        "dash": ["📈 Live metrics", "🧬 Smart insights", "🛡 Fraud overview"],
        "orders": ["🧾 Orders", "📸 Proof queue", "🎫 Support", "💎 VIP requests"],
        "catalog": ["📁 Categories", "🛒 Products", "🔐 Vault", "💳 Payment methods"],
        "users": ["👥 Users", "👑 Admins", "🚫 Ban control", "💰 Wallet tools"],
        "growth": ["🎟 Coupons", "🎁 Redeem", "🤖 AI sales", "📣 Broadcasts"],
        "system": ["🗄 Backup", "📤 Export", "🧩 Feature switches", "🍃 MongoDB sync"],
    }
    await safe_edit(call.message, premium_card(names.get(section, "🖥 Admin Section"), "Choose a premium control module", hints.get(section, ["Choose an action."]), "Layered design: advanced but clean"), reply_markup=admin_section_kb(section))
    await call.answer()
@router.callback_query(F.data == "admin:dash")
async def admin_dash(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    u = await db.fetchone("SELECT COUNT(*) n FROM users")
    u_today = await db.fetchone("SELECT COUNT(*) n FROM users WHERE joined_at>?", (now() - 86400,))
    p = await db.fetchone("SELECT COUNT(*) n FROM products WHERE active=1")
    o_total = await db.fetchone("SELECT COUNT(*) n FROM orders")
    o_pend = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE status IN ('PENDING','WAITING_PROOF')")
    rev = await db.fetchone("SELECT COALESCE(SUM(amount),0) s FROM orders WHERE status='DELIVERED'")
    rev_today = await db.fetchone("SELECT COALESCE(SUM(amount),0) s FROM orders WHERE status='DELIVERED' AND updated_at>?", (now() - 86400,))
    st = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE used=0")
    tkt = await db.fetchone("SELECT COUNT(*) n FROM tickets WHERE status='OPEN'")

    body = (
        f"👥 Total Users: <b>{u['n']}</b> (+{u_today['n']} today)\n"
        f"🛒 Active Products: <b>{p['n']}</b>\n"
        f"🔐 Available Stock: <b>{st['n']}</b>\n"
        f"🧾 Total Orders: <b>{o_total['n']}</b>\n"
        f"⏳ Pending Approval: <b>{o_pend['n']}</b>\n"
        f"🎫 Open Tickets: <b>{tkt['n']}</b>\n"
        f"💰 Revenue Today: <b>{money(rev_today['s'])}</b>\n"
        f"💸 Total Revenue: <b>{money(rev['s'])}</b>\n\n"
        f"{'⚠️ ' + str(o_pend['n']) + ' orders need attention!' if o_pend['n'] > 0 else '✅ All orders reviewed.'}"
    )
    rows = [
        [btn("🧾 Pending Orders", "admin:orders"), btn("📈 Analytics", "admin:analytics")],
        [btn("⬅️ Admin Home", "admin:home")]
    ]
    await safe_edit(call.message, card("📊 Live Dashboard", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data == "admin:analytics")
async def admin_analytics(call: CallbackQuery):
    if not is_admin(call.from_user.id): return

    # Top 5 products
    top_prods = await db.fetchall("SELECT name, sold, rating_sum, rating_count FROM products ORDER BY sold DESC LIMIT 5")
    # Revenue last 7 days
    rev_7 = await db.fetchone("SELECT COALESCE(SUM(amount),0) s FROM orders WHERE status='DELIVERED' AND updated_at>?", (now() - 7*86400,))
    rev_30 = await db.fetchone("SELECT COALESCE(SUM(amount),0) s FROM orders WHERE status='DELIVERED' AND updated_at>?", (now() - 30*86400,))
    # Order status breakdown
    statuses = await db.fetchall("SELECT status, COUNT(*) n FROM orders GROUP BY status")
    # User growth
    u_week = await db.fetchone("SELECT COUNT(*) n FROM users WHERE joined_at>?", (now() - 7*86400,))

    body = f"📈 <b>Revenue</b>\n7 Days: {money(rev_7['s'])}\n30 Days: {money(rev_30['s'])}\n\n"
    body += "🏆 <b>Top Products by Sales</b>\n"
    for p in top_prods:
        avg = (p["rating_sum"] / p["rating_count"]) if p["rating_count"] else 0
        bar = progress_bar(p["sold"], max(top_prods[0]["sold"], 1))
        body += f"• {esc(p['name'][:22])}: {bar} {p['sold']} sold"
        if avg:
            body += f" {stars(avg)}"
        body += "\n"

    body += f"\n📊 <b>Order Status</b>\n"
    for s in statuses:
        body += f"• {status_badge(s['status'])}: {s['n']}\n"

    body += f"\n👥 <b>New Users (7 days):</b> {u_week['n']}"

    await safe_edit(call.message, card("📈 Analytics", body), reply_markup=kb([[btn("⬅️ Admin Home", "admin:home")]]))
    await call.answer()

# ═══════════════════════════════════════════════════════════════
#  ADMIN — CATEGORIES
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:cats")
async def admin_cats(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    cats = await db.fetchall("SELECT * FROM categories ORDER BY sort_order, created_at DESC")
    body = "Current categories:\n\n"
    for c in cats:
        cnt = await db.fetchone("SELECT COUNT(*) n FROM products WHERE category_id=? AND active=1", (c["id"],))
        body += f"{c['emoji']} <b>{esc(c['name'])}</b> — {cnt['n']} products {'✅' if c['active'] else '🚫'}\n"
    if not cats:
        body = "No categories yet."
    rows = [[btn("➕ Add Category", "admin:cat:add")]]
    for c in cats[:8]:
        rows.append([
            btn((f"🚫 Hide" if c["active"] else "✅ Show"), f"admin:cat:toggle:{c['id']}"),
            btn(f"{c['emoji']} {c['name'][:20]}", f"admin:cat:info:{c['id']}"),
        ])
    rows.append([btn("⬅️ Admin Home", "admin:home")])
    await safe_edit(call.message, card("📁 Category Manager", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data == "admin:cat:add")
async def admin_cat_add(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(AddCategory.name)
    await safe_edit(call.message, card("➕ New Category", "Send category name:\n\nExample: Netflix Accounts"), reply_markup=cancel_kb())
    await call.answer()


@router.message(AddCategory.name)
async def cat_name_recv(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddCategory.emoji)
    await message.answer(card("➕ Category Emoji", "Send an emoji for this category:\n\nExample: 🎬 📱 🎮 💻 🎵"), reply_markup=cancel_kb())


@router.message(AddCategory.emoji)
async def cat_emoji_recv(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    emoji = message.text.strip()[:2] or "📦"
    cid = code("CAT")
    await db.execute("INSERT INTO categories(id,name,emoji,created_at) VALUES(?,?,?,?)", (cid, data["name"], emoji, now()))
    await state.clear()
    await message.answer(card("✅ Category Added", f"{emoji} <b>{esc(data['name'])}</b>\nID: <code>{cid}</code>"), reply_markup=admin_home_kb())


@router.callback_query(F.data.startswith("admin:cat:toggle:"))
async def cat_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    cid = call.data.split(":")[-1]
    await db.execute("UPDATE categories SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (cid,))
    await admin_cats(call)

# ═══════════════════════════════════════════════════════════════
#  ADMIN — PRODUCTS
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:products")
async def admin_products(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    prods = await db.fetchall(
        "SELECT p.*, c.name cat FROM products p LEFT JOIN categories c ON c.id=p.category_id ORDER BY p.created_at DESC LIMIT 20"
    )
    body = ""
    for p in prods:
        sc = ""
        if p["delivery_mode"] == "STOCK":
            sc_row = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE product_id=? AND used=0", (p["id"],))
            n = sc_row["n"] if sc_row else 0
            sc = f" [{n} stock{'⚠️' if n <= LOW_STOCK else ''}]"
        feat = "⭐ " if p["featured"] else ""
        body += f"{feat}<code>{p['id']}</code> | {esc(p['name'][:20])} | {money(p['price'])}{sc} {'✅' if p['active'] else '🚫'}\n"
    if not body:
        body = "No products yet."

    rows = [[btn("➕ Add Product Wizard", "admin:prod:add")]]
    for p in prods[:8]:
        rows.append([
            btn("⭐" if not p["featured"] else "☆", f"admin:prod:feat:{p['id']}"),
            btn(f"{p['name'][:18]}", f"admin:prod:view:{p['id']}"),
            btn("✅" if p["active"] else "🚫", f"admin:prod:toggle:{p['id']}"),
        ])
    rows.append([btn("⬅️ Admin Home", "admin:home")])
    await safe_edit(call.message, card("🛒 Product Manager", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("admin:prod:view:"))
async def admin_prod_view(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    pid = call.data.split(":")[-1]
    p = await db.fetchone("SELECT p.*, c.name cat FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.id=?", (pid,))
    if not p: return await call.answer("Not found.", show_alert=True)
    sc = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE product_id=? AND used=0", (pid,))
    avg = (p["rating_sum"] / p["rating_count"]) if p["rating_count"] else 0
    body = (
        f"<b>{esc(p['name'])}</b>\n"
        f"Category: {esc(p['cat'])}\n"
        f"Price: {money(p['price'])}\n"
        f"Mode: {p['delivery_mode']}\n"
        f"Stock: {sc['n'] if sc else 0}\n"
        f"Sold: {p['sold']}\n"
        f"Rating: {stars(avg)} ({p['rating_count']} reviews)\n"
        f"Featured: {'✅' if p['featured'] else '❌'}\n"
        f"Active: {'✅' if p['active'] else '🚫'}\n\n"
        f"Description:\n{esc(p['description'])}"
    )
    rows = [
        [btn("✏️ Edit Name", f"edit:name:{pid}"), btn("✏️ Edit Price", f"edit:price:{pid}")],
        [btn("✏️ Edit Desc", f"edit:desc:{pid}"), btn("➕ Add Stock", f"stock:add:{pid}")],
        [btn("⬅️ Products", "admin:products")]
    ]
    await safe_edit(call.message, card("🛒 Product Detail", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("edit:"))
async def edit_product_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    parts = call.data.split(":")
    field, pid = parts[1], parts[2]
    await state.set_state(EditProduct.value)
    await state.update_data(field=field, product_id=pid)
    labels = {"name": "product name", "price": "new price (number only)", "desc": "new description"}
    await safe_edit(call.message, card(f"✏️ Edit {field.title()}", f"Send the new {labels.get(field, field)}:"), reply_markup=cancel_kb())
    await call.answer()


@router.message(EditProduct.value)
async def edit_product_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    field, pid = data["field"], data["product_id"]
    col = {"name": "name", "price": "price", "desc": "description"}[field]
    val = message.text.strip()
    if field == "price":
        try:
            val = float(val)
        except ValueError:
            return await message.answer("❌ Price must be a number.")
    await db.execute(f"UPDATE products SET {col}=? WHERE id=?", (val, pid))
    await state.clear()
    await message.answer(card("✅ Updated", f"Product {field} updated."), reply_markup=admin_home_kb())


@router.callback_query(F.data.startswith("admin:prod:feat:"))
async def prod_feat(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    pid = call.data.split(":")[-1]
    await db.execute("UPDATE products SET featured=CASE featured WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (pid,))
    await admin_products(call)


@router.callback_query(F.data.startswith("admin:prod:toggle:"))
async def prod_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    pid = call.data.split(":")[-1]
    await db.execute("UPDATE products SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (pid,))
    await admin_products(call)


# Product Add Wizard
@router.callback_query(F.data == "admin:prod:add")
async def prod_add(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(AddProduct.name)
    await safe_edit(call.message, card("➕ Add Product (1/6)", "Send product name:"), reply_markup=cancel_kb())
    await call.answer()


@router.message(AddProduct.name)
async def prod_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddProduct.price)
    await message.answer(card("💰 Price (2/6)", "Send selling price (number only):\nExample: 150"), reply_markup=cancel_kb())


@router.message(AddProduct.price)
async def prod_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip())
    except Exception:
        return await message.answer("❌ Enter a valid number only.")
    await state.update_data(price=price)
    await state.set_state(AddProduct.orig_price)
    await message.answer(card("🏷 Original Price (3/6)", "Send original/MRP price (for showing discount).\nSend 0 to skip:"), reply_markup=cancel_kb())


@router.message(AddProduct.orig_price)
async def prod_orig(message: Message, state: FSMContext):
    try:
        orig = float(message.text.strip())
    except Exception:
        orig = 0
    await state.update_data(orig_price=orig)
    cats = await db.fetchall("SELECT * FROM categories WHERE active=1")
    if not cats:
        await state.clear()
        return await message.answer(card("❌ No Categories", "Add a category first!"), reply_markup=admin_home_kb())
    await state.set_state(AddProduct.category)
    rows = [[btn(f"{c['emoji']} {c['name']}", f"prodcat:{c['id']}")] for c in cats]
    rows.append([btn("❌ Cancel", "state:cancel")])
    await message.answer(card("📁 Category (4/6)", "Choose category:"), reply_markup=kb(rows))


@router.callback_query(AddProduct.category, F.data.startswith("prodcat:"))
async def prod_cat(call: CallbackQuery, state: FSMContext):
    await state.update_data(category_id=call.data.split(":", 1)[1])
    await state.set_state(AddProduct.mode)
    await safe_edit(call.message, card("🚚 Delivery Mode (5/6)",
        "<b>STOCK</b> → Deliver account/code from stock list\n"
        "<b>AUTO_CODE</b> → Bot generates unique code\n"
        "<b>MANUAL</b> → Admin delivers manually after approval"
    ), reply_markup=kb([
        [btn("🔐 STOCK (Accounts/Codes)", "prodmode:STOCK")],
        [btn("🤖 AUTO_CODE (Generated)", "prodmode:AUTO_CODE")],
        [btn("🧑‍💻 MANUAL (Admin Delivers)", "prodmode:MANUAL")],
        [btn("❌ Cancel", "state:cancel")]
    ]))
    await call.answer()


@router.callback_query(AddProduct.mode, F.data.startswith("prodmode:"))
async def prod_mode(call: CallbackQuery, state: FSMContext):
    await state.update_data(delivery_mode=call.data.split(":", 1)[1])
    await state.set_state(AddProduct.desc)
    await safe_edit(call.message, card("📝 Description (6/6)", "Send product description:"), reply_markup=cancel_kb())
    await call.answer()


@router.message(AddProduct.desc)
async def prod_save(message: Message, state: FSMContext):
    data = await state.get_data()
    pid = code("PRD")
    await db.execute(
        "INSERT INTO products(id,category_id,name,price,original_price,description,delivery_mode,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (pid, data["category_id"], data["name"], data["price"], data.get("orig_price", 0), message.text.strip(), data["delivery_mode"], now())
    )
    await state.clear()
    await message.answer(card("✅ Product Added!",
        f"📦 <b>{esc(data['name'])}</b>\n"
        f"💰 Price: {money(data['price'])}\n"
        f"🚚 Mode: {data['delivery_mode']}\n"
        f"🆔 ID: <code>{pid}</code>"
    ), reply_markup=admin_home_kb())

# ═══════════════════════════════════════════════════════════════
#  ADMIN — STOCK
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:stock")
async def admin_stock(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    threshold = await stock_alert_threshold()
    alerts = "ON" if await stock_alert_enabled() else "OFF"
    prods = await db.fetchall("SELECT p.*, (SELECT COUNT(*) FROM stock WHERE product_id=p.id AND used=0) AS avail FROM products p ORDER BY p.created_at DESC LIMIT 20")
    body = f"🔔 Alerts: <b>{alerts}</b>  |  ⚠️ Low limit: <b>{threshold}</b>\n\n"
    for p in prods:
        if p["delivery_mode"] != "STOCK":
            warn = "🤖"
        elif int(p["avail"] or 0) == 0:
            warn = "🚫"
        elif int(p["avail"] or 0) <= threshold:
            warn = "⚠️"
        else:
            warn = "✅"
        body += f"{warn} {esc(p['name'][:24])} — Stock: <b>{p['avail']}</b>\n"
    rows = [[btn(f"{'🚫' if (p['delivery_mode']=='STOCK' and int(p['avail'] or 0)==0) else '⚠️' if (p['delivery_mode']=='STOCK' and int(p['avail'] or 0)<=threshold) else '📦'} {p['name'][:24]} [{p['avail']}]", f"stock:add:{p['id']}")] for p in prods]
    rows.append([btn("⚙️ Stock Alert Settings", "admin:stockalerts")])
    rows.append([btn("⬅️ Admin Home", "admin:home")])
    await safe_edit(call.message, card("🔐 Stock Manager", body or "No products."), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data == "admin:stockalerts")
async def admin_stock_alerts(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    threshold = await stock_alert_threshold()
    master = "ON ✅" if await stock_alert_enabled() else "OFF ❌"
    added = "ON ✅" if await stock_alert_enabled("added") else "OFF ❌"
    low = "ON ✅" if await stock_alert_enabled("low") else "OFF ❌"
    out = "ON ✅" if await stock_alert_enabled("out") else "OFF ❌"
    body = (
        f"🔔 Master Alert: <b>{master}</b>\n"
        f"📈 Stock Added: <b>{added}</b>\n"
        f"⚠️ Low Stock: <b>{low}</b>\n"
        f"🚫 Stock Out: <b>{out}</b>\n"
        f"📦 Low Limit: <b>{threshold}</b>\n\n"
        "Use these buttons to control stock notifications.\n"
        "Low limit examples: 1 / 2 / 3 / 5"
    )
    await safe_edit(call.message, card("⚙️ Stock Alert Settings", body), reply_markup=kb([
        [btn("🔔 Toggle Master", "stockalert:toggle:stock_alerts_enabled")],
        [btn("📈 Toggle Added", "stockalert:toggle:stock_alert_added"), btn("⚠️ Toggle Low", "stockalert:toggle:stock_alert_low_enabled")],
        [btn("🚫 Toggle Out", "stockalert:toggle:stock_alert_out_enabled")],
        [btn("👥 Subscribers", "stockalert:audience:subscribers"), btn("🌍 All Users", "stockalert:audience:all")],
        [btn("Limit 1", "stockalert:limit:1"), btn("Limit 2", "stockalert:limit:2"), btn("Limit 3", "stockalert:limit:3"), btn("Limit 5", "stockalert:limit:5")],
        [btn("🔐 Stock Panel", "admin:stock"), btn("⬅️ Admin Home", "admin:home")]
    ]))
    await call.answer()


@router.callback_query(F.data.startswith("stockalert:toggle:"))
async def stockalert_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    key = call.data.split(":")[-1]
    allowed = {"stock_alerts_enabled", "stock_alert_added", "stock_alert_low_enabled", "stock_alert_out_enabled"}
    if key not in allowed:
        return await call.answer("Invalid setting", show_alert=True)
    current = str(await db.get(key) or "1")
    await db.set(key, "0" if current == "1" else "1")
    await admin_stock_alerts(call)


@router.callback_query(F.data.startswith("stockalert:audience:"))
async def stockalert_audience(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    value = call.data.split(":")[-1]
    if value not in {"subscribers", "all"}:
        return await call.answer("Invalid audience", show_alert=True)
    await db.set("stock_alert_audience", value)
    await admin_stock_alerts(call)


@router.callback_query(F.data.startswith("stockalert:limit:"))
async def stockalert_limit(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    value = max(0, int(call.data.split(":")[-1]))
    await db.set("stock_alert_low", str(value))
    await admin_stock_alerts(call)


@router.callback_query(F.data.startswith("stock:add:"))
async def stock_add(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    pid = call.data.split(":")[-1]
    p = await db.fetchone("SELECT * FROM products WHERE id=?", (pid,))
    sc = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE product_id=? AND used=0", (pid,))
    await state.set_state(AddStock.lines)
    await state.update_data(product_id=pid)
    await safe_edit(call.message, card("🔐 Add Stock",
        f"Product: <b>{esc(p['name'])}</b>\n"
        f"Current stock: {sc['n']}\n\n"
        "Paste account/code lines (one per line):\n\n"
        "<code>email@example.com:password\nCODE-ABCD-1234\nLicense: XXXXX</code>"
    ), reply_markup=cancel_kb())
    await call.answer()


@router.message(AddStock.lines)
async def stock_save(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    pid = data["product_id"]
    lines_ = [x.strip() for x in message.text.splitlines() if x.strip()]
    if not lines_:
        return await message.answer("Send at least one line.")
    for x in lines_:
        await db.conn.execute("INSERT INTO stock(id,product_id,content,created_at) VALUES(?,?,?,?)", (code("STK"), pid, x, now()))
    await db.conn.commit()
    await state.clear()
    p = await db.fetchone("SELECT name FROM products WHERE id=?", (pid,))
    sc = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE product_id=? AND used=0", (pid,))
    body = (
        f"Product: <b>{esc(p['name'] if p else pid)}</b>\n"
        f"Added: <b>{len(lines_)}</b>\n"
        f"Current Stock: <b>{sc['n'] if sc else 0}</b>"
    )
    await message.answer(card("✅ Stock Added", body), reply_markup=admin_home_kb())
    await notify_stock_event(bot, pid, "added", added=len(lines_), actor=message.from_user.first_name or str(message.from_user.id))

# ═══════════════════════════════════════════════════════════════
#  ADMIN — ORDERS
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:orders")
async def admin_orders(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    orders = await db.fetchall(
        "SELECT o.*, p.name, u.username, u.first_name FROM orders o "
        "JOIN products p ON p.id=o.product_id "
        "LEFT JOIN users u ON u.id=o.user_id "
        "WHERE o.status IN ('PENDING','WAITING_PROOF') ORDER BY o.created_at DESC LIMIT 20"
    )
    all_pending = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE status IN ('PENDING','WAITING_PROOF')")

    if not orders:
        return await safe_edit(call.message, card("🧾 Orders", "✅ No pending orders!"), reply_markup=kb([
            [btn("📋 All Orders", "admin:allorders")],
            [btn("⬅️ Admin Home", "admin:home")]
        ]))

    body = f"⏳ <b>{all_pending['n']} pending orders</b>\n\n"
    for o in orders:
        body += f"<code>{o['id']}</code> | {esc(o['name'][:15])} | {money(o['amount'])} | {status_badge(o['status'])}\n"

    rows = [[btn(f"🧾 {o['id']} — {o['status']}", f"admin:order:{o['id']}")] for o in orders]
    rows.append([btn("📋 All Orders", "admin:allorders"), btn("⬅️ Admin Home", "admin:home")])
    await safe_edit(call.message, card("🧾 Pending Orders", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data == "admin:allorders")
async def admin_all_orders(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    orders = await db.fetchall(
        "SELECT o.*, p.name FROM orders o JOIN products p ON p.id=o.product_id ORDER BY o.created_at DESC LIMIT 20"
    )
    body = "\n".join([f"<code>{o['id']}</code> | {esc(o['name'][:15])} | {status_badge(o['status'])}" for o in orders]) or "No orders."
    rows = [[btn(f"📦 {o['id']}", f"admin:order:{o['id']}")] for o in orders]
    rows.append([btn("⬅️ Admin Home", "admin:home")])
    await safe_edit(call.message, card("📋 All Orders (Recent 20)", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("admin:order:"))
async def admin_order_view(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id): return
    oid = call.data.split(":")[-1]
    o = await db.fetchone(
        "SELECT o.*, p.name, p.delivery_mode, u.username, u.first_name FROM orders o "
        "JOIN products p ON p.id=o.product_id LEFT JOIN users u ON u.id=o.user_id WHERE o.id=?",
        (oid,)
    )
    if not o: return await call.answer("Not found.", show_alert=True)

    body = (
        f"🧾 Order: <code>{o['id']}</code>\n"
        f"👤 User: {esc(o['first_name'])} (<code>{o['user_id']}</code>)\n"
        f"🛒 Product: {esc(o['name'])}\n"
        f"💰 Amount: {money(o['amount'])}\n"
        f"🎟 Discount: {money(o['discount'])}\n"
        f"💳 Proof: {'✅ Received' if o['proof_file_id'] else '❌ Not sent'}\n"
        f"📋 Status: {status_badge(o['status'])}\n"
    )
    if o["admin_note"]:
        body += f"📝 Note: {esc(o['admin_note'])}\n"
    if "risk_score" in o.keys() and int(o["risk_score"] or 0) > 0:
        body += f"🛡 Risk: <b>{o['risk_score']}/100</b> — {esc(o['risk_note'])}\n"
    body += f"\n<blockquote>🚚 <b>Timeline</b>\n{await order_timeline(o['id'])}</blockquote>"

    rows = []
    if o["status"] in ("PENDING", "WAITING_PROOF", "PROCESSING"):
        rows += [
            [btn("✅ Approve & Deliver", f"admin:approve:{oid}"), btn("❌ Reject", f"admin:reject:{oid}")],
            [btn("🛠 Mark Processing", f"admin:status:PROCESSING:{oid}"), btn("💸 Refund", f"admin:refund:{oid}")]
        ]
    if o["status"] == "DELIVERED":
        rows.append([btn("🏁 Mark Completed", f"admin:status:COMPLETED:{oid}")])
    rows += [[btn("⬅️ Orders", "admin:orders"), btn("🛡 Fraud", "admin:fraud")]]

    await safe_edit(call.message, card("🧾 Order Control", body), reply_markup=kb(rows))

    # Show proof
    proof = o["proof_file_id"]
    if proof and not str(proof).startswith("TEXT:"):
        try:
            await bot.send_photo(call.from_user.id, proof, caption=f"📸 Proof for {oid}")
        except Exception:
            try:
                await bot.send_document(call.from_user.id, proof, caption=f"📄 Proof for {oid}")
            except Exception:
                pass
    elif proof:
        await bot.send_message(call.from_user.id, card("📝 Text Proof", esc(str(proof)[5:])))
    await call.answer()


async def deliver_order(bot: Bot, oid: str) -> tuple[bool, str]:
    o = await db.fetchone(
        "SELECT o.*, p.name, p.delivery_mode FROM orders o JOIN products p ON p.id=o.product_id WHERE o.id=?",
        (oid,)
    )
    if not o:
        return False, "Order not found"

    qty = max(1, int(o["qty"] or 1))
    delivery = ""
    if str(await db.get("auto_delivery_enabled") or "1") != "1" and o["delivery_mode"] != "MANUAL":
        await db.execute("UPDATE orders SET status='PROCESSING', admin_note=?, updated_at=? WHERE id=?", ("Auto delivery is OFF from V15 plugin control", now(), oid))
        await log_order_event(oid, "PROCESSING", "Auto delivery paused by plugin control", 0)
        return False, "Auto delivery is OFF. Mark processing or enable Vault 2.0 from plugin control."
    if o["delivery_mode"] == "AUTO_CODE":
        codes = [f"{SHOP_NAME.replace(' ', '-').upper()}-{secrets.token_hex(6).upper()}" for _ in range(qty)]
        delivery = "\n".join(codes)
    elif o["delivery_mode"] == "MANUAL":
        delivery = "✅ Your order is approved! Admin will deliver manually. Please wait or contact support."
    else:
        stocks = await db.fetchall("SELECT * FROM stock WHERE product_id=? AND used=0 ORDER BY created_at ASC LIMIT ?", (o["product_id"], qty))
        if len(stocks) < qty:
            return False, f"⚠️ Only {len(stocks)} stock item(s) available, but order needs {qty}. Add stock first."
        delivery_lines = []
        for idx, st in enumerate(stocks, start=1):
            delivery_lines.append(f"{idx}. {st['content']}")
            await db.execute("UPDATE stock SET used=1, order_id=?, used_at=? WHERE id=?", (oid, now(), st["id"]))
        delivery = "\n".join(delivery_lines)

    await db.execute("UPDATE orders SET status='DELIVERED', delivered_text=?, updated_at=? WHERE id=?", (delivery, now(), oid))
    await log_order_event(oid, "DELIVERED", "Order approved and delivered", 0)
    await db.execute("UPDATE products SET sold=sold+? WHERE id=?", (qty, o["product_id"]))
    await db.execute("UPDATE users SET orders_count=orders_count+1, total_spent=total_spent+? WHERE id=?", (o["amount"], o["user_id"]))

    # Check VIP upgrade
    await db.check_vip(o["user_id"])

    msg = card(
        "✅ Order Delivered!",
        f"🧾 Order: <code>{oid}</code>\n"
        f"🛒 Product: {esc(o['name'])}\n"
        f"📦 Quantity: <b>{qty}</b> item(s)\n\n"
        f"<blockquote>📦 <b>Your Delivery</b>\n{esc(delivery)}</blockquote>",
        f"⭐ Rate your experience using My Orders. Support: @{SUPPORT_USER}"
    )
    try:
        await bot.send_message(o["user_id"], msg, reply_markup=kb([[btn("⭐ Rate Order", f"rate:{oid}")]]))
    except Exception:
        pass

    # Advanced stock alert after delivery
    if o["delivery_mode"] == "STOCK":
        rem = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE product_id=? AND used=0", (o["product_id"],))
        remaining = int(rem["n"] if rem else 0)
        if remaining == 0:
            await notify_stock_event(bot, o["product_id"], "out", actor="Auto Delivery")
        elif remaining <= await stock_alert_threshold():
            await notify_stock_event(bot, o["product_id"], "low", actor="Auto Delivery")

    try:
        await v14_super_alert(bot, "new_order", "Order Delivered", f"Order delivered successfully.", user_id=o["user_id"], order_id=oid)
    except Exception:
        pass
    return True, "Delivered successfully!"


@router.callback_query(F.data.startswith("admin:approve:"))
async def admin_approve(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id): return
    oid = call.data.split(":")[-1]
    ok, msg = await deliver_order(bot, oid)
    await call.answer(msg, show_alert=True)
    if ok:
        await admin_orders(call)


@router.callback_query(F.data.startswith("admin:reject:"))
async def admin_reject(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    oid = call.data.split(":")[-1]
    await state.set_state(TextEdit.reject_reason)
    await state.update_data(reject_order_id=oid)
    await safe_edit(call.message, card("❌ Reject Order", f"Order: <code>{oid}</code>\n\nSend rejection reason:"), reply_markup=cancel_kb())
    await call.answer()


@router.message(TextEdit.reject_reason)
async def admin_reject_save(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    oid = data["reject_order_id"]
    o = await db.fetchone("SELECT * FROM orders WHERE id=?", (oid,))
    await db.execute("UPDATE orders SET status='REJECTED', admin_note=?, updated_at=? WHERE id=?", (message.text, now(), oid))
    await log_order_event(oid, "REJECTED", message.text, message.from_user.id)
    await state.clear()
    if o:
        try:
            await bot.send_message(o["user_id"], card("❌ Order Rejected",
                f"Order: <code>{oid}</code>\n"
                f"Reason: {esc(message.text)}\n\n"
                "Contact support if you have questions."
            ))
        except Exception:
            pass
    await message.answer(card("✅ Rejected", f"Order <code>{oid}</code> rejected."), reply_markup=admin_home_kb())


@router.callback_query(F.data.startswith("admin:refund:"))
async def admin_refund(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id): return
    oid = call.data.split(":")[-1]
    o = await db.fetchone("SELECT * FROM orders WHERE id=?", (oid,))
    if not o: return await call.answer("Not found.", show_alert=True)
    amount = o["amount"]
    await db.wallet_add(o["user_id"], amount, "REFUND", f"Refund for order {oid}")
    await db.execute("UPDATE orders SET status='REFUNDED', updated_at=? WHERE id=?", (now(), oid))
    await log_order_event(oid, "REFUNDED", f"Refunded {money(amount)} to wallet", call.from_user.id)
    try:
        await bot.send_message(o["user_id"], card("💸 Refund Processed", f"Order <code>{oid}</code>\nAmount {money(amount)} added to your wallet."))
    except Exception:
        pass
    await call.answer(f"Refunded {money(amount)} to user's wallet.", show_alert=True)
    await admin_orders(call)

# ═══════════════════════════════════════════════════════════════
#  ADMIN — SETTINGS
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data.in_({"admin:setpay", "admin:setnotice", "admin:setpolicy"}))
async def admin_set_text(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    key_map = {"admin:setpay": "payment", "admin:setnotice": "notice", "admin:setpolicy": "policy"}
    title_map = {"admin:setpay": "💳 Edit Payment Text", "admin:setnotice": "📢 Edit Notice", "admin:setpolicy": "📜 Edit Policy"}
    s = key_map[call.data]
    await state.set_state(getattr(TextEdit, s))
    await safe_edit(call.message, card(title_map[call.data], "Send new text (HTML tags allowed):"), reply_markup=cancel_kb())
    await call.answer()


@router.message(TextEdit.payment)
async def save_payment(message: Message, state: FSMContext):
    await db.set("payment_text", message.html_text)
    await state.clear()
    await message.answer(card("✅ Updated", "Payment text saved."), reply_markup=admin_home_kb())


@router.message(TextEdit.notice)
async def save_notice(message: Message, state: FSMContext):
    await db.set("notice", message.html_text)
    await state.clear()
    await message.answer(card("✅ Updated", "Notice saved."), reply_markup=admin_home_kb())


@router.message(TextEdit.policy)
async def save_policy(message: Message, state: FSMContext):
    await db.set("policy", message.html_text)
    await state.clear()
    await message.answer(card("✅ Updated", "Policy saved."), reply_markup=admin_home_kb())


@router.callback_query(F.data == "admin:maintenance")
async def maintenance_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    new = "0" if await db.get("maintenance") == "1" else "1"
    await db.set("maintenance", new)
    status = "🔴 ON — Shop is offline for users" if new == "1" else "🟢 OFF — Shop is live"
    await safe_edit(call.message, card("🛠 Maintenance Mode", f"Status: <b>{status}</b>"), reply_markup=admin_home_kb())
    await call.answer(f"Maintenance {'enabled' if new=='1' else 'disabled'}.")

# ═══════════════════════════════════════════════════════════════
#  ADMIN — COUPONS
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:coupons")
async def admin_coupons(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    coupons = await db.fetchall("SELECT * FROM coupons ORDER BY created_at DESC LIMIT 10")
    body = ""
    for c in coupons:
        exp = f" (expires {time.strftime('%d-%m-%Y', time.gmtime(c['expires_at']))})" if c["expires_at"] else ""
        body += f"<code>{c['code']}</code> — {c['value']}{'%' if c['discount_type']=='percent' else ' '+CURRENCY} — Used: {c['used']}/{c['max_uses']}{'💎' if c['vip_only'] else ''}{exp} {'✅' if c['active'] else '🚫'}\n"
    if not body:
        body = "No coupons yet."

    rows = [
        [btn("➕ Create Coupon", "admin:coupon:create")],
        [btn("⬅️ Admin Home", "admin:home")]
    ]
    await safe_edit(call.message, card("🎟 Coupon Manager", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data == "admin:coupon:create")
async def coupon_create_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(TextEdit.coupon_value)
    await safe_edit(call.message, card("🎟 Create Coupon",
        "Send coupon details in this format:\n\n"
        "<code>CODE | type | value | max_uses | vip_only</code>\n\n"
        "<b>type</b>: percent or fixed\n"
        "<b>vip_only</b>: 1 or 0\n\n"
        "Example:\n<code>SAVE20 | percent | 20 | 50 | 0</code>\n"
        "<code>VIP50 | fixed | 50 | 10 | 1</code>"
    ), reply_markup=cancel_kb())
    await call.answer()


@router.message(TextEdit.coupon_value)
async def coupon_save(message: Message, state: FSMContext):
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) < 4 or parts[1] not in ("percent", "fixed"):
        return await message.answer("❌ Wrong format. Example: CODE | percent | 20 | 50 | 0")
    vip_only = int(parts[4]) if len(parts) > 4 else 0
    await db.execute(
        "INSERT OR REPLACE INTO coupons(code,discount_type,value,max_uses,vip_only,created_at) VALUES(?,?,?,?,?,?)",
        (parts[0].upper(), parts[1], float(parts[2]), int(parts[3]), vip_only, now())
    )
    await state.clear()
    await message.answer(card("✅ Coupon Created", f"Code: <code>{parts[0].upper()}</code>\nDiscount: {parts[2]}{'%' if parts[1]=='percent' else ' '+CURRENCY}"), reply_markup=admin_home_kb())

# ═══════════════════════════════════════════════════════════════
#  ADMIN — TICKETS
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:tickets")
async def admin_tickets(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    ts = await db.fetchall(
        "SELECT t.*, u.first_name FROM tickets t LEFT JOIN users u ON u.id=t.user_id WHERE t.status='OPEN' ORDER BY t.created_at DESC LIMIT 15"
    )
    if not ts:
        return await safe_edit(call.message, card("🎫 Tickets", "✅ No open tickets!"), reply_markup=kb([[btn("⬅️ Admin Home", "admin:home")]]))
    body = f"📬 <b>{len(ts)} open tickets</b>\n\n"
    for t in ts:
        body += f"<code>{t['id']}</code> — {esc(t['first_name'])} (<code>{t['user_id']}</code>)\n{esc(t['message'][:80])}...\n\n"
    rows = [[btn(f"🎫 {t['id']} — {esc(t['first_name'])}", f"ticket:reply:{t['id']}")] for t in ts]
    rows.append([btn("⬅️ Admin Home", "admin:home")])
    await safe_edit(call.message, card("🎫 Open Tickets", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("ticket:reply:"))
async def ticket_reply(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    tid = call.data.split(":")[-1]
    t = await db.fetchone("SELECT * FROM tickets WHERE id=?", (tid,))
    await state.set_state(TextEdit.ticket_reply)
    await state.update_data(ticket_id=tid)
    await safe_edit(call.message, card("🎫 Reply Ticket",
        f"Ticket: <code>{tid}</code>\nUser: <code>{t['user_id']}</code>\n\n"
        f"<b>Message:</b>\n{esc(t['message'])}\n\nSend your reply:"
    ), reply_markup=cancel_kb())
    await call.answer()


@router.message(TextEdit.ticket_reply)
async def ticket_reply_save(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    tid = data["ticket_id"]
    t = await db.fetchone("SELECT * FROM tickets WHERE id=?", (tid,))
    await db.execute("UPDATE tickets SET status='CLOSED', reply=?, updated_at=? WHERE id=?", (message.text, now(), tid))
    await state.clear()
    if t:
        try:
            await bot.send_message(t["user_id"], card("🎫 Support Reply",
                f"Ticket: <code>{tid}</code>\n\n"
                f"📝 Admin Reply:\n{esc(message.text)}"
            ), reply_markup=main_menu(t["user_id"]))
        except Exception:
            pass
    await message.answer(card("✅ Reply Sent", f"Ticket <code>{tid}</code> closed."), reply_markup=admin_home_kb())

# ═══════════════════════════════════════════════════════════════
#  ADMIN — BROADCAST
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    total = await db.fetchone("SELECT COUNT(*) n FROM users WHERE is_banned=0")
    await state.set_state(TextEdit.broadcast)
    await safe_edit(call.message, card("📣 Broadcast Message",
        f"Send to <b>{total['n']}</b> active users.\n\nSend your message (HTML supported):"
    ), reply_markup=cancel_kb())
    await call.answer()


@router.message(TextEdit.broadcast)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    users = await db.fetchall("SELECT id FROM users WHERE is_banned=0")
    sent = failed = 0
    for u in users:
        try:
            await bot.send_message(u["id"], card("📣 Announcement", message.html_text, SHOP_NAME))
            sent += 1
            await asyncio.sleep(0.05)
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
        except Exception:
            failed += 1
    await message.answer(card("✅ Broadcast Complete", f"✅ Sent: {sent}\n❌ Failed: {failed}"), reply_markup=admin_home_kb())

# ═══════════════════════════════════════════════════════════════
#  ADMIN — USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:users")
async def admin_users(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    total = await db.fetchone("SELECT COUNT(*) n FROM users")
    vips = await db.fetchone("SELECT COUNT(*) n FROM users WHERE role='vip'")
    banned = await db.fetchone("SELECT COUNT(*) n FROM users WHERE is_banned=1")
    recent = await db.fetchall("SELECT * FROM users ORDER BY joined_at DESC LIMIT 5")
    body = (
        f"👥 Total: <b>{total['n']}</b>\n"
        f"💎 VIPs: <b>{vips['n']}</b>\n"
        f"🚫 Banned: <b>{banned['n']}</b>\n\n"
        "Recent users:\n"
    )
    for u in recent:
        body += f"• {esc(u['first_name'])} (<code>{u['id']}</code>) — {role_badge(u['role'])}\n"

    rows = [
        [btn("🚫 Ban User", "admin:banuser"), btn("✅ Unban User", "admin:unbanuser")],
        [btn("💎 Give VIP", "admin:givevip"), btn("👑 Admin Manager", "admin:admins")],
        [btn("💰 Add Wallet", "admin:addwallet:0"), btn("💎 VIP Requests", "admin:vipreqs")],
        [btn("⬅️ Admin Home", "admin:home")]
    ]
    await safe_edit(call.message, card("👥 User Manager", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data == "admin:vipreqs")
async def admin_vip_requests(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    reqs = await db.fetchall("SELECT t.*, u.first_name, u.username FROM tickets t LEFT JOIN users u ON u.id=t.user_id WHERE t.status='OPEN' AND t.message LIKE 'VIP REQUEST:%' ORDER BY t.created_at DESC LIMIT 15")
    if not reqs:
        return await safe_edit(call.message, card("💎 VIP Requests", "✅ No open VIP requests."), reply_markup=kb([[btn("⬅️ Admin Home", "admin:home")]]))
    body = ""
    rows = []
    for r in reqs:
        body += f"<code>{r['id']}</code> — {esc(r['first_name'])} (<code>{r['user_id']}</code>)\n{esc(r['message'].replace('VIP REQUEST:', '').strip()[:90])}\n\n"
        rows.append([btn(f"💎 Grant {r['user_id']}", f"admin:vipgrant:{r['user_id']}"), btn(f"🎫 Reply {r['id']}", f"ticket:reply:{r['id']}")])
    rows.append([btn("⬅️ Admin Home", "admin:home")])
    await safe_edit(call.message, card("💎 VIP Requests", body), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data.startswith("admin:vipgrant:"))
async def quick_grant_vip(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id): return
    uid = int(call.data.split(":")[-1])
    await db.execute("INSERT OR IGNORE INTO users(id,joined_at,role,ref_code) VALUES(?,?,?,?)", (uid, now(), "user", secrets.token_hex(4).upper()))
    await db.execute("UPDATE users SET role='vip', vip_expires=0 WHERE id=?", (uid,))
    await db.execute("UPDATE tickets SET status='CLOSED', reply=?, updated_at=? WHERE user_id=? AND status='OPEN' AND message LIKE 'VIP REQUEST:%'", ("VIP granted by admin", now(), uid))
    try:
        await bot.send_message(uid, card("💎 VIP Activated", "Congratulations! Your VIP membership has been activated.\n\nYou now get VIP discounts and VIP-only coupon access."), reply_markup=main_menu(uid, "vip"))
    except Exception:
        pass
    await call.answer("VIP granted ✅", show_alert=True)
    await admin_vip_requests(call)

@router.callback_query(F.data == "admin:admins")
async def admin_manager(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    rows_db = await db.fetchall("SELECT id, first_name, username, role FROM users WHERE role='admin' ORDER BY joined_at DESC LIMIT 30")
    all_admins = list(dict.fromkeys([*ADMIN_IDS, *DYNAMIC_ADMIN_IDS]))
    body = "👑 <b>Current Admins</b>\n\n"
    shown = set()
    for admin_id in all_admins:
        shown.add(int(admin_id))
        u = await db.get_user(int(admin_id))
        owner = " 🔒 OWNER" if int(admin_id) in ADMIN_IDS else ""
        name = esc(u['first_name']) if u and u['first_name'] else "Unknown / not started"
        body += f"• {name} — <code>{admin_id}</code>{owner}\n"
    for u in rows_db:
        if int(u['id']) not in shown:
            body += f"• {esc(u['first_name'])} — <code>{u['id']}</code>\n"
    rows = [
        [btn("➕ Add Admin", "admin:addadmin"), btn("➖ Remove Admin", "admin:removeadmin")],
        [btn("👥 User Manager", "admin:users"), btn("⬅️ Admin Home", "admin:home")]
    ]
    await safe_edit(call.message, card("👑 Admin Manager", body, "Add/remove admins directly from bot. Owner IDs from .env cannot be removed."), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:addadmin")
async def add_admin_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(AdminRoleState.user_id)
    await state.update_data(action="add_admin")
    await safe_edit(call.message, card("➕ Add Admin", "Send Telegram user ID to make admin. User should start the bot once for full notification support."), reply_markup=cancel_kb())
    await call.answer()

@router.callback_query(F.data == "admin:removeadmin")
async def remove_admin_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(AdminRoleState.user_id)
    await state.update_data(action="remove_admin")
    await safe_edit(call.message, card("➖ Remove Admin", "Send Telegram user ID to remove admin. Owner IDs from .env are protected."), reply_markup=cancel_kb())
    await call.answer()

@router.message(AdminRoleState.user_id)
async def admin_role_save(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    action = data.get("action")
    try:
        uid = int(message.text.strip())
    except ValueError:
        return await message.answer("❌ Invalid user ID. Send numeric Telegram ID only.")
    await state.clear()
    if action == "add_admin":
        await db.execute("INSERT OR IGNORE INTO users(id,joined_at,role,ref_code) VALUES(?,?,?,?)", (uid, now(), "admin", secrets.token_hex(4).upper()))
        await db.execute("UPDATE users SET role='admin', is_banned=0 WHERE id=?", (uid,))
        DYNAMIC_ADMIN_IDS.add(uid)
        try:
            await bot.send_message(uid, card("👑 Admin Access Granted", f"You are now an admin of <b>{esc(SHOP_NAME)}</b>.\nUse /panel to open the admin control center."), reply_markup=admin_home_kb())
        except Exception:
            pass
        await notify_admins(bot, card("👑 Admin Added", f"New admin: <code>{uid}</code>\nAdded by: <code>{message.from_user.id}</code>"), exclude=message.from_user.id)
        return await message.answer(card("✅ Admin Added", f"User <code>{uid}</code> is now admin. Notification sent if the user has started the bot."), reply_markup=admin_home_kb())
    if uid in ADMIN_IDS:
        return await message.answer(card("🔒 Protected Owner", "This admin ID is in .env ADMIN_IDS, so it cannot be removed from the bot panel."), reply_markup=admin_home_kb())
    await db.execute("UPDATE users SET role='user' WHERE id=?", (uid,))
    DYNAMIC_ADMIN_IDS.discard(uid)
    try:
        await bot.send_message(uid, card("⚠️ Admin Access Removed", f"Your admin access for <b>{esc(SHOP_NAME)}</b> has been removed."), reply_markup=main_menu(uid))
    except Exception:
        pass
    await notify_admins(bot, card("⚠️ Admin Removed", f"Removed admin: <code>{uid}</code>\nRemoved by: <code>{message.from_user.id}</code>"), exclude=message.from_user.id)
    await message.answer(card("✅ Admin Removed", f"User <code>{uid}</code> is no longer admin."), reply_markup=admin_home_kb())

@router.callback_query(F.data == "admin:bans")
async def admin_bans(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    await admin_users(call)


@router.callback_query(F.data == "admin:banuser")
async def ban_user(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(UserBanState.user_id)
    await state.update_data(action="ban")
    await safe_edit(call.message, card("🚫 Ban User", "Send user ID to ban:"), reply_markup=cancel_kb())
    await call.answer()


@router.callback_query(F.data == "admin:unbanuser")
async def unban_user(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(UserBanState.user_id)
    await state.update_data(action="unban")
    await safe_edit(call.message, card("✅ Unban User", "Send user ID to unban:"), reply_markup=cancel_kb())
    await call.answer()


@router.message(UserBanState.user_id)
async def do_ban(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    try:
        uid = int(message.text.strip())
    except ValueError:
        return await message.answer("❌ Invalid ID.")
    action = data["action"]
    if action == "ban":
        await db.execute("UPDATE users SET is_banned=1 WHERE id=?", (uid,))
        try:
            await bot.send_message(uid, "🚫 You have been banned from this shop.")
        except Exception:
            pass
        await message.answer(card("✅ Done", f"User <code>{uid}</code> banned."), reply_markup=admin_home_kb())
    else:
        await db.execute("UPDATE users SET is_banned=0 WHERE id=?", (uid,))
        try:
            await bot.send_message(uid, "✅ You have been unbanned. Welcome back!")
        except Exception:
            pass
        await message.answer(card("✅ Done", f"User <code>{uid}</code> unbanned."), reply_markup=admin_home_kb())
    await state.clear()


@router.callback_query(F.data == "admin:givevip")
async def give_vip(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(AdminWalletState.user_id)
    await state.update_data(action="vip")
    await safe_edit(call.message, card("💎 Give VIP", "Send user ID to grant VIP:"), reply_markup=cancel_kb())
    await call.answer()


@router.callback_query(F.data.startswith("admin:creditexact:"))
async def admin_credit_exact(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split(":")
    if len(parts) < 4:
        return await call.answer("Invalid credit request.", show_alert=True)
    uid = int(parts[2])
    amount = round(float(parts[3]), 2)
    if amount <= 0:
        return await call.answer("Invalid amount.", show_alert=True)
    await db.wallet_add(uid, amount, "TOPUP_VERIFIED", f"Exact top-up credited by admin {call.from_user.id}")
    try:
        await bot.send_message(uid, card("✅ Wallet Top-Up Verified", f"Added: <b>{money(amount)}</b>\nYou can now buy products with instant wallet autopay."), reply_markup=main_menu(uid))
    except Exception:
        pass
    await safe_edit(call.message, card("✅ Exact Credit Done", f"User <code>{uid}</code> credited with <b>{money(amount)}</b>."), reply_markup=admin_home_kb())
    await call.answer("Credited ✅")


@router.callback_query(F.data.startswith("admin:addwallet:"))
async def admin_wallet_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    uid_str = call.data.split(":")[-1]
    if uid_str and uid_str != "0":
        await state.update_data(action="wallet", target_uid=int(uid_str))
        await state.set_state(AdminWalletState.amount)
        await safe_edit(call.message, card("💰 Add Wallet Balance", f"Adding balance to user <code>{uid_str}</code>\n\nSend amount:"), reply_markup=cancel_kb())
    else:
        await state.set_state(AdminWalletState.user_id)
        await state.update_data(action="wallet")
        await safe_edit(call.message, card("💰 Add Wallet Balance", "Send user ID:"), reply_markup=cancel_kb())
    await call.answer()


@router.message(AdminWalletState.user_id)
async def admin_wallet_uid(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    try:
        uid = int(message.text.strip())
    except ValueError:
        return await message.answer("❌ Invalid ID.")
    await state.update_data(target_uid=uid)
    data = await state.get_data()
    if data.get("action") == "vip":
        await db.execute("INSERT OR IGNORE INTO users(id,joined_at,role,ref_code) VALUES(?,?,?,?)", (uid, now(), "user", secrets.token_hex(4).upper()))
        await db.execute("UPDATE users SET role='vip', vip_expires=0 WHERE id=?", (uid,))
        await db.execute("UPDATE tickets SET status='CLOSED', reply=?, updated_at=? WHERE user_id=? AND status='OPEN' AND message LIKE 'VIP REQUEST:%'", ("VIP granted by admin", now(), uid))
        await state.clear()
        try:
            await bot.send_message(uid, card("💎 VIP Activated", "Congratulations! Admin activated VIP membership for your account. You can now use VIP discounts and VIP-only coupons."), reply_markup=main_menu(uid, "vip"))
        except Exception:
            pass
        await notify_admins(bot, card("💎 VIP Granted", f"User <code>{uid}</code> got VIP.\nGranted by: <code>{message.from_user.id}</code>"), exclude=message.from_user.id)
        await message.answer(card("✅ VIP Granted", f"User <code>{uid}</code> is now VIP 💎\nNotification sent if the user has started the bot."), reply_markup=admin_home_kb())
    else:
        await state.set_state(AdminWalletState.amount)
        await message.answer(card("💰 Amount", f"Send amount to add to user <code>{uid}</code>:"), reply_markup=cancel_kb())


@router.message(AdminWalletState.amount)
async def admin_wallet_amount(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    try:
        amount = float(message.text.strip())
    except ValueError:
        return await message.answer("❌ Invalid amount.")
    data = await state.get_data()
    uid = data.get("target_uid")
    await db.wallet_add(uid, amount, "ADMIN_CREDIT", "Admin added balance")
    await state.clear()
    try:
        await bot.send_message(uid, card("💰 Wallet Credited!", f"<b>{money(amount)}</b> added to your wallet by admin."))
    except Exception:
        pass
    await message.answer(card("✅ Done", f"Added {money(amount)} to user <code>{uid}</code>"), reply_markup=admin_home_kb())

# ═══════════════════════════════════════════════════════════════
#  ADMIN — WALLET CONFIG
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:walletcfg")
async def wallet_cfg(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    bonus = await db.get("referral_bonus")
    vip_disc = await db.get("vip_discount")
    vip_price = await db.get("vip_price") or "Contact Admin"
    rows = [
        [btn("✏️ Edit Topup Text", "admin:walletcfg:topup")],
        [btn(f"🎁 Referral Bonus: {bonus} {CURRENCY}", "admin:walletcfg:refbonus")],
        [btn(f"💎 VIP Discount: {vip_disc}%", "admin:walletcfg:vipdisc")],
        [btn("📝 Edit VIP Text", "admin:walletcfg:viptext"), btn("💰 VIP Price", "admin:walletcfg:vipprice")],
        [btn("⬅️ Admin Home", "admin:home")]
    ]
    await safe_edit(call.message, card("💰 Wallet & VIP Config",
        f"Referral Bonus: <b>{bonus} {CURRENCY}</b>\nVIP Discount: <b>{vip_disc}%</b>\nVIP Price: <b>{esc(vip_price)}</b>\n\nVIP = auto-upgrade after {VIP_THRESHOLD} orders"
    ), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data == "admin:walletcfg:topup")
async def wallet_topup_edit(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(TextEdit.wallet_topup_text)
    await safe_edit(call.message, card("✏️ Edit Top-Up Text", "Send new wallet top-up instructions:"), reply_markup=cancel_kb())
    await call.answer()


@router.message(TextEdit.wallet_topup_text)
async def save_topup_text(message: Message, state: FSMContext):
    await db.set("wallet_topup_text", message.html_text)
    await state.clear()
    await message.answer(card("✅ Updated", "Wallet top-up text saved."), reply_markup=admin_home_kb())


@router.callback_query(F.data == "admin:walletcfg:refbonus")
async def ref_bonus_edit(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(TextEdit.ref_bonus)
    await safe_edit(call.message, card("🎁 Referral Bonus", "Send new referral bonus amount (number only):"), reply_markup=cancel_kb())
    await call.answer()


@router.message(TextEdit.ref_bonus)
async def save_ref_bonus(message: Message, state: FSMContext):
    try:
        val = float(message.text.strip())
        if val < 0:
            raise ValueError
    except ValueError:
        return await message.answer("❌ Number only. Example: 0.10 or 20")
    clean = (str(int(val)) if val.is_integer() else f"{val:.8f}".rstrip("0").rstrip("."))
    await db.set("referral_bonus", clean)
    await state.clear()
    await message.answer(card("✅ Updated", f"Referral bonus set to {money(val)}"), reply_markup=admin_home_kb())


@router.callback_query(F.data == "admin:walletcfg:vipdisc")
async def vip_disc_edit(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(TextEdit.vip_discount)
    await safe_edit(call.message, card("💎 VIP Discount", "Send VIP discount percentage (0-100):"), reply_markup=cancel_kb())
    await call.answer()


@router.message(TextEdit.vip_discount)
async def save_vip_disc(message: Message, state: FSMContext):
    try:
        val = float(message.text.strip())
    except ValueError:
        return await message.answer("❌ Number only.")
    await db.set("vip_discount", str(val))
    await state.clear()
    await message.answer(card("✅ Updated", f"VIP discount set to {val}%"), reply_markup=admin_home_kb())

@router.callback_query(F.data == "admin:walletcfg:viptext")
async def vip_text_edit(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(TextEdit.vip_text)
    current = await db.get("vip_text")
    await safe_edit(call.message, card("📝 Edit VIP Text", f"Current text:\n\n{current}\n\nSend new VIP information/benefits text:"), reply_markup=cancel_kb())
    await call.answer()

@router.message(TextEdit.vip_text)
async def save_vip_text(message: Message, state: FSMContext):
    await db.set("vip_text", message.html_text)
    await state.clear()
    await message.answer(card("✅ Updated", "VIP user-panel text saved."), reply_markup=admin_home_kb())

@router.callback_query(F.data == "admin:walletcfg:vipprice")
async def vip_price_edit(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(TextEdit.vip_price)
    await safe_edit(call.message, card("💰 VIP Price / Info", "Send VIP price or custom info. Example: 199 BDT / month or Contact admin."), reply_markup=cancel_kb())
    await call.answer()

@router.message(TextEdit.vip_price)
async def save_vip_price(message: Message, state: FSMContext):
    await db.set("vip_price", message.text.strip())
    await state.clear()
    await message.answer(card("✅ Updated", f"VIP price/info set to: <b>{esc(message.text.strip())}</b>"), reply_markup=admin_home_kb())

# ═══════════════════════════════════════════════════════════════
#  ADMIN — BACKUP / EXPORT CENTER
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:backup")
async def backup_db(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    if not os.path.exists(DB_PATH):
        return await call.answer("Database file not found yet.", show_alert=True)
    await call.message.answer_document(FSInputFile(DB_PATH), caption=f"🗄 Database Backup — {SHOP_NAME} — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    await call.answer("Backup sent ✅")

# ═══════════════════════════════════════════════════════════════
#  ADMIN — EXPORT
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:export")
async def export_csv(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    out = f"/tmp/export_{int(time.time())}.csv"
    rows = await db.fetchall(
        "SELECT o.id, o.user_id, u.username, p.name, o.amount, o.discount, o.status, o.coupon_code, o.created_at "
        "FROM orders o JOIN products p ON p.id=o.product_id LEFT JOIN users u ON u.id=o.user_id ORDER BY o.created_at DESC"
    )
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["order_id", "user_id", "username", "product", "amount", "discount", "status", "coupon", "created_at"])
        for r in rows:
            w.writerow([r["id"], r["user_id"], r["username"], r["name"], r["amount"], r["discount"], r["status"], r["coupon_code"], time.strftime('%Y-%m-%d %H:%M', time.gmtime(r["created_at"]))])
    await call.message.answer_document(FSInputFile(out), caption=f"📊 Orders Export — {len(rows)} records")
    try:
        os.remove(out)
    except Exception:
        pass
    await call.answer("Export ready!")


# ═══════════════════════════════════════════════════════════════
#  V22.1 — AI CONCIERGE PRO HELPERS
# ═══════════════════════════════════════════════════════════════

def parse_budget_from_text(query: str) -> Optional[float]:
    """Detect user budget/amount from Bangla/English natural text."""
    text = str(query or "").lower().replace(",", "")
    patterns = [
        r"(?:under|below|within|budget|less than|কম|মধ্যে|ভিতরে|নিচে)\s*(?:৳|tk|taka|bdt|usdt|\$)?\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*(?:৳|tk|taka|bdt|টাকা|usdt|\$)\s*(?:এর মধ্যে|মধ্যে|নিচে|কম|under|below)?",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return parse_amount(m.group(1), 0)
    return None

def ai_intent(query: str) -> str:
    q = str(query or "").lower()
    groups = {
        "track_order": ["order", "track", "status", "delivery", "অর্ডার", "ট্র্যাক", "ডেলিভারি", "স্ট্যাটাস"],
        "wallet": ["wallet", "deposit", "topup", "balance", "bkash", "nagad", "pay", "ওয়ালেট", "ডিপোজিট", "ব্যালেন্স", "পেমেন্ট"],
        "coupon": ["coupon", "promo", "discount", "offer", "কুপন", "ডিসকাউন্ট", "অফার"],
        "vip": ["vip", "premium", "membership", "প্রিমিয়াম", "ভিআইপি"],
        "support": ["support", "help", "problem", "issue", "সাপোর্ট", "সমস্যা", "হেল্প"],
    }
    for intent, words in groups.items():
        if any(w in q for w in words):
            return intent
    return "product_search"

def smart_synonyms(words: Iterable[str]) -> set[str]:
    syn = {
        "netflix": {"netflix", "নেটফ্লিক্স", "ott", "stream"},
        "canva": {"canva", "ক্যানভা", "design"},
        "youtube": {"youtube", "yt", "ইউটিউব", "premium"},
        "spotify": {"spotify", "স্পটিফাই", "music"},
        "gaming": {"game", "gaming", "pubg", "freefire", "ff", "uc", "diamond", "গেম"},
        "facebook": {"facebook", "fb", "ফেসবুক"},
        "instagram": {"instagram", "ig", "ইনস্টা"},
    }
    out = set(words)
    joined = " ".join(words).lower()
    for base, items in syn.items():
        if base in joined or any(x in joined for x in items):
            out |= items
    return {x.lower() for x in out if x}

#  V13 — AI COMMERCE ASSISTANT / ORDER TRACKING / ALERT CENTER
# ═══════════════════════════════════════════════════════════════

COMMON_AI_WORDS = {
    "i", "me", "my", "need", "want", "give", "show", "find", "buy", "price", "cheap",
    "please", "hello", "hi", "bro", "ভাই", "দাও", "চাই", "লাগবে", "কিনতে", "কম", "দাম", "সস্তা",
    "প্রোডাক্ট", "একটা", "আমার", "আমাকে", "মধ্যে", "টাকা", "এর", "টা", "কি", "আছে"
}

async def log_order_event(order_id: str, status: str, note: str = "", actor_id: int = 0):
    try:
        await db.execute(
            "INSERT INTO order_events(id,order_id,status,note,actor_id,created_at) VALUES(?,?,?,?,?,?)",
            (code("EVT"), order_id, status, note[:500], actor_id, now())
        )
    except Exception as e:
        logger.warning("Could not log order event: %s", e)

async def order_timeline(order_id: str) -> str:
    rows = await db.fetchall("SELECT * FROM order_events WHERE order_id=? ORDER BY created_at ASC", (order_id,))
    if not rows:
        return "No timeline event saved yet."
    out = []
    for r in rows[-8:]:
        t = time.strftime('%Y-%m-%d %H:%M', time.localtime(int(r['created_at'] or now())))
        note = f" — {esc(r['note'])}" if r['note'] else ""
        out.append(f"• {t} | <b>{status_badge(r['status'])}</b>{note}")
    return "\n".join(out)

async def calculate_order_risk(uid: int) -> tuple[int, str]:
    if str(await db.get("fraud_guard_enabled") or "1") != "1":
        return 0, "Fraud Guard disabled"
    limit = int(parse_amount(await db.get("fraud_order_limit") or "3", 3))
    window_min = int(parse_amount(await db.get("fraud_window_min") or "10", 10))
    since = now() - window_min * 60
    recent = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE user_id=? AND created_at>=?", (uid, since))
    unpaid = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE user_id=? AND status IN ('WAITING_PROOF','PENDING','PROCESSING')", (uid,))
    rejected = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE user_id=? AND status='REJECTED' AND created_at>=?", (uid, now() - 24*3600))
    wallet = await db.fetchone("SELECT wallet,total_spent,orders_count FROM users WHERE id=?", (uid,))
    score = 0
    reasons = []
    if recent and recent['n'] > limit:
        score += 50
        reasons.append(f"{recent['n']} orders in {window_min} min")
    if unpaid and unpaid['n'] >= 3:
        score += 25
        reasons.append(f"{unpaid['n']} active unpaid/pending orders")
    if rejected and rejected['n'] >= 2:
        score += 25
        reasons.append(f"{rejected['n']} rejected orders in 24h")
    if wallet and float(wallet['total_spent'] or 0) == 0 and int(wallet['orders_count'] or 0) == 0 and unpaid and unpaid['n'] >= 2:
        score += 10
        reasons.append("new buyer with multiple pending orders")
    return min(score, 100), "; ".join(reasons) or "Normal activity"

async def maybe_flag_order(bot: Bot, uid: int, order_id: str):
    score, reason = await calculate_order_risk(uid)
    if score < 50:
        return
    await db.execute("UPDATE orders SET risk_score=?, risk_note=? WHERE id=?", (score, reason, order_id))
    await db.execute(
        "INSERT INTO fraud_flags(id,user_id,order_id,score,reason,created_at) VALUES(?,?,?,?,?,?)",
        (code("FRD"), uid, order_id, score, reason, now())
    )
    await notify_admins(bot, card("🛡 Fraud Guard Alert", f"User: <code>{uid}</code>\nOrder: <code>{order_id}</code>\nRisk: <b>{score}/100</b>\nReason: {esc(reason)}"), reply_markup=kb([[btn("🧾 Open Orders", "admin:orders"), btn("🛡 Fraud Panel", "admin:fraud")]]))

async def smart_product_matches(query: str, limit: int = 6):
    raw_words = [w.strip().lower() for w in re.split(r"[\s/\-_,.]+", query or "")]
    words = [w for w in raw_words if w and w not in COMMON_AI_WORDS]
    words = list(smart_synonyms(words))
    budget = parse_budget_from_text(query) if str(await db.get("ai_budget_parser_enabled") or "1") == "1" else None
    rows = await db.fetchall(
        "SELECT p.*, c.name cat, c.emoji emoji, (SELECT COUNT(*) FROM stock WHERE product_id=p.id AND used=0) AS avail "
        "FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1 ORDER BY p.featured DESC, p.sold DESC, p.created_at DESC LIMIT 250"
    )
    scored = []
    ql = query.lower()
    cheap_hint = any(x in ql for x in ["cheap", "low", "budget", "under", "below", "কম", "সস্তা", "নিম্ন", "মধ্যে"]) or budget is not None
    vip_hint = any(x in ql for x in ["vip", "premium", "প্রিমিয়াম", "ভিআইপি"])
    stock_hint = any(x in ql for x in ["stock", "available", "আছে", "স্টক"])
    for p in rows:
        text = f"{p['name']} {p['description'] or ''} {p['cat'] or ''}".lower()
        score = 0
        price = float(p['price'] or 0)
        avail = int(p['avail'] or 0)
        if p['featured']:
            score += 5
        if p['sold']:
            score += min(8, int(p['sold'] or 0))
        for w in words:
            if len(w) < 2:
                continue
            if w in text:
                score += 16 if w in str(p['name']).lower() else 9
        if budget is not None:
            if price <= budget:
                score += 18
                # Prefer products close to budget but not over it.
                score += max(0, int(8 - abs(budget - price) / max(budget, 1) * 8))
            else:
                score -= 20
        elif cheap_hint and price <= 200:
            score += 8
        if vip_hint and p['featured']:
            score += 5
        if stock_hint and (p['delivery_mode'] != 'STOCK' or avail > 0):
            score += 7
        if p['delivery_mode'] == 'STOCK' and avail <= 0:
            score -= 10
        if not words and (cheap_hint or vip_hint or stock_hint):
            score += 1
        if score > 0:
            scored.append((score, p))
    if cheap_hint:
        scored.sort(key=lambda x: (-x[0], float(x[1]['price'] or 0), -int(x[1]['sold'] or 0)))
    else:
        scored.sort(key=lambda x: (-x[0], -int(x[1]['featured'] or 0), -int(x[1]['sold'] or 0)))
    return [p for _, p in scored[:limit]]

async def ai_answer_for(uid: int, query: str) -> tuple[str, InlineKeyboardMarkup]:
    ql = query.lower().strip()
    intent = ai_intent(query)
    budget = parse_budget_from_text(query)
    if intent == "track_order":
        rows = await db.fetchall("SELECT id,status,created_at FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (uid,))
        if rows:
            body = neon_card("🚚 Order Intelligence", "I found your latest order activity", [f"🧾 <code>{r['id']}</code> — <b>{status_badge(r['status'])}</b>" for r in rows], "Tap an order to open live tracking")
            return body, kb([[btn(f"🚚 Track {r['id']}", f"order:view:{r['id']}")] for r in rows] + [[btn("🏠 Home", "menu:main")]])
        return neon_card("🚚 Order Intelligence", "No order found yet", ["🛍 Browse products", "🧠 Ask AI for a product suggestion", "🛟 Open support if you expected an order"], "I can track once an order is created"), kb([[btn("🛍 Shop", "shop:cats"), btn("🏠 Home", "menu:main")]])
    if intent == "wallet":
        txt = preview_text(await db.get("wallet_topup_text"), max_lines=7, max_chars=450)
        return neon_card("💳 Wallet Assistant", "Wallet payment is the fastest verified payment inside the bot", ["✅ Wallet balance is verified from the bot ledger", "📦 Wallet purchases can auto-deliver stock", f"📌 {esc(txt)}"], "Use Deposit to add balance"), kb([[btn("💳 Deposit Now", "wallet:topup"), btn("👤 Profile", "profile:me")], [btn("🏠 Home", "menu:main")]])
    if intent == "coupon":
        return neon_card("🎟 Coupon Assistant", "I can help you use offers correctly", ["🎟 Apply coupon during checkout", "🎁 Redeem code can unlock wallet/VIP/product", "🔥 Hot deals may support discounts"], "Tap Coupon or Hot Deals"), kb([[btn("🎟 Coupon", "coupon:ask"), btn("🔥 Hot Deals", "shop:hot")], [btn("🏠 Home", "menu:main")]])
    if intent == "vip":
        txt = preview_text(await db.get("vip_benefits"), max_lines=7, max_chars=500)
        return neon_card("💎 VIP Concierge", "Premium buyer benefits and priority support", [f"{esc(txt)}"], "Open plans to request VIP"), kb([[btn("💎 VIP Plans", "vip:plans"), btn("🎁 VIP Benefits", "vip:benefits")], [btn("🏠 Home", "menu:main")]])
    if intent == "support":
        return neon_card("🛟 Support Concierge", "Tell us the order ID, payment issue or product name", ["🎫 Ticket flow keeps your issue organized", "🚚 Order tracking is available", "💳 Payment proof can be reviewed by admin"], "Open a ticket for human admin help"), kb([[btn("🛟 Open Ticket", "ticket:new"), btn("🚚 Track Order", "track:ask")], [btn("🏠 Home", "menu:main")]])

    matches = await smart_product_matches(query)
    await db.execute("INSERT INTO ai_logs(id,user_id,query,matched,created_at) VALUES(?,?,?,?,?)", (code("AIL"), uid, query[:500], ",".join([m['id'] for m in matches]), now()))
    if not matches:
        no_result = await db.get("ai_no_result_text") or "I could not find a perfect match. Try product name, budget, category, or open Support Ticket."
        lines = [
            f"📝 Your request: <i>{esc(preview_text(query, max_lines=1, max_chars=90))}</i>",
            f"🔎 Result: {esc(no_result)}",
            "💡 Try: ‘২০০ টাকার মধ্যে Netflix’, ‘cheap Canva’, ‘gaming account stock’",
        ]
        return neon_card("🧠 AI Concierge Max", "No perfect match yet", lines, "I searched products, price hints and stock data"), kb([[btn("🛍 Browse Shop", "shop:cats"), btn("🛟 Support", "ticket:new")], [btn("🔎 Search Again", "ai:ask"), btn("🏠 Home", "menu:main")]])
    lines = [f"📝 Request: <i>{esc(preview_text(query, max_lines=1, max_chars=90))}</i>"]
    if budget is not None:
        lines.append(f"🎯 Detected budget: <b>{money(budget)}</b>")
    buttons = []
    for i, p in enumerate(matches, 1):
        stock = p['avail'] if p['delivery_mode'] == 'STOCK' else '∞'
        fit = "✅ within budget" if budget is not None and float(p['price'] or 0) <= budget else ("💎 best match" if i == 1 else "✨ option")
        desc = preview_text(p['description'], max_lines=1, max_chars=58) if p['description'] else "Instant digital product"
        lines.append(f"{i}. {esc(p['emoji'] or '📦')} <b>{esc(p['name'][:30])}</b> — {money(p['price'])} • 📦 {stock} • {fit}")
        lines.append(f"   <i>{esc(desc)}</i>")
        buttons.append([btn(f"🛒 {i}. {p['name'][:22]} — {money(p['price'])}", f"prod:{p['id']}")])
    buttons.append([btn("🔎 Search Again", "ai:ask"), btn("🏠 Home", "menu:main")])
    return neon_card("🧠 AI Concierge Max", "Stock-aware product recommendations", lines, "Local smart engine: budget + keyword + stock + popularity"), kb(buttons)

@router.callback_query(F.data == "ai:ask")
async def ai_ask(call: CallbackQuery, state: FSMContext):
    if str(await db.get("ai_assistant_enabled") or "1") != "1" and not is_admin(call.from_user.id):
        return await call.answer("AI assistant is temporarily off.", show_alert=True)
    await state.set_state(AIAssistantState.query)
    intro = await db.get("ai_assistant_intro")
    await safe_edit(call.message, neon_card("🧠 AI Concierge Max", "Write naturally — I will understand product, budget, payment, VIP or support intent", ["🎯 Example: ২০০ টাকার মধ্যে Netflix চাই", "📦 I check live stock and price", "💳 I explain wallet/external payment", "🚚 I can track recent orders"], "Send one message in Bangla or English"), reply_markup=kb([[btn("🔥 Hot Deals", "shop:hot"), btn("🛍 Shop", "shop:cats")], [btn("❌ Cancel", "state:cancel")]]))
    await call.answer()

@router.message(Command("ai", "assistant"))
async def ai_command(message: Message, state: FSMContext):
    await db.add_user(message)
    await state.set_state(AIAssistantState.query)
    intro = await db.get("ai_assistant_intro")
    await message.answer(neon_card("🧠 AI Concierge Max", "Write naturally — I will understand product, budget, payment, VIP or support intent", ["🎯 Example: ২০০ টাকার মধ্যে Netflix চাই", "📦 I check live stock and price", "💳 I explain wallet/external payment", "🚚 I can track recent orders"], "Send one message in Bangla or English"), reply_markup=cancel_kb())

@router.message(AIAssistantState.query)
async def ai_query(message: Message, state: FSMContext):
    query = (message.text or "").strip()
    if len(query) < 2:
        return await message.answer("Write product name, budget, problem, or order question.", reply_markup=cancel_kb())
    loader = None
    if ANIMATION_ENABLED:
        try:
            loader = await message.answer("<b>🧠 AI Concierge Pro</b>\n<code>▰▱▱</code> reading your request…")
            await asyncio.sleep(ANIMATION_SPEED_MS / 1000)
            await safe_edit(loader, "<b>🧠 AI Concierge Pro</b>\n<code>▰▰▱</code> checking live stock + price…")
            await asyncio.sleep(ANIMATION_SPEED_MS / 1000)
        except Exception:
            loader = None
    body, markup = await ai_answer_for(message.from_user.id, query)
    await state.clear()
    final_text = body if body.startswith("<blockquote>") else neon_card("🧠 AI Commerce Answer", "Smart result", [body], "Live local AI engine • fast • stock-aware")
    if loader:
        await safe_edit(loader, final_text, reply_markup=markup)
    else:
        await message.answer(final_text, reply_markup=markup)

@router.callback_query(F.data == "track:ask")
async def track_ask(call: CallbackQuery, state: FSMContext):
    await state.set_state(TrackState.order_id)
    rows = await db.fetchall("SELECT id,status FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (call.from_user.id,))
    if rows:
        buttons = [[btn(f"🚚 {r['id']} — {status_badge(r['status'])}", f"order:view:{r['id']}")] for r in rows]
        buttons.append([btn("✍️ Type Order ID", "track:type"), btn("🏠 Menu", "menu:main")])
        await safe_edit(call.message, card("🚚 Order Tracking", "Choose your order or type order ID:"), reply_markup=kb(buttons))
    else:
        await safe_edit(call.message, card("🚚 Order Tracking", "Type your order ID. Example: ORD-xxxx"), reply_markup=cancel_kb())
    await call.answer()

@router.callback_query(F.data == "track:type")
async def track_type(call: CallbackQuery, state: FSMContext):
    await state.set_state(TrackState.order_id)
    await safe_edit(call.message, card("🚚 Track Order", "Send your order ID now:"), reply_markup=cancel_kb())
    await call.answer()

@router.message(Command("track"))
async def track_command(message: Message, state: FSMContext):
    await db.add_user(message)
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        return await show_order_tracking_message(message, parts[1].strip())
    await state.set_state(TrackState.order_id)
    await message.answer(card("🚚 Track Order", "Send your order ID now:"), reply_markup=cancel_kb())

@router.message(TrackState.order_id)
async def track_order_id(message: Message, state: FSMContext):
    await state.clear()
    await show_order_tracking_message(message, message.text.strip())

async def show_order_tracking_message(message: Message, order_id: str):
    order_id = order_id.strip().upper()
    if is_admin(message.from_user.id):
        o = await db.fetchone("SELECT o.*, p.name FROM orders o JOIN products p ON p.id=o.product_id WHERE o.id=?", (order_id,))
    else:
        o = await db.fetchone("SELECT o.*, p.name FROM orders o JOIN products p ON p.id=o.product_id WHERE o.id=? AND o.user_id=?", (order_id, message.from_user.id))
    if not o:
        return await message.answer(card("🚚 Tracking", "Order not found. Check ID or open Support Ticket."), reply_markup=main_menu(message.from_user.id))
    timeline = await order_timeline(o['id'])
    body = (
        f"🧾 Order: <code>{o['id']}</code>\n"
        f"🛒 Product: <b>{esc(o['name'])}</b>\n"
        f"💰 Amount: <b>{money(o['amount'] - o['discount'])}</b>\n"
        f"📋 Current: <b>{status_badge(o['status'])}</b>\n\n"
        f"<blockquote>🚚 <b>Timeline</b>\n{timeline}</blockquote>"
    )
    await message.answer(card("🚚 Live Order Tracking", body), reply_markup=kb([[btn("📦 My Orders", "orders:mine"), btn("🏠 Menu", "menu:main")]]))

@router.callback_query(F.data == "admin:alerts")
async def admin_alert_center(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    last = await db.fetchall("SELECT * FROM alert_logs ORDER BY created_at DESC LIMIT 5")
    low = await db.fetchall("SELECT p.name, (SELECT COUNT(*) FROM stock WHERE product_id=p.id AND used=0) AS avail FROM products p WHERE p.delivery_mode='STOCK' AND p.active=1 ORDER BY avail ASC LIMIT 8")
    body = "🚨 <b>Alert Center</b> — user notice, VIP alert, stock alert control.\n\n"
    if low:
        body += "⚠️ <b>Lowest stock</b>\n" + "\n".join([f"• {esc(x['name'][:22])}: <b>{x['avail']}</b>" for x in low]) + "\n\n"
    if last:
        body += "📜 <b>Recent alert logs</b>\n" + "\n".join([f"• {esc(r['audience'])}: {r['sent_count']} sent / {r['failed']} failed" for r in last])
    rows = [
        [btn("📣 Alert All Users", "alert:compose:all"), btn("💎 Alert VIP", "alert:compose:vip")],
        [btn("👑 Alert Admins", "alert:compose:admins"), btn("⚙️ Stock Alert Settings", "admin:stockalerts")],
        [btn("🔎 Low Stock Report", "admin:alerts:low"), btn("⬅️ Admin Home", "admin:home")],
    ]
    await safe_edit(call.message, card("🚨 Alert Center", body), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:alerts:low")
async def admin_low_stock_report(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    threshold = await stock_alert_threshold()
    rows = await db.fetchall("SELECT p.id,p.name,(SELECT COUNT(*) FROM stock WHERE product_id=p.id AND used=0) AS avail FROM products p WHERE p.delivery_mode='STOCK' AND p.active=1 ORDER BY avail ASC LIMIT 30")
    body = f"⚠️ Low limit: <b>{threshold}</b>\n\n"
    for p in rows:
        avail = int(p['avail'] or 0)
        if avail == 0:
            icon = "🚫"
        elif avail <= threshold:
            icon = "⚠️"
        else:
            icon = "✅"
        body += f"{icon} <code>{esc(p['id'])}</code> — {esc(p['name'][:24])}: <b>{avail}</b>\n"
    await safe_edit(call.message, card("🔎 Stock Health Report", body or "No stock products."), reply_markup=kb([[btn("⚙️ Alert Settings", "admin:stockalerts"), btn("⬅️ Alert Center", "admin:alerts")]]))
    await call.answer()

@router.callback_query(F.data.startswith("alert:compose:"))
async def alert_compose(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    audience = call.data.split(":")[-1]
    await state.set_state(TextEdit.alert_message)
    await state.update_data(alert_audience=audience)
    await safe_edit(call.message, card("📣 Compose Alert", f"Audience: <b>{esc(audience.upper())}</b>\n\nSend alert text/photo caption now. Text supports Telegram HTML formatting."), reply_markup=cancel_kb())
    await call.answer()

@router.message(TextEdit.alert_message)
async def alert_send(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    audience = data.get("alert_audience", "all")
    if audience == "vip":
        targets = await db.fetchall("SELECT id FROM users WHERE is_banned=0 AND (role='vip' OR role='admin' OR vip_expires>?)", (now(),))
    elif audience == "admins":
        targets = [{"id": aid} for aid in all_admin_ids()]
    else:
        targets = await db.fetchall("SELECT id FROM users WHERE is_banned=0")
    text = message.html_text or message.text or ""
    sent = failed = 0
    for t in targets:
        uid = int(t['id']) if isinstance(t, dict) else int(t['id'])
        try:
            await bot.send_message(uid, card("🚨 Store Alert", text), reply_markup=kb([[btn("🛍 Open Shop", "shop:cats"), btn("🎫 Support", "ticket:new")]]))
            sent += 1
            await asyncio.sleep(0.035)
        except Exception:
            failed += 1
    await db.execute("INSERT INTO alert_logs(id,audience,message,sent_count,failed,actor_id,created_at) VALUES(?,?,?,?,?,?,?)", (code("ALT"), audience, text[:1000], sent, failed, message.from_user.id, now()))
    await state.clear()
    await message.answer(card("✅ Alert Sent", f"Audience: <b>{esc(audience)}</b>\nSent: <b>{sent}</b>\nFailed: <b>{failed}</b>"), reply_markup=admin_home_kb())

@router.callback_query(F.data == "admin:ai")
async def admin_ai_center(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    enabled = str(await db.get("ai_assistant_enabled") or "1") == "1"
    logs = await db.fetchall("SELECT * FROM ai_logs ORDER BY created_at DESC LIMIT 6")
    body = f"🤖 Status: <b>{'ON ✅' if enabled else 'OFF ❌'}</b>\n\n"
    if logs:
        body += "🧠 <b>Recent AI questions</b>\n" + "\n".join([f"• <code>{r['user_id']}</code>: {esc(preview_text(r['query'], max_lines=1, max_chars=60))}" for r in logs])
    else:
        body += "No AI questions yet."
    await safe_edit(call.message, card("🤖 AI Commerce Center", body), reply_markup=kb([
        [btn("🔌 Toggle AI", "admin:ai:toggle"), btn("✏️ Edit AI Intro", "admin:ai:intro")],
        [btn("📝 Edit No-Result Text", "admin:ai:noresult"), btn("🧪 Test as User", "ai:ask")],
        [btn("⬅️ Admin Home", "admin:home")]
    ]))
    await call.answer()

@router.callback_query(F.data == "admin:ai:toggle")
async def admin_ai_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    cur = str(await db.get("ai_assistant_enabled") or "1")
    await db.set("ai_assistant_enabled", "0" if cur == "1" else "1")
    await admin_ai_center(call)

@router.callback_query(F.data == "admin:ai:intro")
async def admin_ai_intro_edit(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(TextEdit.ai_intro)
    await safe_edit(call.message, card("✏️ Edit AI Intro", "Send new AI assistant intro text:"), reply_markup=cancel_kb())
    await call.answer()

@router.message(TextEdit.ai_intro)
async def admin_ai_intro_save(message: Message, state: FSMContext):
    await db.set("ai_assistant_intro", message.html_text)
    await state.clear()
    await message.answer(card("✅ Saved", "AI intro text updated."), reply_markup=admin_home_kb())

@router.callback_query(F.data == "admin:ai:noresult")
async def admin_ai_noresult_edit(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(TextEdit.ai_no_result)
    await safe_edit(call.message, card("📝 Edit AI No-Result Text", "Send message shown when AI finds no matching product:"), reply_markup=cancel_kb())
    await call.answer()

@router.message(TextEdit.ai_no_result)
async def admin_ai_noresult_save(message: Message, state: FSMContext):
    await db.set("ai_no_result_text", message.html_text)
    await state.clear()
    await message.answer(card("✅ Saved", "AI no-result text updated."), reply_markup=admin_home_kb())

@router.callback_query(F.data == "admin:fraud")
async def admin_fraud_center(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    enabled = str(await db.get("fraud_guard_enabled") or "1") == "1"
    limit = await db.get("fraud_order_limit") or "3"
    window = await db.get("fraud_window_min") or "10"
    flags = await db.fetchall("SELECT * FROM fraud_flags ORDER BY created_at DESC LIMIT 10")
    body = f"🛡 Status: <b>{'ON ✅' if enabled else 'OFF ❌'}</b>\nRule: more than <b>{limit}</b> orders in <b>{window} min</b> triggers warning.\n\n"
    if flags:
        body += "🚩 <b>Recent flags</b>\n"
        for f in flags:
            body += f"• <code>{f['user_id']}</code> | {f['score']}/100 | <code>{esc(f['order_id'])}</code>\n  {esc(preview_text(f['reason'], max_lines=1, max_chars=80))}\n"
    else:
        body += "No fraud flags yet."
    await safe_edit(call.message, card("🛡 Fraud Guard Center", body), reply_markup=kb([
        [btn("🔌 Toggle Fraud Guard", "fraud:toggle"), btn("⚙️ Set Rule", "fraud:rule")],
        [btn("🚫 Blacklist", "fraud:blacklist"), btn("🛡 Pro View", "admin:fraudpro")],
        [btn("🧾 Pending Orders", "admin:orders"), btn("⬅️ Admin Home", "admin:home")]
    ]))
    await call.answer()

@router.callback_query(F.data == "fraud:toggle")
async def fraud_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    cur = str(await db.get("fraud_guard_enabled") or "1")
    await db.set("fraud_guard_enabled", "0" if cur == "1" else "1")
    await admin_fraud_center(call)

@router.callback_query(F.data == "fraud:rule")
async def fraud_rule_ask(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(TextEdit.fraud_limit)
    await safe_edit(call.message, card("⚙️ Fraud Rule", "Send as: <code>ORDER_LIMIT | WINDOW_MINUTES</code>\nExample: <code>3 | 10</code>"), reply_markup=cancel_kb())
    await call.answer()

@router.message(TextEdit.fraud_limit)
async def fraud_rule_save(message: Message, state: FSMContext):
    try:
        parts = [x.strip() for x in message.text.replace(",", "|").split("|")]
        limit = max(1, int(float(parts[0])))
        window = max(1, int(float(parts[1]))) if len(parts) > 1 else 10
    except Exception:
        return await message.answer("❌ Format: 3 | 10")
    await db.set("fraud_order_limit", str(limit))
    await db.set("fraud_window_min", str(window))
    await state.clear()
    await message.answer(card("✅ Fraud Rule Updated", f"Limit: <b>{limit}</b> orders\nWindow: <b>{window}</b> minutes"), reply_markup=admin_home_kb())

@router.callback_query(F.data == "admin:insights")
async def admin_smart_insights(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    revenue = await db.fetchone("SELECT COALESCE(SUM(amount-discount),0) total FROM orders WHERE status IN ('DELIVERED','COMPLETED')")
    pending = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE status IN ('WAITING_PROOF','PENDING','PROCESSING')")
    users = await db.fetchone("SELECT COUNT(*) n FROM users")
    vip = await db.fetchone("SELECT COUNT(*) n FROM users WHERE role='vip' OR vip_expires=0 OR vip_expires>?", (now(),))
    best = await db.fetchall("SELECT name,sold,price FROM products WHERE active=1 ORDER BY sold DESC, featured DESC LIMIT 5")
    flags = await db.fetchone("SELECT COUNT(*) n FROM fraud_flags WHERE resolved=0")
    body = (
        f"💰 Delivered revenue: <b>{money(revenue['total'] if revenue else 0)}</b>\n"
        f"🧾 Active orders: <b>{pending['n'] if pending else 0}</b>\n"
        f"👥 Users: <b>{users['n'] if users else 0}</b> | 💎 VIP: <b>{vip['n'] if vip else 0}</b>\n"
        f"🚩 Open fraud flags: <b>{flags['n'] if flags else 0}</b>\n\n"
    )
    if best:
        body += "🏆 <b>Top products</b>\n" + "\n".join([f"• {esc(b['name'][:24])} — sold {b['sold']} | {money(b['price'])}" for b in best])
    await safe_edit(call.message, card("🧬 Smart Commerce Insights", body, "Fast snapshot for admin decisions"), reply_markup=kb([[btn("📊 Dashboard", "admin:dash"), btn("📈 Analytics", "admin:analytics")], [btn("⬅️ Admin Home", "admin:home")]]))
    await call.answer()

@router.callback_query(F.data.startswith("admin:status:"))
async def admin_order_set_status(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id): return
    _, _, new_status, oid = call.data.split(":", 3)
    allowed = {"PROCESSING", "COMPLETED", "CANCELLED"}
    if new_status not in allowed:
        return await call.answer("Invalid status", show_alert=True)
    o = await db.fetchone("SELECT * FROM orders WHERE id=?", (oid,))
    if not o:
        return await call.answer("Order not found", show_alert=True)
    await db.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?", (new_status, now(), oid))
    await log_order_event(oid, new_status, f"Updated by admin {call.from_user.id}", call.from_user.id)
    try:
        await bot.send_message(o['user_id'], card("🚚 Order Status Updated", f"Order: <code>{oid}</code>\nStatus: <b>{status_badge(new_status)}</b>"), reply_markup=kb([[btn("🚚 Track Order", f"order:view:{oid}")]]))
    except Exception:
        pass
    await call.answer("Status updated", show_alert=True)
    await admin_order_view(call, bot)


# ═══════════════════════════════════════════════════════════════
#  V15 MONGODB AUTOPILOT AI COMMERCE OS — EXTRA MODULES
# ═══════════════════════════════════════════════════════════════

class V14State(StatesGroup):
    cart_proof = State()
    paymethod_add = State()
    vendor_request = State()
    blacklist_user = State()
    super_alert_message = State()

def normalize_trx_id(text: str) -> str:
    """Normalize a bKash/Nagad/Rocket transaction ID for duplicate checks."""
    trx = re.sub(r"[^A-Za-z0-9_-]", "", str(text or "").strip().upper())
    if len(trx) < 6 or len(trx) > 64:
        return ""
    return trx

async def trx_is_duplicate(method_id: str, trx_id: str) -> bool:
    if not await v14_setting_on("autopay_strict_trx_duplicate", "1"):
        return False
    row = await db.fetchone(
        "SELECT id FROM external_payment_requests WHERE method=? AND trx_id=? AND status NOT IN ('REJECTED','CANCELLED') LIMIT 1",
        (method_id, trx_id)
    )
    return row is not None

async def create_external_payment_request(user_id: int, amount: float, purpose: str, method: str, related_ids: str, trx_id: str = "", proof_file_id: str = "", status: str = "PENDING") -> str:
    req_id = code("EPR")
    await db.execute(
        "INSERT INTO external_payment_requests(id,user_id,amount,currency,purpose,method,related_ids,trx_id,proof_file_id,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (req_id, user_id, amount, CURRENCY, purpose, method, related_ids, trx_id, proof_file_id, status, now(), now())
    )
    try:
        await db.execute(
            "INSERT INTO payment_intents(id,user_id,amount,currency,purpose,method,related_ids,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (req_id.replace("EPR", "PIN", 1), user_id, amount, CURRENCY, purpose, method, related_ids, status, now(), now())
        )
    except Exception:
        pass
    return req_id

async def smart_payment_method_kb(prefix: str) -> list[list[InlineKeyboardButton]]:
    """Build RichPay vertical payment method buttons — clean on mobile."""
    methods = await db.fetchall("SELECT * FROM payment_methods WHERE active=1 ORDER BY sort_order, created_at LIMIT 8")
    rows = []
    for m in methods:
        title = str(m["title"] or m["id"]).strip()
        rows.append([btn(f"{method_icon(title, m['id'])} {title}", f"{prefix}:{m['id']}")])
    return rows


async def wallet_payment_rows(amount: float) -> list[list[InlineKeyboardButton]]:
    methods = await db.fetchall("SELECT * FROM payment_methods WHERE active=1 ORDER BY sort_order, created_at LIMIT 6")
    rows, line = [], []
    for m in methods:
        title = str(m["title"] or m["id"]).strip()
        line.append(btn(f"💳 {title}", f"walletpay:{amount:g}:{m['id']}"))
        if len(line) == 2:
            rows.append(line); line = []
    if line:
        rows.append(line)
    rows.append([btn("📸 Upload Screenshot/Text", f"walletproof:{amount:g}")])
    if PAYMENT_WEBAPP_URL or (await db.get("autopay_webapp_url")):
        rows.append([url_btn("🌐 Open Web Payment Page", PAYMENT_WEBAPP_URL or await db.get("autopay_webapp_url"))])
    rows.append([btn("⬅️ Money", "menu:money"), btn("🏠 Home", "menu:main")])
    return rows

async def smart_payment_instruction(method_id: str, amount: float, purpose_label: str) -> str:
    m = await db.fetchone("SELECT * FROM payment_methods WHERE id=? AND active=1", (method_id,))
    if not m:
        return f"Exact amount: <b>{money(amount)}</b>\nSend payment, then send Transaction ID."
    note = await db.get("autopay_note") or "টাকা পাঠানোর ৫-১০ সেকেন্ড পর Transaction ID দিন।"
    brand = await db.get("autopay_brand") or SHOP_NAME
    ref = payment_ref_code(purpose_label)
    network_warning = ""
    t = f"{m['title']} {m['id']}".lower()
    if "bep20" in t or "bsc" in t:
        network_warning = "\nNetwork: <b>BEP20 / BSC only</b>"
    elif "trc20" in t or "tron" in t:
        network_warning = "\nNetwork: <b>TRC20 / Tron only</b>"
    body = (
        f"{esc(purpose_label)}\n"
        f"Amount: <b>{money(amount)}</b>\n"
        f"Store: <b>{esc(brand)}</b>\n\n"
        f"Open your <b>{esc(m['title'])}</b> app\n"
        f"Send to: <code>{esc(m['account'])}</code>{network_warning}\n"
        f"Amount: <b>{money(amount)}</b>\n"
        f"Add this note/reference exactly:\n\n"
        f"<code>{esc(ref)}</code>\n\n"
        f"<blockquote>{esc(note)}</blockquote>\n"
    )
    if m["instructions"]:
        body += f"\n<i>{esc(preview_text(m['instructions'], max_lines=3, max_chars=260))}</i>\n"
    body += "\nAfter payment, send your <b>Transaction ID / TXID only</b>."
    return body


async def approve_external_payment_request(bot: Bot, req_id: str, admin_id: int) -> tuple[bool, str]:
    r = await db.fetchone("SELECT * FROM external_payment_requests WHERE id=?", (req_id,))
    if not r:
        return False, "Request not found"
    if r["status"] in ("APPROVED", "DELIVERED", "CREDITED"):
        return False, "Already approved"
    amount = round(float(r["amount"] or 0), 2)
    purpose = str(r["purpose"] or "").upper()
    related = str(r["related_ids"] or "")
    status = "APPROVED"
    note = "Approved by admin"

    if purpose == "WALLET":
        await db.wallet_add(r["user_id"], amount, "TOPUP_TRX_VERIFIED", f"TRX {r['trx_id']} / {req_id}")
        status = "CREDITED"
        note = f"Wallet credited {money(amount)}"
        try:
            await bot.send_message(r["user_id"], card("✅ Wallet Top-Up Verified", f"Amount: <b>{money(amount)}</b>\nTRX: <code>{esc(r['trx_id'])}</code>\nYour wallet is ready for instant purchase."), reply_markup=main_menu(r["user_id"]))
        except Exception:
            pass
    elif purpose == "ORDER":
        oid = related
        await db.execute("UPDATE orders SET payment_status='VERIFIED', status='PROCESSING', payment_ref=?, updated_at=? WHERE id=?", (r["trx_id"], now(), oid))
        await log_order_event(oid, "PROCESSING", f"External payment approved: {req_id}", admin_id)
        ok, msg = await deliver_order(bot, oid)
        status = "DELIVERED" if ok else "APPROVED"
        note = msg
    elif purpose == "CART":
        checkout_id = related
        co = await db.fetchone("SELECT * FROM cart_checkouts WHERE id=?", (checkout_id,))
        order_ids = [x for x in str(co["order_ids"] if co else "").split(',') if x]
        delivered = 0
        for oid in order_ids:
            await db.execute("UPDATE orders SET payment_status='VERIFIED', status='PROCESSING', payment_ref=?, updated_at=? WHERE id=?", (r["trx_id"], now(), oid))
            await log_order_event(oid, "PROCESSING", f"Cart external payment approved: {req_id}", admin_id)
            ok, _msg = await deliver_order(bot, oid)
            delivered += 1 if ok else 0
        await db.execute("UPDATE cart_checkouts SET status=?, updated_at=? WHERE id=?", ("DELIVERED" if delivered == len(order_ids) else "PAID", now(), checkout_id))
        await db.execute("DELETE FROM cart WHERE user_id=?", (r["user_id"],))
        status = "DELIVERED" if delivered else "APPROVED"
        note = f"Cart approved. Delivered {delivered}/{len(order_ids)} orders."
    else:
        return False, "Unknown purpose"

    await db.execute("UPDATE external_payment_requests SET status=?, admin_id=?, note=?, updated_at=? WHERE id=?", (status, admin_id, note, now(), req_id))
    await db.execute(
        "INSERT INTO autopay_logs(id,user_id,intent_id,amount,result,note,created_at) VALUES(?,?,?,?,?,?,?)",
        (code("APL"), r["user_id"], req_id, amount, status, note, now())
    )
    return True, note

@router.callback_query(F.data.startswith("admin:payreq:approve:"))
async def admin_payreq_approve(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    req_id = call.data.split(":")[-1]
    ok, msg = await approve_external_payment_request(bot, req_id, call.from_user.id)
    await call.answer(msg, show_alert=True)
    await safe_edit(call.message, card("✅ Payment Request Updated" if ok else "⚠️ Payment Request", f"Req: <code>{req_id}</code>\n{esc(msg)}"), reply_markup=admin_home_kb())

@router.callback_query(F.data.startswith("admin:payreq:reject:"))
async def admin_payreq_reject(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return
    req_id = call.data.split(":")[-1]
    r = await db.fetchone("SELECT * FROM external_payment_requests WHERE id=?", (req_id,))
    if not r:
        return await call.answer("Request not found", show_alert=True)
    await db.execute("UPDATE external_payment_requests SET status='REJECTED', admin_id=?, note=?, updated_at=? WHERE id=?", (call.from_user.id, "Rejected by admin", now(), req_id))
    try:
        await bot.send_message(r["user_id"], card("❌ Payment Rejected", f"Request: <code>{req_id}</code>\nTRX: <code>{esc(r['trx_id'])}</code>\nPlease contact support if this was a mistake."))
    except Exception:
        pass
    await safe_edit(call.message, card("❌ Payment Request Rejected", f"Req: <code>{req_id}</code>"), reply_markup=admin_home_kb())
    await call.answer("Rejected")

async def payment_methods_text() -> str:
    """Build live payment instructions from admin-managed payment methods."""
    methods = await db.fetchall("SELECT * FROM payment_methods WHERE active=1 ORDER BY sort_order, created_at")
    fallback = await db.get("payment_text") or "Send payment, then upload screenshot proof."
    if not methods:
        return fallback
    body = "💳 <b>Payment Methods</b>\n\n"
    for m in methods:
        body += f"• <b>{esc(m['title'])}</b>: <code>{esc(m['account'])}</code>\n"
        if m["instructions"]:
            body += f"  <i>{esc(preview_text(m['instructions'], max_lines=1, max_chars=90))}</i>\n"
    body += "\n📸 Send exact amount, then upload screenshot/photo or transaction text."
    extra = preview_text(fallback, max_lines=2, max_chars=180)
    if extra and "Payment Methods" not in extra:
        body += f"\n\n{extra}"
    return body

async def v14_setting_on(key: str, default: str = "1") -> bool:
    return str(await db.get(key) or default) == "1"

async def v14_super_alert(bot: Bot, kind: str, title: str, message: str, user_id: int | None = None, order_id: str | None = None):
    """Central V15 alert pipeline for important business events."""
    if not await v14_setting_on(f"super_alert_{kind}", "1"):
        return
    lines = [message]
    if user_id:
        lines.append(f"👤 User: <code>{user_id}</code>")
    if order_id:
        lines.append(f"🧾 Order: <code>{esc(order_id)}</code>")
    await db.execute(
        "INSERT INTO alert_logs(id,audience,message,sent_count,failed,actor_id,created_at) VALUES(?,?,?,?,?,?,?)",
        (code("ALT"), "admins", f"{title}\n{message}", 0, 0, user_id or 0, now())
    )
    await notify_admins(bot, card(f"🚨 {title}", "\n".join(lines)), reply_markup=kb([[btn("🚀 V15 OS", "admin:v14dash"), btn("🧾 Order Board", "admin:orders")]]))

async def v14_blocked_user(uid: int) -> bool:
    row = await db.fetchone("SELECT 1 FROM fraud_blacklist WHERE user_id=?", (uid,))
    return row is not None

async def v14_shop_closed_text() -> str:
    notice = preview_text(await db.get("notice") or "Shop is temporarily closed.", max_lines=3, max_chars=180)
    return card("🛠 Shop Closed", f"The store is closed by admin control right now.\n\n📢 {esc(notice)}", "Try again later or contact support.")

@router.message(Command("cart"))
async def cart_command(message: Message):
    await db.add_user(message)
    items = await db.fetchall(
        "SELECT cart.*, products.name, products.price FROM cart JOIN products ON products.id=cart.product_id WHERE cart.user_id=?",
        (message.from_user.id,)
    )
    if not items:
        return await message.answer(card("🧺 Smart Cart", "Your cart is empty. Browse shop and add products first."), reply_markup=kb([[btn("🛍 Shop", "shop:cats")], [btn("🏠 Menu", "menu:main")]]))
    total = sum(float(i["price"]) * int(i["qty"]) for i in items)
    body = "".join([f"• {esc(i['name'])} × {i['qty']} = {money(float(i['price']) * int(i['qty']))}\n" for i in items])
    body += f"\n💰 <b>Total: {money(total)}</b>"
    await message.answer(card("🧺 Smart Cart", body, "Smart checkout: wallet autopay or exact amount proof flow."), reply_markup=kb([[btn("⚡ Smart Pay All", "cart:smartpay"), btn("🛍 Shop", "shop:cats")], [btn("🏠 Menu", "menu:main")]]))

@router.callback_query(F.data == "cart:smartpay")
async def v18_cart_smartpay(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not await v14_setting_on("cart_enabled", "1"):
        return await call.answer("Smart cart is temporarily disabled.", show_alert=True)
    if not await v14_setting_on("shop_open", "1") and not is_admin(call.from_user.id):
        return await safe_edit(call.message, await v14_shop_closed_text(), reply_markup=back_main())
    items = await db.fetchall(
        "SELECT cart.*, products.name, products.price, products.delivery_mode FROM cart JOIN products ON products.id=cart.product_id WHERE cart.user_id=?",
        (call.from_user.id,)
    )
    if not items:
        return await call.answer("Cart is empty.", show_alert=True)

    problems = []
    subtotal = 0.0
    for i in items:
        qty = max(1, int(i["qty"] or 1))
        subtotal += float(i["price"]) * qty
        if i["delivery_mode"] == "STOCK":
            sc = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE product_id=? AND used=0", (i["product_id"],))
            have = int(sc["n"] if sc else 0)
            if have < qty:
                problems.append(f"{i['name']} needs {qty}, stock has {have}")
    if problems:
        return await safe_edit(call.message, card("⚠️ Cart Stock Problem", "\n".join([f"• {esc(x)}" for x in problems])), reply_markup=kb([[btn("🛍 Shop", "shop:cats"), btn("🏠 Home", "menu:main")]]))

    vip_disc = 0.0
    if await db.check_vip(call.from_user.id):
        vip_pct = float(await db.get("vip_discount") or "0")
        vip_disc = round(subtotal * vip_pct / 100, 2)
    final_total = round(max(0, subtotal - vip_disc), 2)
    checkout_id = code("CART")
    order_ids = []
    for i in items:
        qty = max(1, int(i["qty"] or 1))
        item_total = round(float(i["price"]) * qty, 2)
        item_discount = round((item_total / subtotal) * vip_disc, 2) if subtotal > 0 else 0
        oid = code("ORD")
        order_ids.append(oid)
        await db.execute(
            "INSERT INTO orders(id,user_id,product_id,qty,amount,discount,status,created_at,updated_at,admin_note,payment_status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (oid, call.from_user.id, i["product_id"], qty, item_total, item_discount, "WAITING_PROOF", now(), now(), f"V18 Smart Cart checkout {checkout_id}", "UNPAID")
        )
        await log_order_event(oid, "WAITING_PROOF", f"Created from V18 smart cart {checkout_id}", call.from_user.id)
        await maybe_flag_order(bot, call.from_user.id, oid)
    await db.execute(
        "INSERT INTO cart_checkouts(id,user_id,order_ids,total,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (checkout_id, call.from_user.id, ",".join(order_ids), final_total, "WAITING_PAYMENT", now(), now())
    )
    u = await db.get_user(call.from_user.id)
    balance = float(u["wallet"] if u else 0)
    need = round(max(0, final_total - balance), 2)
    rows = []
    if balance >= final_total and await v14_setting_on("wallet_autopay_enabled", "1"):
        rows.append([btn(f"⚡ Wallet AutoPay {money(final_total)}", f"cart:wallet:{checkout_id}")])
    elif need > 0:
        rows.append([btn(f"➕ Add Exact {money(need)}", f"wallet:topup:{need:g}")])
    rows.append([btn(f"📸 Manual Pay Exact {money(final_total)}", f"cart:manual:{checkout_id}")])
    rows.append([btn("🧺 Cart", "cart:view"), btn("🏠 Home", "menu:main")])
    lines = [f"• {esc(i['name'])} × {int(i['qty'] or 1)} = {money(float(i['price'])*int(i['qty'] or 1))}" for i in items]
    body = "\n".join(lines) + f"\n\nSubtotal: <b>{money(subtotal)}</b>\nVIP Discount: <b>-{money(vip_disc)}</b>\nExact Total: <b>{money(final_total)}</b>\nWallet: <b>{money(balance)}</b>"
    body += "\n\n<blockquote>🧠 Wallet AutoPay verifies inside the bot instantly and delivers stock automatically.</blockquote>"
    await safe_edit(call.message, card("⚡ Smart Cart Payment", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("cart:manual:"))
async def v18_cart_manual(call: CallbackQuery, state: FSMContext):
    checkout_id = call.data.split(":")[-1]
    co = await db.fetchone("SELECT * FROM cart_checkouts WHERE id=? AND user_id=?", (checkout_id, call.from_user.id))
    if not co:
        return await call.answer("Checkout not found.", show_alert=True)
    order_ids = [x for x in str(co["order_ids"] or "").split(',') if x]
    await state.update_data(checkout_id=checkout_id, order_ids=",".join(order_ids), expected_amount=float(co["total"] or 0), pay_purpose="CART")
    await db.execute("UPDATE cart_checkouts SET status='WAITING_METHOD', updated_at=? WHERE id=?", (now(), checkout_id))
    rows = await smart_payment_method_kb(f"cartpay:{checkout_id}")
    rows.append([btn("📸 Upload Proof/Text Instead", f"cart:proof:{checkout_id}")])
    if PAYMENT_WEBAPP_URL or (await db.get("autopay_webapp_url")):
        rows.append([url_btn("🌐 Open Web Payment Page", PAYMENT_WEBAPP_URL or await db.get("autopay_webapp_url"))])
    rows.append([btn("❌ Cancel", "state:cancel")])
    body = (f"Checkout: <code>{checkout_id}</code>\nOrders: <b>{len(order_ids)}</b>\nExact amount: <b>{money(co['total'])}</b>\n\n"
            "Select method, pay exact amount, then submit Transaction ID.")
    await safe_edit(call.message, card("⚡ Cart NeoPay", body), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data.startswith("cart:proof:"))
async def v19_cart_proof_fallback(call: CallbackQuery, state: FSMContext):
    checkout_id = call.data.split(":")[-1]
    co = await db.fetchone("SELECT * FROM cart_checkouts WHERE id=? AND user_id=?", (checkout_id, call.from_user.id))
    if not co:
        return await call.answer("Checkout not found.", show_alert=True)
    order_ids = [x for x in str(co["order_ids"] or "").split(',') if x]
    await state.set_state(V14State.cart_proof)
    await state.update_data(checkout_id=checkout_id, order_ids=order_ids, total=float(co["total"] or 0))
    await db.execute("UPDATE cart_checkouts SET status='WAITING_PROOF', updated_at=? WHERE id=?", (now(), checkout_id))
    body = f"Checkout: <code>{checkout_id}</code>\nOrders: <b>{len(order_ids)}</b>\nExact amount: <b>{money(co['total'])}</b>\n\n{await payment_methods_text()}\n\n📸 Send screenshot/photo/document or transaction text now."
    await safe_edit(call.message, card("📸 Cart Manual Payment", body), reply_markup=cancel_kb())
    await call.answer()


@router.callback_query(F.data.startswith("cartpay:"))
async def v19_cart_payment_method(call: CallbackQuery, state: FSMContext):
    _, checkout_id, method_id = call.data.split(":", 2)
    co = await db.fetchone("SELECT * FROM cart_checkouts WHERE id=? AND user_id=?", (checkout_id, call.from_user.id))
    if not co:
        return await call.answer("Checkout not found.", show_alert=True)
    order_ids = [x for x in str(co["order_ids"] or "").split(',') if x]
    m = await db.fetchone("SELECT * FROM payment_methods WHERE id=? AND active=1", (method_id,))
    if not m:
        return await call.answer("Payment method unavailable.", show_alert=True)
    await state.set_state(PaymentProof.trx_id)
    await state.update_data(checkout_id=checkout_id, order_ids=",".join(order_ids), expected_amount=float(co["total"] or 0), pay_purpose="CART", payment_method=method_id)
    await db.execute("UPDATE cart_checkouts SET status='WAITING_TRX', updated_at=? WHERE id=?", (now(), checkout_id))
    body = await smart_payment_instruction(method_id, float(co["total"] or 0), f"Cart checkout {checkout_id}")
    await safe_edit(call.message, card("🔐 Cart Transaction ID", body), reply_markup=kb([[btn("📸 Upload Screenshot Instead", f"cart:proof:{checkout_id}")], [btn("❌ Cancel", "state:cancel")]]))
    await call.answer()


@router.callback_query(F.data.startswith("cart:wallet:"))
async def v18_cart_wallet(call: CallbackQuery, state: FSMContext, bot: Bot):
    checkout_id = call.data.split(":")[-1]
    co = await db.fetchone("SELECT * FROM cart_checkouts WHERE id=? AND user_id=?", (checkout_id, call.from_user.id))
    if not co:
        return await call.answer("Checkout not found.", show_alert=True)
    if co["status"] in ("PAID", "DELIVERED", "COMPLETED"):
        return await call.answer("Already paid.", show_alert=True)
    total = round(float(co["total"] or 0), 2)
    u = await db.get_user(call.from_user.id)
    if float(u["wallet"] if u else 0) < total:
        return await call.answer(f"Need {money(total - float(u['wallet'] if u else 0))} more.", show_alert=True)
    order_ids = [x for x in str(co["order_ids"] or "").split(',') if x]
    intent_id = code("PAY")
    await db.execute(
        "INSERT INTO payment_intents(id,user_id,amount,currency,purpose,method,related_ids,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (intent_id, call.from_user.id, total, CURRENCY, "CART", "WALLET", checkout_id, "VERIFIED", now(), now())
    )
    await db.execute("UPDATE users SET wallet=wallet-? WHERE id=?", (total, call.from_user.id))
    await db.execute("INSERT INTO wallet_txns(id,user_id,amount,type,note,created_at) VALUES(?,?,?,?,?,?)", (code("WTX"), call.from_user.id, -total, "AUTOPAY_CART", f"Checkout {checkout_id} / {intent_id}", now()))
    await db.execute("INSERT INTO autopay_logs(id,user_id,intent_id,amount,result,note,created_at) VALUES(?,?,?,?,?,?,?)", (code("APL"), call.from_user.id, intent_id, total, "VERIFIED", f"Wallet cart payment {checkout_id}", now()))
    await db.execute("UPDATE cart_checkouts SET status='PAID', updated_at=? WHERE id=?", (now(), checkout_id))
    delivered = 0
    failed = []
    for oid in order_ids:
        o = await db.fetchone("SELECT * FROM orders WHERE id=?", (oid,))
        if not o:
            continue
        final = round(max(0, float(o["amount"] or 0)-float(o["discount"] or 0)), 2)
        await db.execute("UPDATE orders SET wallet_used=?, status='PROCESSING', proof_file_id=?, payment_method='WALLET', payment_status='VERIFIED', payment_ref=?, autopay=1, updated_at=? WHERE id=?", (final, f"WALLET:{intent_id}", intent_id, now(), oid))
        await log_order_event(oid, "PROCESSING", f"Cart wallet verified instantly ({intent_id})", call.from_user.id)
        ok, msg = await deliver_order(bot, oid) if await v14_setting_on("wallet_auto_delivery_enabled", "1") else (False, "Auto delivery disabled")
        if ok:
            delivered += 1
        else:
            failed.append(f"{oid}: {msg}")
    await db.execute("DELETE FROM cart WHERE user_id=?", (call.from_user.id,))
    await state.clear()
    status = "DELIVERED" if delivered == len(order_ids) else "PARTIAL"
    await db.execute("UPDATE cart_checkouts SET status=?, updated_at=? WHERE id=?", (status, now(), checkout_id))
    body = f"Checkout <code>{checkout_id}</code>\nPaid: <b>{money(total)}</b>\nRef: <code>{intent_id}</code>\nDelivered: <b>{delivered}/{len(order_ids)}</b>"
    if failed:
        body += "\n\n⚠️ Some items need admin/manual stock:\n" + "\n".join(esc(x) for x in failed[:5])
    await safe_edit(call.message, card("✅ Cart Wallet AutoPay", body), reply_markup=kb([[btn("📦 Orders", "orders:mine"), btn("🏠 Home", "menu:main")]]))
    await notify_admins(bot, card("⚡ Cart Wallet Autopay", f"Checkout <code>{checkout_id}</code> paid by wallet. Delivered {delivered}/{len(order_ids)}.\nAmount: <b>{money(total)}</b>\nRef: <code>{intent_id}</code>"), reply_markup=kb([[btn("🧾 Order Board", "admin:orders")]]))
    await call.answer("Wallet verified instantly ✅", show_alert=False)


@router.callback_query(F.data == "cart:checkout")
async def v14_cart_checkout(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not await v14_setting_on("cart_enabled", "1"):
        return await call.answer("Smart cart is temporarily disabled.", show_alert=True)
    if not await v14_setting_on("shop_open", "1") and not is_admin(call.from_user.id):
        return await safe_edit(call.message, await v14_shop_closed_text(), reply_markup=back_main())
    items = await db.fetchall(
        "SELECT cart.*, products.name, products.price, products.delivery_mode FROM cart JOIN products ON products.id=cart.product_id WHERE cart.user_id=?",
        (call.from_user.id,)
    )
    if not items:
        return await call.answer("Cart is empty.", show_alert=True)

    problems = []
    total = 0.0
    for i in items:
        qty = max(1, int(i["qty"] or 1))
        total += float(i["price"]) * qty
        if i["delivery_mode"] == "STOCK":
            sc = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE product_id=? AND used=0", (i["product_id"],))
            if int(sc["n"] if sc else 0) < qty:
                problems.append(f"{i['name']} needs {qty}, stock has {int(sc['n'] if sc else 0)}")
    if problems:
        return await safe_edit(call.message, card("⚠️ Cart Stock Problem", "\n".join([f"• {esc(x)}" for x in problems])), reply_markup=kb([[btn("🔐 Stock Alerts", "wish:view"), btn("🛍 Shop", "shop:cats")], [btn("🏠 Menu", "menu:main")]]))

    vip_disc = 0.0
    if await db.check_vip(call.from_user.id):
        vip_pct = float(await db.get("vip_discount") or "0")
        vip_disc = round(total * vip_pct / 100, 2)
    final_total = max(0, round(total - vip_disc, 2))
    checkout_id = code("CART")
    order_ids = []
    for i in items:
        qty = max(1, int(i["qty"] or 1))
        subtotal = round(float(i["price"]) * qty, 2)
        # Distribute VIP discount proportionally for cleaner analytics.
        item_discount = round((subtotal / total) * vip_disc, 2) if total > 0 else 0
        oid = code("ORD")
        order_ids.append(oid)
        await db.execute(
            "INSERT INTO orders(id,user_id,product_id,qty,amount,discount,status,created_at,updated_at,admin_note) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (oid, call.from_user.id, i["product_id"], qty, subtotal, item_discount, "WAITING_PROOF", now(), now(), f"V15 Smart Cart checkout {checkout_id}")
        )
        await log_order_event(oid, "WAITING_PROOF", f"Created from smart cart {checkout_id}", call.from_user.id)
        await maybe_flag_order(bot, call.from_user.id, oid)
    await db.execute(
        "INSERT INTO cart_checkouts(id,user_id,order_ids,total,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (checkout_id, call.from_user.id, ",".join(order_ids), final_total, "WAITING_PROOF", now(), now())
    )
    await state.set_state(V14State.cart_proof)
    await state.update_data(checkout_id=checkout_id, order_ids=order_ids, total=final_total)
    await safe_edit(call.message, card(
        "🧺 Smart Cart Checkout",
        f"Checkout: <code>{checkout_id}</code>\nOrders: <b>{len(order_ids)}</b>\nSubtotal: <b>{money(total)}</b>\nVIP Discount: <b>-{money(vip_disc)}</b>\nFinal Total: <b>{money(final_total)}</b>\n\n{await payment_methods_text()}\n\n📸 Send screenshot/photo/document or transaction text now.",
        "One proof can verify the full cart. Admin can approve each order from Proof Queue."
    ), reply_markup=cancel_kb())
    await call.answer()

@router.message(V14State.cart_proof)
async def v14_cart_proof(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    checkout_id = data.get("checkout_id")
    order_ids = data.get("order_ids", [])
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    elif message.text:
        file_id = "TEXT:" + message.text[:1000]
    else:
        return await message.answer("Please send screenshot/photo/document or transaction text.", reply_markup=cancel_kb())
    await db.execute("UPDATE cart_checkouts SET proof_file_id=?, status='PENDING', updated_at=? WHERE id=?", (file_id, now(), checkout_id))
    for oid in order_ids:
        await db.execute("UPDATE orders SET proof_file_id=?, status='PENDING', payment_method=COALESCE(payment_method,'EXTERNAL_PROOF'), payment_status='PROOF_SUBMITTED', updated_at=? WHERE id=?", (file_id, now(), oid))
        await log_order_event(oid, "PENDING", f"Cart proof submitted for {checkout_id}", message.from_user.id)
    await db.execute("DELETE FROM cart WHERE user_id=?", (message.from_user.id,))
    await state.clear()
    await message.answer(card("✅ Cart Proof Submitted", f"Checkout <code>{checkout_id}</code> is now in admin proof queue.\nOrders: <b>{len(order_ids)}</b>"), reply_markup=main_menu(message.from_user.id))
    await v14_super_alert(bot, "payment_proof", "Cart Payment Proof", f"Checkout <code>{checkout_id}</code> submitted proof for {len(order_ids)} order(s).", user_id=message.from_user.id)

@router.callback_query(F.data == "admin:v14dash")
async def v14_os_dashboard(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    total_sales = await db.fetchone("SELECT COALESCE(SUM(amount-discount),0) total FROM orders WHERE status IN ('DELIVERED','COMPLETED')")
    today_sales = await db.fetchone("SELECT COALESCE(SUM(amount-discount),0) total FROM orders WHERE status IN ('DELIVERED','COMPLETED') AND updated_at>?", (now()-86400,))
    pending_pay = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE status='PENDING'")
    waiting = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE status='WAITING_PROOF'")
    cart_pending = await db.fetchone("SELECT COUNT(*) n FROM cart_checkouts WHERE status='PENDING'")
    vendors = await db.fetchone("SELECT COUNT(*) n FROM vendor_requests WHERE status='PENDING'")
    low = await db.fetchone("SELECT COUNT(*) n FROM products p WHERE p.delivery_mode='STOCK' AND p.active=1 AND (SELECT COUNT(*) FROM stock s WHERE s.product_id=p.id AND s.used=0)<=?", (await stock_alert_threshold(),))
    methods = await db.fetchone("SELECT COUNT(*) n FROM payment_methods WHERE active=1")
    users = await db.fetchone("SELECT COUNT(*) n FROM users")
    body = (
        f"💰 Total Delivered Sales: <b>{money(total_sales['total'] if total_sales else 0)}</b>\n"
        f"📆 Today Sales: <b>{money(today_sales['total'] if today_sales else 0)}</b>\n"
        f"📸 Proof Queue: <b>{pending_pay['n'] if pending_pay else 0}</b> | ⏳ Waiting Proof: <b>{waiting['n'] if waiting else 0}</b>\n"
        f"🧺 Cart Proofs: <b>{cart_pending['n'] if cart_pending else 0}</b>\n"
        f"🔐 Low/Out Stock Products: <b>{low['n'] if low else 0}</b>\n"
        f"🏪 Vendor Requests: <b>{vendors['n'] if vendors else 0}</b>\n"
        f"💳 Active Payment Methods: <b>{methods['n'] if methods else 0}</b>\n"
        f"👥 Total Users: <b>{users['n'] if users else 0}</b>\n\n"
        f"🧩 Plugin mode: code edit ছাড়া settings panel থেকে control."
    )
    await safe_edit(call.message, card("🚀 V22 Premium Motion OS Dashboard", body, "AI Commerce • Cart • Payments • Vendor • Alerts • Fraud"), reply_markup=kb([
        [btn("📸 Proof Queue", "admin:payments"), btn("💳 Pay Methods", "admin:paymethods")],
        [btn("🧩 Feature Switches", "admin:plugins"), btn("🚨 Alerts", "admin:v14alerts")],
        [btn("🔐 Delivery Vault", "admin:vault"), btn("🏪 Vendors", "admin:vendors")],
        [btn("⬅️ Admin Home", "admin:home")]
    ]))
    await call.answer()

@router.callback_query(F.data == "admin:cartstats")
async def v14_cart_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    active = await db.fetchone("SELECT COUNT(DISTINCT user_id) n, COALESCE(SUM(qty),0) qty FROM cart")
    pending = await db.fetchall("SELECT * FROM cart_checkouts ORDER BY created_at DESC LIMIT 10")
    body = f"🧺 Active cart users: <b>{active['n'] if active else 0}</b>\n📦 Items in carts: <b>{active['qty'] if active else 0}</b>\n\n"
    if pending:
        body += "Recent checkouts:\n" + "\n".join([f"• <code>{c['id']}</code> — {money(c['total'])} — {esc(c['status'])}" for c in pending])
    else:
        body += "No cart checkouts yet."
    await safe_edit(call.message, card("🧺 Smart Cart Control", body), reply_markup=kb([[btn("📸 Proof Queue", "admin:payments"), btn("⬅️ Admin", "admin:home")]]))
    await call.answer()

@router.callback_query(F.data == "admin:payments")
async def v14_payment_queue(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    rows = await db.fetchall(
        "SELECT o.*, p.name, u.first_name FROM orders o JOIN products p ON p.id=o.product_id LEFT JOIN users u ON u.id=o.user_id WHERE o.status='PENDING' ORDER BY o.updated_at DESC LIMIT 20"
    )
    if not rows:
        return await safe_edit(call.message, card("📸 Payment Proof Queue", "No pending payment proofs right now."), reply_markup=kb([[btn("🚀 V15 OS", "admin:v14dash"), btn("⬅️ Admin", "admin:home")]]))
    body = "📸 <b>Latest pending proofs</b>\n\n"
    buttons = []
    for o in rows:
        body += f"• <code>{o['id']}</code> | {esc(o['name'][:18])} | {money(o['amount']-o['discount'])} | {esc(o['first_name'])}\n"
        buttons.append([btn(f"🧾 {o['id']} • {o['name'][:18]}", f"admin:order:{o['id']}")])
    buttons.append([btn("⬅️ Admin Home", "admin:home")])
    await safe_edit(call.message, card("📸 Payment Screenshot Auto Queue", body), reply_markup=kb(buttons))
    await call.answer()

@router.callback_query(F.data == "admin:paymethods")
async def v14_payment_methods_admin(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    methods = await db.fetchall("SELECT * FROM payment_methods ORDER BY sort_order, created_at")
    body = "💳 <b>Admin-managed payment methods</b>\n\n"
    buttons = []
    if methods:
        for m in methods:
            status = "✅" if m["active"] else "🚫"
            body += f"{status} <b>{esc(m['title'])}</b> — <code>{esc(m['account'])}</code>\n"
            buttons.append([btn(f"{status} Toggle {m['title'][:20]}", f"paym:toggle:{m['id']}")])
    else:
        body += "No payment methods yet. Add one now."
    buttons += [[btn("➕ Add Method", "paym:add"), btn("📝 Legacy Text", "admin:setpay")], [btn("⬅️ Admin Home", "admin:home")]]
    await safe_edit(call.message, card("💳 Payment Method Manager", body, "Format: bKash/Nagad/Rocket/Binance/custom; user checkout updates live."), reply_markup=kb(buttons))
    await call.answer()

@router.callback_query(F.data == "paym:add")
async def v14_payment_method_add(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(V14State.paymethod_add)
    await safe_edit(call.message, card("➕ Add Payment Method", "Send one line:\n<code>Title | Account/Number | Instructions</code>\n\nExample:\n<code>bKash Personal | 017xxxxxxxx | Send Money only, include order ID in reference</code>"), reply_markup=cancel_kb())
    await call.answer()

@router.message(V14State.paymethod_add)
async def v14_payment_method_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    parts = [x.strip() for x in (message.text or "").split("|")]
    if len(parts) < 2:
        return await message.answer("❌ Format: Title | Account | Instructions", reply_markup=cancel_kb())
    title, account = parts[0], parts[1]
    inst = parts[2] if len(parts) > 2 else ""
    order = await db.fetchone("SELECT COALESCE(MAX(sort_order),0)+1 n FROM payment_methods")
    pid = "PAY-" + secrets.token_hex(4).upper()
    await db.execute("INSERT INTO payment_methods(id,title,account,instructions,active,sort_order,created_at) VALUES(?,?,?,?,?,?,?)", (pid, title, account, inst, 1, int(order['n'] if order else 1), now()))
    await state.clear()
    await message.answer(card("✅ Payment Method Added", f"<b>{esc(title)}</b>\n<code>{esc(account)}</code>"), reply_markup=admin_home_kb())

@router.callback_query(F.data.startswith("paym:toggle:"))
async def v14_payment_method_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    pid = call.data.split(":", 2)[2]
    m = await db.fetchone("SELECT * FROM payment_methods WHERE id=?", (pid,))
    if not m:
        return await call.answer("Not found", show_alert=True)
    await db.execute("UPDATE payment_methods SET active=? WHERE id=?", (0 if m["active"] else 1, pid))
    await call.answer("Updated", show_alert=False)
    await v14_payment_methods_admin(call)

PLUGIN_KEYS = [
    ("shop_open", "🛍 Shop Open"),
    ("cart_enabled", "🧺 Smart Cart"),
    ("payment_proof_required", "📸 Payment Proof Required"),
    ("auto_delivery_enabled", "🔐 Auto Delivery Vault"),
    ("ai_assistant_enabled", "🤖 AI Assistant"),
    ("alert_center_enabled", "🚨 Alert Center"),
    ("fraud_guard_enabled", "🛡 Fraud Shield"),
    ("vendor_enabled", "🏪 Vendor Panel"),
    ("coupon_enabled", "🎟 Coupons"),
    ("redeem_enabled", "🎁 Redeem Codes"),
    ("vip_enabled", "💎 VIP System"),
]

@router.callback_query(F.data == "admin:plugins")
async def v14_plugins_panel(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    body = "🧩 <b>Plugin-style control</b>\nCode edit ছাড়া feature ON/OFF করুন।\n\n"
    rows = []
    for key, label in PLUGIN_KEYS:
        val = await db.get(key) or "1"
        state = "ON ✅" if str(val) == "1" else "OFF ❌"
        body += f"{label}: <b>{state}</b>\n"
        rows.append([btn(f"{label} — {state}", f"plug:toggle:{key}")])
    rows.append([btn("🚀 V15 OS", "admin:v14dash"), btn("⬅️ Admin", "admin:home")])
    await safe_edit(call.message, card("🧩 Autopilot Plugin Control", body), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data.startswith("plug:toggle:"))
async def v14_plugin_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    key = call.data.split(":", 2)[2]
    allowed = {k for k, _ in PLUGIN_KEYS}
    if key not in allowed:
        return await call.answer("Invalid plugin", show_alert=True)
    old = str(await db.get(key) or "1")
    new = "0" if old == "1" else "1"
    await db.set(key, new)
    await db.execute("INSERT INTO plugin_logs(id,key,old_value,new_value,actor_id,created_at) VALUES(?,?,?,?,?,?)", (code("PLG"), key, old, new, call.from_user.id, now()))
    await call.answer(f"{key}: {'ON' if new == '1' else 'OFF'}", show_alert=False)
    await v14_plugins_panel(call)

@router.callback_query(F.data == "admin:vault")
async def v14_vault_panel(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    products = await db.fetchall("SELECT p.id,p.name,p.delivery_mode,p.sold,(SELECT COUNT(*) FROM stock s WHERE s.product_id=p.id AND s.used=0) AS avail FROM products p WHERE p.active=1 ORDER BY avail ASC, p.sold DESC LIMIT 20")
    body = f"🔐 Auto Delivery: <b>{'ON ✅' if await v14_setting_on('auto_delivery_enabled','1') else 'OFF ❌'}</b>\nLow stock threshold: <b>{await stock_alert_threshold()}</b>\n\n"
    if products:
        for p in products:
            stock = "∞" if p["delivery_mode"] != "STOCK" else int(p["avail"] or 0)
            icon = "🚫" if p["delivery_mode"] == "STOCK" and stock == 0 else "⚠️" if p["delivery_mode"] == "STOCK" and stock <= await stock_alert_threshold() else "✅"
            body += f"{icon} {esc(p['name'][:28])} — Stock: <b>{stock}</b> | Sold: {p['sold']}\n"
    else:
        body += "No products yet."
    await safe_edit(call.message, card("🔐 Auto Stock Vault 2.0", body, "Approve order → vault auto-picks first unused stock line."), reply_markup=kb([[btn("➕ Add Stock", "admin:stock"), btn("⚙️ Alert Settings", "admin:stockalerts")], [btn("⬅️ Admin", "admin:home")]]))
    await call.answer()

@router.callback_query(F.data == "admin:v14alerts")
async def v14_alerts_panel(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    keys = ["new_order", "payment_proof", "low_stock", "fraud", "vendor"]
    body = "🚨 <b>Super Alert System</b>\n\n"
    rows = []
    for k in keys:
        val = await db.get(f"super_alert_{k}") or "1"
        body += f"• {k.replace('_',' ').title()}: <b>{'ON ✅' if val=='1' else 'OFF ❌'}</b>\n"
        rows.append([btn(f"Toggle {k.replace('_',' ').title()}", f"salert:toggle:{k}")])
    rows += [[btn("📣 Send All Alert", "salert:send:all"), btn("💎 VIP Alert", "salert:send:vip")], [btn("👑 Admin Alert", "salert:send:admin"), btn("⬅️ Admin", "admin:home")]]
    await safe_edit(call.message, card("🚨 Super Alert Center", body, "New order • proof • low stock • ticket/vendor • fraud warnings"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data.startswith("salert:toggle:"))
async def v14_alert_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    key = "super_alert_" + call.data.split(":", 2)[2]
    old = str(await db.get(key) or "1")
    await db.set(key, "0" if old == "1" else "1")
    await call.answer("Updated", show_alert=False)
    await v14_alerts_panel(call)

@router.callback_query(F.data.startswith("salert:send:"))
async def v14_alert_send_ask(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    audience = call.data.split(":", 2)[2]
    await state.set_state(V14State.super_alert_message)
    await state.update_data(alert_audience=audience)
    await safe_edit(call.message, card("📣 Send Super Alert", f"Audience: <b>{esc(audience.upper())}</b>\n\nSend alert text now."), reply_markup=cancel_kb())
    await call.answer()

@router.message(V14State.super_alert_message)
async def v14_alert_send_run(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    audience = data.get("alert_audience", "all")
    text = message.html_text or message.text or ""
    sent = failed = 0
    if audience == "admin":
        target_rows = [{"id": aid} for aid in all_admin_ids()]
    elif audience == "vip":
        target_rows = await db.fetchall("SELECT id FROM users WHERE role IN ('vip','admin') OR vip_expires=0 OR vip_expires>?", (now(),))
    else:
        target_rows = await db.fetchall("SELECT id FROM users WHERE is_banned=0")
    for u in target_rows:
        try:
            await bot.send_message(int(u["id"]), card("🚨 Store Alert", text, SHOP_NAME))
            sent += 1
            await asyncio.sleep(0.03)
        except Exception:
            failed += 1
    await db.execute("INSERT INTO alert_logs(id,audience,message,sent_count,failed,actor_id,created_at) VALUES(?,?,?,?,?,?,?)", (code("ALT"), audience, text[:1000], sent, failed, message.from_user.id, now()))
    await state.clear()
    await message.answer(card("✅ Super Alert Sent", f"Audience: <b>{esc(audience)}</b>\nSent: <b>{sent}</b>\nFailed: <b>{failed}</b>"), reply_markup=admin_home_kb())

@router.message(Command("vendor"))
async def v14_vendor_command(message: Message):
    await db.add_user(message)
    await message.answer(card("🏪 Seller/Vendor Panel", "Apply as seller/vendor or submit a product request for admin review."), reply_markup=kb([[btn("📝 Submit Vendor Request", "vendor:request")], [btn("🏠 Menu", "menu:main")]]))

@router.callback_query(F.data == "vendor:home")
async def v14_vendor_home(call: CallbackQuery):
    if not await v14_setting_on("vendor_enabled", "1"):
        return await call.answer("Vendor panel is temporarily disabled.", show_alert=True)
    mine = await db.fetchall("SELECT * FROM vendor_requests WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (call.from_user.id,))
    body = "🏪 <b>Seller/Vendor Center</b>\nSubmit product/seller request. Admin will review and approve.\n\n"
    if mine:
        body += "Your latest requests:\n" + "\n".join([f"• <code>{r['id']}</code> — {esc(r['status'])}" for r in mine])
    else:
        body += "No vendor request yet."
    await safe_edit(call.message, card("🏪 Vendor Panel", body), reply_markup=kb([[btn("📝 Submit Request", "vendor:request")], [btn("🏠 Menu", "menu:main")]]))
    await call.answer()

@router.callback_query(F.data == "vendor:request")
async def v14_vendor_request_start(call: CallbackQuery, state: FSMContext):
    if not await v14_setting_on("vendor_enabled", "1"):
        return await call.answer("Vendor panel is off.", show_alert=True)
    await state.set_state(V14State.vendor_request)
    await safe_edit(call.message, card("📝 Vendor Request", "Send details:\n• Your product/category\n• Price range\n• Stock/delivery style\n• Contact info\n• Any note for admin"), reply_markup=cancel_kb())
    await call.answer()

@router.message(V14State.vendor_request)
async def v14_vendor_request_save(message: Message, state: FSMContext, bot: Bot):
    rid = code("VEN")
    await db.execute("INSERT INTO vendor_requests(id,user_id,message,status,created_at,updated_at) VALUES(?,?,?,?,?,?)", (rid, message.from_user.id, message.html_text or message.text, "PENDING", now(), now()))
    await state.clear()
    await message.answer(card("✅ Vendor Request Sent", f"Request ID: <code>{rid}</code>\nAdmin will review soon."), reply_markup=main_menu(message.from_user.id))
    await v14_super_alert(bot, "vendor", "New Vendor Request", f"Request: <code>{rid}</code>\n{esc(preview_text(message.text or '', max_lines=4, max_chars=250))}", user_id=message.from_user.id)

@router.callback_query(F.data == "admin:vendors")
async def v14_admin_vendors(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    reqs = await db.fetchall("SELECT vr.*, u.first_name FROM vendor_requests vr LEFT JOIN users u ON u.id=vr.user_id ORDER BY vr.created_at DESC LIMIT 20")
    if not reqs:
        return await safe_edit(call.message, card("🏪 Vendor Requests", "No vendor/seller requests yet."), reply_markup=kb([[btn("⬅️ Admin", "admin:home")]]))
    body = "🏪 <b>Recent vendor requests</b>\n\n"
    buttons = []
    for r in reqs:
        body += f"• <code>{r['id']}</code> — {esc(r['status'])} — {esc(r['first_name'])} (<code>{r['user_id']}</code>)\n"
        buttons.append([btn(f"✅ Approve {r['id']}", f"vendor:approve:{r['id']}"), btn(f"❌ Reject", f"vendor:reject:{r['id']}")])
    buttons.append([btn("⬅️ Admin Home", "admin:home")])
    await safe_edit(call.message, card("🏪 Vendor/Seller Admin", body), reply_markup=kb(buttons))
    await call.answer()

@router.callback_query(F.data.startswith("vendor:approve:"))
async def v14_vendor_approve(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id): return
    rid = call.data.split(":", 2)[2]
    r = await db.fetchone("SELECT * FROM vendor_requests WHERE id=?", (rid,))
    if not r:
        return await call.answer("Request not found", show_alert=True)
    await db.execute("UPDATE vendor_requests SET status='APPROVED', admin_note=?, updated_at=? WHERE id=?", (f"Approved by {call.from_user.id}", now(), rid))
    await db.execute("UPDATE users SET role='vendor' WHERE id=? AND role='user'", (r["user_id"],))
    try:
        await bot.send_message(r["user_id"], card("✅ Vendor Request Approved", f"Request <code>{rid}</code> approved. You can now contact admin/support for product listing."))
    except Exception:
        pass
    await call.answer("Approved", show_alert=True)
    await v14_admin_vendors(call)

@router.callback_query(F.data.startswith("vendor:reject:"))
async def v14_vendor_reject(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id): return
    rid = call.data.split(":", 2)[2]
    r = await db.fetchone("SELECT * FROM vendor_requests WHERE id=?", (rid,))
    if not r:
        return await call.answer("Request not found", show_alert=True)
    await db.execute("UPDATE vendor_requests SET status='REJECTED', admin_note=?, updated_at=? WHERE id=?", (f"Rejected by {call.from_user.id}", now(), rid))
    try:
        await bot.send_message(r["user_id"], card("❌ Vendor Request Rejected", f"Request <code>{rid}</code> was rejected. You can submit again with clearer details."))
    except Exception:
        pass
    await call.answer("Rejected", show_alert=True)
    await v14_admin_vendors(call)

@router.callback_query(F.data == "fraud:blacklist")
async def v14_fraud_blacklist_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await state.set_state(V14State.blacklist_user)
    await safe_edit(call.message, card("🚫 Fraud Blacklist", "Send:\n<code>USER_ID | reason</code>\n\nThis will also ban the user from the shop."), reply_markup=cancel_kb())
    await call.answer()

@router.message(V14State.blacklist_user)
async def v14_fraud_blacklist_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    parts = [x.strip() for x in (message.text or "").split("|", 1)]
    if not parts or not parts[0].isdigit():
        return await message.answer("❌ Format: USER_ID | reason", reply_markup=cancel_kb())
    uid = int(parts[0])
    reason = parts[1] if len(parts) > 1 else "Fraud Shield Pro blacklist"
    await db.execute("INSERT OR REPLACE INTO fraud_blacklist(user_id,reason,actor_id,created_at) VALUES(?,?,?,?)", (uid, reason, message.from_user.id, now()))
    await db.execute("UPDATE users SET is_banned=1 WHERE id=?", (uid,))
    await state.clear()
    await message.answer(card("✅ Blacklisted", f"User: <code>{uid}</code>\nReason: {esc(reason)}"), reply_markup=admin_home_kb())

# Patch-friendly extra Fraud Center entry. Existing Fraud Guard callback remains primary.
@router.callback_query(F.data == "admin:fraudpro")
async def v14_fraud_pro(call: CallbackQuery):
    if not is_admin(call.from_user.id): return
    bl = await db.fetchall("SELECT * FROM fraud_blacklist ORDER BY created_at DESC LIMIT 10")
    body = "🛡 <b>Fraud Shield Pro</b>\n\n"
    body += f"Basic guard: <b>{'ON ✅' if await v14_setting_on('fraud_guard_enabled','1') else 'OFF ❌'}</b>\n"
    body += "\n🚫 <b>Blacklist</b>\n" + ("\n".join([f"• <code>{b['user_id']}</code> — {esc(preview_text(b['reason'], max_lines=1, max_chars=80))}" for b in bl]) if bl else "No blacklisted users yet.")
    await safe_edit(call.message, card("🛡 Fraud Shield Pro", body), reply_markup=kb([[btn("➕ Add Blacklist", "fraud:blacklist"), btn("⚙️ Basic Rule", "admin:fraud")], [btn("⬅️ Admin", "admin:home")]]))
    await call.answer()


# ═══════════════════════════════════════════════════════════════
#  V15 MONGODB CONTROL CENTER
# ═══════════════════════════════════════════════════════════════

@router.message(Command("mongo"))
async def cmd_mongo_status(message: Message):
    await db.add_user(message)
    if not is_admin(message.from_user.id):
        return await message.answer("Access denied.")
    if MONGO_ENABLED and not mongo.ready:
        await mongo.connect()
    body = await mongo.status_text()
    await message.answer(card("🍃 MongoDB Control Center", body), reply_markup=mongo_admin_kb())

@router.callback_query(F.data == "admin:mongodb")
async def admin_mongodb_panel(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    if MONGO_ENABLED and not mongo.ready:
        await mongo.connect()
    body = await mongo.status_text()
    body += "\n\n<b>V15 Hybrid Rule:</b> SQLite keeps local speed/stability; MongoDB keeps cloud mirror, backup, analytics and alerts."
    await safe_edit(call.message, card("🍃 MongoDB Control Center", body), reply_markup=mongo_admin_kb())
    await call.answer()

def mongo_admin_kb() -> InlineKeyboardMarkup:
    rows = [
        [btn("⚡ Full Sync Now", "mongo:sync"), btn("🧪 Test Ping", "mongo:test")],
        [btn("📊 Collection Counts", "mongo:counts"), btn("🧾 Sync Log", "mongo:log")],
        [btn("⬅️ Admin", "admin:home"), btn("🏠 Menu", "menu:main")],
    ]
    return kb(rows)

@router.callback_query(F.data == "mongo:test")
async def mongo_test_ping(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    ok = await mongo.connect()
    body = "Ping result: <b>Connected ✅</b>" if ok else f"Ping failed: <code>{esc(preview_text(mongo.error, max_lines=2, max_chars=220))}</code>"
    await safe_edit(call.message, card("🧪 MongoDB Ping Test", body), reply_markup=mongo_admin_kb())
    await call.answer("MongoDB tested", show_alert=False)

@router.callback_query(F.data == "mongo:sync")
async def mongo_manual_sync(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    if not MONGO_ENABLED:
        body = "MongoDB is disabled. Set <code>MONGO_ENABLED=1</code> and <code>MONGO_URI</code> in .env, then restart the bot."
        await safe_edit(call.message, card("🍃 MongoDB Sync", body), reply_markup=mongo_admin_kb())
        return await call.answer("MongoDB disabled", show_alert=True)
    if not mongo.ready:
        await mongo.connect()
    res = await mongo.full_sync_from_sqlite(db, reason=f"manual:{call.from_user.id}")
    if not res.get("ok"):
        body = f"Sync failed: <code>{esc(preview_text(res.get('error'), max_lines=3, max_chars=260))}</code>"
    else:
        summary = res.get("summary", {})
        top = "\n".join([f"• {esc(k)}: <b>{v}</b>" for k, v in summary.items() if v][:20]) or "No rows found yet."
        body = f"✅ Full sync completed.\nLast Sync: <b>{esc(res.get('last_sync'))}</b>\n\n{top}"
        await mongo.log_event("manual_sync", "Admin triggered MongoDB sync", {"actor_id": call.from_user.id, "summary": summary})
    await safe_edit(call.message, card("⚡ MongoDB Sync Engine", body), reply_markup=mongo_admin_kb())
    await call.answer("Sync completed" if res.get("ok") else "Sync failed", show_alert=not res.get("ok"))

@router.callback_query(F.data == "mongo:counts")
async def mongo_counts(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    if MONGO_ENABLED and not mongo.ready:
        await mongo.connect()
    counts = await mongo.collection_counts()
    body = "\n".join([f"• {esc(k)}: <b>{v}</b>" for k, v in counts.items()]) if counts else "MongoDB is not connected or no collections found."
    await safe_edit(call.message, card("📊 MongoDB Collections", body), reply_markup=mongo_admin_kb())
    await call.answer()

@router.callback_query(F.data == "mongo:log")
async def mongo_log(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    if MONGO_ENABLED and not mongo.ready:
        await mongo.connect()
    body = "No Mongo sync log yet."
    if mongo.ready:
        try:
            rows = await mongo.database.bot_sync_logs.find({}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(length=5)
            if rows:
                body = "\n\n".join([f"• <b>{esc(r.get('reason'))}</b> — {esc(r.get('created_at'))}\n{esc(preview_text(json.dumps(r.get('summary', {}), ensure_ascii=False), max_lines=2, max_chars=160))}" for r in rows])
        except Exception as e:
            body = f"Could not read sync log: <code>{esc(str(e))}</code>"
    await safe_edit(call.message, card("🧾 MongoDB Sync Log", body), reply_markup=mongo_admin_kb())
    await call.answer()

# ═══════════════════════════════════════════════════════════════
#  FALLBACK
# ═══════════════════════════════════════════════════════════════

@router.message()
async def fallback(message: Message):
    await db.add_user(message)
    maint = await db.get("maintenance")
    if maint == "1" and not is_admin(message.from_user.id):
        return await message.answer(card("🛠 Maintenance", "Shop is temporarily offline."))
    await message.answer(
        "Use /start to open the main menu.",
        reply_markup=main_menu(message.from_user.id)
    )


# ═══════════════════════════════════════════════════════════════
#  V21 FINAL AI STORE OS — EXTRA COMPACT PREMIUM LAYER
# ═══════════════════════════════════════════════════════════════

async def v21_store_stats(uid: int) -> tuple[str, InlineKeyboardMarkup]:
    """Build V23 premium store lobby: beautiful, readable, not overcrowded."""
    cats = await db.fetchone("SELECT COUNT(*) n FROM categories WHERE active=1")
    prods = await db.fetchone("SELECT COUNT(*) n FROM products WHERE active=1")
    stock = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE used=0")
    cart = await db.fetchone("SELECT COALESCE(SUM(qty),0) n FROM cart WHERE user_id=?", (uid,))
    orders = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE user_id=?", (uid,))
    u = await db.get_user(uid)
    bal = money(u["wallet"] if u else 0) if WALLET_ENABLED else "Off"
    featured = await db.fetchall(
        "SELECT p.*, c.emoji cat_emoji FROM products p LEFT JOIN categories c ON c.id=p.category_id "
        "WHERE p.active=1 ORDER BY p.featured DESC, p.sold DESC, p.created_at DESC LIMIT 5"
    )
    lines = [
        f"💼 Wallet: <b>{bal}</b>  •  🧺 Cart: <b>{cart['n'] if cart else 0}</b>  •  📦 Orders: <b>{orders['n'] if orders else 0}</b>",
        f"🛍 Products: <b>{prods['n'] if prods else 0}</b>  •  📁 Categories: <b>{cats['n'] if cats else 0}</b>  •  🔐 Ready Stock: <b>{stock['n'] if stock else 0}</b>",
    ]
    if featured:
        lines.append("\n<b>✨ Premium Featured Drops</b>")
        for p in featured:
            icon = p["cat_emoji"] or "💎"
            lines.append(f"{esc(icon)} <b>{esc(p['name'][:34])}</b> — {money(p['price'])}")
    else:
        lines.append("\n<i>No product added yet. Admin can add products from Admin Command OS.</i>")
    rows = [
        [btn("🛍 Browse", "shop:cats"), btn("🔥 Hot", "shop:hot")],
        [btn("🔎 Search", "shop:search"), btn("🤖 Ask AI", "ai:ask")],
        [btn("🧺 Cart", "cart:view"), btn("📦 Orders", "orders:mine")],
        [btn("💳 Pay OS", "pay:hub"), btn("🏠 Home", "menu:main")],
    ]
    return "\n".join(lines), kb(rows)

@router.callback_query(F.data == "shop:home")
async def v21_shop_home(call: CallbackQuery):
    if not await v14_setting_on("shop_open", "1") and not is_admin(call.from_user.id):
        return await safe_edit(call.message, await v14_shop_closed_text(), reply_markup=back_main())
    body, markup = await v21_store_stats(call.from_user.id)
    lines = [
        "Available digital products are grouped below.",
        "Use search or AI if you want the bot to find the best item for your budget.",
        "",
    ] + body.split("\n")[:10]
    await safe_edit(call.message, hypernova_card("🛍 Premium Store", "Browse products, choose quantity, pay exact amount and receive delivery.", lines, "Store • Cart • AI • Checkout", await db.get("v25_safe_turbo_mode") or V25_UI_MODE), reply_markup=markup)
    await call.answer()


@router.message(Command("store", "shop"))
async def v21_store_command(message: Message):
    await db.add_user(message)
    body, markup = await v21_store_stats(message.from_user.id)
    await message.answer(neon_card(f"💎 {SHOP_NAME}", "Store Hall — product, cart and AI buying flow", body.split("\n"), "Premium store lobby • smooth and readable"), reply_markup=markup)

@router.callback_query(F.data == "pay:hub")
async def v21_pay_hub(call: CallbackQuery):
    u = await db.get_user(call.from_user.id)
    balance = money(u["wallet"] if u else 0) if WALLET_ENABLED else "Disabled"
    methods = await db.fetchall("SELECT * FROM payment_methods WHERE active=1 ORDER BY sort_order, created_at DESC LIMIT 6")
    method_lines = []
    for m in methods:
        title = m["title"] or m["id"]
        method_lines.append(f"{method_icon(title, m['id'])} <b>{esc(title)}</b>")
    if not method_lines:
        method_lines.append("<i>Admin can add bKash/Nagad/Binance/USDT methods from Pay Methods.</i>")
    body = (
        f"💼 Wallet balance: <b>{balance}</b>\n"
        f"✅ Wallet purchases verify instantly from bot ledger.\n"
        f"🔐 External payments use exact amount + unique ref/TRX queue.\n\n"
        f"<b>Active Methods</b>\n" + "\n".join(method_lines[:6])
    )
    rows = [
        [btn("💳 Deposit", "wallet:topup"), btn("🧺 Cart Pay", "cart:view")],
        [btn("🛍 Store", "shop:home"), btn("📦 Orders", "orders:mine")],
        [btn("🏠 Home", "menu:main")],
    ]
    await safe_edit(call.message, neon_card("💳 Smart Pay OS", "Exact amount checkout with wallet autopay and external TRX queue", body.split("\n"), "Wallet = instant verify • external = exact amount + admin queue"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:finalos")
async def v21_admin_final_os(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    today0 = int(time.time() // 86400 * 86400)
    orders = await db.fetchone("SELECT COUNT(*) n, COALESCE(SUM(amount-discount),0) rev FROM orders WHERE created_at>=?", (today0,))
    pending = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE status IN ('WAITING_PROOF','WAITING_CONFIRM','PENDING','PROCESSING')")
    products = await db.fetchone("SELECT COUNT(*) n FROM products")
    stock = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE used=0")
    users = await db.fetchone("SELECT COUNT(*) n FROM users")
    payreq = await db.fetchone("SELECT COUNT(*) n FROM external_payment_requests WHERE status IN ('PENDING','PENDING_TRX')")
    tickets = await db.fetchone("SELECT COUNT(*) n FROM tickets WHERE status!='SOLVED'")
    mongo_state = "Connected" if mongo.ready else ("Fallback" if MONGO_ENABLED else "Off")
    body = (
        f"📈 Today: <b>{money(orders['rev'] if orders else 0)}</b>  •  🧾 <b>{orders['n'] if orders else 0}</b> orders\n"
        f"⏳ Pending: <b>{pending['n'] if pending else 0}</b>  •  💳 Pay Queue: <b>{payreq['n'] if payreq else 0}</b>  •  🎫 Tickets: <b>{tickets['n'] if tickets else 0}</b>\n"
        f"🛍 Products: <b>{products['n'] if products else 0}</b>  •  🔐 Stock: <b>{stock['n'] if stock else 0}</b>  •  👥 Users: <b>{users['n'] if users else 0}</b>\n"
        f"🍃 MongoDB: <b>{esc(mongo_state)}</b>\n\n"
        f"<i>Open only one control room at a time — this keeps mobile UI clean.</i>"
    )
    rows = [
        [btn("🧾 Approval Center", "admin:sec:orders"), btn("🛍 Catalog", "admin:sec:catalog")],
        [btn("💳 Pay Methods", "admin:paymethods"), btn("🔐 Delivery Vault", "admin:vault")],
        [btn("📊 Analytics", "admin:analytics"), btn("🚨 Alerts", "admin:v14alerts")],
        [btn("🍃 MongoDB", "admin:mongodb"), btn("🗄 Backup", "admin:backup")],
        [btn("⚙️ Settings", "admin:sec:system"), btn("🏠 User Home", "menu:main")],
    ]
    await safe_edit(call.message, neon_card("⚡ Admin Nexus OS", "Live command center for your whole digital shop", body.split("\n"), "V23 NeoLux • premium admin design • smooth controls"), reply_markup=kb(rows))
    await call.answer()


# ═══════════════════════════════════════════════════════════════
#  V23 NEOLUX STYLE STUDIO — EDIT WELCOME FROM BOT
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:style")
async def admin_style_studio(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    title = await db.get("premium_home_title") or SHOP_NAME
    subtitle = await db.get("premium_home_subtitle") or "Premium digital shop"
    footer = await db.get("shop_footer") or "NeoLux AI Store OS"
    lines = [
        f"🏷 Title: <b>{esc(preview_text(title, max_lines=1, max_chars=44))}</b>",
        f"📝 Subtitle: <i>{esc(preview_text(subtitle, max_lines=1, max_chars=64))}</i>",
        f"✨ Footer: <i>{esc(preview_text(footer, max_lines=1, max_chars=64))}</i>",
        "🎛 Change welcome text without touching code",
        "⚡ Smooth mode stays ON for fast callbacks",
    ]
    rows = [
        [btn("🏷 Edit Home Title", "style:edit:title")],
        [btn("📝 Edit Subtitle", "style:edit:subtitle")],
        [btn("✨ Edit Footer", "style:edit:footer")],
        [btn("👁 Preview Home", "menu:main"), btn("⬅️ Admin OS", "admin:home")],
    ]
    await safe_edit(call.message, neon_card("🎨 NeoLux Style Studio", "Premium text and brand control from bot panel", lines, "Make it beautiful without code edit"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data.startswith("style:edit:"))
async def style_edit_router(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    field = call.data.split(":")[-1]
    if field == "title":
        await state.set_state(TextEdit.home_title)
        prompt = "Send new premium home title. Example:\n<code>🌌 LUFFY STORE APEX ULTRA</code>"
    elif field == "subtitle":
        await state.set_state(TextEdit.home_subtitle)
        prompt = "Send new premium subtitle. Example:\n<code>Premium digital shop — AI guided buying, exact payment, instant delivery</code>"
    else:
        await state.set_state(TextEdit.home_footer)
        prompt = "Send new footer/tagline. Example:\n<code>NeoLux AI Store OS • smooth checkout • instant stock delivery</code>"
    await safe_edit(call.message, card("🎨 Style Studio", prompt), reply_markup=cancel_kb())
    await call.answer()

@router.message(TextEdit.home_title)
async def save_home_title(message: Message, state: FSMContext):
    await db.set("premium_home_title", preview_text(message.html_text, max_lines=1, max_chars=70))
    await state.clear()
    await message.answer(card("✅ Home Title Updated", "Your premium welcome title has been saved."), reply_markup=admin_home_kb())

@router.message(TextEdit.home_subtitle)
async def save_home_subtitle(message: Message, state: FSMContext):
    await db.set("premium_home_subtitle", preview_text(message.html_text, max_lines=2, max_chars=160))
    await state.clear()
    await message.answer(card("✅ Subtitle Updated", "Your welcome subtitle has been saved."), reply_markup=admin_home_kb())

@router.message(TextEdit.home_footer)
async def save_home_footer(message: Message, state: FSMContext):
    await db.set("shop_footer", preview_text(message.html_text, max_lines=2, max_chars=150))
    await state.clear()
    await message.answer(card("✅ Footer Updated", "Your premium footer/tagline has been saved."), reply_markup=admin_home_kb())


# ═══════════════════════════════════════════════════════════════
#  V24 QUANTUM AI STORE OS — FINAL PREMIUM FEATURE PACK
# ═══════════════════════════════════════════════════════════════

async def admin_action(actor_id: int, action: str, target: str = "", note: str = ""):
    if str(await db.get("v24_admin_action_log") or "1") != "1":
        return
    try:
        await db.execute(
            "INSERT INTO admin_action_logs(id,actor_id,action,target,note,created_at) VALUES(?,?,?,?,?,?)",
            (code("ACT"), actor_id, action, target, preview_text(note, max_lines=1, max_chars=180), now())
        )
    except Exception:
        pass

async def v24_admin_snapshot() -> tuple[list[str], InlineKeyboardMarkup]:
    today = now() - 86400
    sales = await db.fetchone("SELECT COUNT(*) n, COALESCE(SUM(amount-discount),0) rev FROM orders WHERE status IN ('DELIVERED','COMPLETED') AND updated_at>?", (today,))
    pending = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE status IN ('WAITING_PROOF','WAITING_CONFIRM','PENDING','PROCESSING')")
    payq = await db.fetchone("SELECT COUNT(*) n FROM external_payment_requests WHERE status NOT IN ('APPROVED','REJECTED','CANCELLED')")
    low = await db.fetchone("SELECT COUNT(*) n FROM products p WHERE p.delivery_mode='STOCK' AND p.active=1 AND (SELECT COUNT(*) FROM stock s WHERE s.product_id=p.id AND s.used=0)<=?", (await stock_alert_threshold(),))
    users = await db.fetchone("SELECT COUNT(*) n FROM users")
    vip = await db.fetchone("SELECT COUNT(*) n FROM users WHERE role='vip' OR vip_expires>0")
    tickets = await db.fetchone("SELECT COUNT(*) n FROM tickets WHERE status!='SOLVED'")
    fraud = await db.fetchone("SELECT COUNT(*) n FROM fraud_flags WHERE status='OPEN'")
    mongo_state = "Connected" if mongo.ready else ("Fallback" if MONGO_ENABLED else "Off")
    theme = QUANTUM_THEMES.get(await db.get("v24_theme") or "luxury_dark", QUANTUM_THEMES["luxury_dark"])
    lines = [
        f"📈 Today Sales: <b>{money(sales['rev'] if sales else 0)}</b>  •  🧾 Orders <b>{sales['n'] if sales else 0}</b>",
        f"⏳ Pending: <b>{pending['n'] if pending else 0}</b>  •  💳 Pay Queue <b>{payq['n'] if payq else 0}</b>  •  🎫 Tickets <b>{tickets['n'] if tickets else 0}</b>",
        f"🔐 Low Stock: <b>{low['n'] if low else 0}</b>  •  🛡 Fraud Flags <b>{fraud['n'] if fraud else 0}</b>",
        f"👥 Users: <b>{users['n'] if users else 0}</b>  •  💎 VIP <b>{vip['n'] if vip else 0}</b>  •  🍃 Mongo <b>{esc(mongo_state)}</b>",
        f"🎨 Theme: <b>{esc(theme['name'])}</b>  •  ⚡ Speed Engine 2.0 <b>{'ON' if await db.get('v24_speed_engine') == '1' else 'OFF'}</b>",
    ]
    rows = [
        [btn("✅ Approval Center", "admin:sec:orders"), btn("💳 Pay Queue", "admin:payments")],
        [btn("🎨 Theme Engine", "admin:v24theme"), btn("🧠 AI Brain", "admin:v24brain")],
        [btn("🛍 Products", "admin:v24products"), btn("⚡ Speed", "admin:v24speed")],
        [btn("🚨 Alerts", "admin:v24alerts"), btn("🛡 Security", "admin:v24security")],
        [btn("📊 Analytics", "admin:v24analytics"), btn("🧾 Receipts", "admin:v24invoices")],
        [btn("🧩 Plugins", "admin:v24plugins"), btn("🏪 Vendors", "admin:v24vendors")],
        [btn("🍃 MongoDB", "admin:mongodb"), btn("🏠 User Home", "menu:main")],
    ]
    return lines, kb(rows)

@router.callback_query(F.data == "admin:v24os")
async def v24_admin_os(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    lines, markup = await v24_admin_snapshot()
    await safe_edit(call.message, quantum_card("Quantum Admin OS", "Final premium operating system for your digital shop", lines, "All major controls are inside the bot panel.", await db.get("v24_theme") or "luxury_dark"), reply_markup=markup)
    await call.answer()

@router.message(Command("v24", "quantum"))
async def v24_command(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ Admin only.")
    lines, markup = await v24_admin_snapshot()
    await message.answer(quantum_card("Quantum Admin OS", "Final premium operating system for your digital shop", lines, "All major controls are inside the bot panel.", await db.get("v24_theme") or "luxury_dark"), reply_markup=markup)

@router.callback_query(F.data == "admin:v24theme")
async def v24_theme_engine(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    current = await db.get("v24_theme") or "luxury_dark"
    lines = []
    rows = []
    for key, meta in QUANTUM_THEMES.items():
        mark = "✅" if key == current else "▫️"
        lines.append(f"{mark} {meta['icon']} <b>{esc(meta['name'])}</b> — {esc(meta['accent'])}")
        rows.append([btn(f"{mark} {meta['icon']} {meta['name']}", f"v24theme:set:{key}")])
    rows += [[btn("🏷 Edit Title", "style:edit:title"), btn("📝 Subtitle", "style:edit:subtitle")], [btn("👁 Preview Home", "menu:main"), btn("⬅️ Quantum OS", "admin:v24os")]]
    await safe_edit(call.message, quantum_card("Theme Engine", "Change premium personality from admin panel", lines, "Telegram button colors cannot be changed, but theme text/layout/icon style can.", current), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data.startswith("v24theme:set:"))
async def v24_theme_set(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    key = call.data.split(":")[-1]
    if key not in QUANTUM_THEMES:
        return await call.answer("Theme not found.", show_alert=True)
    await db.set("v24_theme", key)
    await admin_action(call.from_user.id, "theme_changed", key, QUANTUM_THEMES[key]["name"])
    await call.answer(f"Theme set: {QUANTUM_THEMES[key]['name']}", show_alert=True)
    await v24_theme_engine(call)

@router.callback_query(F.data == "admin:v24welcome")
async def v24_welcome_journey(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    enabled = await db.get("v24_smart_journey") or "1"
    journey = await db.get("v24_welcome_journey_text") or "Browse, ask AI, pay exact amount and get delivery."
    lines = [
        f"🧭 Smart Journey: <b>{'ON' if enabled == '1' else 'OFF'}</b>",
        f"🏷 Title/Subtitles are editable from Style Studio",
        f"💼 Home card includes wallet/cart/orders/VIP/status",
        f"✨ Journey Text: <i>{esc(preview_text(journey, max_lines=2, max_chars=150))}</i>",
        "⚡ Loading animation can be ON for luxury mode or FAST_MODE for speed.",
    ]
    rows = [[btn("🔁 Toggle Journey", "v24:toggle:v24_smart_journey")], [btn("🏷 Edit Home Title", "style:edit:title"), btn("📝 Edit Subtitle", "style:edit:subtitle")], [btn("✨ Edit Footer", "style:edit:footer"), btn("👁 Preview", "menu:main")], [btn("⬅️ Quantum OS", "admin:v24os")]]
    await safe_edit(call.message, quantum_card("Smart Welcome Journey", "Not too tiny, not too crowded — premium first impression", lines, "Use FAST_MODE=1 for smooth speed or FAST_MODE=0 for motion effect.", await db.get("v24_theme") or "luxury_dark"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data.startswith("v24:toggle:"))
async def v24_toggle_setting(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    key = call.data.split(":", 2)[2]
    allowed = {
        "v24_smart_journey", "v24_product_showcase", "v24_ai_brain_pro", "v24_gateway_ready",
        "v24_speed_engine", "v24_receipts_enabled", "v24_security_shield", "v24_analytics_pro",
        "ai_assistant_enabled", "cart_enabled", "wallet_autopay_enabled", "stock_alerts_enabled", "vendor_enabled",
        "coupon_enabled", "redeem_enabled", "vip_enabled", "shop_open",
        "v25_welcome_studio_2", "v25_ai_brain_ultra", "v25_payment_intelligence_2",
        "v25_admin_control_center_pro", "v25_alert_automation_pro", "v25_receipt_invoice_pro",
        "v25_auto_cleanup_enabled", "v25_speed_core_lowram", "v25_smart_product_ranking"
    }
    if key not in allowed:
        return await call.answer("Setting not allowed.", show_alert=True)
    current = await db.get(key) or "0"
    new = "0" if current == "1" else "1"
    await db.set(key, new)
    await admin_action(call.from_user.id, "toggle", key, f"{current}->{new}")
    await call.answer(f"{key}: {'ON' if new=='1' else 'OFF'}", show_alert=True)
    # keep user on useful page
    if key.startswith("v24_"):
        return await v24_admin_os(call)
    return await v24_plugin_center(call)

@router.callback_query(F.data == "admin:v24products")
async def v24_product_showcase(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    products = await db.fetchone("SELECT COUNT(*) n FROM products WHERE active=1")
    stock = await db.fetchone("SELECT COUNT(*) n FROM stock WHERE used=0")
    featured = await db.fetchone("SELECT COUNT(*) n FROM products WHERE featured=1 AND active=1")
    no_stock = await db.fetchone("SELECT COUNT(*) n FROM products p WHERE p.active=1 AND p.delivery_mode='STOCK' AND (SELECT COUNT(*) FROM stock s WHERE s.product_id=p.id AND s.used=0)=0")
    lines = [
        f"🛍 Active Products: <b>{products['n'] if products else 0}</b>  •  ⭐ Featured <b>{featured['n'] if featured else 0}</b>",
        f"🔐 Ready Stock Lines: <b>{stock['n'] if stock else 0}</b>  •  🔴 Empty Stock Products <b>{no_stock['n'] if no_stock else 0}</b>",
        "💎 Product card shows badge, stock, rating, warranty, bulk note and exact checkout actions.",
        "🧺 Buy flow: Product → Quantity → Summary → Payment → Verify → Delivery.",
        "🔔 Stock watch lets users get restock alerts.",
    ]
    rows = [[btn("🛒 Product Manager", "admin:products"), btn("📁 Categories", "admin:cats")], [btn("🔐 Delivery Vault", "admin:vault"), btn("🔥 Hot Showcase", "shop:hot")], [btn("🔁 Toggle Showcase", "v24:toggle:v24_product_showcase"), btn("⬅️ Quantum OS", "admin:v24os")]]
    await safe_edit(call.message, quantum_card("Product Showcase 2.0", "Premium product experience without copying any bot", lines, "Use concise product names and premium descriptions for best look.", await db.get("v24_theme") or "luxury_dark"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:v24brain")
async def v24_ai_brain(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    logs = await db.fetchone("SELECT COUNT(*) n FROM ai_logs")
    products = await db.fetchone("SELECT COUNT(*) n FROM products WHERE active=1")
    lines = [
        f"🧠 AI Brain Pro: <b>{'ON' if await db.get('v24_ai_brain_pro') == '1' else 'OFF'}</b>",
        f"🔎 Searchable Products: <b>{products['n'] if products else 0}</b>  •  🧾 AI Logs <b>{logs['n'] if logs else 0}</b>",
        "💬 Understands Bangla/English mixed text and price/budget hints.",
        "🛍 Recommends products using name, category, description, price and stock.",
        "💳 Detects payment/wallet/order/support/VIP/coupon intent and routes users.",
    ]
    rows = [[btn("🧪 Test AI", "ai:ask"), btn("⚙️ AI Control", "admin:ai")], [btn("🔁 Toggle AI Brain", "v24:toggle:v24_ai_brain_pro"), btn("⬅️ Quantum OS", "admin:v24os")]]
    await safe_edit(call.message, quantum_card("AI Brain Pro", "Real smart local commerce assistant for your shop", lines, "For online LLM API later, this structure is ready to plug in.", await db.get("v24_theme") or "luxury_dark"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:v24gateway")
async def v24_gateway_ready(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    methods = await db.fetchall("SELECT * FROM payment_methods WHERE active=1 ORDER BY sort_order LIMIT 8")
    payq = await db.fetchone("SELECT COUNT(*) n FROM external_payment_requests WHERE status NOT IN ('APPROVED','REJECTED','CANCELLED')")
    method_lines = [f"{method_icon(m['title'], m['id'])} <b>{esc(m['title'])}</b> — <code>{esc(preview_text(m['account'], max_lines=1, max_chars=45))}</code>" for m in methods]
    if not method_lines:
        method_lines = ["No active payment methods yet."]
    lines = [
        f"💳 Gateway Ready Mode: <b>{'ON' if await db.get('v24_gateway_ready') == '1' else 'OFF'}</b>",
        f"📸 Pending External Queue: <b>{payq['n'] if payq else 0}</b>",
        "✅ Wallet payments are 100% auto verified from bot database ledger.",
        "🔐 External payments use exact amount + unique ref + TRX duplicate guard.",
        *method_lines[:5],
    ]
    rows = [[btn("💳 Pay Methods", "admin:paymethods"), btn("📸 Proof Queue", "admin:payments")], [btn("🧺 Cart Pay", "cart:view"), btn("💼 Pay Hub", "pay:hub")], [btn("🔁 Toggle Gateway Ready", "v24:toggle:v24_gateway_ready"), btn("⬅️ Quantum OS", "admin:v24os")]]
    await safe_edit(call.message, quantum_card("Real Payment Gateway Ready", "Wallet autopay now, official API plugin later", lines, "bKash/Nagad/Binance official API credentials can be plugged into gateway_attempts flow.", await db.get("v24_theme") or "luxury_dark"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:v24speed")
async def v24_speed_engine(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    cache = await db.get("speed_core_cache_seconds") or "30"
    lines = [
        f"⚡ Speed Engine 2.0: <b>{'ON' if await db.get('v24_speed_engine') == '1' else 'OFF'}</b>",
        f"🏎 FAST_MODE: <b>{'ON' if FAST_MODE else 'OFF'}</b>  •  Animation: <b>{'ON' if ANIMATION_ENABLED else 'OFF'}</b>",
        f"🧠 Settings Cache: <b>{esc(cache)} sec</b>  •  DB: <b>SQLite WAL + Mongo sync optional</b>",
        "🛡 Safe edit fallback handles message-not-modified and old callback errors.",
        "📣 Broadcast/admin alerts are throttled to reduce Telegram flood wait.",
    ]
    rows = [[btn("🔁 Toggle Speed Engine", "v24:toggle:v24_speed_engine"), btn("🗄 Backup", "admin:backup")], [btn("🍃 Mongo Sync", "mongo:sync"), btn("⬅️ Quantum OS", "admin:v24os")]]
    await safe_edit(call.message, quantum_card("Speed Engine 2.0", "Smooth performance core for high traffic shop bot", lines, "For maximum speed: FAST_MODE=1 and keep animation short.", await db.get("v24_theme") or "luxury_dark"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:v24plugins")
async def v24_plugin_center(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    keys = [
        ("shop_open", "🏪 Shop"), ("cart_enabled", "🧺 Cart"), ("wallet_autopay_enabled", "⚡ Wallet AutoPay"),
        ("ai_assistant_enabled", "🧠 AI"), ("coupon_enabled", "🎟 Coupon"), ("redeem_enabled", "🎁 Redeem"),
        ("vip_enabled", "💎 VIP"), ("vendor_enabled", "🏪 Vendor"), ("stock_alerts_enabled", "🔔 Stock Alerts"),
    ]
    lines, rows = [], []
    for key, name in keys:
        val = await db.get(key) or "0"
        lines.append(f"{'🟢' if val=='1' else '🔴'} <b>{name}</b> — {'ON' if val=='1' else 'OFF'}")
        rows.append([btn(f"{'🟢' if val=='1' else '🔴'} {name}", f"v24:toggle:{key}")])
    rows.append([btn("⚙️ Legacy Switches", "admin:plugins"), btn("⬅️ Quantum OS", "admin:v24os")])
    await safe_edit(call.message, quantum_card("Plugin Control Center", "Turn major systems ON/OFF from the bot", lines, "No code edit needed for core shop controls.", await db.get("v24_theme") or "luxury_dark"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:v24alerts")
async def v24_alert_hub(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    alerts = await db.fetchall("SELECT audience, COUNT(*) n FROM alert_logs GROUP BY audience ORDER BY n DESC LIMIT 6")
    recent = await db.fetchall("SELECT * FROM alert_logs ORDER BY created_at DESC LIMIT 4")
    lines = ["🚨 Smart Alert Hub separates urgent/admin/user/VIP/payment/stock alerts."]
    for a in alerts:
        lines.append(f"• {esc(a['audience'])}: <b>{a['n']}</b>")
    for r in recent:
        lines.append(f"🕒 {esc(preview_text(r['message'], max_lines=1, max_chars=55))}")
    rows = [[btn("📣 Send Alert", "admin:v14alerts"), btn("🔎 Low Stock", "admin:alerts:low")], [btn("🔁 Toggle Alerts", "v24:toggle:stock_alerts_enabled"), btn("⬅️ Quantum OS", "admin:v24os")]]
    await safe_edit(call.message, quantum_card("Smart Alert Hub", "Order, payment, stock, fraud, ticket and vendor signals", lines, "Users get stock alerts; admins get business-critical alerts.", await db.get("v24_theme") or "luxury_dark"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:v24analytics")
async def v24_analytics_pro(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    d1, d7, d30 = now()-86400, now()-7*86400, now()-30*86400
    rev1 = await db.fetchone("SELECT COALESCE(SUM(amount-discount),0) s, COUNT(*) n FROM orders WHERE status IN ('DELIVERED','COMPLETED') AND updated_at>?", (d1,))
    rev7 = await db.fetchone("SELECT COALESCE(SUM(amount-discount),0) s, COUNT(*) n FROM orders WHERE status IN ('DELIVERED','COMPLETED') AND updated_at>?", (d7,))
    rev30 = await db.fetchone("SELECT COALESCE(SUM(amount-discount),0) s, COUNT(*) n FROM orders WHERE status IN ('DELIVERED','COMPLETED') AND updated_at>?", (d30,))
    top = await db.fetchall("SELECT name,sold FROM products ORDER BY sold DESC LIMIT 5")
    users = await db.fetchone("SELECT COUNT(*) n FROM users WHERE joined_at>?", (d7,))
    cart = await db.fetchone("SELECT COUNT(*) n FROM cart")
    lines = [
        f"📅 Today: <b>{money(rev1['s'] if rev1 else 0)}</b> / <b>{rev1['n'] if rev1 else 0}</b> orders",
        f"📈 7 Days: <b>{money(rev7['s'] if rev7 else 0)}</b> / <b>{rev7['n'] if rev7 else 0}</b> orders",
        f"🗓 30 Days: <b>{money(rev30['s'] if rev30 else 0)}</b> / <b>{rev30['n'] if rev30 else 0}</b> orders",
        f"👥 New Users 7d: <b>{users['n'] if users else 0}</b>  •  🧺 Cart Lines <b>{cart['n'] if cart else 0}</b>",
    ]
    if top:
        lines.append("🏆 Top Products:")
        for p in top:
            lines.append(f"• {esc(p['name'][:28])}: <b>{p['sold']}</b> sold")
    rows = [[btn("📈 Legacy Analytics", "admin:analytics"), btn("🧬 Insights", "admin:insights")], [btn("🔁 Toggle Analytics", "v24:toggle:v24_analytics_pro"), btn("⬅️ Quantum OS", "admin:v24os")]]
    await safe_edit(call.message, quantum_card("Analytics Pro", "Sales, users, product ranking and conversion hints", lines, "Use this dashboard daily before restocking or broadcasting.", await db.get("v24_theme") or "luxury_dark"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:v24invoices")
async def v24_invoice_center(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    delivered = await db.fetchall("SELECT o.*, p.name FROM orders o LEFT JOIN products p ON p.id=o.product_id WHERE o.status IN ('DELIVERED','COMPLETED') ORDER BY o.updated_at DESC LIMIT 5")
    count = await db.fetchone("SELECT COUNT(*) n FROM invoice_receipts")
    lines = [f"🧾 Receipt Engine: <b>{'ON' if await db.get('v24_receipts_enabled') == '1' else 'OFF'}</b>", f"📚 Saved Receipt Rows: <b>{count['n'] if count else 0}</b>"]
    if delivered:
        lines.append("Recent delivered orders:")
        for o in delivered:
            lines.append(f"• <code>{esc(o['id'])}</code> — {esc(o['name'] or 'Product')} — {money(float(o['amount'] or 0)-float(o['discount'] or 0))}")
    rows = [[btn("📦 Orders", "admin:orders"), btn("📤 Export", "admin:export")], [btn("🔁 Toggle Receipts", "v24:toggle:v24_receipts_enabled"), btn("⬅️ Quantum OS", "admin:v24os")]]
    await safe_edit(call.message, quantum_card("Invoice + Receipt System", "Beautiful post-delivery receipts for trust and support", lines, "User can open each order details as receipt from order history.", await db.get("v24_theme") or "luxury_dark"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:v24security")
async def v24_security_shield(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    fraud = await db.fetchone("SELECT COUNT(*) n FROM fraud_flags WHERE status='OPEN'")
    banned = await db.fetchone("SELECT COUNT(*) n FROM users WHERE is_banned=1")
    dupe_trx = await db.fetchone("SELECT COUNT(*) n FROM external_payment_requests GROUP BY method,trx_id HAVING COUNT(*)>1 LIMIT 1")
    actions = await db.fetchone("SELECT COUNT(*) n FROM admin_action_logs")
    lines = [
        f"🛡 Security Shield: <b>{'ON' if await db.get('v24_security_shield') == '1' else 'OFF'}</b>",
        f"🚨 Open Fraud Flags: <b>{fraud['n'] if fraud else 0}</b>  •  🚫 Banned Users <b>{banned['n'] if banned else 0}</b>",
        f"🔁 Duplicate TRX monitor: <b>{'flagged' if dupe_trx else 'clean'}</b>",
        f"🧾 Admin Action Logs: <b>{actions['n'] if actions else 0}</b>",
        "⚡ Spam click throttle and banned-user middleware are active.",
    ]
    rows = [[btn("🛡 Fraud Shield", "admin:fraudpro"), btn("🚫 Ban Control", "admin:bans")], [btn("🔁 Toggle Security", "v24:toggle:v24_security_shield"), btn("⬅️ Quantum OS", "admin:v24os")]]
    await safe_edit(call.message, quantum_card("Security Shield", "Fraud, duplicate TRX, blacklist and admin action protection", lines, "Security stays strict but does not slow down normal users.", await db.get("v24_theme") or "luxury_dark"), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:v24vendors")
async def v24_vendor_pro(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    pending = await db.fetchone("SELECT COUNT(*) n FROM vendor_requests WHERE status='PENDING'")
    total = await db.fetchone("SELECT COUNT(*) n FROM vendor_requests")
    lines = [
        f"🏪 Vendor/Seller Pro: <b>{'ON' if await db.get('vendor_enabled') == '1' else 'OFF'}</b>",
        f"⏳ Pending Requests: <b>{pending['n'] if pending else 0}</b>  •  Total <b>{total['n'] if total else 0}</b>",
        "Seller can request access; admin reviews before anything appears in shop.",
        "This keeps the marketplace advanced but safe.",
    ]
    rows = [[btn("🏪 Vendor Queue", "admin:vendors"), btn("🛍 Products", "admin:products")], [btn("🔁 Toggle Vendor", "v24:toggle:vendor_enabled"), btn("⬅️ Quantum OS", "admin:v24os")]]
    await safe_edit(call.message, quantum_card("Vendor/Seller Pro", "Seller workflow with admin approval", lines, "Good for future multi-seller digital shop growth.", await db.get("v24_theme") or "luxury_dark"), reply_markup=kb(rows))
    await call.answer()


# ═══════════════════════════════════════════════════════════════
#  V25 HYPERNOVA AI COMMERCE OS
# ═══════════════════════════════════════════════════════════════

async def v25_admin_snapshot():
    today = int(time.time()) - 86400
    sales = await db.fetchone("SELECT COALESCE(SUM(amount-discount),0) rev, COUNT(*) n FROM orders WHERE created_at>=?", (today,))
    pending = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE status IN ('WAITING_PROOF','WAITING_CONFIRM','PENDING','PROCESSING')")
    payq = await db.fetchone("SELECT COUNT(*) n FROM external_payment_requests WHERE status NOT IN ('APPROVED','REJECTED','CANCELLED')")
    low = await db.fetchone("SELECT COUNT(*) n FROM products p WHERE p.delivery_mode='STOCK' AND p.active=1 AND (SELECT COUNT(*) FROM stock s WHERE s.product_id=p.id AND s.used=0)<=?", (await stock_alert_threshold(),))
    users = await db.fetchone("SELECT COUNT(*) n FROM users")
    mode = await db.get("v25_safe_turbo_mode") or V25_UI_MODE
    mongo_state = "Connected" if mongo.ready else ("Fallback" if MONGO_ENABLED else "Off")
    lines = [
        "<b>📊 Today</b>",
        f"Sales: <b>{money(sales['rev'] if sales else 0)}</b>  •  Orders: <b>{sales['n'] if sales else 0}</b>",
        "",
        "<b>🧾 Queue</b>",
        f"Pending Orders: <b>{pending['n'] if pending else 0}</b>  •  Payments: <b>{payq['n'] if payq else 0}</b>  •  Low Stock: <b>{low['n'] if low else 0}</b>",
        "",
        "<b>⚙️ System</b>",
        f"Users: <b>{users['n'] if users else 0}</b>  •  MongoDB: <b>{esc(mongo_state)}</b>  •  Mode: <b>{esc(v25_mode_meta(mode)['name'])}</b>",
    ]
    rows = [
        [btn("📊 Dashboard", "admin:v25os"), btn("📦 Orders", "admin:sec:orders")],
        [btn("🛍 Products", "admin:v24products"), btn("💳 Payments", "admin:v25pay")],
        [btn("👥 Users", "admin:sec:users"), btn("🚨 Alerts", "admin:v24alerts")],
        [btn("🤖 AI Control", "admin:v25ai"), btn("⚙️ System", "admin:sec:system")],
        [btn("🎨 Style Studio", "admin:v25welcome"), btn("🚀 Performance", "admin:v25mode")],
        [btn("🏠 User Menu", "menu:main")],
    ]
    return lines, kb(rows)


@router.callback_query(F.data == "admin:v25os")
async def v25_admin_os(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin only.", show_alert=True)
    lines, markup = await v25_admin_snapshot()
    await safe_edit(call.message, hypernova_card("V26 Admin Studio", "Page-based command center for premium store control", lines, "Dashboard • Orders • Products • Payments • AI • System", await db.get("v25_safe_turbo_mode") or V25_UI_MODE), reply_markup=markup)
    await call.answer()

@router.message(Command("v25", "v26", "hypernova"))
async def v25_command(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ Admin only.")
    lines, markup = await v25_admin_snapshot()
    await message.answer(hypernova_card("V26 Admin Studio", "Page-based command center for premium store control", lines, "Dashboard • Orders • Products • Payments • AI • System", await db.get("v25_safe_turbo_mode") or V25_UI_MODE), reply_markup=markup)

@router.callback_query(F.data == "v25:mode")
async def v25_user_mode(call: CallbackQuery):
    mode = await db.get("v25_safe_turbo_mode") or V25_UI_MODE
    meta = v25_mode_meta(mode)
    lines = [
        f"Current: <b>{esc(meta['name'])}</b>",
        "Turbo: fastest, low animation, best for 1GB VPS.",
        "Balanced: premium look with smooth performance.",
        "Luxury: richer animation and text for stronger VPS.",
    ]
    await safe_edit(call.message, hypernova_card("🚀 Performance Mode", "Choose how your bot should feel.", lines, "Admin can change the default from Admin Studio.", mode), reply_markup=kb([[btn("🏠 Back Home", "menu:main")]]))
    await call.answer()


@router.callback_query(F.data == "admin:v25mode")
async def v25_mode_center(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    current = await db.get("v25_safe_turbo_mode") or V25_UI_MODE
    lines = []
    rows = []
    for key, meta in V25_MODES.items():
        mark = "✅" if key == current else "▫️"
        lines.append(f"{mark} {meta['icon']} <b>{esc(meta['name'])}</b> — {esc(meta['desc'])}")
        rows.append([btn(f"{mark} {meta['icon']} {meta['name']}", f"v25mode:set:{key}")])
    rows += [[btn("🧹 Cleanup", "admin:v25cleanup"), btn("⬅️ HyperNova OS", "admin:v25os")]]
    await safe_edit(call.message, hypernova_card("Turbo / Balanced / Luxury Mode", "Control beauty vs speed directly from the bot", lines, "For 1GB VPS, Balanced or Turbo is best.", current), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data.startswith("v25mode:set:"))
async def v25_mode_set(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    mode = call.data.split(":")[-1]
    if mode not in V25_MODES:
        return await call.answer("Unknown mode.", show_alert=True)
    await db.set("v25_safe_turbo_mode", mode)
    await db.set("premium_animation_enabled", "0" if mode == "turbo" else "1")
    await db.set("speed_core_cache_seconds", "120" if mode == "turbo" else ("60" if mode == "balanced" else "30"))
    await admin_action(call.from_user.id, "v25_mode", mode, V25_MODES[mode]["desc"])
    await call.answer(f"Mode set: {V25_MODES[mode]['name']}", show_alert=True)
    await v25_mode_center(call)

@router.callback_query(F.data == "admin:v25welcome")
async def v25_welcome_studio(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    title = await db.get('v25_home_title') or await db.get('premium_home_title') or 'LUFFY HYPERNOVA AI STORE'
    sub = await db.get('v25_home_subtitle') or 'Premium AI commerce experience for instant digital delivery.'
    lines = [
        "<b>Current Welcome</b>",
        f"Title: <b>{esc(preview_text(title, max_lines=1, max_chars=46))}</b>",
        f"Subtitle: <i>{esc(preview_text(sub, max_lines=1, max_chars=80))}</i>",
        "",
        "Use these controls to change your bot look without touching code.",
    ]
    rows = [
        [btn("🏷 Edit Title", "style:edit:title"), btn("📝 Edit Subtitle", "style:edit:subtitle")],
        [btn("🧾 Edit Footer", "style:edit:footer"), btn("👁 Preview Home", "menu:main")],
        [btn("🚀 Performance", "admin:v25mode"), btn("⬅️ Admin Studio", "admin:v25os")],
    ]
    await safe_edit(call.message, hypernova_card("🎨 Style Studio", "Premium welcome, footer and layout control.", lines, "Beautiful, readable and mobile safe.", await db.get("v25_safe_turbo_mode") or V25_UI_MODE), reply_markup=kb(rows))
    await call.answer()


@router.callback_query(F.data == "admin:v25ai")
async def v25_ai_ultra(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    logs = await db.fetchone("SELECT COUNT(*) n FROM ai_logs")
    products = await db.fetchone("SELECT COUNT(*) n FROM products WHERE active=1")
    lines = [
        f"🧠 AI Brain Ultra: <b>{'ON' if await db.get('v25_ai_brain_ultra') == '1' else 'OFF'}</b>",
        f"🔎 Active Products: <b>{products['n'] if products else 0}</b> • AI Logs <b>{logs['n'] if logs else 0}</b>",
        "💬 Understands Bangla/English mixed product, budget, order and wallet intents.",
        "🛍 Uses product name/category/price/stock to suggest smarter items.",
        "⚡ Local semantic style = no external API cost and low latency.",
    ]
    rows = [[btn("🤖 Test AI", "ai:ask"), btn("🔁 Toggle AI", "v24:toggle:v25_ai_brain_ultra")], [btn("🔎 Product Search", "shop:search"), btn("⬅️ HyperNova OS", "admin:v25os")]]
    await safe_edit(call.message, hypernova_card("AI Brain Ultra", "Real smart assistant feel without heavy server load", lines, "Add better product names/descriptions for better AI suggestions.", await db.get("v25_safe_turbo_mode") or V25_UI_MODE), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:v25pay")
async def v25_payment_intelligence(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    pending = await db.fetchone("SELECT COUNT(*) n FROM external_payment_requests WHERE status NOT IN ('APPROVED','REJECTED','CANCELLED')")
    methods = await db.fetchone("SELECT COUNT(*) n FROM payment_methods WHERE active=1")
    wallet_orders = await db.fetchone("SELECT COUNT(*) n FROM orders WHERE autopay=1")
    lines = [
        f"💳 Payment Intelligence 2.0: <b>{'ON' if await db.get('v25_payment_intelligence_2') == '1' else 'OFF'}</b>",
        f"✅ Wallet AutoPay Orders: <b>{wallet_orders['n'] if wallet_orders else 0}</b> • Active Methods <b>{methods['n'] if methods else 0}</b>",
        f"⏳ External Pay Queue: <b>{pending['n'] if pending else 0}</b>",
        "💼 Wallet = 100% internal verification + auto delivery.",
        "🌐 External bKash/Nagad/Crypto = exact amount + unique ref + TRX queue unless official API is added.",
    ]
    rows = [[btn("💳 Pay Methods", "admin:paymethods"), btn("📸 Pay Queue", "admin:payments")], [btn("🔁 Toggle Pay Intel", "v24:toggle:v25_payment_intelligence_2"), btn("⬅️ HyperNova OS", "admin:v25os")]]
    await safe_edit(call.message, hypernova_card("Payment Intelligence 2.0", "Exact amount payment, duplicate TRX guard and auto-delivery flow", lines, "Official gateway API can be plugged in later.", await db.get("v25_safe_turbo_mode") or V25_UI_MODE), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "admin:v25cleanup")
async def v25_cleanup_center(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    ai = await db.fetchone("SELECT COUNT(*) n FROM ai_logs")
    alerts = await db.fetchone("SELECT COUNT(*) n FROM alert_logs")
    plugins = await db.fetchone("SELECT COUNT(*) n FROM plugin_logs")
    lines = [
        f"🧹 Auto Cleanup: <b>{'ON' if await db.get('v25_auto_cleanup_enabled') == '1' else 'OFF'}</b>",
        f"🧠 AI logs <b>{ai['n'] if ai else 0}</b> • 🚨 Alerts <b>{alerts['n'] if alerts else 0}</b> • 🧩 Plugin logs <b>{plugins['n'] if plugins else 0}</b>",
        f"🗓 Cleanup window: <b>{V25_CLEANUP_DAYS} days</b>",
        "⚡ Keeps 1GB VPS smoother by cleaning old non-critical logs.",
        "🔐 Does not delete users, products, orders, wallet, receipts or stock.",
    ]
    rows = [[btn("🧹 Run Cleanup Now", "v25cleanup:run"), btn("🔁 Toggle Cleanup", "v24:toggle:v25_auto_cleanup_enabled")], [btn("⚙️ Mode Center", "admin:v25mode"), btn("⬅️ HyperNova OS", "admin:v25os")]]
    await safe_edit(call.message, hypernova_card("Auto Cleanup System", "Smooth low-RAM maintenance without losing important data", lines, "Best for small VPS hosting.", await db.get("v25_safe_turbo_mode") or V25_UI_MODE), reply_markup=kb(rows))
    await call.answer()

@router.callback_query(F.data == "v25cleanup:run")
async def v25_cleanup_run(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Admin only.", show_alert=True)
    await v25_autocleanup_once()
    await call.answer("Cleanup completed ✅", show_alert=True)
    await v25_cleanup_center(call)


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

async def setup_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Open premium home"),
        BotCommand(command="menu", description="Open premium menu"),
        BotCommand(command="store", description="Open premium store"),
        BotCommand(command="panel", description="Admin Studio"),
        BotCommand(command="v26", description="Admin V26 command center"),
        BotCommand(command="redeem", description="Redeem reward code"),
        BotCommand(command="ai", description="Ask AI shop assistant"),
        BotCommand(command="track", description="Track order status"),
        BotCommand(command="cart", description="Open smart cart"),
        BotCommand(command="vendor", description="Seller/vendor request"),
        BotCommand(command="mongo", description="Admin MongoDB control"),
        BotCommand(command="cancel", description="Cancel current action"),
    ]
    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        logger.warning("Could not set bot commands: %s", e)

async def main():
    await db.connect()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # Avoid webhook conflict and old pending update burst.
    await bot.delete_webhook(drop_pending_updates=True)
    await setup_bot_commands(bot)
    await v25_autocleanup_once()

    me = await bot.get_me()
    print(f"{'='*55}")
    print(f"  {SHOP_NAME} — {APP_VERSION}")
    print(f"  Bot: @{me.username}")
    print(f"  Admins: {all_admin_ids()}")
    print(f"  Wallet: {'Enabled' if WALLET_ENABLED else 'Disabled'}")
    print(f"  V25 HyperNova Welcome Studio + Smooth Core: Enabled")
    print(f"  User stock alerts: Enabled")
    print(f"  AI Brain Ultra + Search Assistant: Enabled")
    print(f"  Smart Cart + Smart Pay OS + Wallet AutoPay: Enabled")
    print(f"  Vendor Panel + Fraud Shield Pro + Auto Cleanup: Enabled")
    print(f"  MongoDB: {'Connected' if mongo.ready else ('Enabled fallback' if MONGO_ENABLED else 'Disabled')}")
    print(f"{'='*55}")

    # Safe polling loop: protects hosting panels from Telegram RetryAfter / Bad Gateway loops.
    while True:
        try:
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                polling_timeout=30,
            )
        except TelegramRetryAfter as e:
            wait_time = int(getattr(e, "retry_after", 5)) + 3
            print(f"⚠️ Flood control. Sleeping {wait_time}s...")
            await asyncio.sleep(wait_time)
        except TelegramServerError:
            print("⚠️ Telegram Bad Gateway. Sleeping 15s...")
            await asyncio.sleep(15)
        except TelegramNetworkError:
            print("⚠️ Network error. Sleeping 10s...")
            await asyncio.sleep(10)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Polling error: {e}")
            await asyncio.sleep(10)

    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
