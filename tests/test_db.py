import asyncio
import os
import sqlite3
import tempfile
from datetime import date
import pytest

from app import db


def _raw_insert_sex(user_id: int, day: str, protection: str = "yes", created: str = "2026-10-18T12:00:00+00:00") -> None:
    """Прямая вставка в обход db.add_sex — чтобы посадить исторический дубль."""
    con = sqlite3.connect(str(db.DB_PATH))
    try:
        con.execute(
            "INSERT INTO sex_logs (user_id, day, protection, created_at) VALUES (?, ?, ?, ?)",
            (user_id, day, protection, created),
        )
        con.commit()
    finally:
        con.close()


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


def test_add_sex_is_upsert(temp_db):
    async def run():
        await db.ensure_user(210, "Даша")

        first = await db.add_sex(210, date(2026, 10, 18), "yes")
        assert first == "created"

        second = await db.add_sex(210, date(2026, 10, 18), "yes")
        assert second == "updated"

        # другой день — новая запись
        third = await db.add_sex(210, date(2026, 10, 16), "no")
        assert third == "created"

        logs = await db.recent_sex(210)
        assert len(logs) == 2
        assert [row["day"] for row in logs] == ["2026-10-18", "2026-10-16"]
        assert logs[0]["protection"] == "yes"

    asyncio.run(run())


def test_add_sex_updates_protection(temp_db):
    async def run():
        await db.ensure_user(215, "Вера")
        await db.add_sex(215, date(2026, 10, 18), "yes")
        result = await db.add_sex(215, date(2026, 10, 18), "no")
        assert result == "updated"

        logs = await db.recent_sex(215)
        assert len(logs) == 1
        assert logs[0]["protection"] == "no"

    asyncio.run(run())


def test_recent_sex_collapses_legacy_duplicates(temp_db):
    async def run():
        await db.ensure_user(220, "Лена")
        # Исторический дубль: две строки за один день, вставлены напрямую.
        _raw_insert_sex(220, "2026-10-18", "yes", "2026-10-18T10:00:00+00:00")
        _raw_insert_sex(220, "2026-10-18", "yes", "2026-10-18T12:00:00+00:00")

        rows = await db.recent_sex(220)
        assert len(rows) == 1
        assert rows[0]["day"] == "2026-10-18"

        # Обе строки остались в базе — ничего не удалено.
        con = sqlite3.connect(str(db.DB_PATH))
        try:
            n = con.execute("SELECT COUNT(*) FROM sex_logs WHERE user_id = ?", (220,)).fetchone()[0]
        finally:
            con.close()
        assert n == 2

    asyncio.run(run())


def test_sex_days_count_counts_days_not_rows(temp_db):
    async def run():
        await db.ensure_user(230, "Ира")
        await db.add_sex(230, date(2026, 10, 18), "yes")
        await db.add_sex(230, date(2026, 10, 18), "yes")
        await db.add_sex(230, date(2026, 10, 16), "yes")
        await db.add_sex(230, date(2026, 9, 15), "no")

        assert await db.sex_days_count(230) == 3

    asyncio.run(run())


def test_recent_sex_offset_pages_history(temp_db):
    async def run():
        await db.ensure_user(240, "Света")
        for day in (1, 2, 3, 4, 5, 6, 7):
            await db.add_sex(240, date(2026, 10, day), "yes")

        page1 = await db.recent_sex(240, limit=5, offset=0)
        page2 = await db.recent_sex(240, limit=5, offset=5)
        assert len(page1) == 5
        assert len(page2) == 2
        assert page1[0]["day"] == "2026-10-07"
        assert page2[-1]["day"] == "2026-10-01"

    asyncio.run(run())


def test_delete_sex_removes_only_that_day(temp_db):
    async def run():
        await db.ensure_user(250, "Юля")
        await db.add_sex(250, date(2026, 10, 18), "yes")
        await db.add_sex(250, date(2026, 10, 16), "yes")

        removed = await db.delete_sex(250, date(2026, 10, 18))
        assert removed == 1

        rows = await db.recent_sex(250)
        assert [row["day"] for row in rows] == ["2026-10-16"]

        # Повторное удаление — ноль, без ошибки.
        assert await db.delete_sex(250, date(2026, 10, 18)) == 0

    asyncio.run(run())


def test_delete_sex_clears_all_duplicates_for_day(temp_db):
    async def run():
        await db.ensure_user(255, "Настя")
        _raw_insert_sex(255, "2026-10-18", "yes", "2026-10-18T10:00:00+00:00")
        _raw_insert_sex(255, "2026-10-18", "yes", "2026-10-18T12:00:00+00:00")

        assert await db.delete_sex(255, date(2026, 10, 18)) == 2
        assert await db.sex_days_count(255) == 0

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


def test_viewer_priority(temp_db):
    from app.handlers import viewed_user, _is_viewer_only

    async def run():
        await db.ensure_user(701, "Алиса")
        await db.update_user(701, onboarded=1, last_start="2026-09-01", cycle_length=28, period_length=5)

        await db.ensure_user(702, "Парень")
        await db.update_user(702, onboarded=1, last_start="2026-08-15", cycle_length=30, period_length=4)

        await db.bind_partner(701, 702)

        viewed = await viewed_user(702)
        assert viewed["tg_id"] == 701
        assert viewed["name"] == "Алиса"

        assert _is_viewer_only({"onboarded": 1}, viewing_other=True) is True
        assert _is_viewer_only({"onboarded": 0}, viewing_other=False) is False

    asyncio.run(run())

