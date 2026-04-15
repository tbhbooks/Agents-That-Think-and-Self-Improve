# Chapter 13 — Interface Spec

## Overview

Build the orchestrator-workers pattern first — centralized task decomposition and dispatch via `Orchestrator`, `TaskDispatch`, and `OrchestratorResult`. Then watch it break (bottleneck, single point of failure, rigid routing) and replace it with emergent self-organization. `SwarmEvent` is the event contract — agents publish and subscribe to events on the broadcast bus. `FanOutCollector` distributes work in parallel and merges results (with deadline-based partial merges). `RouteDecision` lets each agent decide whether to pass work forward, push it back, escalate, or mark done — forming review chains. `ConsensusRequest` + `VoterConfig` implement weighted voting where domain expertise determines vote weight. `ConflictResolution` resolves factual disagreements through evidence, expert deference, or escalation. `BackpressureSignal` lets overwhelmed agents signal capacity limits. Collective learning propagates skill improvements across the swarm with verification before adoption.

Operates on the `todo-api` codebase (see `../todo-api/`).

---

## Orchestrator

```
Orchestrator:
    agents: dict[string, AgentCard]   # from peer registry (Ch 11)
    messenger: PeerMessenger          # from Ch 12

    decompose(task: string) -> list[TaskDispatch]
        # Use LLM to break task into ordered steps
        # Each step maps to an agent capability
        # Returns a plan: list of TaskDispatch with status "pending"

    select_agent(step: TaskDispatch) -> string
        # Match step requirements to agent capabilities from registry
        # Returns agent name
        # Raises NoAgentFoundError if no match

    process(task: string) -> OrchestratorResult
        # Main entry point:
        #   1. decompose(task) -> list of steps
        #   2. For each step: select_agent, dispatch via messenger, collect result
        #   3. synthesize(results) -> final output
        # Returns OrchestratorResult with all dispatches and timing

    synthesize(results: list) -> any
        # Combine all step results into a coherent final output
        # Includes: code status, review verdict, test results, etc.

TaskDispatch:
    step: string                    # description of the subtask
    assigned_to: string             # agent name
    correlation_id: string          # links to original task
    status: enum("pending", "in_progress", "complete", "failed")

OrchestratorResult:
    task: string                    # original task description
    dispatches: list[TaskDispatch]  # all steps with their outcomes
    final_output: any               # synthesized result
    total_time: float               # wall-clock seconds
```

### Orchestrator Flow

```
1. User submits task to Orchestrator
2. Orchestrator calls decompose(task) → list of TaskDispatch (all "pending")
3. For each step sequentially:
   a. select_agent(step) → agent name
   b. messenger.request(agent, action, payload, correlation_id)
   c. Update step status: "in_progress" → "complete" (or "failed")
4. synthesize(all results) → final output
5. Return OrchestratorResult
```

### Orchestrator Limitations

The orchestrator works for simple, predictable workflows but hits three ceilings:

| Limitation | What happens | Why it's structural |
|-----------|-------------|-------------------|
| **Rigid routing** | New agent added → orchestrator must be updated | decompose() and select_agent() encode agent knowledge; new agents don't automatically participate |
| **Bottleneck** | All messages flow through the center (star topology) | Runner can't get Reviewer's findings directly — everything relays through orchestrator |
| **Single point of failure** | Orchestrator crashes mid-task → all progress lost | Only the orchestrator knows the plan state; no agent can resume independently |

These limitations motivate the shift to event-driven coordination in the rest of the chapter.

---

## SwarmEvent

```
SwarmEvent:
    id: string (uuid)               # unique event identifier
    type: string                    # "code_ready", "review_complete", "tests_complete",
                                    # "audit_complete", "backpressure", "skill_improved"
    source: string                  # agent name that published
    correlation_id: string          # links related events to original task (from Ch 12)
    payload: dict                   # the actual content (varies by event type)
    timestamp: datetime             # when the event was published

    # Coordination metadata
    requires_response: bool         # does the publisher expect replies?
    response_deadline: datetime | null  # when replies are due (null = no deadline)
```

### Event Flow

```
# Every agent's main loop:
function on_event(event: SwarmEvent):
    if event.type not in my_subscriptions:
        return  # ignore events I don't care about

    if not within_budget():
        publish(BackpressureSignal(reason="at capacity"))
        return  # can't take more work

    result = process(event)
    publish(SwarmEvent(
        type=result_type,
        source=self.name,
        correlation_id=event.correlation_id,
        payload=result
    ))
```

### Event Types

