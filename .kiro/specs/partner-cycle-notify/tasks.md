# Tasks — partner-cycle-notify

## Dependency graph

```
TSK-001 (tests red) ─┬─> TSK-002 (notify.py) ─┐
                     └─> TSK-003 (daily_tick) ├─> TSK-005 (pytest green)
TSK-004 (handlers ping) ─────────────────────┤
TSK-006 (UI честный) ────────────────────────┘
TSK-005 ─> TSK-007 (commit+push) ─> TSK-008 (deploy с бэкапом) ─> TSK-009 (verify на сервере)
TSK-010 (аудит мелких багов) — независимо, до TSK-007
```

## Tasks

### TSK-001 — Red-тесты
- **Requirement:** FR-1, FR-3, NFR-2 (AC-1, AC-2, AC-4)
- **Deliverables:** `tests/test_partner_daily.py` — 6 тестов (5 из design.md + sex-без-гейта), все падают (red).
- **Acceptance:** `pytest tests/test_partner_daily.py` → FAIL список точно на новый код.
- Зависимости: нет. Статус: ✅ (red подтверждён ImportError на `ping_period_marked`; позже все 6 зелёные — 6 passed)

### TSK-002 — ping_viewers: kind "red_day" + снятие гейта sex
- **Requirement:** FR-1, FR-3
- **Deliverables:** `app/notify.py` — ветка red_day в ping_viewers, удаление `if kind == "sex" and not owner.get("share_sex"): return`.
- **Acceptance:** Тесты TSK-001 п1, п3 → зелёные.
- Зависимости: TSK-001. Статус: ✅

### TSK-003 — daily_tick day-N блок
- **Requirement:** FR-1, FR-2
- **Deliverables:** `app/notify.py::daily_tick` — блок red_dayN + dedup + only-partner.
- **Acceptance:** Тесты TSK-001 п1, п2, п4 → зелёные.
- Зависимости: TSK-001. Статус: ✅ (условие `red_start < today <= red_end`, `day_n = (today - red_start).days + 1`)

### TSK-004 — Моментальный пинг на путях set_period без пинга
- **Requirement:** FR-4 (AC-3)
- **Deliverables:** `app/handlers.py` — helper `ping_period_marked` (после `load`), вызовы на обоих путях set_period (в т.ч. set_period_len).
- **Acceptance:** Тест TSK-001 п5 → зелёный.
- Зависимости: TSK-001. Статус: ✅

### TSK-006 — UI после снятия гейта (texts, keyboards)
- **Requirement:** FR-3 (честный UI), NFR-3
- **Deliverables:** texts.py:partner_card — «Видна партнёру»; keyboards.py — удалить toggle-кнопку близости; texts.py:592 — фиксированный текст; handlers.py — мёртвый `set:sexshare` помечен комментом.
- **Acceptance:** `pytest tests/test_texts.py tests/test_routes.py` — зелёные.
- Зависимости: TSK-001. Статус: ✅ (test_texts держится только на длину — строка стала короче)

### TSK-010 — Аудит notify-потока на мелкие баги
- **Requirement:** FR-6
- **Deliverables:** пройти все места ping_viewers/notify_once; находки — фиксить в этом же PR либо зафиксировать решение.
- **Acceptance:** список мест пройден, вывод зафиксирован `Факт:`.
- Зависимости: нет. Статус: ✅ (см. Факт ниже)

### TSK-005 — pytest полный, green
- **Requirement:** NFR-2
- **Deliverables:** `pytest` полный прогон — 0 FAIL.
- **Acceptance:** exit 0; пост-гейт.
- Зависимости: TSK-002, TSK-003, TSK-004, TSK-006, TSK-010. Статус: ✅ (**66 passed**, было 60 + 6 новых)

### TSK-007 — commit + push
- **Requirement:** NFR-1, NFR-3
- **Deliverables:** коммиты по логике изменений (tests / notify / handlers / ui); пуш в origin main.
- **Acceptance:** `git log` чистый; raw.githubusercontent.com отдаёт новые файлы (HTTP 200).
- Зависимости: TSK-005. Статус: ⬜

### TSK-008 — Deploy на сервер с бэкапом
- **Requirement:** NFR-1, AC-5
- **Deliverables:** запуск `update.sh` (бэкап luna.db → curl новых файлов → pip → pm2 restart cycle-bot).
- **Acceptance:** файл бэкапа свежий; pm2 cycle-bot online; схема таблиц не изменилась (PRAGMA table_info до/после).
- Зависимости: TSK-007. Статус: ⬜

### TSK-009 — Post-deploy verify
- **Requirement:** NFR-1, AC-4, AC-5
- **Deliverables:** `deploy/verify_history.py` или проверки на сервере; наблюдение следующего дня N — в `Факт:`.
- **Acceptance:** логи PM2 без ошибок, notify_sent получает kind `red_dayN` ровно 1 запись на день.
- Зависимости: TSK-008. Статус: ⬜

## Progress

| Task | Было | Стало | Проверено чем |
| --- | --- | --- | --- |
| TSK-001 | нет тестов | 6 red-тестов → 6 green | pytest (ImportError red, потом 6 passed) |
| TSK-002 | гейт share_sex пинал близость; red_day не было | ветка red_day, гейт снят | тест sex/share_sex=0, тест red_day2 |
| TSK-003 | партнёр узнавал только о дне 1/прогнозе | день N партнёру, дедуп, владелице тишина | тесты day2/дедуп/день-1/вне окна |
| TSK-004 | set_period_len терял пинг | helper + 2 пинга | тест ping_period_marked |
| TSK-006 | UI врал про toggle близости | честные тексты, кнопка убрана, dead handler помечен | test_texts + test_routes зелёные |
| TSK-010 | — | аудит пройден, изменений не потребовал | см. Факт |
| TSK-005 | 60 passed | 66 passed | `pytest tests/ -q` |
| TSK-007 | ⬜ | ⬜ | — |
| TSK-008 | ⬜ | ⬜ | — |
| TSK-009 | ⬜ | ⬜ | — |

## Факт: аудит notify-потока (TSK-010)

- ping_viewers — все kind ветки: period / sex / fertile / delay / red_day; гейт остался только на delay (share_delay, осознанно).
- Пинг «period» на `nxtd:`-пути — только при `came_from_period` (это onboarding/правка прямо после отметки красных) — поведение корректное, не баг; подтверждение прогноза без отметки пинга не шлёт.
- `set:sexshare` в handlers — мёртвый маршрут (клавиатура шлёт `tgl:share_sex`, который ловит общий `tgl_value`); помечен комментом, не удалён (минимальный дифф).
- Дедуп `notify_once` — UNIQUE(user_id, kind, day); kind `red_day{N}` — новые строки, миграций не потребовалось.

## Факт: попутная находка (несоответствие спеки)

- В design D4 тезис «кнопка Близость мёртвая» был ошибкой: генерик-обработчик `tgl:` существует (handlers ~892). Реальное решение: toggle удалён не из-за бага, а потому что гейт снят (FR-3) — проверять было нечего, кнопка предлагала выбор, которого больше нет. Дизайн-док поправлен.
