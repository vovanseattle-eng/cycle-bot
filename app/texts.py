from __future__ import annotations

from datetime import date
from html import escape

from app.cycle import (
    MODE_MONTHLY,
    PHASE_DELAY,
    PHASE_FERTILE,
    PHASE_FOLLICULAR,
    PHASE_LUTEAL,
    PHASE_PERIOD,
    PHASE_UNKNOWN,
    CycleSnapshot,
    progress_bar,
)
from app.dates import fmt_day, fmt_range, greet, plural_days
from app.emoji import E, em

DISCLAIMER = "Прогноз по среднему циклу. Это не врач и не контрацепция."

INTENT_TRACK = "track"
INTENT_TRY = "try"
INTENT_AVOID = "avoid"
INTENT_LABEL = {
    INTENT_TRACK: "Слежу за циклом",
    INTENT_TRY: "Планирую беременность",
    INTENT_AVOID: "Не планирую",
}

PROTECTION_LABEL = {
    "yes": "С защитой",
    "no": "Без защиты",
    "skip": "Как есть",
}

TIPS = {
    PHASE_PERIOD: [
        "Тепло на низ живота и вода без геройства.",
        "Железо: гречка, печень, зелень. Кофе чуть отодвинь.",
        "Спорт мягкий: прогулка, растяжка.",
        "Секс можно, если хочется и нет боли.",
    ],
    PHASE_FOLLICULAR: [
        "Энергия поднимается — удобное окно для дел и тренировок.",
        "Кожа и настроение чаще спокойнее.",
        "Сон всё равно важнее любых советов.",
        "Красные закончились — живи в своём ритме.",
    ],
    PHASE_FERTILE: [
        "Голубые дни: шанс зачатия выше. Календарь врёт реже, чем хочется.",
        "Либидо часто выше — это нормально.",
        "Яйцеклетка около суток, сперматозоиды до пяти дней.",
        "Не в планах беременность — только надёжная защита.",
    ],
    PHASE_LUTEAL: [
        "Тянет на соль и сладкое, нервы тоньше. Это биология.",
        "Магний, прогулка, меньше кофеина.",
        "Грудь и живот могут налиться — одежда без войны с телом.",
        "Тяжёлый ПМС несколько циклов — к врачу, не к терпению.",
    ],
    PHASE_DELAY: [
        "Бывает от стресса, переезда, болезни, недосыпа.",
        "Секс без защиты — тест с первого дня, повтор через 2–3.",
        "Неделя без беременности — ещё не катастрофа.",
        "Десять дней и тишина теста — к гинекологу, не в гугл ночью.",
    ],
}

PHASE_ICON = {
    PHASE_PERIOD: E.FIRE,
    PHASE_FOLLICULAR: E.SPARKLE,
    PHASE_FERTILE: E.DESIGN,
    PHASE_LUTEAL: E.STAR,
    PHASE_DELAY: E.STATS,
    PHASE_UNKNOWN: E.INFO,
}

PHASE_NAME = {
    PHASE_PERIOD: "Красные дни",
    PHASE_FOLLICULAR: "Фолликулярная фаза",
    PHASE_FERTILE: "Голубые дни",
    PHASE_LUTEAL: "Лютеиновая фаза",
    PHASE_DELAY: "Задержка",
    PHASE_UNKNOWN: "Не отмечен",
}


MOODS = {
    "good": "Хорошо",
    "ok": "Норм",
    "sad": "Грусть",
    "mad": "Злость",
    "anx": "Тревога",
    "tired": "Усталость",
}
FLOWS = {
    "spot": "Мазня",
    "light": "Слабо",
    "mid": "Средне",
    "heavy": "Сильно",
}
SYMPTOMS = {
    "cramp": "Спазмы",
    "head": "Голова",
    "acne": "Кожа",
    "tired": "Усталость",
    "bloat": "Вздутие",
    "back": "Поясница",
    "breast": "Грудь",
    "nausea": "Тошнота",
    "sleep": "Сон",
    "hunger": "Аппетит",
}
TZ_LABELS = {
    "Europe/Kaliningrad": "Калининград",
    "Europe/Moscow": "Москва",
    "Europe/Samara": "Самара",
    "Asia/Yekaterinburg": "Екатеринбург",
    "Asia/Omsk": "Омск",
    "Asia/Krasnoyarsk": "Красноярск",
    "Asia/Irkutsk": "Иркутск",
    "Asia/Yakutsk": "Якутск",
    "Asia/Vladivostok": "Владивосток",
}


