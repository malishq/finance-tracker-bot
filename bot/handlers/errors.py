from __future__ import annotations

import logging

from aiogram.types import ErrorEvent

from ..texts import ERROR

logger = logging.getLogger(__name__)


async def on_error(event: ErrorEvent) -> None:
    update = event.update
    logger.exception("Ошибка при обработке апдейта %s: %s", update.update_id, event.exception)
    try:
        if update.message is not None:
            await update.message.answer(ERROR)
        elif update.callback_query is not None:
            await update.callback_query.answer(ERROR, show_alert=True)
    except Exception:
        logger.exception("Не удалось сообщить пользователю об ошибке")
