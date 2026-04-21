#!/usr/bin/env python3
"""
utils/date_extractor.py — Event date/time extraction with confidence scoring.

Strategy (in order):
  1. spaCy NER (DATE, TIME entities) — high confidence
  2. Regex patterns (month-name + day) — medium confidence
  3. Relative terms ("tonight") — low confidence

Returns: (date_str: str|None, time_str: str|None, confidence: int)
  confidence: 0 = none, 1 = low (relative), 2 = medium (regex), 3 = high (NER)
"""

import re
from datetime import date as date_t

# ── Month map ─────────────────────────────────────────────────────────────────

_MONTH_MAP = {
    "january":1,  "february":2,  "march":3,    "april":4,
    "may":5,      "june":6,      "july":7,      "august":8,
    "september":9,"october":10,  "november":11, "december":12,
    "jan":1, "feb":2, "mar":3, "apr":4,
    "jun":6, "jul":7, "aug":8,
    "sep":9, "oct":10, "nov":11, "dec":12,
}

_MONTH_RE = re.compile(
    r'\b(' + '|'.join(_MONTH_MAP) + r')\.?\s+(\d{1,2})(?:st|nd|rd|th)?'
    r'(?:,?\s+(\d{4}))?\b',
    re.IGNORECASE
)
_TIME_RE = re.compile(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', re.IGNORECASE)

# ── spaCy (optional, graceful fallback) ───────────────────────────────────────

_nlp = None
_NLP_LOADED = False

def _get_nlp():
    """Lazily load spaCy model; return None if unavailable."""
    global _nlp, _NLP_LOADED
    if _NLP_LOADED:
        return _nlp
    _NLP_LOADED = True
    try:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
    except Exception:
        _nlp = None
    return _nlp


def _parse_time(text: str):
    """Extract HH:MM string from text, or None."""
    tm = _TIME_RE.search(text)
    if not tm:
        return None
    h  = int(tm.group(1))
    mi = int(tm.group(2) or "0")
    ap = tm.group(3).lower()
    if ap == "pm" and h != 12:
        h += 12
    elif ap == "am" and h == 12:
        h = 0
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return f"{h:02d}:{mi:02d}"
    return None


def _regex_dates(text: str) -> list[date_t]:
    """Extract candidate dates via regex month-name patterns."""
    today = date_t.today()
    found: list[date_t] = []
    for m in _MONTH_RE.finditer(text):
        mon_key = m.group(1).lower().rstrip(".")
        mon = _MONTH_MAP.get(mon_key)
        if not mon:
            continue
        day = int(m.group(2))
        if day < 1 or day > 31:
            continue
        yr = int(m.group(3)) if m.group(3) else today.year
        try:
            found.append(date_t(yr, mon, day))
        except ValueError:
            pass
    return found


def _spacy_dates(text: str) -> list[date_t]:
    """Extract dates via spaCy NER DATE entities."""
    nlp = _get_nlp()
    if not nlp:
        return []
    from dateutil import parser as dateutil_parser
    today = date_t.today()
    found: list[date_t] = []
    doc = nlp(text[:1000])  # cap to avoid slow processing
    for ent in doc.ents:
        if ent.label_ != "DATE":
            continue
        try:
            parsed = dateutil_parser.parse(ent.text, default=date_t(today.year, today.month, today.day))
            found.append(parsed.date())
        except Exception:
            pass
    return found


# ── Public API ────────────────────────────────────────────────────────────────

def extract_event_datetime(
    title: str, desc: str
) -> tuple[str | None, str | None, int]:
    """
    Extract the earliest plausible event date and a start time from article text.

    Returns
    -------
    date_str     : ISO date (YYYY-MM-DD) or None
    time_str     : HH:MM (24h) or None
    confidence   : 0=none, 1=low (relative), 2=medium (regex), 3=high (NER)
    """
    text = title + " " + (desc or "")
    today = date_t.today()
    time_str = _parse_time(text)

    # 1. Try spaCy NER first (highest confidence)
    ner_dates = _spacy_dates(text)
    if ner_dates:
        best = min(ner_dates)
        return best.isoformat(), time_str, 3

    # 2. Fallback: regex month-name patterns
    rx_dates = _regex_dates(text)
    if rx_dates:
        best = min(rx_dates)
        return best.isoformat(), time_str, 2

    # 3. Relative terms
    if re.search(r'\btonight\b', text, re.IGNORECASE):
        return today.isoformat(), time_str, 1
    if re.search(r'\bthis (weekend|saturday|sunday|friday)\b', text, re.IGNORECASE):
        # Compute nearest Friday
        wd = today.weekday()  # 0=Mon
        days_to_fri = (4 - wd) % 7
        fri = today.replace(day=today.day + days_to_fri)  # safe-ish
        return fri.isoformat(), time_str, 1

    return None, time_str, 0
