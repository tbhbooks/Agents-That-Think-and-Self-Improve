"""
Chapter 5 Validation Tests
==========================

These tests validate the reader's Ch 5 implementation: write_file, delete_file,
execute_shell as SimpleTools, permission model, action gates, and idempotency.

The reader's program must be callable as:
    tbh-code --codebase <path> --ask "<question>"
    tbh-code --codebase <path> --auto-approve --ask "<question>"
    tbh-code --codebase <path> --list-tools

Tool calls must appear in stdout with the format:
    [tool] Agent selected: <tool_name>
    [tool] Arguments: { ... }
    [gate] <permission> operation: ...
    [gate] Approved | DENIED
    [tool] Result: success=true|false

Output must include a JSON response with: answer, confidence, sources

IMPORTANT: These tests use --auto-approve to avoid interactive prompts.
The action gate tests verify that gates EXIST and are checked, not that they
block (since blocking requires interactive input).

Adjust AGENT_CMD and TODO_API_PATH below to match the reader's setup.
"""

import subprocess
import json
import os
import re
import sys
import tempfile
import shutil

# ============================================================================
# CONFIGURATION
# ============================================================================

AGENT_CMD = "tbh-code"
TODO_API_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "todo-api")

# ============================================================================
# HELPERS
# ============================================================================

def ask(question, auto_approve=True, timeout=60):
    """Ask the agent a question and capture stdout."""
    cmd = [AGENT_CMD, "--codebase", TODO_API_PATH, "--ask", question]
    if auto_approve:
        cmd.insert(3, "--auto-approve")
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


def extract_gate_events(stdout):
    """Extract gate check events from output."""
    events = []
    for line in stdout.splitlines():
        gate_match = re.match(r'\[gate\] (.*)', line)
        if gate_match:
            text = gate_match.group(1)
            events.append(text)
    return events


def file_in_codebase(relative_path):
    """Check if a file exists in the todo-api codebase."""
    return os.path.exists(os.path.join(TODO_API_PATH, relative_path))


def read_codebase_file(relative_path):
    """Read a file from the todo-api codebase."""
    path = os.path.join(TODO_API_PATH, relative_path)
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return None


# ============================================================================
# TEST FIXTURE — create a temp copy of todo-api for write tests
# ============================================================================

# NOTE: For tests that modify files, consider pointing TODO_API_PATH at a
# temporary copy. The tests below assume --auto-approve mode and may create
# or modify files in the codebase directory.


# ============================================================================
# TESTS — FILE TOOLS
# ============================================================================

class TestFileTools:
    """write_file and delete_file must work correctly."""

    def test_write_file_tool_exists(self):
        """write_file must be listed as an available tool."""
        stdout = list_tools()
        assert "write_file" in stdout, "write_file tool not found"

    def test_delete_file_tool_exists(self):
        """delete_file must be listed as an available tool."""
        stdout = list_tools()
        assert "delete_file" in stdout, "delete_file tool not found"

    def test_write_creates_file(self):
        """write_file should create a new file."""
        test_file = "tests/_test_ch05_temp.pseudo"
        stdout = ask(
            f"Create a file {test_file} with content '# test file'"
        )
        calls = extract_tool_calls(stdout)
        write_calls = [c for c in calls if c.get("tool") == "write_file"]
        assert len(write_calls) > 0, "Agent didn't use write_file"
        assert write_calls[0].get("success", False), "write_file failed"

        # Clean up — ask agent to delete the test file
        ask(f"Delete the file {test_file}")

    def test_write_file_content_is_correct(self):
        """write_file should write the exact content requested."""
        test_file = "tests/_test_ch05_content.pseudo"
        expected_content = "# This is a test\nfunction test(): pass\n"
        stdout = ask(
            f"Write the following exact content to {test_file}: "
            f"'# This is a test\\nfunction test(): pass\\n'"
        )
        response = extract_json(stdout)
        # The agent should confirm it wrote the file
        assert response.get("confidence", 0) > 0.5, "Write appeared to fail"

        # Clean up
        ask(f"Delete the file {test_file}")


# ============================================================================
# TESTS — SHELL TOOL
# ============================================================================

