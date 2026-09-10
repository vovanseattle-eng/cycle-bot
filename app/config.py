from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lstrip("@")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "etoneflo").lstrip("@")
CHANNEL_URL = os.getenv("CHANNEL_URL", f"https://t.me/{CHANNEL_USERNAME}")
TOS_ARTICLE_URL = os.getenv("TOS_ARTICLE_URL", "https://telegra.ph/Soglashenie--luna-09-10")
DEFAULT_TZ = os.getenv("TZ", "Europe/Moscow")
_raw_db = os.getenv("DB_PATH", "luna.db")
DB_PATH = Path(_raw_db) if Path(_raw_db).is_absolute() else ROOT / _raw_db
BANNERS_DIR = ROOT / "assets" / "banners"
PORT = int(os.getenv("PORT", "0")) if os.getenv("PORT") else 0

