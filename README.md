# Premium OTT Subscription Shop Bot

An advanced Telegram shop bot (aiogram 3 + MongoDB) for selling OTT & AI
subscriptions (ChatGPT Plus, Netflix, Spotify, etc.). Full in-bot admin control,
colorful emoji-accented buttons, premium/custom emoji support, wallet system,
referrals, and hybrid delivery.

## Features

**For buyers**
- Browse categories and products with live stock display
- Buy with **Wallet balance**, **Telegram Stars**, or **USDT** (TRC20/BEP20)
- Reloadable wallet (top up via USDT proof or Stars)
- Order history with delivered details
- Refer & earn rewards
- Optional force-join channel gate

**For admins (fully in-bot, no code needed)**
- Live statistics & revenue
- Categories & products CRUD
- Stock management (bulk add, one item per line)
- Approve / reject USDT orders & top-ups (with proof screenshots)
- Auto delivery from stock, manual fallback when out of stock
- User management: adjust balance, top buyers, ban/unban
- Broadcast to all users
- Settings: shop name, welcome text, support, USDT addresses, Stars rate,
  referral reward, force-join channel, open/close shop, custom emoji IDs

## Setup

1. **Install dependencies**
   ```bash
   uv venv .venv
   uv pip install --python .venv/bin/python -r requirements.txt
   ```

2. **Configure environment** — create `.env.development.local` (or set real env vars):
   ```
   BOT_TOKEN=123456:your-token-from-BotFather
   MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net
   DB_NAME=ott_shop_bot
   ADMIN_IDS=111111111,222222222
   ```
   - `BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
   - `MONGODB_URI` — e.g. a free MongoDB Atlas cluster
   - `ADMIN_IDS` — your numeric Telegram ID(s), comma-separated (get it from [@userinfobot](https://t.me/userinfobot))

3. **Run the bot**
   ```bash
   .venv/bin/python -m bot.main
   ```

4. Open your bot, send `/start`. Admins use `/admin` (or the Admin Panel button).

## Telegram Stars & Premium Emojis

- **Stars** payments work out of the box (no payment provider token needed).
  Set the conversion rate in *Admin → Settings → Stars / Unit*.
- **Premium/custom emojis** render via `<tg-emoji>` tags with safe unicode
  fallbacks. Replace the default emoji IDs in `bot/emojis.py` or via settings.

## Project structure

```
bot/
  config.py        # env + defaults
  db.py            # MongoDB (motor) data layer
  emojis.py        # unicode + premium custom emojis
  keyboards.py     # inline keyboards
  states.py        # FSM states
  utils.py         # delivery, admin notify, helpers
  main.py          # entrypoint (python -m bot.main)
  handlers/
    start.py       # /start, menu, referral, about, support
    shop.py        # categories, products, checkout
    payments.py    # wallet / Stars / USDT payments + delivery
    wallet.py      # balance & top-ups
    orders.py      # user order history
    admin.py       # full admin panel
```
