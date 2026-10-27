import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, List, Optional

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.methods import TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from bot.config import Config
from bot.db import Database
from bot.keyboards import (
    MENU_BUDGET, MENU_HISTORY, MENU_MONTH, MENU_SETTINGS, BudgetCb, ChartCb, EditFieldCb, EntryCb, ExportCb,
    HistCb, SetCatCb, SettingsCb, CategoryCb,
)
from main import build_dispatcher

USER_ID = 777
MESSAGE_TYPES = {"SendMessage", "SendPhoto", "SendDocument", "EditMessageText", "EditMessageReplyMarkup"}


class FakeSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: List[TelegramMethod[Any]] = []
        self.counter = 1000

    async def close(self) -> None:
        return None

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: Optional[int] = None) -> Any:
        self.calls.append(method)
        self.counter += 1
        if type(method).__name__ in MESSAGE_TYPES:
            chat_id = getattr(method, "chat_id", None) or USER_ID
            text = getattr(method, "text", None) or getattr(method, "caption", None)
            return Message(
                message_id=self.counter,
                date=datetime.now(timezone.utc),
                chat=Chat(id=int(chat_id), type="private"),
                text=text,
            )
        return True

    async def stream_content(self, url: str, headers=None, timeout: int = 30, chunk_size: int = 65536, raise_for_status: bool = True) -> AsyncGenerator[bytes, None]:
        yield b""

    def texts(self) -> List[str]:
        result = []
        for call in self.calls:
            if type(call).__name__ not in MESSAGE_TYPES:
                continue
            text = getattr(call, "text", None) or getattr(call, "caption", None)
            if text:
                result.append(text)
        return result

    def last_text(self) -> str:
        texts = self.texts()
        return texts[-1] if texts else ""

    def reset(self) -> None:
        self.calls.clear()


DISPATCHER = build_dispatcher(Database(":memory:"), Config(bot_token="42:TEST", admin_ids=[USER_ID]))


class Harness:
    def __init__(self) -> None:
        self.session = FakeSession()
        self.bot = Bot("42:TEST", session=self.session, default=DefaultBotProperties(parse_mode="HTML"))
        self.db = Database(":memory:")
        self.dp = DISPATCHER
        self.dp["db"] = self.db
        self.update_id = 0
        self.message_id = 0
        self.user = User(id=USER_ID, is_bot=False, first_name="Тест")
        self.chat = Chat(id=USER_ID, type="private")

    async def start(self) -> None:
        await self.db.connect()

    async def stop(self) -> None:
        await self.db.close()

    def _next(self) -> int:
        self.update_id += 1
        return self.update_id

    async def send(self, text: str) -> None:
        self.message_id += 1
        message = Message(
            message_id=self.message_id, date=datetime.now(timezone.utc), chat=self.chat, from_user=self.user, text=text
        )
        self.session.reset()
        await self.dp.feed_update(self.bot, Update(update_id=self._next(), message=message))

    async def click(self, data: str) -> None:
        self.message_id += 1
        message = Message(
            message_id=self.message_id, date=datetime.now(timezone.utc), chat=self.chat, from_user=self.user, text="…"
        )
        query = CallbackQuery(id=str(self._next()), from_user=self.user, chat_instance="1", message=message, data=data)
        self.session.reset()
        await self.dp.feed_update(self.bot, Update(update_id=self._next(), callback_query=query))

    def names(self) -> List[str]:
        return [type(call).__name__ for call in self.session.calls]


def run(coro):
    return asyncio.run(coro)


async def scenario_entries(h: Harness) -> None:
    await h.send("/start")
    assert "SendMessage" in h.names()
    assert "Привет" in h.session.last_text()

    await h.send("350 кофе")
    text = h.session.last_text()
    assert "Записал расход" in text and "350" in text and "Кафе" in text
    entry = await h.db.last_entry(USER_ID)
    assert entry.amount == 35000 and entry.category == "Кафе"

    await h.send("+50000 зарплата")
    assert "Записал доход" in h.session.last_text() and "Зарплата" in h.session.last_text()

    await h.send("1200 продукты вчера\nпривет")
    texts = h.session.texts()
    assert any("Продукты" in t for t in texts) and any("Не понял строки" in t for t in texts)

    await h.send("как дела?")
    assert "Не нашёл сумму" in h.session.last_text()

    await h.send("/foo")
    assert "Не знаю такой команды" in h.session.last_text()

    coffee = (await h.db.recent_entries(USER_ID, 10))
    coffee = [e for e in coffee if e.description == "кофе"][0]
    await h.click(EntryCb(action="cat", entry_id=coffee.id).pack())
    assert "EditMessageText" in h.names() and "Выбери категорию" in h.session.last_text()
    await h.click(SetCatCb(entry_id=coffee.id, slug="food", src="new").pack())
    assert "Продукты" in h.session.last_text() and "Запомнил" in h.session.last_text()
    assert (await h.db.get_entry(USER_ID, coffee.id)).category == "Продукты"
    assert (await h.db.rules(USER_ID)) == {"кофе": "Продукты"}

    await h.send("200 кофе")
    assert "Продукты" in h.session.last_text()

    await h.send("отменить последнюю")
    assert "Отменил последнюю" in h.session.last_text()
    assert (await h.db.count_entries(USER_ID)) == 3

    await h.click(EntryCb(action="del", entry_id=coffee.id).pack())
    assert "Удалил запись" in h.session.last_text()
    assert (await h.db.get_entry(USER_ID, coffee.id)) is None
    await h.click(EntryCb(action="del", entry_id=coffee.id).pack())
    assert any(getattr(c, "show_alert", False) for c in h.session.calls)


