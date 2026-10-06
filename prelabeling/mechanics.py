"""Deterministic text measurements that do not require model judgment."""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Sequence


URL_RE = re.compile(r"(?i)(?:https?://|www\.)\S+")
TOKEN_RE = re.compile(r"[a-z]+(?:'[a-z]+)*")


def rounded(value: float | Decimal, places: int) -> float:
    quantum = Decimal(1).scaleb(-places)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def round4(value: float | Decimal) -> float:
    return rounded(value, 4)


def tokenize(text: str) -> list[str]:
    without_urls = URL_RE.sub("", text)
    normalized = without_urls.replace("\u2018", "'").replace("\u2019", "'").lower()
    return TOKEN_RE.findall(normalized)


def split_paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    return re.split(r"\n(?:[ \t]*\n)+", normalized)


def mattr(tokens: Sequence[str], window_size: int = 20) -> dict[str, Any]:
    n = len(tokens)
    if n == 0:
        return {
            "token_count": 0, "window_size": window_size, "window_ttr": [],
            "MATTR": None, "short_text": True,
        }
    if n < window_size:
        value = round4(Decimal(len(set(tokens))) / Decimal(n))
        return {
            "token_count": n, "window_size": window_size,
            "window_ttr": [value], "MATTR": value, "short_text": True,
        }
    scores = [round4(Decimal(len(set(tokens[i : i + window_size]))) / Decimal(window_size))
              for i in range(n - window_size + 1)]
    return {
        "token_count": n, "window_size": window_size, "window_ttr": scores,
        "MATTR": round4(Decimal(str(sum(scores))) / Decimal(len(scores))), "short_text": False,
    }


def syllables_in_token(token: str) -> int:
    """A fixed, intentionally simple fallback heuristic for F1."""
    word = token.replace("'", "")
    if not word:
        return 0
    if len(word) <= 3:
        return 1
    groups = len(re.findall(r"[aeiouy]+", word))
    if word.endswith("e") and not word.endswith(("le", "ye")) and groups > 1:
        groups -= 1
    if word.endswith("es") and not word.endswith(("aes", "ees", "oes")) and groups > 1:
        groups -= 1
    if word.endswith("ed") and not word.endswith(("ted", "ded")) and groups > 1:
        groups -= 1
    return max(1, groups)


def mechanical_values(text: str) -> dict[str, Any]:
    tokens = tokenize(text)
    paragraphs = split_paragraphs(text)
    return {
        "N1": {"word_count": len(tokens), "tokens": tokens},
        "O1": {"paragraph_count": len(paragraphs), "paragraphs": paragraphs},
        "D2": mattr(tokens),
        "F1_syllable_count": sum(syllables_in_token(token) for token in tokens),
    }
