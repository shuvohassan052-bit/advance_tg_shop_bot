"""
MongoDB data-access layer (async via motor).

Collections:
  users       - bot users, balance, referral info
  categories  - product categories
  products    - subscription products
  stock       - delivery items (codes/accounts) tied to a product
  orders      - purchase records (pending/approved/rejected/delivered)
  topups      - wallet top-up requests (USDT / Stars)
  settings    - single document holding editable bot settings
"""
from __future__ import annotations

import time
from typing import Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from . import config

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def now() -> int:
    return int(time.time())


def oid(value: str) -> Optional[ObjectId]:
    try:
        return ObjectId(value)
    except Exception:
        return None


async def init_db() -> None:
    """Connect to MongoDB and ensure indexes + default settings."""
    global _client, _db
    _client = AsyncIOMotorClient(config.MONGODB_URI, serverSelectionTimeoutMS=8000)
    _db = _client[config.DB_NAME]

    # Indexes
    await _db.users.create_index("user_id", unique=True)
    await _db.products.create_index("category_id")
    await _db.stock.create_index([("product_id", 1), ("status", 1)])
    await _db.orders.create_index("user_id")
    await _db.orders.create_index("status")
    await _db.topups.create_index("user_id")

    # Ping
    await _client.admin.command("ping")

    # Ensure settings doc
    existing = await _db.settings.find_one({"_id": "global"})
    if not existing:
        await _db.settings.insert_one({"_id": "global", **config.DEFAULTS, "custom_emojis": {}})
    else:
        # Backfill any missing default keys
        patch = {k: v for k, v in config.DEFAULTS.items() if k not in existing}
        if patch:
            await _db.settings.update_one({"_id": "global"}, {"$set": patch})


def db() -> AsyncIOMotorDatabase:
    assert _db is not None, "DB not initialized. Call init_db() first."
    return _db


async def close_db() -> None:
    if _client:
        _client.close()


# ---------------- Settings ----------------
async def get_settings() -> dict[str, Any]:
    doc = await db().settings.find_one({"_id": "global"})
    if not doc:
        doc = {"_id": "global", **config.DEFAULTS, "custom_emojis": {}}
    # merge defaults
    merged = {**config.DEFAULTS, **doc}
    return merged


async def update_setting(key: str, value: Any) -> None:
    await db().settings.update_one({"_id": "global"}, {"$set": {key: value}}, upsert=True)


# ---------------- Users ----------------
async def get_or_create_user(user_id: int, username: str, full_name: str,
                             ref_by: Optional[int] = None) -> dict[str, Any]:
    user = await db().users.find_one({"user_id": user_id})
    if user:
        await db().users.update_one(
            {"user_id": user_id},
            {"$set": {"username": username, "full_name": full_name, "last_seen": now()}},
        )
        return user
    doc = {
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "balance": 0.0,
        "ref_by": ref_by if ref_by and ref_by != user_id else None,
        "ref_count": 0,
        "ref_earned": 0.0,
        "banned": False,
        "total_spent": 0.0,
        "orders_count": 0,
        "joined": now(),
        "last_seen": now(),
    }
    await db().users.insert_one(doc)
    if doc["ref_by"]:
        await db().users.update_one({"user_id": doc["ref_by"]}, {"$inc": {"ref_count": 1}})
    return doc


async def get_user(user_id: int) -> Optional[dict[str, Any]]:
    return await db().users.find_one({"user_id": user_id})


async def adjust_balance(user_id: int, amount: float) -> None:
    await db().users.update_one({"user_id": user_id}, {"$inc": {"balance": amount}})


async def set_banned(user_id: int, banned: bool) -> None:
    await db().users.update_one({"user_id": user_id}, {"$set": {"banned": banned}})


async def count_users() -> int:
    return await db().users.count_documents({})


async def all_user_ids() -> list[int]:
    ids = []
    async for u in db().users.find({"banned": {"$ne": True}}, {"user_id": 1}):
        ids.append(u["user_id"])
    return ids


async def top_users(limit: int = 10) -> list[dict[str, Any]]:
    cur = db().users.find({}).sort("total_spent", -1).limit(limit)
    return [u async for u in cur]


# ---------------- Categories ----------------
async def add_category(name: str, emoji: str = "📦") -> str:
    res = await db().categories.insert_one({"name": name, "emoji": emoji, "created": now()})
    return str(res.inserted_id)


async def list_categories() -> list[dict[str, Any]]:
    return [c async for c in db().categories.find({}).sort("created", 1)]


async def get_category(cat_id: str) -> Optional[dict[str, Any]]:
    _id = oid(cat_id)
    return await db().categories.find_one({"_id": _id}) if _id else None


async def delete_category(cat_id: str) -> None:
    _id = oid(cat_id)
    if _id:
        await db().categories.delete_one({"_id": _id})
        await db().products.delete_many({"category_id": cat_id})


# ---------------- Products ----------------
async def add_product(category_id: str, name: str, description: str, price: float,
                      delivery_mode: str = "auto", manual_note: str = "") -> str:
    doc = {
        "category_id": category_id,
        "name": name,
        "description": description,
        "price": float(price),
        "delivery_mode": delivery_mode,  # auto | manual | both
        "manual_note": manual_note,
        "active": True,
        "sold": 0,
        "created": now(),
    }
    res = await db().products.insert_one(doc)
    return str(res.inserted_id)


