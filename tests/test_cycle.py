from datetime import date

from app.cycle import (
    PHASE_DELAY,
    PHASE_FERTILE,
    PHASE_PERIOD,
    apply_next_date,
    blue_window,
    delay_days,
    predicted_next,
    snapshot,
)


def test_red_and_next_for_28():
    start = date(2026, 9, 1)
    snap = snapshot(start, 28, 5, date(2026, 9, 3))
    assert snap.phase == PHASE_PERIOD
    assert snap.red_start == start
    assert snap.red_end == date(2026, 9, 5)
    assert snap.next_period == date(2026, 9, 29)
    assert predicted_next(start, 28) == date(2026, 9, 29)


def test_blue_window_uses_luteal_14():
    start = date(2026, 9, 1)
    blue_start, ovulation, blue_end = blue_window(start, 28)
    assert ovulation == date(2026, 9, 14)
    assert blue_start == date(2026, 9, 9)
    assert blue_end == date(2026, 9, 15)
    snap = snapshot(start, 28, 5, date(2026, 9, 14))
    assert snap.phase == PHASE_FERTILE


def test_longer_cycle_shifts_ovulation():
    start = date(2026, 9, 1)
    _, ovulation, _ = blue_window(start, 32)
    assert ovulation == date(2026, 9, 18)


def test_delay_counts_after_predicted():
    start = date(2026, 8, 1)
    today = date(2026, 9, 5)
    assert delay_days(start, 28, today) == 7
    snap = snapshot(start, 28, 5, today)
    assert snap.phase == PHASE_DELAY
    assert snap.delay_days == 7


def test_monthly_same_day_aug_to_sep():
    start = date(2026, 8, 16)
    snap = snapshot(start, 28, 5, date(2026, 9, 10), predict_mode="monthly")
    assert snap.next_period == date(2026, 9, 16)
    assert delay_days(start, 28, date(2026, 9, 10), predict_mode="monthly") == 0


def test_apply_next_same_day_is_monthly():
    length, mode = apply_next_date(date(2026, 8, 16), date(2026, 9, 16))
    assert mode == "monthly"
    assert length == 31


def test_apply_next_interval():
    length, mode = apply_next_date(date(2026, 9, 1), date(2026, 9, 29))
    assert mode == "interval"
    assert length == 28

