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
    """Run one non-interactive Claude CLI request (no tools, plain text output)."""
    return _run(["claude", "--tools", "", "--output-format", "text", "-p", prompt])


def cursor_exec(prompt: str) -> str:
    """Run one non-interactive Cursor CLI agent request (no tools, plain text output)."""
    return _run(["agent", "--tools", "", "--output-format", "text", "-p", prompt])


def codex_exec(prompt: str) -> str:
    """Run one non-interactive Codex request and parse final assistant text.

    -s read-only: sandbox prevents shell execution and file writes.
    Note: file reads are still possible; for a fully blind call prepend a
    system instruction to the prompt (e.g. 'Answer from the prompt only,
    do not read any files.').
    """
    raw = _run(["codex", "exec", "-s", "read-only", "--json", prompt])
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
