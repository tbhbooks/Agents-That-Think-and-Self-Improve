"""
Chapter 1 Validation Tests
==========================

These tests validate the reader's Ch 1 implementation.

The reader's program must be callable as:
    tbh-code --mode oneshot --task "<task>"
    tbh-code --mode loop --task "<task>" --max-iterations <n>

Output is captured from stdout. The agent loop mode must include trace lines
with the format:
    [loop] Iteration N:
    [observe] ...
    [think] ...
    [act] ...
    [reflect] confidence=X.X, issues=[...]
    [loop] Result after N iterations:

Adjust AGENT_CMD below to match the reader's implementation.
"""

import subprocess
import re
import json
import sys

# ============================================================================
# CONFIGURATION — reader adjusts this to their implementation
# ============================================================================

AGENT_CMD = "tbh-code"  # or "python tbh_code.py", "go run .", "cargo run", etc.

TASK = (
    "Find the security vulnerability in the todo-api authentication system. "
    "Identify the file, the function, and explain what's wrong."
)

# ============================================================================
# HELPERS
# ============================================================================

def run_agent(mode, task, max_iterations=5, timeout=60):
    """Run the agent and capture stdout."""
    cmd = [AGENT_CMD, "--mode", mode, "--task", task]
    if mode == "loop":
        cmd += ["--max-iterations", str(max_iterations)]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout, result.stderr, result.returncode


def parse_loop_output(stdout):
    """Parse agent loop output into structured data."""
    iterations = []
    current_iteration = None

    for line in stdout.splitlines():
        # Match iteration start
        iter_match = re.match(r'\[loop\] Iteration (\d+):', line)
        if iter_match:
            if current_iteration:
                iterations.append(current_iteration)
            current_iteration = {
                "number": int(iter_match.group(1)),
                "phases": {},
            }
            continue

        # Match phase lines
        for phase in ["observe", "think", "act", "reflect"]:
            phase_match = re.match(rf'\s*\[{phase}\]\s*(.*)', line)
            if phase_match and current_iteration:
                current_iteration["phases"][phase] = phase_match.group(1)

        # Match confidence in reflect
        conf_match = re.search(r'confidence=([0-9.]+)', line)
        if conf_match and current_iteration:
            current_iteration["confidence"] = float(conf_match.group(1))

    if current_iteration:
        iterations.append(current_iteration)

    # Extract final result
    final_result = ""
    result_started = False
    for line in stdout.splitlines():
        if re.match(r'\[loop\] Result after', line):
            result_started = True
            continue
        if result_started:
            final_result += line + "\n"

    return iterations, final_result.strip()


# ============================================================================
# TESTS — ONE-SHOT MODE
# ============================================================================

class TestOneShot:
    """Tests for the one-shot wrapper (Program 1)."""

    def test_produces_response(self):
        """One-shot mode must produce a non-empty response."""
        stdout, stderr, code = run_agent("oneshot", TASK)
        assert code == 0, f"Agent exited with code {code}: {stderr}"
        assert len(stdout.strip()) > 0, "One-shot produced empty output"

    def test_response_is_confident(self):
        """One-shot response should NOT contain hedging about its own limitations.
        (This validates the confidence illusion — the one-shot doesn't know
        what it doesn't know.)"""
        stdout, _, _ = run_agent("oneshot", TASK)
        response = stdout.lower()
        # One-shot typically does NOT say "I can't verify" or "I don't have access"
        # It just answers confidently (which is the problem)
        limitation_phrases = [
            "i cannot verify",
            "i don't have access",
            "without reading the code",
            "i would need to see",
        ]
        # If the one-shot is honest about limitations, that's fine too —
        # but it's not the expected behavior. We just note it.
        has_limitations = any(phrase in response for phrase in limitation_phrases)
        if has_limitations:
            print("NOTE: One-shot was unexpectedly honest about limitations. "
                  "This is unusual — most LLMs hallucinate confidently.")


# ============================================================================
# TESTS — AGENT LOOP MODE
# ============================================================================

