from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

from app import db, texts
from app.config import BOT_USERNAME, CHANNEL_USERNAME
from app.cycle import MODE_INTERVAL, MODE_MONTHLY, add_months, apply_next_date, cfg_from_user, marks_for_month
from app.dates import fmt_day, today_in
from app.helpers import show
from app.keyboards import (
    BTN_BLUE,
    BTN_CAL,
    BTN_DELAY,
    BTN_HOME,
    BTN_PARTNER,
    BTN_RED,
    BTN_SETTINGS,
    BTN_SEX,
    BTN_TIPS,
    back_home_kb,
    delay_kb,
    diary_kb,
    main_menu_kb,
    month_kb,
    next_period_kb,
    pair_confirm_kb,
    partner_kb,
    partner_viewer_kb,
    period_actions_kb,
    period_edit_kb,
    period_len_kb,
    period_new_kb,
    pregnancy_kb,
    settings_cycle_kb,
    settings_kb,
    settings_notify_kb,
    settings_privacy_kb,
    settings_tz_kb,
    sex_prot_kb,
    sex_when_kb,
    start_kb,
    tos_kb,
)
from app.notify import ping_viewers
from app.state import Flow, user_snap

router = Router()

_MEMBER_OK = {
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
}

_tos_ok: set[int] = set()


class TosGate(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)
        if from_user is None:
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and (event.data or "").startswith("tos:"):
            return await handler(event, data)
        if isinstance(event, Message) and (event.text or "").startswith("/start"):
            return await handler(event, data)
        if from_user.id in _tos_ok:
            return await handler(event, data)
        user = await db.get_user(from_user.id)
        if user and int(user.get("tos_accepted") or 0):
            _tos_ok.add(from_user.id)
            return await handler(event, data)
        if isinstance(event, CallbackQuery):
            try:
                await event.answer("Сначала соглашение и подписка на канал.", show_alert=True)
            except Exception:
                pass
        fresh = user or await db.ensure_user(from_user.id, from_user.first_name or "")
        await show(event, "welcome", texts.tos_card(fresh.get("name") or from_user.first_name or "", fresh.get("tz")), tos_kb())
        return


router.message.middleware(TosGate())
router.callback_query.middleware(TosGate())


