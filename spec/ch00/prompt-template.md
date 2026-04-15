# Chapter 0 — Prompt Template

## Goal

Set up the development environment for `tbh-code`. By the end of this chapter, the reader has:

1. An LLM API key configured as an environment variable
2. A Python 3.10+ project with virtual environment and SDK installed
3. The `todo-api` example codebase copied into their project
4. A project skeleton ready for Chapter 1
5. A passing smoke test that proves the LLM connection works

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

### 2. LLM Client Smoke Test

A minimal script that:
- Imports the LLM SDK (Anthropic or OpenAI)
- Reads the API key from an environment variable (NOT hardcoded)
- Sends a single prompt: `"Say 'tbh-code ready' and nothing else."`
- Prints the response text to stdout
- Exits with code 0 on success, non-zero on failure

### 3. Environment Variables

```bash
# One of:
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

The smoke test must NOT contain the API key. It reads from the environment.

---

## Acceptance Criteria

- [ ] `python3 --version` returns 3.10+
- [ ] Virtual environment exists and is activated
- [ ] `pip list` shows `anthropic` or `openai` installed
- [ ] `todo-api/` directory exists with ~10 `.pseudo` files
- [ ] `python smoke_test.py` outputs `tbh-code ready` (or close)
- [ ] No API keys in source files
