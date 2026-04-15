"""
Chapter 2 Validation Tests
==========================

These tests validate the reader's Ch 2 implementation: an Augmented LLM
agent that reads a codebase, maintains conversation history, and returns
structured responses.

The reader's program must be callable as:
    tbh-code --codebase <path> --ask "<question>"       (single-question mode)
    echo "<question>" | tbh-code --codebase <path>      (pipe mode, optional)

Output must be valid JSON with fields: answer, confidence, sources

For multi-turn tests, the program must support a mode where it reads
questions from stdin line by line and outputs one JSON response per line:
    tbh-code --codebase <path> --interactive < questions.txt

Adjust AGENT_CMD and TODO_API_PATH below to match the reader's setup.
"""

import subprocess
import json
import os
import sys
import tempfile

# ============================================================================
# CONFIGURATION
# ============================================================================

AGENT_CMD = "tbh-code"
TODO_API_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "todo-api")

# ============================================================================
# HELPERS
# ============================================================================

def ask(question, timeout=60):
    """Ask the agent a single question and parse the JSON response."""
    cmd = [AGENT_CMD, "--codebase", TODO_API_PATH, "--ask", question]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Extract JSON from output — may have non-JSON preamble (loading messages etc.)
    stdout = result.stdout.strip()
    # Find the first { and last } to extract JSON
    json_start = stdout.find("{")
    json_end = stdout.rfind("}") + 1
    assert json_start >= 0 and json_end > json_start, (
        f"No JSON found in output:\n{stdout}"
    )
    json_str = stdout[json_start:json_end]
    response = json.loads(json_str)
    return response


def ask_multi_turn(questions, timeout=120):
    """Ask multiple questions in sequence (multi-turn conversation).
    Uses interactive mode with stdin."""
    input_text = "\n".join(questions) + "\n"
    cmd = [AGENT_CMD, "--codebase", TODO_API_PATH, "--interactive"]
    result = subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Parse one JSON object per question
    responses = []
    stdout = result.stdout.strip()
    depth = 0
    current = ""
    for char in stdout:
        if char == "{":
            depth += 1
        if depth > 0:
            current += char
        if char == "}" and depth > 0:
            depth -= 1
            if depth == 0:
                try:
                    responses.append(json.loads(current))
                except json.JSONDecodeError:
                    pass
                current = ""

    return responses


# ============================================================================
# TESTS — STRUCTURED OUTPUT
# ============================================================================

class TestStructuredOutput:
    """The agent must return valid structured responses."""

    def test_response_is_valid_json(self):
        """Response must be parseable JSON."""
        response = ask("What files are in this project?")
        assert isinstance(response, dict), "Response is not a JSON object"

    def test_response_has_required_fields(self):
        """Response must include answer, confidence, and sources."""
        response = ask("What files are in this project?")
        assert "answer" in response, "Response missing 'answer' field"
        assert "confidence" in response, "Response missing 'confidence' field"
        assert "sources" in response, "Response missing 'sources' field"

    def test_confidence_is_valid_range(self):
        """Confidence must be a float between 0.0 and 1.0."""
        response = ask("What does the main file do?")
        conf = response["confidence"]
        assert isinstance(conf, (int, float)), f"Confidence is not a number: {conf}"
        assert 0.0 <= conf <= 1.0, f"Confidence {conf} not in [0.0, 1.0]"

    def test_sources_is_a_list(self):
        """Sources must be a list of strings."""
        response = ask("What does the auth middleware do?")
        sources = response["sources"]
        assert isinstance(sources, list), f"Sources is not a list: {sources}"
        for s in sources:
            assert isinstance(s, str), f"Source entry is not a string: {s}"


# ============================================================================
# TESTS — FILE READING
# ============================================================================

