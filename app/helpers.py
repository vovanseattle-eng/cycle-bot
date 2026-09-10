from __future__ import annotations

import json
from pathlib import Path

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaAnimation,
    InputMediaVideo,
    Message,
    ReplyKeyboardRemove,
)

from app.config import ROOT

CACHE_FILE = ROOT / "assets" / "file_ids.json"
BANNERS = ROOT / "assets" / "banners"
CAPTION_LIMIT = 1024
ANIM_EXTS = {".mp4", ".webm", ".gif"}

_ids: dict[str, str] = {}
_kinds: dict[str, str] = {}
_disk_loaded = False

# Имена файлов, которые отличаются от ключа экрана.
BANNER_ALIAS = {
    "welcome": "privetstvie",
}

BANNER_FALLBACK = {
    "period": "home",
    "fertile": "home",
    "calendar": "home",
    "settings": "home",
    "history": "home",
}


def _load_disk() -> None:
    global _disk_loaded
    if _disk_loaded:
        return
    _disk_loaded = True
    if not CACHE_FILE.exists():
        return
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    for key, value in data.items():
        if isinstance(value, str) and value:
            _ids[key] = value
        elif isinstance(value, dict) and value.get("id"):
            _ids[key] = str(value["id"])
            if value.get("kind"):
                _kinds[key] = str(value["kind"])


def get_cached_id(key: str) -> str | None:
    _load_disk()
    if key in _ids:
        return _ids[key]
    alias = BANNER_ALIAS.get(key)
    if alias and alias in _ids:
        return _ids[alias]
    fallback = BANNER_FALLBACK.get(key)
    if fallback and fallback in _ids:
        return _ids[fallback]
    return None


def save_cached_id(key: str, file_id: str, kind: str | None = None) -> None:
    _load_disk()
    _ids[key] = file_id
    if kind:
        _kinds[key] = kind
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(_ids, indent=2), encoding="utf-8")
    except Exception:
        pass


def banner_path(key: str) -> Path | None:
    names: list[str] = []
    if key in BANNER_ALIAS:
        names.append(BANNER_ALIAS[key])
    names.append(key)
    if key in BANNER_FALLBACK:
        names.append(BANNER_FALLBACK[key])
    for name in names:
        for ext in (".mp4", ".webm", ".gif", ".png", ".jpg", ".jpeg", ".webp"):
            path = BANNERS / f"{name}{ext}"
            if path.exists() and path.stat().st_size > 0:
                return path
    return None


def fit_caption(text: str, limit: int = CAPTION_LIMIT) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    nl = cut.rfind("\n")
    if nl >= limit // 2:
        cut = cut[:nl]
    return cut.rstrip() + "…"


