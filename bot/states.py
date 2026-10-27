from aiogram.fsm.state import State, StatesGroup


class EditEntry(StatesGroup):
    waiting_value = State()


class BudgetForm(StatesGroup):
    waiting_amount = State()


class SettingsForm(StatesGroup):
    waiting_currency = State()
    waiting_tz = State()
    waiting_reminder = State()


class CategoryForm(StatesGroup):
    waiting_name = State()
