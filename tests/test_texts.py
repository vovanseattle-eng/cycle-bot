from datetime import date

from app.cycle import snapshot
from app.dates import month_title
from app.helpers import CAPTION_LIMIT, fit_caption
from app.keyboards import diary_kb, next_period_kb, partner_viewer_kb, settings_cycle_kb, settings_tz_kb
from app.texts import (
    blue_card,
    calendar_card,
    delay_card,
    diary_card,
    history_card,
    home_card,
    onboard_intro,
    partner_card,
    partner_viewer_card,
    pregnancy_card,
    settings_card,
    tips_card,
    tos_card,
)


def _cards():
    delay = snapshot(date(2026, 8, 1), 28, 5, date(2026, 9, 5))
    mid = snapshot(date(2026, 9, 1), 28, 5, date(2026, 9, 10))
    sex_rows = [{"day": "2026-08-20", "protection": "no"}]
    user = {
        "name": "Александра",
        "cycle_length": 28,
        "period_length": 5,
        "luteal_days": 14,
        "notify": 1,
        "notify_hour": 9,
        "tz": "Europe/Moscow",
        "intent": "try",
        "predict_mode": "interval",
        "fertile_before": 5,
        "fertile_after": 1,
    }
    return [
        ("home", home_card(mid, name="Александра")),
        ("home_delay", home_card(delay, name="Александра")),
        ("calendar", calendar_card(mid)),
        ("blue", blue_card(mid)),
        ("delay", delay_card(delay, False)),
        ("tips", tips_card(delay, "try")),
        ("preg_try", pregnancy_card(delay, "try", sex_rows)),
        ("preg_avoid", pregnancy_card(delay, "avoid", sex_rows)),
        ("preg_track", pregnancy_card(mid, "track", sex_rows)),
        ("history", history_card([], mid)),
        ("diary", diary_card({}, mid)),
        ("settings", settings_card(user)),
        ("tos", tos_card("Александра")),
        ("onboard", onboard_intro("Александра")),
        ("partner", partner_card(True, "Иван", True, None)),
        ("partner_viewer", partner_viewer_card("Александра")),
    ]


def test_captions_fit_telegram_limit():
    for name, text in _cards():
        assert len(text) <= CAPTION_LIMIT, f"{name} is {len(text)} chars"


def test_fit_caption_cuts_at_newline():
    text = "aaa\n" + ("b" * 2000)
    out = fit_caption(text, 20)
    assert len(out) <= 20
    assert out.endswith("…")


def test_file_id_memory_cache(monkeypatch, tmp_path):
    from app import helpers

    monkeypatch.setattr(helpers, "CACHE_FILE", tmp_path / "ids.json")
    helpers._ids.clear()
    helpers._kinds.clear()
    helpers._disk_loaded = False
    helpers.save_cached_id("k", "id1")
    assert helpers.get_cached_id("k") == "id1"
    helpers._ids.clear()
    helpers._disk_loaded = False
    assert helpers.get_cached_id("k") == "id1"


def test_month_title_capitalized():
    assert month_title(2026, 9) == "Сентябрь 2026"


def test_next_period_marks_28_as_default():
    markup = next_period_kb(date(2026, 9, 1))
    labels = [btn.text for row in markup.inline_keyboard for btn in row]
    assert any("28 дн." in (t or "") for t in labels)


def test_settings_cycle_shows_numbers():
    markup = settings_cycle_kb({"cycle_length": 28, "period_length": 5, "luteal_days": 14, "fertile_before": 5, "fertile_after": 1})
    labels = [btn.text for row in markup.inline_keyboard for btn in row]
    assert any("Цикл 28" in (t or "") for t in labels)
    assert any("Красные 5" in (t or "") for t in labels)


def test_diary_keyboard_layout():
    n = sum(len(row) for row in diary_kb({}).inline_keyboard)
    assert n == 24


def test_home_primary_buttons_are_red():
    from app.keyboards import main_menu_kb

    rows = main_menu_kb().inline_keyboard
    assert rows[0][0].text == "Календарь"
    assert rows[0][0].style == "danger"
    assert rows[1][0].text == "Красные дни"
    assert rows[1][0].style == "danger"
    assert len(rows[0]) == 1
    assert len(rows[1]) == 1
    assert len(rows[2]) == 2


def test_tz_keyboard_counts():
    n = sum(len(row) for row in settings_tz_kb().inline_keyboard)
    assert n == 10


def test_partner_viewer_keyboard():
    rows = partner_viewer_kb().inline_keyboard
    assert len(rows) == 2
    assert rows[0][0].text == "Отвязаться"
    assert rows[0][0].callback_data == "pair:drop"
    assert rows[1][0].text == "Назад"

