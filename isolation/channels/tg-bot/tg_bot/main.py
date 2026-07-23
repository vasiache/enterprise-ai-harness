"""
tg_bot/main.py - entry point.

Reads BOT_TOKEN, TENANT_ID, ORG_ID, KAGENT_URL, DATABASE_URL from env,
starts aiogram3 polling loop.
"""

import asyncio
import logging
import os

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from tg_bot import handlers

logger = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"Required env var {name!r} is not set")
    return value


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    bot_token = _require_env("BOT_TOKEN")
    tenant_id = _require_env("TENANT_ID")
    org_id = _require_env("ORG_ID")
    kagent_url = _require_env("KAGENT_URL")
    database_url = _require_env("DATABASE_URL")

    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None

    logger.info("Starting TG bot: tenant=%s org=%s proxy=%s", tenant_id, org_id, https_proxy or "none")

    if https_proxy:
        connector = aiohttp.TCPConnector()
        session = AiohttpSession(proxy=https_proxy)
    else:
        connector = None
        session = AiohttpSession()

    bot = Bot(
        token=bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    handlers.register(dp, tenant_id=tenant_id, org_id=org_id,
                      kagent_url=kagent_url, database_url=database_url)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Polling started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