def strip_icons(markup: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup | None:
    if markup is None:
        return None
    rows = []
    for row in markup.inline_keyboard:
        fresh = []
        for btn in row:
            data = btn.model_dump(exclude_none=True)
            data.pop("icon_custom_emoji_id", None)
            data.pop("style", None)
            fresh.append(InlineKeyboardButton(**data))
        rows.append(fresh)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _file_id_from(sent: Message | bool | None) -> tuple[str | None, str | None]:
    if not isinstance(sent, Message):
        return None, None
    if sent.animation:
        return sent.animation.file_id, "animation"
    if sent.video:
        return sent.video.file_id, "video"
    return None, None


def _remember(sent: Message | bool | None, cache_key: str) -> None:
    fid, kind = _file_id_from(sent)
    if fid:
        save_cached_id(cache_key, fid, kind)


def _input_media(media, caption: str, parse_mode: str, as_video: bool):
    if as_video:
        return InputMediaVideo(media=media, caption=caption, parse_mode=parse_mode)
    return InputMediaAnimation(media=media, caption=caption, parse_mode=parse_mode)


def _not_modified(err: str) -> bool:
    return "message is not modified" in err


async def _edit_caption(msg: Message, caption: str, markup, parse_mode: str) -> bool:
    attempts = [markup]
    if isinstance(markup, InlineKeyboardMarkup):
        attempts.append(strip_icons(markup))
    for kb in attempts:
        try:
            await msg.edit_caption(caption=caption, reply_markup=kb, parse_mode=parse_mode)
            return True
        except TelegramBadRequest as e:
            err = str(e).lower()
            if _not_modified(err):
                return True
            if "icon" in err or "custom emoji" in err or "emoji_id" in err:
                continue
            return False
        except Exception:
            return False
    return False


async def _edit_text(msg: Message, caption: str, markup, parse_mode: str) -> bool:
    try:
        await msg.edit_text(caption, reply_markup=markup, parse_mode=parse_mode)
        return True
    except TelegramBadRequest as e:
        return _not_modified(str(e).lower())
    except Exception:
        return False


async def _edit_media(msg: Message, media, caption: str, markup, parse_mode: str, as_video: bool) -> Message | bool | None:
    body = _input_media(media, caption, parse_mode, as_video)
    try:
        return await msg.edit_media(media=body, reply_markup=markup)
    except TelegramBadRequest as e:
        err = str(e).lower()
        if _not_modified(err):
            return True
        if "icon" in err or "custom emoji" in err or "emoji_id" in err:
            try:
                return await msg.edit_media(
                    media=body,
                    reply_markup=strip_icons(markup) if isinstance(markup, InlineKeyboardMarkup) else markup,
                )
            except TelegramBadRequest as e2:
                if _not_modified(str(e2).lower()):
                    return True
                return None
        return None
    except Exception:
        return None


async def _drop_reply_keyboard(message: Message) -> None:
    try:
        dummy = await message.answer("\u2063", reply_markup=ReplyKeyboardRemove())
        await dummy.delete()
    except Exception:
        pass


async def show_or_edit_banner(
    event: Message | CallbackQuery,
    banner_path: Path | None,
    cache_key: str,
    caption: str,
    reply_markup=None,
    parse_mode: str = "HTML",
) -> None:
    caption = fit_caption(caption)
    cached_id = get_cached_id(cache_key)
    path = banner_path
    suffix = path.suffix.lower() if path else ""
    has_file = bool(path and suffix in ANIM_EXTS)

    async def send_media(target: Message, markup) -> None:
        media_input = cached_id or (FSInputFile(path) if path and has_file else None)
        if media_input is None:
            await target.answer(caption, reply_markup=markup, parse_mode=parse_mode)
            return
        try:
            sent = await target.answer_animation(
                animation=media_input,
                caption=caption,
                reply_markup=markup,
                parse_mode=parse_mode,
            )
            _remember(sent, cache_key)
            return
        except TelegramBadRequest:
            pass
        if path and has_file:
            try:
                sent = await target.answer_animation(
                    animation=FSInputFile(path),
                    caption=caption,
                    reply_markup=strip_icons(markup) if isinstance(markup, InlineKeyboardMarkup) else markup,
                    parse_mode=parse_mode,
                )
                _remember(sent, cache_key)
                return
            except TelegramBadRequest:
                pass
            try:
                sent = await target.answer_video(
                    video=FSInputFile(path),
                    caption=caption,
                    reply_markup=markup,
                    parse_mode=parse_mode,
                    supports_streaming=True,
                )
                _remember(sent, cache_key)
                return
            except TelegramBadRequest:
                pass
        await target.answer(caption, reply_markup=markup, parse_mode=parse_mode)

    if isinstance(event, CallbackQuery):
        msg = event.message
        if not msg:
            return
        try:
            await event.answer()
        except Exception:
            pass

        cur_fid, cur_kind = _file_id_from(msg)
        want_fid = cached_id
        want_video = _kinds.get(cache_key) == "video"

        # Нет своего баннера — оставляем текущий ролик, меняем только текст и кнопки.
        if cur_fid and not has_file:
            if await _edit_caption(msg, caption, reply_markup, parse_mode):
                return

        # Тот же файл уже в сообщении — edit_media не нужен.
        if cur_fid and want_fid and cur_fid == want_fid:
            if await _edit_caption(msg, caption, reply_markup, parse_mode):
                return

        if cur_fid and want_fid:
            sent = await _edit_media(msg, want_fid, caption, reply_markup, parse_mode, want_video)
            if sent is not None:
                if sent is not True:
                    _remember(sent, cache_key)
                return
            sent = await _edit_media(msg, want_fid, caption, reply_markup, parse_mode, not want_video)
            if sent is not None:
                if sent is not True:
                    _remember(sent, cache_key)
                return
            _ids.pop(cache_key, None)
            want_fid = None

        if cur_fid and has_file and path:
            sent = await _edit_media(msg, FSInputFile(path), caption, reply_markup, parse_mode, False)
            if sent is not None:
                if sent is not True:
                    _remember(sent, cache_key)
                return
            sent = await _edit_media(msg, FSInputFile(path), caption, reply_markup, parse_mode, True)
            if sent is not None:
                if sent is not True:
                    _remember(sent, cache_key)
                return
            if await _edit_caption(msg, caption, reply_markup, parse_mode):
                return

        if msg.text and not cur_fid:
            if await _edit_text(msg, caption, reply_markup, parse_mode):
                return

        try:
            await msg.delete()
        except Exception:
            pass
        await send_media(msg, reply_markup)
        return

    await _drop_reply_keyboard(event)
    await send_media(event, reply_markup)


async def show(event: Message | CallbackQuery, key: str, text: str, reply_markup=None) -> None:
    await show_or_edit_banner(
        event,
        banner_path(key),
        key,
        text,
        reply_markup=reply_markup,
    )