def head(icon: E, title: str, slogan: str) -> str:
    if slogan:
        return f"{em(icon)} <b>{title}</b>\n<i>{slogan}</i>"
    return f"{em(icon)} <b>{title}</b>"


def header(title: str) -> str:
    return head(E.BELL, f"ЛУНА · {escape(title).upper()}", "Тихое обновление цикла")


def kv(name: str, value: str) -> str:
    return f"<b>{name}</b>  <code>{escape(value)}</code>"


def named(title: str, body: str, icon: E | None = None, expandable: bool = False) -> str:
    """Иконка только у заголовка, внутри цитаты — текст без смайликов."""
    label = f"{em(icon)} <b>{title}</b>" if icon else f"<b>{title}</b>"
    open_tag = "blockquote expandable" if expandable else "blockquote"
    return f"{label}\n<{open_tag}>{body}</blockquote>"


def pack(title: str, *rows: str, icon: E | None = None, expandable: bool = False) -> str:
    return named(title, "\n".join(row for row in rows if row), icon=icon, expandable=expandable)


def _bar(snap: CycleSnapshot) -> str:
    return f"<code>{progress_bar(snap.cycle_day, snap.cycle_length, snap.delay_days)}</code>"


def home_card(snap: CycleSnapshot, name: str = "", for_partner: bool = False, tz: str | None = None) -> str:
    who = escape(name) if name else ""
    if for_partner and who:
        slogan = f"Цикл · {who}"
        title = "ЛУНА · ПАРТНЁР"
    else:
        slogan = greet(name, tz)
        title = "ЛУНА · СЕГОДНЯ"
    lines = [head(E.FIRE, title, slogan), ""]

    if snap.phase == PHASE_UNKNOWN or snap.last_start is None:
        lines.append(named(
            "С чего начать",
            "Нажми «Красные дни» — первый день последних месячных. Голубые луна посчитает сама.",
            E.INFO,
        ))
        return "\n".join(lines)

    phase = PHASE_NAME[snap.phase]
    day = snap.cycle_day or 1
    bits = [phase]
    if snap.phase == PHASE_DELAY:
        bits.append(plural_days(snap.delay_days))
    else:
        bits.append(f"День {day} из {snap.cycle_length}")
    bits.append(_bar(snap))
    if snap.red_start and snap.red_end:
        bits.append(f"Красные {fmt_range(snap.red_start, snap.red_end)}")
    if snap.blue_start and snap.blue_end:
        bits.append(f"Голубые {fmt_range(snap.blue_start, snap.blue_end)}")
    if snap.next_period:
        nxt = fmt_day(snap.next_period)
        if snap.days_until is not None and snap.days_until > 0:
            nxt += f" · через {plural_days(snap.days_until)}"
        elif snap.days_until == 0:
            nxt += " · сегодня"
        bits.append(f"Следующие {nxt}")
    lines.append(named("Сейчас", "\n".join(bits), PHASE_ICON[snap.phase]))
    return "\n".join(lines)


