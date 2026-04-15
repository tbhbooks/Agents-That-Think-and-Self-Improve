# Chapter 6 — Memory & Context

## Scope

Give the agent memory that persists across sessions and a context management system that stays within token limits. The agent stores facts, decisions, and outcomes — and retrieves the right memories at the right time.

## Learning Objectives

- Distinguish short-term memory (conversation history) from long-term memory (persistent store)
- Implement session persistence — save state on exit, restore on start
- Build a context budget system that allocates tokens across competing needs
- Implement retrieval that ranks memories by relevance and recency
- Store outcomes alongside actions — not just *what* the agent did, but *whether it worked* (self-improvement thread)

## What You Build

1. **MemoryStore:** Persistent key-value store for facts, decisions, outcomes, and rules. Supports save, retrieve, and search with tag-based and keyword filtering.
2. **Session persistence:** Save full conversation state (history, active task, loaded files) on exit. Restore on start with `--session <id>`.
3. **Context budget:** Finite token window partitioned across system prompt, conversation history, retrieved memories, loaded files, and current task. The agent respects the budget — no overflow.
4. **Retrieval:** Given a new task, query long-term memory for relevant entries. Rank by keyword match + recency. Inject top results into context.
5. **Outcome tracking:** Every completed task logs an OutcomeEntry: what was attempted, what happened, and a brief diagnosis. This feeds Ch 9.

## Key Interfaces

- `MemoryStore { save(entry: MemoryEntry), retrieve(key), search(query, filters) → MemoryEntry[] }`
- `MemoryEntry { key, content, type: fact|decision|outcome|rule, tags[], timestamp }`
- `Session { save_state(session_id), restore_state(session_id) → SessionState }`
- `ContextBudget { total_tokens, allocations: dict, allocate(items) → selected_items[] }`
- `OutcomeEntry { task, action, result, metrics: dict, diagnosis }`

## Success Criteria

- Agent resumes a previous session with full context (conversation history, active task)
- Agent retrieves relevant memories for a new task — not random, not everything
- Context stays within token budget (allocations sum to <= total)
- Outcome entries are stored with structured metrics and diagnosis
- Memories can be searched by type, tag, and keyword

## Concepts Introduced

- Short-term vs long-term memory (whiteboard vs notebook)
- Session persistence and restoration
- Context window management and token budgeting
- Retrieval: keyword match + recency ranking
- Outcome tracking as structured learning data

## Self-Improvement Thread

Memory is the foundation of learning. This chapter introduces **outcome tracking**: the agent stores not just what it did, but whether it worked and why. Outcome entries — `{ task, action, result, metrics, diagnosis }` — become the raw data for Ch 9's self-improvement loop. Without memory, every session is day one.

## CLI Addition

```
# Resume a previous session
tbh-code --codebase ./todo-api --session abc123

# New session (default — generates session ID)
tbh-code --codebase ./todo-api --ask "..."

# Session ID appears in output for later resume
```

## What This Chapter Does NOT Include

- **No embedding-based retrieval** — keyword + recency is enough for now (embeddings are an advanced extension)
- **No planning** — the agent remembers, but doesn't decompose tasks (that's Ch 7)
- **No self-evaluation** — outcomes are logged but the agent doesn't score its own work (that's Ch 8)
- **No skill rewriting** — outcomes are stored but don't change agent behavior yet (that's Ch 9)
- **No shared memory** — memory is local to one agent (multi-agent memory is Ch 11+)
