# Design — partner-cycle-notify

## Решения (D-лист)

### D1: day-N уведомления через `daily_tick`, без новых таблиц
В `app/notify.py::daily_tick` после существующего блока регистрации kinds добавить:

```python
if snap.phase == PHASE_PERIOD and snap.red_start and snap.today > snap.red_start:
    from app.cycle import clamp_period_length, red_window  # использовать уже импортированные helpers
    _red_s, _red_e = red_window(snap.red_start, snap.period_length)
    if snap.red_start < snap.today <= _red_e:
        n = (snap.today - snap.red_start).days + 1
        kind = f"red_day{n}"
        if await db.notify_once(user["tg_id"], kind, snap.today):
            await ping_viewers(bot, user, "red_day", extra=f"день {n}")
```

- Dedup — `notify_sent` (owner_id, kind `red_dayN`, date). Схема не трогается. Дни с N≥2 (день 1 остаётся закреплён за `red_today`).
- only_partner: сообщение уходит ТОЛЬКО partners (через ping_viewers). Сам владелец день-N не получает (выбор пользователя) — это не классический send_message ветка, а отдельный ificers до kinds-цикла.
- Время: owner's notify_hour — уже гарантировано daily_tick (он итерируется по owner и отфильтрован по hour_in(owner.tz)).

### D2: `ping_viewers` — новый kind "red_day" + снятие share_sex гейта

В `ping_viewers`:
- Добавить ветку `elif kind == "red_day": body = f"Красные дни · {extra} у {name}"` (extra = «день 2» и т.п.).
- **Удалить гейт** `if kind == "sex" and not owner.get("share_sex"): return` — партнёр теперь всегда получает пинг близости (FR-3).
- Гейт `share_delay` остаётся как есть (FR-5 без регрессий).

### D3: Моментальный пинг на всех путях отметки (`handlers.py`)
Два пути, где `set_period` вызывается без пинга:
- около строки 670 (`purpose != "revise"` ветка: `set_period` → `pick_next` flow): после `await db.set_period(...)` добавить `fresh = await load(call.from_user.id)` + `ping_viewers(call.bot, fresh, "period", extra=fmt_day(chosen))`.
- около строки 691 (ветка «цикл собран», clen-saved): аналогично после `set_period(user["tg_id"], chosen, plen)`.
- путь `nxtd` (строка 825) уже пингует — не трогать.
- revise-путь (строка 664-669): после `revise_period` пинг НЕ добавляем (перенос старой даты ≠ событие «начались») — фиксируем как осознанный выбор; если окажется нужным — отдельная задача аудита.

### D4: UI не соврёт после снятия гейта (`texts.py`, `keyboards.py`)
- `partner_card` (texts.py:454): `kv("Близость", "Открыта" if share_sex else "Скрыта")` → фиксированный `kv("Близость", "Видна партнёру")`.
- `keyboards.py:398` кнопка `tgl:share_sex` — удалить (флаг больше не влияет на доставку; кнопка была бы мёртвой).
- texts.py:592 (privacy summary): `kv('Близость', vis('share_sex', 0))` → фиксированный текст «Видна партнёру» без условия.
- Столбец `users.share_sex` остаётся в БД (не читается для гейта) — миграций нет.
- Схема коллбэков (поправлено по факту кода): на `tgl:share_sex` отвечал общий генерик-обработчик `tgl:` (handlers ~892) — кнопка была рабочей. Мёртвый хвост — отдельный маршрут `set:sexshare` (handlers ~991), на который ничего не ссылается: помечен комментом, код не удалён (минимальный дифф; удаление расширяет дифф без пользы).

## Ошибки и отказы

- send_message к партнёру падает → try/except continue (существующее поведение, не трогаем).
- Первый запуск после деплоя: если тик успел сработать раньше кода — dedup по дате не даст дублей.
- У владельца `period_length` меняется mid-window → red_window пересчитывается на каждом тике, N пересчитывается от фактического `red_start`.

## Тесты (design-уровень)

Новый файл `tests/test_partner_daily.py`:
1. `red_day2_ping` — partner (viewer) получает «Красные дни · день 2» на день 2, владелец НЕ получает.
2. `red_day_once` — повторный вызов daily_tick в тот же день не дублирует (notify_sent dedup).
3. `sex_ping_always` — при share_sex=0 ping_viewers("sex") всё равно уходит партнёру.
4. `day1_no_dup` — на день 1 red_day-ветка не создаёт сообщение (условие red_start < today).
5. `set_period_instant_ping` — путь «цикл собран» пингует мгновенно (mock ping_viewers).

Зафиксированные к тестам данные: fixture из `tests/test_routes.py` (aiogram mock бот) — переиспользовать подход.

## Датаминга нет

- Ни одна таблица не ALTER-ится. Резерв перед деплоем — существующий шаг `update.sh`.
