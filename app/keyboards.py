from __future__ import annotations

import calendar as cal
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.dates import WEEKDAYS, month_title
from app.emoji import E

BTN_HOME = "✦ сегодня"
BTN_CAL = "календарь"
BTN_RED = "красные"
BTN_BLUE = "голубые"
BTN_SEX = "секс"
BTN_DELAY = "задержка"
BTN_TIPS = "советы"
BTN_PARTNER = "партнёр"
BTN_SETTINGS = "ещё"

RED = "danger"


def _b(
    builder: InlineKeyboardBuilder,
    text: str,
    data: str,
    icon: E,
    *,
    style: str | None = None,
) -> None:
    builder.button(text=text, callback_data=data, icon_custom_emoji_id=icon, style=style)


def _back(builder: InlineKeyboardBuilder, data: str = "menu:home") -> None:
    # Текст без ◁ — иначе на кнопке будет и иконка, и стрелка.
    _b(builder, "Назад", data, E.BACK)


def main_menu_kb(viewer: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    _b(b, "Календарь", "menu:cal", E.FILE, style=RED)
    if viewer:
        _b(b, "Советы", "menu:tips", E.INFO)
        _b(b, "Партнёр", "menu:partner", E.PROFILE)
        b.adjust(1, 2)
        return b.as_markup()
    _b(b, "Красные дни", "menu:red", E.FIRE, style=RED)
    _b(b, "Голубые", "menu:blue", E.DESIGN)
    _b(b, "Близость", "menu:sex", E.STAR)
    _b(b, "Задержка", "menu:delay", E.STATS)
    _b(b, "Дневник", "menu:diary", E.EDIT)
    _b(b, "Ещё", "menu:settings", E.SETTINGS)
    b.adjust(1, 1, 2, 2, 1)
    return b.as_markup()


def back_home_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    _back(b)
    b.adjust(1)
    return b.as_markup()


def start_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    _b(b, "Поставить красные дни", "onboard:go", E.FIRE, style=RED)
    b.adjust(1)
    return b.as_markup()


def tos_kb() -> InlineKeyboardMarkup:
    from app.config import CHANNEL_URL, TOS_ARTICLE_URL

    b = InlineKeyboardBuilder()
    b.button(text="Читать соглашение", url=TOS_ARTICLE_URL, icon_custom_emoji_id=E.FILE)
    b.button(text="Подписаться на канал", url=CHANNEL_URL, icon_custom_emoji_id=E.LINK)
    _b(b, "Принимаю", "tos:ok", E.CHECK, style=RED)
    b.adjust(1)
    return b.as_markup()


def period_actions_kb(has_period: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if has_period:
        _b(b, "Поправить эти", "period:edit", E.EDIT, style=RED)
        _b(b, "Новые начались", "period:new", E.FIRE, style=RED)
        _back(b)
        b.adjust(1)
        return b.as_markup()
    _b(b, "Сегодня", "period:today", E.CHECK, style=RED)
    _b(b, "Вчера", "period:yesterday", E.STATS)
    _b(b, "Выбрать дату", "cal:open:period", E.FILE)
    _back(b)
    b.adjust(2, 1, 1)
    return b.as_markup()


def period_edit_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    _b(b, "Сменить дату", "cal:open:revise", E.FILE, style=RED)
    _b(b, "Сменить длительность", "period:len", E.STATS)
    _back(b, "menu:red")
    b.adjust(1)
    return b.as_markup()


def period_new_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    _b(b, "Сегодня", "period:today", E.CHECK, style=RED)
    _b(b, "Вчера", "period:yesterday", E.STATS)
    _b(b, "Выбрать дату", "cal:open:period", E.FILE)
    _back(b, "menu:red")
    b.adjust(2, 1, 1)
    return b.as_markup()


def period_len_kb(back: str = "menu:red") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for n in range(3, 9):
        label = f"{n} дн." + (" обычно" if n == 5 else "")
        _b(b, label, f"plen:{n}", E.CHECK if n == 5 else E.STATS)
    _back(b, back)
    b.adjust(3, 3, 1)
    return b.as_markup()


def cycle_len_kb(back: str = "menu:settings") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for n in (24, 26, 28, 30, 32, 35):
        label = f"{n}" + (" обычно" if n == 28 else "")
        _b(b, label, f"clen:{n}", E.CHECK if n == 28 else E.STATS)
    _back(b, back)
    b.adjust(3, 3, 1)
    return b.as_markup()


def sex_when_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    _b(b, "Сегодня", "sex:today", E.CHECK, style=RED)
    _b(b, "Вчера", "sex:yesterday", E.STATS)
    _b(b, "Другая дата", "cal:open:sex", E.FILE)
    _back(b)
    b.adjust(2, 1, 1)
    return b.as_markup()


def sex_prot_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    _b(b, "С защитой", "sprot:yes", E.CHECK)
    _b(b, "Без защиты", "sprot:no", E.CROSS)
    _b(b, "Не указывать", "sprot:skip", E.EDIT)
    _back(b, "menu:sex")
    b.adjust(1)
    return b.as_markup()


def delay_kb(can_mark: bool, already: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if can_mark and not already:
        _b(b, "Зафиксировать задержку", "delay:mark", E.STATS, style=RED)
    _b(b, "Красные всё-таки начались", "period:today", E.FIRE, style=RED)
    _back(b)
    b.adjust(1)
    return b.as_markup()


def pregnancy_kb(intent: str = "track") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for code, label in (("track", "Слежу за циклом"), ("try", "Планирую"), ("avoid", "Не планирую")):
        _b(b, label, f"preg:{code}", E.CHECK if intent == code else E.EDIT)
    _back(b)
    b.adjust(1)
    return b.as_markup()


def partner_kb(has_partner: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if has_partner:
        _b(b, "Новая ссылка", "pair:invite", E.LINK)
        _b(b, "Отвязать", "pair:drop", E.TRASH, style=RED)
        _back(b)
        b.adjust(2, 1)
    else:
        _b(b, "Пригласить", "pair:invite", E.PROFILE)
        _back(b)
        b.adjust(1, 1)
    return b.as_markup()


def partner_viewer_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    _b(b, "Отвязаться", "pair:drop", E.TRASH, style=RED)
    _back(b)
    b.adjust(1)
    return b.as_markup()


def pair_confirm_kb(code: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    _b(b, "Смотреть цикл", f"pair:yes:{code}", E.CHECK)
    _b(b, "Нет, спасибо", "pair:no", E.CROSS)
    b.adjust(1)
    return b.as_markup()


def settings_kb(user: dict) -> InlineKeyboardMarkup:
    del user
    b = InlineKeyboardBuilder()
    _b(b, "Советы", "menu:tips", E.INFO)
    _b(b, "Беременность", "menu:preg", E.DESIGN)
    _b(b, "История", "menu:history", E.FILE)
    _b(b, "Партнёр", "menu:partner", E.PROFILE)
    _b(b, "Цикл и прогноз", "set:cyclepage", E.STATS)
    _b(b, "Уведомления", "set:notifypage", E.BELL)
    _b(b, "Приватность", "set:privpage", E.PROFILE)
    _b(b, "Часовой пояс", "set:tzpage", E.NAV)
    _back(b)
    b.adjust(2, 2, 1, 1, 1, 1, 1)
    return b.as_markup()


def month_kb(
    year: int,
    month: int,
    purpose: str,
    today: date,
    red: set[date],
    blue: set[date],
    pickable: bool,
) -> InlineKeyboardMarkup:
    cal.setfirstweekday(cal.MONDAY)
    weeks = cal.monthcalendar(year, month)
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="‹", callback_data=f"caln:{purpose}:{_shift(year, month, -1)}", style=RED),
            InlineKeyboardButton(text=month_title(year, month), callback_data="cal:noop"),
            InlineKeyboardButton(text="›", callback_data=f"caln:{purpose}:{_shift(year, month, 1)}", style=RED),
        ],
        [InlineKeyboardButton(text=d, callback_data="cal:noop") for d in WEEKDAYS],
    ]
    for week_days in weeks:
        week: list[InlineKeyboardButton] = []
        for day in week_days:
            if day == 0:
                week.append(InlineKeyboardButton(text=" ", callback_data="cal:noop"))
                continue
            current = date(year, month, day)
            if current in red:
                label = f"{day}°"
            elif current in blue:
                label = f"{day}*"
            elif current == today:
                label = f"·{day}"
            else:
                label = str(day)
            if current == today and current in red:
                label = f"·{day}°"
            elif current == today and current in blue:
                label = f"·{day}*"
            data = f"cald:{purpose}:{current.isoformat()}" if pickable else "cal:noop"
            extra: dict = {"style": RED} if current in red else {}
            week.append(InlineKeyboardButton(text=label, callback_data=data, **extra))
        rows.append(week)
    back = {
        "view": "menu:home",
        "period": "menu:red",
        "onboard": "onboard:go",
        "sex": "menu:sex",
        "next": "set:nextdate",
        "revise": "period:edit",
    }.get(purpose, "menu:home")
    rows.append(
        [
            InlineKeyboardButton(
                text="Назад",
                callback_data=back,
                icon_custom_emoji_id=E.BACK,
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _shift(year: int, month: int, delta: int) -> str:
    month += delta
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return f"{year:04d}-{month:02d}"


def next_period_kb(start: date, back: str = "menu:home") -> InlineKeyboardMarkup:
    from datetime import timedelta

    from app.cycle import add_months

    monthly = add_months(start, 1)
    b = InlineKeyboardBuilder()
    for n in (26, 28, 30, 31):
        d = start + timedelta(days=n)
        label = f"{n} дн. · {d.day:02d}.{d.month:02d}"
        _b(b, label, f"nxtd:{n}:i", E.CHECK if n == 28 else E.STATS)
    _b(b, f"То же число · {monthly.day:02d}.{monthly.month:02d}", "nxtd:0:m", E.CHECK)
    _b(b, "Выбрать дату", "cal:open:next", E.FILE)
    _back(b, back)
    b.adjust(2, 2, 1, 1, 1)
    return b.as_markup()


def settings_cycle_kb(user: dict) -> InlineKeyboardMarkup:
    cl = int(user.get("cycle_length") or 28)
    pl = int(user.get("period_length") or 5)
    lu = int(user.get("luteal_days") or 14)
    fb = int(user.get("fertile_before") if user.get("fertile_before") is not None else 6)
    fa = int(user.get("fertile_after") if user.get("fertile_after") is not None else 3)
    mode = "Прогноз: число месяца" if user.get("predict_mode") == "monthly" else "Прогноз: интервал"
    b = InlineKeyboardBuilder()
    _b(b, mode, "tgl:predict_mode", E.SETTINGS)
    _b(b, f"Цикл {cl} −", "adj:cl:-1", E.STATS)
    _b(b, f"Цикл {cl} +", "adj:cl:1", E.CHECK)
    _b(b, f"Красные {pl} −", "adj:pl:-1", E.STATS)
    _b(b, f"Красные {pl} +", "adj:pl:1", E.CHECK)
    _b(b, f"Лютеин. {lu} −", "adj:lu:-1", E.STATS)
    _b(b, f"Лютеин. {lu} +", "adj:lu:1", E.CHECK)
    _b(b, f"До овул. {fb} −", "adj:fb:-1", E.STATS)
    _b(b, f"До овул. {fb} +", "adj:fb:1", E.CHECK)
    _b(b, f"После {fa} −", "adj:fa:-1", E.STATS)
    _b(b, f"После {fa} +", "adj:fa:1", E.CHECK)
    _b(b, "Следующие красные", "set:nextdate", E.FILE, style=RED)
    _back(b, "menu:settings")
    b.adjust(1, 2, 2, 2, 2, 2, 1, 1)
    return b.as_markup()


def settings_notify_kb(user: dict) -> InlineKeyboardMarkup:
    def lab(on: bool, title: str) -> str:
        return f"{title}: Вкл" if on else f"{title}: Выкл"

    hour = int(user.get("notify_hour") or 9)
    b = InlineKeyboardBuilder()
    _b(b, lab(bool(user.get("notify", 1)), "Все"), "tgl:notify", E.BELL)
    _b(b, f"Час {hour} −", "adj:nh:-1", E.STATS)
    _b(b, f"Час {hour} +", "adj:nh:1", E.CHECK)
    _b(b, lab(bool(user.get("notify_red", 1)), "Красные"), "tgl:notify_red", E.FIRE)
    _b(b, lab(bool(user.get("notify_before", 1)), "За день"), "tgl:notify_before", E.FIRE)
    _b(b, lab(bool(user.get("notify_blue", 1)), "Голубые"), "tgl:notify_blue", E.DESIGN)
    _b(b, lab(bool(user.get("notify_delay", 1)), "Задержка"), "tgl:notify_delay", E.STATS)
    _back(b, "menu:settings")
    b.adjust(1, 2, 1, 1, 1, 1, 1)
    return b.as_markup()


def settings_privacy_kb(user: dict) -> InlineKeyboardMarkup:
    def lab(on: bool, title: str) -> str:
        return f"{title}: Открыто" if on else f"{title}: Скрыто"

    b = InlineKeyboardBuilder()
    _b(b, lab(bool(user.get("share_sex")), "Близость"), "tgl:share_sex", E.STAR)
    _b(b, lab(bool(user.get("share_delay", 1)), "Задержка"), "tgl:share_delay", E.STATS)
    _b(b, lab(bool(user.get("share_diary")), "Дневник"), "tgl:share_diary", E.EDIT)
    _back(b, "menu:settings")
    b.adjust(1)
    return b.as_markup()


def settings_tz_kb() -> InlineKeyboardMarkup:
    from app.texts import TZ_LABELS

    b = InlineKeyboardBuilder()
    for tz, label in TZ_LABELS.items():
        _b(b, label, f"tz:{tz}", E.NAV)
    _back(b, "menu:settings")
    b.adjust(2, 2, 2, 2, 1, 1)
    return b.as_markup()


def diary_kb(entry: dict) -> InlineKeyboardMarkup:
    from app.texts import FLOWS, MOODS, SYMPTOMS

    main_symptoms = ("cramp", "head", "tired", "bloat", "breast", "nausea")
    b = InlineKeyboardBuilder()
    for code, label in MOODS.items():
        _b(b, label, f"mood:{code}", E.STAR if entry.get("mood") == code else E.EDIT)
    for code, label in FLOWS.items():
        _b(b, label, f"flow:{code}", E.FIRE if entry.get("flow") == code else E.EDIT)
    for n in range(0, 6):
        _b(b, f"Боль {n}", f"pain:{n}", E.CHECK if int(entry.get("pain") or 0) == n else E.LIGHTNING)
    for code in main_symptoms:
        on = code in (entry.get("symptoms") or [])
        _b(b, SYMPTOMS[code], f"sym:{code}", E.CHECK if on else E.INFO)
    _b(b, "Заметка", "diary:note", E.WRITE)
    _back(b)
    b.adjust(3, 3, 2, 2, 3, 3, 3, 3, 1, 1)
    return b.as_markup()