async def scenario_reports(h: Harness) -> None:
    await h.send("/start")
    await h.send("+50000 зарплата")
    await h.send("350 кофе")
    await h.send("1200 продукты вчера")
    await h.send("/today")
    text = h.session.last_text()
    assert "Сегодня" in text and "Доходы" in text and "Топ расходов" in text
    await h.send(MENU_MONTH)
    text = h.session.last_text()
    assert "Расходы" in text and "Баланс" in text and "Записей: 3" in text
    await h.send("/week")
    assert "Неделя" in h.session.last_text()
    for kind in ("pie", "days", "balance"):
        await h.click(ChartCb(kind=kind).pack())
        assert "SendPhoto" in h.names(), kind
        photo = [c for c in h.session.calls if type(c).__name__ == "SendPhoto"][0]
        assert photo.photo.data[:8] == b"\x89PNG\r\n\x1a\n"


async def scenario_history(h: Harness) -> None:
    await h.send("/start")
    await h.send("350 кофе")
    await h.send("1200 продукты")
    await h.send(MENU_HISTORY)
    assert "Последние записи" in h.session.last_text() and "1–2 из 2" in h.session.last_text()
    entry = await h.db.last_entry(USER_ID)
    await h.click(HistCb(action="edit", value=entry.id).pack())
    assert "Что изменить" in h.session.last_text()
    await h.click(EditFieldCb(entry_id=entry.id, field="amount").pack())
    assert "сумму" in h.session.last_text()
    await h.send("много")
    assert "Попробуй ещё раз" in h.session.last_text()
    await h.send("1 500,50")
    assert "Обновил" in h.session.last_text()
    assert (await h.db.get_entry(USER_ID, entry.id)).amount == 150050
    await h.click(EditFieldCb(entry_id=entry.id, field="date").pack())
    await h.send("15.10")
    assert (await h.db.get_entry(USER_ID, entry.id)).entry_date.day == 15
    await h.click(EditFieldCb(entry_id=entry.id, field="desc").pack())
    await h.send("продукты на неделю")
    assert (await h.db.get_entry(USER_ID, entry.id)).description == "продукты на неделю"
    await h.click(EditFieldCb(entry_id=entry.id, field="kind").pack())
    assert (await h.db.get_entry(USER_ID, entry.id)).kind == "income"
    await h.click(EditFieldCb(entry_id=entry.id, field="kind").pack())
    assert (await h.db.get_entry(USER_ID, entry.id)).kind == "expense"
    await h.click(EditFieldCb(entry_id=entry.id, field="cat").pack())
    await h.click(SetCatCb(entry_id=entry.id, slug="home", src="hist").pack())
    assert (await h.db.get_entry(USER_ID, entry.id)).category == "Жильё"
    await h.click(HistCb(action="del", value=entry.id).pack())
    assert "Удалить запись?" in h.session.last_text()
    await h.click(HistCb(action="confirm", value=entry.id).pack())
    assert (await h.db.count_entries(USER_ID)) == 1
    await h.click(EditFieldCb(entry_id=entry.id, field="amount").pack())
    await h.send(MENU_HISTORY)
    assert "1–1 из 1" in h.session.last_text()


