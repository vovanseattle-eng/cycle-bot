from __future__ import annotations

import secrets
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from app.config import DB_PATH

_db: aiosqlite.Connection | None = None

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    cycle_length INTEGER NOT NULL DEFAULT 28,
    period_length INTEGER NOT NULL DEFAULT 5,
    tz TEXT NOT NULL DEFAULT 'Europe/Moscow',
    notify INTEGER NOT NULL DEFAULT 1,
    share_sex INTEGER NOT NULL DEFAULT 0,
    last_start TEXT,
    onboarded INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    length INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(tg_id)
);

CREATE TABLE IF NOT EXISTS sex_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    protection TEXT NOT NULL DEFAULT 'skip',
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(tg_id)
);

CREATE TABLE IF NOT EXISTS delay_marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    expected_date TEXT NOT NULL,
    marked_at TEXT NOT NULL,
    UNIQUE (user_id, expected_date),
    FOREIGN KEY (user_id) REFERENCES users(tg_id)
);

CREATE TABLE IF NOT EXISTS partnerships (
    owner_id INTEGER NOT NULL,
    viewer_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, viewer_id),
    FOREIGN KEY (owner_id) REFERENCES users(tg_id),
    FOREIGN KEY (viewer_id) REFERENCES users(tg_id)
);

CREATE TABLE IF NOT EXISTS invites (
    code TEXT PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(tg_id)
);

CREATE TABLE IF NOT EXISTS notify_sent (
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    day TEXT NOT NULL,
    PRIMARY KEY (user_id, kind, day)
);

CREATE TABLE IF NOT EXISTS diary (
    user_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    mood TEXT NOT NULL DEFAULT '',
    flow TEXT NOT NULL DEFAULT '',
    pain INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, day)
);