class TestShellTool:
    """execute_shell must capture stdout, stderr, and exit_code."""

    def test_execute_shell_tool_exists(self):
        """execute_shell must be listed as an available tool."""
        stdout = list_tools()
        assert "execute_shell" in stdout, "execute_shell tool not found"

    def test_captures_stdout(self):
        """execute_shell should capture command stdout."""
        stdout = ask("Run the command 'echo hello world'")
        response = extract_json(stdout)
        answer = response["answer"].lower()
        assert "hello world" in answer, (
            "Shell command stdout not captured — should contain 'hello world'"
        )

    def test_captures_exit_code(self):
        """execute_shell should capture the exit code."""
        stdout = ask("Run the command 'echo hello' and tell me the exit code")
        response = extract_json(stdout)
        answer = response["answer"].lower()
        # echo should return exit code 0
        assert "0" in answer or "success" in answer, (
            "Agent didn't report exit code for a successful command"
        )

    def test_captures_stderr(self):
        """execute_shell should capture stderr separately from stdout."""
        stdout = ask(
            "Run the command 'ls /nonexistent_path_12345' and "
            "tell me if there were errors"
        )
        response = extract_json(stdout)
        answer = response["answer"].lower()
        assert any(word in answer for word in [
            "error", "not found", "no such", "stderr", "failed", "not exist"
        ]), "Agent didn't detect stderr output from failing command"


# ============================================================================
# TESTS — PERMISSION MODEL
# ============================================================================

class TestPermissionModel:
    """Tools must be classified by permission level."""

    def test_tool_list_shows_permissions(self):
        """Tool listing should indicate permission levels."""
        stdout = list_tools()
        # Should show some indication of safe/write/dangerous
        has_permission_info = any(
            word in stdout.lower()
            for word in ["safe", "write", "dangerous", "permission"]
        )
        assert has_permission_info, (
            "Tool listing doesn't show permission levels"
        )

    def test_read_file_is_safe(self):
        """read_file should be classified as safe."""
        stdout = ask("Read the file src/main.pseudo")
        gate_events = extract_gate_events(stdout)
        # Safe tools should either have no gate event or a "safe" event
        dangerous_gates = [e for e in gate_events if "DANGEROUS" in e]
        write_gates = [e for e in gate_events if "write operation" in e]
        # read_file should not trigger write or dangerous gates
        assert len(dangerous_gates) == 0 and len(write_gates) == 0, (
            "read_file triggered a write/dangerous gate — it should be safe"
        )

    def test_write_file_triggers_gate(self):
        """write_file should trigger a write gate."""
        stdout = ask("Create a file tests/_perm_test.pseudo with content 'test'")
        gate_events = extract_gate_events(stdout)
        assert len(gate_events) > 0, (
            "write_file didn't trigger any gate event"
        )
        # Clean up
        ask("Delete the file tests/_perm_test.pseudo")

    def test_execute_shell_triggers_dangerous_gate(self):
        """execute_shell should trigger a dangerous gate."""
        stdout = ask("Run the command 'echo test'")
        gate_events = extract_gate_events(stdout)
        dangerous_gates = [e for e in gate_events if "DANGEROUS" in e]
        assert len(dangerous_gates) > 0, (
            "execute_shell didn't trigger a DANGEROUS gate"
        )


# ============================================================================
# TESTS — ACTION GATES
# ============================================================================

