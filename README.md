# The Builder's Handbook: Agents That Think and Self-Improve

*The Builder's Handbook (TBH), you should build it yourself.*

---

## What You're Building

A **CLI coding agent** — from scratch, in any language you choose.

By the end of this book, your agent will read codebases, edit files, run commands, plan multi-step tasks, learn from its mistakes, and coordinate with peer agents in a local swarm. You'll understand every layer because you built every layer.

**Build target:** `tbh-code` — a terminal coding agent like OpenCode, Codex CLI, Claude Code or Aider.

**Language:** Python by default (least boilerplate). Specs are language-agnostic — bring Rust, Go, TypeScript if you prefer.

---

## Table of Contents

### Getting Started

| Ch | Title | What You Build |
|----|-------|----------------|
| 0 | [The Starting Line](chapters/ch00.md) | API keys, Python setup, project skeleton, smoke test |

> 📁 [spec/ch00/](spec/ch00/) — [prompt-template.md](spec/ch00/prompt-template.md) · [interface-spec.md](spec/ch00/interface-spec.md) · [expected-output.txt](spec/ch00/expected-output.txt) · [test_ch00.py](spec/ch00/validation/test_ch00.py)

### Foundation

| Ch | Title | What You Build |
|----|-------|----------------|
| 1 | [The One-Shot Trap and the Loop That Fixes It](chapters/ch01.md) | Prompt wrapper → watch it fail → discover the agent loop |
| 2 | [Your First Real Agent](chapters/ch02.md) | Working agent that answers questions about a codebase |

> 📁 [spec/ch01/](spec/ch01/) — [prompt-template.md](spec/ch01/prompt-template.md) · [interface-spec.md](spec/ch01/interface-spec.md) · [expected-output.txt](spec/ch01/expected-output.txt) · [test_ch01.py](spec/ch01/validation/test_ch01.py)
>
> 📁 [spec/ch02/](spec/ch02/) — [prompt-template.md](spec/ch02/prompt-template.md) · [interface-spec.md](spec/ch02/interface-spec.md) · [expected-output.txt](spec/ch02/expected-output.txt) · [test_ch02.py](spec/ch02/validation/test_ch02.py)

### Tools & Skills

| Ch | Title | What You Build |
|----|-------|----------------|
| 3 | [Tool Use + MCP](chapters/ch03.md) | Tool calling interface with MCP server/client |
| 4 | [Skills: Teaching Your Agent What To Do](chapters/ch04.md) | Playbooks/recipes that compose tools into behaviors |
| 5 | [File System + Shell](chapters/ch05.md) | Agent reads/writes files, runs commands |

> 📁 [spec/ch03/](spec/ch03/) — [prompt-template.md](spec/ch03/prompt-template.md) · [interface-spec.md](spec/ch03/interface-spec.md) · [expected-output.txt](spec/ch03/expected-output.txt) · [test_ch03.py](spec/ch03/validation/test_ch03.py)
>
> 📁 [spec/ch04/](spec/ch04/) — [prompt-template.md](spec/ch04/prompt-template.md) · [interface-spec.md](spec/ch04/interface-spec.md) · [expected-output.txt](spec/ch04/expected-output.txt) · [test_ch04.py](spec/ch04/validation/test_ch04.py)
>
> 📁 [spec/ch05/](spec/ch05/) — [prompt-template.md](spec/ch05/prompt-template.md) · [interface-spec.md](spec/ch05/interface-spec.md) · [expected-output.txt](spec/ch05/expected-output.txt) · [test_ch05.py](spec/ch05/validation/test_ch05.py)

### Intelligence

| Ch | Title | What You Build |
|----|-------|----------------|
| 6 | [Memory & Context](chapters/ch06.md) | Session memory, context management, outcome tracking |
| 7 | [Planning & Reasoning](chapters/ch07.md) | Task decomposition, strategy refinement |
| 8 | [Evaluation & Guardrails](chapters/ch08.md) | Self-check, lint, human gate, diagnostic feedback |
| 9 | [Self-Improvement: Agents That Get Better](chapters/ch09.md) | Mistake journal, skill rewriting, evaluator-optimizer |

