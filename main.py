from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import Config, load_config
from bot.db import Database
from bot.handlers import budgets, common, entries, errors, export, history, reports, settings
from bot.reminders import reminder_loop
from bot.texts import BOT_DESCRIPTION, BOT_SHORT_DESCRIPTION

logger = logging.getLogger("finance-bot")

COMMANDS = [
    BotCommand(command="start", description="Начать и показать меню"),
    BotCommand(command="help", description="Как записывать траты"),
    BotCommand(command="today", description="Сводка за сегодня"),
    BotCommand(command="week", description="Сводка за неделю"),
    BotCommand(command="month", description="Сводка за месяц"),
    BotCommand(command="charts", description="Графики"),
    BotCommand(command="list", description="Последние записи"),
    BotCommand(command="undo", description="Отменить последнюю запись"),
    BotCommand(command="budget", description="Лимиты по категориям"),
    BotCommand(command="export", description="Выгрузка в CSV и Excel"),
    BotCommand(command="settings", description="Валюта, часовой пояс, напоминание"),
    BotCommand(command="cancel", description="Прервать ввод"),
]


def build_dispatcher(db: Database, config: Config) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp["db"] = db
    dp["config"] = config
    dp.include_routers(
        common.router,
        reports.router,
        history.router,
        budgets.router,
        export.router,
        settings.router,
        entries.router,
    )
    dp.errors.register(errors.on_error)
    return dp


async def on_startup(bot: Bot, db: Database, dispatcher: Dispatcher) -> None:
    try:
        await bot.set_my_commands(COMMANDS)
        await bot.set_my_description(description=BOT_DESCRIPTION)
        await bot.set_my_short_description(short_description=BOT_SHORT_DESCRIPTION)
    except TelegramAPIError as error:
        logger.warning("Не удалось обновить команды и описание бота: %s", error)
    dispatcher["reminder_task"] = asyncio.create_task(reminder_loop(bot, db))
    logger.info("Бот запущен")


async def on_shutdown(dispatcher: Dispatcher, db: Database) -> None:
    task = dispatcher.workflow_data.get("reminder_task")
    if task is not None:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    await db.close()
    logger.info("Бот остановлен")


async def run() -> None:
    config = load_config()
    logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db = Database(config.db_path, config.default_currency, config.default_tz_offset)
    await db.connect()
    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(db, config)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Остановлено по Ctrl+C")


if __name__ == "__main__":
    main()
