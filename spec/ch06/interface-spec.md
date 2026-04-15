# Chapter 6 — Interface Spec

## Overview

Add persistent memory and context management to the agent. A `MemoryStore` saves facts, decisions, outcomes, and rules across sessions. A `Session` saves and restores full conversation state. A `ContextBudget` allocates the finite token window across competing needs. `OutcomeEntry` tracks whether actions worked — the raw data for self-improvement.

Operates on the `todo-api` codebase (see `../todo-api/`).

---

## MemoryEntry

```
MemoryEntry:
    key: string                     # unique identifier, e.g. "todo-api/auth-fix-outcome"
    content: string                 # the memory content (human-readable)
    type: MemoryType                # what kind of memory this is
    tags: string[]                  # searchable tags, e.g. ["auth", "bug-fix", "todo-api"]
    timestamp: datetime             # when this memory was created
    session_id: string | null       # which session created this memory (optional)
```

### MemoryType

```
MemoryType: enum("fact", "decision", "outcome", "rule")
```

| Type | What It Stores | Example |
|------|---------------|---------|
| fact | Something the agent learned about the codebase | "todo-api uses Express-style routing with pseudo-code" |
| decision | A choice the agent made and why | "Chose batched query over lazy loading for N+1 fix" |
| outcome | What happened when an action was taken (success/failure + metrics) | "Fixed auth middleware — 8/8 tests pass" |
| rule | A behavioral constraint (from user feedback or learned) | "Never use mocks in integration tests" |

---

## MemoryStore

```
MemoryStore:
    storage_path: string            # where memories are persisted (file or directory)

    save(entry: MemoryEntry) -> void
        # Persist a memory entry
        # If key already exists, overwrite with new entry
        # Writes to disk immediately (crash-safe)

    retrieve(key: string) -> MemoryEntry | null
        # Look up a specific memory by key
        return load_from_storage(key)

    search(query: string, filters: SearchFilters | null, limit: int = 10) -> MemoryEntry[]
        # Search memories by keyword match + optional filters
        # Returns entries ranked by relevance (keyword match) + recency
        candidates = all_entries()

        if filters:
            candidates = apply_filters(candidates, filters)

        scored = []
        for entry in candidates:
            keyword_score = count_keyword_matches(query, entry.content + " ".join(entry.tags))
            recency_score = recency_weight(entry.timestamp)  # newer = higher
            scored.append((entry, keyword_score * 0.7 + recency_score * 0.3))

        scored.sort(by=score, descending=true)
        return scored[:limit]

    list(type: MemoryType | null) -> MemoryEntry[]
        # List all memories, optionally filtered by type
        entries = all_entries()
        if type:
            entries = [e for e in entries if e.type == type]
        return entries

SearchFilters:
    type: MemoryType | null         # filter by memory type
    tags: string[] | null           # filter by tags (any match)
    since: datetime | null          # filter by timestamp (after this date)
```

### Storage Format

Memories are stored as files on disk — one JSON file per entry, organized by type:

```
.tbh-code/
  memory/
    facts/
      todo-api-uses-express.json
    decisions/
      auth-fix-batched-query.json
    outcomes/
      auth-middleware-fix-2024-01-15.json
    rules/
      no-mocks-in-integration.json
```

Each JSON file contains the serialized `MemoryEntry`.

---

## Session

```
Session:
    session_id: string              # unique session identifier

SessionState:
    session_id: string
    conversation_history: Message[] # full conversation from Ch 2
    active_task: string | null      # what the agent was working on
    loaded_files: string[]          # which files were in context
    tool_calls: ToolCallRecord[]    # tools used this session
    timestamp: datetime             # when session was saved

Session:
    save_state(session_id: string, state: SessionState) -> void
        # Serialize session state to disk
        # Path: .tbh-code/sessions/{session_id}.json
        write_json(.tbh-code/sessions/{session_id}.json, state)

    restore_state(session_id: string) -> SessionState | null
        # Load session state from disk
        # Returns null if session_id not found
        path = .tbh-code/sessions/{session_id}.json
        if not file_exists(path):
            return null
        return read_json(path)

    list_sessions() -> SessionSummary[]
        # List all saved sessions with basic info
        return [
            { session_id, active_task, timestamp }
            for each .json in .tbh-code/sessions/
        ]
```

### Session Lifecycle

```
1. Agent starts:
   - If --session <id> provided: restore_state(id) → resume
   - If no session flag: generate new session_id, start fresh

2. During execution:
   - Session ID shown in output: [session: abc123]
   - Conversation history accumulates as in Ch 2

3. Agent exits (or user quits):
   - save_state(session_id, current_state)
   - Print: "Session saved: abc123. Resume with --session abc123"

4. Agent resumes:
   - restore_state(abc123) → loads history, active task, files
   - Agent continues where it left off
```

---

## ContextBudget

