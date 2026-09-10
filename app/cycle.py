from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

PHASE_PERIOD = "period"
PHASE_FOLLICULAR = "follicular"
PHASE_FERTILE = "fertile"
PHASE_LUTEAL = "luteal"
PHASE_DELAY = "delay"
PHASE_UNKNOWN = "unknown"

PHASE_TITLE = {
    PHASE_PERIOD: "Красные дни",
    PHASE_FOLLICULAR: "Фолликулярная фаза",
    PHASE_FERTILE: "Голубые дни",
    PHASE_LUTEAL: "Лютеиновая фаза",
    PHASE_DELAY: "Задержка",
    PHASE_UNKNOWN: "Цикл ещё не отмечен",
}

MODE_INTERVAL = "interval"
MODE_MONTHLY = "monthly"


@dataclass(frozen=True)
class CycleConfig:
    last_start: date | None
    cycle_length: int = 28
    period_length: int = 5
    luteal_days: int = 14
    fertile_before: int = 5
    fertile_after: int = 1
    predict_mode: str = MODE_INTERVAL
    next_override: date | None = None


@dataclass(frozen=True)
class CycleSnapshot:
    last_start: date | None
    cycle_length: int
    period_length: int
    today: date
    cycle_day: int | None
    delay_days: int
    next_period: date | None
    red_start: date | None
    red_end: date | None
    blue_start: date | None
    ovulation: date | None
    blue_end: date | None
    phase: str
    predict_mode: str = MODE_INTERVAL
    luteal_days: int = 14
    days_until: int | None = None

    @property
    def in_red(self) -> bool:
        return self.phase == PHASE_PERIOD

    @property
    def in_blue(self) -> bool:
        return self.phase == PHASE_FERTILE


def clamp_cycle_length(value: int) -> int:
    return min(60, max(20, int(value)))


def clamp_period_length(value: int) -> int:
    return min(12, max(2, int(value)))


def clamp_luteal(value: int) -> int:
    return min(16, max(10, int(value)))


def clamp_fertile(value: int, lo: int = 1, hi: int = 8) -> int:
    return min(hi, max(lo, int(value)))


def add_months(start: date, months: int) -> date:
    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def cfg_from_user(user: dict, today: date) -> CycleConfig:
    override = user.get("next_override")
    nxt = date.fromisoformat(override) if override else None
    last = user.get("last_start")
    last_d = date.fromisoformat(last) if last else None
    if nxt and last_d and nxt <= last_d:
        nxt = None
    return CycleConfig(
        last_start=last_d,
        cycle_length=int(user.get("cycle_length") or 28),
        period_length=int(user.get("period_length") or 5),
        luteal_days=int(user.get("luteal_days") or 14),
        fertile_before=int(user.get("fertile_before") or 5),
        fertile_after=int(user.get("fertile_after") or 1),
        predict_mode=user.get("predict_mode") or MODE_INTERVAL,
        next_override=nxt,
    )


def predicted_next(
    start: date,
    cycle_length: int,
    predict_mode: str = MODE_INTERVAL,
    override: date | None = None,
) -> date:
    if override and override > start:
        return override
    if predict_mode == MODE_MONTHLY:
        return add_months(start, 1)
    return start + timedelta(days=clamp_cycle_length(cycle_length))


def cycle_span(start: date, nxt: date) -> int:
    return max(20, (nxt - start).days)


def ovulation_cycle_day(cycle_length: int, luteal_days: int = 14) -> int:
    return clamp_cycle_length(cycle_length) - clamp_luteal(luteal_days)


def red_window(start: date, period_length: int) -> tuple[date, date]:
    length = clamp_period_length(period_length)
    return start, start + timedelta(days=length - 1)


def blue_window(
    start: date,
    cycle_length: int,
    luteal_days: int = 14,
    fertile_before: int = 5,
    fertile_after: int = 1,
    next_date: date | None = None,
) -> tuple[date, date, date]:
    nxt = next_date or (start + timedelta(days=clamp_cycle_length(cycle_length)))
    span = cycle_span(start, nxt)
    ovu_day = ovulation_cycle_day(span, luteal_days)
    ovulation = start + timedelta(days=ovu_day - 1)
    before = clamp_fertile(fertile_before, 1, 8)
    after = clamp_fertile(fertile_after, 0, 3)
    return (
        ovulation - timedelta(days=before),
        ovulation,
        ovulation + timedelta(days=after),
    )


def delay_days(
    start: date,
    cycle_length: int,
    today: date,
    predict_mode: str = MODE_INTERVAL,
    override: date | None = None,
) -> int:
    expected = predicted_next(start, cycle_length, predict_mode, override)
    if today <= expected:
        return 0
    return (today - expected).days


def snapshot(
    last_start: date | None,
    cycle_length: int,
    period_length: int,
    today: date,
    luteal_days: int = 14,
    fertile_before: int = 5,
    fertile_after: int = 1,
    predict_mode: str = MODE_INTERVAL,
    next_override: date | None = None,
) -> CycleSnapshot:
    cfg = CycleConfig(
        last_start=last_start,
        cycle_length=cycle_length,
        period_length=period_length,
        luteal_days=luteal_days,
        fertile_before=fertile_before,
        fertile_after=fertile_after,
        predict_mode=predict_mode,
        next_override=next_override,
    )
    return snapshot_cfg(cfg, today)


