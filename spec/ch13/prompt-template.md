# Chapter 13 — Swarm Patterns

## Scope

Build the orchestrator-workers pattern first — centralized task decomposition and dispatch — then watch it break. Replace it with emergent coordination patterns where agents self-organize around tasks. Seven patterns total: orchestrator-workers, fan-out/fan-in, review chains, consensus, conflict resolution, backpressure, and collective learning.

## Learning Objectives

- Build the orchestrator-workers pattern — decompose, dispatch, collect, synthesize
- Understand why orchestrators become bottlenecks, single points of failure, and ceilings
- Replace orchestrator-driven coordination with event-driven self-organization
- Implement fan-out/fan-in — parallel work distribution and merged result collection
- Build review chains — sequential pipelines that emerge from agent routing decisions
- Implement consensus — weighted voting where domain expertise determines vote weight
- Handle conflict resolution — evidence-based resolution when agents contradict each other
- Build backpressure — agents signal capacity limits and requesters adapt
- Enable collective learning — skill improvements propagate across the swarm with verification

## What You Build

1. **Orchestrator-workers** — an `Orchestrator` agent that receives a task, uses `decompose()` to break it into `TaskDispatch` steps, dispatches each to the right worker via `select_agent()`, collects results, and calls `synthesize()` to produce an `OrchestratorResult`. Then you watch it break: new agents require orchestrator changes, all messages bottleneck through the center, and a crash mid-task loses all progress.

2. **SwarmEvent** — the event contract that replaces direct agent-to-agent instructions. Events flow through the broadcast bus (Ch 11). Agents subscribe to event types and decide independently whether to act.

3. **Fan-out/fan-in** — one event goes to multiple agents in parallel. A `FanOutCollector` tracks expected responses, handles deadlines, and merges results. Partial results when agents timeout.

4. **Review chains** — sequential pipelines where each agent makes a `RouteDecision`: pass forward, push back, escalate, or done. The chain emerges from individual decisions, not predefined flow.

5. **Consensus** — weighted voting on decisions. `VoterConfig` assigns weights per decision type (security decisions weight the security expert, architecture decisions weight the reviewer). `ConsensusResult` includes the winning option, margin, and dissent.

6. **Conflict resolution** — when agents contradict each other on facts. Three strategies: request evidence, defer to domain expert, escalate to human. `ConflictResolution` tracks strategy, evidence, and who decided.

7. **Backpressure** — overwhelmed agents publish `BackpressureSignal` with queue depth, capacity, estimated wait, and action (reject/delay/redirect). Requesters adapt.