```
ContextBudget:
    total_tokens: int               # max context window size (e.g. 20000 for demos, scale up for production)
    allocations: dict               # named budget slots

    # Default allocation percentages
    DEFAULT_ALLOCATIONS:
        system_prompt: 0.10         # 10% — system prompt + tool schemas
        conversation_history: 0.30  # 30% — recent conversation turns
        retrieved_memories: 0.15    # 15% — relevant long-term memories
        loaded_files: 0.35          # 35% — file contents for current task
        current_task: 0.10          # 10% — current user message + response buffer

    allocate(items: BudgetItem[]) -> BudgetItem[]
        # Given items competing for context space, select within budget
        # Each item has a token_count and priority
        #
        # Algorithm:
        # 1. Sort items by priority (highest first)
        # 2. Add items until budget for that category is exhausted
        # 3. Return selected items

        selected = []
        remaining = {}
        for category, pct in DEFAULT_ALLOCATIONS:
            remaining[category] = int(total_tokens * pct)

        for item in sorted(items, by=priority, descending=true):
            if remaining[item.category] >= item.token_count:
                selected.append(item)
                remaining[item.category] -= item.token_count

        return selected

    usage() -> BudgetUsage
        # Return current token usage by category
        return { category: (allocated - remaining) for each category }

BudgetItem:
    content: string                 # the text to include in context
    category: string                # which budget slot this belongs to
    token_count: int                # estimated tokens (len(content) / 4 as rough estimate)
    priority: float                 # higher = more important (0.0 to 1.0)

BudgetUsage:
    total: int
    used: int
    by_category: dict[string, { allocated: int, used: int }]
```

### Budget Math Example (20K demo window)

```
Total: 20,000 tokens

  system_prompt:           2,000 tokens (10%)
  conversation_history:    6,000 tokens (30%)
  retrieved_memories:      3,000 tokens (15%)
  loaded_files:            7,000 tokens (35%)
  current_task:            2,000 tokens (10%)

If memories need 4,500 tokens but budget is 3,000:
  → Rank by relevance, take top entries that fit in 3,000
  → Remainder is dropped (not loaded into context)

Note: 20K is deliberately small to make the budget visible.
Scale total_tokens to 128K, 200K, or 1M for production —
the percentages and algorithm don't change.
```

---

## OutcomeEntry

```
OutcomeEntry:
    task: string                    # what was the agent trying to do
    action: string                  # what did the agent actually do
    result: string                  # what happened (success/failure description)
    metrics: dict                   # measurable results
    diagnosis: string               # brief analysis of why it worked or didn't
    timestamp: datetime

    # Stored as a MemoryEntry with type="outcome"
```

### Example OutcomeEntry

```
OutcomeEntry:
    task: "Fix the auth middleware bug in todo-api"
    action: "Rewrote auth_middleware to decode base64 tokens and look up users in DB"
    result: "success"
    metrics: {
        tests_before: "4 pass, 1 fail",
        tests_after: "8 pass, 0 fail",
        files_modified: 2,
        lines_changed: 31
    }
    diagnosis: "The original middleware accepted any non-empty token. Fix was straightforward — decode token, look up user. Added 4 new test cases."
```

### When to Log Outcomes

Outcomes are logged automatically when:
1. A task completes (success or failure)
2. A skill finishes executing
3. The user confirms or rejects agent output

The agent does NOT log outcomes for intermediate steps — only final task results.

---

## Memory Integration with Agent Loop

### Retrieval Flow

```
1. User provides a new task
2. Agent queries MemoryStore: search(task_description, filters={type: [outcome, rule]})
3. Top N results are injected into context as "relevant memories"
4. ContextBudget ensures memories fit within allocation
5. Agent reasons with both current task and past experience
```

### System Prompt Addition (Ch 6)

Add to the Ch 5 system prompt:

```
You have access to long-term memory from previous sessions.

Relevant memories for this task:
{retrieved_memories}

Rules (always follow these):
{rules}

When you complete a task, log the outcome:
- What you tried
- Whether it worked
- Key metrics
- Brief diagnosis
```

---

## CLI Interface

```
# New session (default)
tbh-code --codebase ./todo-api --ask "Fix the N+1 query bug"

# Resume a previous session
tbh-code --codebase ./todo-api --session abc123

# List saved sessions
tbh-code --codebase ./todo-api --list-sessions
```

---

## Upgrade from Ch 5

| Capability | Ch 5 | Ch 6 |
|-----------|------|------|
| Tool interface | Yes | Yes |
| SimpleTools (read + write + execute) | Yes | Yes |
| MCPTool | Yes | Yes |
| SkillTool | Yes | Yes |
| PermissionLevel + ActionGate | Yes | Yes |
| MemoryStore | No | Yes — persistent facts, decisions, outcomes, rules |
| Session persistence | No | Yes — save and restore conversation state |
| ContextBudget | No | Yes — token allocation across context categories |
| Retrieval | No | Yes — keyword + recency ranking |
| Outcome tracking | No | Yes — structured metrics and diagnosis |

---

## Test Task

```
Task: Agent works on todo-api across two sessions.

Session 1:
  1. Agent fixes the auth middleware bug (using Ch 5 capabilities)
  2. Agent logs outcome: task, action, result, metrics, diagnosis
  3. Session saves on exit

Session 2 (resumed):
  1. Agent restores session state — knows it already fixed auth
  2. New task: "Fix a similar token validation issue in the API key middleware"
  3. Agent retrieves the auth middleware outcome from memory
  4. Agent uses the prior approach as starting point

Expected: Agent references prior work, doesn't start from scratch.
```

---

## What This Chapter Does NOT Include

- **No embedding-based retrieval** — keyword + recency ranking only (embeddings are an advanced extension)
- **No planning** — agent remembers but doesn't decompose tasks into steps (that's Ch 7)
- **No self-evaluation** — outcomes are logged but the agent doesn't score its own output (that's Ch 8)
- **No skill rewriting** — outcomes are stored but don't automatically change behavior (that's Ch 9)
- **No shared memory** — memory is local to one agent instance (multi-agent memory is Ch 11+)
- **No summarization** — old context is dropped by budget, not compressed (reader can add summarization as extension)
