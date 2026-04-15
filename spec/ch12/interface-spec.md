# Chapter 12 — Interface Spec

## Overview

Build peer-to-peer communication between agents. A `Message` envelope carries every inter-agent exchange — requests, responses, stream chunks, stream ends. An `Artifact` is a typed work product (diff, test report, review) that travels inside message payloads. A `PeerMessenger` manages sending, receiving, request/response, streaming, and chain tracing via correlation IDs.

Operates on the `todo-api` codebase (see `../todo-api/`).

---

## Message

```
Message:
    id: string (uuid)               # unique per message
    from: string                     # sender agent name
    to: string                       # recipient agent name
    type: MessageType                # what kind of message
    correlation_id: string (uuid)    # ties related messages together
    payload: dict                    # typed content — the actual work
    timestamp: ISO 8601 string       # when the message was created

MessageType: enum(
    "request",                       # sender expects a response
    "response",                      # reply to a request
    "stream_chunk",                  # partial result — more coming
    "stream_end"                     # final message in a stream — includes summary
)
```

### Field Semantics

- **`id`** — unique per message. Used for logging, deduplication, and reference.
- **`from` / `to`** — routing. The bus delivers based on `to`. The receiver identifies the sender via `from`.
- **`type`** — determines receiver behavior. A `request` expects a `response`. A `stream_chunk` means more is coming. A `stream_end` means done.
- **`correlation_id`** — the conversation thread. All messages in a multi-agent chain share one `correlation_id`. Enables tracing the full story of a task.
- **`payload`** — the work. A diff, test results, review findings. Typed and parseable, never prose summaries.
- **`timestamp`** — ISO 8601. Ordering and audit trail.

### Example: Request Message

```json
{
  "id": "msg-001",
  "from": "coder",
  "to": "reviewer",
  "type": "request",
  "correlation_id": "chain-abc",
  "payload": {
    "action": "review_code",
    "diff": "--- a/src/middleware/auth.pseudo\n+++ b/src/middleware/auth.pseudo\n@@ -8,6 +8,12 @@\n+    token = decode_base64(header)\n+    user = db.find_user(token)\n+    if user is null:\n+        return response(401, 'invalid token')\n+    if not constant_time_equal(user.token, header):\n+        return response(401, 'invalid token')\n+    req.user = user",
    "context": "Fixing auth middleware — was accepting any non-empty token"
  },
  "timestamp": "2025-02-10T09:15:00Z"
}
```

### Example: Response Message

```json
{
  "id": "msg-002",
  "from": "reviewer",
  "to": "coder",
  "type": "response",
  "correlation_id": "chain-abc",
  "payload": {
    "action": "review_result",
    "verdict": "approve_with_comments",
    "findings": [
      { "severity": "info", "comment": "constant_time_equal — good, prevents timing attacks" },
      { "severity": "warning", "comment": "No token expiry check. Tokens valid forever once issued." }
    ],
    "summary": "Solid fix. One concern: no token expiry."
  },
  "timestamp": "2025-02-10T09:15:03Z"
}
```

---

## Artifact

```
Artifact:
    id: string (uuid)               # unique per artifact
    type: ArtifactType              # what kind of work product
    producer: string                 # agent that created it
    content: dict                    # type-specific structured payload
    created_at: ISO 8601 string      # when the artifact was created

ArtifactType: enum(
    "diff",                          # code changes
    "test_report",                   # test execution results
    "review",                        # code review findings
    "documentation",                 # generated documentation
    "file_snapshot"                  # file state at a point in time
)
```

### Artifact Semantics

- Artifacts are **receipts for work done** — not descriptions, not summaries.
- Every artifact has a `producer` — the agent that created it.
- Artifacts travel **inside message payloads**. They are not sent separately.
- The `type` tells the receiver how to parse `content`.
- The `id` enables referencing artifacts later in the chain.

### Example: Test Report Artifact

