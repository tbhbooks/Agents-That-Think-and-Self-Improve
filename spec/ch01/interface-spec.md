# Chapter 1 — Interface Spec

## Overview

Two programs. The first is a one-shot prompt wrapper that fails. The second is an agent loop that catches the failure.

Both operate on the `todo-api` codebase (see `../todo-api/`).

---

## Program 1: One-Shot Wrapper

### Interface

```
OneShot:
    llm_client: LLMClient

    send(prompt: string) → Response

Response:
    content: string
    model: string
    usage: { prompt_tokens: int, completion_tokens: int }
```

### Behavior

1. Takes a natural language prompt as input
2. Sends it to an LLM API (any provider — OpenAI, Anthropic, local model)
3. Returns the raw response
4. No loop, no verification, no tools

### Configuration

The reader provides their own LLM API key. The spec does not mandate a provider.

```
Config:
    api_key: string (from environment variable)
    model: string (reader's choice)
    max_tokens: int (default: 1024)
```

---

## Program 2: Agent Loop

### Interface

```
AgentLoop:
    llm_client: LLMClient
    max_iterations: int (default: 5)

    run(task: string) → AgentResult

AgentResult:
    answer: string
    iterations: int
    trace: StepTrace[]

StepTrace:
    step: int
    phase: enum("observe", "think", "act", "reflect")
    content: string
    grounded: bool  # did this step reference verifiable facts?
```

### The Four Phases

Each iteration of the loop executes four phases:

```
observe(task, previous_result) → observation
    # What do I know? What can I see?
    # In Ch 1: limited to the task description and prior iterations
    # In Ch 2+: will include file contents, tool results, etc.

think(observation) → plan
    # What should I do next?
    # Produce a short reasoning trace

act(plan) → result
    # Execute the plan
    # In Ch 1: ask the LLM to produce an answer
    # In Ch 2+: will include tool calls, file reads, etc.

reflect(task, result) → ReflectOutcome
    # Is this answer grounded? Am I confident?
    # Check: does the answer reference specific, verifiable facts?
    # Check: does the answer contain hedging language ("might", "probably")?
    # Check: has the answer improved since last iteration?

ReflectOutcome:
    should_continue: bool
    confidence: float (0.0 to 1.0)
    issues: string[]  # what's still wrong
```

### Loop Termination

The loop exits when ANY of:
- `reflect` returns `should_continue: false` (agent is confident)
- `max_iterations` is reached (safety valve)
- Two consecutive iterations produce identical output (stuck)

### Grounding Check (Reflect Phase)

In Ch 1, the reflect phase performs a **simple grounding check**:

1. **Specificity test:** Does the answer name concrete things (file paths, function names, line numbers)?
2. **Hedge detection:** Count hedge words ("might", "probably", "could be", "I think"). High count = low confidence.
3. **Consistency test:** If this isn't the first iteration, did the answer change? If the answer keeps changing, the agent isn't converging.

This is deliberately primitive. The point is to show that even a basic check catches obvious hallucinations. More sophisticated verification comes in later chapters (Ch 3: tool-based verification, Ch 8: self-evaluation).

---

## Test Task

The spec provides one standard test task for validation:

```
Task: "Find the security vulnerability in the todo-api authentication system.
       Identify the file, the function, and explain what's wrong."

Expected: The agent should identify:
  - File: src/middleware/auth.pseudo
  - Issue: auth_middleware accepts any non-empty token without validation
  - Specifics: no signature check, no expiry check, hardcoded user ID
```

### Why This Task?

- **One-shot will fail:** Without seeing the actual code, the LLM will hallucinate file names, function names, or invent a plausible but wrong vulnerability
- **The loop helps:** Even without tools, the reflect phase catches the hallucination — the answer names files that can't be verified, uses hedge language, or changes between iterations

---

## CLI Interface

The reader's program should be runnable from the command line:

```
# One-shot mode
tbh-code --mode oneshot --task "Find the security vulnerability..."

# Agent loop mode
tbh-code --mode loop --task "Find the security vulnerability..." --max-iterations 5
```

### Output Format

Both modes print to stdout. The agent loop mode also prints the trace:

```
# One-shot output
[oneshot] Response:
<LLM response text>

# Agent loop output
[loop] Iteration 1:
  [observe] <observation>
  [think] <reasoning>
  [act] <action/response>
  [reflect] confidence=0.3, issues=["references unverified file paths"]
[loop] Iteration 2:
  [observe] <observation including feedback from reflect>
  [think] <adjusted reasoning>
  [act] <revised response>
  [reflect] confidence=0.7, issues=["still no direct verification"]
[loop] Result after 2 iterations:
<final answer>
```

---

## What This Chapter Does NOT Include

These are explicitly out of scope for Ch 1:

- **No file reading** — the agent cannot read `todo-api` files (that's Ch 2)
- **No tools** — no function calling, no MCP (that's Ch 3)
- **No memory** — no persistence across runs (that's Ch 6)
- **No structured output parsing** — raw text only (that's Ch 2)

The agent loop in Ch 1 is "thinking harder" — re-examining its own output — not "acting smarter." The limitation is the lesson: loops help, but loops without tools are still limited.