8. **Collective learning** — skill improvements from Ch 9 propagate via `skill_improved` events on the broadcast bus. Receiving agents verify before adopting (Ch 9's `verify_improvement`). The swarm's knowledge is the union of all agents' improvements.

## Key Interfaces

```
Orchestrator:
    agents: dict[string, AgentCard]
    messenger: PeerMessenger

    decompose(task: string) -> list[TaskDispatch]
    select_agent(step: TaskDispatch) -> string
    process(task: string) -> OrchestratorResult
    synthesize(results: list) -> any

TaskDispatch:
    step: string
    assigned_to: string
    correlation_id: string
    status: enum("pending", "in_progress", "complete", "failed")

OrchestratorResult:
    task: string
    dispatches: list[TaskDispatch]
    final_output: any
    total_time: float

SwarmEvent:
    id: string (uuid)
    type: string                    # "code_ready", "review_complete", etc.
    source: string                  # agent that published
    correlation_id: string          # links to original task
    payload: dict                   # the content
    timestamp: datetime
    requires_response: bool         # does publisher expect replies?
    response_deadline: datetime | null

FanOutCollector:
    correlation_id: string
    expected_responses: string[]    # which agents should respond
    received: dict                  # agent_name → response
    deadline: datetime

    submit(agent_name, response) → void
    is_complete() → bool            # all expected responses received
    is_expired() → bool             # deadline passed
    merge() → MergedResult          # combine all responses

RouteDecision:
    action: enum("pass_forward", "push_back", "escalate", "done")
    target: string | null           # which agent or event type
    reason: string                  # why this decision
    payload: dict                   # the work product

ConsensusRequest:
    decision: string                # what's being decided
    options: string[]               # the choices
    voters: VoterConfig[]           # who votes and with what weight

VoterConfig:
    agent: string
    weight: float                   # expertise weight for THIS decision
    required: bool                  # must this agent vote?

ConsensusResult:
    chosen: string                  # winning option
    votes: Vote[]                   # all votes cast
    margin: float                   # winning margin
    unanimous: bool

ConflictResolution:
    strategy: enum("request_evidence", "defer_to_expert", "escalate")
    conflict: Conflict
    resolution: string
    evidence: dict | null
    decided_by: string              # which agent or "human"

BackpressureSignal:
    source: string                  # who's overwhelmed
    queue_depth: int                # how backed up
    capacity: int                   # max queue size
    estimated_wait: float           # seconds until capacity frees up
    action: enum("reject", "delay", "redirect")
```

## Success Criteria

- Orchestrator decomposes a task into ordered TaskDispatch steps
- Orchestrator dispatches each step to the correct agent via select_agent()
- Orchestrator collects all results and synthesizes a final OrchestratorResult
- Orchestrator breaks when a new agent is added (requires orchestrator modification)
- Orchestrator is a bottleneck: all messages flow through the center (star topology)
- Orchestrator crash mid-task loses in-progress work (single point of failure)
- Fan-out sends one event to multiple agents and collects results in parallel
- Fan-in merges partial results when agents timeout (with warnings)
- Fan-out wall-clock time equals the slowest agent, not the sum
- Review chains route work based on agent decisions, not predefined flow
- Adding a new agent to the chain requires no changes to existing agents
- Consensus weighted tally correctly reflects domain expertise weights
- Required voters block consensus if they don't vote
- Conflict resolution requests evidence before deciding
- Evidence-based resolution produces a concrete diagnosis
- Backpressure signals prevent queue overflow
- Requesters adapt to backpressure (wait, retry, or redirect)
- Skill improvements propagate via broadcast bus
- Receiving agents verify before adopting shared skills
- Agents reject shared skills that degrade their performance

## Concepts Introduced

- Orchestrator-workers pattern (centralized decompose/dispatch/collect/synthesize)
- Orchestrator limitations (bottleneck, single point of failure, rigid routing)
- Event-driven coordination (events replace instructions)
- Fan-out/fan-in (parallel distribution + merged results)
- Review chains (emergent sequential pipelines)
- Consensus and weighted voting
- Conflict resolution strategies (evidence, expert, escalation)
- Backpressure and graceful degradation
- Collective learning (swarm-level self-improvement)

## Thread: Self-Improvement (Collective)

Self-improvement becomes collective here:
- **Ch 9:** Individual agent improves itself (mistake journal, skill rewriting, verification)
- **Ch 11:** Agents share skills and capabilities via broadcast
- **Ch 13 (here):** The swarm gets smarter as a whole — one agent's improvement propagates, others verify and adopt, improvements bounce between agents

## CLI Interface

```
# Run with swarm mode
tbh-code --swarm --task "Add a DELETE /tasks/:id endpoint to todo-api"

# Same codebase, swarm coordination is automatic
```

## Upgrade from Ch 12

| Capability | Ch 12 | Ch 13 |
|-----------|-------|-------|
| Agent identity + discovery | Yes | Yes |
| Broadcast bus | Yes | Yes (+ event subscriptions) |
| Direct messaging | Yes | Yes (+ routing decisions) |
| Orchestrator-workers | No | Yes — then replaced by emergent patterns |
| Fan-out/fan-in | No | Yes — parallel work + merged results |
| Review chains | No | Yes — emergent sequential pipelines |
| Consensus voting | No | Yes — weighted domain expertise |
| Conflict resolution | No | Yes — evidence-based resolution |
| Backpressure | No | Yes — capacity signals + graceful degradation |
| Collective learning | No | Yes — skill propagation + verification |
