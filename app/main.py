from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonCommands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from aiohttp import web

from app.config import BOT_TOKEN, DEFAULT_TZ, PORT
from app.db import close, connect
from app.handlers import router
from app.notify import daily_tick

log = logging.getLogger("luna")


async def start_health_server() -> web.AppRunner | None:
    """Запускает легковесный HTTP сервер для Render Health Check."""
    if not PORT:
        return None
    try:
        app = web.Application()
        app.router.add_get("/", lambda r: web.Response(text="Luna Cycle Bot is running!"))
        app.router.add_get("/health", lambda r: web.Response(text="OK"))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        log.info("Health-check HTTP сервер запущен на порту %s", PORT)
        return runner
    except Exception as e:
        log.warning("Не удалось запустить health-check сервер: %s", e)
        return None


async def set_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="settings", description="Параметры и настройки"),
        BotCommand(command="help", description="Инструкция и помощь"),
    ]
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception as e:
        log.warning("Не удалось установить команды бота: %s", e)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not BOT_TOKEN or BOT_TOKEN.startswith("123456"):
        raise SystemExit("Положи токен в cycle-bot/.env — см. .env.example")

    await connect()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone=DEFAULT_TZ)
    scheduler.add_job(daily_tick, CronTrigger(minute=0), args=[bot])
    scheduler.start()

    health_runner = await start_health_server()
    await set_bot_commands(bot)
    log.info("это не Flo слушает")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if health_runner:
            await health_runner.cleanup()
        scheduler.shutdown(wait=False)
        await close()
        await bot.session.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