def snapshot_cfg(cfg: CycleConfig, today: date) -> CycleSnapshot:
    cycle_length = clamp_cycle_length(cfg.cycle_length)
    period_length = clamp_period_length(cfg.period_length)
    luteal = clamp_luteal(cfg.luteal_days)
    mode = cfg.predict_mode if cfg.predict_mode in {MODE_INTERVAL, MODE_MONTHLY} else MODE_INTERVAL

    if cfg.last_start is None:
        return CycleSnapshot(
            last_start=None,
            cycle_length=cycle_length,
            period_length=period_length,
            today=today,
            cycle_day=None,
            delay_days=0,
            next_period=None,
            red_start=None,
            red_end=None,
            blue_start=None,
            ovulation=None,
            blue_end=None,
            phase=PHASE_UNKNOWN,
            predict_mode=mode,
            luteal_days=luteal,
        )

    start = cfg.last_start
    nxt = predicted_next(start, cycle_length, mode, cfg.next_override)
    span = cycle_span(start, nxt)
    red_start, red_end = red_window(start, period_length)
    blue_start, ovulation, blue_end = blue_window(
        start, span, luteal, cfg.fertile_before, cfg.fertile_after, nxt
    )
    late = delay_days(start, cycle_length, today, mode, cfg.next_override)
    day = (today - start).days + 1
    until = (nxt - today).days

    if today < start:
        phase = PHASE_UNKNOWN
    elif red_start <= today <= red_end:
        phase = PHASE_PERIOD
    elif late > 0:
        phase = PHASE_DELAY
    elif blue_start <= today <= blue_end:
        phase = PHASE_FERTILE
    elif today < blue_start:
        phase = PHASE_FOLLICULAR
    else:
        phase = PHASE_LUTEAL

    return CycleSnapshot(
        last_start=start,
        cycle_length=span,
        period_length=period_length,
        today=today,
        cycle_day=day,
        delay_days=late,
        next_period=nxt,
        red_start=red_start,
        red_end=red_end,
        blue_start=blue_start,
        ovulation=ovulation,
        blue_end=blue_end,
        phase=phase,
        predict_mode=mode,
        luteal_days=luteal,
        days_until=until if late == 0 else -late,
    )


def iter_cycle_starts(cfg: CycleConfig, horizon: int = 4) -> list[date]:
    if cfg.last_start is None:
        return []
    starts = []
    for i in range(-1, horizon):
        if cfg.predict_mode == MODE_MONTHLY:
            starts.append(add_months(cfg.last_start, i))
        else:
            starts.append(cfg.last_start + timedelta(days=clamp_cycle_length(cfg.cycle_length) * i))
    return starts


def marks_for_month(
    last_start: date | None,
    cycle_length: int,
    period_length: int,
    year: int,
    month: int,
    horizon_cycles: int = 4,
    luteal_days: int = 14,
    fertile_before: int = 5,
    fertile_after: int = 1,
    predict_mode: str = MODE_INTERVAL,
    next_override: date | None = None,
) -> tuple[set[date], set[date], date | None]:
    cfg = CycleConfig(
        last_start=last_start,
        cycle_length=cycle_length,
        period_length=period_length,
        luteal_days=luteal_days,
        fertile_before=fertile_before,
        fertile_after=fertile_after,
        predict_mode=predict_mode,
        next_override=next_override,
    )
    red: set[date] = set()
    blue: set[date] = set()
    ovulation: date | None = None
    if last_start is None:
        return red, blue, ovulation

    for start in iter_cycle_starts(cfg, horizon_cycles):
        nxt = predicted_next(start, cfg.cycle_length, cfg.predict_mode, cfg.next_override if start == last_start else None)
        span = cycle_span(start, nxt)
        r0, r1 = red_window(start, cfg.period_length)
        b0, ovu, b1 = blue_window(start, span, cfg.luteal_days, cfg.fertile_before, cfg.fertile_after, nxt)
        cursor = r0
        while cursor <= r1:
            if cursor.year == year and cursor.month == month:
                red.add(cursor)
            cursor += timedelta(days=1)
        cursor = b0
        while cursor <= b1:
            if cursor.year == year and cursor.month == month:
                blue.add(cursor)
            cursor += timedelta(days=1)
        if ovu.year == year and ovu.month == month:
            ovulation = ovu
    return red, blue, ovulation


def progress_bar(cycle_day: int | None, cycle_length: int, delay: int, width: int = 10) -> str:
    if cycle_day is None:
        return "─" * width
    if delay > 0:
        filled = width
    else:
        filled = round(min(cycle_length, max(1, cycle_day)) / max(cycle_length, 1) * width)
        filled = min(width, max(0, filled))
    return "━" * filled + "─" * (width - filled)


def apply_next_date(start: date, nxt: date) -> tuple[int, str]:
    """cycle_length, predict_mode from an explicit next-period date."""
    length = (nxt - start).days
    if length < 20:
        length = 20
    if nxt.day == start.day:
        return clamp_cycle_length(length), MODE_MONTHLY
    return clamp_cycle_length(length), MODE_INTERVAL
