from __future__ import annotations

import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from ..db import Database
from ..keyboards import MENU_CHARTS, MENU_MONTH, MENU_TODAY, MENU_WEEK, ChartCb, charts_menu
from ..services.charts import balance_line, bars_by_day, pie_by_category
from ..services.models import EXPENSE
from ..services.money import fmt_money, fmt_percent
from ..services.periods import (
    MONTH, TODAY, WEEK, comparison_period, format_range, last_days, period_for, period_title,
)
from ..services.summary import average_per_day, by_category, compare, group_by_day, running_balance, summarize
from ..utils import UserContext, chat_id_of, load_context

router = Router(name="reports")

PERIOD_BY_TEXT = {MENU_TODAY: TODAY, MENU_WEEK: WEEK, MENU_MONTH: MONTH}
CHART_DAYS = 30


def _pct_text(pct: float) -> str:
    return f"{abs(pct):.0f}%"


async def summary_text(db: Database, ctx: UserContext, kind: str) -> str:
    period = period_for(kind, ctx.today)
    previous = comparison_period(period, ctx.today)
    entries = await db.entries_between(ctx.user_id, period.start, period.end)
    past_entries = await db.entries_between(ctx.user_id, previous.start, previous.end)
    current = summarize(entries)
    past = summarize(past_entries)
    cur = ctx.currency
    shown_end = min(period.end, ctx.today)
    title = period_title(period, ctx.today)
    if kind != TODAY:
        title = f"{title} · {format_range(period.start, shown_end)}"
    lines = [f"<b>{title}</b>", ""]
    if current.count == 0:
        lines.append("Записей за этот период пока нет.")
    else:
        lines.append(f"Доходы: <b>{fmt_money(current.income, cur)}</b>")
        lines.append(f"Расходы: <b>{fmt_money(current.expense, cur)}</b>")
        lines.append(f"Баланс: <b>{fmt_money(current.balance, cur, signed=True)}</b>")
        elapsed = (shown_end - period.start).days + 1
        if kind != TODAY and current.expense:
            average = fmt_money(average_per_day(current.expense, elapsed), cur)
            lines.append(f"Записей: {current.count} · в среднем {average} в день")
        else:
            lines.append(f"Записей: {current.count}")
        if current.top:
            lines.extend(["", "<b>Топ расходов</b>"])
            for name, amount, share in current.top:
                lines.append(f"{ctx.label(name, EXPENSE)} — {fmt_money(amount, cur)} · {fmt_percent(share)}")
    label_prev = "вчера" if kind == TODAY else f"за {format_range(previous.start, previous.end)}"
    comparison = compare(current, past)
    if current.expense or past.expense:
        lines.append("")
        if past.expense == 0:
            lines.append(f"Расходов {label_prev} не было.")
        elif current.expense == 0:
            lines.append(f"Пока без расходов, {label_prev} было {fmt_money(past.expense, cur)}.")
        elif comparison.expense_pct > 0:
            lines.append(
                f"📈 Расходы на {_pct_text(comparison.expense_pct)} больше, чем {label_prev} "
                f"({fmt_money(past.expense, cur)})."
            )
        elif comparison.expense_pct < 0:
            lines.append(
                f"📉 Расходы на {_pct_text(comparison.expense_pct)} меньше, чем {label_prev} "
                f"({fmt_money(past.expense, cur)})."
            )
        else:
            lines.append(f"Расходы такие же, как {label_prev}.")
    if current.income and past.income and comparison.income_pct is not None:
        sign = "+" if comparison.income_pct >= 0 else "−"
        lines.append(f"Доходы: {sign}{_pct_text(comparison.income_pct)} к тому же периоду ({fmt_money(past.income, cur)}).")
    return "\n".join(lines)


async def show_period(message: Message, db: Database, state: FSMContext, kind: str) -> None:
    await state.clear()
    ctx = await load_context(db, message.from_user.id)
    await message.answer(await summary_text(db, ctx, kind), reply_markup=charts_menu())


@router.message(Command("today"))
async def cmd_today(message: Message, db: Database, state: FSMContext) -> None:
    await show_period(message, db, state, TODAY)


@router.message(Command("week"))
async def cmd_week(message: Message, db: Database, state: FSMContext) -> None:
    await show_period(message, db, state, WEEK)


@router.message(Command("month"))
async def cmd_month(message: Message, db: Database, state: FSMContext) -> None:
    await show_period(message, db, state, MONTH)


@router.message(F.text.in_(PERIOD_BY_TEXT))
async def menu_period(message: Message, db: Database, state: FSMContext) -> None:
    await show_period(message, db, state, PERIOD_BY_TEXT[message.text])


@router.message(Command("charts"))
@router.message(F.text == MENU_CHARTS)
async def cmd_charts(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Какой график показать?", reply_markup=charts_menu())


async def build_chart(db: Database, ctx: UserContext, kind: str):
    cur = ctx.currency
    if kind == "pie":
        period = period_for(MONTH, ctx.today)
        entries = await db.entries_between(ctx.user_id, period.start, period.end)
        data = by_category(entries, EXPENSE)
        title = f"Расходы по категориям · {period_title(period, ctx.today)}"
        subtitle = format_range(period.start, min(period.end, ctx.today))
        image = await asyncio.to_thread(pie_by_category, data, "Расходы по категориям", subtitle, cur)
        return image, f"🥧 {title}"
    window = last_days(ctx.today, CHART_DAYS)
    entries = await db.entries_between(ctx.user_id, window.start, window.end)
    range_text = format_range(window.start, window.end)
    if kind == "days":
        points = group_by_day(entries, window.start, window.end, EXPENSE)
        total = sum(amount for _, amount in points)
        subtitle = f"{range_text} · всего {fmt_money(total, cur)}"
        image = await asyncio.to_thread(bars_by_day, points, "Расходы по дням", subtitle, cur)
        return image, f"📊 Расходы по дням за {CHART_DAYS} дней · {range_text}"
    opening = await db.balance_before(ctx.user_id, window.start)
    points = running_balance(entries, window.start, window.end, opening)
    subtitle = f"{range_text} · доходы минус расходы с учётом прошлых записей"
    image = await asyncio.to_thread(balance_line, points, "Накопленный баланс", subtitle, cur)
    return image, f"📈 Накопленный баланс за {CHART_DAYS} дней · {range_text}"


@router.callback_query(ChartCb.filter())
async def send_chart(callback: CallbackQuery, callback_data: ChartCb, db: Database) -> None:
    ctx = await load_context(db, callback.from_user.id)
    image, caption = await build_chart(db, ctx, callback_data.kind)
    photo = BufferedInputFile(image, filename=f"{callback_data.kind}.png")
    await callback.bot.send_photo(chat_id_of(callback), photo, caption=caption)
    await callback.answer()
