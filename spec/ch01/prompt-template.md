# Chapter 1 — The One-Shot Trap and the Loop That Fixes It

## Scope

Build a prompt wrapper that calls an LLM once, observe it fail on a real task, then refactor it into an agent loop.

## Prerequisite Configuration

Carry forward the Chapter 0 setup:

- keep API keys in `.env` (project root), not in source code
- load environment variables via `python-dotenv` in `tbh_code/llm.py`
- read model selection from `TBH_MODEL` with a sensible default

Clarify to the reader: these `.env` values are used by the `tbh-code` program they are building, not by the companion coding agent itself.

## Learning Objectives

- Understand why a single LLM call produces confident but unreliable output
- Experience the "confidence illusion" — the output looks right but isn't grounded
- Discover the observe-think-act-reflect cycle as the fix
- Distinguish the Three Levels: Chatbot → Augmented LLM → Agent
- Understand workflows vs agents (Anthropic taxonomy)

## What You Build

1. **One-shot wrapper:** Send a user prompt to an LLM, return the response. No loop, no tools, no verification.
2. **Test it:** Ask it to analyze a codebase, refactor a function, or find a bug. Watch it hallucinate file paths, invent APIs, or confidently produce wrong answers.
3. **Add the loop:** Refactor into an observe-think-act-reflect cycle. The agent now checks its own output against reality before responding. 
   **Critically:** Do not hardcode the expected caveats or manually append disclaimers to the final output. Instead, feed the issues detected by the `reflect` phase back into the LLM prompt for the next iteration. Allow the LLM to organically correct its own output based on the iterative feedback.
   **Architecture Note:** In Chapter 1, the loop makes **two LLM calls per iteration**: `think` (ask the LLM to reason about the observation and plan a strategy) and `act` (ask the LLM to produce an answer based on that plan). The `observe` phase is code-only (assembles context from the task, prior answer, and reflect issues), and the `reflect` phase is a code-only heuristic check (hedge detection, specificity pressure, consistency). Later chapters may escalate reflect to an LLM call as well.
   **Visibility:** Print the progress to the console at each phase (`[observe]`, `[think]`, `[act]`, `[reflect]`) so the reader can see the loop iterating and correcting itself in real time.

## Key Interfaces

- `send(prompt) → response` (one-shot)
- `loop(task) → observe → think → act → reflect → done?` (agent loop)

## Success Criteria

- One-shot wrapper produces a response (may be wrong — that's the point)
- Agent loop version detects when its output doesn't match reality
- Agent loop version iterates at least once before producing final output
- Agent loop prints the trace of each phase to the terminal in real time

## Concepts Introduced

- The confidence illusion
- One-shot vs loop architecture
- Observe → Think → Act → Reflect
- The Three Levels (Chatbot, Augmented LLM, Agent)
- Workflows vs Agents
- The complexity ladder (start simple, escalate when needed)

## Validate

After implementing, run the tests from your `tbh-code/` sibling folder:

```bash
uv run pytest ../Agents-That-Think-and-Self-Improve/spec/ch01/validation/test_ch01.py -v
```

All tests should pass before moving to Chapter 2.
