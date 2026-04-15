# Chapter 14 — Interface Spec

## Overview

Build the production layer for the agent swarm: checkpoints for crash recovery, distributed tracing for observability, agent versioning for compatibility, mixed-version protocol negotiation, and system-wide idempotency for safe retries. Circuit breakers, health checks, and structured logging complete the production stack.

Operates on the `todo-api` codebase (see `../todo-api/`).

---

## Checkpoint

```
Checkpoint:
    agent_id: string              # which agent created this checkpoint
    task_id: string               # which task was in progress
    step_index: int               # how far through the plan (0-indexed)
    state: dict                   # agent-specific state snapshot
        current_plan: Plan        #   the plan being executed
        completed_steps: list     #   steps already done, with results
        pending_messages: list    #   outbox messages not yet delivered
        tool_results: list        #   results from tool calls so far
        memory_updates: list      #   memory entries created this task
        context_summary: string   #   compressed context for LLM reload on resume
    timestamp: datetime           # when this checkpoint was taken
    parent_checkpoint_id: string | null  # previous checkpoint ID (for chain)
```

### Context Summary

The `context_summary` field is the key to resumability. You cannot restore an LLM's context window byte-for-byte. Instead, summarize relevant context at checkpoint time. On resume, this summary becomes the opening context — not identical to the original, but close enough to continue.

Example:
```
"Refactoring payment module. Steps 1-3 of 5 complete.
 Written: payment_validator.pseudo, updated routes.pseudo.
 Next: update middleware."
```

---

## CheckpointStore

```
CheckpointStore:
    save(agent_id: string, checkpoint: Checkpoint) -> checkpoint_id: string
        # Serialize checkpoint to durable storage (disk, SQLite, etc.)
        # Key format: "{agent_id}/{task_id}/{timestamp}"
        # Returns unique checkpoint ID
        key = f"{agent_id}/{checkpoint.task_id}/{checkpoint.timestamp}"
        storage.write(key, serialize(checkpoint))
        return key

    restore(agent_id: string, task_id: string | null = null) -> Checkpoint | null
        # Load the most recent checkpoint for this agent
        # If task_id provided, filter to that specific task
        # Returns null if no checkpoint found
        checkpoints = storage.list(prefix=f"{agent_id}/")
        if task_id:
            checkpoints = filter(c -> c.task_id == task_id, checkpoints)
        if checkpoints is empty:
            return null
        return deserialize(storage.read(most_recent(checkpoints)))

    list(agent_id: string) -> list[CheckpointSummary]
        # List all checkpoints for an agent (for debugging/inspection)
        # Returns lightweight summaries, not full checkpoint data
        return storage.list(prefix=f"{agent_id}/")
            .map(c -> CheckpointSummary(
                checkpoint_id=c.key,
                task_id=c.task_id,
                step_index=c.step_index,
                timestamp=c.timestamp
            ))

    cleanup(agent_id: string, keep_last: int = 5)
        # Prune old checkpoints, keep the N most recent
        all = storage.list(prefix=f"{agent_id}/")
        to_delete = all.sort_by(timestamp).drop_last(keep_last)
        for checkpoint in to_delete:
            storage.delete(checkpoint.key)

CheckpointSummary:
    checkpoint_id: string
    task_id: string
    step_index: int
    timestamp: datetime
```

### Integration Points: Where Checkpoints Fire in the Agent Loop

```
agent_loop_with_checkpoints(task, checkpoint_store):
    # Step 0: Check for existing checkpoint (RESTORE)
    checkpoint = checkpoint_store.restore(agent_id, task.id)
    if checkpoint:
        log(f"Resuming from checkpoint: step {checkpoint.step_index}")
        plan = checkpoint.state.current_plan
        completed = checkpoint.state.completed_steps
        context = checkpoint.state.context_summary
        start_step = checkpoint.step_index + 1
    else:
        plan = create_plan(task)
        completed = []
        context = task.description
        start_step = 0

    # Step 1: Execute remaining steps
    for i in range(start_step, len(plan.steps)):
        step = plan.steps[i]

        # Observe → Think → Act
        observation = execute_step(step, context)
        analysis = analyze(observation, plan, completed)
        result = act(analysis)
        completed.append(StepResult(step=step, result=result))

        # SAVE checkpoint after each step boundary
        checkpoint_store.save(agent_id, Checkpoint(
            agent_id=agent_id,
            task_id=task.id,
            step_index=i,
            state={
                "current_plan": plan,
                "completed_steps": completed,
                "pending_messages": get_outbox(),
                "tool_results": get_tool_results(),
                "memory_updates": get_memory_updates(),
                "context_summary": summarize_context(task, plan, completed)
            },
            timestamp=now(),
            parent_checkpoint_id=checkpoint.id if checkpoint else null
        ))

    # Step 2: Publish result and clean up
    publish_result(task, completed)
    checkpoint_store.cleanup(agent_id)
```