```json
{
  "id": "artifact-001",
  "type": "test_report",
  "producer": "runner",
  "content": {
    "test_path": "tests/",
    "focus": "auth",
    "results": [
      { "test": "test_register_creates_user", "status": "pass", "duration_ms": 45 },
      { "test": "test_login_returns_token", "status": "pass", "duration_ms": 38 },
      { "test": "test_invalid_token_rejected", "status": "pass", "duration_ms": 52 },
      { "test": "test_expired_token_rejected", "status": "fail", "duration_ms": 61,
        "error": "Expected 401, got 200. Expired tokens still accepted." }
    ],
    "summary": { "total": 4, "passed": 3, "failed": 1, "duration_ms": 196 }
  },
  "created_at": "2025-02-10T09:15:07Z"
}
```

### Example: Review Artifact

```json
{
  "id": "artifact-002",
  "type": "review",
  "producer": "reviewer",
  "content": {
    "approved": true,
    "blocking_issues": [],
    "non_blocking": ["Add token expiry check"],
    "test_coverage": "3/4 passing — 1 failure is a known gap, not a regression"
  },
  "created_at": "2025-02-10T09:15:15Z"
}
```

### Example: Diff Artifact

```json
{
  "id": "artifact-003",
  "type": "diff",
  "producer": "coder",
  "content": {
    "file": "src/middleware/auth.pseudo",
    "diff_text": "--- a/src/middleware/auth.pseudo\n+++ b/src/middleware/auth.pseudo\n@@ -8,6 +8,12 @@\n+    token = decode_base64(header)\n+    ...",
    "lines_added": 8,
    "lines_removed": 2
  },
  "created_at": "2025-02-10T09:14:55Z"
}
```

---

## PeerMessenger

```
PeerMessenger:
    bus: BroadcastBus                # from Ch 11 — routes messages
    pending: dict                    # correlation_id -> callback
    inbox: Message[]                 # received messages waiting to be consumed
    name: string                     # this agent's name

    send(message: Message) -> void
        # Deliver message to the target agent via the broadcast bus.
        # Bus routes based on the "to" field.
        # Fire-and-forget from the sender's perspective.
        assert message.id is not null
        assert message.from == self.name
        assert message.to is not null
        assert message.type in ["request", "response", "stream_chunk", "stream_end"]
        assert message.correlation_id is not null
        assert message.timestamp is not null
        bus.deliver(message)

    receive(filter: MessageFilter, timeout: int = 30) -> Message
        # Block until a message arrives that matches the filter.
        # Returns the matching message.
        # Raises TimeoutError if no matching message arrives within timeout seconds.
        deadline = now() + timeout
        while now() < deadline:
            for msg in inbox:
                if matches(msg, filter):
                    inbox.remove(msg)
                    return msg
            wait(until=new_message_or_deadline)
        raise TimeoutError(
            f"No message matching {filter} within {timeout}s"
        )

    request(to: string, action: string, payload: dict,
            correlation_id: string, timeout: int = 30) -> Message
        # Send a request and wait for the correlated response.
        # Wraps send + receive for the common request/response case.
        msg = Message(
            id=generate_uuid(),
            from=self.name,
            to=to,
            type="request",
            correlation_id=correlation_id,
            payload={ "action": action, **payload },
            timestamp=now()
        )
        send(msg)
        return receive(
            filter={ correlation_id: correlation_id, type: "response", from: to },
            timeout=timeout
        )

    stream(to: string, chunks_generator: Iterator, correlation_id: string) -> void
        # Send stream_chunk messages as results are produced,
        # followed by a stream_end with summary.
        chunks = []
        for chunk in chunks_generator:
            chunks.append(chunk)
            send(Message(
                id=generate_uuid(),
                from=self.name,
                to=to,
                type="stream_chunk",
                correlation_id=correlation_id,
                payload=chunk,
                timestamp=now()
            ))
        send(Message(
            id=generate_uuid(),
            from=self.name,
            to=to,
            type="stream_end",
            correlation_id=correlation_id,
            payload={ "summary": summarize(chunks) },
            timestamp=now()
        ))

    start_chain() -> string
        # Create a new correlation_id for a new logical task.
        return generate_uuid()

    continue_chain(message: Message) -> string
        # Reuse the correlation_id from an existing message.
        # Same task, next step — same thread.
        return message.correlation_id

MessageFilter:
    from: string | null              # filter by sender
    type: string | string[] | null   # filter by message type(s)
    correlation_id: string | null    # filter by conversation thread
```

