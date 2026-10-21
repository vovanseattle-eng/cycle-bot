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
    sex_card,
    sex_delete_confirm,
    sex_history_card,
    sex_history_hint,
    sex_saved,
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


def _sex_rows(n: int = 3):
    return [
        {"day": f"2026-10-{18 - i:02d}", "protection": "yes"}
        for i in range(n)
    ]


def test_sex_card_shows_total_and_partner():
    text = sex_card(_sex_rows(3), True, total=12)
    assert "БЛИЗОСТЬ" in text
    assert "Видит это" in text
    assert "12" in text
    assert len(text) <= CAPTION_LIMIT


def test_sex_card_hides_partner_when_not_shared():
    text = sex_card(_sex_rows(3), False, total=3)
    assert "Не видит это" in text
    assert "Видит это" not in text.replace("Не видит это", "")


def test_sex_history_card_shows_range():
    text = sex_history_card(_sex_rows(5), total=12, page=0, per_page=5)
    assert "1–5 из 12" in text
    assert len(text) <= CAPTION_LIMIT


def test_sex_history_card_second_page_range():
    text = sex_history_card(_sex_rows(2), total=12, page=2, per_page=5)
    assert "11–12 из 12" in text


def test_sex_history_card_empty():
    text = sex_history_card([], total=0, page=0, per_page=5)
    assert "Пока пусто" in text


def test_sex_delete_confirm_warns():
    text = sex_delete_confirm("18 октября")
    assert "18 октября" in text
    assert "нельзя" in text


def test_sex_saved_distinguishes_update():
    assert "ОБНОВЛЕНО" in sex_saved("18 октября", "yes", updated=True)
    assert "ОТМЕЧЕНО" in sex_saved("18 октября", "yes")
    assert "ОБНОВЛЕНО" not in sex_saved("18 октября", "yes")


def test_sex_history_hint_mentions_button():
    text = sex_history_hint(7)
    assert "Вся история" in text
    assert "7" in text
    assert len(text) <= CAPTION_LIMIT


def test_sex_when_keyboard_has_history_button():
    from app.keyboards import sex_when_kb

    labels = [btn.text for row in sex_when_kb().inline_keyboard for btn in row]
    assert "Вся история" in labels


def test_sex_history_keyboard_has_delete_and_paging():
    from app.keyboards import sex_history_kb

    rows = _sex_rows(3)
    markup = sex_history_kb(rows, page=1, has_more=True, per_page=5)
    flat = [(btn.text, btn.callback_data) for row in markup.inline_keyboard for btn in row]
    assert any(cb == "sexdel:2026-10-18" for _, cb in flat)
    assert any(cb == "sexhist:2" for _, cb in flat)
    assert any(cb == "sexhist:0" for _, cb in flat)
    # Назад ведёт в карточку «Близость»
    assert any(cb == "menu:sex" for _, cb in flat)

    last = sex_history_kb(rows, page=0, has_more=False, per_page=5)
    flat_last = [btn.callback_data for row in last.inline_keyboard for btn in row]
    assert "sexhist:1" not in flat_last
    assert "sexhist:-1" not in flat_last


def test_sex_history_keyboard_one_button_per_date():
    from app.keyboards import sex_history_kb

    rows = _sex_rows(3)
    markup = sex_history_kb(rows, page=0, has_more=False, per_page=5)
    # Каждая дата — отдельная кнопка-строка, без «Убрать» в подписи.
    date_buttons = [
        btn for row in markup.inline_keyboard for btn in row
        if (btn.callback_data or "").startswith("sexdel:")
    ]
    assert len(date_buttons) == 3
    assert date_buttons[0].text == "18 октября"


def test_sex_delete_keyboard():
    from app.keyboards import sex_delete_kb

    flat = [(btn.text, btn.callback_data) for row in sex_delete_kb("2026-10-18").inline_keyboard for btn in row]
    assert ("Да, убрать", "sexdelok:2026-10-18") in flat
    assert ("Отмена", "sexdelno") in flat