class TestAgentLoop:
    """Tests for the agent loop (Program 2)."""

    def test_produces_response(self):
        """Agent loop must produce a non-empty final result."""
        stdout, stderr, code = run_agent("loop", TASK)
        assert code == 0, f"Agent exited with code {code}: {stderr}"
        iterations, result = parse_loop_output(stdout)
        assert len(result) > 0, "Agent loop produced empty final result"

    def test_iterates_at_least_once(self):
        """Agent loop must execute at least 2 iterations (the first to answer,
        the second to reflect and potentially improve)."""
        stdout, _, _ = run_agent("loop", TASK)
        iterations, _ = parse_loop_output(stdout)
        assert len(iterations) >= 2, (
            f"Agent loop ran only {len(iterations)} iteration(s). "
            "Must iterate at least twice to demonstrate the reflect phase."
        )

    def test_does_not_exceed_max_iterations(self):
        """Agent loop must respect the max_iterations parameter."""
        max_iter = 3
        stdout, _, _ = run_agent("loop", TASK, max_iterations=max_iter)
        iterations, _ = parse_loop_output(stdout)
        assert len(iterations) <= max_iter, (
            f"Agent loop ran {len(iterations)} iterations, "
            f"exceeding max_iterations={max_iter}"
        )

    def test_has_all_four_phases(self):
        """Each iteration must include observe, think, act, and reflect phases."""
        stdout, _, _ = run_agent("loop", TASK)
        iterations, _ = parse_loop_output(stdout)
        required_phases = {"observe", "think", "act", "reflect"}
        for iteration in iterations:
            present = set(iteration["phases"].keys())
            missing = required_phases - present
            assert not missing, (
                f"Iteration {iteration['number']} missing phases: {missing}"
            )

    def test_reflect_includes_confidence(self):
        """The reflect phase must output a confidence score."""
        stdout, _, _ = run_agent("loop", TASK)
        iterations, _ = parse_loop_output(stdout)
        for iteration in iterations:
            assert "confidence" in iteration, (
                f"Iteration {iteration['number']} reflect phase "
                "missing confidence score"
            )
            assert 0.0 <= iteration["confidence"] <= 1.0, (
                f"Confidence {iteration['confidence']} not in [0.0, 1.0]"
            )

    def test_loop_terminates_before_max(self):
        """With max_iterations=10, the loop should converge before hitting the
        limit (for this task, without tools, ~2-4 iterations is expected)."""
        stdout, _, _ = run_agent("loop", TASK, max_iterations=10)
        iterations, _ = parse_loop_output(stdout)
        assert len(iterations) < 10, (
            "Agent loop hit max_iterations=10. Expected convergence before "
            "that — the reflect phase should recognize it can't improve "
            "without tools."
        )

    def test_final_answer_is_less_hallucinated(self):
        """The final answer should be more cautious than a typical one-shot.
        Check for limitation-awareness language."""
        stdout, _, _ = run_agent("loop", TASK)
        _, result = parse_loop_output(stdout)
        result_lower = result.lower()

        # The loop agent should express SOME awareness of its limitations
        awareness_phrases = [
            "cannot verify",
            "cannot confirm",
            "don't have access",
            "without reading",
            "without seeing",
            "without access",
            "would need to",
            "limited",
            "unable to confirm",
        ]
        has_awareness = any(phrase in result_lower for phrase in awareness_phrases)
        assert has_awareness, (
            "Agent loop final answer shows no awareness of its limitations. "
            "The reflect phase should have caught that it can't verify "
            "file names or function names without code access."
        )


# ============================================================================
# TESTS — COMPARISON
# ============================================================================

class TestComparison:
    """Tests that compare one-shot vs loop behavior."""

    def test_loop_has_higher_final_confidence_than_initial(self):
        """The loop's final confidence should be >= its initial confidence,
        showing that iteration improved (or at least maintained) quality."""
        stdout, _, _ = run_agent("loop", TASK)
        iterations, _ = parse_loop_output(stdout)
        if len(iterations) >= 2:
            first_conf = iterations[0].get("confidence", 0)
            last_conf = iterations[-1].get("confidence", 0)
            assert last_conf >= first_conf, (
                f"Confidence decreased from {first_conf} to {last_conf}. "
                "The loop should improve or maintain confidence."
            )


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    # Simple test runner — readers can also use pytest
    test_classes = [TestOneShot, TestAgentLoop, TestComparison]
    passed = 0
    failed = 0
    errors = []

    for cls in test_classes:
        instance = cls()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                test_name = f"{cls.__name__}.{method_name}"
                try:
                    getattr(instance, method_name)()
                    print(f"  PASS  {test_name}")
                    passed += 1
                except AssertionError as e:
                    print(f"  FAIL  {test_name}: {e}")
                    failed += 1
                    errors.append((test_name, str(e)))
                except Exception as e:
                    print(f"  ERROR {test_name}: {e}")
                    failed += 1
                    errors.append((test_name, str(e)))

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    if errors:
        print(f"\nFailures:")
        for name, err in errors:
            print(f"  {name}: {err}")
    sys.exit(0 if failed == 0 else 1)