---

## Request/Response Pattern

The most common exchange: one agent asks, another answers.

```
1. Coder calls request(to="reviewer", action="review_code", payload={diff}, correlation_id="chain-abc")
2. request() internally:
   a. Creates Message(type="request", correlation_id="chain-abc")
   b. Calls send(message)
   c. Calls receive(filter={correlation_id="chain-abc", type="response", from="reviewer"})
3. Reviewer receives the request, processes it, sends Message(type="response", correlation_id="chain-abc")
4. Coder's receive() returns the response
```

Both messages share the same `correlation_id`. The response links back to the request.

---

## Streaming Pattern

For long-running operations where the requester wants incremental feedback.

```
1. Coder sends request(to="runner", action="run_tests", ...)
2. Runner calls stream(to="coder", chunks_generator=test_results, correlation_id="chain-abc")
3. stream() internally sends:
   a. stream_chunk for each test result as it completes
   b. stream_end with summary after all tests finish
4. Coder collects chunks:
   results = []
   while true:
       msg = receive(filter={correlation_id, type: ["stream_chunk", "stream_end"]})
       if msg.type == "stream_chunk":
           results.append(msg.payload)
           display_progress(msg.payload)
       if msg.type == "stream_end":
           return { chunks: results, summary: msg.payload.summary }
```

### Stream Contract

- Every `stream_chunk` has a `payload` with partial results.
- `stream_end` always comes last and includes a `summary` field in its payload.
- All stream messages share the same `correlation_id`.
- Chunks arrive in the order they were sent.

---

## Artifact Handoff Pattern

Artifacts travel inside message payloads. They are not a separate transport.

```
1. Runner produces a test_report artifact after running tests
2. Runner (or Coder) sends a message with the artifact in the payload:
   Message(
       type="request",
       payload={
           "action": "update_review",
           "artifact": { id, type: "test_report", producer: "runner", content: {...} }
       }
   )
3. Reviewer receives the message, extracts the artifact, reads it directly
4. Reviewer acts on the artifact's structured content — no prose interpretation needed
```

### Artifact Producers

| Artifact Type | Typical Producer | Content Fields |
|--------------|-----------------|----------------|
| `diff` | coder | `file`, `diff_text`, `lines_added`, `lines_removed` |
| `test_report` | runner | `test_path`, `focus`, `results[]`, `summary` |
| `review` | reviewer | `approved`, `blocking_issues[]`, `non_blocking[]`, `test_coverage` |
| `documentation` | researcher | `title`, `sections[]`, `references[]` |
| `file_snapshot` | any | `path`, `content`, `sha256` |

---

## Chain Tracing

One `correlation_id` per logical task. All messages in the chain — across agents, across hops — share it.

```
[chain-abc] msg-001: coder -> reviewer     (request: review this diff)
[chain-abc] msg-002: reviewer -> coder     (response: approve with comments)
[chain-abc] msg-003: coder -> runner       (request: run tests)
[chain-abc] msg-004: runner -> coder       (stream_chunk: test 1 pass)
[chain-abc] msg-005: runner -> coder       (stream_chunk: test 2 pass)
[chain-abc] msg-006: runner -> coder       (stream_chunk: test 3 pass)
[chain-abc] msg-007: runner -> coder       (stream_chunk: test 4 fail)
[chain-abc] msg-008: runner -> coder       (stream_end: 3/4 passed)
[chain-abc] msg-009: coder -> reviewer     (request: update review with test report)
[chain-abc] msg-010: reviewer -> coder     (response: maintain approval)
```

### Chain Management Rules

- **New task?** Call `start_chain()` — new `correlation_id`.
- **Same task, next step?** Call `continue_chain(original_message)` — reuse `correlation_id`.
- **Never mix tasks** on the same `correlation_id`.

---

## Error Handling

### Timeout