| Event Type | Published By | Subscribed By | Payload |
|-----------|-------------|---------------|---------|
| `code_ready` | Coder | Reviewer, Runner, Security Auditor | files_changed, diff |
| `review_complete` | Reviewer | Coder, Fan-In Collector | approved, issues, severity |
| `tests_complete` | Runner | Coder, Fan-In Collector | passed, failed, failures |
| `audit_complete` | Security Auditor | Coder, Fan-In Collector | vulnerabilities |
| `backpressure` | Any agent | Requester | queue_depth, capacity, action |
| `skill_improved` | Any agent | All agents | skill, version, change |

---

## FanOutCollector

```
FanOutCollector:
    correlation_id: string          # which task this collector tracks
    expected_responses: string[]    # agent names that should respond
    received: dict                  # agent_name → response payload
    deadline: datetime              # when to stop waiting

    submit(agent_name: string, response: dict) → void
        # Record a response from an agent
        # Precondition: agent_name is in expected_responses
        # Postcondition: received[agent_name] = response
        assert agent_name in expected_responses
        received[agent_name] = response

    is_complete() → bool
        # All expected agents have responded
        return len(received) == len(expected_responses)

    is_expired() → bool
        # Deadline has passed
        return now() > deadline

    merge() → MergedResult
        # Combine all received responses into a single result
        # If some agents haven't responded, include warnings
        missing = [a for a in expected_responses if a not in received]
        return MergedResult(
            responses=received,
            missing=missing,
            warnings=[f"{a} did not respond within deadline" for a in missing],
            complete=len(missing) == 0
        )

MergedResult:
    responses: dict                 # agent_name → response payload
    missing: string[]               # agents that didn't respond
    warnings: string[]              # human-readable warnings
    complete: bool                  # true if all agents responded
```

### Fan-Out Flow

```
1. Coder publishes code_ready event with requires_response=true and response_deadline
2. Broadcast bus delivers event to all subscribers (Reviewer, Runner, Security Auditor)
3. FanOutCollector is created with expected_responses = list of subscribers
4. Each subscriber processes in parallel and publishes a result event
5. FanOutCollector.submit() is called for each response
6. When is_complete() or is_expired():
   - merge() combines all received responses
   - Publishes merged feedback to Coder
7. Partial results (missing agents) include warnings
```

### Example: Fan-Out Timing

```
Sequential:  Reviewer(12.3s) + Runner(18.7s) + Security(15.1s) = 46.1s
Fan-out:     max(12.3s, 18.7s, 15.1s) = 18.7s  (60% faster)
```

---

## RouteDecision

```
RouteDecision:
    action: enum("pass_forward", "push_back", "escalate", "done")
    target: string | null           # which agent or event type to route to
    reason: string                  # why this routing decision was made
    payload: dict                   # the work product being routed

# Actions:
#   pass_forward — work is good, send to next agent in chain
#   push_back   — work has issues, send back to source for revision
#   escalate    — can't decide, escalate to human or higher authority
#   done        — work is complete, no further routing needed
```

### Review Chain Decision Logic

```
function decide_route(event: SwarmEvent, my_result: dict) → RouteDecision:
    # Reviewer logic:
    if my_result.issues.count > 0 and any_critical(my_result.issues):
        return RouteDecision(
            action="push_back",
            target=event.source,
            reason="Critical issues found — fix before testing",
            payload=my_result
        )
    else:
        return RouteDecision(
            action="pass_forward",
            target="runner",
            reason="Code approved — ready for testing",
            payload=my_result
        )

    # Runner logic:
    if my_result.failed > 0:
        return RouteDecision(
            action="push_back",
            target=event.source,
            reason=f"{my_result.failed} tests failed — fix and resubmit",
            payload=my_result
        )
    else:
        return RouteDecision(
            action="done",
            target=event.source,
            reason="All tests passed",
            payload=my_result
        )
```

### Emergent Chains

```
Adding a new agent to the chain:
1. Security Auditor subscribes to review_approved events
2. Security Auditor inserts itself between Reviewer and Runner
3. Chain becomes: Coder → Reviewer → Security Auditor → Runner → Coder
4. No existing agent was modified
```

---

## ConsensusRequest

```
ConsensusRequest:
    decision: string                # what's being decided
    options: string[]               # the choices available
    voters: VoterConfig[]           # who votes and with what weight
```

---

## VoterConfig

```
VoterConfig:
    agent: string                   # agent name
    weight: float                   # expertise weight for THIS decision type
    required: bool                  # must this agent vote for consensus to be valid?
```

### Weight Profiles by Decision Type

