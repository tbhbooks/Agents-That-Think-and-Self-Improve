# Chapter 12 — Peer Communication

## Scope

Build direct agent-to-agent messaging — structured message envelopes, request/response, streaming, artifact handoffs, and correlation IDs for tracing multi-agent conversations. No central coordinator.

## Learning Objectives

- Design message envelopes with routing, typing, correlation, and metadata
- Implement request/response patterns between peer agents
- Handle streaming results from long-running agent tasks
- Build artifact handoffs — agents pass typed work products to each other
- Implement correlation IDs for tracking multi-agent conversation chains
- Handle timeouts and undeliverable messages

## What You Build

1. **Message envelope:** Structured message with `id`, `from`, `to`, `type`, `correlation_id`, `payload`, `timestamp`. Seven fields, every message, no exceptions.
2. **Send/receive plumbing:** `send(message)` delivers to the target agent via the broadcast bus. `receive(filter)` blocks until a matching message arrives. Filter by `from`, `type`, `correlation_id`.
3. **Request/response:** `request(to, action, payload, correlation_id)` wraps send + receive for the common ask-and-wait pattern. Returns the correlated response.
4. **Streaming:** `stream(to, chunks_generator, correlation_id)` sends `stream_chunk` messages as results are produced, followed by a `stream_end` with a summary. Receiver collects chunks incrementally.
5. **Artifact handoffs:** Typed work products (`diff`, `test_report`, `review`, `documentation`, `file_snapshot`) travel inside message payloads. Each artifact has `id`, `type`, `producer`, `content`, `created_at`.
6. **Chain tracing:** `start_chain()` creates a new `correlation_id`. `continue_chain(message)` reuses the existing one. All messages in a multi-agent chain share one ID.
7. **Timeout handling:** `receive()` supports a timeout. Unresponsive peers return a timeout error rather than blocking forever.

## Key Interfaces

```
Message:
    id: string (uuid)
    from: string (agent name)
    to: string (agent name)
    type: enum("request", "response", "stream_chunk", "stream_end")
    correlation_id: string (uuid)
    payload: dict
    timestamp: ISO 8601 string

Artifact:
    id: string (uuid)
    type: enum("diff", "test_report", "review", "documentation", "file_snapshot")
    producer: string (agent that created it)
    content: dict (type-specific payload)
    created_at: ISO 8601 string

PeerMessenger:
    bus: BroadcastBus             # from Ch 11
    pending: dict                 # correlation_id -> callback
    inbox: Message[]

    send(message) -> void
    receive(filter, timeout) -> Message
    request(to, action, payload, correlation_id) -> Message
    stream(to, chunks_generator, correlation_id) -> void

    start_chain() -> string           # new correlation_id
    continue_chain(message) -> string # reuse correlation_id
```

## Success Criteria

- Coder agent sends a review request to Reviewer agent with a diff artifact
- Reviewer agent responds with structured findings using the same `correlation_id`
- Runner agent streams test results back as `stream_chunk` messages, ending with `stream_end`
- `stream_end` includes a summary of all chunks
- Artifacts (`diff`, `test_report`, `review`) are passed between agents intact and parseable
- Correlation IDs correctly link all messages in a 10-message, 3-agent chain
- `start_chain()` produces a new correlation_id; `continue_chain()` reuses existing
- Timeout fires when a peer does not respond within the configured window
- Messages are filterable by `from`, `type`, and `correlation_id`

## Concepts Introduced

- Message envelopes and structured routing
- Request/response between peers (synchronous pattern)
- Streaming partial results (incremental pattern)
- Artifact handoffs — typed, attributed, traceable work products
- Correlation IDs for conversation threading
- Chain management (`start_chain` / `continue_chain`)
- Timeout handling for unresponsive peers
- Peer-to-peer vs coordinator-mediated communication
- Blackboard pattern — agents read from and write to a shared workspace rather than messaging each other directly
- Saga pattern — a sequence of agent actions with compensating rollbacks if any step fails

## CLI Interface

```
# Run swarm with peer communication
tbh-code --swarm --codebase ./todo-api --ask "Fix the auth middleware and get it reviewed"

# Run a single agent in listen mode
tbh-code --agent runner --listen

# Run a specific agent with a task
tbh-code --agent coder --codebase ./todo-api --auto-approve --ask "Fix auth and get it reviewed"
```

## Upgrade from Ch 11

| Capability | Ch 11 | Ch 12 |
|-----------|-------|-------|
| Agent identity + capabilities | Yes | Yes |
| Broadcast bus | Yes | Yes |
| Agent discovery | Yes | Yes |
| Capability advertisement | Yes | Yes |
| Skill sharing | Yes | Yes |
| Message envelopes | No | Yes — structured 7-field messages |
| Request/response | No | Yes — correlated ask-and-wait |
| Streaming | No | Yes — incremental chunks + stream_end |
| Artifact handoffs | No | Yes — typed work products in payloads |
| Correlation IDs | No | Yes — one thread per conversation chain |
| Timeout handling | No | Yes — unresponsive peers don't block forever |

## What This Chapter Does NOT Include

- **No self-organization** — agents talk when told to, not autonomously (that's Ch 13)
- **No consensus or voting** — one-to-one communication only (group patterns are Ch 13)
- **No persistent message queues** — in-memory delivery, not durable messaging
- **No authentication between agents** — local swarm, trusted peers
- **No message encryption** — local transport, not cross-network
- **No central coordinator** — peers talk directly, bus only routes