def calendar_card(snap: CycleSnapshot, picking: bool = False) -> str:
    slogan = "Нажми день в сетке" if picking else "Голубые дни считает луна"
    lines = [head(E.FILE, "ЛУНА · КАЛЕНДАРЬ", slogan), ""]
    if snap.last_start is None:
        lines.append(named("Календарь", "Сначала поставь красные дни — сетка оживёт.", E.FILE))
        return "\n".join(lines)
    bits = ["° красные · * голубые · · сегодня"]
    if snap.red_start and snap.red_end:
        bits.append(f"Красные {fmt_range(snap.red_start, snap.red_end)}")
    if snap.blue_start and snap.blue_end:
        bits.append(f"Голубые {fmt_range(snap.blue_start, snap.blue_end)}")
    lines.append(named("Сетка", "\n".join(bits), E.FILE))
    return "\n".join(lines)


def period_card(snap: CycleSnapshot) -> str:
    lines = [head(E.FIRE, "ЛУНА · КРАСНЫЕ ДНИ", "Первый день — день 1 цикла"), ""]
    if snap.red_start and snap.red_end:
        lines.append(named("Сейчас в календаре", fmt_range(snap.red_start, snap.red_end), E.FIRE))
        lines.append(named(
            "Что сделать",
            "«Поправить эти» — если ошиблась в дате или длительности. «Новые начались» — если кровотечение уже следующее.",
            E.EDIT,
        ))
    else:
        lines.append(named(
            "Как ставить",
            "Поставь первый день кровотечения. Если месячные уже идут — старт, не «сегодня, потому что вспомнила».",
            E.EDIT,
        ))
    return "\n".join(lines)


def blue_card(snap: CycleSnapshot) -> str:
    lines = [head(E.DESIGN, "ЛУНА · ГОЛУБЫЕ ДНИ", "Считаются сами по прогнозу красных"), ""]
    if snap.blue_start and snap.blue_end and snap.ovulation:
        status = "Сегодня как раз они"
        if snap.today < snap.blue_start:
            status = f"Через {plural_days((snap.blue_start - snap.today).days)}"
        elif not snap.in_blue:
            status = "В этом цикле окно уже прошло"
        lines.append(pack(
            "Окно",
            kv("Дни", fmt_range(snap.blue_start, snap.blue_end)),
            kv("Овуляция", fmt_day(snap.ovulation)),
            kv("Статус", status),
            icon=E.DESIGN,
        ))
    else:
        lines.append(named("Пока пусто", "Голубые появятся, как только будут красные и прогноз следующих.", E.INFO))
    return "\n".join(lines)


def sex_card(rows: list[dict], share: bool) -> str:
    lines = [head(E.STAR, "ЛУНА · БЛИЗОСТЬ", "Без морали и длинного дневника"), ""]
    if rows:
        recent = "\n".join(
            f"{fmt_day(date.fromisoformat(row['day']))} · {PROTECTION_LABEL.get(row['protection'], 'Как есть')}"
            for row in rows[:5]
        )
        lines.append(named("Недавно", recent, E.STAR))
    else:
        lines.append(named("Недавно", "Пока пусто — и это тоже нормально.", E.STAR))
    lines.append(named("Партнёр", "Видит это" if share else "Не видит это", E.PROFILE))
    return "\n".join(lines)


def delay_card(snap: CycleSnapshot, already: bool) -> str:
    lines = [head(E.STATS, "ЛУНА · ЗАДЕРЖКА", "Если прогноз прошёл, а кровотечения нет"), ""]
    if snap.last_start is None:
        lines.append(named("Задержка", "Без даты красных считать не из чего.", E.STATS))
        return "\n".join(lines)
    if snap.delay_days <= 0 and snap.next_period:
        left = (snap.next_period - snap.today).days
        status = "По прогнозу сегодня" if left == 0 else f"Ещё {plural_days(left)}"
        lines.append(pack(
            "Прогноз",
            kv("Красные", fmt_day(snap.next_period)),
            kv("До них", status),
            icon=E.STATS,
        ))
        lines.append(named("Как отметить", "Зафиксировать можно, когда день уже прошёл.", E.EDIT))
    else:
        flag = "Уже стоит, партнёр видит" if already else "Можно зафиксировать — партнёр получит тихое уведомление"
        lines.append(pack(
            "Сейчас",
            kv("Прогноз был", fmt_day(snap.next_period) if snap.next_period else "—"),
            kv("Задержка", plural_days(snap.delay_days)),
            kv("Отметка", flag),
            icon=E.STATS,
        ))
        lines.append(named(
            "Тест",
            "С первого дня задержки, лучше утром. Минус — повтор через 2–3 дня. "
            "Десять дней и тишина теста — к врачу, не в гугл.",
            E.STAR,
        ))
    return "\n".join(lines)


