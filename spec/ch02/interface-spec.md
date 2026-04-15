# Chapter 2 — Interface Spec

## Overview

Upgrade the Ch 1 agent loop into a real **Augmented LLM**: an agent that reads a codebase, maintains conversation history, and returns structured responses. The agent can now answer questions about `todo-api` by actually reading the files.

---

## Agent

### Interface

```
Agent:
    config: AgentConfig
    system_prompt: string
    history: Message[]
    context: FileContext

    chat(user_message: string) → StructuredResponse
    reset() → void
```

### AgentConfig

```
AgentConfig:
    llm_client: LLMClient
    model: string
    max_tokens: int (default: 2048)
    codebase_path: string  # path to todo-api/
    max_context_files: int (default: 20)
    max_file_size: int (default: 10000)  # bytes — skip files larger than this
```

---

## System Prompt

The system prompt defines the agent's identity. The reader writes it as part of the build.

### Required Elements

```
SystemPrompt:
    role: string         # "You are tbh-code, a coding assistant..."
    capabilities: string # "You can read and analyze code files..."
    constraints: string  # "Only reference files you have actually read..."
    output_format: string # "Respond with JSON: { answer, confidence, sources }"
```

### Example System Prompt

```
You are tbh-code, a coding assistant that analyzes codebases.

Capabilities:
- You can read source files provided in context
- You can answer questions about code structure, bugs, and design

Constraints:
- Only reference files that appear in your context
- If you don't have enough information, say so
- Never invent file names, function names, or line numbers

Output format:
Respond with valid JSON:
{
  "answer": "your analysis here",
  "confidence": 0.0 to 1.0,
  "sources": ["file1.ext:line", "file2.ext:line"]
}
```

---

## Conversation History

### Interface

```
Message:
    role: enum("system", "user", "assistant")
    content: string
    timestamp: string (ISO 8601)

History:
    messages: Message[]

    add(message: Message) → void
    get_messages() → Message[]
    token_count() → int
    truncate(max_tokens: int) → void  # remove oldest messages to fit budget
```

### Behavior

- History is maintained within a session (not across sessions — that's Ch 6)
- System prompt is always the first message
- Each `chat()` call appends the user message and the assistant response
- When history grows too large, oldest non-system messages are removed

---

## File Context

### Interface

```
FileContext:
    codebase_path: string
    files: FileEntry[]

    load(path: string) → void
    get_relevant(query: string) → FileEntry[]

FileEntry:
    path: string (relative to codebase root)
    content: string
    size: int (bytes)
    language: string (inferred from extension)
```

### Loading Strategy (Naive — Ch 2)

Ch 2 uses a simple loading strategy. Smarter retrieval comes in Ch 6.

1. Walk the directory tree at `codebase_path`
2. Skip files larger than `max_file_size`
3. Skip binary files (images, executables, etc.)
4. Skip common ignore patterns (node_modules, .git, __pycache__, etc.)
5. Load up to `max_context_files` files
6. For `get_relevant(query)`: simple keyword match — files whose path or content contains query terms score higher

### Context Injection

When building the LLM prompt, inject file context between the system prompt and conversation history:

```
[System prompt]
[File context — relevant files for this query]
[Conversation history]
[Current user message]
```

---

## Structured Response

### Interface

```
StructuredResponse:
    answer: string          # the analysis/answer
    confidence: float       # 0.0 to 1.0
    sources: string[]       # file paths referenced (e.g., "src/middleware/auth.pseudo:15")
    raw: string             # the raw LLM output before parsing
```

### Parsing

The agent instructs the LLM to produce JSON output (via system prompt). The parser:

1. Attempts to extract JSON from the LLM response
2. Validates required fields (`answer`, `confidence`, `sources`)
3. Falls back gracefully if JSON parsing fails:
   - `answer` = raw response text
   - `confidence` = 0.0
   - `sources` = []
   - `raw` = original text

---

## CLI Interface

```
# Interactive mode (default)
tbh-code --codebase ./todo-api

# Starts a REPL:
tbh-code> What does the auth middleware do?
{
  "answer": "The auth middleware in src/middleware/auth.pseudo checks for...",
  "confidence": 0.9,
  "sources": ["src/middleware/auth.pseudo:8"]
}

tbh-code> Is there a bug in it?
{
  "answer": "Yes. The middleware accepts any non-empty token...",
  "confidence": 0.95,
  "sources": ["src/middleware/auth.pseudo:12"]
}

# Single-question mode
tbh-code --codebase ./todo-api --ask "Find the security vulnerability in auth"
```

---

## Upgrade from Ch 1

| Capability | Ch 1 | Ch 2 |
|-----------|------|------|
| LLM call | ✓ | ✓ |
| Agent loop (observe/think/act/reflect) | ✓ | ✓ (now with file context in observe) |
| File reading | ✗ | ✓ |
| System prompt | ✗ | ✓ |
| Conversation history | ✗ | ✓ (within session) |
| Structured output | ✗ | ✓ (JSON with answer/confidence/sources) |
| Context management | ✗ | ✓ (naive file loading, keyword relevance) |

The Ch 1 agent loop is still present — it now has real data in the "observe" phase (file contents) instead of operating blind.

---

## Test Task

Same task as Ch 1, but now the agent can actually solve it:

```
Task: "Find the security vulnerability in the todo-api authentication system.
       Identify the file, the function, and explain what's wrong."

Expected StructuredResponse:
{
  "answer": "The auth middleware in src/middleware/auth.pseudo has a critical
             vulnerability. The auth_middleware() function accepts any non-empty
             token as valid — it checks that the Authorization header is present
             and non-empty, but never decodes the token, verifies a signature,
             checks expiry, or looks up the user. It hardcodes req.user to
             { id: 1, username: 'unknown' } for every request.",
  "confidence": 0.95,
  "sources": ["src/middleware/auth.pseudo:8-15"]
}
```

### Multi-Turn Test

```
Turn 1: "What files are in the todo-api project?"
  → Agent lists files it loaded

Turn 2: "What does the auth middleware do?"
  → Agent describes the middleware, referencing src/middleware/auth.pseudo

Turn 3: "Is there a bug in the auth middleware?"
  → Agent identifies the token validation bug, with file + line references

Turn 4: "Are there any tests for token validation?"
  → Agent checks tests/auth_test.pseudo, notes that no test covers
    the middleware's token validation logic
```

---

## What This Chapter Does NOT Include

- **No tool calling** — file reading is built into the agent, not an MCP tool (that's Ch 3)
- **No persistent memory** — history resets when the agent exits (that's Ch 6)
- **No file writing** — read-only access to the codebase (that's Ch 5)
- **No planning** — single-step reasoning, no task decomposition (that's Ch 7)
