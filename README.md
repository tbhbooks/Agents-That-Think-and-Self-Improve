# The Builder's Handbook: Agents That Think and Self-Improve (A Coding Agent)

---

## Learn How Agents Work — By Building One.

You use AI coding agents every day — Cursor, Claude Code, Copilot, Aider. You type a prompt. It reads your files, edits your code, runs your tests, catches its own mistakes.

Do you know how any of that actually works?

This book shows you — by making you build one from scratch. A **CLI coding agent** called `tbh-code`, from first LLM call to multi-agent swarm. You'll understand every layer because you built every layer.

---

## Two Ways to Read

**Read only.** Skip Chapter 0, start at [Chapter 1](chapters/ch01.md). Every concept is explained with diagrams, traces, and full output — no setup required to follow along.

**Build as you read.** Start at [Chapter 0](chapters/ch00.md) to set up your environment (~10 minutes). Install [uv](https://docs.astral.sh/uv/) once, then use `uv run tbh-code ...` the same way every chapter — no venv activation, no path management. Each chapter has a spec and validation tests. You build, you run, you see it work. Python by default (least boilerplate) — specs are language-agnostic, so bring Rust, Go, or TypeScript if you prefer.

---

## Quick Start

If you are using Cursor, Claude Code, Codex, OpenClaw, or another coding agent:

1. Open this repo in your coding agent.
2. [`tbhbooks-agent-kit`](https://github.com/tbhbooks/tbhbooks-agent-kit) is the fastest way to turn your agent into a chapter-by-chapter learning and coding coach. Paste this prompt:

   > Read AGENTS.md first, then install tbhbooks-agent-kit.

3. After the installation, paste this prompt:

   > Start with Chapter 0 setup for this TBH book, create tbh-code as a sibling folder to this repo (not inside it), then continue to Chapter 1 in guided build mode.

Note - 
> **API keys are required for `tbh-code`.**
> Even when you use a companion coding agent, your `tbh-code` project must still configure provider keys (for example in `.env`) to run LLM calls.

The kit is optional but useful. It gives agents shared TBH workflows for setup, chapter building, hints, validation, reviews, progress state, and live references.

---

## Table of Contents

### Getting Started

| Ch | Title | What You Build |
|----|-------|----------------|
| 0 | [Setup (Optional)](chapters/ch00.md) | API keys, Python setup, project skeleton, smoke test |

### Foundation

| Ch | Title | What You Build |
|----|-------|----------------|
| 1 | [The One-Shot Trap and the Loop That Fixes It](chapters/ch01.md) | Prompt wrapper → watch it fail → discover the agent loop |
| 2 | [Your First Real Agent](chapters/ch02.md) | Working agent that answers questions about a codebase |

### Tools & Skills

| Ch | Title | What You Build |
|----|-------|----------------|
| 3 | [Tool Use + MCP](chapters/ch03.md) | Tool calling interface with MCP server/client |
| 4 | [Skills: Teaching Your Agent What To Do](chapters/ch04.md) | Playbooks/recipes that compose tools into behaviors |
| 5 | [File System + Shell](chapters/ch05.md) | Agent reads/writes files, runs commands |

### Intelligence

| Ch | Title | What You Build |
|----|-------|----------------|
| 6 | [Memory & Context](chapters/ch06.md) | Session memory, context management, outcome tracking |
| 7 | [Planning & Reasoning](chapters/ch07.md) | Task decomposition, strategy refinement |
| 8 | [Evaluation & Guardrails](chapters/ch08.md) | Self-check, lint, human gate, diagnostic feedback |
| 9 | [Self-Improvement: Agents That Get Better](chapters/ch09.md) | Mistake journal, skill rewriting, evaluator-optimizer |

### The Agent Swarm

| Ch | Title | What You Build |
|----|-------|----------------|
| 10 | [Splitting Into Agents](chapters/ch10.md) | Monolith → peer agents (coder, reviewer, runner, researcher) |
| 11 | [Broadcast & Discovery](chapters/ch11.md) | Agents announce capabilities + skills, discover peers |
| 12 | [Peer Communication](chapters/ch12.md) | Direct agent-to-agent messaging, artifact handoffs |
| 13 | [Swarm Patterns](chapters/ch13.md) | Orchestrator-workers → peer coordination, consensus, collective learning |

### Production

| Ch | Title | What You Build |
|----|-------|----------------|
| 14 | [Production Architecture](chapters/ch14.md) | Checkpoints, tracing, versioned deploys |
| 15 | [The Agent Ecosystem](chapters/ch15.md) | External MCP tools, A2A partner agents, governance |

---

## How to Use This Book

1. **Read the chapter** — understand the concept and why it matters.
2. **Read the spec** — each chapter has a spec in `spec/chNN/` with interface contracts and expected behavior.
3. **Build it** — implement the spec in your language. No code to copy. The spec is all you need.
   > **Using Claude Code?** Install [The Builder's Handbook (TBH) plugin](https://github.com/tbhbooks/tbh-skill) for a guided build-along experience — specs, hints, validation, and progress tracking right inside your terminal:
   > ```
   > /plugin marketplace add tbhbooks/tbh-skill
   > /plugin install tbh@the-builders-handbook
   > /tbh:setup
   > ```
   >
   > **Using Cursor, Codex, OpenClaw, or another coding agent?** Follow the [Agent Quick Start](#agent-quick-start). Runtime shim files (`CURSOR.md`, `CODEX.md`, `CLAUDE.md`) point to [`AGENTS.md`](AGENTS.md); other agents should fall back to it directly.
4. **Validate** — run the validation tests in `spec/chNN/validation/` to confirm your implementation works.
5. **Move on** — each chapter builds on the last. Your agent grows incrementally.

---

## Specs Define "Done"

Each chapter's spec lives in `spec/chNN/`:

```
spec/chNN/
├── prompt-template.md      What to implement (language-agnostic)
├── interface-spec.md       API contracts and types
├── expected-output.txt     What the program should do
└── validation/
    └── test_chNN.py        Automated tests your code must pass
```

---

<details>
<summary>Build Progression — what <code>tbh-code</code> looks like at each stage</summary>

```
Ch 1:  prompt → LLM → text → FAIL → add loop                      one-shot → agent loop
Ch 2:  prompt → LLM + codebase context → answer                    augmented LLM
Ch 3:  prompt → LLM → [MCP tools] → verify                         tool use + protocol
Ch 4:  + skill specs that compose tools into behaviors              skills
Ch 5:  prompt → LLM → [read/write/exec] → verify                   real actions
Ch 6:  + session memory, outcome tracking                           memory + learning
Ch 7:  + task planning, strategy refinement                         planning + adapting
Ch 8:  + self-check, diagnostic feedback                            evaluation + diagnosis
Ch 9:  + mistake journal, skill rewriting                           self-improvement
Ch 10: monolith → [coder, reviewer, runner, researcher]             split into agents
Ch 11: agents broadcast capabilities + skills                       discovery + sharing
Ch 12: agents message each other directly                           peer communication
Ch 13: swarm self-organizes: fan-out, review, consensus             swarm patterns
Ch 14: + checkpoints, tracing, versioned deploys                    production
Ch 15: + external MCP tools, A2A partner agents                     ecosystem
```

</details>

---

*"tbh, the spec is all you need."*
