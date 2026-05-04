# tbh-code Bootstrap (Chapter 0 Starter)

This directory is a copy-ready bootstrap for `tbh-code`.

## Use

From your `tbh-code/` project root (created as a sibling to the book repo):

```bash
cp -r ../Agents-That-Think-and-Self-Improve/spec/bootstrap/tbh-code/. .
cp -r ../Agents-That-Think-and-Self-Improve/spec/todo-api ./todo-api
```

Then (with uv — recommended):

```bash
uv sync                        # installs deps + registers tbh-code entry point
cp .env.example .env           # add your API key
uv run python smoke_test.py    # verify LLM connection
uv run tbh-code --mode oneshot --task "hello"
```

**Optional: add `tbh-code` to your `PATH` as a global command:**

```bash
uv tool install --editable .
tbh-code --mode oneshot --task "hello"
```

Or with pip (classic path):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
python smoke_test.py
```

Expected output includes `tbh-code ready`.

## Notes

- API keys are required for `tbh-code` runtime.
- Keep secrets in `.env` (never commit real keys).
- This bootstrap is intentionally minimal and matches Chapter 0.

## Optional backend switch via `.env`

`tbh_code/llm.py` supports:

- `TBH_LLM_BACKEND=api` (default, uses `aisuite`)
- `TBH_LLM_BACKEND=cli` (uses optional CLI adapters)

When using CLI mode:

```bash
TBH_LLM_BACKEND=cli
TBH_CLI_BACKEND=claude   # claude | cursor | codex
TBH_ADAPTERS_PATH=tbh-agent-adapters/python
```
