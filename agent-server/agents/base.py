from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

from config import GROQ_MODEL
from models import SpecialistOpinion

logger = logging.getLogger(__name__)

try:
    from groq import Groq
    _groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception:
    _groq = None


def log_risk_discrepancy(agent_name: str, patient_id: str, medication: str):
    """Returns a consistency_check callable that logs when LLM and
    deterministic risk levels disagree."""
    async def _check(llm_result: SpecialistOpinion, det_result: SpecialistOpinion) -> None:
        if llm_result.risk_level != det_result.risk_level:
            logger.warning(
                "Consistency: %s risk mismatch for %s/%s — LLM=%s, deterministic=%s",
                agent_name, patient_id, medication,
                llm_result.risk_level, det_result.risk_level,
            )
        if llm_result.flagged != det_result.flagged:
            logger.warning(
                "Consistency: %s flagged mismatch for %s/%s — LLM=%s, deterministic=%s",
                agent_name, patient_id, medication,
                llm_result.flagged, det_result.flagged,
            )
    return _check


def parse_opinion(text: str) -> dict:
    if not text:
        return {}
    cleaned = text.strip()
    json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {}


from agents.mcp_client import call_tool as _execute_tool


async def _run_consistency(
    check: Callable[[SpecialistOpinion, SpecialistOpinion], Awaitable[None]],
    fallback_fn: Callable[[], Awaitable[SpecialistOpinion]],
    llm_result: SpecialistOpinion,
) -> None:
    try:
        det_result = await fallback_fn()
        await check(llm_result, det_result)
    except Exception:
        pass


async def run_specialist_agent(
    agent_name: str,
    system_prompt: str,
    allowed_tools: list[str] | None = None,
    user_message: str = "",
    build_opinion: Callable[[dict, list[str], list[str], str], SpecialistOpinion] | None = None,
    fallback: Callable[[], Awaitable[SpecialistOpinion]] | None = None,
    post_process: Callable[[dict], dict] | None = None,
    consistency_check: Callable[[SpecialistOpinion, SpecialistOpinion], Awaitable[None]] | None = None,
) -> SpecialistOpinion:
    start = time.perf_counter()

    if _groq is None or not os.environ.get("GROQ_API_KEY"):
        return await fallback()

    from agents.mcp_client import MCPClient
    tool_schemas = MCPClient.get_instance().get_tool_schemas()

    if allowed_tools is not None:
        allowed_set = set(allowed_tools)
        tool_schemas = [s for s in tool_schemas if s["function"]["name"] in allowed_set]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    tool_calls_made: list[str] = []
    tool_results_raw: list[str] = []
    for iteration in range(1, 6):
        try:
            response = await asyncio.to_thread(
                _groq.chat.completions.create,
                model=GROQ_MODEL,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
                temperature=0.3,
            )
            choice = response.choices[0]
            msg = choice.message

            if choice.finish_reason == "stop" and msg.content:
                parsed = parse_opinion(msg.content)
                if post_process:
                    parsed = post_process(parsed)
                result = build_opinion(parsed, tool_calls_made, tool_results_raw, msg.content)
                if consistency_check:
                    asyncio.create_task(_run_consistency(consistency_check, fallback, result))
                return result

            if choice.finish_reason == "tool_calls" and msg.tool_calls:
                for tc in msg.tool_calls:
                    func = tc.function
                    name = func.name
                    try:
                        args = json.loads(func.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    result = await _execute_tool(name, args)
                    tool_calls_made.append(name)
                    tool_results_raw.append(result)

                    messages.append({
                        "role": "assistant",
                        "content": msg.content,
                        "tool_calls": [{
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": name, "arguments": func.arguments},
                        }],
                    })
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                continue

            if msg.content:
                messages.append({"role": "assistant", "content": msg.content})
                continue

        except Exception as exc:
            logger.warning("%s agent iteration %d failed: %s", agent_name, iteration, exc)
            return await fallback()

    return await fallback()
