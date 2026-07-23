"""
tg_bot/handlers.py - message handlers for aiogram3.

Flow:
  1. Lookup tg_user_id in platform.users → get tenant_id + org_id.
     Uses a direct asyncpg connection (no RLS - lookup happens BEFORE
     we know the tenant, so we must query the full users table).
  2. If not found → reply "not registered".
  3. If user has a pending HITL question (input_required from previous turn):
       → send DataPart resume to the same task_id/context_id
  4. Otherwise send text to A2A agent for (tenant_id, org_id) → reply.
  5. If reply.input_required → store state, show question + optional keyboard.

NOTE: In Phase 0 this bot belongs to ONE org (TENANT_ID / ORG_ID in env).
      The DB lookup verifies the user is registered for THIS org only.

HITL state is stored in-memory (_pending_hitl). Pod restart clears it - the
user will need to re-send their answer once. This is acceptable for Phase 0:
HITL pauses are short-lived (seconds to minutes).

Phase 2 persistence plan (when replicas > 1 or restart tolerance is required):
  - Store {tg_user_id: {task_id, context_id, question, options}} in platform.hitl_pending
    (PostgreSQL table, TTL via created_at + cleanup job).
  - OR use Redis SETEX with 1h TTL (simpler, no schema migration).
  - Key insight: only task_id + context_id are needed for resume - not the full A2AResult.
"""

import asyncio
import logging
from typing import Optional

import asyncpg
from aiogram import Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from tg_bot import a2a_client
from tg_bot.a2a_client import A2AResult

logger = logging.getLogger(__name__)

_tenant_id: str = ""
_org_id: str = ""
_kagent_url: str = ""
_database_url: str = ""

_pending_hitl: dict[int, A2AResult] = {}


def register(
    dp: Dispatcher,
    *,
    tenant_id: str,
    org_id: str,
    kagent_url: str,
    database_url: str,
) -> None:
    global _tenant_id, _org_id, _kagent_url, _database_url
    _tenant_id = tenant_id
    _org_id = org_id
    _kagent_url = kagent_url
    _database_url = database_url

    dp.message.register(_cmd_start, CommandStart())
    dp.message.register(_on_message)
    dp.callback_query.register(_on_hitl_callback, lambda c: c.data and c.data.startswith("hitl:"))



async def _lookup_user(tg_user_id: int) -> Optional[dict]:
    """Return {tenant_id, org_id} for a Telegram user, or None.

    Uses app_user + SET LOCAL app.tenant_id so RLS filters correctly
    to this tenant only. app_user cannot see other tenants' rows.
    """
    conn = await asyncpg.connect(_database_url)
    try:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.tenant_id', $1, true)", _tenant_id)
            row = await conn.fetchrow(
                """
                SELECT tenant_id, org_id
                FROM platform.users
                WHERE tg_id = $1
                  AND org_id = $2
                LIMIT 1
                """,
                tg_user_id,
                _org_id,
            )
        if row is None:
            return None
        return {"tenant_id": row["tenant_id"], "org_id": row["org_id"]}
    finally:
        await conn.close()



def _make_hitl_keyboard(options: list[str]) -> InlineKeyboardMarkup:
    """Build InlineKeyboardMarkup from list of option strings."""
    builder = InlineKeyboardBuilder()
    for opt in options:
        builder.add(InlineKeyboardButton(text=opt, callback_data=f"hitl:{opt}"))
    builder.adjust(1)
    return builder.as_markup()


async def _handle_hitl_result(
    result: A2AResult,
    tg_user_id: int,
    answer_fn,
) -> None:
    """Process an A2AResult: if input_required → store state + ask.
    Otherwise → send text reply.

    answer_fn is either message.answer or callback_query.message.answer.
    """
    if result.input_required:
        _pending_hitl[tg_user_id] = result
        question_text = f"❓ {result.question}" if result.question else "❓ Агент ожидает ответа."
        if result.options:
            markup = _make_hitl_keyboard(result.options)
            await answer_fn(question_text, reply_markup=markup)
        else:
            await answer_fn(question_text)
    else:
        _pending_hitl.pop(tg_user_id, None)
        await answer_fn(result.text)



