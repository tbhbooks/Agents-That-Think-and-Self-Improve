# Chapter 1 — The One-Shot Trap and the Loop That Fixes It

## Scope

Build a prompt wrapper that calls an LLM once, observe it fail on a real task, then refactor it into an agent loop.

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

## Key Interfaces

- `send(prompt) → response` (one-shot)
- `loop(task) → observe → think → act → reflect → done?` (agent loop)

## Success Criteria

- One-shot wrapper produces a response (may be wrong — that's the point)
- Agent loop version detects when its output doesn't match reality
- Agent loop version iterates at least once before producing final output

## Concepts Introduced

- The confidence illusion
- One-shot vs loop architecture
- Observe → Think → Act → Reflect
- The Three Levels (Chatbot, Augmented LLM, Agent)
- Workflows vs Agents
- The complexity ladder (start simple, escalate when needed)
