"""
Emoji & premium custom-emoji helpers.

Telegram premium (custom) emojis are rendered with the <tg-emoji> HTML tag:
    <tg-emoji emoji-id="5368324170671202286">👍</tg-emoji>

Custom emoji IDs only render for Premium users / when the bot is allowed to use
them. We always provide a safe unicode fallback inside the tag, so non-premium
clients still see a normal emoji. Admins can override IDs in-bot (Settings),
which get stored in the DB and merged over these defaults at runtime.
"""
from __future__ import annotations

# Plain unicode emojis used across the UI (always safe)
E = {
    "fire": "🔥",
    "star": "⭐",
    "stars": "✨",
    "cart": "🛒",
    "bag": "🛍️",
    "money": "💰",
    "card": "💳",
    "wallet": "👛",
    "crypto": "🪙",
    "gem": "💎",
    "rocket": "🚀",
    "check": "✅",
    "cross": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "bell": "🔔",
    "gift": "🎁",
    "crown": "👑",
    "lock": "🔒",
    "key": "🗝️",
    "tv": "📺",
    "robot": "🤖",
    "music": "🎵",
    "film": "🎬",
    "play": "▶️",
    "back": "⬅️",
    "home": "🏠",
    "refresh": "🔄",
    "user": "👤",
    "users": "👥",
    "admin": "🛠️",
    "box": "📦",
    "list": "📋",
    "pencil": "✏️",
    "trash": "🗑️",
    "plus": "➕",
    "minus": "➖",
    "clock": "🕐",
    "calendar": "📅",
    "chart": "📈",
    "megaphone": "📣",
    "settings": "⚙️",
    "search": "🔎",
    "tag": "🏷️",
    "receipt": "🧾",
    "hourglass": "⏳",
    "sparkle_heart": "💖",
    "thumbs_up": "👍",
    "support": "🆘",
    "link": "🔗",
    "down": "⬇️",
    "up": "⬆️",
}

# Default premium custom-emoji IDs (admins can override these in-bot).
# Map a logical name -> (custom_emoji_id, unicode_fallback).
# NOTE: These are placeholder IDs; replace via Admin > Settings > Custom Emojis.
PREMIUM_DEFAULTS: dict[str, tuple[str, str]] = {
    "fire": ("5420315771991497307", "🔥"),
    "crown": ("5384360852713224011", "👑"),
    "gem": ("5377498341074542641", "💎"),
    "rocket": ("5377706399873520202", "🚀"),
    "check": ("5427009714745517609", "✅"),
    "money": ("5424972470023104089", "💰"),
}

# Logical names that admins can attach a premium custom-emoji ID to, in-bot.
PREMIUM_KEYS: list[str] = ["crown", "fire", "gem", "rocket", "check", "money", "star", "gift"]

# Runtime overrides loaded from DB settings (logical name -> custom_emoji_id)
_premium_overrides: dict[str, str] = {}


def set_premium_overrides(overrides: dict[str, str]) -> None:
    """Replace the in-memory premium emoji ID overrides (called on startup / settings save)."""
    global _premium_overrides
    _premium_overrides = {k: v for k, v in (overrides or {}).items() if v}


def get_premium_overrides() -> dict[str, str]:
    """Return a copy of the current in-memory premium emoji ID overrides."""
    return dict(_premium_overrides)


def set_one_override(name: str, emoji_id: str | None) -> None:
    """Set or clear a single premium emoji override in memory."""
    if emoji_id:
        _premium_overrides[name] = emoji_id
    else:
        _premium_overrides.pop(name, None)


def effective_emoji_id(name: str) -> str | None:
    """Return the custom emoji ID that will currently be used for a logical name."""
    if name in _premium_overrides:
        return _premium_overrides[name]
    if name in PREMIUM_DEFAULTS:
        return PREMIUM_DEFAULTS[name][0]
    return None


def premium(name: str) -> str:
    """
    Return an HTML <tg-emoji> tag for a logical premium emoji name, with a safe
    unicode fallback. Falls back to a plain unicode emoji if name is unknown.
    """
    fallback = E.get(name, "✨")
    emoji_id = _premium_overrides.get(name)
    if not emoji_id and name in PREMIUM_DEFAULTS:
        emoji_id, fallback = PREMIUM_DEFAULTS[name]
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback


def e(name: str) -> str:
    """Shortcut to fetch a plain unicode emoji by name."""
    return E.get(name, "")
