# tbh-code Bootstrap (Chapter 0 Starter)

This directory is a copy-ready bootstrap for `tbh-code`.

## Use

From your `tbh-code/` project root (created as a sibling to the book repo):

```bash
cp -r ../Agents-That-Think-and-Self-Improve/spec/bootstrap/tbh-code/. .
cp -r ../Agents-That-Think-and-Self-Improve/spec/todo-api ./todo-api
```

Then:

```bash
python3 -m venv .venv
source .venv/bin/activate
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
