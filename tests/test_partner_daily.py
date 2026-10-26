"""Партнёрские уведомления: каждый день красных (2..N), близость без гейта, дедуп."""

import asyncio
import os
import tempfile
from datetime import date, timedelta

import pytest

from app import db
from app.cycle import PHASE_PERIOD
from app.handlers import ping_period_marked
from app.notify import daily_tick, ping_viewers
from app.state import user_snap

OWNER = 9001
PARTNER = 9002


class FakeBot:
    """Ловит send_message в список (chat_id, text)."""

    def __init__(self):
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **kwargs):
        self.sent.append((int(chat_id), text))


@pytest.fixture
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(db, "DB_PATH", path)
    db._db = None
    conn = asyncio.run(db.connect())
    yield conn
    asyncio.run(db.close())
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


@pytest.fixture
def tick_hour(monkeypatch):
    """Не зависеть от реального времени: час ровно тот, что в notify_hour."""
    monkeypatch.setattr("app.notify.hour_in", lambda tz: 9)


@pytest.fixture
def bound_pair(temp_db):
    """Ольга (владелица, цикл в красных) + Денис (партнёр)."""
    asyncio.run(_setup_pair(OWNER, PARTNER))


async def _setup_pair(owner: int, partner: int) -> None:
    today = date.today()
    await db.ensure_user(owner, "Ольга")
    await db.ensure_user(partner, "Денис")
    await db.set_period(owner, today, 5)
    await db.update_user(owner, notify_hour=9)
    await db.bind_partner(owner, partner)


# --- ping_viewers: близость всегда партнёру (FR-3) ---


def test_sex_ping_ignores_share_sex(bound_pair, temp_db):
    async def run():
        owner = await db.get_user(OWNER)  # share_sex = 0 по умолчанию
        bot = FakeBot()
        await ping_viewers(bot, owner, "sex", extra="сегодня")
        assert [c for c, _ in bot.sent] == [PARTNER]
        assert "отметила близость" in bot.sent[0][1]

    asyncio.run(run())


# --- daily_tick: день N красных партнёру (FR-1, FR-2), дедуп (AC-4) ---


async def _set_phase_day(start_offset_days: int) -> None:
    """last_start = today - offset, чтобы владельцу оказался нужный день красных."""
    await db.set_period(OWNER, date.today() - timedelta(days=start_offset_days), 5)


def _partner_msgs(bot: FakeBot, text_contains: str) -> list:
    return [t for c, t in bot.sent if c == PARTNER and text_contains in t]


def test_red_day2_goes_to_partner_not_owner(bound_pair, tick_hour, temp_db):
    async def run():
        await _set_phase_day(1)  # сегодня — день 2 красных
        user = await db.get_user(OWNER)
        snap = user_snap(user)
        assert snap.phase == PHASE_PERIOD, "сцена: владелец в красных"

        bot = FakeBot()
        await daily_tick(bot)

        day_msgs = _partner_msgs(bot, "день 2")
        assert len(day_msgs) == 1, f"партнёру должен упасть «день 2», came={bot.sent}"
        owner_msgs = [t for c, t in bot.sent if c == OWNER]
        assert owner_msgs == [], "день 2 не должен идти самой владелице"

    asyncio.run(run())


def test_red_day_notify_dedups_same_day(bound_pair, tick_hour, temp_db):
    async def run():
        await _set_phase_day(1)
        bot = FakeBot()
        await daily_tick(bot)
        await daily_tick(bot)  # повторный тик в тот же день
        assert len(_partner_msgs(bot, "день 2")) == 1, "dedup не отработал"

    asyncio.run(run())


def test_red_day1_not_duplicated_by_new_block(bound_pair, tick_hour, temp_db):
    async def run():
        await _set_phase_day(0)  # сегодня — день 1
        user = await db.get_user(OWNER)
        snap = user_snap(user)
        assert snap.red_start == snap.today, "сцена: день 1"

        bot = FakeBot()
        await daily_tick(bot)
        # партнёру — ровно один пинг по красным (от red_today), а не два
        assert len(_partner_msgs(bot, "начались красные дни")) == 1
        day1_extra = _partner_msgs(bot, "день 1")
        assert day1_extra == [], "новый блок не должен слать на день 1"

    asyncio.run(run())


def test_red_day_beyond_window_silent(bound_pair, tick_hour, temp_db):
    async def run():
        await _set_phase_day(6)  # за пределами окна (5 дней) — фолликулярная фаза
        user = await db.get_user(OWNER)
        snap = user_snap(user)
        assert snap.phase != PHASE_PERIOD

        bot = FakeBot()
        await daily_tick(bot)
        assert all(c != PARTNER for c, _ in bot.sent), "вне окна пингов быть не должно"

    asyncio.run(run())


# --- моментальный пинг при отмечании красных (FR-4, AC-3) ---


def test_ping_period_marked_reaches_partner(bound_pair, temp_db):
    async def run():
        bot = FakeBot()
        await ping_period_marked(bot, OWNER, date.today())
        assert len(_partner_msgs(bot, "начались красные дни")) == 1

    asyncio.run(run())