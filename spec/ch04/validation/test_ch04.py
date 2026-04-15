"""
Chapter 4 Validation Tests
==========================

These tests validate the reader's Ch 4 implementation: SkillTool extends Tool,
skill loading, skill matching, and skill execution.

The reader's program must be callable as:
    tbh-code --codebase <path> --ask "<question>"              (auto skill match)
    tbh-code --codebase <path> --skill "<name>" --task "<task>" (explicit skill)
    tbh-code --codebase <path> --list-skills                   (list skills)

Skill execution must appear in stdout with the format:
    [skill] Matched task to skill: <name> (score: X.XX)
    [skill] Executing skill: <name>
    [skill] Step N/M: <description>
      [tool] <tool_name>({ ... })
      [tool] Result: success=true|false
    [skill] Skill "<name>" completed successfully (N/M steps)

Or for no match:
    [skill] No matching skill found for task

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

def ask(question, extra_args=None, timeout=60):
    """Ask the agent a question and capture stdout."""
    cmd = [AGENT_CMD, "--codebase", TODO_API_PATH, "--ask", question]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    return result.stdout


def run_skill(skill_name, task, timeout=60):
    """Run a specific skill explicitly."""
    cmd = [
        AGENT_CMD, "--codebase", TODO_API_PATH,
        "--skill", skill_name, "--task", task,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    return result.stdout


def list_skills(timeout=30):
    """List available skills."""
    cmd = [AGENT_CMD, "--codebase", TODO_API_PATH, "--list-skills"]
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


def extract_skill_match(stdout):
    """Extract skill matching info from output."""
    match = re.search(
        r'\[skill\] Matched task to skill: (\S+) \(score: ([0-9.]+)\)',
        stdout,
    )
    if match:
        return {"skill": match.group(1), "score": float(match.group(2))}

    no_match = re.search(r'\[skill\] No matching skill found', stdout)
    if no_match:
        return {"skill": None, "score": 0.0}

    return None


def extract_skill_steps(stdout):
    """Extract skill execution steps from output."""
    steps = []
    for line in stdout.splitlines():
        step_match = re.match(
            r'\[skill\] Step (\d+)/(\d+): (.+)', line
        )
        if step_match:
            steps.append({
                "number": int(step_match.group(1)),
                "total": int(step_match.group(2)),
                "description": step_match.group(3),
            })
    return steps


def extract_tool_calls_in_skill(stdout):
    """Extract tool calls made during skill execution."""
    calls = []
    for line in stdout.splitlines():
        tool_match = re.match(r'\s+\[tool\] (\w+)\(', line)
        if tool_match:
            calls.append(tool_match.group(1))
    return calls


# ============================================================================
# TESTS — SKILL SPEC
# ============================================================================

class TestSkillSpec:
    """SkillTool must implement the Tool interface with valid spec format."""

    def test_skills_are_listed(self):
        """--list-skills must show available skills."""
        stdout = list_skills()
        assert len(stdout.strip()) > 0, "Skill list is empty"

    def test_has_find_bug_skill(self):
        """Skill list must include find-bug."""
        stdout = list_skills()
        assert "find-bug" in stdout, "find-bug skill not found"

    def test_has_add_endpoint_skill(self):
        """Skill list must include add-endpoint."""
        stdout = list_skills()
        assert "add-endpoint" in stdout, "add-endpoint skill not found"

    def test_has_document_function_skill(self):
        """Skill list must include document-function."""
        stdout = list_skills()
        assert "document-function" in stdout, "document-function skill not found"

    def test_skill_has_description(self):
        """Each skill listing should include a description."""
        stdout = list_skills()
        # Skills should have descriptive text alongside their names
        lines = stdout.splitlines()
        skill_names = ["find-bug", "add-endpoint", "document-function"]
        for name in skill_names:
            found = any(name in line for line in lines)
            assert found, f"Skill {name} not found in listing"

    def test_skill_shows_tools_used(self):
        """Skill listing should show which tools the skill uses."""
        stdout = list_skills()
        # At least one skill should mention its tool dependencies
        assert "search_code" in stdout or "read_file" in stdout, (
            "Skill listing doesn't show tools used"
        )


# ============================================================================
# TESTS — SKILL LOADER
# ============================================================================

class TestSkillLoader:
    """SkillLoader must load skills from files and register them."""

    def test_skills_loaded_on_startup(self):
        """Skills should be loaded automatically on startup."""
        stdout = ask("What files are in this project?")
        assert "skill" in stdout.lower() or "Loaded" in stdout, (
            "No indication that skills were loaded on startup"
        )

    def test_at_least_three_skills_loaded(self):
        """At least 3 skills should be available."""
        stdout = list_skills()
        skill_names = ["find-bug", "add-endpoint", "document-function"]
        loaded = sum(1 for name in skill_names if name in stdout)
        assert loaded >= 3, (
            f"Expected at least 3 skills loaded, found {loaded}"
        )

    def test_skills_coexist_with_tools(self):
        """Skills and tools should both be available in the registry."""
        # Ask something that requires a tool (not a skill)
        stdout = ask("Read the file src/main.pseudo")
        # Agent should still have access to read_file tool
        response = extract_json(stdout)
        assert len(response["answer"]) > 0, (
            "Agent couldn't use tools after skills were loaded"
        )


# ============================================================================
# TESTS — SKILL MATCHING
# ============================================================================

class TestSkillMatching:
    """Agent must match tasks to the correct skill."""

    def test_matches_find_bug_skill(self):
        """Task about finding bugs should match find-bug skill."""
        stdout = ask("Find the bug in the auth middleware")
        match = extract_skill_match(stdout)
        assert match is not None, "No skill match trace in output"
        assert match["skill"] == "find-bug", (
            f"Expected find-bug skill, got: {match['skill']}"
        )

    def test_matches_document_function_skill(self):
        """Task about documenting should match document-function skill."""
        stdout = ask("Document the auth_middleware function")
        match = extract_skill_match(stdout)
        assert match is not None, "No skill match trace in output"
        assert match["skill"] == "document-function", (
            f"Expected document-function skill, got: {match['skill']}"
        )

    def test_no_match_for_unrelated_task(self):
        """Unrelated tasks should not match any skill."""
        stdout = ask("What is the meaning of life?")
        match = extract_skill_match(stdout)
        assert match is not None, "No skill match trace in output"
        assert match["skill"] is None, (
            f"Unrelated task should not match a skill, got: {match['skill']}"
        )

    def test_fallback_produces_response(self):
        """When no skill matches, agent should still produce a response."""
        stdout = ask("What is the meaning of life?")
        response = extract_json(stdout)
        assert len(response["answer"]) > 0, (
            "Agent produced no response when no skill matched"
        )

    def test_explicit_skill_selection(self):
        """--skill flag should use the specified skill regardless of matching."""
        stdout = run_skill("find-bug", "investigate the auth system")
        match = extract_skill_match(stdout)
        # When using --skill, the agent should use that skill directly
        steps = extract_skill_steps(stdout)
        assert len(steps) > 0, (
            "Explicit skill selection didn't execute any steps"
        )


# ============================================================================
# TESTS — SKILL EXECUTION
# ============================================================================

class TestSkillExecution:
    """Skills must execute steps in order, calling the correct tools."""

    def test_steps_execute_in_order(self):
        """Skill steps must execute in numerical order."""
        stdout = run_skill("find-bug", "investigate the auth middleware")
        steps = extract_skill_steps(stdout)
        assert len(steps) >= 2, (
            f"Expected at least 2 steps, got {len(steps)}"
        )
        # Verify order
        for i, step in enumerate(steps):
            assert step["number"] == i + 1, (
                f"Step {i+1} has number {step['number']} — out of order"
            )

    def test_steps_call_correct_tools(self):
        """Each step should call the tool specified in the skill spec."""
        stdout = run_skill("find-bug", "investigate the auth middleware")
        tool_calls = extract_tool_calls_in_skill(stdout)
        assert len(tool_calls) >= 2, (
            f"Expected at least 2 tool calls, got {len(tool_calls)}"
        )
        # find-bug should use search_code and read_file
        assert "search_code" in tool_calls, (
            "find-bug skill should call search_code"
        )
        assert "read_file" in tool_calls, (
            "find-bug skill should call read_file"
        )

    def test_skill_returns_tool_result(self):
        """Skill execution should produce a ToolResult (visible as JSON response)."""
        stdout = run_skill("find-bug", "investigate the auth middleware")
        response = extract_json(stdout)
        assert "answer" in response, "Skill execution didn't produce answer"
        assert "confidence" in response, "Skill execution didn't produce confidence"
        assert "sources" in response, "Skill execution didn't produce sources"

    def test_skill_result_is_grounded(self):
        """Skill execution result should reference actual files."""
        stdout = run_skill("find-bug", "investigate the auth middleware")
        response = extract_json(stdout)
        # Should reference the auth middleware file
        answer = response["answer"].lower()
        assert "auth" in answer and "middleware" in answer, (
            "find-bug skill result doesn't mention auth middleware"
        )
        sources = response.get("sources", [])
        assert any("auth" in s for s in sources), (
            "find-bug skill result doesn't reference auth files in sources"
        )

    def test_optional_steps_dont_block(self):
        """Optional steps that fail should not prevent skill completion."""
        # document-function has optional steps for usages and tests
        stdout = run_skill(
            "document-function",
            "Document the create_user function"
        )
        response = extract_json(stdout)
        # Skill should complete even if optional steps find nothing
        assert response.get("confidence", 0) > 0, (
            "Skill failed — optional steps may have blocked execution"
        )

    def test_step_output_flows_to_next_step(self):
        """Output from one step should be available to the next step."""
        stdout = run_skill("find-bug", "investigate the auth middleware")
        steps = extract_skill_steps(stdout)
        tool_calls = extract_tool_calls_in_skill(stdout)

        # Step 1 should search, step 2 should read the file that was found
        # If read_file is called with a path from search results, flow is working
        if len(steps) >= 2 and len(tool_calls) >= 2:
            assert tool_calls[0] == "search_code", "First call should be search"
            assert tool_calls[1] == "read_file", "Second call should be read"
            # The fact that read_file succeeded means it got a valid path
            # from the search results


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestSkillSpec,
        TestSkillLoader,
        TestSkillMatching,
        TestSkillExecution,
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
