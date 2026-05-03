"""Optional CLI wrappers for local agent runtimes."""

from __future__ import annotations

import json
import subprocess


class CLIBackendError(RuntimeError):
    """Raised when a CLI backend call fails."""


def _run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise CLIBackendError(f"CLI not found: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise CLIBackendError(
            f"CLI command failed ({' '.join(cmd)}): {stderr}"
        ) from exc
    return result.stdout.strip()


def claude_exec(prompt: str) -> str:
    """Run one non-interactive Claude CLI request."""
    return _run(["claude", "-p", prompt])


def cursor_exec(prompt: str) -> str:
    """Run one non-interactive Cursor CLI agent request."""
    return _run(["agent", "-p", "--output-format", "text", prompt])


def codex_exec(prompt: str) -> str:
    """Run one non-interactive Codex request and parse final assistant text."""
    raw = _run(["codex", "exec", "--json", prompt])
    last_assistant = ""

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    last_assistant = text

    if not last_assistant:
        raise CLIBackendError("No assistant message found in codex --json output.")
    return last_assistant.strip()