async def _cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Привет! Я ваш ассистент.\n"
        "Напишите мне сообщение, и я передам его агенту."
    )


async def _keep_typing(chat, stop_event: asyncio.Event) -> None:
    """Send 'typing' action every 4s until stop_event is set.

    Telegram typing indicator expires after ~5s, so we refresh every 4s
    to keep it visible during long LLM calls (up to 120s).
    """
    try:
        while not stop_event.is_set():
            await chat.do("typing")
            await asyncio.wait_for(asyncio.shield(asyncio.sleep(4)), timeout=4)
    except Exception:
        pass


async def _on_hitl_callback(callback: CallbackQuery) -> None:
    """Handle option button press during a HITL question."""
    if not callback.data or not callback.message or not callback.from_user:
        return

    tg_user_id = callback.from_user.id
    chosen_text = callback.data.removeprefix("hitl:")

    pending = _pending_hitl.get(tg_user_id)
    if pending is None:
        await callback.answer("Вопрос уже не актуален.", show_alert=True)
        return

    await callback.answer()

    user = await _lookup_user(tg_user_id)
    if user is None:
        await callback.message.answer("❌ Пользователь не найден.")
        return

    stop_typing = asyncio.Event()
    asyncio.create_task(_keep_typing(callback.message.chat, stop_typing))
    try:
        result = await a2a_client.send(
            _kagent_url,
            user["tenant_id"],
            user["org_id"],
            chosen_text,
            context_id=pending.context_id,
            task_id=pending.task_id,
            is_hitl_resume=True,
        )
    except Exception as exc:
        logger.error("A2A HITL resume (callback) failed: %s", exc)
        await callback.message.answer("⚠️ Агент временно недоступен. Попробуйте позже.")
        return
    finally:
        stop_typing.set()

    await _handle_hitl_result(result, tg_user_id, callback.message.answer)


async def _on_message(message: Message) -> None:
    if message.text is None:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    tg_user_id = message.from_user.id if message.from_user else None
    if tg_user_id is None:
        await message.answer("Не удалось определить пользователя.")
        return

    try:
        user = await _lookup_user(tg_user_id)
    except Exception as exc:
        logger.error("DB lookup failed for tg_id=%s: %s", tg_user_id, exc)
        await message.answer("⚠️ Ошибка при проверке пользователя. Попробуйте позже.")
        return

    if user is None:
        await message.answer(
            "❌ Вы не зарегистрированы в системе.\n"
            "Обратитесь к администратору для получения доступа."
        )
        return

    context_id = f"tg-{tg_user_id}"

    stop_typing = asyncio.Event()
    asyncio.create_task(_keep_typing(message.chat, stop_typing))

    pending = _pending_hitl.get(tg_user_id)
    if pending is not None:
        try:
            result = await a2a_client.send(
                _kagent_url,
                user["tenant_id"],
                user["org_id"],
                message.text,
                context_id=pending.context_id,
                task_id=pending.task_id,
                is_hitl_resume=True,
            )
        except Exception as exc:
            logger.error("A2A HITL resume failed: %s", exc)
            await message.answer("⚠️ Агент временно недоступен. Попробуйте позже.")
            return
        finally:
            stop_typing.set()
        await _handle_hitl_result(result, tg_user_id, message.answer)
        return

    try:
        result = await a2a_client.send(
            _kagent_url,
            user["tenant_id"],
            user["org_id"],
            message.text,
            context_id=context_id,
        )
    except Exception as exc:
        logger.error("A2A call failed: %s", exc)
        await message.answer("⚠️ Агент временно недоступен. Попробуйте позже.")
        return
    finally:
        stop_typing.set()

    await _handle_hitl_result(result, tg_user_id, message.answer)

