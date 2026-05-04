# Chapter 0 — Prompt Template

## Goal

Set up the development environment for `tbh-code`. By the end of this chapter, the reader has:

1. An LLM API key configured in a local `.env` file
2. `uv` installed and a Python 3.10+ project created with it (pip is an accepted alternative)
3. The `todo-api` example codebase copied into their project
4. A project skeleton with `tbh-code` installed as a local CLI (`uv run tbh-code`)
5. A passing smoke test that proves the LLM connection works

Constraint: `tbh-code` must be created in the root of the book repo alongside `AGENTS.md`, not as a sibling folder.
Policy: API keys are required for `tbh-code` runtime and must be loaded from `.env` (not hardcoded).
Recommended toolchain: `uv` for dependency management and running `tbh-code` across all chapters.

---

## What to Build

### 1. Project Skeleton

```
tbh-code/
├── tbh_code/
│   ├── __init__.py       # empty
│   ├── main.py           # CLI entry point (empty — Ch 1)
│   └── llm.py            # LLM client wrapper (empty — Ch 1)
├── pyproject.toml        # or requirements.txt
├── todo-api/             # copied from spec/todo-api/
└── smoke_test.py         # LLM connectivity test
```

Optional fast path: allow copying starter files from `spec/bootstrap/tbh-code/`.

### 2. LLM Client Smoke Test

A minimal script that:
- Imports the LLM SDK (Anthropic or OpenAI)
- Loads `.env` and reads the API key from environment variables (NOT hardcoded)
- Sends a single prompt: `"Say 'tbh-code ready' and nothing else."`
- Prints the response text to stdout
- Exits with code 0 on success, non-zero on failure

### 3. Local Environment File

```bash
.env
  # One of:
  ANTHROPIC_API_KEY=sk-ant-...
  OPENAI_API_KEY=sk-...
```

Also include `.env.example` (no secrets) and ensure `.env` is in `.gitignore`.

The smoke test must NOT contain the API key. It reads from environment variables loaded from `.env`.

Important: this `.env` is for the reader's `tbh-code` program runtime, not for the companion coding agent chat itself.

### 4. Optional CLI Adapter Repo (Outside Interface Spec)

If the reader wants local agent runtime experiments, create a separate optional repo/folder in `tbh-code/` next to `todo-api/`, for example:

`tbh-agent-adapters/python/cli_backends.py`

Adapters can shell out to:

- `claude -p ...`
- `agent -p ...` (Cursor CLI)
- `codex exec --json ...`

This path is optional and experimental for Chapter 0. Do not make it required for validation.

---

## Acceptance Criteria

- [ ] `uv --version` returns a version (or `python3 --version` returns 3.10+ if using pip)
- [ ] `uv sync` completes without errors (installs deps + registers `tbh-code` entry point)
- [ ] `uv run tbh-code --mode oneshot --task "hello"` prints `tbh-code ready`
- [ ] `todo-api/` directory exists with ~10 `.pseudo` files
- [ ] `uv run python smoke_test.py` outputs `tbh-code ready` (or close)
- [ ] `.env` exists locally and is ignored by git
- [ ] No API keys in source files