CREATE TABLE IF NOT EXISTS symptoms (
    user_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    code TEXT NOT NULL,
    PRIMARY KEY (user_id, day, code)
);
"""

USER_COLUMNS = {
    "luteal_days": "INTEGER NOT NULL DEFAULT 14",
    "fertile_before": "INTEGER NOT NULL DEFAULT 6",
    "fertile_after": "INTEGER NOT NULL DEFAULT 3",
    "predict_mode": "TEXT NOT NULL DEFAULT 'interval'",
    "next_override": "TEXT",
    "notify_hour": "INTEGER NOT NULL DEFAULT 9",
    "notify_before": "INTEGER NOT NULL DEFAULT 1",
    "notify_red": "INTEGER NOT NULL DEFAULT 1",
    "notify_blue": "INTEGER NOT NULL DEFAULT 1",
    "notify_delay": "INTEGER NOT NULL DEFAULT 1",
    "share_delay": "INTEGER NOT NULL DEFAULT 1",
    "share_diary": "INTEGER NOT NULL DEFAULT 0",
    "intent": "TEXT NOT NULL DEFAULT 'track'",
    "tos_accepted": "INTEGER NOT NULL DEFAULT 0",
}


async def _migrate(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(users)")
    have = {row[1] for row in await cur.fetchall()}
    for name, spec in USER_COLUMNS.items():
        if name not in have:
            await db.execute(f"ALTER TABLE users ADD COLUMN {name} {spec}")
    await db.execute("UPDATE users SET fertile_before = 6 WHERE fertile_before = 5")
    await db.execute("UPDATE users SET fertile_after = 3 WHERE fertile_after = 1")
    await db.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


async def connect() -> aiosqlite.Connection:
    global _db
    if _db is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA synchronous=NORMAL")
        await _db.execute("PRAGMA temp_store=MEMORY")
        await _db.execute("PRAGMA cache_size=-8000")
        await _db.execute("PRAGMA busy_timeout=5000")
        await _db.executescript(SCHEMA)
        await _migrate(_db)
        await _db.commit()
    return _db


async def close() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def ensure_user(tg_id: int, name: str = "") -> dict[str, Any]:
    db = await connect()
    cur = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    row = await cur.fetchone()
    if row:
        data = dict(row)
        if name and data.get("name") != name and not data.get("name"):
            await db.execute("UPDATE users SET name = ? WHERE tg_id = ?", (name, tg_id))
            await db.commit()
            data["name"] = name
        return data
    await db.execute(
        "INSERT INTO users (tg_id, name, created_at) VALUES (?, ?, ?)",
        (tg_id, name, _now()),
    )
    await db.commit()
    cur = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    return dict(await cur.fetchone())


async def get_user(tg_id: int) -> dict[str, Any] | None:
    db = await connect()
    cur = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def update_user(tg_id: int, **fields: Any) -> None:
    if not fields:
        return
    db = await connect()
    cols = ", ".join(f"{k} = ?" for k in fields)
    await db.execute(f"UPDATE users SET {cols} WHERE tg_id = ?", (*fields.values(), tg_id))
    await db.commit()


async def set_period(user_id: int, start: date, length: int) -> None:
    db = await connect()
    await db.execute(
        "DELETE FROM periods WHERE user_id = ? AND start_date = ?",
        (user_id, start.isoformat()),
    )
    await db.execute(
        "INSERT INTO periods (user_id, start_date, length, created_at) VALUES (?, ?, ?, ?)",
        (user_id, start.isoformat(), length, _now()),
    )
    await db.execute(
        "UPDATE users SET last_start = ?, period_length = ?, onboarded = 1, next_override = NULL WHERE tg_id = ?",
        (start.isoformat(), length, user_id),
    )
    await db.commit()


async def revise_period(user_id: int, start: date, length: int, start_changed: bool) -> None:
    """Правит текущие красные, не заводя новый цикл в истории."""
    db = await connect()
    cur = await db.execute(
        "SELECT id FROM periods WHERE user_id = ? ORDER BY start_date DESC, id DESC LIMIT 1",
        (user_id,),
    )
    row = await cur.fetchone()
    iso = start.isoformat()
    if row:
        await db.execute(
            "DELETE FROM periods WHERE user_id = ? AND start_date = ? AND id != ?",
            (user_id, iso, row["id"]),
        )
        await db.execute(
            "UPDATE periods SET start_date = ?, length = ? WHERE id = ?",
            (iso, length, row["id"]),
        )
    else:
        await db.execute(
            "INSERT INTO periods (user_id, start_date, length, created_at) VALUES (?, ?, ?, ?)",
            (user_id, iso, length, _now()),
        )
    if start_changed:
        await db.execute(
            "UPDATE users SET last_start = ?, period_length = ?, onboarded = 1, next_override = NULL WHERE tg_id = ?",
            (iso, length, user_id),
        )
    else:
        await db.execute(
            "UPDATE users SET last_start = ?, period_length = ?, onboarded = 1 WHERE tg_id = ?",
            (iso, length, user_id),
        )
    await db.commit()


async def recent_periods(user_id: int, limit: int = 8) -> list[dict[str, Any]]:
    db = await connect()
    cur = await db.execute(
        "SELECT * FROM periods WHERE user_id = ? ORDER BY start_date DESC LIMIT ?",
        (user_id, limit),
    )
    return [dict(r) for r in await cur.fetchall()]


async def get_diary(user_id: int, day: date) -> dict[str, Any]:
    db = await connect()
    cur = await db.execute(
        "SELECT * FROM diary WHERE user_id = ? AND day = ?",
        (user_id, day.isoformat()),
    )
    row = await cur.fetchone()
    data = dict(row) if row else {"user_id": user_id, "day": day.isoformat(), "mood": "", "flow": "", "pain": 0, "note": ""}
    cur = await db.execute(
        "SELECT code FROM symptoms WHERE user_id = ? AND day = ?",
        (user_id, day.isoformat()),
    )
    data["symptoms"] = [r["code"] for r in await cur.fetchall()]
    return data


async def upsert_diary(user_id: int, day: date, **fields: Any) -> None:
    db = await connect()
    cur = await db.execute(
        "SELECT 1 FROM diary WHERE user_id = ? AND day = ?",
        (user_id, day.isoformat()),
    )
    if await cur.fetchone():
        if fields:
            cols = ", ".join(f"{k} = ?" for k in fields)
            await db.execute(
                f"UPDATE diary SET {cols}, updated_at = ? WHERE user_id = ? AND day = ?",
                (*fields.values(), _now(), user_id, day.isoformat()),
            )
    else:
        await db.execute(
            """
            INSERT INTO diary (user_id, day, mood, flow, pain, note, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                day.isoformat(),
                fields.get("mood", ""),
                fields.get("flow", ""),
                int(fields.get("pain", 0) or 0),
                fields.get("note", ""),
                _now(),
            ),
        )
    await db.commit()


async def toggle_symptom(user_id: int, day: date, code: str) -> bool:
    db = await connect()
    cur = await db.execute(
        "SELECT 1 FROM symptoms WHERE user_id = ? AND day = ? AND code = ?",
        (user_id, day.isoformat(), code),
    )
    if await cur.fetchone():
        await db.execute(
            "DELETE FROM symptoms WHERE user_id = ? AND day = ? AND code = ?",
            (user_id, day.isoformat(), code),
        )
        await db.commit()
        return False
    await db.execute(
        "INSERT INTO symptoms (user_id, day, code) VALUES (?, ?, ?)",
        (user_id, day.isoformat(), code),
    )
    await db.commit()
    return True


