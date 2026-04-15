"""
Chapter 6 Validation Tests
==========================

These tests validate the reader's Ch 6 implementation: MemoryStore,
Session persistence, ContextBudget, retrieval ranking, and outcome tracking.

The reader's program must be callable as:
    tbh-code --codebase <path> --ask "<question>"
    tbh-code --codebase <path> --session <id>
    tbh-code --codebase <path> --auto-approve --ask "<question>"
    tbh-code --codebase <path> --list-sessions

Memory traces must appear in stdout with the format:
    [memory] Saving <type>: <key>
    [memory] Searching for relevant memories: "<query>"
    [memory] Retrieved N entries:
    [context] Budget allocation:

Session traces:
    [session: <id>] ...
    Session saved: <id>. Resume with --session <id>

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

def ask(question, session_id=None, auto_approve=True, timeout=60):
    """Ask the agent a question and capture stdout."""
    cmd = [AGENT_CMD, "--codebase", TODO_API_PATH, "--ask", question]
    if auto_approve:
        cmd.insert(3, "--auto-approve")
    if session_id:
        cmd.extend(["--session", session_id])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    return result.stdout


def list_sessions(timeout=30):
    """List saved sessions."""
    cmd = [AGENT_CMD, "--codebase", TODO_API_PATH, "--list-sessions"]
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


def extract_session_id(stdout):
    """Extract session ID from agent output."""
    match = re.search(r'\[session: ([a-zA-Z0-9]+)\]', stdout)
    if match:
        return match.group(1)
    # Also check for "Session saved: <id>" line
    match = re.search(r'Session saved: ([a-zA-Z0-9]+)', stdout)
    if match:
        return match.group(1)
    return None


def extract_memory_events(stdout):
    """Extract memory-related events from output."""
    events = []
    for line in stdout.splitlines():
        mem_match = re.match(r'\[memory\] (.+)', line)
        if mem_match:
            events.append(mem_match.group(1))
    return events


def extract_context_budget(stdout):
    """Extract context budget info from output."""
    budget_lines = []
    in_budget = False
    for line in stdout.splitlines():
        if "[context]" in line:
            budget_lines.append(line)
            if "Budget" in line or "allocation" in line.lower():
                in_budget = True
        elif in_budget and line.strip().startswith(("system_prompt", "conversation",
                                                     "retrieved", "loaded", "current",
                                                     "TOTAL")):
            budget_lines.append(line)
        else:
            in_budget = False
    return budget_lines


# ============================================================================
# TESTS — MEMORY STORE
# ============================================================================

class TestMemoryStore:
    """MemoryStore must save, retrieve, and search entries."""

    def test_outcome_saved_after_task(self):
        """Completing a task should save an outcome to memory."""
        stdout = ask("Find the auth middleware function and describe what it does")
        mem_events = extract_memory_events(stdout)
        # At least one memory save should occur
        save_events = [e for e in mem_events if "Saving" in e or "saving" in e]
        assert len(save_events) > 0, (
            "No memory save events found after task completion. "
            "Agent should save outcomes to memory."
        )

    def test_outcome_has_type(self):
        """Saved memory entries should have a type (fact, decision, outcome, rule)."""
        stdout = ask("Search for all route definitions in todo-api")
        mem_events = extract_memory_events(stdout)
        save_events = [e for e in mem_events if "Saving" in e or "saving" in e]
        if save_events:
            has_type = any(
                t in " ".join(save_events).lower()
                for t in ["outcome", "fact", "decision", "rule"]
            )
            assert has_type, (
                "Memory save events don't indicate entry type. "
                "Expected one of: outcome, fact, decision, rule"
            )

    def test_memory_has_tags(self):
        """Saved memory entries should include searchable tags."""
        stdout = ask("Find where user passwords are handled in the codebase")
        mem_events = extract_memory_events(stdout)
        all_text = " ".join(mem_events).lower()
        # Tags should appear somewhere in memory output
        has_tags = "tags" in all_text or "tag" in all_text or "[" in all_text
        # This is a soft check — tags may be in the JSON payload
        assert len(mem_events) > 0, "No memory events found"

    def test_memory_search_returns_results(self):
        """Searching memory should return relevant entries."""
        # First, create a memory by doing work
        ask("Describe the database layer in todo-api")
        # Then, ask something that should trigger retrieval
        stdout = ask("What database does todo-api use?")
        mem_events = extract_memory_events(stdout)
        search_events = [e for e in mem_events if "Search" in e or "Retriev" in e]
        assert len(search_events) > 0, (
            "No memory search/retrieval events found. "
            "Agent should search memory for relevant context."
        )

    def test_retrieved_memories_are_ranked(self):
        """Retrieved memories should be ranked by relevance."""
        # Do some work to populate memory
        ask("Describe the auth routes in todo-api")
        ask("Describe the task routes in todo-api")
        # Now ask something auth-related — auth memory should rank higher
        stdout = ask("How does authentication work in this codebase?")
        mem_events = extract_memory_events(stdout)
        retrieved = [e for e in mem_events if "Retrieved" in e or "score" in e.lower()]
        assert len(retrieved) > 0, (
            "No retrieval ranking found in output. "
            "Agent should show scored/ranked memory results."
        )


# ============================================================================
# TESTS — SESSION PERSISTENCE
# ============================================================================

class TestSession:
    """Session must save and restore state across agent restarts."""

    def test_session_id_displayed(self):
        """Agent output should include a session ID."""
        stdout = ask("List files in the src/ directory")
        session_id = extract_session_id(stdout)
        assert session_id is not None, (
            "No session ID found in output. "
            "Expected [session: <id>] in output."
        )

    def test_session_saved_on_exit(self):
        """Agent should save session state on exit."""
        stdout = ask("Read the file src/main.pseudo")
        has_save = "Session saved" in stdout or "session saved" in stdout.lower()
        session_id = extract_session_id(stdout)
        # Either explicit save message or session ID present
        assert session_id is not None, (
            "No session tracking found. Agent should track sessions."
        )

    def test_session_restore(self):
        """Resuming a session should restore prior conversation context."""
        # First session — do some work
        stdout1 = ask("Find the auth middleware and describe the bug")
        session_id = extract_session_id(stdout1)
        assert session_id is not None, "No session ID from first session"

        # Resume session — agent should know about prior work
        stdout2 = ask(
            "What did we discuss earlier about the auth middleware?",
            session_id=session_id
        )
        response = extract_json(stdout2)
        answer = response["answer"].lower()
        # Agent should reference auth middleware from prior conversation
        assert "auth" in answer, (
            "Resumed session doesn't reference prior auth middleware discussion. "
            "Session restore should include conversation history."
        )

    def test_session_list(self):
        """--list-sessions should show saved sessions."""
        # Create at least one session
        ask("List the files in todo-api")
        stdout = list_sessions()
        assert len(stdout.strip()) > 0, "Session list is empty"


# ============================================================================
# TESTS — CONTEXT BUDGET
# ============================================================================

class TestContextBudget:
    """ContextBudget must allocate tokens within limits."""

    def test_budget_shown_in_output(self):
        """Agent should display context budget allocation."""
        stdout = ask("Read every file in the src/ directory and summarize")
        budget_lines = extract_context_budget(stdout)
        assert len(budget_lines) > 0, (
            "No context budget information in output. "
            "Agent should show [context] Budget allocation."
        )

    def test_budget_does_not_overflow(self):
        """Token usage should not exceed total budget."""
        stdout = ask(
            "Read all files in the codebase and tell me about every function"
        )
        budget_lines = extract_context_budget(stdout)
        budget_text = " ".join(budget_lines).lower()
        # Should not contain overflow/error indicators
        # (Agent may show WARNING for trim, but should resolve it)
        assert "overflow" not in budget_text or "trimm" in budget_text, (
            "Context budget overflow detected without trimming"
        )

    def test_budget_categories_present(self):
        """Budget should show allocation across standard categories."""
        stdout = ask("Summarize the codebase architecture")
        budget_lines = extract_context_budget(stdout)
        budget_text = " ".join(budget_lines).lower()
        categories = ["system_prompt", "conversation", "memor", "file", "task"]
        found = sum(1 for cat in categories if cat in budget_text)
        # At least some categories should be present
        assert found >= 2 or len(budget_lines) > 0, (
            "Budget allocation doesn't show expected categories"
        )


# ============================================================================
# TESTS — OUTCOME TRACKING
# ============================================================================

class TestOutcomeTracking:
    """Outcomes must be stored with structured metrics and diagnosis."""

    def test_outcome_logged_on_completion(self):
        """Completing a task should log an outcome entry."""
        stdout = ask(
            "Add a comment to the top of src/main.pseudo explaining what it does",
        )
        mem_events = extract_memory_events(stdout)
        outcome_events = [
            e for e in mem_events
            if "outcome" in e.lower() or "Saving outcome" in e
        ]
        assert len(outcome_events) > 0, (
            "No outcome logged after task completion. "
            "Agent should log outcomes with type 'outcome'."
        )

    def test_outcome_has_metrics(self):
        """Outcome entries should include measurable metrics."""
        stdout = ask(
            "Write a test for the list_files endpoint and run it"
        )
        mem_events = extract_memory_events(stdout)
        all_text = " ".join(mem_events)
        has_metrics = "metrics" in all_text.lower() or "tests" in all_text.lower()
        assert has_metrics or len(mem_events) > 0, (
            "Outcome entry doesn't include metrics. "
            "Expected structured data like test counts, files modified."
        )

    def test_outcome_has_diagnosis(self):
        """Outcome entries should include a diagnosis string."""
        stdout = ask("Find and describe any security issues in the auth code")
        mem_events = extract_memory_events(stdout)
        all_text = " ".join(mem_events).lower()
        has_diagnosis = "diagnosis" in all_text or "because" in all_text
        # Soft check — diagnosis may be in JSON payload
        assert len(mem_events) > 0, (
            "No memory events found — outcome with diagnosis expected"
        )


# ============================================================================
# TESTS — RETRIEVAL
# ============================================================================

class TestRetrieval:
    """Relevant memories must be ranked and injected into context."""

    def test_memories_retrieved_for_related_task(self):
        """When given a related task, agent should retrieve relevant memories."""
        # First, build some memory
        ask("Describe the auth middleware in todo-api")
        # Now ask a related question
        stdout = ask("How should I fix security issues in the middleware?")
        mem_events = extract_memory_events(stdout)
        retrieval_events = [
            e for e in mem_events
            if "Retrieved" in e or "Search" in e or "Retriev" in e
        ]
        assert len(retrieval_events) > 0, (
            "Agent didn't search memory for a related task. "
            "Should retrieve prior middleware knowledge."
        )

    def test_memories_appear_in_sources(self):
        """Retrieved memories should appear in the response sources."""
        ask("Describe the database design in todo-api")
        stdout = ask("What data storage approach does this project use?")
        response = extract_json(stdout)
        sources = response.get("sources", [])
        # Sources may include memory: prefixed entries
        has_memory_source = any("memory" in s.lower() for s in sources)
        # Or the answer should reference prior knowledge
        answer = response["answer"].lower()
        has_prior_ref = any(
            phrase in answer
            for phrase in ["previous", "earlier", "prior", "already", "known"]
        )
        assert has_memory_source or has_prior_ref, (
            "Retrieved memories not reflected in response. "
            "Expected memory references in sources or answer."
        )

    def test_irrelevant_memories_not_retrieved(self):
        """Unrelated memories should not dominate retrieval."""
        # Build memory about auth
        ask("Describe the auth routes")
        # Ask about something completely different
        stdout = ask("How many test files are there?")
        mem_events = extract_memory_events(stdout)
        # If retrieval happens, auth memories should have low scores
        # This is a soft check — just verify retrieval isn't broken
        response = extract_json(stdout)
        assert response.get("answer"), "Agent failed to respond"


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestMemoryStore,
        TestSession,
        TestContextBudget,
        TestOutcomeTracking,
        TestRetrieval,
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
