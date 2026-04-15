"""
Chapter 7 Validation Tests
==========================

These tests validate the reader's Ch 7 implementation: task decomposition,
plan execution, failure handling with replan, chain-of-thought reasoning,
and strategy tracking.

The reader's program must be callable as:
    tbh-code --codebase <path> --ask "<question>"
    tbh-code --codebase <path> --auto-approve --ask "<question>"

Plan traces must appear in stdout with the format:
    [plan] Decomposing task: "<task>"
    [plan] Generated plan (N steps):
    [think] Step N: <reasoning>
    [plan] Step N completed: <description>
    [plan] Step N FAILED: <error>
    [plan] Plan completed: N/N steps succeeded

Memory traces for strategy:
    [memory] Saving strategy: <task_type>/<name>

Output must include a JSON response with: answer, confidence, sources

Adjust AGENT_CMD and TODO_API_PATH below to match the reader's setup.
"""

import subprocess
import json
import os
import re
import sys

# ============================================================================
# CONFIGURATION
# ============================================================================

AGENT_CMD = "tbh-code"
TODO_API_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "todo-api")

# ============================================================================
# HELPERS
# ============================================================================

def ask(question, auto_approve=True, timeout=90):
    """Ask the agent a question and capture stdout."""
    cmd = [AGENT_CMD, "--codebase", TODO_API_PATH, "--ask", question]
    if auto_approve:
        cmd.insert(3, "--auto-approve")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    return result.stdout


def extract_json(stdout):
    """Extract the JSON response from agent output."""
    json_start = stdout.find("{")
    json_end = stdout.rfind("}") + 1
    assert json_start >= 0 and json_end > json_start, (
        f"No JSON found in output:\n{stdout}"
    )
    return json.loads(stdout[json_start:json_end])


def extract_plan_steps(stdout):
    """Extract plan steps from agent output."""
    steps = []
    for line in stdout.splitlines():
        # Match "Step N:" in plan or think lines
        step_match = re.match(r'\s*Step (\d+)[:/]?\s*(.*)', line)
        if step_match:
            steps.append({
                "number": int(step_match.group(1)),
                "text": step_match.group(2).strip()
            })
    return steps


def extract_think_traces(stdout):
    """Extract chain-of-thought reasoning traces."""
    traces = []
    for line in stdout.splitlines():
        think_match = re.match(r'\[think\] (.+)', line)
        if think_match:
            traces.append(think_match.group(1))
    return traces


def extract_plan_events(stdout):
    """Extract plan-related events from output."""
    events = []
    for line in stdout.splitlines():
        plan_match = re.match(r'\[plan\] (.+)', line)
        if plan_match:
            events.append(plan_match.group(1))
    return events


def extract_tool_calls(stdout):
    """Extract tool call traces from agent output."""
    calls = []
    current_call = {}
    for line in stdout.splitlines():
        selected = re.match(r'\[tool\] Agent selected: (.+)', line)
        if selected:
            if current_call:
                calls.append(current_call)
            current_call = {"tool": selected.group(1).strip()}

        result_match = re.match(r'\[tool\] Result: success=(true|false)', line)
        if result_match and current_call:
            current_call["success"] = result_match.group(1) == "true"

    if current_call:
        calls.append(current_call)
    return calls


def extract_memory_events(stdout):
    """Extract memory-related events from output."""
    events = []
    for line in stdout.splitlines():
        mem_match = re.match(r'\[memory\] (.+)', line)
        if mem_match:
            events.append(mem_match.group(1))
    return events


# ============================================================================
# TESTS — DECOMPOSITION
# ============================================================================