> 📁 [spec/ch06/](spec/ch06/) — [prompt-template.md](spec/ch06/prompt-template.md) · [interface-spec.md](spec/ch06/interface-spec.md) · [expected-output.txt](spec/ch06/expected-output.txt) · [test_ch06.py](spec/ch06/validation/test_ch06.py)
>
> 📁 [spec/ch07/](spec/ch07/) — [prompt-template.md](spec/ch07/prompt-template.md) · [interface-spec.md](spec/ch07/interface-spec.md) · [expected-output.txt](spec/ch07/expected-output.txt) · [test_ch07.py](spec/ch07/validation/test_ch07.py)
>
> 📁 [spec/ch08/](spec/ch08/) — [prompt-template.md](spec/ch08/prompt-template.md) · [interface-spec.md](spec/ch08/interface-spec.md) · [expected-output.txt](spec/ch08/expected-output.txt) · [test_ch08.py](spec/ch08/validation/test_ch08.py)
>
> 📁 [spec/ch09/](spec/ch09/) — [prompt-template.md](spec/ch09/prompt-template.md) · [interface-spec.md](spec/ch09/interface-spec.md) · [expected-output.txt](spec/ch09/expected-output.txt) · [test_ch09.py](spec/ch09/validation/test_ch09.py)

### The Agent Swarm

| Ch | Title | What You Build |
|----|-------|----------------|
| 10 | [Splitting Into Agents](chapters/ch10.md) | Monolith → peer agents (coder, reviewer, runner, researcher) |
| 11 | [Broadcast & Discovery](chapters/ch11.md) | Agents announce capabilities + skills, discover peers |
| 12 | [Peer Communication](chapters/ch12.md) | Direct agent-to-agent messaging, artifact handoffs |
| 13 | [Swarm Patterns](chapters/ch13.md) | Orchestrator-workers → peer coordination, consensus, collective learning |

> 📁 [spec/ch10/](spec/ch10/) — [prompt-template.md](spec/ch10/prompt-template.md) · [interface-spec.md](spec/ch10/interface-spec.md) · [expected-output.txt](spec/ch10/expected-output.txt) · [test_ch10.py](spec/ch10/validation/test_ch10.py)
>
> 📁 [spec/ch11/](spec/ch11/) — [prompt-template.md](spec/ch11/prompt-template.md) · [interface-spec.md](spec/ch11/interface-spec.md) · [expected-output.txt](spec/ch11/expected-output.txt) · [test_ch11.py](spec/ch11/validation/test_ch11.py)
>
> 📁 [spec/ch12/](spec/ch12/) — [prompt-template.md](spec/ch12/prompt-template.md) · [interface-spec.md](spec/ch12/interface-spec.md) · [expected-output.txt](spec/ch12/expected-output.txt) · [test_ch12.py](spec/ch12/validation/test_ch12.py)
>
> 📁 [spec/ch13/](spec/ch13/) — [prompt-template.md](spec/ch13/prompt-template.md) · [interface-spec.md](spec/ch13/interface-spec.md) · [expected-output.txt](spec/ch13/expected-output.txt) · [test_ch13.py](spec/ch13/validation/test_ch13.py)

### Production

| Ch | Title | What You Build |
|----|-------|----------------|
| 14 | [Production Architecture](chapters/ch14.md) | Checkpoints, tracing, versioned deploys |
| 15 | [The Agent Ecosystem](chapters/ch15.md) | External MCP tools, A2A partner agents, governance |

> 📁 [spec/ch14/](spec/ch14/) — [prompt-template.md](spec/ch14/prompt-template.md) · [interface-spec.md](spec/ch14/interface-spec.md) · [expected-output.txt](spec/ch14/expected-output.txt) · [test_ch14.py](spec/ch14/validation/test_ch14.py)
>
> 📁 [spec/ch15/](spec/ch15/) — [prompt-template.md](spec/ch15/prompt-template.md) · [interface-spec.md](spec/ch15/interface-spec.md) · [expected-output.txt](spec/ch15/expected-output.txt) · [test_ch15.py](spec/ch15/validation/test_ch15.py)

---

## Build Progression

What `tbh-code` looks like at each stage:

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

*"tbh, the spec is all you need."*