### Checkpoint Boundaries

Checkpoint at:
- After each plan step completion
- After each state-changing tool call (write_file, execute_shell)
- Before publishing a message to the broadcast bus
- NOT after every LLM call (too expensive)
- NOT only at task completion (too late)

---

## TraceSpan

```
TraceSpan:
    span_id: string               # unique ID for this span (uuid)
    trace_id: string              # shared across all spans in one trace
    parent_span_id: string | null # null for root span
    agent: string                 # which agent owns this span
    action: string                # what happened: "tool_call", "llm_call",
                                  # "send_message", "handle_code_ready", etc.
    start_time: datetime
    end_time: datetime | null     # null if still in progress
    status: "ok" | "error" | "timeout" | "crashed"
    metadata: dict                # action-specific details
        tool_name: string         #   for tool calls
        message_type: string      #   for messages
        error_message: string     #   for errors
        checkpoint_id: string     #   for resume spans
```

---

## Trace

```
Trace:
    trace_id: string
    root_span: TraceSpan          # the top-level span
    spans: list[TraceSpan]        # all spans (flat list)
    duration: float               # total wall-clock seconds

    waterfall() -> string:
        # Render a human-readable waterfall view
        # Each span: indented by nesting depth, shows agent, action, duration, status
        lines = []
        for span in sort_by_start_time(spans):
            indent = "  " * depth(span)
            status_icon = "✓" if span.status == "ok" else "✗"
            duration = (span.end_time - span.start_time).seconds
            lines.append(f"{indent}{status_icon} [{span.agent}] {span.action} ({duration}s)")
        return "\n".join(lines)

    depth(span) -> int:
        # Count ancestors to determine nesting level
        d = 0
        current = span
        while current.parent_span_id is not null:
            current = find_span(current.parent_span_id)
            d += 1
        return d
```

### Waterfall Rendering Example

```
WATERFALL:
──────────────────────────────────────────────────────────────────
  0s        5s        10s       15s       20s       25s
  |         |         |         |         |         |
  ✓ [user]  submit_task ─────────────────────────────── 22.4s
  ├─ ✓ [coder]  process_task ────────────────────────── 21.8s
  │  ├─ ✓ [coder]  tool:read_file ── 0.2s
  │  ├─ ✓ [coder]  tool:write_file ── 0.4s
  │  ├─ ✓ [coder]  publish:code_ready ── 0.1s
  │  ├─ ✓ [reviewer]  handle_code_ready ────────── 8.2s
  │  │  ├─ ✓ [reviewer]  tool:read_file ── 0.2s
  │  │  └─ ✓ [reviewer]  publish:review_complete ── 0.1s
  │  ├─ ✓ [runner]  handle_code_ready ──────────────── 14.6s
  │  │  └─ ✓ [runner]  tool:execute_shell ── 13.8s
  │  └─ ✓ [coder]  merge_feedback ── 1.2s
──────────────────────────────────────────────────────────────────
```

---

## Trace Propagation Through PeerMessenger Messages

The `MessageEnvelope` from Ch 12 gains a `trace_context` field:

```
MessageEnvelope:          # from Ch 12, extended
    id: string
    from_agent: string
    to_agent: string
    type: string
    payload: dict
    correlation_id: string
    timestamp: datetime
    trace_context: TraceContext | null   # NEW — for distributed tracing

TraceContext:
    trace_id: string
    parent_span_id: string
```

### Propagation Logic

