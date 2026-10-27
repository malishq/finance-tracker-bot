from __future__ import annotations

NBSP = " "


def fmt_money(minor: int, currency: str = "₽", signed: bool = False) -> str:
    negative = minor < 0
    minor = abs(int(minor))
    whole, cents = divmod(minor, 100)
    digits = f"{whole:,}".replace(",", NBSP)
    text = digits if cents == 0 else f"{digits},{cents:02d}"
    if negative:
        text = "−" + text
    elif signed and minor > 0:
        text = "+" + text
    return f"{text}{NBSP}{currency}" if currency else text


def fmt_percent(share: float) -> str:
    return f"{int(share * 100 + 0.5)}%"