class FastAck(BaseMiddleware):
    """Снимает часики с кнопки до тяжёлой работы. Алерты tos:/diary:note оставляем хендлеру."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, CallbackQuery):
            raw = event.data or ""
            if not raw.startswith(("tos:", "diary:note")):
                try:
                    await event.answer()
                except Exception:
                    pass
        return await handler(event, data)


router.callback_query.middleware(FastAck())


async def is_subscribed(bot, user_id: int) -> tuple[bool, str]:
    if not CHANNEL_USERNAME:
        return True, ""
    try:
        member = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
    except Exception as e:
        err = str(e).lower()
        if "member list is inaccessible" in err or "administrator" in err or "chat not found" in err:
            return False, f"Не вижу канал. Бот должен быть админом @{CHANNEL_USERNAME} — иначе подписку не проверить."
        return False, "Не удалось проверить подписку. Открой канал и нажми «Принимаю» ещё раз."
    if member.status in _MEMBER_OK:
        return True, ""
    if member.status == ChatMemberStatus.RESTRICTED and getattr(member, "is_member", False):
        return True, ""
    return False, "Сначала подпишись на канал, потом жми «Принимаю» ещё раз."


async def load(tg_id: int, name: str = "") -> dict:
    return await db.ensure_user(tg_id, name)


def _is_viewer_only(me: dict, viewing_other: bool) -> bool:
    return viewing_other and not me.get("onboarded")


async def send_home(target: Message | CallbackQuery, user: dict) -> None:
    me_id = target.from_user.id
    me = await db.get_user(me_id) or user
    snap = user_snap(user)
    viewing_other = False
    name = user.get("name") or ""
    if not user.get("onboarded"):
        owners = await db.owners_for_viewer(user["tg_id"])
        if owners:
            user = owners[0]
            snap = user_snap(user)
            name = user.get("name") or ""
            viewing_other = True
        else:
            await show(target, "welcome", texts.onboard_intro(user.get("name") or "", user.get("tz")), start_kb())
            return
    text = texts.home_card(snap, name=name, for_partner=viewing_other, tz=user.get("tz"))
    await show(target, "home", text, main_menu_kb(viewer=_is_viewer_only(me, viewing_other)))


async def viewed_user(tg_id: int) -> dict:
    user = await load(tg_id)
    if user.get("onboarded"):
        return user
    owners = await db.owners_for_viewer(tg_id)
    return owners[0] if owners else user


async def send_calendar(
    target: Message | CallbackQuery,
    user: dict,
    purpose: str,
    year: int | None = None,
    month: int | None = None,
) -> None:
    snap = user_snap(user)
    today = snap.today
    year = year or today.year
    month = month or today.month
    cfg = cfg_from_user(user, today)
    red, blue, _ = marks_for_month(
        snap.last_start,
        cfg.cycle_length,
        cfg.period_length,
        year,
        month,
        luteal_days=cfg.luteal_days,
        fertile_before=cfg.fertile_before,
        fertile_after=cfg.fertile_after,
        predict_mode=cfg.predict_mode,
        next_override=cfg.next_override,
    )
    pickable = purpose in {"period", "onboard", "sex", "next", "revise"}
    await show(
        target,
        "calendar",
        texts.calendar_card(snap, picking=purpose != "view"),
        month_kb(year, month, purpose, today, red, blue, pickable),
    )


async def show_red(target: Message | CallbackQuery, state: FSMContext) -> None:
    user = await load(target.from_user.id)
    snap = user_snap(user)
    await state.update_data(purpose="period" if user.get("onboarded") else "onboard")
    await show(target, "period", texts.period_card(snap), period_actions_kb(bool(snap.last_start)))


async def show_blue(target: Message | CallbackQuery) -> None:
    user = await viewed_user(target.from_user.id)
    await show(target, "fertile", texts.blue_card(user_snap(user)), back_home_kb())


async def show_sex(target: Message | CallbackQuery, state: FSMContext) -> None:
    user = await load(target.from_user.id)
    if not user.get("onboarded"):
        await show(target, "welcome", texts.onboard_intro(user.get("name") or "", user.get("tz")), start_kb())
        return
    rows = await db.recent_sex(user["tg_id"])
    await state.update_data(purpose="sex")
    await show(target, "sex", texts.sex_card(rows, bool(user.get("share_sex"))), sex_when_kb())


async def show_delay(target: Message | CallbackQuery) -> None:
    user = await load(target.from_user.id)
    snap = user_snap(user)
    already = bool(snap.next_period and await db.delay_marked(user["tg_id"], snap.next_period))
    await show(target, "delay", texts.delay_card(snap, already), delay_kb(snap.delay_days > 0, already))


async def show_tips(target: Message | CallbackQuery) -> None:
    user = await viewed_user(target.from_user.id)
    await show(target, "tips", texts.tips_card(user_snap(user), user.get("intent") or "track"), back_home_kb())


async def show_preg(target: Message | CallbackQuery) -> None:
    user = await load(target.from_user.id)
    snap = user_snap(user)
    rows = await db.recent_sex(user["tg_id"]) if user.get("onboarded") else []
    await show(
        target,
        "preg",
        texts.pregnancy_card(snap, user.get("intent") or "track", rows),
        pregnancy_kb(user.get("intent") or "track"),
    )


async def show_partner(target: Message | CallbackQuery) -> None:
    user = await load(target.from_user.id)
    owners = await db.owners_for_viewer(user["tg_id"])
    if owners and not user.get("onboarded"):
        owner = owners[0]
        owner_name = (owner.get("name") or "партнёр").strip()
        await show(
            target,
            "partner",
            texts.partner_viewer_card(owner_name),
            partner_viewer_kb(),
        )
        return
    partner = await db.partner_of(user["tg_id"])
    await show(
        target,
        "partner",
        texts.partner_card(bool(partner), (partner or {}).get("name") or "", bool(user.get("share_sex")), None),
        partner_kb(bool(partner)),
    )


async def show_diary(target: Message | CallbackQuery) -> None:
    user = await load(target.from_user.id)
    snap = user_snap(user)
    entry = await db.get_diary(user["tg_id"], snap.today)
    await show(target, "tips", texts.diary_card(entry, snap), diary_kb(entry))


async def show_settings(target: Message | CallbackQuery) -> None:
    user = await load(target.from_user.id)
    await show(target, "settings", texts.settings_card(user), settings_kb(user))


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    user = await load(message.from_user.id, message.from_user.first_name or "")
    payload = (command.args or "").strip()
    if payload.startswith("p_"):
        await state.update_data(invite_code=payload[2:])
    if not int(user.get("tos_accepted") or 0):
        await show(message, "welcome", texts.tos_card(user.get("name") or "", user.get("tz")), tos_kb())
        return

    if payload.startswith("p_"):
        code = payload[2:]
        owner_id = await db.invite_owner(code)
        if not owner_id or owner_id == message.from_user.id:
            await show(message, "partner", texts.partner_card(False, "", False, None), partner_kb(False))
            return
        owner = await db.get_user(owner_id)
        await show(
            message,
            "partner",
            texts.partner_invite_card((owner or {}).get("name") or "партнёр"),
            pair_confirm_kb(code),
        )
        return

    await send_home(message, user)


@router.callback_query(F.data == "tos:ok")
async def tos_ok(call: CallbackQuery, state: FSMContext) -> None:
    ok, hint = await is_subscribed(call.bot, call.from_user.id)
    if not ok:
        await call.answer(hint, show_alert=True)
        return
    user = await load(call.from_user.id, call.from_user.first_name or "")
    await db.update_user(user["tg_id"], tos_accepted=1)
    _tos_ok.add(call.from_user.id)
    data = await state.get_data()
    code = (data.get("invite_code") or "").strip()
    if code:
        owner_id = await db.invite_owner(code)
        if owner_id and owner_id != call.from_user.id:
            owner = await db.get_user(owner_id)
            await show(
                call,
                "partner",
                texts.partner_invite_card((owner or {}).get("name") or "партнёр"),
                pair_confirm_kb(code),
            )
            return
    await send_home(call, await load(call.from_user.id))


@router.message(Command("menu"))
@router.message(F.text == BTN_HOME)
async def cmd_home(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_home(message, await load(message.from_user.id, message.from_user.first_name or ""))


@router.message(Command("settings"))
@router.message(F.text == BTN_SETTINGS)
async def cmd_settings(message: Message) -> None:
    await show_settings(message)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    user = await load(message.from_user.id, message.from_user.first_name or "")
    await show(
        message,
        "welcome",
        texts.onboard_intro(user.get("name") or "", user.get("tz")),
        start_kb() if not user.get("onboarded") else main_menu_kb(),
    )


@router.callback_query(F.data == "menu:home")
@router.callback_query(F.data == "nav:home")
async def cb_home(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await send_home(call, await load(call.from_user.id, call.from_user.first_name or ""))


@router.callback_query(F.data == "menu:cal")
async def cb_cal(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await send_calendar(call, await viewed_user(call.from_user.id), "view")


@router.callback_query(F.data == "menu:red")
async def cb_red(call: CallbackQuery, state: FSMContext) -> None:
    await show_red(call, state)


@router.callback_query(F.data == "menu:blue")
async def cb_blue(call: CallbackQuery) -> None:
    await show_blue(call)


@router.callback_query(F.data == "menu:sex")
async def cb_sex(call: CallbackQuery, state: FSMContext) -> None:
    await show_sex(call, state)


@router.callback_query(F.data == "menu:delay")
async def cb_delay(call: CallbackQuery) -> None:
    await show_delay(call)


@router.callback_query(F.data == "menu:tips")
async def cb_tips(call: CallbackQuery) -> None:
    await show_tips(call)


@router.callback_query(F.data == "menu:preg")
async def cb_preg(call: CallbackQuery) -> None:
    await show_preg(call)


@router.callback_query(F.data.startswith("preg:"))
async def set_preg_intent(call: CallbackQuery) -> None:
    code = call.data.split(":", 1)[1]
    if code not in texts.INTENT_LABEL:
        await call.answer()
        return
    user = await load(call.from_user.id)
    await db.update_user(user["tg_id"], intent=code)
    await show_preg(call)


@router.callback_query(F.data == "menu:partner")
async def cb_partner(call: CallbackQuery) -> None:
    await show_partner(call)


@router.callback_query(F.data == "menu:settings")
async def cb_settings(call: CallbackQuery) -> None:
    await show_settings(call)


@router.callback_query(F.data == "menu:diary")
async def cb_diary(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_diary(call)


@router.callback_query(F.data == "menu:history")
async def cb_history(call: CallbackQuery) -> None:
    user = await load(call.from_user.id)
    rows = await db.recent_periods(user["tg_id"])
    await show(call, "calendar", texts.history_card(rows, user_snap(user)), back_home_kb())


@router.message(F.text == BTN_RED)
async def btn_red(message: Message, state: FSMContext) -> None:
    await show_red(message, state)


@router.message(F.text == BTN_BLUE)
async def btn_blue(message: Message) -> None:
    await show_blue(message)


@router.message(F.text == BTN_CAL)
async def btn_cal(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_calendar(message, await viewed_user(message.from_user.id), "view")


@router.message(F.text == BTN_SEX)
async def btn_sex(message: Message, state: FSMContext) -> None:
    await show_sex(message, state)


@router.message(F.text == BTN_DELAY)
async def btn_delay(message: Message) -> None:
    await show_delay(message)


@router.message(F.text == BTN_TIPS)
async def btn_tips(message: Message) -> None:
    await show_tips(message)


@router.message(F.text == BTN_PARTNER)
async def btn_partner(message: Message) -> None:
    await show_partner(message)


@router.callback_query(F.data == "onboard:go")
async def onboard_go(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(purpose="onboard")
    await show(call, "period", texts.period_card(user_snap(await load(call.from_user.id))), period_actions_kb(False))


@router.callback_query(F.data == "period:edit")
async def period_edit(call: CallbackQuery, state: FSMContext) -> None:
    user = await load(call.from_user.id)
    snap = user_snap(user)
    if snap.last_start is None:
        await call.answer("Сначала поставь красные дни.", show_alert=True)
        return
    await state.update_data(purpose="revise", chosen=snap.last_start.isoformat())
    await show(call, "period", texts.period_card(snap), period_edit_kb())


@router.callback_query(F.data == "period:new")
async def period_new(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(purpose="period")
    user = await load(call.from_user.id)
    await show(call, "period", texts.period_card(user_snap(user)), period_new_kb())


@router.callback_query(F.data == "period:len")
async def period_len_only(call: CallbackQuery, state: FSMContext) -> None:
    user = await load(call.from_user.id)
    snap = user_snap(user)
    if snap.last_start is None:
        await call.answer("Сначала поставь красные дни.", show_alert=True)
        return
    await state.set_state(Flow.pick_plen)
    await state.update_data(purpose="revise", chosen=snap.last_start.isoformat())
    await show(call, "period", texts.pick_day_card("period", fmt_day(snap.last_start)), period_len_kb(back="period:edit"))


@router.callback_query(F.data == "cal:noop")
async def cal_noop(call: CallbackQuery) -> None:
    await call.answer()


@router.callback_query(F.data.startswith("cal:open:"))
async def cal_open(call: CallbackQuery, state: FSMContext) -> None:
    purpose = call.data.split(":")[-1]
    await state.update_data(purpose=purpose)
    user = await viewed_user(call.from_user.id) if purpose == "view" else await load(call.from_user.id)
    year = month = None
    if purpose == "revise":
        start = db.parse_date(user.get("last_start"))
        if start:
            year, month = start.year, start.month
    await send_calendar(call, user, purpose, year, month)


@router.callback_query(F.data.startswith("caln:"))
async def cal_nav(call: CallbackQuery, state: FSMContext) -> None:
    _, purpose, ym = call.data.split(":", 2)
    year_s, month_s = ym.split("-")
    await state.update_data(purpose=purpose)
    user = await viewed_user(call.from_user.id) if purpose == "view" else await load(call.from_user.id)
    await send_calendar(call, user, purpose, int(year_s), int(month_s))


@router.callback_query(F.data.startswith("cald:"))
async def cal_pick(call: CallbackQuery, state: FSMContext) -> None:
    _, purpose, iso = call.data.split(":", 2)
    await handle_date(call, state, purpose, date.fromisoformat(iso))


@router.callback_query(F.data.in_({"period:today", "period:yesterday"}))
async def period_shortcut(call: CallbackQuery, state: FSMContext) -> None:
    user = await load(call.from_user.id)
    today = today_in(user.get("tz"))
    chosen = today if call.data.endswith("today") else today - timedelta(days=1)
    purpose = (await state.get_data()).get("purpose")
    if purpose != "onboard":
        purpose = "period"
    await handle_date(call, state, purpose, chosen)


@router.callback_query(F.data.in_({"sex:today", "sex:yesterday"}))
async def sex_shortcut(call: CallbackQuery, state: FSMContext) -> None:
    user = await load(call.from_user.id)
    today = today_in(user.get("tz"))
    chosen = today if call.data.endswith("today") else today - timedelta(days=1)
    await handle_date(call, state, "sex", chosen)


async def handle_date(target: CallbackQuery, state: FSMContext, purpose: str, chosen: date) -> None:
    await state.update_data(chosen=chosen.isoformat(), purpose=purpose)
    if purpose == "sex":
        await state.set_state(Flow.pick_sex_prot)
        await show(target, "sex", texts.pick_day_card("sex", fmt_day(chosen)), sex_prot_kb())
        return
    if purpose == "next":
        user = await load(target.from_user.id)
        start = db.parse_date(user.get("last_start"))
        if start is None:
            await target.answer("Сначала поставь красные дни.", show_alert=True)
            return
        if chosen <= start:
            await target.answer("Дата должна быть позже начала цикла.", show_alert=True)
            return
        length, mode = apply_next_date(start, chosen)
        await db.update_user(user["tg_id"], cycle_length=length, predict_mode=mode, next_override=None)
        await state.clear()
        await send_home(target, await load(target.from_user.id))
        return
    await state.set_state(Flow.pick_plen)
    back = "period:edit" if purpose == "revise" else ("onboard:go" if purpose == "onboard" else "menu:red")
    await show(target, "period", texts.pick_day_card("period", fmt_day(chosen)), period_len_kb(back=back))


@router.callback_query(F.data.startswith("plen:"), Flow.pick_plen)
async def pick_plen(call: CallbackQuery, state: FSMContext) -> None:
    length = int(call.data.split(":")[1])
    data = await state.get_data()
    iso = data.get("chosen")
    if not iso:
        await call.answer("Сначала выбери дату красных.", show_alert=True)
        return
    chosen = date.fromisoformat(iso)
    user = await load(call.from_user.id)
    purpose = data.get("purpose") or "period"
    if purpose == "revise":
        old = db.parse_date(user.get("last_start"))
        await db.revise_period(user["tg_id"], chosen, length, start_changed=old != chosen)
        await state.clear()
        await send_home(call, await load(call.from_user.id))
        return
    await db.set_period(user["tg_id"], chosen, length)
    await state.update_data(chosen=chosen.isoformat(), period_length=length)
    await state.set_state(Flow.pick_next)
    await show(call, "home", texts.cycle_len_card(), next_period_kb(chosen, back="menu:red"))


@router.callback_query(F.data.startswith("clen:"))
async def pick_clen(call: CallbackQuery, state: FSMContext) -> None:
    length = int(call.data.split(":")[1])
    data = await state.get_data()
    user = await load(call.from_user.id, call.from_user.first_name or "")
    current_state = await state.get_state()
    await db.update_user(user["tg_id"], cycle_length=length)

    if current_state == Flow.pick_clen or data.get("purpose") == "onboard":
        iso = data.get("chosen")
        if not iso:
            await call.answer("Сначала выбери дату красных.", show_alert=True)
            return
        chosen = date.fromisoformat(iso)
        plen = int(data.get("period_length") or user.get("period_length") or 5)
        await db.set_period(user["tg_id"], chosen, plen)
        await db.update_user(user["tg_id"], cycle_length=length, name=call.from_user.first_name or "")
        await state.clear()
        await call.answer("Цикл собран")
        await send_home(call, await load(call.from_user.id))
        return

    await state.clear()
    await show_settings(call)


@router.callback_query(F.data.startswith("sprot:"), Flow.pick_sex_prot)
async def pick_sex_prot(call: CallbackQuery, state: FSMContext) -> None:
    protection = call.data.split(":")[1]
    data = await state.get_data()
    iso = data.get("chosen")
    if not iso:
        await call.answer("Сначала выбери день.", show_alert=True)
        return
    chosen = date.fromisoformat(iso)
    user = await load(call.from_user.id)
    await db.add_sex(user["tg_id"], chosen, protection)
    await state.clear()
    fresh = await load(call.from_user.id)
    await show(call, "sex", texts.sex_saved(fmt_day(chosen), protection), sex_when_kb())
    if fresh.get("share_sex"):
        await ping_viewers(call.bot, fresh, "sex", extra=fmt_day(chosen))


@router.callback_query(F.data == "delay:mark")
async def delay_mark(call: CallbackQuery) -> None:
    user = await load(call.from_user.id)
    snap = user_snap(user)
    if snap.delay_days <= 0 or not snap.next_period:
        await call.answer("Пока рано — прогноз ещё не прошёл.", show_alert=True)
        return
    created = await db.mark_delay(user["tg_id"], snap.next_period)
    await show(call, "delay", texts.delay_card(snap, True), delay_kb(False, True))
    if created:
        await ping_viewers(call.bot, user, "delay", extra=str(snap.delay_days))
    else:
        await call.answer("Уже стоит")


@router.callback_query(F.data == "pair:invite")
async def pair_invite(call: CallbackQuery) -> None:
    user = await load(call.from_user.id)
    if not user.get("onboarded"):
        await call.answer("Сначала поставь свой цикл.", show_alert=True)
        return
    code = await db.create_invite(user["tg_id"])
    link = f"https://t.me/{BOT_USERNAME}?start=p_{code}" if BOT_USERNAME else f"/start p_{code}"
    partner = await db.partner_of(user["tg_id"])
    await show(
        call,
        "partner",
        texts.partner_card(bool(partner), (partner or {}).get("name") or "", bool(user.get("share_sex")), link),
        partner_kb(bool(partner)),
    )


@router.callback_query(F.data == "pair:drop")
async def pair_drop(call: CallbackQuery) -> None:
    await db.unbind_partner(call.from_user.id)
    user = await load(call.from_user.id)
    if not user.get("onboarded"):
        await call.answer("Связь отключена")
        await show(call, "welcome", texts.onboard_intro(user.get("name") or "", user.get("tz")), start_kb())
        return
    await show(call, "partner", texts.partner_card(False, "", bool(user.get("share_sex")), None), partner_kb(False))


@router.callback_query(F.data.startswith("pair:yes:"))
async def pair_yes(call: CallbackQuery, state: FSMContext) -> None:
    code = call.data.split(":")[-1]
    owner_id = await db.invite_owner(code)
    if not owner_id or owner_id == call.from_user.id:
        await call.answer("Ссылка уже не работает.", show_alert=True)
        return
    await db.ensure_user(call.from_user.id, call.from_user.first_name or "")
    await db.bind_partner(owner_id, call.from_user.id)
    await state.clear()
    owner = await db.get_user(owner_id)
    me = await load(call.from_user.id)
    await show(
        call,
        "partner",
        texts.home_card(user_snap(owner), name=(owner or {}).get("name") or "", for_partner=True),
        main_menu_kb(viewer=not me.get("onboarded")),
    )
    try:
        await call.bot.send_message(
            owner_id,
            texts.partner_bound(call.from_user.first_name or "человек"),
        )
    except Exception:
        pass


@router.callback_query(F.data == "pair:no")
async def pair_no(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await load(call.from_user.id)
    await show(call, "welcome", texts.onboard_intro(user.get("name") or "", user.get("tz")), start_kb())


@router.callback_query(F.data.startswith("nxtd:"))
async def pick_next_preset(call: CallbackQuery, state: FSMContext) -> None:
    _, raw, mode = call.data.split(":")
    user = await load(call.from_user.id)
    start = db.parse_date(user.get("last_start"))
    if start is None:
        data = await state.get_data()
        if data.get("chosen"):
            start = date.fromisoformat(data["chosen"])
    if start is None:
        await call.answer("Сначала поставь красные дни.", show_alert=True)
        return
    if mode == "m":
        nxt = add_months(start, 1)
        length, pmode = apply_next_date(start, nxt)
        await db.update_user(user["tg_id"], cycle_length=length, predict_mode=MODE_MONTHLY, next_override=None)
    else:
        days = int(raw)
        await db.update_user(user["tg_id"], cycle_length=days, predict_mode=MODE_INTERVAL, next_override=None)
    came_from_period = await state.get_state() == Flow.pick_next
    await state.clear()
    fresh = await load(call.from_user.id)
    if came_from_period:
        await ping_viewers(call.bot, fresh, "period", extra=fmt_day(start))
    await send_home(call, fresh)


@router.callback_query(F.data == "set:cyclepage")
async def set_cyclepage(call: CallbackQuery) -> None:
    user = await load(call.from_user.id)
    await show(call, "settings", texts.settings_cycle_card(user, user_snap(user)), settings_cycle_kb(user))


@router.callback_query(F.data == "set:notifypage")
async def set_notifypage(call: CallbackQuery) -> None:
    user = await load(call.from_user.id)
    await show(call, "settings", texts.settings_notify_card(user), settings_notify_kb(user))


@router.callback_query(F.data == "set:privpage")
async def set_privpage(call: CallbackQuery) -> None:
    user = await load(call.from_user.id)
    await show(call, "settings", texts.settings_privacy_card(user), settings_privacy_kb(user))


@router.callback_query(F.data == "set:tzpage")
async def set_tzpage(call: CallbackQuery) -> None:
    user = await load(call.from_user.id)
    await show(call, "settings", texts.settings_tz_card(user), settings_tz_kb())


@router.callback_query(F.data == "set:nextdate")
async def set_nextdate(call: CallbackQuery, state: FSMContext) -> None:
    user = await load(call.from_user.id)
    start = db.parse_date(user.get("last_start"))
    if start is None:
        await call.answer("Сначала поставь красные дни.", show_alert=True)
        return
    await state.update_data(purpose="next", chosen=start.isoformat())
    await show(call, "home", texts.cycle_len_card(), next_period_kb(start, back="set:cyclepage"))


@router.callback_query(F.data.startswith("adj:"))
async def adj_value(call: CallbackQuery) -> None:
    _, key, raw = call.data.split(":")
    delta = int(raw)
    bounds = {
        "cl": ("cycle_length", 20, 60),
        "pl": ("period_length", 2, 12),
        "lu": ("luteal_days", 10, 16),
        "fb": ("fertile_before", 1, 8),
        "fa": ("fertile_after", 0, 5),
        "nh": ("notify_hour", 6, 22),
    }
    if key not in bounds:
        await call.answer()
        return
    field, lo, hi = bounds[key]
    user = await load(call.from_user.id)
    default_val = 6 if key == "fb" else 3 if key == "fa" else lo
    cur = int(user.get(field) if user.get(field) is not None else default_val)
    nxt = min(hi, max(lo, cur + delta))
    await db.update_user(user["tg_id"], **{field: nxt})
    fresh = await load(call.from_user.id)
    if key == "nh":
        await show(call, "settings", texts.settings_notify_card(fresh), settings_notify_kb(fresh))
    else:
        await show(call, "settings", texts.settings_cycle_card(fresh, user_snap(fresh)), settings_cycle_kb(fresh))


@router.callback_query(F.data.startswith("tgl:"))
async def tgl_value(call: CallbackQuery) -> None:
    field = call.data.split(":", 1)[1]
    user = await load(call.from_user.id)
    if field == "predict_mode":
        mode = MODE_MONTHLY if user.get("predict_mode") != MODE_MONTHLY else MODE_INTERVAL
        await db.update_user(user["tg_id"], predict_mode=mode)
        fresh = await load(call.from_user.id)
        await show(call, "settings", texts.settings_cycle_card(fresh, user_snap(fresh)), settings_cycle_kb(fresh))
        return
    cur = int(user.get(field) or 0)
    await db.update_user(user["tg_id"], **{field: 0 if cur else 1})
    fresh = await load(call.from_user.id)
    if field.startswith("share_"):
        await show(call, "settings", texts.settings_privacy_card(fresh), settings_privacy_kb(fresh))
    else:
        await show(call, "settings", texts.settings_notify_card(fresh), settings_notify_kb(fresh))


@router.callback_query(F.data.startswith("tz:"))
async def set_tz(call: CallbackQuery) -> None:
    tz = call.data.split(":", 1)[1]
    user = await load(call.from_user.id)
    await db.update_user(user["tg_id"], tz=tz)
    fresh = await load(call.from_user.id)
    await show(call, "settings", texts.settings_tz_card(fresh), settings_tz_kb())


@router.callback_query(F.data.startswith("mood:"))
async def set_mood(call: CallbackQuery) -> None:
    user = await load(call.from_user.id)
    day = user_snap(user).today
    await db.upsert_diary(user["tg_id"], day, mood=call.data.split(":", 1)[1])
    await show_diary(call)


@router.callback_query(F.data.startswith("flow:"))
async def set_flow(call: CallbackQuery) -> None:
    user = await load(call.from_user.id)
    day = user_snap(user).today
    await db.upsert_diary(user["tg_id"], day, flow=call.data.split(":", 1)[1])
    await show_diary(call)


@router.callback_query(F.data.startswith("pain:"))
async def set_pain(call: CallbackQuery) -> None:
    user = await load(call.from_user.id)
    day = user_snap(user).today
    await db.upsert_diary(user["tg_id"], day, pain=int(call.data.split(":")[1]))
    await show_diary(call)


@router.callback_query(F.data.startswith("sym:"))
async def set_sym(call: CallbackQuery) -> None:
    user = await load(call.from_user.id)
    day = user_snap(user).today
    await db.toggle_symptom(user["tg_id"], day, call.data.split(":", 1)[1])
    await show_diary(call)


@router.callback_query(F.data == "diary:note")
async def diary_note(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Flow.diary_note)
    await call.answer("Напиши заметку следующим сообщением")


@router.message(Flow.diary_note, F.text)
async def save_diary_note(message: Message, state: FSMContext) -> None:
    user = await load(message.from_user.id)
    day = user_snap(user).today
    await db.upsert_diary(user["tg_id"], day, note=(message.text or "")[:500])
    await state.clear()
    await show_diary(message)


@router.callback_query(F.data == "set:cycle")
async def set_cycle(call: CallbackQuery, state: FSMContext) -> None:
    await set_cyclepage(call)


@router.callback_query(F.data == "set:period")
async def set_period_len(call: CallbackQuery, state: FSMContext) -> None:
    user = await load(call.from_user.id)
    snap = user_snap(user)
    if snap.last_start is None:
        await call.answer("Сначала поставь красные дни.", show_alert=True)
        return
    await state.set_state(Flow.pick_plen)
    await state.update_data(purpose="period", chosen=snap.last_start.isoformat())
    await show(call, "settings", texts.pick_day_card("period", fmt_day(snap.last_start)), period_len_kb(back="menu:settings"))


@router.callback_query(F.data == "set:notify")
async def set_notify(call: CallbackQuery) -> None:
    user = await load(call.from_user.id)
    await db.update_user(user["tg_id"], notify=0 if user.get("notify") else 1)
    await show_settings(call)


@router.callback_query(F.data == "set:sexshare")
async def set_sexshare(call: CallbackQuery) -> None:
    user = await load(call.from_user.id)
    await db.update_user(user["tg_id"], share_sex=0 if user.get("share_sex") else 1)
    await show_settings(call)


@router.callback_query(F.data.startswith("plen:"))
async def plen_stale(call: CallbackQuery) -> None:
    await call.answer("Сначала выбери дату красных.", show_alert=True)


@router.callback_query(F.data.startswith("sprot:"))
async def sprot_stale(call: CallbackQuery) -> None:
    await call.answer("Сначала выбери день.", show_alert=True)


@router.callback_query()
async def unknown_cb(call: CallbackQuery) -> None:
    await call.answer()