```
propagate_trace(messenger, target_agent, message, current_span):
    # Sender: attach trace context to outgoing message
    message.trace_context = TraceContext(
        trace_id=current_span.trace_id,
        parent_span_id=current_span.span_id
    )
    messenger.send(target_agent, message)

receive_with_trace(message, tracer):
    # Receiver: extract trace context and create child span
    if message.trace_context:
        span = tracer.start_span(
            trace_id=message.trace_context.trace_id,
            parent_span_id=message.trace_context.parent_span_id,
            agent=self.name,
            action=f"handle_{message.type}"
        )
    else:
        # No trace context — start a new trace
        span = tracer.start_trace(agent=self.name, action=f"handle_{message.type}")
    return span
```

---

## AgentVersion

```
AgentVersion:
    agent_name: string            # "coder"
    version: string               # semver: "2.1.0"
    capabilities_hash: string     # hash of capabilities list
    protocol_version: string      # message format version: "1.0"
    changelog: string             # human-readable description of changes
```

### Semver Rules for Agents

| Change Type | Version Bump | Example |
|-------------|:------------:|---------|
| Breaking: different output format, removed capability | **Major** (1.x -> 2.0) | Coder switches from free-text diffs to structured patch format |
| New: added capability, new skill | **Minor** (2.0 -> 2.1) | Coder adds `write-tests` skill |
| Fix: bug fix, prompt tweak, same behavior | **Patch** (2.1.0 -> 2.1.1) | Coder fixes off-by-one in line numbers |

### Version in Agent Card (Ch 11 extension)

The `AgentCard` from Ch 11 now includes version information:

```
AgentCard:               # from Ch 11, extended
    name: string
    capabilities: list[string]
    skills: list[string]
    version: AgentVersion        # NEW
```

---

## Compatibility Check

```
CompatibilityResult: "compatible" | "degraded" | "incompatible"

check_compatible(agent_a: AgentVersion, agent_b: AgentVersion) -> CompatibilityResult:
    # Protocol must match for any communication
    if agent_a.protocol_version != agent_b.protocol_version:
        major_a = parse_major(agent_a.protocol_version)
        major_b = parse_major(agent_b.protocol_version)
        if major_a != major_b:
            return "incompatible"    # different protocol major versions can't talk
        return "degraded"            # same major, different minor — some features missing

    # Same protocol — check agent version compatibility
    major_a = parse_major(agent_a.version)
    major_b = parse_major(agent_b.version)

    if major_a != major_b:
        return "degraded"            # different major agent versions — breaking changes exist

    return "compatible"              # same protocol, same major — fully compatible
```

### Compatibility Matrix

| Protocol Match | Agent Major Match | Result |
|:-:|:-:|:-:|
| Same major+minor | Same major | **compatible** |
| Same major, diff minor | Same major | **degraded** |
| Same major, any | Different major | **degraded** |
| Different major | Any | **incompatible** |

---

## Mixed-Version Protocol Negotiation

```
NegotiatedProtocol:
    protocol_version: string              # lowest common protocol version
    available_capabilities: list[string]   # intersection of all agents' capabilities
    degraded_features: list[string]        # features unavailable due to version mismatch

negotiate_protocol(agents: list[AgentVersion]) -> NegotiatedProtocol:
    protocol_versions = [a.protocol_version for a in agents]
    min_protocol = min(protocol_versions)  # use lowest common version

    capabilities = intersection(
        [a.capabilities for a in agents]   # only capabilities ALL agents share
    )

    degraded_features = []
    for agent in agents:
        for cap in agent.capabilities:
            if cap not in capabilities:
                degraded_features.append(f"{agent.agent_name}: {cap} (not available)")

    return NegotiatedProtocol(
        protocol_version=min_protocol,
        available_capabilities=capabilities,
        degraded_features=degraded_features
    )
```

### Rainbow Deployment

```
RainbowDeployment:
    agent_name: string
    old_version: AgentVersion
    new_version: AgentVersion
    traffic_split: float              # 0.0 to 1.0 — fraction going to new version

    route_task(task) -> AgentVersion:
        if random() < traffic_split:
            return new_version
        return old_version

    check_health() -> "advance" | "hold" | "rollback":
        if metrics.new_error_rate > metrics.old_error_rate * 1.5:
            return "rollback"
        if metrics.new_error_rate <= metrics.old_error_rate:
            return "advance"
        return "hold"
```

---

## IdempotencyKey and IdempotencyStore

