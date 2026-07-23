"""
tg_bot/a2a_client.py - minimal A2A JSON-RPC client for kagent-controller.

Sends a text message to an agent and returns the text response.
Supports HITL: detects input_required state and sends DataPart resume.

Protocol: HTTP POST JSON-RPC 2.0
Endpoint: {KAGENT_URL}/api/a2a/tenant-{tenant_id}/{agent_name}/

HITL wire format (resume DataPart):
  {
    "decision_type": "approve",
    "ask_user_answers": [{"answer": ["<user text>"]}]
  }

Architecture note: all bots route to the same entry agent (management-agent).
Org-level routing is the responsibility of the LLM inside management-agent,
not the channel. AGENT_NAME env controls the target agent name.
"""

import logging
import os
import uuid
from dataclasses import dataclass
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

A2A_TIMEOUT = 120

ENTRY_AGENT = os.environ.get("AGENT_NAME", "management-agent")


@dataclass
class A2AResult:
    """Result of an A2A call."""
    text: str
    task_id: Optional[str] = None
    context_id: Optional[str] = None
    input_required: bool = False
    question: Optional[str] = None
    options: Optional[list[str]] = None


def _extract_text(result: dict) -> str:
    """Extract human-readable text from A2A response result."""
    try:
        parts = result["artifacts"][0]["parts"]
        part = parts[0]
        if "text" in part:
            return str(part["text"])
        data = part.get("data", {})
        if isinstance(data, dict):
            resp = data.get("response", {})
            if "text" in resp:
                return str(resp["text"])
            if "structuredContent" in resp:
                sc = resp["structuredContent"]
                return sc if isinstance(sc, str) else str(sc)
        return str(data)
    except (KeyError, IndexError, TypeError):
        return str(result)


def _extract_hitl_question(result: dict) -> tuple[Optional[str], Optional[list[str]]]:
    """Extract question + options from input_required status message DataPart.

    kagent executor stores the interrupt payload inside an adk_request_confirmation
    DataPart in status.message.parts:
      data.args.originalFunctionCall.args == {"question": "...", "options": [...]}
    """
    try:
        parts = result.get("status", {}).get("message", {}).get("parts", [])
        for part in parts:
            data = part.get("data", {})
            if not isinstance(data, dict):
                continue
            if data.get("name") == "adk_request_confirmation":
                args = data.get("args", {})
                ofc = args.get("originalFunctionCall", {})
                ofc_args = ofc.get("args", {})
                question = ofc_args.get("question")
                options = ofc_args.get("options") or []
                return question, options if options else None
    except Exception:
        pass
    return None, None


def _build_resume_datapart(user_text: str) -> dict:
    """Build the DataPart payload that kagent executor expects for HITL resume.

    Wire format:
      {"decision_type": "approve", "ask_user_answers": [{"answer": ["<text>"]}]}
    """
    return {
        "decision_type": "approve",
        "ask_user_answers": [{"answer": [user_text]}],
    }


async def send(
    kagent_url: str,
    tenant_id: str,
    org_id: str,
    text: str,
    *,
    context_id: Optional[str] = None,
    task_id: Optional[str] = None,
    is_hitl_resume: bool = False,
) -> A2AResult:
    """Send a message to the agent and return A2AResult.

    Args:
        kagent_url:     kagent controller URL
        tenant_id:      tenant short ID
        org_id:         org short ID (unused for routing - all bots go to ENTRY_AGENT)
        text:           user text
        context_id:     A2A context_id for conversation continuity (thread_id)
        task_id:        existing task_id for HITL resume
        is_hitl_resume: if True, wraps text in DataPart resume format
    """
    agent = ENTRY_AGENT
    namespace = f"tenant-{tenant_id}"
    url = f"{kagent_url}/api/a2a/{namespace}/{agent}/"

    new_task_id = task_id or str(uuid.uuid4())
    ctx_id = context_id or new_task_id

    if is_hitl_resume:
        parts = [{"kind": "data", "data": _build_resume_datapart(text)}]
    else:
        parts = [{"kind": "text", "text": text}]

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": parts,
                "messageId": str(uuid.uuid4()),
                "contextId": ctx_id,
                **({"taskId": task_id} if task_id else {}),
            },
            "configuration": {"blocking": True},
        },
    }

    logger.info(
        "A2A → %s  agent=%s  org=%s  ctx=%s  resume=%s",
        url, agent, org_id, ctx_id, is_hitl_resume,
    )

    timeout = aiohttp.ClientTimeout(total=A2A_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                logger.error("A2A HTTP %d: %s", resp.status, body[:300])
                return A2AResult(text=f"⚠️ Агент вернул ошибку HTTP {resp.status}.")
            data = await resp.json()

    if "error" in data:
        err = data["error"]
        logger.error("A2A error: %s", err)
        return A2AResult(text=f"⚠️ Ошибка агента: {err.get('message', err)}")

    result = data.get("result", {})
    state = result.get("status", {}).get("state", "")

    if state == "input-required":
        returned_task_id = result.get("id") or new_task_id
        question, options = _extract_hitl_question(result)
        display = question or "Агент ожидает подтверждения."
        logger.info(
            "HITL input_required: task_id=%s question=%r options=%r",
            returned_task_id, question, options,
        )
        return A2AResult(
            text=display,
            task_id=returned_task_id,
            context_id=ctx_id,
            input_required=True,
            question=question,
            options=options,
        )

    return A2AResult(text=_extract_text(result))