def tips_card(snap: CycleSnapshot, intent: str = INTENT_TRACK) -> str:
    phase = snap.phase if snap.phase in TIPS else PHASE_FOLLICULAR
    intent = intent if intent in INTENT_LABEL else INTENT_TRACK
    lines = [head(E.INFO, "ЛУНА · СОВЕТЫ", PHASE_NAME.get(phase, "")), ""]
    lines.append(named("Что помогает", "\n".join(TIPS[phase]), E.INFO, expandable=True))
    extra = {
        INTENT_TRY: "Если планируешь: фолиевая заранее, как скажет врач. Голубые дни — окно, не гарантия.",
        INTENT_AVOID: "Если не планируешь: календарь не защита. Нужен презерватив или схема от врача.",
        INTENT_TRACK: "Беременность календарь не ставит и не отменяет. В разделе «Беременность» — про тест и окно.",
    }[intent]
    lines.append(named("Беременность", extra, E.DESIGN))
    lines.append(named("Важно", "Не лечение и не диагноз. Если больно — живой врач.", E.INFO))
    return "\n".join(lines)


def pregnancy_card(snap: CycleSnapshot, intent: str = INTENT_TRACK, sex_rows: list[dict] | None = None) -> str:
    intent = intent if intent in INTENT_LABEL else INTENT_TRACK
    lines = [head(E.DESIGN, "ЛУНА · БЕРЕМЕННОСТЬ", "Не тест и не контрацепция"), ""]
    lines.append(named("Цель", INTENT_LABEL[intent], E.DESIGN))

    if snap.blue_start and snap.blue_end:
        if snap.in_blue:
            status = "Сегодня окно"
        elif snap.today < snap.blue_start:
            status = f"Через {plural_days((snap.blue_start - snap.today).days)}"
        else:
            status = "Окно уже прошло"
        lines.append(named(
            "Окно зачатия",
            f"{fmt_range(snap.blue_start, snap.blue_end)} · {status}. "
            "Яйцеклетка ~сутки, сперматозоиды до пяти дней.",
            E.DESIGN,
        ))
    else:
        lines.append(named(
            "Окно зачатия",
            "Появится, когда будут красные дни и прогноз следующих.",
            E.DESIGN,
        ))

    unprotected: list[date] = []
    if snap.last_start and sex_rows:
        for row in sex_rows:
            try:
                day = date.fromisoformat(row["day"])
            except Exception:
                continue
            if row.get("protection") == "no" and snap.last_start <= day <= snap.today:
                unprotected.append(day)

    in_window = bool(
        snap.blue_start
        and snap.blue_end
        and any(snap.blue_start <= day <= snap.blue_end for day in unprotected)
    )

    if snap.phase == PHASE_DELAY:
        n = snap.delay_days
        if n <= 2:
            test = "Можно тест с утра. Минус — повтор через 2–3 дня."
        elif n < 10:
            test = f"Задержка {plural_days(n)}. Сделай тест, при минусе повтор."
        else:
            test = "Десять дней и больше: тест и живой врач, даже если минус."
        if unprotected:
            test += " Была близость без защиты."
        lines.append(named("Тест", test, E.CHECK))
    elif in_window:
        lines.append(named(
            "Тест",
            "Близость без защиты попала в голубые. Тест — с первого дня задержки.",
            E.CHECK,
        ))
    else:
        lines.append(named(
            "Тест",
            "С первого дня задержки, лучше утром. Раньше тест часто молчит.",
            E.CHECK,
        ))

    if intent == INTENT_TRY:
        lines.append(named(
            "Если планируешь",
            "Фолиевая — как скажет врач, обычно до зачатия. "
            "Голубые дни повышают шанс, не гарантируют. "
            "Год попыток до 35 лет, полгода после — к репродуктологу.",
            E.INFO,
            expandable=True,
        ))
    elif intent == INTENT_AVOID:
        lines.append(named(
            "Если не планируешь",
            "Луна не защита. Нужен презерватив или схема от врача, не календарь.",
            E.INFO,
            expandable=True,
        ))
    else:
        lines.append(named(
            "На заметку",
            "Тошнота и грудь бывают и при ПМС. Выбери цель выше — советы станут точнее.",
            E.INFO,
            expandable=True,
        ))

    lines.append(named(
        "Срочно к врачу",
        "Боль с одной стороны, кровь, обморок на задержке — сразу к врачу.",
        E.LIGHTNING,
    ))
    return "\n".join(lines)