```
# Security decision — security auditor's vote weighs most
security_weights = {
    "security-auditor": 3.0,
    "reviewer": 1.0,
    "runner": 1.0,
    "coder": 0.5
}

# Architecture decision — reviewer's vote weighs most
architecture_weights = {
    "reviewer": 3.0,
    "coder": 2.0,
    "security-auditor": 1.0,
    "runner": 0.5
}

# Correctness decision — runner's vote weighs most
correctness_weights = {
    "runner": 3.0,
    "reviewer": 2.0,
    "coder": 1.0,
    "security-auditor": 0.5
}
```

---

## ConsensusResult

```
ConsensusResult:
    chosen: string                  # winning option
    votes: Vote[]                   # all votes cast
    margin: float                   # difference between winner and runner-up
    unanimous: bool                 # did all voters agree?

Vote:
    agent: string                   # who voted
    choice: string                  # what they chose
    weight: float                   # their weight for this decision
    reasoning: string               # why they chose this option
```

### Consensus Algorithm

```
function run_consensus(decision, options, voters, deadline) → ConsensusResult:
    votes = []
    for voter in voters:
        request = ConsensusRequest(decision, options)
        response = send_and_wait(voter.agent, request, deadline)
        if response:
            votes.append(Vote(
                agent=voter.agent,
                choice=response.choice,
                weight=voter.weight,
                reasoning=response.reasoning
            ))
        elif voter.required:
            # Required voter didn't respond — consensus fails
            raise ConsensusError(f"Required voter {voter.agent} did not respond")

    # Tally weighted votes
    tallies = {}
    for vote in votes:
        tallies[vote.choice] = tallies.get(vote.choice, 0) + vote.weight

    chosen = max(tallies, key=tallies.get)
    runner_up = sorted(tallies.values(), reverse=True)
    margin = runner_up[0] - runner_up[1] if len(runner_up) > 1 else runner_up[0]
    unanimous = len(set(v.choice for v in votes)) == 1

    return ConsensusResult(chosen, votes, margin, unanimous)
```

---

## ConflictResolution

```
ConflictResolution:
    strategy: enum("request_evidence", "defer_to_expert", "escalate")
    conflict: Conflict              # the disagreement
    resolution: string              # what was decided
    evidence: dict | null           # supporting evidence (if strategy is request_evidence)
    decided_by: string              # which agent made the call, or "human"

Conflict:
    claims: dict                    # agent_name → their claim
    type: string                    # "security", "correctness", "code_quality", "design"
    correlation_id: string          # which task this relates to
```

### Resolution Strategies

```
function resolve_conflict(conflict: Conflict) → ConflictResolution:
    # Strategy 1: Request evidence (default for empirical disputes)
    if conflict.type in ["correctness", "test_results"]:
        evidence = {}
        for agent, claim in conflict.claims.items():
            evidence[agent] = request_evidence(agent, claim)
        resolution = evaluate_evidence(evidence)
        return ConflictResolution(
            strategy="request_evidence",
            conflict=conflict,
            resolution=resolution,
            evidence=evidence,
            decided_by="evidence"
        )

    # Strategy 2: Defer to domain expert
    elif conflict.type in ["security", "code_quality"]:
        expert = domain_expert_for(conflict.type)
        resolution = defer_to(expert, conflict)
        return ConflictResolution(
            strategy="defer_to_expert",
            conflict=conflict,
            resolution=resolution,
            evidence=null,
            decided_by=expert
        )

    # Strategy 3: Escalate to human
    else:
        return ConflictResolution(
            strategy="escalate",
            conflict=conflict,
            resolution="awaiting human input",
            evidence=null,
            decided_by="human"
        )
```

### Domain Expert Mapping

```
conflict_type → expert:
    "security"      → "security-auditor"
    "code_quality"  → "reviewer"
    "test_results"  → "runner"
    "design"        → escalate to human (subjective)
```

---

## BackpressureSignal

```
BackpressureSignal:
    source: string                  # who's overwhelmed
    queue_depth: int                # current items in queue
    capacity: int                   # maximum queue size
    estimated_wait: float           # seconds until capacity frees up
    action: enum("reject", "delay", "redirect")

# Actions:
#   reject   — refuses the work (requester should retry after estimated_wait)
#   delay    — accepts but queues (requester should expect delayed response)
#   redirect — suggests another agent (requester should reroute)
```

### Backpressure Flow

```
function handle_incoming(event: SwarmEvent):
    if queue.size >= max_queue_size:
        publish(SwarmEvent(
            type="backpressure",
            source=self.name,
            payload=BackpressureSignal(
                source=self.name,
                queue_depth=queue.size,
                capacity=max_queue_size,
                estimated_wait=avg_processing_time * queue.size,
                action="reject"
            )
        ))
        return  # don't accept the work

    queue.add(event)
    process_next()
```

