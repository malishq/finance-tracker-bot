from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import aiosqlite

from .services.categories import Category
from .services.models import EXPENSE, INCOME, Entry, UserSettings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    currency TEXT NOT NULL,
    tz_offset INTEGER NOT NULL,
    reminder_time TEXT,
    last_reminder_date TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    amount INTEGER NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    entry_date TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_user_date ON entries(user_id, entry_date);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    emoji TEXT NOT NULL DEFAULT '',
    UNIQUE(user_id, kind, name)
);
CREATE TABLE IF NOT EXISTS budgets (
    user_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    limit_amount INTEGER NOT NULL,
    PRIMARY KEY (user_id, category)
);
CREATE TABLE IF NOT EXISTS keyword_rules (
    user_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    category TEXT NOT NULL,
    PRIMARY KEY (user_id, keyword)
);
"""

USER_FIELDS = {"currency", "tz_offset", "reminder_time", "last_reminder_date"}
ENTRY_FIELDS = {"kind", "amount", "category", "description", "entry_date"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _entry(row: aiosqlite.Row) -> Entry:
    return Entry(
        id=row["id"],
        kind=row["kind"],
        amount=row["amount"],
        category=row["category"],
        description=row["description"],
        entry_date=date.fromisoformat(row["entry_date"]),
    )


def _user(row: aiosqlite.Row) -> UserSettings:
    return UserSettings(
        user_id=row["user_id"],
        currency=row["currency"],
        tz_offset=row["tz_offset"],
        reminder_time=row["reminder_time"],
        last_reminder_date=row["last_reminder_date"],
    )


class Database:
    def __init__(self, path: str, default_currency: str = "₽", default_tz_offset: int = 3) -> None:
        self.path = path
        self.default_currency = default_currency
        self.default_tz_offset = default_tz_offset
        self._conn: Optional[aiosqlite.Connection] = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("База данных не подключена")
        return self._conn

    async def connect(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def ensure_user(self, user_id: int) -> UserSettings:
        await self.conn.execute(
            "INSERT OR IGNORE INTO users (user_id, currency, tz_offset, created_at) VALUES (?, ?, ?, ?)",
            (user_id, self.default_currency, self.default_tz_offset, _now()),
        )
        await self.conn.commit()
        async with self.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        return _user(row)

    async def update_user(self, user_id: int, **fields) -> None:
        keys = [key for key in fields if key in USER_FIELDS]
        if not keys:
            return
        assignments = ", ".join(f"{key} = ?" for key in keys)
        values = [fields[key] for key in keys] + [user_id]
        await self.conn.execute(f"UPDATE users SET {assignments} WHERE user_id = ?", values)
        await self.conn.commit()

    async def add_entry(self, user_id: int, kind: str, amount: int, category: str, description: str, entry_date: date) -> int:
        cursor = await self.conn.execute(
            "INSERT INTO entries (user_id, kind, amount, category, description, entry_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, kind, amount, category, description, entry_date.isoformat(), _now()),
        )
        await self.conn.commit()
        return cursor.lastrowid

    async def get_entry(self, user_id: int, entry_id: int) -> Optional[Entry]:
        async with self.conn.execute("SELECT * FROM entries WHERE user_id = ? AND id = ?", (user_id, entry_id)) as cursor:
            row = await cursor.fetchone()
        return _entry(row) if row else None

    async def update_entry(self, user_id: int, entry_id: int, **fields) -> bool:
        keys = [key for key in fields if key in ENTRY_FIELDS]
        if not keys:
            return False
        values = []
        for key in keys:
            value = fields[key]
            values.append(value.isoformat() if isinstance(value, date) else value)
        assignments = ", ".join(f"{key} = ?" for key in keys)
        cursor = await self.conn.execute(
            f"UPDATE entries SET {assignments} WHERE user_id = ? AND id = ?", values + [user_id, entry_id]
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def delete_entry(self, user_id: int, entry_id: int) -> bool:
        cursor = await self.conn.execute("DELETE FROM entries WHERE user_id = ? AND id = ?", (user_id, entry_id))
        await self.conn.commit()
        return cursor.rowcount > 0

    async def last_entry(self, user_id: int) -> Optional[Entry]:
        async with self.conn.execute(
            "SELECT * FROM entries WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return _entry(row) if row else None

    async def recent_entries(self, user_id: int, limit: int = 10, offset: int = 0) -> List[Entry]:
        async with self.conn.execute(
            "SELECT * FROM entries WHERE user_id = ? ORDER BY entry_date DESC, id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
        return [_entry(row) for row in rows]

    async def count_entries(self, user_id: int) -> int:
        async with self.conn.execute("SELECT COUNT(*) FROM entries WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        return row[0]

    async def entries_between(self, user_id: int, start: date, end: date) -> List[Entry]:
        async with self.conn.execute(
            "SELECT * FROM entries WHERE user_id = ? AND entry_date BETWEEN ? AND ? ORDER BY entry_date, id",
            (user_id, start.isoformat(), end.isoformat()),
        ) as cursor:
            rows = await cursor.fetchall()
        return [_entry(row) for row in rows]

    async def all_entries(self, user_id: int) -> List[Entry]:
        async with self.conn.execute(
            "SELECT * FROM entries WHERE user_id = ? ORDER BY entry_date, id", (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [_entry(row) for row in rows]

    async def balance_before(self, user_id: int, day: date) -> int:
        async with self.conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN kind = ? THEN amount ELSE -amount END), 0) FROM entries WHERE user_id = ? AND entry_date < ?",
            (INCOME, user_id, day.isoformat()),
        ) as cursor:
            row = await cursor.fetchone()
        return row[0]

    async def spent_by_category(self, user_id: int, start: date, end: date) -> Dict[str, int]:
        async with self.conn.execute(
            "SELECT category, SUM(amount) AS total FROM entries WHERE user_id = ? AND kind = ? AND entry_date BETWEEN ? AND ? GROUP BY category",
            (user_id, EXPENSE, start.isoformat(), end.isoformat()),
        ) as cursor:
            rows = await cursor.fetchall()
        return {row["category"]: row["total"] for row in rows}

    async def custom_categories(self, user_id: int) -> List[Category]:
        async with self.conn.execute(
            "SELECT * FROM categories WHERE user_id = ? ORDER BY id", (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [Category(f"u{row['id']}", row["name"], row["emoji"], row["kind"], True) for row in rows]

    async def add_category(self, user_id: int, kind: str, name: str, emoji: str) -> Optional[Category]:
        cursor = await self.conn.execute(
            "INSERT OR IGNORE INTO categories (user_id, kind, name, emoji) VALUES (?, ?, ?, ?)",
            (user_id, kind, name, emoji),
        )
        await self.conn.commit()
        if cursor.rowcount == 0:
            return None
        return Category(f"u{cursor.lastrowid}", name, emoji, kind, True)

    async def delete_category(self, user_id: int, category_id: int) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM categories WHERE user_id = ? AND id = ?", (user_id, category_id)
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def budgets(self, user_id: int) -> Dict[str, int]:
        async with self.conn.execute(
            "SELECT category, limit_amount FROM budgets WHERE user_id = ? ORDER BY category", (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return {row["category"]: row["limit_amount"] for row in rows}

    async def set_budget(self, user_id: int, category: str, limit_amount: int) -> None:
        await self.conn.execute(
            "INSERT INTO budgets (user_id, category, limit_amount) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, category) DO UPDATE SET limit_amount = excluded.limit_amount",
            (user_id, category, limit_amount),
        )
        await self.conn.commit()

    async def delete_budget(self, user_id: int, category: str) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM budgets WHERE user_id = ? AND category = ?", (user_id, category)
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def rules(self, user_id: int) -> Dict[str, str]:
        async with self.conn.execute(
            "SELECT keyword, category FROM keyword_rules WHERE user_id = ?", (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return {row["keyword"]: row["category"] for row in rows}

    async def set_rule(self, user_id: int, keyword: str, category: str) -> None:
        if not keyword:
            return
        await self.conn.execute(
            "INSERT INTO keyword_rules (user_id, keyword, category) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, keyword) DO UPDATE SET category = excluded.category",
            (user_id, keyword, category),
        )
        await self.conn.commit()

    async def users_with_reminders(self) -> List[UserSettings]:
        async with self.conn.execute("SELECT * FROM users WHERE reminder_time IS NOT NULL") as cursor:
            rows = await cursor.fetchall()
        return [_user(row) for row in rows]

    async def mark_reminded(self, user_id: int, day: str) -> None:
        await self.conn.execute("UPDATE users SET last_reminder_date = ? WHERE user_id = ?", (day, user_id))
        await self.conn.commit()

    async def stats(self) -> Dict[str, int]:
        async with self.conn.execute("SELECT COUNT(*) FROM users") as cursor:
            users = (await cursor.fetchone())[0]
        async with self.conn.execute("SELECT COUNT(*) FROM entries") as cursor:
            entries = (await cursor.fetchone())[0]
        async with self.conn.execute("SELECT COUNT(*) FROM users WHERE reminder_time IS NOT NULL") as cursor:
            reminders = (await cursor.fetchone())[0]
        return {"users": users, "entries": entries, "reminders": reminders}