async def scenario_budgets(h: Harness) -> None:
    await h.send("/start")
    await h.send(MENU_BUDGET)
    assert "Лимитов пока нет" in h.session.last_text()
    await h.click(BudgetCb(action="set").pack())
    assert "Для какой категории" in h.session.last_text()
    await h.click(BudgetCb(action="pick", slug="cafe").pack())
    assert "Кафе" in h.session.last_text()
    await h.send("1000")
    texts = h.session.texts()
    assert any("Лимит для" in t for t in texts) and any("из 1 000" in t for t in texts)
    await h.send("850 кофе")
    assert "85%" in h.session.last_text()
    await h.send("100 кофе")
    assert "Лимит" not in h.session.last_text()
    await h.send("100 кофе")
    assert "превышен" in h.session.last_text()
    await h.send("/budget")
    assert "🚨" in h.session.last_text() and "105%" in h.session.last_text()
    await h.click(BudgetCb(action="del").pack())
    await h.click(BudgetCb(action="rm", slug="cafe").pack())
    assert "Лимитов пока нет" in h.session.last_text()


async def scenario_export(h: Harness) -> None:
    await h.send("/start")
    await h.send("/export")
    assert "За какой период" in h.session.last_text()
    await h.click(ExportCb(period="month").pack())
    assert "В каком формате" in h.session.last_text()
    await h.click(ExportCb(period="month", fmt="csv").pack())
    assert "SendDocument" not in h.names()
    await h.send("350 кофе")
    await h.send("+50000 зарплата")
    await h.click(ExportCb(period="month", fmt="csv").pack())
    document = [c for c in h.session.calls if type(c).__name__ == "SendDocument"][0]
    assert document.document.filename.endswith(".csv")
    assert "Кафе" in document.document.data.decode("utf-8")
    await h.click(ExportCb(period="all", fmt="xlsx").pack())
    document = [c for c in h.session.calls if type(c).__name__ == "SendDocument"][0]
    assert document.document.filename.startswith("finance_all_") and document.document.data[:2] == b"PK"


async def scenario_settings(h: Harness) -> None:
    await h.send("/start")
    await h.send(MENU_SETTINGS)
    assert "Настройки" in h.session.last_text()
    await h.click(SettingsCb(action="currency").pack())
    await h.click(SettingsCb(action="cur_set", value="$").pack())
    assert (await h.db.ensure_user(USER_ID)).currency == "$"
    await h.click(SettingsCb(action="cur_custom").pack())
    await h.send("слишком длинно")
    assert "До 5 символов" in h.session.last_text()
    await h.send("₸")
    assert (await h.db.ensure_user(USER_ID)).currency == "₸"
    await h.click(SettingsCb(action="tz_set", value="5").pack())
    assert (await h.db.ensure_user(USER_ID)).tz_offset == 5
    await h.click(SettingsCb(action="tz_custom").pack())
    await h.send("-4")
    assert (await h.db.ensure_user(USER_ID)).tz_offset == -4
    await h.click(SettingsCb(action="reminder").pack())
    await h.click(SettingsCb(action="rem_set", value="21:00").pack())
    assert (await h.db.ensure_user(USER_ID)).reminder_time == "21:00"
    await h.click(SettingsCb(action="rem_custom").pack())
    await h.send("25:99")
    assert "Не понял время" in h.session.last_text()
    await h.send("9:30")
    assert (await h.db.ensure_user(USER_ID)).reminder_time == "09:30"
    await h.click(SettingsCb(action="rem_set", value="off").pack())
    assert (await h.db.ensure_user(USER_ID)).reminder_time is None
    await h.click(SettingsCb(action="categories").pack())
    await h.click(CategoryCb(action="add", value="expense").pack())
    await h.send("🎮 Игры")
    assert "Добавил категорию" in h.session.texts()[0]
    custom = await h.db.custom_categories(USER_ID)
    assert len(custom) == 1 and custom[0].name == "Игры" and custom[0].emoji == "🎮"
    await h.send("500 игры")
    coffee = await h.db.last_entry(USER_ID)
    await h.click(SetCatCb(entry_id=coffee.id, slug=custom[0].slug, src="new").pack())
    assert (await h.db.get_entry(USER_ID, coffee.id)).category == "Игры"
    await h.send("300 игры")
    assert "🎮 Игры" in h.session.last_text()
    await h.click(CategoryCb(action="del_list").pack())
    await h.click(CategoryCb(action="rm", value=custom[0].slug[1:]).pack())
    assert await h.db.custom_categories(USER_ID) == []
    await h.send("/stats")
    assert "Статистика" in h.session.last_text()
    await h.send("/cancel")
    assert "нечего отменять" in h.session.last_text()


async def run_scenario(scenario) -> None:
    h = Harness()
    await h.start()
    try:
        await scenario(h)
    finally:
        await h.stop()


@pytest.mark.parametrize(
    "scenario",
    [scenario_entries, scenario_reports, scenario_history, scenario_budgets, scenario_export, scenario_settings],
    ids=lambda s: s.__name__,
)
def test_flows(scenario):
    run(run_scenario(scenario))
