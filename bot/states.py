"""FSM states for multi-step flows (user + admin)."""
from aiogram.fsm.state import State, StatesGroup


class TopUp(StatesGroup):
    amount = State()
    proof = State()


class BuyProof(StatesGroup):
    proof = State()


class AdminCategory(StatesGroup):
    name = State()
    emoji = State()


class AdminProduct(StatesGroup):
    category = State()
    name = State()
    description = State()
    price = State()
    delivery_mode = State()
    manual_note = State()


class AdminStock(StatesGroup):
    items = State()


class AdminBroadcast(StatesGroup):
    message = State()
    confirm = State()


class AdminSetting(StatesGroup):
    value = State()


class AdminBalance(StatesGroup):
    user_id = State()
    amount = State()


class AdminManualDeliver(StatesGroup):
    content = State()
