"""
Chapter 14 Validation Tests
============================

These tests validate the reader's Ch 14 implementation: production architecture
including checkpoints, distributed tracing, agent versioning, mixed-version
handling, and system-wide idempotency.

The reader's program must be callable as:
    tbh-code --swarm --task "<task>"
    tbh-code --swarm --trace --task "<task>"

Production traces must appear in stdout with the format:
    [coder] Checkpoint saved: <task_id>/step-<N>
    [coder] Found checkpoint: <task_id>/step-<N>
    [coder] Resuming from checkpoint: step <N>
    [coder] Resuming from step <N>/<M>
    [system] Trace started: <trace_id>
    [system] Trace complete: <trace_id>
    Trace ID: <trace_id>
    WATERFALL:
    [system] Compatibility check: <agent_a> <-> <agent_b>
    [system] Result: COMPATIBLE | DEGRADED | INCOMPATIBLE
    [system] Protocol negotiation for <task_id>:
    [reviewer] Idempotency check: <key> → Proceed | AlreadyDone
    [reviewer] Duplicate detected. Returning cached result.

Output must include JSON payloads matching the interface spec.

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

def swarm_task(task, extra_flags=None, timeout=180):
    """Run a swarm task and capture stdout."""
    cmd = [AGENT_CMD, "--swarm"]
    if extra_flags:
        cmd.extend(extra_flags)
    cmd.extend(["--task", task])
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
    """Extract events with a specific tag like [coder], [system], etc."""
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
# TESTS — CHECKPOINTS
# ============================================================================

class TestCheckpoint:
    """Checkpoints must save agent state at boundaries and restore after crash."""

    def test_checkpoint_saved_during_task(self):
        """Agent should save checkpoints at plan step boundaries."""
        stdout = swarm_task(
            "Refactor payment module validation (5-step task with checkpoints)"
        )
        all_text = stdout.lower()
        has_checkpoint = (
            "checkpoint saved" in all_text or
            "checkpoint:" in all_text
        )
        assert has_checkpoint, (
            "No checkpoint save found. "
            "Agent should save checkpoints at plan step boundaries."
        )

    def test_checkpoint_includes_step_index(self):
        """Checkpoint output should indicate which step was checkpointed."""
        stdout = swarm_task(
            "Process a multi-step task with checkpoints enabled"
        )
        all_text = stdout.lower()
        has_step = (
            re.search(r'step[-_]?\d', all_text) is not None or
            "step_index" in all_text
        )
        assert has_step, (
            "Checkpoint doesn't indicate step index. "
            "Checkpoints should record which plan step was completed."
        )

    def test_resume_from_checkpoint_after_crash(self):
        """After simulated crash, agent should resume from last checkpoint."""
        stdout = swarm_task(
            "Process task with simulated crash at step 4 — resume from checkpoint"
        )
        all_text = stdout.lower()
        has_resume = (
            "resuming" in all_text or
            "resume" in all_text or
            "restored" in all_text or
            "found checkpoint" in all_text
        )
        assert has_resume, (
            "No checkpoint resume found after crash. "
            "Agent should detect and restore from checkpoint on startup."
        )
        # Verify work was not lost
        has_completion = (
            "complete" in all_text or
            "done" in all_text or
            "0 steps" in all_text  # 0 steps lost
        )
        assert has_completion, (
            "Task didn't complete after resume. "
            "Agent should finish remaining steps after restoring checkpoint."
        )

    def test_list_checkpoints(self):
        """CheckpointStore.list should return checkpoint summaries."""
        stdout = swarm_task(
            "Process a task and list all checkpoints at the end"
        )
        all_text = stdout.lower()
        has_listing = (
            "checkpoint" in all_text and
            (re.search(r'step[-_]?\d', all_text) is not None or
             "list" in all_text)
        )
        assert has_listing, (
            "No checkpoint listing found. "
            "CheckpointStore.list should return summaries of saved checkpoints."
        )

    def test_cleanup_old_checkpoints(self):
        """CheckpointStore.cleanup should prune old checkpoints, keeping last N."""
        stdout = swarm_task(
            "Process a task with checkpoint cleanup after completion"
        )
        all_text = stdout.lower()
        has_cleanup = (
            "cleanup" in all_text or
            "cleaning" in all_text or
            "pruning" in all_text or
            "keeping" in all_text
        )
        assert has_cleanup, (
            "No checkpoint cleanup found. "
            "CheckpointStore.cleanup should prune old checkpoints."
        )


# ============================================================================
# TESTS — DISTRIBUTED TRACING
# ============================================================================

class TestDistributedTracing:
    """Distributed tracing must follow tasks across agents with span trees."""

    def test_trace_created_with_id(self):
        """A trace should be started with a unique trace ID."""
        stdout = swarm_task(
            "Add DELETE /tasks/:id endpoint",
            extra_flags=["--trace"]
        )
        all_text = stdout.lower()
        has_trace_id = (
            "trace" in all_text and
            re.search(r'trace[-_]?[a-z0-9]{4}', all_text) is not None
        )
        assert has_trace_id, (
            "No trace ID found. "
            "Distributed tracing should assign a unique trace ID."
        )

    def test_trace_spans_across_agents(self):
        """Trace should contain spans from multiple agents."""
        stdout = swarm_task(
            "Add DELETE /tasks/:id endpoint with full tracing",
            extra_flags=["--trace"]
        )
        all_text = stdout
        agents_in_trace = set()
        for agent in ["coder", "reviewer", "runner", "security"]:
            if f"[{agent}]" in all_text.lower():
                agents_in_trace.add(agent)
        assert len(agents_in_trace) >= 2, (
            f"Only found spans for {agents_in_trace}. "
            "Trace should span multiple agents."
        )

    def test_waterfall_rendering(self):
        """Trace should render a human-readable waterfall view."""
        stdout = swarm_task(
            "Add DELETE /tasks/:id endpoint with trace waterfall",
            extra_flags=["--trace"]
        )
        all_text = stdout.lower()
        has_waterfall = (
            "waterfall" in all_text or
            # Check for waterfall-like structure (indented spans with timing)
            re.search(r'[✓✗○].*\[.*\].*\d+\.?\d*s', stdout) is not None
        )
        assert has_waterfall, (
            "No waterfall view found. "
            "Trace.waterfall() should render a human-readable timeline."
        )

    def test_parent_child_span_relationships(self):
        """Spans should have parent-child relationships forming a tree."""
        stdout = swarm_task(
            "Add DELETE /tasks/:id endpoint with span details",
            extra_flags=["--trace"]
        )
        all_text = stdout.lower()
        has_parent = (
            "parent" in all_text or
            # Tree structure indicators
            "├─" in stdout or
            "│" in stdout or
            "└─" in stdout
        )
        assert has_parent, (
            "No parent-child span relationships found. "
            "Spans should form a tree with parent_span_id references."
        )

    def test_trace_propagation_through_messages(self):
        """Trace context should propagate through PeerMessenger messages."""
        stdout = swarm_task(
            "Multi-agent task with trace propagation across messages",
            extra_flags=["--trace"]
        )
        all_text = stdout.lower()
        # Check that spans from different agents share the same trace_id
        trace_ids = re.findall(r'trace[-_]?([a-z0-9]{4,})', all_text)
        if len(trace_ids) >= 2:
            # All should be the same trace ID
            assert len(set(trace_ids)) == 1, (
                f"Multiple trace IDs found: {set(trace_ids)}. "
                "All spans in one task should share the same trace_id."
            )
        else:
            # Check for trace_context mention
            has_propagation = (
                "trace_context" in all_text or
                "trace context" in all_text or
                "propagat" in all_text
            )
            assert has_propagation or len(trace_ids) > 0, (
                "No trace propagation found. "
                "Trace context should propagate through message envelopes."
            )


# ============================================================================
# TESTS — AGENT VERSIONING
# ============================================================================

class TestVersioning:
    """Agent versioning must use semver and check compatibility."""

    def test_agent_declares_version(self):
        """Each agent should declare its version in AgentVersion format."""
        stdout = swarm_task(
            "Show agent versions in the swarm"
        )
        all_text = stdout.lower()
        has_version = (
            re.search(r'v?\d+\.\d+\.\d+', stdout) is not None or
            "version" in all_text
        )
        assert has_version, (
            "No agent version declaration found. "
            "Agents should declare semver versions."
        )

    def test_compatibility_check_compatible(self):
        """Agents with same protocol and same major version → compatible."""
        stdout = swarm_task(
            "Check compatibility: coder v2.1.0 and runner v2.0.0 (same protocol)"
        )
        all_text = stdout.lower()
        has_compatible = "compatible" in all_text
        assert has_compatible, (
            "No compatibility result found. "
            "check_compatible should return 'compatible' for same protocol + same major."
        )

    def test_compatibility_check_degraded(self):
        """Agents with same protocol but different major version → degraded."""
        stdout = swarm_task(
            "Check compatibility: coder v2.1.0 and reviewer v1.3.2 (same protocol, different major)"
        )
        all_text = stdout.lower()
        has_degraded = "degraded" in all_text
        assert has_degraded, (
            "No 'degraded' result found. "
            "check_compatible should return 'degraded' for different major agent versions."
        )

    def test_compatibility_check_incompatible(self):
        """Agents with different protocol major version → incompatible."""
        stdout = swarm_task(
            "Check compatibility: coder (protocol 2.0) and reviewer (protocol 1.0)"
        )
        all_text = stdout.lower()
        has_incompatible = "incompatible" in all_text
        assert has_incompatible, (
            "No 'incompatible' result found. "
            "check_compatible should return 'incompatible' for different protocol major versions."
        )

    def test_version_in_agent_card(self):
        """AgentVersion should be included in the agent card (Ch 11 extension)."""
        stdout = swarm_task(
            "Show agent cards with version information"
        )
        all_text = stdout.lower()
        has_version_in_card = (
            ("agent_card" in all_text or "card" in all_text or "capabilities" in all_text) and
            ("version" in all_text or re.search(r'v?\d+\.\d+', stdout) is not None)
        )
        assert has_version_in_card, (
            "No version in agent card found. "
            "AgentCard should include version information."
        )


# ============================================================================
# TESTS — MIXED-VERSION SWARM
# ============================================================================

class TestMixedVersion:
    """Mixed-version swarms must negotiate protocol and degrade gracefully."""

    def test_protocol_negotiation(self):
        """Swarm should negotiate to lowest common protocol version."""
        stdout = swarm_task(
            "Run task with mixed-version swarm (coder v2, reviewer v1, runner v1)"
        )
        all_text = stdout.lower()
        has_negotiation = (
            "negotiat" in all_text or
            "common protocol" in all_text or
            "degraded" in all_text
        )
        assert has_negotiation, (
            "No protocol negotiation found. "
            "Mixed-version swarms should negotiate to lowest common protocol."
        )

    def test_degraded_features_listed(self):
        """Negotiation should list which features are unavailable."""
        stdout = swarm_task(
            "Run mixed-version task — show degraded features"
        )
        all_text = stdout.lower()
        has_degraded_list = (
            "degraded" in all_text or
            "not available" in all_text or
            "fallback" in all_text or
            "falling back" in all_text
        )
        assert has_degraded_list, (
            "No degraded features listed. "
            "Protocol negotiation should report which features are unavailable."
        )

    def test_mixed_version_task_completes(self):
        """Task should complete successfully despite version differences."""
        stdout = swarm_task(
            "Add DELETE /tasks/:id endpoint with mixed-version swarm"
        )
        all_text = stdout.lower()
        has_completion = (
            "complete" in all_text or
            "success" in all_text or
            "done" in all_text
        )
        assert has_completion, (
            "Mixed-version task didn't complete. "
            "Swarm should complete tasks even with degraded features."
        )

    def test_incompatible_agent_rejected(self):
        """Agent with incompatible protocol version should be rejected."""
        stdout = swarm_task(
            "Attempt collaboration with incompatible protocol version"
        )
        all_text = stdout.lower()
        has_rejection = (
            "incompatible" in all_text or
            "cannot communicate" in all_text or
            "rejected" in all_text or
            "refused" in all_text
        )
        assert has_rejection, (
            "No incompatibility handling found. "
            "Agents with incompatible protocol versions should be rejected."
        )


# ============================================================================
# TESTS — IDEMPOTENCY
# ============================================================================

class TestIdempotency:
    """Idempotency must prevent duplicate work on retries."""

    def test_idempotency_key_generated(self):
        """Messages should include an idempotency key."""
        stdout = swarm_task(
            "Send code_ready with idempotency key"
        )
        all_text = stdout.lower()
        has_key = (
            "idempotency" in all_text or
            "idempotency_key" in all_text
        )
        assert has_key, (
            "No idempotency key found. "
            "Messages should include an idempotency key for deduplication."
        )

    def test_duplicate_detected(self):
        """Retry with same idempotency key should be detected as duplicate."""
        stdout = swarm_task(
            "Send code_ready, simulate network blip, retry with same idempotency key"
        )
        all_text = stdout.lower()
        has_duplicate = (
            "duplicate" in all_text or
            "already" in all_text or
            "alreadydone" in all_text or
            "cached" in all_text
        )
        assert has_duplicate, (
            "No duplicate detection found. "
            "Retry with same idempotency key should return cached result."
        )

    def test_idempotent_retry_returns_same_result(self):
        """Retried operation should produce the same result as original."""
        stdout = swarm_task(
            "Review code with retry — verify idempotent result"
        )
        all_text = stdout.lower()
        # Should not see "2 reviews" or "duplicate review"
        has_single_result = (
            "1 copy" in all_text or
            "cached result" in all_text or
            "duplicate suppressed" in all_text or
            "returning cached" in all_text or
            "skipping" in all_text
        )
        assert has_single_result, (
            "No evidence of idempotent deduplication. "
            "Retry should return cached result, not create duplicate work."
        )

    def test_different_key_processes_normally(self):
        """Message with a different idempotency key should be processed normally."""
        stdout = swarm_task(
            "Send two code_ready messages with different idempotency keys"
        )
        all_text = stdout.lower()
        has_proceed = "proceed" in all_text
        assert has_proceed, (
            "No 'Proceed' result for new idempotency key. "
            "Different keys should be processed normally, not deduplicated."
        )

    def test_saga_idempotency_skips_completed_steps(self):
        """Saga retry should skip already-completed steps via idempotency."""
        stdout = swarm_task(
            "Run 3-step saga, fail at step 3, retry — steps 1-2 should be skipped"
        )
        all_text = stdout.lower()
        has_skip = (
            "skipping" in all_text or
            "already completed" in all_text or
            "alreadydone" in all_text
        )
        assert has_skip, (
            "No step skipping on saga retry. "
            "Already-completed saga steps should be skipped via idempotency."
        )


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestCheckpoint,
        TestDistributedTracing,
        TestVersioning,
        TestMixedVersion,
        TestIdempotency,
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
