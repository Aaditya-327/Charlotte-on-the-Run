"""
utils/scoring.py — Event relevance scoring utilities.

Provides `compute_event_score`, which mirrors the original keyword-weighted logic
from fetcher.py but is isolated here so it can be extended later (e.g., TF-IDF).
"""
import re


def compute_event_score(
    title: str,
    desc: str,
    event_kw: dict,
    news_kw: dict,
) -> int:
    """
    Compute an integer relevance score for a candidate event item.

    Parameters
    ----------
    title     : Article title.
    desc      : Article description / summary.
    event_kw  : {keyword: weight} dict for positive (event) signals.
    news_kw   : {keyword: weight} dict for negative (non-event) signals.

    Returns
    -------
    int — higher = more event-like. May be negative for strong news items.
    """
    text = (title + " " + desc).lower()

    score = sum(w for kw, w in event_kw.items() if kw in text)
    score -= sum(w for kw, w in news_kw.items() if kw in text)

    # Temporal heuristics
    if re.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text):
        score += 2
    if re.search(r"\b\d{1,2}:\d{2}\s*(am|pm)\b", text):
        score += 3

    # Price signal
    if re.search(r"\$\d+", text):
        score += 2

    return score
