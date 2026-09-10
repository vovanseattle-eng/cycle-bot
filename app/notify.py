from __future__ import annotations

from html import escape

from aiogram import Bot

from app import db
from app.cycle import PHASE_DELAY, PHASE_FERTILE, PHASE_PERIOD
from app.emoji import E
from app.dates import hour_in
from app.state import user_snap
from app.texts import head, named


async def ping_viewers(bot: Bot, owner: dict, kind: str, extra: str = "") -> None:
    name = escape(owner.get("name") or "партнёр")
    if kind == "period":
        body = f"У {name} начались красные дни"
        if extra:
            body += f" · {extra}"
    elif kind == "delay":
        body = f"У {name} задержка"
        if extra:
            body += f" · {extra} дн."
    elif kind == "period_soon":
        body = f"У {name} завтра по прогнозу красные дни"
    elif kind == "sex":
        body = f"{name} отметила близость"
        if extra:
            body += f" · {extra}"
    elif kind == "fertile":
        body = f"У {name} сегодня голубые дни"
    else:
        body = extra or f"Обновление цикла · {name}"

    if kind == "sex" and not owner.get("share_sex"):
        return
    if kind == "delay" and not owner.get("share_delay", 1):
        return

    text = f"{head(E.PROFILE, 'ЭТО НЕ FLO · ПАРТНЁР', 'Тихое обновление')}\n\n{named('Что случилось', body, E.PROFILE)}"
    for viewer_id in await db.viewers_of(owner["tg_id"]):
        try:
            await bot.send_message(viewer_id, text)
        except Exception:
            continue


async def daily_tick(bot: Bot) -> None:
    for user in await db.all_users():
        want_hour = int(user.get("notify_hour") or 9)
        if hour_in(user.get("tz")) != want_hour:
            continue
        snap = user_snap(user)
        if snap.last_start is None:
            continue
        kinds: list[tuple[str, str]] = []
        if user.get("notify_red", 1) and snap.phase == PHASE_PERIOD and snap.red_start == snap.today:
            kinds.append(("red_today", f"{head(E.FIRE, 'ЭТО НЕ FLO · КРАСНЫЕ ДНИ', '')}\n\n{named('Сегодня', 'Первый день цикла.', E.FIRE)}"))
        if user.get("notify_blue", 1) and snap.phase == PHASE_FERTILE and snap.blue_start == snap.today:
            kinds.append(("blue_today", f"{head(E.DESIGN, 'ЭТО НЕ FLO · ГОЛУБЫЕ ДНИ', '')}\n\n{named('Окно', 'Открылось. Это оценка, не контрацепция.', E.DESIGN)}"))
        if user.get("notify_delay", 1) and snap.phase == PHASE_DELAY and snap.delay_days == 1:
            kinds.append(("delay_1", f"{head(E.STATS, 'ЭТО НЕ FLO · ЗАДЕРЖКА', '')}\n\n{named('Статус', 'Прогноз красных уже вчера.', E.STATS)}"))
        if user.get("notify_delay", 1) and snap.phase == PHASE_DELAY and snap.delay_days == 7:
            kinds.append(("delay_7", f"{head(E.STATS, 'ЭТО НЕ FLO · ЗАДЕРЖКА', '')}\n\n{named('Статус', 'Неделя. Если был секс без защиты — тест.', E.STATS)}"))
        if user.get("notify_before", 1) and snap.next_period and (snap.next_period - snap.today).days == 1:
            kinds.append(("red_tomorrow", f"{head(E.BELL, 'ЭТО НЕ FLO · ЗАВТРА', '')}\n\n{named('Прогноз', 'Завтра красные дни.', E.BELL)}"))

        for kind, text in kinds:
            if await db.notify_once(user["tg_id"], kind, snap.today):
                try:
                    await bot.send_message(user["tg_id"], text)
                except Exception:
                    pass
                notify_kind = {
                    "red_today": "period",
                    "blue_today": "fertile",
                    "delay_1": "delay",
                    "delay_7": "delay",
                    "red_tomorrow": "period_soon",
                }[kind]
                extra = "завтра" if kind == "red_tomorrow" else ""
                await ping_viewers(bot, user, notify_kind, extra=extra)
