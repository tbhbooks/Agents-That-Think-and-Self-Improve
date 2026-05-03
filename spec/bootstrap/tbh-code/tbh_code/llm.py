"""Chapter 0 LLM wrapper for tbh-code.

Supports two modes selected via .env:
- TBH_LLM_BACKEND=api (default): use aisuite provider APIs
- TBH_LLM_BACKEND=cli: use local CLI adapters (claude/cursor/codex)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import aisuite as ai
from dotenv import load_dotenv

load_dotenv()

MODEL = os.environ.get("TBH_MODEL", "anthropic:claude-sonnet-4-20250514")
BACKEND = os.environ.get("TBH_LLM_BACKEND", "api").strip().lower()
CLI_BACKEND = os.environ.get("TBH_CLI_BACKEND", "claude").strip().lower()
ADAPTERS_PATH = os.environ.get("TBH_ADAPTERS_PATH", "tbh-agent-adapters/python")

_client = ai.Client()


def _messages_to_prompt(messages) -> str:
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines).strip()


def _chat_cli(messages) -> str:
    adapters_dir = Path(ADAPTERS_PATH).resolve()
    if str(adapters_dir) not in sys.path:
        sys.path.append(str(adapters_dir))

    try:
        from cli_backends import claude_exec, codex_exec, cursor_exec
    except Exception as exc:  # pragma: no cover - bootstrap helper
        raise RuntimeError(
            f"Unable to import CLI adapters from {adapters_dir}."
        ) from exc

    prompt = _messages_to_prompt(messages)
    if CLI_BACKEND == "claude":
        return claude_exec(prompt)
    if CLI_BACKEND == "cursor":
        return cursor_exec(prompt)
    if CLI_BACKEND == "codex":
        return codex_exec(prompt)
    raise ValueError(
        f"Unsupported TBH_CLI_BACKEND={CLI_BACKEND!r}. "
        "Use one of: claude, cursor, codex."
    )


def chat(messages, **kwargs):
    """Send messages and return assistant text."""
    if BACKEND == "cli":
        return _chat_cli(messages)
    response = _client.chat.completions.create(
        model=MODEL,
        messages=messages,
        **kwargs,
    )
    return response.choices[0].message.content


def chat_raw(messages, **kwargs):
    """Send messages and return raw response object (API backend only)."""
    if BACKEND == "cli":
        raise RuntimeError(
            "chat_raw is only supported for TBH_LLM_BACKEND=api."
        )
    return _client.chat.completions.create(
        model=MODEL,
        messages=messages,
        **kwargs,
    )