def partner_card(has_partner: bool, partner_name: str, share_sex: bool, link: str | None) -> str:
    lines = [head(E.PROFILE, "ЛУНА · ПАРТНЁР", "Один человек, которому это можно видеть"), ""]
    if has_partner:
        lines.append(pack(
            "Доступ",
            kv("Смотрит", partner_name or "без имени"),
            kv("Видит", "Красные, голубые, задержку и прогноз"),
            kv("Близость", "Открыта" if share_sex else "Скрыта"),
            icon=E.PROFILE,
        ))
        lines.append(named("Ссылка", "Новая ссылка гасит старую. Можно отвязать.", E.LINK))
    else:
        lines.append(named(
            "Доступ",
            "Красные, голубые, задержка — как у тебя в боте. Близость по желанию, по умолчанию скрыта.",
            E.PROFILE,
        ))
        if link:
            lines.append(named("Приглашение", f"<code>{escape(link)}</code>", E.LINK))
        else:
            lines.append(named("Приглашение", "Нажми «Пригласить» — будет одноразовая ссылка.", E.LINK))
    return "\n".join(lines)


def partner_invite_card(owner_name: str) -> str:
    shown = escape(owner_name) or "человек"
    return (
        f"{head(E.PROFILE, 'ЛУНА · ПРИГЛАШЕНИЕ', 'Это доверие')}\n\n"
        f"{named('Кто', shown, E.PROFILE)}\n"
        f"{named('Что откроется', 'Красные дни, голубые, задержка и ближайший прогноз. Можно отказаться.', E.INFO)}"
    )


def partner_viewer_card(owner_name: str) -> str:
    shown = escape(owner_name) or "партнёр"
    return (
        f"{head(E.PROFILE, 'ЛУНА · ПАРТНЁР', 'Связанный цикл')}\n\n"
        f"{pack('Статус', kv('Смотришь', shown), kv('Видно', 'Красные, голубые, задержка, прогноз'), icon=E.PROFILE)}\n"
        f"{named('Управление', 'Ты можешь отвязаться в любой момент.', E.INFO)}"
    )


def partner_bound(viewer_name: str) -> str:
    shown = escape(viewer_name) or "человек"
    return f"{header('партнёр')}\n\n{named('Новый зритель', f'{shown} теперь видит твой цикл.', E.PROFILE)}"