```
IdempotencyKey:
    key: string
    # Format: "{source_agent}:{task_id}:{action}:{sequence}"
    # Example: "coder:task-088:code_ready:1"

IdempotencyStore:
    check(key: string) -> AlreadyDone(result) | Proceed
        # Check if this operation has already been completed
        if store.has(key):
            return AlreadyDone(result=store.get(key))
        return Proceed

    record(key: string, result: any)
        # Record result so future duplicates can be skipped
        store.set(key, result, ttl=3600)  # expire after 1 hour
```

### Wiring Into Message Flow

```
# Sender side
send_with_idempotency(messenger, target, message, idempotency_store):
    key = f"{self.name}:{message.task_id}:{message.type}:{message.sequence}"
    message.idempotency_key = key
    messenger.send(target, message)

# Receiver side
handle_with_idempotency(message, idempotency_store, handler):
    if message.idempotency_key:
        result = idempotency_store.check(message.idempotency_key)
        if result is AlreadyDone:
            log(f"Duplicate detected: {message.idempotency_key}. Returning cached result.")
            return result.result

    # Not a duplicate — process normally
    result = handler(message)

    # Record the result for future deduplication
    if message.idempotency_key:
        idempotency_store.record(message.idempotency_key, result)

    return result
```

### Saga Integration for Compensating Transactions

Idempotency keys integrate with the saga pattern from Ch 12. When a saga step is retried, the idempotency key prevents already-completed steps from re-executing:

```
saga_step_with_idempotency(step, saga_id, idempotency_store):
    key = f"{saga_id}:{step.name}:{step.attempt}"

    result = idempotency_store.check(key)
    if result is AlreadyDone:
        log(f"Saga step {step.name} already completed. Skipping.")
        return result.result

    result = execute(step)
    idempotency_store.record(key, result)
    return result
```

---

## CircuitBreaker

```
CircuitBreaker:
    state: "closed" | "open" | "half-open"
    failure_count: int
    threshold: int = 3
    cooldown: duration = 30s

    call(agent, request) -> result:
        if state == "open":
            if time_since_opened > cooldown:
                state = "half-open"
            else:
                raise CircuitOpen("Agent {agent} circuit is open. Try again later.")

        try:
            result = agent.process(request)
            if state == "half-open":
                state = "closed"
                failure_count = 0
            return result
        catch error:
            failure_count += 1
            if failure_count >= threshold:
                state = "open"
            raise
```

---

## HealthReport

```
HealthReport:
    agent_name: string
    status: "healthy" | "degraded" | "unhealthy"
    queue_depth: int
    last_task_completed: datetime
    uptime: duration
    checkpoint_age: duration       # time since last checkpoint
    version: AgentVersion
```

---

## Structured Logging

```
LogEntry:
    timestamp: datetime
    agent: string
    trace_id: string | null
    span_id: string | null
    level: "debug" | "info" | "warn" | "error"
    message: string
    metadata: dict
```

---

## Test Task

```
Task: End-to-end production architecture on the todo-api codebase.

Phase 1 — Checkpoint save:
  Coder processes a 5-step task. Checkpoints saved after each step.
  Output shows checkpoint IDs and step indices.

Phase 2 — Crash and resume:
  Coder crashes at step 4. Restarts. Restores checkpoint from step 3.
  Resumes from step 4. Completes task. 0 steps lost.

Phase 3 — Distributed trace:
  Full task with 4 agents. Trace waterfall shows all spans.
  Parent-child relationships visible. Timing breakdown per agent.

Phase 4 — Version compatibility:
  Check 3 agent pairs:
    coder v2.1.0 + reviewer v1.3.2 (protocol 1.0) → degraded
    coder v2.1.0 + runner v2.0.0 (protocol 1.0) → compatible
    coder v2.1.0 (protocol 2.0) + reviewer v1.3.2 (protocol 1.0) → incompatible

Phase 5 — Mixed-version swarm:
  4 agents at different versions. Protocol negotiation.
  Degraded features listed. Task completes successfully.

Phase 6 — Idempotent retry:
  Coder sends code_ready. Reviewer processes it. Network blip.
  Coder retries with same idempotency key. Reviewer returns cached result.
  One review, one result.
```

---

## What This Chapter Does NOT Include

- **No external agent federation** — connecting to agents outside the swarm is Ch 15
- **No MCP marketplace** — discovering and connecting to external MCP servers is Ch 15
- **No governance** — maturity gates and trust levels for external agents is Ch 15
- **No distributed checkpoint storage** — each agent owns its own checkpoints locally
