from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import DEFAULT_TZ

WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
MONTHS = [
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
]
MONTHS_GEN = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]


def _safe_tz(tz: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz or DEFAULT_TZ)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def today_in(tz: str | None = None) -> date:
    return datetime.now(_safe_tz(tz)).date()


def hour_in(tz: str | None = None) -> int:
    return datetime.now(_safe_tz(tz)).hour


def greet(name: str, tz: str | None = None) -> str:
    hour = hour_in(tz)
    who = (name or "").strip() or "ты"
    if hour < 6:
        hi = "Доброй ночи"
    elif hour < 12:
        hi = "Доброе утро"
    elif hour < 18:
        hi = "Добрый день"
    else:
        hi = "Добрый вечер"
    return f"{hi}, {who}"


def fmt_day(value: date) -> str:
    return f"{value.day} {MONTHS_GEN[value.month - 1]}"


def fmt_range(start: date, end: date) -> str:
    if start == end:
        return fmt_day(start)
    if start.month == end.month:
        return f"{start.day}–{end.day} {MONTHS_GEN[start.month - 1]}"
    return f"{fmt_day(start)} — {fmt_day(end)}"


def month_title(year: int, month: int) -> str:
    name = MONTHS[month - 1]
    return f"{name[0].upper()}{name[1:]} {year}"


def plural_days(n: int) -> str:
    n_abs = abs(n)
    if 11 <= n_abs % 100 <= 14:
        word = "дней"
    else:
        mod = n_abs % 10
        if mod == 1:
            word = "день"
        elif 2 <= mod <= 4:
            word = "дня"
        else:
            word = "дней"
    return f"{n} {word}"
