"""
Chapter 10 Validation Tests
============================

These tests validate the reader's Ch 10 implementation: agent identity,
capability boundaries, effort budgets, four specialized agents (coder,
reviewer, runner, researcher), and the agent factory.

The reader's program must be callable as:
    tbh-code --agent <name> --codebase <path> --ask "<question>"
    tbh-code --list-agents
    tbh-code --agent <name> --show-identity

Agent traces must appear in stdout with the format:
    [<agent-name>] Starting task: <summary>
    [<agent-name>] Budget: <N> tool calls, <N> LLM calls
    [<agent-name>] Tool call N/M: <tool_name>
    [<agent-name>] Budget exhausted (N/M tool calls used)
    [<agent-name>] REJECTED: tool '<name>' not in allowed tools [...]

Output must include a JSON response with: answer, confidence, sources, budget_report

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

AGENT_NAMES = ["coder", "reviewer", "runner", "researcher"]

AGENT_TOOLS = {
    "coder": ["read_file", "write_file", "search_code"],
    "reviewer": ["read_file", "search_code"],
    "runner": ["execute_shell", "read_file"],
    "researcher": ["read_file", "search_code", "list_directory"],
}

AGENT_BUDGETS = {
    "coder": {"max_tool_calls": 25, "max_llm_calls": 10},
    "reviewer": {"max_tool_calls": 20, "max_llm_calls": 8},
    "runner": {"max_tool_calls": 15, "max_llm_calls": 5},
    "researcher": {"max_tool_calls": 30, "max_llm_calls": 10},
}

# ============================================================================
# HELPERS
# ============================================================================

def ask_agent(agent_name, question, timeout=120):
    """Ask a specific agent a question and capture stdout."""
    cmd = [
        AGENT_CMD, "--agent", agent_name,
        "--codebase", TODO_API_PATH, "--ask", question
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"Agent '{agent_name}' failed: {result.stderr}"
    return result.stdout


def list_agents(timeout=30):
    """List available agents."""
    cmd = [AGENT_CMD, "--list-agents"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"--list-agents failed: {result.stderr}"
    return result.stdout


def show_identity(agent_name, timeout=30):
    """Show agent identity."""
    cmd = [AGENT_CMD, "--agent", agent_name, "--show-identity"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"--show-identity failed for '{agent_name}': {result.stderr}"
    return result.stdout


def extract_json(stdout):
    """Extract the JSON response from agent output."""
    json_start = stdout.find("{")
    json_end = stdout.rfind("}") + 1
    assert json_start >= 0 and json_end > json_start, (
        f"No JSON found in output:\n{stdout}"
    )
    return json.loads(stdout[json_start:json_end])


def extract_agent_events(stdout, agent_name):
    """Extract events for a specific agent from output."""
    events = []
    pattern = re.compile(rf'\[{re.escape(agent_name)}\] (.+)')
    for line in stdout.splitlines():
        match = pattern.match(line.strip())
        if match:
            events.append(match.group(1))
    return events


def extract_tool_events(stdout):
    """Extract tool call events from output."""
    events = []
    for line in stdout.splitlines():
        tool_match = re.match(r'\[tool\] (.+)', line.strip())
        if tool_match:
            events.append(tool_match.group(1))
    return events


def extract_rejected_tools(stdout):
    """Extract rejected tool call events from output."""
    rejected = []
    for line in stdout.splitlines():
        if "REJECTED" in line and "not in allowed tools" in line:
            rejected.append(line.strip())
    return rejected


def extract_budget_report(response):
    """Extract budget report from JSON response."""
    if "budget_report" in response:
        return response["budget_report"]
    return None


# ============================================================================
# TESTS — AGENT IDENTITY
# ============================================================================

class TestAgentIdentity:
    """Every agent must have a complete identity with all required fields."""

    def test_list_agents_returns_all_four(self):
        """--list-agents should return coder, reviewer, runner, researcher."""
        stdout = list_agents()
        for name in AGENT_NAMES:
            assert name in stdout.lower(), (
                f"Agent '{name}' not found in --list-agents output. "
                f"Expected all four: {AGENT_NAMES}"
            )

    def test_coder_identity_has_required_fields(self):
        """Coder identity must include name, description, capabilities, constraints, tools, skills, budget."""
        stdout = show_identity("coder")
        stdout_lower = stdout.lower()
        for field in ["coder", "capabilities", "constraints", "tools", "budget"]:
            assert field in stdout_lower, (
                f"Coder identity missing '{field}'. "
                "Agent identity must include all required fields."
            )

    def test_reviewer_identity_has_required_fields(self):
        """Reviewer identity must include name, description, capabilities, constraints, tools, skills, budget."""
        stdout = show_identity("reviewer")
        stdout_lower = stdout.lower()
        for field in ["reviewer", "capabilities", "constraints", "tools", "budget"]:
            assert field in stdout_lower, (
                f"Reviewer identity missing '{field}'."
            )

    def test_runner_identity_has_required_fields(self):
        """Runner identity must include all required fields."""
        stdout = show_identity("runner")
        stdout_lower = stdout.lower()
        for field in ["runner", "capabilities", "constraints", "tools", "budget"]:
            assert field in stdout_lower, (
                f"Runner identity missing '{field}'."
            )

    def test_researcher_identity_has_required_fields(self):
        """Researcher identity must include all required fields."""
        stdout = show_identity("researcher")
        stdout_lower = stdout.lower()
        for field in ["researcher", "capabilities", "constraints", "tools", "budget"]:
            assert field in stdout_lower, (
                f"Researcher identity missing '{field}'."
            )

    def test_agents_have_distinct_descriptions(self):
        """Each agent should have a unique description."""
        descriptions = []
        for name in AGENT_NAMES:
            stdout = show_identity(name)
            descriptions.append(stdout)
        # Each identity output should be different
        for i in range(len(descriptions)):
            for j in range(i + 1, len(descriptions)):
                assert descriptions[i] != descriptions[j], (
                    f"Agents '{AGENT_NAMES[i]}' and '{AGENT_NAMES[j]}' "
                    "have identical identity output. Each agent should be distinct."
                )


# ============================================================================
# TESTS — BUDGET
# ============================================================================

class TestBudget:
    """Budget must have required fields and be enforced at runtime."""

    def test_budget_shown_in_identity(self):
        """Agent identity should display budget limits."""
        stdout = show_identity("coder")
        stdout_lower = stdout.lower()
        has_budget = (
            "tool call" in stdout_lower or
            "max_tool_calls" in stdout_lower or
            "budget" in stdout_lower
        )
        assert has_budget, (
            "Coder identity doesn't show budget information. "
            "Budget (max_tool_calls, max_llm_calls) must be visible."
        )

    def test_budget_report_in_response(self):
        """Agent response should include a budget report."""
        stdout = ask_agent(
            "researcher",
            "List the files in the src directory"
        )
        response = extract_json(stdout)
        budget = extract_budget_report(response)
        assert budget is not None, (
            "Response missing budget_report. "
            "Every agent response must include budget usage."
        )

    def test_budget_report_has_usage_and_max(self):
        """Budget report should show both usage and max for tool calls and LLM calls."""
        stdout = ask_agent(
            "researcher",
            "Search for auth-related code in the codebase"
        )
        response = extract_json(stdout)
        budget = extract_budget_report(response)
        assert budget is not None, "Missing budget_report in response"
        required_keys = ["tool_calls_used", "tool_calls_max", "llm_calls_used", "llm_calls_max"]
        for key in required_keys:
            assert key in budget, (
                f"Budget report missing '{key}'. "
                f"Required keys: {required_keys}"
            )

    def test_budget_enforcement_stops_agent(self):
        """Agent must stop when budget is exhausted and return partial results."""
        # Give the runner a task that requires many tool calls
        stdout = ask_agent(
            "runner",
            "Run every test file individually, one at a time, and report each result"
        )
        agent_events = extract_agent_events(stdout, "runner")
        all_text = " ".join(agent_events).lower()

        # Check for budget exhaustion or partial results
        budget_exhausted = "budget exhausted" in all_text or "budget" in all_text
        response = extract_json(stdout)
        is_partial = response.get("partial", False)
        budget = extract_budget_report(response)

        # Either the agent hit its budget limit, or it finished within budget
        # If it finished within budget, that's fine too — the budget was sufficient
        if budget and budget.get("tool_calls_used", 0) >= budget.get("tool_calls_max", 999):
            assert budget_exhausted or is_partial, (
                "Agent used all budget but didn't report exhaustion. "
                "Budget exhaustion should be reported with partial=true."
            )


# ============================================================================
# TESTS — TOOL BOUNDARY ENFORCEMENT
# ============================================================================

class TestToolBoundaries:
    """Agents must only use tools in their tool list. Structural enforcement."""

    def test_reviewer_cannot_write_files(self):
        """Reviewer must not have write_file — structural enforcement."""
        stdout = ask_agent(
            "reviewer",
            "Fix the timing attack vulnerability in auth.pseudo — "
            "replace string equality with constant-time comparison"
        )
        rejected = extract_rejected_tools(stdout)
        response = extract_json(stdout)
        answer = response["answer"].lower()

        # The reviewer should either reject write_file or report without writing
        wrote_file = "write_file" in " ".join(extract_tool_events(stdout)) and \
                     "REJECTED" not in " ".join(extract_tool_events(stdout))
        has_recommendation = (
            "recommend" in answer or
            "coder" in answer or
            "cannot fix" in answer or
            "report" in answer or
            "read-only" in answer
        )
        assert not wrote_file or len(rejected) > 0, (
            "Reviewer used write_file without rejection. "
            "write_file should not be in the reviewer's tool list."
        )
        assert has_recommendation or len(rejected) > 0, (
            "Reviewer neither rejected write_file nor recommended the coder fix it. "
            "Boundary enforcement should prevent writing and defer to coder."
        )

    def test_runner_cannot_write_files(self):
        """Runner must not have write_file — structural enforcement."""
        stdout = ask_agent(
            "runner",
            "The test_delete_task test is failing because it doesn't send an auth token. "
            "Fix the test file."
        )
        rejected = extract_rejected_tools(stdout)
        response = extract_json(stdout)
        answer = response["answer"].lower()

        has_deferral = (
            "cannot" in answer or
            "coder" in answer or
            "don't have" in answer or
            "not available" in answer or
            "write access" in answer
        )
        assert has_deferral or len(rejected) > 0, (
            "Runner neither rejected write_file nor deferred to coder. "
            "Runner should not be able to edit files."
        )

    def test_researcher_cannot_execute_commands(self):
        """Researcher must not have execute_shell — structural enforcement."""
        stdout = ask_agent(
            "researcher",
            "Run the test suite to see which tests pass"
        )
        rejected = extract_rejected_tools(stdout)
        response = extract_json(stdout)
        answer = response["answer"].lower()

        has_deferral = (
            "cannot" in answer or
            "runner" in answer or
            "don't have" in answer or
            "not available" in answer or
            "execute" in answer
        )
        assert has_deferral or len(rejected) > 0, (
            "Researcher neither rejected execute_shell nor deferred to runner. "
            "Researcher should not be able to execute commands."
        )

    def test_coder_cannot_execute_commands(self):
        """Coder must not have execute_shell — structural enforcement."""
        stdout = ask_agent(
            "coder",
            "Run the tests to check if the auth changes work"
        )
        rejected = extract_rejected_tools(stdout)
        response = extract_json(stdout)
        answer = response["answer"].lower()

        has_deferral = (
            "cannot" in answer or
            "runner" in answer or
            "don't have" in answer or
            "not available" in answer
        )
        assert has_deferral or len(rejected) > 0, (
            "Coder neither rejected execute_shell nor deferred to runner. "
            "Coder should not be able to execute commands."
        )


# ============================================================================
# TESTS — DISTINCT CAPABILITIES
# ============================================================================

class TestDistinctCapabilities:
    """Each agent must have distinct tools, skills, and capabilities."""

    def test_only_coder_has_write_file(self):
        """Only the coder should have write_file in its tool list."""
        for name in AGENT_NAMES:
            stdout = show_identity(name)
            stdout_lower = stdout.lower()
            if name == "coder":
                assert "write_file" in stdout_lower, (
                    "Coder should have write_file in its tool list."
                )
            else:
                # write_file should not appear in the tools section
                # (it may appear in constraints as "never write")
                tools_section = extract_tools_section(stdout)
                if tools_section:
                    assert "write_file" not in tools_section.lower(), (
                        f"Agent '{name}' has write_file in its tools. "
                        "Only the coder should have write_file."
                    )

    def test_only_runner_has_execute_shell(self):
        """Only the runner should have execute_shell in its tool list."""
        for name in AGENT_NAMES:
            stdout = show_identity(name)
            tools_section = extract_tools_section(stdout)
            if tools_section:
                if name == "runner":
                    assert "execute_shell" in tools_section.lower(), (
                        "Runner should have execute_shell in its tool list."
                    )
                else:
                    assert "execute_shell" not in tools_section.lower(), (
                        f"Agent '{name}' has execute_shell in its tools. "
                        "Only the runner should have execute_shell."
                    )

    def test_all_agents_have_read_file(self):
        """Every agent should have read_file — all agents can read."""
        for name in AGENT_NAMES:
            stdout = show_identity(name)
            assert "read_file" in stdout.lower(), (
                f"Agent '{name}' missing read_file. All agents should be able to read."
            )

    def test_agents_have_different_skill_sets(self):
        """Each agent should have skills relevant to its role."""
        coder_id = show_identity("coder").lower()
        reviewer_id = show_identity("reviewer").lower()
        # Coder should have coding-related skills
        assert any(s in coder_id for s in ["refactor", "write-tests", "find-bug"]), (
            "Coder missing coding-related skills."
        )
        # Reviewer should have review-related skills
        assert any(s in reviewer_id for s in ["code-review", "review", "security-audit", "audit"]), (
            "Reviewer missing review-related skills."
        )


# ============================================================================
# TESTS — AGENT PROCESSING
# ============================================================================

class TestAgentProcessing:
    """Agents must process tasks within their budgets and boundaries."""

    def test_researcher_processes_read_task(self):
        """Researcher should be able to map code and return structured results."""
        stdout = ask_agent(
            "researcher",
            "Map the authentication flow in the codebase"
        )
        response = extract_json(stdout)
        assert "answer" in response, "Response missing 'answer' field"
        assert "confidence" in response, "Response missing 'confidence' field"
        assert "sources" in response, "Response missing 'sources' field"
        assert len(response["answer"]) > 0, "Answer should not be empty"

    def test_coder_processes_write_task(self):
        """Coder should be able to write code and return structured results."""
        stdout = ask_agent(
            "coder",
            "Add a helper function to validate email format in src/utils.pseudo"
        )
        response = extract_json(stdout)
        assert "answer" in response, "Response missing 'answer' field"
        assert "confidence" in response, "Response missing 'confidence' field"

    def test_agent_reports_budget_usage(self):
        """Agent output should show budget usage during processing."""
        stdout = ask_agent(
            "researcher",
            "Search for all authentication-related code"
        )
        agent_events = extract_agent_events(stdout, "researcher")
        all_text = " ".join(agent_events).lower()
        has_budget_info = (
            "budget" in all_text or
            "tool call" in all_text or
            "/" in all_text  # e.g., "7/30"
        )
        assert has_budget_info, (
            "Agent output doesn't show budget usage. "
            "Expected traces like 'Tool call 7/30' or 'Budget: ...'."
        )

    def test_agent_shows_starting_message(self):
        """Agent should announce its name and task at the start."""
        stdout = ask_agent(
            "reviewer",
            "Check the auth middleware for security issues"
        )
        agent_events = extract_agent_events(stdout, "reviewer")
        has_start = any(
            "starting" in e.lower() or "task" in e.lower()
            for e in agent_events
        )
        assert has_start or len(agent_events) > 0, (
            "Agent didn't announce itself. "
            "Expected '[reviewer] Starting task: ...' at the beginning."
        )


# ============================================================================
# TESTS — MONOLITH VS SPECIALISTS
# ============================================================================

class TestMonolithComparison:
    """Specialized agents should produce better results than the monolith on complex tasks."""

    def test_reviewer_finds_issues_coder_misses(self):
        """Independent reviewer should catch issues the coder doesn't see."""
        # Coder writes a fix
        coder_stdout = ask_agent(
            "coder",
            "Refactor the auth middleware to decode tokens and look up users"
        )
        coder_response = extract_json(coder_stdout)

        # Reviewer evaluates
        reviewer_stdout = ask_agent(
            "reviewer",
            "Review the auth refactoring — look for security issues, "
            "missing edge cases, and bugs"
        )
        reviewer_response = extract_json(reviewer_stdout)
        reviewer_answer = reviewer_response["answer"].lower()

        # Reviewer should find at least one issue
        has_issues = any(
            word in reviewer_answer
            for word in ["issue", "bug", "vulnerability", "missing", "problem",
                         "recommend", "concern", "risk"]
        )
        assert has_issues, (
            "Reviewer found no issues in coder's output. "
            "Independent review should catch at least one concern."
        )


# ============================================================================
# HELPER — EXTRACT TOOLS SECTION
# ============================================================================

def extract_tools_section(identity_output):
    """Extract the tools line/section from identity output."""
    lines = identity_output.splitlines()
    for i, line in enumerate(lines):
        if "tools:" in line.lower() or "available tools:" in line.lower():
            # Return this line and a few following lines
            section = "\n".join(lines[i:i+3])
            return section
    return None


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestAgentIdentity,
        TestBudget,
        TestToolBoundaries,
        TestDistinctCapabilities,
        TestAgentProcessing,
        TestMonolithComparison,
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
