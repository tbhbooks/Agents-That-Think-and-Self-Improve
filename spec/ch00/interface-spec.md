# Chapter 0 — Interface Spec

## Overview

No agent code in this chapter — just environment setup. The only "interface" is the smoke test: a script that proves the LLM connection works.

---

## Smoke Test

### Interface

```
smoke_test:
    input: none (loads `.env`, then reads API key from environment)
    output: prints LLM response to stdout
    exit_code: 0 on success, non-zero on failure
```

### Behavior

1. Load `.env` from project root
2. Initialize an LLM client using the API key from environment
3. Send a single message: `"Say 'tbh-code ready' and nothing else."`
4. Print the response text to stdout
5. Exit cleanly

### Anthropic Implementation

```python
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()  # reads ANTHROPIC_API_KEY
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=100,
    messages=[{"role": "user", "content": "Say 'tbh-code ready' and nothing else."}]
)
print(message.content[0].text)
```

### OpenAI Implementation

```python
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()  # reads OPENAI_API_KEY
response = client.chat.completions.create(
    model="gpt-4o",
    max_tokens=100,
    messages=[{"role": "user", "content": "Say 'tbh-code ready' and nothing else."}]
)
print(response.choices[0].message.content)
```

---

## Project Structure

`tbh-code` is a sibling folder to the book repo (same parent directory), not a child directory inside the book repo.

```
tbh-code/
├── tbh_code/
│   ├── __init__.py       # empty — package marker
│   ├── main.py           # empty — CLI entry point (Ch 1)
│   └── llm.py            # empty — LLM client wrapper (Ch 1)
├── pyproject.toml        # dependencies: anthropic/openai + python-dotenv
├── todo-api/             # copied from spec/todo-api/
│   ├── src/
│   │   ├── main.pseudo
│   │   ├── routes/tasks.pseudo
│   │   ├── routes/auth.pseudo
│   │   ├── middleware/auth.pseudo
│   │   ├── models/task.pseudo
│   │   ├── models/user.pseudo
│   │   └── db.pseudo
│   ├── tests/
│   │   ├── tasks_test.pseudo
│   │   └── auth_test.pseudo
│   └── README.md
└── smoke_test.py
```

---

## Environment Variables

| Variable | Provider | Required |
|----------|----------|----------|
| `ANTHROPIC_API_KEY` | Anthropic (Claude) | If using Anthropic |
| `OPENAI_API_KEY` | OpenAI | If using OpenAI |

Keys must be stored in environment variables, never in source code.

Load them from `.env` during local development and keep `.env` out of version control.

---

## What This Chapter Does NOT Include

- **No agent code** — that's Ch 1
- **No system prompt** — that's Ch 2
- **No tool calling** — that's Ch 3
- **No project logic** — just scaffolding and a connectivity test
