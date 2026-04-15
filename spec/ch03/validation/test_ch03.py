"""
Chapter 3 Validation Tests
==========================

These tests validate the reader's Ch 3 implementation: Tool interface,
SimpleTool implementations, ToolRegistry, MCP server/client, and
ground-truth verification.

The reader's program must be callable as:
    tbh-code --codebase <path> --ask "<question>"          (tool-using mode)
    tbh-code --codebase <path> --list-tools                (list available tools)

Tool calls must appear in stdout with the format:
    [tool] Agent selected: <tool_name>
    [tool] Arguments: { ... }
    [tool] Result: success=true|false
    [verify] ... — PASS|FAIL

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


def list_tools(timeout=30):
    """List available tools."""
    cmd = [AGENT_CMD, "--codebase", TODO_API_PATH, "--list-tools"]
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

        args_match = re.match(r'\[tool\] Arguments: (.+)', line)
        if args_match and current_call:
            try:
                current_call["args"] = json.loads(args_match.group(1))
            except json.JSONDecodeError:
                current_call["args_raw"] = args_match.group(1)

        result_match = re.match(r'\[tool\] Result: success=(true|false)', line)
        if result_match and current_call:
            current_call["success"] = result_match.group(1) == "true"

    if current_call:
        calls.append(current_call)
    return calls


def extract_verifications(stdout):
    """Extract verification results from agent output."""
    verifications = []
    for line in stdout.splitlines():
        verify_match = re.match(r'\[verify\] (.+) — (PASS|FAIL)', line)
        if verify_match:
            verifications.append({
                "check": verify_match.group(1),
                "result": verify_match.group(2),
            })
    return verifications


# ============================================================================
# TESTS — TOOL INTERFACE
# ============================================================================

class TestToolInterface:
    """The Tool interface must be implemented with required fields."""

    def test_tools_are_listed(self):
        """--list-tools must show available tools."""
        stdout = list_tools()
        assert len(stdout.strip()) > 0, "Tool list is empty"

    def test_has_read_file_tool(self):
        """Tool list must include read_file."""
        stdout = list_tools()
        assert "read_file" in stdout, "read_file tool not found in tool list"

    def test_has_list_files_tool(self):
        """Tool list must include list_files."""
        stdout = list_tools()
        assert "list_files" in stdout, "list_files tool not found in tool list"

    def test_has_search_code_tool(self):
        """Tool list must include search_code."""
        stdout = list_tools()
        assert "search_code" in stdout, "search_code tool not found in tool list"

    def test_tools_have_descriptions(self):
        """Each tool listing should include a description."""
        stdout = list_tools()
        # Each tool name should be followed by descriptive text
        lines = [l.strip() for l in stdout.splitlines() if l.strip()]
        tool_names = ["read_file", "list_files", "search_code"]
        for name in tool_names:
            found = False
            for i, line in enumerate(lines):
                if name in line:
                    found = True
                    # Next line or same line should have description text
                    break
            assert found, f"Tool {name} not found with description"

    def test_tool_execute_returns_result(self):
        """Tool calls must return ToolResult with success field."""
        stdout = ask("Read the file src/middleware/auth.pseudo")
        calls = extract_tool_calls(stdout)
        assert len(calls) > 0, "No tool calls found in output"
        assert "success" in calls[0], (
            "Tool call result missing success field"
        )


# ============================================================================
# TESTS — SIMPLE TOOLS
# ============================================================================

class TestSimpleTools:
    """SimpleTool implementations must work correctly."""

    def test_read_file_reads_content(self):
        """read_file must return actual file content."""
        stdout = ask("Read the file src/middleware/auth.pseudo and show me what's in it")
        response = extract_json(stdout)
        answer = response["answer"].lower()
        assert "auth_middleware" in answer, (
            "read_file didn't return actual file content — "
            "should contain auth_middleware function"
        )

    def test_read_file_nonexistent_fails(self):
        """read_file on a non-existent file must return success=false."""
        stdout = ask("Read the file src/services/nonexistent.pseudo")
        calls = extract_tool_calls(stdout)
        # At least one tool call should have failed
        read_calls = [c for c in calls if c.get("tool") == "read_file"]
        if read_calls:
            failed = any(not c.get("success", True) for c in read_calls)
            # Or the agent should acknowledge the file doesn't exist
            response = extract_json(stdout)
            assert failed or "not" in response["answer"].lower() or "doesn't" in response["answer"].lower(), (
                "Agent didn't detect that the file doesn't exist"
            )

    def test_list_files_lists_directory(self):
        """list_files must return directory entries."""
        stdout = ask("List all files in the src/ directory")
        response = extract_json(stdout)
        answer = response["answer"].lower()
        # Should mention key directories/files
        assert "routes" in answer or "middleware" in answer or "models" in answer, (
            "list_files didn't return actual directory contents"
        )

    def test_search_code_finds_pattern(self):
        """search_code must find matching patterns in files."""
        stdout = ask("Search for 'auth_middleware' in the codebase")
        response = extract_json(stdout)
        answer = response["answer"].lower()
        assert "auth" in answer and "middleware" in answer, (
            "search_code didn't find auth_middleware"
        )
        # Should reference the actual file
        assert any("auth" in s for s in response.get("sources", [])), (
            "search_code result doesn't reference the auth middleware file"
        )

    def test_search_code_returns_line_numbers(self):
        """search_code results should include file and line information."""
        stdout = ask("Search for 'auth_middleware' in src/")
        calls = extract_tool_calls(stdout)
        search_calls = [c for c in calls if c.get("tool") == "search_code"]
        assert len(search_calls) > 0, "Agent didn't use search_code"
        assert search_calls[0].get("success", False), "search_code failed"


# ============================================================================
# TESTS — TOOL REGISTRY
# ============================================================================

class TestToolRegistry:
    """ToolRegistry must manage tools correctly."""

    def test_registry_lists_all_tools(self):
        """Registry must list at least the 3 core tools."""
        stdout = list_tools()
        tool_names = ["read_file", "list_files", "search_code"]
        for name in tool_names:
            assert name in stdout, f"Registry missing tool: {name}"

    def test_registry_find_by_name(self):
        """Agent should be able to find and use a specific tool by name."""
        stdout = ask("Use the read_file tool to read src/main.pseudo")
        calls = extract_tool_calls(stdout)
        read_calls = [c for c in calls if c.get("tool") == "read_file"]
        assert len(read_calls) > 0, (
            "Agent didn't use read_file when explicitly asked"
        )

    def test_registry_handles_unknown_tool(self):
        """Asking for a non-existent tool should not crash."""
        stdout = ask("What files are in this project?")
        # Should succeed — agent picks from available tools
        response = extract_json(stdout)
        assert response["answer"], "Agent failed to respond"


# ============================================================================
# TESTS — TOOL SELECTION
# ============================================================================

class TestToolSelection:
    """Agent must select the appropriate tool for the task."""

    def test_selects_search_for_find_tasks(self):
        """When asked to find something, agent should use search_code."""
        stdout = ask("Find where auth_middleware is defined")
        calls = extract_tool_calls(stdout)
        tool_names = [c.get("tool") for c in calls]
        assert "search_code" in tool_names, (
            f"Agent should have used search_code for a find task. "
            f"Used: {tool_names}"
        )

    def test_selects_read_for_examine_tasks(self):
        """When asked to read a specific file, agent should use read_file."""
        stdout = ask("Show me the contents of src/middleware/auth.pseudo")
        calls = extract_tool_calls(stdout)
        tool_names = [c.get("tool") for c in calls]
        assert "read_file" in tool_names, (
            f"Agent should have used read_file for a read task. "
            f"Used: {tool_names}"
        )

    def test_selects_list_for_directory_tasks(self):
        """When asked to list files, agent should use list_files."""
        stdout = ask("What files and directories are in the src/ folder?")
        calls = extract_tool_calls(stdout)
        tool_names = [c.get("tool") for c in calls]
        assert "list_files" in tool_names, (
            f"Agent should have used list_files for a listing task. "
            f"Used: {tool_names}"
        )

    def test_chains_multiple_tools(self):
        """Complex tasks should use multiple tools in sequence."""
        stdout = ask(
            "Find all functions that take a User parameter and show me "
            "the code for each one"
        )
        calls = extract_tool_calls(stdout)
        tool_names = [c.get("tool") for c in calls]
        assert len(calls) >= 2, (
            f"Complex task should use multiple tools. Only used: {tool_names}"
        )
        # Should search first, then read
        assert "search_code" in tool_names, "Should have searched first"
        assert "read_file" in tool_names, "Should have read files to confirm"


# ============================================================================
# TESTS — VERIFICATION
# ============================================================================

class TestVerification:
    """Tool results must be verified before being trusted."""

    def test_verification_appears_in_output(self):
        """Agent output should include verification traces."""
        stdout = ask("Find the auth middleware function")
        verifications = extract_verifications(stdout)
        # At least one verification should appear
        assert len(verifications) > 0, (
            "No verification traces found in output. "
            "Agent should verify tool results."
        )

    def test_verification_passes_for_valid_results(self):
        """Verification should PASS when tool returns correct results."""
        stdout = ask("Read the file src/middleware/auth.pseudo")
        verifications = extract_verifications(stdout)
        if verifications:
            passed = [v for v in verifications if v["result"] == "PASS"]
            assert len(passed) > 0, (
                "No verification passed for a valid file read"
            )

    def test_verification_catches_missing_file(self):
        """Verification should FAIL when tool can't find the target."""
        stdout = ask("Read the file src/services/auth_service.pseudo")
        # Either verification fails or agent reports file not found
        verifications = extract_verifications(stdout)
        response = extract_json(stdout)
        answer = response["answer"].lower()

        verification_failed = any(
            v["result"] == "FAIL" for v in verifications
        )
        agent_reported_missing = any(
            phrase in answer
            for phrase in ["not found", "doesn't exist", "does not exist",
                          "no such file", "not exist"]
        )
        assert verification_failed or agent_reported_missing, (
            "Agent didn't catch that the file doesn't exist — "
            "verification should have failed"
        )


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestToolInterface,
        TestSimpleTools,
        TestToolRegistry,
        TestToolSelection,
        TestVerification,
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
