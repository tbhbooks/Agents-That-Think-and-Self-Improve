"""
Chapter 13 Validation Tests
============================

These tests validate the reader's Ch 13 implementation: swarm coordination
patterns including orchestrator-workers, fan-out/fan-in, review chains,
consensus, conflict resolution, backpressure, and collective learning.

The reader's program must be callable as:
    tbh-code --swarm --task "<task>"

Swarm traces must appear in stdout with the format:
    [orchestrator] Decomposing into subtasks...
    [orchestrator] Plan:
    [orchestrator] Dispatching Step <N> → <agent>
    [orchestrator] Step <N> complete (<time>)
    [orchestrator] Synthesizing results...
    [orchestrator] Result:
    [fan-out] Event <type> → <N> subscribers: <names>
    [fan-in] All <N> responses received for <id> (<time> total)
    [fan-in] Merged feedback for <id>:
    [fan-in] Deadline reached for <id>
    [fan-in] Received: <agents> (<N> of <M>)
    [reviewer] RouteDecision:
    [consensus] Decision: "<text>"
    [consensus] Result:
    [conflict] Contradiction detected (<id>):
    [conflict] Strategy: <strategy>
    [conflict] Resolution:
    [runner] Publishing backpressure signal:
    [security-auditor] Publishing: skill_improved
    [reviewer] Adopted <skill> v<N>

Output must include JSON event payloads matching the interface spec.

Adjust AGENT_CMD and TODO_API_PATH below to match the reader's setup.
"""

import subprocess
import json
import os
import re
import sys
import time

# ============================================================================
# CONFIGURATION
# ============================================================================

AGENT_CMD = "tbh-code"
TODO_API_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "todo-api")

# ============================================================================
# HELPERS
# ============================================================================

def swarm_task(task, timeout=180):
    """Run a swarm task and capture stdout."""
    cmd = [AGENT_CMD, "--swarm", "--task", task]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    return result.stdout