async def list_products(category_id: Optional[str] = None, only_active: bool = True) -> list[dict[str, Any]]:
    q: dict[str, Any] = {}
    if category_id:
        q["category_id"] = category_id
    if only_active:
        q["active"] = True
    return [p async for p in db().products.find(q).sort("created", 1)]


async def get_product(product_id: str) -> Optional[dict[str, Any]]:
    _id = oid(product_id)
    return await db().products.find_one({"_id": _id}) if _id else None


async def update_product(product_id: str, patch: dict[str, Any]) -> None:
    _id = oid(product_id)
    if _id:
        await db().products.update_one({"_id": _id}, {"$set": patch})


async def delete_product(product_id: str) -> None:
    _id = oid(product_id)
    if _id:
        await db().products.delete_one({"_id": _id})
        await db().stock.delete_many({"product_id": product_id})


async def inc_product_sold(product_id: str) -> None:
    _id = oid(product_id)
    if _id:
        await db().products.update_one({"_id": _id}, {"$inc": {"sold": 1}})


# ---------------- Stock ----------------
async def add_stock(product_id: str, items: list[str]) -> int:
    docs = [{"product_id": product_id, "content": it.strip(), "status": "available", "created": now()}
            for it in items if it.strip()]
    if not docs:
        return 0
    await db().stock.insert_many(docs)
    return len(docs)


async def stock_count(product_id: str) -> int:
    return await db().stock.count_documents({"product_id": product_id, "status": "available"})


async def pop_stock(product_id: str) -> Optional[dict[str, Any]]:
    """Atomically claim one available stock item."""
    return await db().stock.find_one_and_update(
        {"product_id": product_id, "status": "available"},
        {"$set": {"status": "sold", "sold_at": now()}},
    )


async def clear_stock(product_id: str) -> int:
    res = await db().stock.delete_many({"product_id": product_id, "status": "available"})
    return res.deleted_count


# ---------------- Orders ----------------
async def create_order(user_id: int, product: dict[str, Any], pay_method: str,
                       status: str = "pending") -> str:
    doc = {
        "user_id": user_id,
        "product_id": str(product["_id"]),
        "product_name": product["name"],
        "price": float(product["price"]),
        "pay_method": pay_method,  # wallet | usdt | stars
        "status": status,          # pending | approved | rejected | delivered
        "delivered_content": None,
        "proof_file_id": None,
        "created": now(),
    }
    res = await db().orders.insert_one(doc)
    return str(res.inserted_id)


async def get_order(order_id: str) -> Optional[dict[str, Any]]:
    _id = oid(order_id)
    return await db().orders.find_one({"_id": _id}) if _id else None


async def update_order(order_id: str, patch: dict[str, Any]) -> None:
    _id = oid(order_id)
    if _id:
        await db().orders.update_one({"_id": _id}, {"$set": patch})


async def list_orders(user_id: Optional[int] = None, status: Optional[str] = None,
                      limit: int = 20) -> list[dict[str, Any]]:
    q: dict[str, Any] = {}
    if user_id:
        q["user_id"] = user_id
    if status:
        q["status"] = status
    cur = db().orders.find(q).sort("created", -1).limit(limit)
    return [o async for o in cur]


async def mark_user_purchase(user_id: int, amount: float) -> None:
    await db().users.update_one(
        {"user_id": user_id},
        {"$inc": {"total_spent": amount, "orders_count": 1}},
    )


# ---------------- Topups ----------------
async def create_topup(user_id: int, amount: float, method: str,
                       status: str = "pending") -> str:
    doc = {
        "user_id": user_id,
        "amount": float(amount),
        "method": method,  # usdt | stars
        "status": status,  # pending | approved | rejected
        "proof_file_id": None,
        "created": now(),
    }
    res = await db().topups.insert_one(doc)
    return str(res.inserted_id)


async def get_topup(topup_id: str) -> Optional[dict[str, Any]]:
    _id = oid(topup_id)
    return await db().topups.find_one({"_id": _id}) if _id else None


async def update_topup(topup_id: str, patch: dict[str, Any]) -> None:
    _id = oid(topup_id)
    if _id:
        await db().topups.update_one({"_id": _id}, {"$set": patch})


# ---------------- Stats ----------------
async def stats() -> dict[str, Any]:
    total_users = await db().users.count_documents({})
    total_orders = await db().orders.count_documents({})
    delivered = await db().orders.count_documents({"status": "delivered"})
    pending_orders = await db().orders.count_documents({"status": "pending"})
    pending_topups = await db().topups.count_documents({"status": "pending"})
    products = await db().products.count_documents({})
    revenue_cur = db().orders.aggregate([
        {"$match": {"status": "delivered"}},
        {"$group": {"_id": None, "total": {"$sum": "$price"}}},
    ])
    revenue = 0.0
    async for r in revenue_cur:
        revenue = r.get("total", 0.0)
    return {
        "users": total_users,
        "orders": total_orders,
        "delivered": delivered,
        "pending_orders": pending_orders,
        "pending_topups": pending_topups,
        "products": products,
        "revenue": revenue,
    }