def settings_card(user: dict) -> str:
    name = escape(user.get("name") or "без имени")
    period_len = user.get("period_length", 5)
    luteal = user.get("luteal_days", 14)
    hour = user.get("notify_hour", 9)
    mode = "То же число месяца" if user.get("predict_mode") == MODE_MONTHLY else f'{user.get("cycle_length", 28)} дней'
    tz = TZ_LABELS.get(user.get("tz") or "", user.get("tz") or "Москва")
    notify = "Включены" if user.get("notify") else "Выключены"
    return (
        f"{head(E.SETTINGS, 'ЛУНА · ЕЩЁ', 'Советы, партнёр и тонкая настройка')}\n\n"
        f"{pack('Сводка', kv('Имя', name), kv('Прогноз', mode), kv('Красные', f'{period_len} дн.'), kv('Лютеиновая', f'{luteal} дн.'), icon=E.SETTINGS)}\n"
        f"{pack('Ещё', kv('Уведомления', f'{notify} · {hour}:00'), kv('Пояс', tz), kv('Беременность', INTENT_LABEL.get(user.get('intent') or INTENT_TRACK, INTENT_LABEL[INTENT_TRACK])), icon=E.INFO)}"
    )


def tos_card(name: str = "", tz: str | None = None) -> str:
    return (
        f"{head(E.FILE, 'ЛУНА', greet(name, tz))}\n\n"
        f"{named('Чтобы начать', 'Открой соглашение, подпишись на канал и нажми «Принимаю».', E.CHECK)}"
    )


def onboard_intro(name: str = "", tz: str | None = None) -> str:
    return (
        f"{head(E.FIRE, 'ЛУНА', greet(name, tz))}\n\n"
        f"{named('Как это работает', 'Красные дни ставишь ты. Голубые луна считает сама. Остальное — по желанию.', E.INFO)}"
    )


def sex_saved(day_label: str, protection: str) -> str:
    extra = PROTECTION_LABEL.get(protection, "")
    return (
        f"{head(E.CHECK, 'ЛУНА · ОТМЕЧЕНО', 'Тихо легло в календарь')}\n\n"
        f"{named('Запись', f'{day_label} · {extra}', E.CHECK)}"
    )


def period_saved(day_label: str, length: int) -> str:
    return (
        f"{head(E.CHECK, 'ЛУНА · КРАСНЫЕ СТОЯТ', 'Теперь выбери, когда следующие')}\n\n"
        f"{named('Старт', f'{day_label} · {length} дн.', E.FIRE)}"
    )


def pick_day_card(kind: str, day_label: str) -> str:
    if kind == "sex":
        return f"{head(E.STAR, 'ЛУНА · БЛИЗОСТЬ', day_label)}\n\n{named('Как отметить', 'С защитой, без или молча.', E.STAR)}"
    return f"{head(E.FIRE, 'ЛУНА · КРАСНЫЕ ДНИ', f'Старт · {day_label}')}\n\n{named('Длительность', 'Сколько дней обычно идёт', E.FIRE)}"


def cycle_len_card() -> str:
    return (
        f"{head(E.STATS, 'ЛУНА · СЛЕДУЮЩИЕ КРАСНЫЕ', 'Это не 28 дней у всех')}\n\n"
        f"{named('Как выбрать', 'Если обычно одно и то же число месяца — жми «То же число». 16 августа даст 16 сентября, а не 13-е.', E.STATS)}"
    )


def settings_cycle_card(user: dict, snap: CycleSnapshot) -> str:
    mode = "То же число месяца" if user.get("predict_mode") == MODE_MONTHLY else "Интервал в днях"
    nxt = fmt_day(snap.next_period) if snap.next_period else "—"
    cl = user.get("cycle_length", 28)
    pl = user.get("period_length", 5)
    lu = user.get("luteal_days", 14)
    fb = user.get("fertile_before", 5)
    fa = user.get("fertile_after", 1)
    return (
        f"{head(E.STATS, 'ЛУНА · ЦИКЛ', 'Прогноз следующих красных')}\n\n"
        f"{pack('Прогноз', kv('Режим', mode), kv('Длина', f'{cl} дн.'), kv('Следующие', nxt), icon=E.STATS)}\n"
        f"{pack('Фазы', kv('Красные', f'{pl} дн.'), kv('Лютеиновая', f'{lu} дн.'), kv('Голубые', f'{fb} до овуляции, {fa} после'), icon=E.DESIGN)}"
    )