### Requester Reaction

| Signal | Agent does | Requester does |
|--------|-----------|----------------|
| `reject` | Refuses the work | Wait and retry after `estimated_wait` |
| `delay` | Accepts but queues | Proceed, expect delayed response |
| `redirect` | Suggests another agent | Send to the suggested agent |

---

## Collective Learning

### Skill Propagation

```
# When an agent improves a skill (Ch 9 skill rewriting):
function on_skill_refined(skill: SkillSpec):
    publish(SwarmEvent(
        type="skill_improved",
        source=self.name,
        payload={
            "skill": skill.name,
            "version": skill.version,
            "change": skill.refinement_reason,
            "spec": skill.to_spec_format()
        }
    ))
```

### Adoption Decision

```
function on_skill_improved(event: SwarmEvent):
    new_skill = event.payload.skill
    my_version = get_skill(new_skill.name)

    if my_version is null:
        # I don't have this skill — is it relevant to my role?
        if is_relevant(new_skill, my_capabilities):
            adopt(new_skill)
            log("Adopted new skill: " + new_skill.name)
        return

    if new_skill.version <= my_version.version:
        return  # I already have this version or newer

    # I have an older version — verify improvement before adopting
    result = verify_improvement(
        task_type=new_skill.name,
        before=my_version,
        after=new_skill
    )

    if result.recommendation == "keep":
        adopt(new_skill)
        log("Upgraded " + new_skill.name + " to v" + new_skill.version)
    else:
        log("Rejected " + new_skill.name + " v" + new_skill.version +
            " — degraded " + result.degraded_criteria)
```

### Collective Learning Properties

- No single agent invents the final skill version
- Improvements bounce between agents (SA creates v2, Reviewer improves to v3)
- Agents verify before adopting — self-improvement verification (Ch 9) protects against regression
- Agents reject shared skills that degrade their own performance
- Positive signals matter — agents note when collective skills work well together

---

## Seven Swarm Patterns Summary

| Pattern | What | When | Interface |
|---------|------|------|-----------|
| Orchestrator-workers | Centralized decompose/dispatch/collect/synthesize | Simple predictable workflows (then outgrown) | Orchestrator, TaskDispatch, OrchestratorResult |
| Fan-out/fan-in | Parallel distribution + merged results | Multiple agents can process independently | FanOutCollector |
| Review chains | Emergent sequential pipelines | Work needs sequential stages | RouteDecision |
| Consensus | Weighted voting on decisions | Priority conflict between agents | ConsensusRequest + ConsensusResult |
| Conflict resolution | Evidence-based factual dispute resolution | Agents contradict each other | ConflictResolution |
| Backpressure | Capacity signals + graceful degradation | Agent overwhelmed | BackpressureSignal |
| Collective learning | Shared improvement across swarm | Agent rewrites a skill | skill_improved event + verify_improvement |

---

## Test Task

```
Task: End-to-end swarm coordination on the todo-api codebase.

Phase 1 — Fan-out/fan-in:
  Coder publishes code_ready. Reviewer, Runner, Security Auditor process in parallel.
  FanOutCollector merges results. Wall-clock time < sum of individual times.

Phase 2 — Review chain:
  Reviewer pushes back (critical issue). Coder fixes. Reviewer passes forward.
  Runner runs tests. All pass. Done.

Phase 3 — Consensus:
  Security Auditor and Reviewer disagree on priority. Consensus vote with security weights.
  Security Auditor's higher weight wins.

Phase 4 — Conflict resolution:
  Reviewer says "no ownership check." Runner says "tests pass."
  Strategy: request evidence. Both provide evidence. Resolution: test was incomplete.

Phase 5 — Backpressure:
  Runner at capacity (3/3 queue). Rejects task-005. Coder waits and retries.

Phase 6 — Collective learning:
  Security Auditor rewrites security-scan v1 → v2. Publishes skill_improved.
  Reviewer adopts v2. Reviewer improves to v3. Security Auditor adopts v3.
```

---

## What This Chapter Does NOT Include

- **Orchestrator is built then outgrown** — orchestrator-workers is introduced first, then replaced by emergent event-driven patterns
- **No static pipeline definitions** — review chains are dynamic, not hardcoded
- **No crash recovery** — what happens when an agent dies mid-task is Ch 14
- **No distributed tracing** — following a task across agents is Ch 14
- **No version management** — upgrading agents without breaking the swarm is Ch 14
- **No external agent federation** — connecting to agents outside the swarm is Ch 15
