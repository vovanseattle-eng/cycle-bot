from types import SimpleNamespace

from aiogram import F

# Тот же фильтр, что в app/handlers.py (msg_history_hint).
# Только базовый regexp(pattern) — без mode/flags, чтобы работать
# в любой версии magic_filter на сервере.
HISTORY_FILTER = F.text.regexp(r"(?i).*(посмотреть|смотреть|истори|предыдущ|прошл|когда был|какие даты)")


def _matches(text: str) -> bool:
    return bool(HISTORY_FILTER.resolve(SimpleNamespace(text=text)))


def test_history_filter_catches_client_phrases():
    # Фразы, которые реально писала клиентка.
    assert _matches("как предыдущие посмотреть")
    assert _matches("КАК ПОСМОТРЕТЬ")
    assert _matches("Как Посмотреть")
    assert _matches("какие даты")
    assert _matches("история")
    assert _matches("когда был секс")
    assert _matches("предыдущие записи")


def test_history_filter_ignores_unrelated():
    assert not _matches("а сю было")
    assert not _matches("вот я и не помню 6-8")
    assert not _matches("помоги")
    assert not _matches("привет")
    assert not _matches("")


def test_history_filter_ignores_message_without_text():
    assert not _matches(None)


def test_history_filter_uses_only_base_regexp_api():
    """На сервере может быть старая версия magic_filter — без mode/flags/search.

    Если фильтр начнёт использовать эти параметры, бот упадёт на импорте.
    Проверяем сам вызов в handlers.py, а не сигнатуру установленной библиотеки.
    """
    import inspect

    from app import handlers

    src = inspect.getsource(handlers)
    assert "regexp(" in src
    # В вызове regexp не должно быть mode=/flags=/search=
    for line in src.splitlines():
        if "regexp(" in line and "F.text.regexp" in line:
            assert "mode=" not in line, f"фильтр зависит от mode=: {line.strip()}"
            assert "flags=" not in line, f"фильтр зависит от flags=: {line.strip()}"
            assert "search=" not in line, f"фильтр зависит от search=: {line.strip()}"