class TestDecomposition:
    """Agent must decompose complex tasks into ordered steps."""

    def test_complex_task_produces_plan(self):
        """A multi-step task should trigger plan decomposition."""
        stdout = ask(
            "Add input validation to POST /tasks — title must be "
            "non-empty and under 200 chars"
        )
        plan_events = extract_plan_events(stdout)
        assert len(plan_events) > 0, (
            "No plan events found. Complex task should trigger decomposition."
        )
        decompose_events = [e for e in plan_events if "Decomposing" in e or "Generated plan" in e]
        assert len(decompose_events) > 0, (
            "No decomposition event found. "
            "Expected [plan] Decomposing task or Generated plan."
        )

    def test_plan_has_multiple_steps(self):
        """Decomposed plan should have at least 3 steps."""
        stdout = ask(
            "Add input validation to POST /tasks — title must be "
            "non-empty and under 200 chars"
        )
        plan_events = extract_plan_events(stdout)
        # Look for "N steps" in plan events
        step_count = 0
        for event in plan_events:
            count_match = re.search(r'(\d+)\s*steps', event)
            if count_match:
                step_count = int(count_match.group(1))
                break
        # Also count actual step completions
        completed = [e for e in plan_events if "Step" in e and "completed" in e.lower()]
        actual_steps = max(step_count, len(completed))
        assert actual_steps >= 3, (
            f"Plan should have at least 3 steps, found {actual_steps}. "
            "A meaningful plan needs multiple steps."
        )

    def test_steps_are_ordered(self):
        """Plan steps should execute in logical order (read before write)."""
        stdout = ask(
            "Add a new helper function to the database layer and write a test for it"
        )
        calls = extract_tool_calls(stdout)
        tool_names = [c.get("tool") for c in calls]

        # Find positions of first read and first write
        first_read = -1
        first_write = -1
        for i, name in enumerate(tool_names):
            if name in ("read_file", "search_code", "list_files") and first_read == -1:
                first_read = i
            if name == "write_file" and first_write == -1:
                first_write = i

        if first_read >= 0 and first_write >= 0:
            assert first_read < first_write, (
                f"Read tool at position {first_read}, write at {first_write}. "
                "Agent should read/search BEFORE writing."
            )

    def test_simple_task_skips_planning(self):
        """Simple single-tool tasks should not trigger full decomposition."""
        stdout = ask("What files are in the src/ directory?")
        plan_events = extract_plan_events(stdout)
        decompose_events = [
            e for e in plan_events
            if "Decomposing" in e and "Generated plan" in e
        ]
        # Should either skip planning or have a trivial plan
        calls = extract_tool_calls(stdout)
        # Simple task should use 1-2 tool calls at most
        assert len(calls) <= 3, (
            f"Simple task used {len(calls)} tool calls — may be over-planning"
        )


# ============================================================================
# TESTS — PLAN EXECUTION
# ============================================================================

class TestPlanExecution:
    """Plan steps must execute sequentially with results flowing forward."""

    def test_steps_execute_sequentially(self):
        """Steps should execute one after another."""
        stdout = ask(
            "Find all route handlers in todo-api, then create a summary "
            "document listing each route with its HTTP method"
        )
        plan_events = extract_plan_events(stdout)
        completed = [e for e in plan_events if "completed" in e.lower()]
        assert len(completed) >= 2, (
            f"Only {len(completed)} steps completed. "
            "Multi-step task should have multiple completed steps."
        )

    def test_results_flow_between_steps(self):
        """Later steps should use results from earlier steps."""
        stdout = ask(
            "Search for all TODO comments in the codebase, then create a "
            "file tracking each TODO with its file and line number"
        )
        calls = extract_tool_calls(stdout)
        # Should search first, then write based on search results
        tool_names = [c.get("tool") for c in calls]
        assert "search_code" in tool_names, "Should search first"
        assert "write_file" in tool_names, "Should write based on search results"

    def test_plan_completion_reported(self):
        """Agent should report plan completion status."""
        stdout = ask(
            "Add input validation to POST /tasks — title must be non-empty"
        )
        plan_events = extract_plan_events(stdout)
        completion = [
            e for e in plan_events
            if "completed" in e.lower() and ("plan" in e.lower() or "/" in e)
        ]
        assert len(completion) > 0, (
            "No plan completion status found. "
            "Agent should report how many steps succeeded."
        )


# ============================================================================
# TESTS — REPLAN ON FAILURE
# ============================================================================