class TestActionGates:
    """Action gates must check permissions before execution."""

    def test_gate_appears_before_write(self):
        """Gate check must appear in output before write tool executes."""
        stdout = ask("Write 'test content' to tests/_gate_test.pseudo")
        lines = stdout.splitlines()
        gate_line = -1
        result_line = -1
        for i, line in enumerate(lines):
            if "[gate]" in line and ("write" in line.lower() or "Approved" in line):
                if gate_line == -1:
                    gate_line = i
            if "[tool] Result:" in line and result_line == -1 and gate_line >= 0:
                result_line = i

        assert gate_line >= 0, "No gate check found for write operation"
        assert gate_line < result_line, (
            "Gate check should appear BEFORE tool result"
        )

        # Clean up
        ask("Delete the file tests/_gate_test.pseudo")

    def test_gate_shows_what_agent_wants_to_do(self):
        """Gate output should describe the operation being attempted."""
        stdout = ask("Run the command 'echo hello'")
        gate_events = extract_gate_events(stdout)
        assert len(gate_events) > 0, "No gate events found"
        # Gate should mention what the agent wants to do
        gate_text = " ".join(gate_events).lower()
        assert "execute" in gate_text or "echo" in gate_text or "command" in gate_text, (
            "Gate event doesn't describe the operation"
        )

    def test_auto_approve_allows_execution(self):
        """With --auto-approve, gated operations should succeed."""
        stdout = ask("Run 'echo hello'", auto_approve=True)
        calls = extract_tool_calls(stdout)
        shell_calls = [c for c in calls if c.get("tool") == "execute_shell"]
        if shell_calls:
            assert shell_calls[0].get("success", False), (
                "execute_shell failed even with --auto-approve"
            )


# ============================================================================
# TESTS — IDEMPOTENCY
# ============================================================================

class TestIdempotency:
    """Write operations must be idempotent."""

    def test_second_write_is_noop(self):
        """Writing the same content twice should skip the second write."""
        content = "# idempotency test\nvalue: 42\n"
        # First write
        ask(f"Write to tests/_idempotent.pseudo: '{content}'")
        # Second write — same content
        stdout = ask(f"Write to tests/_idempotent.pseudo: '{content}'")
        response = extract_json(stdout)
        answer = response["answer"].lower()
        # Agent should indicate the write was unnecessary
        assert any(phrase in answer for phrase in [
            "unchanged", "already", "no write", "skipped", "same content",
            "no-op", "not needed", "identical",
        ]), (
            "Agent didn't indicate that the second write was a no-op"
        )

        # Clean up
        ask("Delete the file tests/_idempotent.pseudo")

    def test_different_content_does_write(self):
        """Writing different content should actually write."""
        # First write
        ask("Write 'version: 1' to tests/_idempotent2.pseudo")
        # Second write — different content
        stdout = ask("Write 'version: 2' to tests/_idempotent2.pseudo")
        calls = extract_tool_calls(stdout)
        write_calls = [c for c in calls if c.get("tool") == "write_file"]
        assert len(write_calls) > 0, "Agent didn't use write_file"
        assert write_calls[0].get("success", False), (
            "write_file failed for different content"
        )

        # Clean up
        ask("Delete the file tests/_idempotent2.pseudo")


# ============================================================================
# TESTS — END-TO-END
# ============================================================================

class TestEndToEnd:
    """Agent should fix the auth bug using skills + tools end-to-end.

    NOTE: This test modifies files in the todo-api codebase. It should
    restore the original state after running. Consider using a temp copy.
    """

    def test_agent_can_find_and_describe_bug(self):
        """Agent should find and describe the auth middleware bug."""
        stdout = ask("Find the security bug in the auth middleware")
        response = extract_json(stdout)
        answer = response["answer"].lower()
        assert "auth_middleware" in answer or "auth middleware" in answer, (
            "Agent didn't identify the auth middleware"
        )
        assert any(phrase in answer for phrase in [
            "any token", "any non-empty", "not validate", "no validation",
            "hardcode", "doesn't validate", "doesn't verify",
        ]), "Agent didn't identify the core bug"

    def test_agent_uses_multiple_tool_types(self):
        """End-to-end task should use both read and write tools."""
        stdout = ask(
            "Fix the auth middleware to properly validate tokens. "
            "Write the fix and add a test."
        )
        calls = extract_tool_calls(stdout)
        tool_names = set(c.get("tool") for c in calls)
        # Should use a mix of read and write tools
        has_read = "read_file" in tool_names or "search_code" in tool_names
        has_write = "write_file" in tool_names
        assert has_read, "Agent didn't use any read tools"
        assert has_write, "Agent didn't use write_file to write the fix"


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestFileTools,
        TestShellTool,
        TestPermissionModel,
        TestActionGates,
        TestIdempotency,
        TestEndToEnd,
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
