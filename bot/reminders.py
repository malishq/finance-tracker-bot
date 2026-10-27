from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramNotFound

from .db import Database
from .services.reminders import reminder_due
from .texts import REMINDER

logger = logging.getLogger(__name__)
CHECK_INTERVAL = 30


async def send_due_reminders(bot: Bot, db: Database) -> int:
    sent = 0
    now_utc = datetime.now(timezone.utc)
    for user in await db.users_with_reminders():
        day = reminder_due(user, now_utc)
        if day is None:
            continue
        try:
            await bot.send_message(user.user_id, REMINDER)
        except (TelegramForbiddenError, TelegramNotFound):
            logger.info("Пользователь %s недоступен, выключаю напоминание", user.user_id)
            await db.update_user(user.user_id, reminder_time=None)
            continue
        except TelegramAPIError as error:
            logger.warning("Не удалось отправить напоминание %s: %s", user.user_id, error)
            continue
        await db.mark_reminded(user.user_id, day)
        sent += 1
    return sent


async def reminder_loop(bot: Bot, db: Database, interval: int = CHECK_INTERVAL) -> None:
    logger.info("Цикл напоминаний запущен")
    while True:
        try:
            await send_due_reminders(bot, db)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка в цикле напоминаний")
        await asyncio.sleep(interval)