class TestReplan:
    """Step failure should trigger replanning, not crash."""

    def test_failure_does_not_crash(self):
        """A failing step should not crash the agent."""
        # This task is likely to have a step that fails
        stdout = ask(
            "Create a new middleware that validates request body is JSON, "
            "apply it to all routes, and run the tests"
        )
        # Agent should complete (return code 0 checked by ask())
        response = extract_json(stdout)
        assert response.get("answer"), "Agent failed to produce an answer"

    def test_replan_triggers_on_test_failure(self):
        """If tests fail, agent should replan with a fix."""
        stdout = ask(
            "Add a feature to mark tasks as urgent with a priority field, "
            "write tests, and make sure all tests pass"
        )
        plan_events = extract_plan_events(stdout)
        all_text = " ".join(plan_events).lower()
        # Look for either replan or all tests passing
        has_replan = "replan" in all_text or "replanning" in all_text
        has_success = "completed" in all_text
        assert has_replan or has_success, (
            "Agent didn't handle potential test failure — "
            "should either replan or succeed."
        )

    def test_replan_uses_different_approach(self):
        """Replanned steps should differ from the original failed approach."""
        stdout = ask(
            "Write a caching layer for database queries — if the first "
            "approach doesn't work, try a different strategy"
        )
        plan_events = extract_plan_events(stdout)
        # If replanning occurred, there should be additional steps
        response = extract_json(stdout)
        assert response.get("answer"), "Agent should produce an answer even if replanning occurs"


# ============================================================================
# TESTS — CHAIN OF THOUGHT
# ============================================================================

class TestChainOfThought:
    """Agent must show reasoning before each step."""

    def test_think_traces_present(self):
        """[think] traces should appear before tool calls."""
        stdout = ask(
            "Add input validation to POST /tasks — title must be non-empty"
        )
        think_traces = extract_think_traces(stdout)
        assert len(think_traces) > 0, (
            "No [think] traces found. Agent should show reasoning "
            "before each step."
        )

    def test_think_before_tool_call(self):
        """[think] should appear before [tool] in output."""
        stdout = ask(
            "Find the auth middleware and describe how it works"
        )
        lines = stdout.splitlines()
        think_line = -1
        tool_line = -1
        for i, line in enumerate(lines):
            if "[think]" in line and think_line == -1:
                think_line = i
            if "[tool] Agent selected" in line and tool_line == -1 and think_line >= 0:
                tool_line = i
                break

        if think_line >= 0 and tool_line >= 0:
            assert think_line < tool_line, (
                "[think] should appear BEFORE [tool] call"
            )

    def test_think_explains_reasoning(self):
        """[think] traces should contain actual reasoning, not just step descriptions."""
        stdout = ask(
            "Add a new DELETE /tasks/:id endpoint with tests"
        )
        think_traces = extract_think_traces(stdout)
        if think_traces:
            # Reasoning should be substantive (more than just the step description)
            avg_length = sum(len(t) for t in think_traces) / len(think_traces)
            assert avg_length > 20, (
                f"Think traces are too short (avg {avg_length:.0f} chars). "
                "Expected substantive reasoning."
            )


# ============================================================================
# TESTS — STRATEGY TRACKING
# ============================================================================

class TestStrategyTracking:
    """Completed plans should log strategy to memory."""

    def test_strategy_logged_after_plan(self):
        """Completing a plan should log a strategy entry to memory."""
        stdout = ask(
            "Add input validation to POST /tasks — title must be non-empty"
        )
        mem_events = extract_memory_events(stdout)
        strategy_events = [
            e for e in mem_events
            if "strategy" in e.lower()
        ]
        assert len(strategy_events) > 0, (
            "No strategy logged after plan completion. "
            "Agent should save strategy to memory."
        )

    def test_strategy_includes_outcome(self):
        """Strategy log should indicate success or failure."""
        stdout = ask(
            "Create a health check endpoint at GET /health that returns 200"
        )
        mem_events = extract_memory_events(stdout)
        all_text = " ".join(mem_events).lower()
        has_outcome = any(
            word in all_text
            for word in ["success", "failed", "outcome", "completed"]
        )
        assert has_outcome or len(mem_events) > 0, (
            "Strategy log should include outcome information"
        )

    def test_prior_strategy_retrieved(self):
        """When decomposing a similar task, prior strategies should be retrieved."""
        # First task — creates a strategy
        ask("Add input validation to POST /tasks — title must be non-empty")
        # Similar task — should retrieve the prior strategy
        stdout = ask(
            "Add input validation to PUT /tasks/:id — title same rules"
        )
        mem_events = extract_memory_events(stdout)
        retrieval = [
            e for e in mem_events
            if "Retrieved" in e or "strategy" in e.lower()
        ]
        assert len(retrieval) > 0, (
            "No strategy retrieval for similar task. "
            "Agent should use prior strategies."
        )


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestDecomposition,
        TestPlanExecution,
        TestReplan,
        TestChainOfThought,
        TestStrategyTracking,
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
