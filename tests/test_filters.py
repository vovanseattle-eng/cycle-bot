from types import SimpleNamespace

from aiogram import F

# Тот же фильтр, что в app/handlers.py (msg_history_hint).
HISTORY_FILTER = F.text.regexp(
    r"(?i)(посмотреть|смотреть|истори|предыдущ|прошл|когда был|какие даты)",
    mode="search",
)


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