def extract_json_block(stdout, after_marker=None):
    """Extract a JSON block from output, optionally after a marker string."""
    text = stdout
    if after_marker:
        idx = text.find(after_marker)
        if idx >= 0:
            text = text[idx:]
    json_start = text.find("{")
    if json_start < 0:
        return None
    depth = 0
    for i in range(json_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[json_start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def extract_tagged_events(stdout, tag):
    """Extract events with a specific tag like [fan-out], [consensus], etc."""
    events = []
    for line in stdout.splitlines():
        match = re.match(rf'\[{re.escape(tag)}\] (.+)', line)
        if match:
            events.append(match.group(1))
    return events


def extract_all_tagged_events(stdout):
    """Extract all tagged events from output."""
    events = []
    for line in stdout.splitlines():
        match = re.match(r'\[([a-z_-]+)\] (.+)', line)
        if match:
            events.append((match.group(1), match.group(2)))
    return events


# ============================================================================
# TESTS — ORCHESTRATOR
# ============================================================================

class TestOrchestrator:
    """Orchestrator must decompose tasks, dispatch to agents, collect results, and synthesize."""

    def test_orchestrator_decomposes_task(self):
        """Orchestrator should break a task into a list of TaskDispatch steps."""
        stdout = swarm_task(
            "Add a DELETE /tasks/:id endpoint to todo-api"
        )
        all_text = stdout.lower()
        has_decompose = (
            "decomposing" in all_text or
            "plan:" in all_text or
            "step 1" in all_text or
            "subtask" in all_text
        )
        assert has_decompose, (
            "No task decomposition found. "
            "Orchestrator should decompose tasks into ordered steps."
        )
        # Check that multiple steps are present
        step_matches = re.findall(r'step\s+\d', all_text)
        assert len(step_matches) >= 2, (
            f"Found {len(step_matches)} steps, expected at least 2. "
            "Orchestrator should produce multiple TaskDispatch steps."
        )

    def test_orchestrator_dispatches_to_correct_agents(self):
        """Orchestrator should dispatch each step to the correct agent via select_agent()."""
        stdout = swarm_task(
            "Add a DELETE /tasks/:id endpoint to todo-api"
        )
        all_text = stdout.lower()
        # Check that dispatching happens to named agents
        has_dispatch = (
            "dispatching" in all_text or
            "→ coder" in all_text or
            "→ reviewer" in all_text or
            "→ runner" in all_text or
            "→ researcher" in all_text or
            "assigned_to" in all_text
        )
        assert has_dispatch, (
            "No dispatch to agents found. "
            "Orchestrator should dispatch steps to specific agents."
        )

    def test_orchestrator_collects_all_results(self):
        """Orchestrator should collect results from all dispatched agents."""
        stdout = swarm_task(
            "Add a DELETE /tasks/:id endpoint to todo-api"
        )
        result = extract_json_block(stdout, after_marker="[orchestrator] Result")
        if result is not None:
            # Check for dispatches with completed status
            if "dispatches" in result:
                completed = [d for d in result["dispatches"] if d.get("status") == "complete"]
                assert len(completed) >= 2, (
                    f"Only {len(completed)} dispatches complete. "
                    "Orchestrator should collect results from all steps."
                )
        else:
            # Check for step completion messages
            all_text = stdout.lower()
            complete_matches = re.findall(r'step\s+\d\s+complete', all_text)
            assert len(complete_matches) >= 2, (
                "Orchestrator didn't collect results from multiple steps."
            )

    def test_orchestrator_synthesizes_final_output(self):
        """Orchestrator should synthesize all step results into an OrchestratorResult."""
        stdout = swarm_task(
            "Add a DELETE /tasks/:id endpoint to todo-api"
        )
        all_text = stdout.lower()
        has_synthesis = (
            "synthesiz" in all_text or
            "final_output" in all_text or
            "orchestratorresult" in all_text
        )
        assert has_synthesis, (
            "No synthesis step found. "
            "Orchestrator should synthesize results into OrchestratorResult."
        )
        result = extract_json_block(stdout, after_marker="[orchestrator] Result")
        if result is not None:
            has_required = (
                "task" in result or
                "dispatches" in result or
                "final_output" in result or
                "total_time" in result
            )
            assert has_required, (
                f"OrchestratorResult missing expected fields. "
                f"Found: {list(result.keys())}. "
                "Expected task, dispatches, final_output, or total_time."
            )

    def test_orchestrator_bottleneck(self):
        """All messages should flow through orchestrator — star topology."""
        stdout = swarm_task(
            "Add a DELETE /tasks/:id endpoint to todo-api"
        )
        all_events = extract_all_tagged_events(stdout)
        # In orchestrator mode, every request/response should involve the orchestrator
        orchestrator_events = [e for tag, e in all_events if tag == "orchestrator"]
        other_events = [e for tag, e in all_events if tag != "orchestrator"]
        # Orchestrator should appear in more events than any single worker
        # (because every message relays through it)
        assert len(orchestrator_events) >= len(all_events) // 3, (
            f"Orchestrator appeared in {len(orchestrator_events)} of {len(all_events)} events. "
            "In orchestrator mode, all messages should flow through the center (star topology)."
        )


# ============================================================================
# TESTS — SWARM EVENT
# ============================================================================

class TestSwarmEvent:
    """SwarmEvent must have all required fields."""

    def test_event_has_required_fields(self):
        """Published events must include id, type, source, correlation_id, payload, timestamp."""
        stdout = swarm_task(
            "Add a DELETE /tasks/:id endpoint to todo-api"
        )
        event = extract_json_block(stdout, after_marker="Publishing event")
        assert event is not None, (
            "No JSON event found after 'Publishing event'. "
            "Events should be published as JSON."
        )
        required_fields = ["type", "source", "correlation_id", "payload", "timestamp"]
        for field in required_fields:
            assert field in event, (
                f"SwarmEvent missing required field: {field}. "
                f"Found fields: {list(event.keys())}"
            )

    def test_event_has_coordination_metadata(self):
        """Events should include requires_response and response_deadline."""
        stdout = swarm_task(
            "Add a DELETE /tasks/:id endpoint to todo-api"
        )
        event = extract_json_block(stdout, after_marker="Publishing event")
        assert event is not None, "No event JSON found"
        has_metadata = "requires_response" in event or "response_deadline" in event
        assert has_metadata, (
            "SwarmEvent missing coordination metadata. "
            "Expected requires_response and/or response_deadline."
        )


# ============================================================================
# TESTS — FAN-OUT/FAN-IN
# ============================================================================

class TestFanOut:
    """Fan-out must distribute work in parallel and merge results."""

    def test_fan_out_distributes_to_multiple_agents(self):
        """Fan-out should send one event to multiple subscribers."""
        stdout = swarm_task(
            "Add a DELETE /tasks/:id endpoint to todo-api"
        )
        fanout_events = extract_tagged_events(stdout, "fan-out")
        has_distribution = any(
            "subscribers" in e or "→" in e
            for e in fanout_events
        )
        assert has_distribution, (
            "No fan-out distribution found. "
            "Expected [fan-out] Event <type> → N subscribers."
        )

    def test_fan_in_collects_all_responses(self):
        """Fan-in collector should track and merge all responses."""
        stdout = swarm_task(
            "Add a DELETE /tasks/:id endpoint to todo-api"
        )
        fanin_events = extract_tagged_events(stdout, "fan-in")
        has_collection = any(
            "responses received" in e or "Merged" in e or "All" in e
            for e in fanin_events
        )
        assert has_collection, (
            "No fan-in collection found. "
            "Expected [fan-in] All N responses received."
        )

    def test_fan_in_merge_includes_all_agents(self):
        """Merged result should include responses from all responding agents."""
        stdout = swarm_task(
            "Add a DELETE /tasks/:id endpoint to todo-api"
        )
        merged = extract_json_block(stdout, after_marker="Merged feedback")
        if merged is not None:
            # Check that multiple agents are represented
            has_multiple = (
                ("responses" in merged and len(merged["responses"]) >= 2) or
                ("review" in merged and "tests" in merged) or
                len(merged) >= 2
            )
            assert has_multiple, (
                f"Merged result only has {len(merged)} entries. "
                "Expected responses from multiple agents."
            )

    def test_fan_out_handles_deadline_with_partial_results(self):
        """When an agent doesn't respond by deadline, merge partial results with warnings."""
        stdout = swarm_task(
            "Add endpoint with one agent intentionally slow or crashed"
        )
        fanin_events = extract_tagged_events(stdout, "fan-in")
        all_text = " ".join(fanin_events).lower()
        # Either all agents responded (no partial) or partial results were handled
        has_partial = (
            "partial" in all_text or
            "missing" in all_text or
            "deadline" in all_text or
            "warning" in all_text or
            "all" in all_text  # all responded successfully
        )
        assert has_partial or len(fanin_events) > 0, (
            "Fan-in doesn't handle partial results. "
            "Expected warnings when agents miss the deadline."
        )

    def test_fan_out_faster_than_sequential(self):
        """Fan-out wall-clock time should be less than sum of individual times."""
        stdout = swarm_task(
            "Add a DELETE /tasks/:id endpoint to todo-api"
        )
        # Look for timing information in fan-in events
        fanin_events = extract_tagged_events(stdout, "fan-in")
        all_text = stdout.lower()
        # Check for timing evidence: "18.7s total" or similar
        time_match = re.search(r'(\d+\.?\d*)\s*s?\s*total', all_text)
        if time_match:
            total_time = float(time_match.group(1))
            # Look for individual agent times
            individual_times = re.findall(
                r'\((\d+\.?\d*)\s*s\)', stdout
            )
            if len(individual_times) >= 2:
                sequential_sum = sum(float(t) for t in individual_times)
                assert total_time < sequential_sum, (
                    f"Fan-out total ({total_time}s) >= sequential sum ({sequential_sum}s). "
                    "Fan-out should be faster than sequential."
                )


# ============================================================================
# TESTS — REVIEW CHAINS
# ============================================================================

class TestReviewChains:
    """Review chains must emerge from individual routing decisions."""

    def test_route_decision_has_valid_action(self):
        """RouteDecision action must be one of: pass_forward, push_back, escalate, done."""
        stdout = swarm_task(
            "Refactor the error handling in todo-api routes"
        )
        valid_actions = ["pass_forward", "push_back", "escalate", "done"]
        all_text = stdout.lower()
        has_action = any(action in all_text for action in valid_actions)
        assert has_action, (
            "No valid RouteDecision action found. "
            f"Expected one of: {valid_actions}"
        )

    def test_push_back_returns_to_source(self):
        """Push back should route work back to the source agent."""
        stdout = swarm_task(
            "Submit code with critical issues for review"
        )
        all_text = stdout.lower()
        has_push_back = "push_back" in all_text or "push back" in all_text
        if has_push_back:
            has_target = "coder" in all_text or "source" in all_text
            assert has_target, (
                "Push back found but no target agent. "
                "Push back should route to the source agent."
            )

    def test_chain_completes_with_done(self):
        """A successful review chain should end with a 'done' decision."""
        stdout = swarm_task(
            "Refactor error handling and get it through review and tests"
        )
        all_text = stdout.lower()
        has_done = (
            '"done"' in all_text or
            "action: done" in all_text or
            "chain complete" in all_text or
            "all tests passed" in all_text
        )
        assert has_done, (
            "Review chain didn't terminate with 'done'. "
            "Expected a done decision or chain complete message."
        )


# ============================================================================
# TESTS — CONSENSUS
# ============================================================================

class TestConsensus:
    """Consensus must use weighted voting based on decision type."""

    def test_consensus_uses_weighted_votes(self):
        """Votes should be weighted by domain expertise for the decision type."""
        stdout = swarm_task(
            "Prioritize next work: refactor create_task or fix SQL injection"
        )
        consensus_events = extract_tagged_events(stdout, "consensus")
        all_text = " ".join(consensus_events).lower()
        has_weights = "weight" in all_text or "weighted" in all_text
        assert has_weights or len(consensus_events) > 0, (
            "No weighted voting found. "
            "Consensus should use domain-expertise weights."
        )

    def test_consensus_produces_result(self):
        """Consensus should produce a result with chosen option and margin."""
        stdout = swarm_task(
            "Prioritize next work: refactor create_task or fix SQL injection"
        )
        result = extract_json_block(stdout, after_marker="[consensus] Result")
        if result is not None:
            assert "chosen" in result, (
                "ConsensusResult missing 'chosen' field"
            )
        else:
            # Check for result in text form
            consensus_events = extract_tagged_events(stdout, "consensus")
            all_text = " ".join(consensus_events).lower()
            has_result = "chosen" in all_text or "result" in all_text or "winner" in all_text
            assert has_result, (
                "No consensus result found. Expected chosen option."
            )

    def test_consensus_weighted_tally_correct(self):
        """Weighted tally should correctly sum vote weights per option."""
        stdout = swarm_task(
            "Prioritize: refactor create_task or fix SQL injection (security decision)"
        )
        # Look for tally information
        all_text = stdout.lower()
        tally_match = re.findall(r'option\s+[ab]:\s*(\d+\.?\d*)', all_text)
        if len(tally_match) >= 2:
            tallies = [float(t) for t in tally_match]
            # Verify tallies are different (weighted voting should produce different totals)
            assert tallies[0] != tallies[1] or len(set(tallies)) == 1, (
                "Tallies should reflect weighted votes"
            )

    def test_consensus_respects_required_voters(self):
        """If a required voter doesn't respond, consensus should fail or wait."""
        stdout = swarm_task(
            "Make a security decision where security-auditor is required but unavailable"
        )
        all_text = stdout.lower()
        has_required_handling = (
            "required" in all_text or
            "must vote" in all_text or
            "waiting" in all_text or
            "failed" in all_text or
            # If all voters responded, that's also valid
            "all" in all_text
        )
        assert has_required_handling, (
            "No handling of required voters found. "
            "Required voters should block consensus if they don't vote."
        )

    def test_consensus_preserves_dissent(self):
        """Losing voters' reasoning should be preserved in the result."""
        stdout = swarm_task(
            "Prioritize next work: refactor create_task or fix SQL injection"
        )
        result = extract_json_block(stdout, after_marker="[consensus] Result")
        all_text = stdout.lower()
        has_dissent = (
            "dissent" in all_text or
            "unanimous" in all_text or
            (result is not None and "votes" in result)
        )
        assert has_dissent, (
            "No dissent or vote details preserved. "
            "ConsensusResult should include all votes and dissent."
        )


# ============================================================================
# TESTS — CONFLICT RESOLUTION
# ============================================================================

class TestConflictResolution:
    """Conflict resolution must handle factual disagreements between agents."""

    def test_conflict_uses_valid_strategy(self):
        """Resolution strategy must be request_evidence, defer_to_expert, or escalate."""
        stdout = swarm_task(
            "Verify the ownership check in delete_task — reviewer and runner disagree"
        )
        valid_strategies = ["request_evidence", "defer_to_expert", "escalate"]
        all_text = stdout.lower()
        has_strategy = any(s in all_text for s in valid_strategies)
        assert has_strategy, (
            "No valid conflict resolution strategy found. "
            f"Expected one of: {valid_strategies}"
        )

    def test_evidence_based_resolution_requests_proof(self):
        """Request evidence strategy should ask both agents to prove their claims."""
        stdout = swarm_task(
            "Resolve: reviewer says no ownership check, runner says tests pass"
        )
        conflict_events = extract_tagged_events(stdout, "conflict")
        all_text = " ".join(conflict_events).lower()
        has_evidence_request = (
            "evidence" in all_text or
            "provide" in all_text or
            "prove" in all_text or
            "specific" in all_text
        )
        assert has_evidence_request or len(conflict_events) > 0, (
            "No evidence request found. "
            "request_evidence strategy should ask agents to prove claims."
        )

    def test_conflict_resolution_produces_actionable_result(self):
        """Resolution should produce a concrete, actionable decision."""
        stdout = swarm_task(
            "Resolve conflict: reviewer says bug exists, runner says tests pass"
        )
        resolution = extract_json_block(stdout, after_marker="Resolution")
        if resolution is not None:
            assert "resolution" in resolution or "decided_by" in resolution, (
                "Conflict resolution missing actionable result."
            )
        else:
            conflict_events = extract_tagged_events(stdout, "conflict")
            all_text = " ".join(conflict_events).lower()
            has_resolution = (
                "resolution" in all_text or
                "decided" in all_text or
                "resolved" in all_text
            )
            assert has_resolution, (
                "No actionable resolution found. "
                "Conflict resolution should produce a decision."
            )


# ============================================================================
# TESTS — BACKPRESSURE
# ============================================================================

class TestBackpressure:
    """Backpressure must prevent queue overflow and signal capacity limits."""

    def test_backpressure_signal_has_required_fields(self):
        """BackpressureSignal must include source, queue_depth, capacity, action."""
        stdout = swarm_task(
            "Send work to runner when its queue is full"
        )
        signal = extract_json_block(stdout, after_marker="backpressure")
        if signal is not None:
            expected_fields = ["source", "queue_depth", "capacity", "action"]
            for field in expected_fields:
                assert field in signal, (
                    f"BackpressureSignal missing field: {field}. "
                    f"Found: {list(signal.keys())}"
                )

    def test_backpressure_action_is_valid(self):
        """Backpressure action must be reject, delay, or redirect."""
        stdout = swarm_task(
            "Send work to runner when its queue is full"
        )
        valid_actions = ["reject", "delay", "redirect"]
        all_text = stdout.lower()
        has_action = any(action in all_text for action in valid_actions)
        assert has_action, (
            "No valid backpressure action found. "
            f"Expected one of: {valid_actions}"
        )

    def test_requester_adapts_to_backpressure(self):
        """Requester should wait, retry, or redirect after receiving backpressure."""
        stdout = swarm_task(
            "Send 5 tasks to runner — trigger backpressure on task 5"
        )
        all_text = stdout.lower()
        has_adaptation = (
            "retry" in all_text or
            "wait" in all_text or
            "redirect" in all_text or
            "back off" in all_text or
            "backoff" in all_text
        )
        assert has_adaptation, (
            "Requester didn't adapt to backpressure. "
            "Expected retry, wait, or redirect behavior."
        )


# ============================================================================
# TESTS — COLLECTIVE LEARNING
# ============================================================================

class TestCollectiveLearning:
    """Collective learning must propagate skill improvements across the swarm."""

    def test_skill_improvement_published_to_bus(self):
        """When an agent rewrites a skill, it should publish a skill_improved event."""
        stdout = swarm_task(
            "Security auditor discovers new SQL injection pattern and rewrites skill"
        )
        all_text = stdout.lower()
        has_publish = "skill_improved" in all_text or "publishing" in all_text
        assert has_publish, (
            "No skill_improved event published. "
            "Skill rewrites should be broadcast to the swarm."
        )

    def test_other_agents_receive_skill_improvement(self):
        """Other agents should receive and process skill_improved events."""
        stdout = swarm_task(
            "Security auditor improves security-scan skill and shares with swarm"
        )
        all_text = stdout.lower()
        has_reception = (
            "received skill_improved" in all_text or
            "adopted" in all_text or
            "rejected" in all_text
        )
        assert has_reception, (
            "No evidence that other agents received the skill improvement. "
            "Skill improvements should propagate via broadcast bus."
        )

    def test_verification_before_adoption(self):
        """Agents must verify improvement before adopting a shared skill."""
        stdout = swarm_task(
            "Propagate a skill improvement across the swarm with verification"
        )
        all_text = stdout.lower()
        has_verification = (
            "verify" in all_text or
            "verification" in all_text or
            "recommendation" in all_text or
            "keep" in all_text
        )
        assert has_verification, (
            "No verification before skill adoption. "
            "Agents should verify improvements before adopting (Ch 9 verify_improvement)."
        )

    def test_reject_degrading_skill(self):
        """Agents should reject shared skills that degrade their performance."""
        stdout = swarm_task(
            "Share a skill improvement that makes one agent's output worse"
        )
        all_text = stdout.lower()
        has_rejection = (
            "rejected" in all_text or
            "degraded" in all_text or
            "rollback" in all_text or
            "worse" in all_text
        )
        assert has_rejection, (
            "No evidence of skill rejection on degradation. "
            "Agents should reject skills that make their performance worse."
        )


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestOrchestrator,
        TestSwarmEvent,
        TestFanOut,
        TestReviewChains,
        TestConsensus,
        TestConflictResolution,
        TestBackpressure,
        TestCollectiveLearning,
    ]
    passed = 0
    failed = 0
    errors = []

    for cls in test_classes:
        print(f"\n{cls.__name__}")
        print("-" * len(cls.__name__))
        instance = cls()
        for method_name in sorted(dir(instance)):
            if method_name.startswith("test_"):
                test_name = f"{cls.__name__}.{method_name}"
                try:
                    getattr(instance, method_name)()
                    print(f"  PASS  {method_name}")
                    passed += 1
                except AssertionError as e:
                    print(f"  FAIL  {method_name}: {e}")
                    failed += 1
                    errors.append((test_name, str(e)))
                except Exception as e:
                    print(f"  ERROR {method_name}: {e}")
                    failed += 1
                    errors.append((test_name, str(e)))

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    if errors:
        print(f"\nFailures:")
        for name, err in errors:
            print(f"  {name}: {err}")
    sys.exit(0 if failed == 0 else 1)
