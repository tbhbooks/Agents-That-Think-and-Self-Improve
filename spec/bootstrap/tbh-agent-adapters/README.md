# tbh-agent-adapters Bootstrap (Optional)

Optional CLI wrappers for local agent runtimes.

This bootstrap is separate from the required `tbh-code` Chapter 0 baseline.

## Included backends

- `claude_exec(prompt)` -> `claude -p`
- `cursor_exec(prompt)` -> `agent -p --output-format text`
- `codex_exec(prompt)` -> `codex exec --json` (parses final assistant message)

## Copy into reader project

From `tbh-code/` root:

```bash
mkdir -p tbh-agent-adapters
cp -r ../Agents-That-Think-and-Self-Improve/spec/bootstrap/tbh-agent-adapters/python ./tbh-agent-adapters/
```

## Quick test

```python
from pathlib import Path
import sys

sys.path.append(str(Path("tbh-agent-adapters/python").resolve()))
from cli_backends import cursor_exec  # swap: claude_exec, codex_exec

print(cursor_exec("Say 'adapter ready' and nothing else."))
```

## Notes

- Requires each CLI to be installed and authenticated.
- Keep API-key `.env` flow in `tbh-code` as the required default path.

## Select via `.env`

In `tbh-code/.env`, choose backend without editing code:

```bash
# default provider path (required baseline)
TBH_LLM_BACKEND=api
TBH_MODEL=anthropic:claude-sonnet-4-20250514

# optional CLI path
# TBH_LLM_BACKEND=cli
# TBH_CLI_BACKEND=cursor   # claude | cursor | codex
# TBH_ADAPTERS_PATH=tbh-agent-adapters/python
```
