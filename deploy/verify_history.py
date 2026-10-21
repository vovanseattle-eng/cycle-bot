#!/usr/bin/env python3
"""Проверка данных cycle-bot на сервере: что реально лежит в базе.

Только чтение (SELECT). Ничего не меняет и не удаляет.

Запуск (из каталога проекта):
    .venv/bin/python deploy/verify_history.py

Показывает по каждому пользователю:
  - сколько строк в sex_logs (с дублями);
  - сколько уникальных дней (это то, что увидит клиент);
  - есть ли исторические дубли и как они отображаются;
  - что именно покажет карточка «Близость» и «Вся история».
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import db, texts  # noqa: E402
from app.dates import fmt_day  # noqa: E402


async def main() -> int:
    conn = await db.connect()

    cur = await conn.execute("SELECT DISTINCT user_id FROM sex_logs ORDER BY user_id")
    users = [int(r["user_id"]) for r in await cur.fetchall()]

    if not users:
        print("В sex_logs нет ни одной записи.")
        await db.close()
        return 0

    print(f"Пользователей с отметками: {len(users)}\n")

    total_dupes = 0
    for uid in users:
        cur = await conn.execute(
            "SELECT COUNT(*) AS c FROM sex_logs WHERE user_id = ?", (uid,)
        )
        raw = int((await cur.fetchone())["c"])

        cur = await conn.execute(
            "SELECT day, COUNT(*) AS c FROM sex_logs WHERE user_id = ? "
            "GROUP BY day HAVING c > 1 ORDER BY day DESC",
            (uid,),
        )
        dupes = [(r["day"], int(r["c"])) for r in await cur.fetchall()]

        cur = await conn.execute("SELECT name FROM users WHERE tg_id = ?", (uid,))
        row = await cur.fetchone()
        name = (row["name"] if row else "") or "без имени"

        unique = await db.sex_days_count(uid)
        shown = await db.recent_sex(uid)

        print(f"--- пользователь {uid} ({name}) ---")
        print(f"  строк в базе: {raw} | уникальных дней: {unique}")
        if dupes:
            total_dupes += len(dupes)
            print(f"  исторических дублей: {len(dupes)}")
            for day, c in dupes[:5]:
                print(f"    {fmt_day(date.fromisoformat(day))} — {c} строки (в истории видна одна)")
        else:
            print("  дублей нет")

        print("  что увидит в «Близости»:")
        for r in shown[:5]:
            prot = texts.PROTECTION_LABEL.get(r["protection"], "Как есть")
            print(f"    {fmt_day(date.fromisoformat(r['day']))} · {prot}")
        if unique > len(shown[:5]):
            print(f"    ... и ещё {unique - len(shown[:5])} — в «Вся история»")

        print("  вся история (все страницы):")
        page = 0
        while True:
            prows = await db.recent_sex(uid, limit=5, offset=page * 5)
            if not prows:
                break
            days = ", ".join(fmt_day(date.fromisoformat(r["day"])) for r in prows)
            print(f"    стр. {page + 1}: {days}")
            page += 1
            if page > 50:
                break
        print()

    print(f"Итого исторических дублей по всем пользователям: {total_dupes}")
    print("Дубли не удалены — они лежат в базе и показываются как одна запись.")

    await db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
