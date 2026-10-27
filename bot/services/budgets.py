from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .money import fmt_money, fmt_percent

WARNING_SHARE = 0.8
OK = "ok"
WARNING = "warning"
EXCEEDED = "exceeded"


@dataclass
class BudgetStatus:
    category: str
    limit: int
    spent: int

    @property
    def share(self) -> float:
        return self.spent / self.limit if self.limit > 0 else 0.0

    @property
    def remaining(self) -> int:
        return self.limit - self.spent

    @property
    def level(self) -> str:
        if self.spent > self.limit:
            return EXCEEDED
        if self.share >= WARNING_SHARE:
            return WARNING
        return OK


def budget_status(category: str, limit: int, spent: int) -> BudgetStatus:
    return BudgetStatus(category=category, limit=limit, spent=spent)


def progress_bar(share: float, width: int = 10) -> str:
    filled = min(width, max(0, round(share * width)))
    return "▓" * filled + "░" * (width - filled)


def alert_text(status: BudgetStatus, currency: str) -> Optional[str]:
    if status.level == EXCEEDED:
        over = fmt_money(status.spent - status.limit, currency)
        return f"🚨 Лимит «{status.category}» превышен на {over}: {fmt_money(status.spent, currency)} из {fmt_money(status.limit, currency)}"
    if status.level == WARNING:
        return (
            f"⚠️ «{status.category}»: потрачено {fmt_percent(status.share)} лимита, "
            f"осталось {fmt_money(status.remaining, currency)}"
        )
    return None


def crossed_threshold(before: BudgetStatus, after: BudgetStatus) -> bool:
    return after.level != OK and after.level != before.level


def statuses_from(limits: Dict[str, int], spent: Dict[str, int]) -> List[BudgetStatus]:
    result = [budget_status(name, limit, spent.get(name, 0)) for name, limit in limits.items()]
    return sorted(result, key=lambda s: (-s.share, s.category))