async def all_notify_users() -> list[dict[str, Any]]:
    db = await connect()
    cur = await db.execute("SELECT * FROM users WHERE onboarded = 1 AND notify = 1")
    return [dict(r) for r in await cur.fetchall()]


async def add_sex(user_id: int, day: date, protection: str) -> None:
    db = await connect()
    await db.execute(
        "INSERT INTO sex_logs (user_id, day, protection, created_at) VALUES (?, ?, ?, ?)",
        (user_id, day.isoformat(), protection, _now()),
    )
    await db.commit()


async def recent_sex(user_id: int, limit: int = 8) -> list[dict[str, Any]]:
    db = await connect()
    cur = await db.execute(
        "SELECT * FROM sex_logs WHERE user_id = ? ORDER BY day DESC, id DESC LIMIT ?",
        (user_id, limit),
    )
    return [dict(r) for r in await cur.fetchall()]


async def sex_on(user_id: int, day: date) -> bool:
    db = await connect()
    cur = await db.execute(
        "SELECT 1 FROM sex_logs WHERE user_id = ? AND day = ? LIMIT 1",
        (user_id, day.isoformat()),
    )
    return await cur.fetchone() is not None


async def mark_delay(user_id: int, expected: date) -> bool:
    db = await connect()
    try:
        await db.execute(
            "INSERT INTO delay_marks (user_id, expected_date, marked_at) VALUES (?, ?, ?)",
            (user_id, expected.isoformat(), _now()),
        )
        await db.commit()
        return True
    except sqlite3.IntegrityError:
        return False


async def delay_marked(user_id: int, expected: date) -> bool:
    db = await connect()
    cur = await db.execute(
        "SELECT 1 FROM delay_marks WHERE user_id = ? AND expected_date = ?",
        (user_id, expected.isoformat()),
    )
    return await cur.fetchone() is not None


async def create_invite(owner_id: int) -> str:
    db = await connect()
    await db.execute("DELETE FROM invites WHERE owner_id = ?", (owner_id,))
    code = secrets.token_urlsafe(6).replace("-", "x").replace("_", "y")[:10]
    await db.execute(
        "INSERT INTO invites (code, owner_id, created_at) VALUES (?, ?, ?)",
        (code, owner_id, _now()),
    )
    await db.commit()
    return code


async def invite_owner(code: str) -> int | None:
    db = await connect()
    cur = await db.execute("SELECT owner_id FROM invites WHERE code = ?", (code,))
    row = await cur.fetchone()
    return int(row["owner_id"]) if row else None


async def bind_partner(owner_id: int, viewer_id: int) -> None:
    db = await connect()
    await db.execute("DELETE FROM partnerships WHERE owner_id = ?", (owner_id,))
    await db.execute(
        "INSERT INTO partnerships (owner_id, viewer_id, created_at) VALUES (?, ?, ?)",
        (owner_id, viewer_id, _now()),
    )
    await db.execute("DELETE FROM invites WHERE owner_id = ?", (owner_id,))
    await db.commit()


async def unbind_partner(user_id: int) -> None:
    db = await connect()
    await db.execute("DELETE FROM partnerships WHERE owner_id = ? OR viewer_id = ?", (user_id, user_id))
    await db.commit()


async def partner_of(owner_id: int) -> dict[str, Any] | None:
    db = await connect()
    cur = await db.execute(
        """
        SELECT u.* FROM partnerships p
        JOIN users u ON u.tg_id = p.viewer_id
        WHERE p.owner_id = ?
        """,
        (owner_id,),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def owners_for_viewer(viewer_id: int) -> list[dict[str, Any]]:
    db = await connect()
    cur = await db.execute(
        """
        SELECT u.* FROM partnerships p
        JOIN users u ON u.tg_id = p.owner_id
        WHERE p.viewer_id = ?
        """,
        (viewer_id,),
    )
    return [dict(r) for r in await cur.fetchall()]


async def viewers_of(owner_id: int) -> list[int]:
    db = await connect()
    cur = await db.execute(
        "SELECT viewer_id FROM partnerships WHERE owner_id = ?",
        (owner_id,),
    )
    return [int(r["viewer_id"]) for r in await cur.fetchall()]


async def all_users() -> list[dict[str, Any]]:
    db = await connect()
    cur = await db.execute("SELECT * FROM users WHERE onboarded = 1 AND notify = 1")
    return [dict(r) for r in await cur.fetchall()]


async def notify_once(user_id: int, kind: str, day: date) -> bool:
    db = await connect()
    try:
        await db.execute(
            "INSERT INTO notify_sent (user_id, kind, day) VALUES (?, ?, ?)",
            (user_id, kind, day.isoformat()),
        )
        await db.commit()
        return True
    except sqlite3.IntegrityError:
        return False
