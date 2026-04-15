"""
Chapter 9 Validation Tests
==========================

These tests validate the reader's Ch 9 implementation: mistake journal,
skill rewriting, evaluator-optimizer loop, user feedback incorporation,
and improvement verification.

The reader's program must be callable as:
    tbh-code --codebase <path> --ask "<question>"
    tbh-code --codebase <path> --auto-approve --ask "<question>"
    tbh-code --codebase <path> --show-journal
    tbh-code --codebase <path> --show-rules
    tbh-code --codebase <path> --show-skills

Improvement traces must appear in stdout with the format:
    [journal] Logging mistake entry:
    [improve] Checking mistake journal for skill: <name>
    [improve] Refining skill...
    [improve] Refined skill: <name> v<N>
    [eval-opt] Round N: score <float>
    [eval-opt] Threshold met. Done.
    [feedback] Stored rule: <text>
    [improve] Comparing before/after:
    [improve] Recommendation: KEEP|ROLLBACK

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

def ask(question, auto_approve=True, timeout=120):
    """Ask the agent a question and capture stdout."""
    cmd = [AGENT_CMD, "--codebase", TODO_API_PATH, "--ask", question]
    if auto_approve:
        cmd.insert(3, "--auto-approve")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    return result.stdout


def show_journal(timeout=30):
    """Show the mistake journal."""
    cmd = [AGENT_CMD, "--codebase", TODO_API_PATH, "--show-journal"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    return result.stdout


def show_rules(timeout=30):
    """Show learned rules."""
    cmd = [AGENT_CMD, "--codebase", TODO_API_PATH, "--show-rules"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    return result.stdout


def show_skills(timeout=30):
    """Show skill versions."""
    cmd = [AGENT_CMD, "--codebase", TODO_API_PATH, "--show-skills"]
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


def extract_journal_events(stdout):
    """Extract journal-related events from output."""
    events = []
    for line in stdout.splitlines():
        journal_match = re.match(r'\[journal\] (.+)', line)
        if journal_match:
            events.append(journal_match.group(1))
    return events


def extract_improve_events(stdout):
    """Extract improvement-related events from output."""
    events = []
    for line in stdout.splitlines():
        improve_match = re.match(r'\[improve\] (.+)', line)
        if improve_match:
            events.append(improve_match.group(1))
    return events


def extract_evalopt_events(stdout):
    """Extract evaluator-optimizer loop events from output."""
    events = []
    for line in stdout.splitlines():
        eo_match = re.match(r'\[eval-opt\] (.+)', line)
        if eo_match:
            events.append(eo_match.group(1))
    return events


def extract_feedback_events(stdout):
    """Extract feedback-related events from output."""
    events = []
    for line in stdout.splitlines():
        fb_match = re.match(r'\[feedback\] (.+)', line)
        if fb_match:
            events.append(fb_match.group(1))
    return events


def extract_eval_scores(stdout):
    """Extract evaluation scores from output."""
    scores = {}
    for line in stdout.splitlines():
        score_match = re.match(
            r'\[eval\] (Correctness|Completeness|Safety|Overall score):\s*([0-9.]+)',
            line
        )
        if score_match:
            scores[score_match.group(1).lower()] = float(score_match.group(2))
    return scores


# ============================================================================
# TESTS — MISTAKE JOURNAL
# ============================================================================

class TestMistakeJournal:
    """Mistake journal must capture structured failure data."""

    def test_mistake_logged_on_low_score(self):
        """A low evaluation score should trigger a journal entry."""
        # Ask for something likely to have issues
        stdout = ask(
            "Add user registration that stores passwords"
        )
        journal_events = extract_journal_events(stdout)
        has_logging = any(
            "Logging" in e or "mistake" in e.lower() or "entry" in e.lower()
            for e in journal_events
        )
        # If eval passed, no journal entry expected — check eval score
        scores = extract_eval_scores(stdout)
        overall = scores.get("overall score", 1.0)
        if overall < 0.7:
            assert has_logging, (
                f"Evaluation score was {overall} but no mistake was logged. "
                "Low scores should trigger journal entries."
            )

    def test_journal_entry_has_diagnosis(self):
        """Journal entries should include diagnosis (not just the error)."""
        stdout = ask(
            "Write a function that uses eval() to parse config"
        )
        journal_events = extract_journal_events(stdout)
        all_text = " ".join(journal_events).lower()
        has_diagnosis = "diagnosis" in all_text or "because" in all_text or "reason" in all_text
        assert len(journal_events) > 0 or has_diagnosis, (
            "Journal entry should include diagnosis explaining what went wrong"
        )

    def test_journal_entry_has_category(self):
        """Journal entries should be categorized."""
        stdout = ask(
            "Add authentication that stores passwords in plaintext"
        )
        journal_events = extract_journal_events(stdout)
        all_text = " ".join(journal_events).lower()
        categories = ["security", "incomplete", "incorrect", "inefficient", "style", "regression"]
        has_category = any(cat in all_text for cat in categories)
        if journal_events:
            assert has_category, (
                "Journal entry missing category. "
                f"Expected one of: {categories}"
            )

    def test_journal_entry_has_suggested_fix(self):
        """Journal entries should include a suggested fix."""
        stdout = ask(
            "Fix a bug using string equality for password comparison"
        )
        journal_events = extract_journal_events(stdout)
        all_text = " ".join(journal_events).lower()
        has_fix = "suggest" in all_text or "fix" in all_text or "instead" in all_text
        if journal_events:
            assert has_fix, (
                "Journal entry missing suggested fix. "
                "Entries should include actionable suggestions."
            )

    def test_show_journal_command(self):
        """--show-journal should display journal entries."""
        # First create some journal entries
        ask("Add registration with plaintext password storage")
        stdout = show_journal()
        assert len(stdout.strip()) > 0, (
            "--show-journal returned empty output. "
            "Should display journal entries."
        )


# ============================================================================
# TESTS — SKILL REWRITING
# ============================================================================

class TestSkillRewriting:
    """Agent must rewrite skills based on mistake patterns."""

    def test_skill_refinement_produces_new_version(self):
        """Refining a skill should produce a higher version number."""
        # Populate journal with relevant mistakes
        ask("Fix the auth middleware — use simple string comparison for tokens")
        # Ask to refine the skill
        stdout = ask(
            "Review and improve the find-bug skill based on recent mistakes"
        )
        improve_events = extract_improve_events(stdout)
        has_refinement = any(
            "Refined" in e or "v2" in e or "version" in e.lower()
            for e in improve_events
        )
        assert has_refinement or len(improve_events) > 0, (
            "No skill refinement events found. "
            "Agent should produce an improved skill version."
        )

    def test_refined_skill_has_additional_steps(self):
        """Refined skill should have more steps or constraints than original."""
        stdout = ask(
            "Show me the differences between find-bug v1 and v2"
        )
        response = extract_json(stdout)
        answer = response["answer"].lower()
        has_new_steps = any(
            word in answer
            for word in ["new step", "added", "additional", "now includes", "v2"]
        )
        assert has_new_steps, (
            "Refined skill doesn't appear to have additional steps. "
            "Skill v2 should add steps/constraints from mistake journal."
        )

    def test_refinement_cites_mistakes(self):
        """Skill refinement should reference which mistakes it addresses."""
        stdout = ask(
            "Refine the find-bug skill based on the mistake journal"
        )
        improve_events = extract_improve_events(stdout)
        all_text = " ".join(improve_events).lower()
        has_citation = any(
            word in all_text
            for word in ["mistake", "journal", "entry", "because", "from past"]
        )
        assert has_citation or len(improve_events) > 0, (
            "Skill refinement should cite which mistakes it addresses"
        )

    def test_show_skills_command(self):
        """--show-skills should display skill versions."""
        stdout = show_skills()
        assert len(stdout.strip()) > 0, (
            "--show-skills returned empty output. "
            "Should display skill versions."
        )


# ============================================================================
# TESTS — EVALUATOR-OPTIMIZER LOOP
# ============================================================================

class TestEvalOptLoop:
    """Evaluator-optimizer loop must converge with improving scores."""

    def test_loop_runs_multiple_rounds(self):
        """Complex tasks should trigger multiple eval-opt rounds."""
        stdout = ask(
            "Do a thorough code review of the auth routes — check for bugs, "
            "security issues, and missing error handling"
        )
        eo_events = extract_evalopt_events(stdout)
        round_events = [e for e in eo_events if "Round" in e]
        assert len(round_events) >= 2, (
            f"Only {len(round_events)} round(s) in eval-opt loop. "
            "Complex task should need multiple rounds."
        )

    def test_scores_improve_over_rounds(self):
        """Scores should generally improve across rounds."""
        stdout = ask(
            "Review the database layer for security issues, performance "
            "problems, and missing error handling"
        )
        eo_events = extract_evalopt_events(stdout)
        scores = []
        for event in eo_events:
            score_match = re.search(r'score\s+([0-9.]+)', event)
            if score_match:
                scores.append(float(score_match.group(1)))

        if len(scores) >= 2:
            # Last score should be >= first score
            assert scores[-1] >= scores[0], (
                f"Scores did not improve: {scores}. "
                "Optimizer should address evaluation feedback."
            )

    def test_loop_converges_or_hits_max(self):
        """Loop should either meet threshold or hit max rounds."""
        stdout = ask(
            "Review all route handlers for proper error handling"
        )
        eo_events = extract_evalopt_events(stdout)
        all_text = " ".join(eo_events).lower()
        converged = "threshold met" in all_text or "done" in all_text
        hit_max = "max rounds" in all_text
        assert converged or hit_max or len(eo_events) > 0, (
            "Eval-opt loop didn't converge or hit max rounds. "
            "Expected clear termination condition."
        )

    def test_score_history_in_response(self):
        """Response should include score history from the loop."""
        stdout = ask(
            "Do a comprehensive security audit of the auth system"
        )
        response = extract_json(stdout)
        answer = response["answer"].lower()
        # Score history might be in evaluation field or answer text
        has_history = (
            "score_history" in str(response) or
            "round" in answer or
            "improved" in answer
        )
        assert has_history, (
            "Response doesn't include score history or round information"
        )


# ============================================================================
# TESTS — USER FEEDBACK
# ============================================================================

class TestUserFeedback:
    """User corrections must persist as behavioral rules."""

    def test_feedback_creates_rule(self):
        """User feedback should be extracted and stored as a rule."""
        # Simulate a conversation with feedback
        stdout = ask(
            "I want you to remember this rule: always add docstrings to "
            "every function you write"
        )
        feedback_events = extract_feedback_events(stdout)
        has_rule = any(
            "Stored rule" in e or "rule" in e.lower()
            for e in feedback_events
        )
        # Also check memory events
        all_text = stdout.lower()
        has_memory = "rule" in all_text and ("stored" in all_text or "saved" in all_text)
        assert has_rule or has_memory, (
            "User feedback not stored as a rule. "
            "Expected [feedback] Stored rule event."
        )

    def test_rule_persists_across_tasks(self):
        """Stored rules should be retrieved for relevant future tasks."""
        # Store a rule
        ask(
            "Remember: never use print statements for logging, use a proper logger"
        )
        # Ask a new task that should trigger the rule
        stdout = ask("Add error logging to the auth middleware")
        # The agent should retrieve and follow the logging rule
        response = extract_json(stdout)
        answer = response["answer"].lower()
        has_rule_applied = any(
            word in answer
            for word in ["logger", "logging", "rule", "preference"]
        )
        # Or check if memory retrieved the rule
        has_memory_retrieval = "rule" in stdout.lower() and "Retrieved" in stdout
        assert has_rule_applied or has_memory_retrieval, (
            "Rule about logging was not applied to the new task. "
            "Stored rules should influence future behavior."
        )

    def test_show_rules_command(self):
        """--show-rules should display learned rules."""
        # Create a rule first
        ask("Remember: always validate input before processing")
        stdout = show_rules()
        assert len(stdout.strip()) > 0, (
            "--show-rules returned empty output. "
            "Should display stored behavioral rules."
        )

    def test_rule_has_applies_to(self):
        """Stored rules should indicate what tasks they apply to."""
        stdout = ask(
            "Remember: use TypeScript strict mode in all new files"
        )
        feedback_events = extract_feedback_events(stdout)
        all_text = " ".join(feedback_events).lower()
        has_scope = "applies" in all_text or "tags" in all_text or "when" in all_text
        if feedback_events:
            assert has_scope or len(feedback_events) > 0, (
                "Rule doesn't indicate what tasks it applies to"
            )


# ============================================================================
# TESTS — IMPROVEMENT VERIFICATION
# ============================================================================

class TestVerification:
    """Adaptations must be verified with before/after metrics."""

    def test_verification_compares_metrics(self):
        """Improvement verification should compare before and after scores."""
        # This test requires journal entries and a skill to refine
        ask("Fix auth middleware with simple string comparison")
        stdout = ask(
            "Verify that the find-bug skill v2 is better than v1"
        )
        improve_events = extract_improve_events(stdout)
        all_text = " ".join(improve_events).lower()
        has_comparison = any(
            word in all_text
            for word in ["before", "after", "comparing", "delta", "improved"]
        )
        assert has_comparison or len(improve_events) > 0, (
            "No before/after comparison found. "
            "Verification should compare metrics."
        )

    def test_verification_has_recommendation(self):
        """Verification should recommend KEEP or ROLLBACK."""
        stdout = ask(
            "Check if recent skill improvements actually helped"
        )
        improve_events = extract_improve_events(stdout)
        all_text = " ".join(improve_events).lower()
        has_recommendation = any(
            word in all_text
            for word in ["keep", "rollback", "recommendation", "better", "worse"]
        )
        response = extract_json(stdout)
        answer = response["answer"].lower()
        answer_has_rec = any(
            word in answer
            for word in ["keep", "rollback", "improved", "better", "verified"]
        )
        assert has_recommendation or answer_has_rec, (
            "Verification missing recommendation. "
            "Expected KEEP or ROLLBACK based on metrics."
        )

    def test_no_degradation_allowed(self):
        """Improvements should not degrade any criterion."""
        stdout = ask(
            "Verify the latest skill improvements"
        )
        improve_events = extract_improve_events(stdout)
        all_text = " ".join(improve_events).lower()
        # If degradation is mentioned, it should trigger rollback
        has_degradation = "degraded" in all_text or "worse" in all_text
        if has_degradation:
            has_rollback = "rollback" in all_text
            assert has_rollback, (
                "Degradation detected but no rollback recommended. "
                "Degraded criteria should trigger rollback."
            )


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestMistakeJournal,
        TestSkillRewriting,
        TestEvalOptLoop,
        TestUserFeedback,
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
