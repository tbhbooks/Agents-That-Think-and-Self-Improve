# Chapter 14 — Production Architecture

## Scope

Make the agent swarm production-ready: durable, observable, and safely deployable. Agents survive crashes, tasks are traceable across agents, versions are declared and checked, mixed-version swarms negotiate gracefully, and retries are safe.

## Learning Objectives

- Implement checkpoints so agents can resume after crashes
- Build distributed tracing that spans multiple agents in a swarm
- Design versioning for agents with semver semantics
- Handle mixed-version swarms via protocol negotiation
- Implement system-wide idempotency for safe retries
- Understand production patterns: circuit breakers, health checks, structured logging

## What You Build

1. **Checkpoints:** Agents save state at plan-step boundaries; crashed agents resume from last checkpoint.
2. **Distributed tracing:** Trace IDs and span context propagate across agent messages; full request path visible as a waterfall.
3. **Agent versioning:** Each agent declares its version (semver) and protocol version; peers check compatibility before collaborating.
4. **Mixed-version handling:** Swarm negotiates down to lowest common protocol/capabilities when agents are at different versions.
5. **System-wide idempotency:** Idempotency keys on every logical operation; receivers deduplicate before processing.
6. **Production patterns:** Circuit breakers, health checks, structured logging (brief implementations).

## Key Interfaces

### Checkpoint

```
Checkpoint:
    agent_id: string              # which agent
    task_id: string               # which task
    step_index: int               # how far through the plan
    state: dict                   # agent-specific state snapshot
        current_plan: Plan
        completed_steps: list
        pending_messages: list
        tool_results: list
        memory_updates: list
        context_summary: string   # compressed context for LLM reload
    timestamp: datetime
    parent_checkpoint_id: string  # previous checkpoint (for history)
```

### CheckpointStore

```
CheckpointStore:
    save(agent_id, checkpoint) -> checkpoint_id
    restore(agent_id, task_id=null) -> Checkpoint | null
    list(agent_id) -> list[CheckpointSummary]
    cleanup(agent_id, keep_last=5)
```

### TraceSpan

```
TraceSpan:
    span_id: string
    trace_id: string
    parent_span_id: string | null
    agent: string
    action: string
    start_time: datetime
    end_time: datetime | null
    status: "ok" | "error" | "timeout" | "crashed"
    metadata: dict
```

### Trace

```
Trace:
    trace_id: string
    root_span: TraceSpan
    spans: list[TraceSpan]
    duration: float

    waterfall() -> string
```

### TraceContext (propagated through messages)

```
TraceContext:
    trace_id: string
    parent_span_id: string
```

### AgentVersion

```
AgentVersion:
    agent_name: string
    version: string               # semver: "2.1.0"
    capabilities_hash: string
    protocol_version: string      # message format version: "1.0"
    changelog: string
```

### CompatibilityCheck

```
CompatibilityResult: "compatible" | "degraded" | "incompatible"

check_compatible(agent_a: AgentVersion, agent_b: AgentVersion) -> CompatibilityResult
```

### Protocol Negotiation

```
NegotiatedProtocol:
    protocol_version: string
    available_capabilities: list[string]
    degraded_features: list[string]

negotiate_protocol(agents: list[AgentVersion]) -> NegotiatedProtocol
```

### IdempotencyKey and IdempotencyStore

```
IdempotencyKey:
    key: string   # "{source_agent}:{task_id}:{action}:{sequence}"

IdempotencyStore:
    check(key) -> AlreadyDone(result) | Proceed
    record(key, result)
```

### CircuitBreaker

```
CircuitBreaker:
    state: "closed" | "open" | "half-open"
    failure_count: int
    threshold: int = 3
    cooldown: duration = 30s

    call(agent, request) -> result
```

### HealthReport

```
HealthReport:
    agent_name: string
    status: "healthy" | "degraded" | "unhealthy"
    queue_depth: int
    last_task_completed: datetime
    uptime: duration
    checkpoint_age: duration
    version: AgentVersion
```

## Success Criteria

- Agent resumes from checkpoint after simulated crash — picks up at next plan step, not from scratch
- Trace shows the full path of a request across all agents as a waterfall view
- Version mismatch between agents is detected: compatible, degraded, or incompatible
- Mixed-version swarm completes tasks using negotiated common capabilities
- Retried operations produce the same result (idempotency key deduplicates)
- Circuit breaker opens after threshold failures and rejects subsequent requests

## Concepts Introduced

- Checkpoints and resumability (durable agent state at boundaries)
- Distributed tracing across agents (trace context propagation, waterfall view)
- Agent versioning with semver (major=breaking, minor=new capability, patch=bugfix)
- Mixed-version deployment and protocol negotiation
- System-wide idempotency (keys, check-before-process, record-after-complete)
- Circuit breakers, health checks, structured logging
- Rainbow deployment (canary, expand, complete)
- Observability as a first-class concern

## Upgrade Table from Ch 13

| Capability | Ch 13 (Swarm Patterns) | Ch 14 (Production Architecture) |
|-----------|------------------------|-------------------------------|
| Crash recovery | No recovery — all progress lost | Checkpoints at boundaries, resume from last step |
| Observability | Correlation IDs group messages | Distributed tracing with waterfall view |
| Versioning | Agents have identity, no version | Semver with compatibility checks |
| Multi-version | Not supported | Protocol negotiation, degraded mode, rainbow deploy |
| Retries | Implicit, may cause duplicates | Idempotency keys deduplicate across agents |
| Failure handling | Backpressure signals | + Circuit breakers, health checks |
| Logging | Ad-hoc per agent | Structured logging with trace/span IDs |

## Phase Upgrade (Observe/Think/Act/Reflect)

| Phase | Ch 13 | Ch 14 |
|-------|-------|-------|
| **Observe** | Events from broadcast bus, peer messages | + Checkpoint restore, trace context extraction |
| **Think** | Route decisions, consensus, conflict resolution | + Version compatibility check, protocol negotiation |
| **Act** | Publish events, fan-out, review chains | + Checkpoint save, span creation, idempotency record |
| **Reflect** | Collective learning, skill propagation | + Trace waterfall analysis, health reporting |