def settings_notify_card(user: dict) -> str:
    def on(key: str, default: int = 1) -> str:
        return "Да" if user.get(key, default) else "Нет"

    hour = user.get("notify_hour", 9)
    return (
        f"{head(E.BELL, 'ЛУНА · УВЕДОМЛЕНИЯ', 'Утром, без спама')}\n\n"
        f"{pack('Рассылка', kv('Все', on('notify')), kv('Час', f'{hour}:00'), kv('Красные сегодня', on('notify_red')), kv('За день до', on('notify_before')), kv('Голубые', on('notify_blue')), kv('Задержка', on('notify_delay')), icon=E.BELL)}"
    )


def settings_privacy_card(user: dict) -> str:
    def vis(key: str, default: int = 0) -> str:
        return "Видит" if user.get(key, default) else "Скрыто"

    return (
        f"{head(E.PROFILE, 'ЛУНА · ПРИВАТНОСТЬ', 'Что видит партнёр')}\n\n"
        f"{pack('Партнёр', kv('Близость', vis('share_sex', 0)), kv('Задержка', vis('share_delay', 1)), kv('Дневник', vis('share_diary', 0)), icon=E.PROFILE)}\n"
        f"{named('Цикл', 'Красные, голубые и прогноз видны всегда, если партнёр привязан.', E.STATS)}"
    )


def settings_tz_card(user: dict) -> str:
    tz = TZ_LABELS.get(user.get("tz") or "", user.get("tz") or "Москва")
    return (
        f"{head(E.NAV, 'ЛУНА · ЧАСОВОЙ ПОЯС', 'Для «сегодня» и уведомлений')}\n\n"
        f"{named('Сейчас', tz, E.NAV)}"
    )


def diary_card(entry: dict, snap: CycleSnapshot) -> str:
    mood = MOODS.get(entry.get("mood") or "", "Не отмечено")
    flow = FLOWS.get(entry.get("flow") or "", "Не отмечено")
    pain = entry.get("pain") or 0
    note = escape(entry.get("note") or "") or "—"
    codes = entry.get("symptoms") or []
    sym = ", ".join(SYMPTOMS[c] for c in codes if c in SYMPTOMS) or "Нет"
    return (
        f"{head(E.EDIT, 'ЛУНА · ДНЕВНИК', f'Сегодня · {fmt_day(snap.today)}')}\n\n"
        f"{pack('Самочувствие', kv('Настроение', mood), kv('Выделения', flow), kv('Боль', str(pain)), kv('Симптомы', sym), icon=E.EDIT)}\n"
        f"{named('Заметка', note, E.WRITE)}"
    )


def history_card(rows: list[dict], snap: CycleSnapshot) -> str:
    nxt = fmt_day(snap.next_period) if snap.next_period else "—"
    if not rows:
        return (
            f"{head(E.FILE, 'ЛУНА · ИСТОРИЯ', 'Прошлые красные и средний цикл')}\n\n"
            f"{named('Записи', 'Пока нет сохранённых циклов.', E.FILE)}\n"
            f"{named('Следующие', nxt, E.STATS)}"
        )
    starts = [date.fromisoformat(r["start_date"]) for r in rows]
    starts_sorted = sorted(starts)
    gaps = [(starts_sorted[i + 1] - starts_sorted[i]).days for i in range(len(starts_sorted) - 1)]
    avg = round(sum(gaps) / len(gaps)) if gaps else snap.cycle_length
    listed = "\n".join(
        f"{fmt_day(date.fromisoformat(row['start_date']))} · {row['length']} дн."
        for row in rows[:6]
    )
    extra = f"\nСредний цикл {avg} дн." if gaps else ""
    return (
        f"{head(E.FILE, 'ЛУНА · ИСТОРИЯ', 'Прошлые красные и средний цикл')}\n\n"
        f"{named('Записи', listed + extra, E.FILE)}\n"
        f"{named('Следующие', nxt, E.STATS)}"
    )
