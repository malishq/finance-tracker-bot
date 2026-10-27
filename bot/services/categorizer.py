from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

from .categories import DEFAULT_CATEGORIES, FALLBACK, KEYWORDS
from .models import EXPENSE, INCOME

PREFIX_MIN_LENGTH = 4

_SLUG_TO_NAME = {c.slug: c.name for c in DEFAULT_CATEGORIES}
_SLUG_KIND = {c.slug: c.kind for c in DEFAULT_CATEGORIES}


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _keyword_matches(keyword: str, text: str, words: List[str]) -> bool:
    if " " in keyword:
        return (" " + text + " ").find(" " + keyword) >= 0
    for word in words:
        if word == keyword:
            return True
        if len(keyword) >= PREFIX_MIN_LENGTH and word.startswith(keyword):
            return True
    return False


def _best_match(text: str, words: List[str], rules: Iterable[Tuple[str, str]]) -> Optional[str]:
    best: Optional[Tuple[int, str]] = None
    for keyword, target in rules:
        keyword = normalize(keyword)
        if not keyword:
            continue
        if _keyword_matches(keyword, text, words):
            score = len(keyword)
            if best is None or score > best[0]:
                best = (score, target)
    return best[1] if best else None


def guess_category(description: str, kind: str, user_rules: Optional[Dict[str, str]] = None) -> str:
    text = normalize(description)
    words = text.split()
    if not words:
        return FALLBACK[kind]
    if user_rules:
        hit = _best_match(text, words, user_rules.items())
        if hit:
            return hit
    rules = []
    for slug, keywords in KEYWORDS.items():
        if _SLUG_KIND.get(slug) != kind:
            continue
        for keyword in keywords:
            rules.append((keyword, _SLUG_TO_NAME[slug]))
    hit = _best_match(text, words, rules)
    return hit or FALLBACK[kind]


def rule_keyword(description: str) -> str:
    return normalize(description)[:60]
