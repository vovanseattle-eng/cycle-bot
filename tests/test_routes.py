"""Проверка маршрутов: новые коллбэки живые, текстовый хендлер не перехватывает лишнего."""

from types import SimpleNamespace

from app.handlers import router

# Все callback_data, которые должны иметь обработчик.
EXPECTED_CALLBACKS = [
    "menu:sex",
    "menu:sexhistory",
    "sexhist:0",
    "sexhist:3",
    "sexdel:2026-10-18",
    "sexdelok:2026-10-18",
    "sexdelno",
]


def _magic_filters(handlers):
    return [f.magic for h in handlers for f in h.filters if getattr(f, "magic", None) is not None]


def _matches_callback(data: str) -> bool:
    """Есть ли в роутере фильтр, который ловит такой callback_data."""
    event = SimpleNamespace(data=data)
    for magic in _magic_filters(router.callback_query.handlers):
        try:
            if magic.resolve(event):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def test_new_callbacks_have_handlers():
    for cb in EXPECTED_CALLBACKS:
        assert _matches_callback(cb), f"нет обработчика для {cb}"


def test_unknown_callback_not_matched_by_new_routes():
    assert not _matches_callback("sex:что-то-неизвестное")


def test_text_history_handler_registered_last():
    """Свободный текст должен ловиться ПОСЛЕ кнопок, иначе он сожрёт их."""
    handlers = router.message.handlers
    assert handlers, "нет текстовых хендлеров"

    assert handlers[-1].callback.__name__ == "msg_history_hint", (
        f"последний message-хендлер — {handlers[-1].callback.__name__}, а не msg_history_hint"
    )


def test_diary_note_handler_before_history_handler():
    """Заметка дневника должна ловиться раньше свободного текста."""
    names = [h.callback.__name__ for h in router.message.handlers]
    assert "save_diary_note" in names, "нет хендлера заметки дневника"
    assert "msg_history_hint" in names, "нет хендлера подсказки по истории"
    assert names.index("save_diary_note") < names.index("msg_history_hint"), (
        "history-хендлер стоит раньше заметки дневника — он её перехватит"
    )


def test_menu_buttons_registered_before_history_handler():
    """Кнопки главного меню должны ловиться раньше свободного текста."""
    names = [h.callback.__name__ for h in router.message.handlers]
    for btn in ("cmd_home", "cmd_settings", "btn_red", "btn_blue", "btn_cal", "btn_sex", "btn_delay"):
        assert btn in names, f"нет хендлера кнопки {btn}"
        assert names.index(btn) < names.index("msg_history_hint"), (
            f"{btn} стоит после history-хендлера"
        )
