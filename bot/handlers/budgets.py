from __future__ import annotations

from typing import Tuple

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from ..db import Database
from ..keyboards import MENU_BUDGET, BudgetCb, budget_categories, budget_delete_list, budget_menu, cancel_keyboard
from ..services.budgets import EXCEEDED, WARNING, progress_bar, statuses_from
from ..services.models import EXPENSE
from ..services.money import fmt_money, fmt_percent
from ..services.parser import ParseError, parse_amount
from ..services.periods import MONTH, period_for, period_title
from ..states import BudgetForm
from ..utils import UserContext, load_context, plain_text, respond

router = Router(name="budgets")

MARKS = {WARNING: " ⚠️", EXCEEDED: " 🚨"}


async def budget_view(db: Database, ctx: UserContext) -> Tuple[str, InlineKeyboardMarkup]:
    limits = await db.budgets(ctx.user_id)
    month = period_for(MONTH, ctx.today)
    cur = ctx.currency
    lines = [f"<b>Лимиты · {period_title(month, ctx.today)}</b>", ""]
    if not limits:
        lines.append(
            "Лимитов пока нет. Задай лимит на категорию — предупрежу, "
            "когда потратишь 80%, и когда выйдешь за рамки."
        )
        return "\n".join(lines), budget_menu(False)
    spent = await db.spent_by_category(ctx.user_id, month.start, month.end)
    statuses = statuses_from(limits, spent)
    for status in statuses:
        lines.append(f"{ctx.label(status.category, EXPENSE)}{MARKS.get(status.level, '')}")
        lines.append(
            f"{progress_bar(status.share)} {fmt_percent(status.share)} · "
            f"{fmt_money(status.spent, cur)} из {fmt_money(status.limit, cur)}"
        )
        lines.append("")
    total_spent = sum(status.spent for status in statuses)
    total_limit = sum(status.limit for status in statuses)
    lines.append(f"Всего: {fmt_money(total_spent, cur)} из {fmt_money(total_limit, cur)}")
    return "\n".join(lines), budget_menu(True)


@router.message(Command("budget"))
@router.message(F.text == MENU_BUDGET)
async def cmd_budget(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    ctx = await load_context(db, message.from_user.id)
    text, markup = await budget_view(db, ctx)
    await message.answer(text, reply_markup=markup)


@router.callback_query(BudgetCb.filter(F.action == "back"))
async def back(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    await state.clear()
    ctx = await load_context(db, callback.from_user.id)
    text, markup = await budget_view(db, ctx)
    await respond(callback, text, markup)
    await callback.answer()


@router.callback_query(BudgetCb.filter(F.action == "set"))
async def choose_category(callback: CallbackQuery, db: Database) -> None:
    ctx = await load_context(db, callback.from_user.id)
    await respond(callback, "Для какой категории задать лимит на месяц?", budget_categories(ctx.categories(EXPENSE)))
    await callback.answer()


@router.callback_query(BudgetCb.filter(F.action == "pick"))
async def pick_category(callback: CallbackQuery, callback_data: BudgetCb, db: Database, state: FSMContext) -> None:
    ctx = await load_context(db, callback.from_user.id)
    category = ctx.category_by_slug(callback_data.slug)
    if category is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return
    limits = await db.budgets(ctx.user_id)
    current = limits.get(category.name)
    note = f"\nСейчас: {fmt_money(current, ctx.currency)}." if current else ""
    await state.set_state(BudgetForm.waiting_amount)
    await state.update_data(category=category.name)
    await respond(
        callback,
        f"Лимит для {category.label} на месяц?{note}\nНапиши сумму, например <code>10000</code>:",
        cancel_keyboard(),
    )
    await callback.answer()


@router.message(BudgetForm.waiting_amount, plain_text())
async def save_limit(message: Message, db: Database, state: FSMContext) -> None:
    data = await state.get_data()
    category = data.get("category")
    try:
        limit = parse_amount(message.text)
    except ParseError as error:
        await message.answer(f"{error}. Напиши сумму числом, например <code>10000</code>.", reply_markup=cancel_keyboard())
        return
    await state.clear()
    ctx = await load_context(db, message.from_user.id)
    await db.set_budget(ctx.user_id, category, limit)
    await message.answer(f"✅ Лимит для {ctx.label(category, EXPENSE)}: {fmt_money(limit, ctx.currency)} в месяц")
    text, markup = await budget_view(db, ctx)
    await message.answer(text, reply_markup=markup)


@router.callback_query(BudgetCb.filter(F.action == "del"))
async def choose_delete(callback: CallbackQuery, db: Database) -> None:
    ctx = await load_context(db, callback.from_user.id)
    limits = await db.budgets(ctx.user_id)
    if not limits:
        await callback.answer("Лимитов нет", show_alert=True)
        return
    await respond(callback, "Какой лимит убрать?", budget_delete_list(limits.keys(), ctx.categories(EXPENSE)))
    await callback.answer()


@router.callback_query(BudgetCb.filter(F.action == "rm"))
async def remove_limit(callback: CallbackQuery, callback_data: BudgetCb, db: Database) -> None:
    ctx = await load_context(db, callback.from_user.id)
    category = ctx.category_by_slug(callback_data.slug)
    name = category.name if category else callback_data.slug
    removed = await db.delete_budget(ctx.user_id, name)
    text, markup = await budget_view(db, ctx)
    await respond(callback, text, markup)
    await callback.answer("Лимит убран" if removed else "Лимит не найден")
