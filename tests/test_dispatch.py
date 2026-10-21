"""Диспетчеризация: какой хендлер сработает на конкретный текст.

Проверяет главный риск правки — свободный текст про историю не должен
перехватывать заметку дневника, кнопки меню и команды.
"""

import asyncio
import datetime

import pytest
from aiogram import Bot
from aiogram.types import Chat, Message, User

from app.handlers import router
from app.state import Flow

BOT = Bot(token="123456:TEST")
CHAT = Chat(id=1, type="private")
USER = User(id=1, is_bot=False, first_name="Клиентка")


def make_message(text: str) -> Message:
    return Message(
        message_id=1,
        date=datetime.datetime(2026, 10, 21, 12, 0),
        chat=CHAT,
        from_user=USER,
        text=text,
    )


async def pick(text: str, raw_state: str | None = None) -> str | None:
    """Первый подходящий хендлер — так же, как выбирает aiogram."""
    message = make_message(text)
    for handler in router.message.handlers:
        ok, _ = await handler.check(message, bot=BOT, raw_state=raw_state)
        if ok:
            return handler.callback.__name__
    return None


def test_diary_note_not_hijacked():
    async def run():
        assert await pick("хочу посмотреть историю", raw_state=Flow.diary_note.state) == "save_diary_note"
        assert await pick("просто заметка", raw_state=Flow.diary_note.state) == "save_diary_note"

    asyncio.run(run())


def test_menu_buttons_still_work():
    async def run():
        cases = {
            "✦ сегодня": "cmd_home",
            "календарь": "btn_cal",
            "красные": "btn_red",
            "секс": "btn_sex",
            "задержка": "btn_delay",
            "советы": "btn_tips",
            "партнёр": "btn_partner",
        }
        for text, expected in cases.items():
            assert await pick(text) == expected, f"кнопка {text!r} ушла не туда"

    asyncio.run(run())


def test_history_phrases_reach_hint():
    async def run():
        for text in (
            "как предыдущие посмотреть",
            "какие даты",
            "история",
            "когда был секс",
        ):
            assert await pick(text) == "msg_history_hint", f"фраза {text!r} не дошла до подсказки"

    asyncio.run(run())


def test_unrelated_text_ignored():
    async def run():
        for text in ("а сю было", "вот я и не помню 6-8", "помоги", "привет"):
            assert await pick(text) is None, f"посторонний текст {text!r} перехвачен"

    asyncio.run(run())


def test_commands_still_work():
    async def run():
        assert await pick("/menu") == "cmd_home"
        assert await pick("/settings") == "cmd_settings"
        assert await pick("/help") == "cmd_help"

    asyncio.run(run())


@pytest.fixture(scope="module", autouse=True)
def _close_bot():
    yield
    asyncio.run(BOT.session.close())