class TestFileReading:
    """The agent must read and reason about actual codebase files."""

    def test_knows_project_files(self):
        """Agent should be able to list files it has loaded."""
        response = ask("What files are in this project?")
        answer = response["answer"].lower()
        # Must mention at least some key files
        assert "main" in answer, "Agent didn't mention main file"
        assert "auth" in answer, "Agent didn't mention auth files"
        assert "task" in answer, "Agent didn't mention task files"

    def test_reads_file_content(self):
        """Agent should answer questions based on actual file content."""
        response = ask("What does the auth middleware do?")
        answer = response["answer"].lower()
        # Should describe actual middleware behavior, not hallucinate
        assert "token" in answer, "Agent didn't mention token handling"
        assert any(word in answer for word in ["header", "authorization"]), (
            "Agent didn't mention the authorization header"
        )

    def test_finds_the_auth_bug(self):
        """Agent should identify the auth middleware vulnerability."""
        response = ask(
            "Find the security vulnerability in the todo-api authentication system. "
            "Identify the file, the function, and explain what's wrong."
        )
        answer = response["answer"].lower()
        # Must identify the correct file
        assert "auth" in answer and "middleware" in answer, (
            "Agent didn't identify the auth middleware as the location"
        )
        # Must identify the actual bug — not a hallucinated one
        assert any(phrase in answer for phrase in [
            "any non-empty",
            "any token",
            "not validate",
            "no validation",
            "doesn't validate",
            "doesn't verify",
            "not verified",
            "hardcode",
            "hard-code",
            "always",
        ]), "Agent didn't identify the 'accepts any token' bug"

    def test_references_real_files(self):
        """Sources should reference files that actually exist in todo-api."""
        response = ask("What does the auth middleware do?")
        for source in response["sources"]:
            # Extract file path (strip line numbers like ":8-15")
            file_path = source.split(":")[0]
            full_path = os.path.join(TODO_API_PATH, file_path)
            assert os.path.exists(full_path), (
                f"Agent referenced non-existent file: {source}"
            )

    def test_does_not_hallucinate_files(self):
        """Agent should not reference files that don't exist."""
        response = ask("Find all bugs in the project")
        for source in response["sources"]:
            file_path = source.split(":")[0]
            full_path = os.path.join(TODO_API_PATH, file_path)
            assert os.path.exists(full_path), (
                f"Agent hallucinated a file: {source}"
            )


# ============================================================================
# TESTS — CONVERSATION HISTORY
# ============================================================================

class TestConversationHistory:
    """Multi-turn tests — agent must maintain context across turns."""

    def test_multi_turn_context(self):
        """Agent should use context from earlier turns in later answers."""
        responses = ask_multi_turn([
            "What does the auth middleware do?",
            "Is there a bug in it?",
        ])
        assert len(responses) >= 2, (
            f"Expected 2 responses, got {len(responses)}"
        )
        # Second response should reference auth middleware without
        # the user repeating "auth middleware" — it's in context from turn 1
        second_answer = responses[1]["answer"].lower()
        assert any(word in second_answer for word in [
            "token", "validation", "middleware", "auth", "bug", "vulnerability"
        ]), "Second turn doesn't seem to reference auth context from first turn"

    def test_three_turn_context(self):
        """Agent maintains context across 3 turns."""
        responses = ask_multi_turn([
            "What files handle authentication?",
            "Which one validates tokens?",
            "Is the validation correct?",
        ])
        assert len(responses) >= 3, (
            f"Expected 3 responses, got {len(responses)}"
        )
        # Third answer should discuss the auth middleware bug
        third_answer = responses[2]["answer"].lower()
        assert any(phrase in third_answer for phrase in [
            "not correct",
            "bug",
            "vulnerability",
            "doesn't validate",
            "no validation",
            "any token",
            "not valid",
            "incorrect",
        ]), "Third turn doesn't discuss the validation bug"


# ============================================================================
# TESTS — HONESTY & GROUNDING
# ============================================================================

class TestHonesty:
    """The agent must be honest about what it knows and doesn't know."""

    def test_admits_ignorance(self):
        """When asked about something not in the codebase, agent should say so."""
        response = ask("What CI/CD pipeline does this project use?")
        answer = response["answer"].lower()
        confidence = response["confidence"]
        # Should express uncertainty — there's no CI config in todo-api
        assert confidence < 0.8, (
            f"Agent is too confident ({confidence}) about CI/CD "
            "when there's no CI config in the codebase"
        )
        assert any(phrase in answer for phrase in [
            "don't see",
            "no",
            "not",
            "can't find",
            "doesn't appear",
            "no evidence",
            "not in",
            "unable to find",
        ]), "Agent should express that CI/CD info is not in the codebase"

    def test_does_not_invent_functions(self):
        """Agent should not invent function names that don't exist."""
        response = ask("What does the validate_token function do?")
        answer = response["answer"].lower()
        # validate_token doesn't exist — agent should say so
        assert any(phrase in answer for phrase in [
            "doesn't exist",
            "does not exist",
            "no function",
            "not found",
            "couldn't find",
            "don't see",
            "there is no",
        ]), (
            "Agent should note that validate_token doesn't exist "
            "rather than describing a hallucinated function"
        )


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestStructuredOutput,
        TestFileReading,
        TestConversationHistory,
        TestHonesty,
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