```
receive(filter, timeout=30) -> Message | TimeoutError

If no matching message arrives within the timeout window:
  - Raise TimeoutError with details about what was expected
  - The caller decides whether to retry, escalate, or abort
  - Pending requests are cleaned up from the pending dict
```

### Undeliverable Messages

```
If the "to" agent is not registered on the bus:
  - send() raises UndeliverableError
  - The message is not silently dropped
  - The caller can check bus.known_agents() before sending
```

### Malformed Messages

```
Messages missing required fields are rejected at send() time:
  - id, from, to, type, correlation_id, timestamp are all required
  - type must be one of the four valid MessageTypes
  - payload must be a dict (can be empty, but must exist)
```

---

## Agent Loop Integration

Each agent runs a message router in its main loop:

```
function agent_loop():
    while running:
        message = receive(filter={ to: self.name })
        match message.type:
            "request"      -> handle_request(message)
            "response"     -> resolve_pending(message)
            "stream_chunk" -> append_stream(message)
            "stream_end"   -> finalize_stream(message)
```

---

## CLI Interface

```
# Run the full swarm with peer communication
tbh-code --swarm --codebase ./todo-api --ask "Fix auth and get it reviewed"

# Run a single agent in listen mode
tbh-code --agent runner --listen

# Run a specific agent with a task
tbh-code --agent coder --codebase ./todo-api --auto-approve \
  --ask "Fix the auth middleware and get it reviewed"
```

---

## Upgrade from Ch 11

| Capability | Ch 11 | Ch 12 |
|-----------|-------|-------|
| Agent identity + capabilities | Yes | Yes |
| Broadcast bus + discovery | Yes | Yes |
| Capability advertisement | Yes | Yes |
| Skill sharing | Yes | Yes |
| Message envelopes (7 fields) | No | Yes |
| Request/response with correlation | No | Yes |
| Streaming (chunks + stream_end) | No | Yes |
| Artifact handoffs (typed work products) | No | Yes |
| Correlation IDs (chain tracing) | No | Yes |
| start_chain / continue_chain | No | Yes |
| Timeout handling | No | Yes |

---

## Alternative Communication Patterns

The request/response and streaming patterns above cover most agent-to-agent communication. Two alternative patterns are worth knowing about:

**Blackboard pattern:** Instead of agents sending messages to each other, all agents read from and write to a shared workspace (the "blackboard"). A coder writes a diff to the blackboard; a reviewer reads it, adds findings; a runner reads the findings, runs tests, writes results back. No direct messaging — agents coordinate through shared state. Simpler to reason about when many agents need access to the same evolving artifact, but harder to trace causality (who triggered what).

**Saga pattern:** A sequence of agent actions where each step has a compensating rollback. If the coder writes a fix, the reviewer approves it, and the runner's tests fail, the saga can roll back the coder's changes automatically. Each agent registers both a "do" action and an "undo" action. Useful for multi-agent workflows where partial completion is worse than no completion — you want all-or-nothing semantics across agents.

Neither pattern is built in this chapter — they are awareness-level alternatives to the direct messaging model. The blackboard pattern appears naturally in Ch 13 (swarm shared state). The saga pattern is relevant for production reliability in Ch 14.

---

## Test Task

```
Task: End-to-end peer communication across a coder-reviewer-runner chain.

Session 1 — Request/response:
  Coder sends review request to Reviewer with a diff.
  Reviewer responds with structured findings.
  Both messages share the same correlation_id.

Session 2 — Streaming:
  Coder sends test request to Runner.
  Runner streams 4 test results as stream_chunk messages.
  Runner sends stream_end with summary.
  Coder collects all chunks in order.

Session 3 — Artifact handoff:
  Coder sends diff artifact to Reviewer.
  Reviewer sends review artifact back to Coder.
  Runner sends test_report artifact to Coder.
  All artifacts have id, type, producer, content, created_at.

Session 4 — Full chain:
  10-message chain across coder, reviewer, runner.
  All messages share one correlation_id.
  3 artifacts exchanged.
  Chain is fully traceable by pulling the correlation_id.

Session 5 — Timeout:
  Coder sends request to an agent that doesn't respond.
  receive() times out after the configured window.
  TimeoutError is raised with details.
```
