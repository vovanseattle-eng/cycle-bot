import asyncio
import os
import tempfile
from datetime import date
import pytest

from app import db


@pytest.fixture
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(db, "DB_PATH", path)
    db._db = None

    async def init():
        return await db.connect()

    conn = asyncio.run(init())
    yield conn

    async def cleanup():
        await db.close()

    asyncio.run(cleanup())
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def test_user_lifecycle(temp_db):
    async def run():
        user = await db.ensure_user(12345, "Алиса")
        assert user["tg_id"] == 12345
        assert user["name"] == "Алиса"
        assert user["onboarded"] == 0

        fetched = await db.get_user(12345)
        assert fetched is not None
        assert fetched["name"] == "Алиса"

        await db.update_user(12345, cycle_length=30, tos_accepted=1)
        updated = await db.get_user(12345)
        assert updated["cycle_length"] == 30
        assert updated["tos_accepted"] == 1

    asyncio.run(run())


def test_periods_and_history(temp_db):
    async def run():
        await db.ensure_user(100, "Лена")
        d1 = date(2026, 8, 1)
        await db.set_period(100, d1, 5)

        u = await db.get_user(100)
        assert u["last_start"] == "2026-08-01"
        assert u["period_length"] == 5
        assert u["onboarded"] == 1

        history = await db.recent_periods(100)
        assert len(history) == 1
        assert history[0]["start_date"] == "2026-08-01"

        # Revise length
        await db.revise_period(100, d1, 6, start_changed=False)
        history2 = await db.recent_periods(100)
        assert len(history2) == 1
        assert history2[0]["length"] == 6

    asyncio.run(run())


def test_sex_and_delay(temp_db):
    async def run():
        await db.ensure_user(200, "Маша")
        today = date(2026, 9, 10)
        await db.add_sex(200, today, "yes")
        assert await db.sex_on(200, today) is True
        assert await db.sex_on(200, date(2026, 9, 9)) is False

        logs = await db.recent_sex(200)
        assert len(logs) == 1
        assert logs[0]["protection"] == "yes"

        expected = date(2026, 9, 15)
        assert await db.delay_marked(200, expected) is False
        assert await db.mark_delay(200, expected) is True
        assert await db.delay_marked(200, expected) is True
        # duplicate mark returns False
        assert await db.mark_delay(200, expected) is False

    asyncio.run(run())


def test_partner_invite_and_unbind(temp_db):
    async def run():
        await db.ensure_user(301, "Ольга")
        await db.ensure_user(302, "Денис")

        code = await db.create_invite(301)
        assert await db.invite_owner(code) == 301
        assert await db.invite_owner("wrong_code") is None

        await db.bind_partner(301, 302)
        assert await db.invite_owner(code) is None

        partner = await db.partner_of(301)
        assert partner is not None
        assert partner["tg_id"] == 302

        owners = await db.owners_for_viewer(302)
        assert len(owners) == 1
        assert owners[0]["tg_id"] == 301

        viewers = await db.viewers_of(301)
        assert viewers == [302]

        # Unbind initiated by viewer (302)
        await db.unbind_partner(302)
        assert await db.partner_of(301) is None
        assert await db.owners_for_viewer(302) == []
        assert await db.viewers_of(301) == []

    asyncio.run(run())


def test_diary_and_symptoms(temp_db):
    async def run():
        await db.ensure_user(400, "Катя")
        today = date(2026, 9, 10)

        await db.upsert_diary(400, today, mood="good", pain=2, note="Хороший день")
        entry = await db.get_diary(400, today)
        assert entry["mood"] == "good"
        assert entry["pain"] == 2
        assert entry["note"] == "Хороший день"
        assert entry["symptoms"] == []

        added = await db.toggle_symptom(400, today, "cramp")
        assert added is True
        entry = await db.get_diary(400, today)
        assert "cramp" in entry["symptoms"]

        removed = await db.toggle_symptom(400, today, "cramp")
        assert removed is False
        entry = await db.get_diary(400, today)
        assert "cramp" not in entry["symptoms"]

    asyncio.run(run())


def test_notify_once(temp_db):
    async def run():
        today = date(2026, 9, 10)
        assert await db.notify_once(500, "red_today", today) is True
        assert await db.notify_once(500, "red_today", today) is False
        assert await db.notify_once(500, "delay_1", today) is True
    asyncio.run(run())


def test_to_pg():
    assert db._to_pg("SELECT 1") == "SELECT 1"
    assert db._to_pg("SELECT * FROM users WHERE tg_id = ?") == "SELECT * FROM users WHERE tg_id = $1"
    assert (
        db._to_pg("INSERT INTO users (tg_id, name, created_at) VALUES (?, ?, ?)")
        == "INSERT INTO users (tg_id, name, created_at) VALUES ($1, $2, $3)"
    )


def test_pg_cursor():
    async def run():
        cursor = db.PgCursor([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}])
        first = await cursor.fetchone()
        assert first == {"id": 1, "name": "a"}
        second = await cursor.fetchone()
        assert second == {"id": 2, "name": "b"}
        third = await cursor.fetchone()
        assert third is None

        cursor2 = db.PgCursor([{"val": 10}, {"val": 20}])
        all_rows = await cursor2.fetchall()
        assert all_rows == [{"val": 10}, {"val": 20}]

    asyncio.run(run())

