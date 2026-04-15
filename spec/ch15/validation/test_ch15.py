"""
Chapter 15 Validation Tests
============================

These tests validate the reader's Ch 15 implementation: ecosystem integration
including external MCP tools, A2A federation, governance gates, maturity levels,
and contract testing.

The reader's program must be callable as:
    tbh-code --swarm --task "<task>"

Ecosystem traces must appear in stdout with the format:
    [mcp] Establishing connection...
    [mcp] Discovering tools...
    [mcp] Tools discovered (<N>):
    [coder] Registering <N> external tools (permission: restricted)
    [governance] Evaluating: <name> from <source>
    [governance] Result: <decision> at <level>
    [governance] Policy <N>: <name>
    [a2a] Fetching directory...
    [a2a] Found <N> agent cards:
    [a2a] Sending A2ARequest:
    [a2a] Response received (<time>):
    [researcher] Registered <N> external agents (trust: sandbox)
    [researcher] Delegating task to <agent>...
    [maturity] <integration> registered at level <N> (<name>)
    [maturity] Call <N>: <tool> → success
    [maturity] Promotion check for <integration>:
    [maturity] <integration> promoted: <from> → <to>
    [maturity] Demoting: <from> → <to>
    [contract] Running contract suite for <integration>
    [contract] Test <N>: <name>
    [contract] Suite result:

Output must include JSON event payloads matching the interface spec.

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

def swarm_task(task, timeout=180):
    """Run a swarm task and capture stdout."""
    cmd = [AGENT_CMD, "--swarm", "--task", task]
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
    """Extract events with a specific tag like [mcp], [governance], etc."""
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
# TESTS — EXTERNAL MCP INTEGRATION
# ============================================================================

class TestExternalMCP:
    """External MCP tools must be discovered, registered, and callable."""

    def test_connect_discovers_tools(self):
        """connect_mcp_server should discover tools from the external server."""
        stdout = swarm_task(
            "Open a PR for the auth refactoring on todo-api"
        )
        all_text = stdout.lower()
        has_discovery = (
            "discovering tools" in all_text or
            "tools discovered" in all_text or
            "list_tools" in all_text
        )
        assert has_discovery, (
            "No tool discovery found. "
            "connect_mcp_server should discover tools via MCP tools/list."
        )

    def test_external_tools_registered_in_registry(self):
        """Discovered tools must be registered in ToolRegistry with source='external'."""
        stdout = swarm_task(
            "Open a PR for the auth refactoring on todo-api"
        )
        all_text = stdout.lower()
        has_registration = (
            "registering" in all_text and "external" in all_text or
            "tools registered" in all_text or
            'source="external"' in all_text or
            "source: external" in all_text
        )
        assert has_registration, (
            "No external tool registration found. "
            "External tools should be registered in ToolRegistry with source='external'."
        )

    def test_external_tools_have_restricted_permissions(self):
        """External tools must start with restricted/sandbox permission level."""
        stdout = swarm_task(
            "Open a PR for the auth refactoring on todo-api"
        )
        all_text = stdout.lower()
        has_restricted = (
            "restricted" in all_text or
            "permission: restricted" in all_text or
            "sandbox" in all_text
        )
        assert has_restricted, (
            "No restricted permission found for external tools. "
            "External tools should start with permission_level='restricted'."
        )

    def test_external_tool_callable_via_standard_interface(self):
        """External tools must be callable through the standard MCP tool interface."""
        stdout = swarm_task(
            "Open a PR for the auth refactoring on todo-api"
        )
        all_text = stdout.lower()
        has_tool_call = (
            "agent selected: create_pr" in all_text or
            "calling create_pr" in all_text or
            "[tool]" in all_text
        )
        assert has_tool_call, (
            "No external tool call found. "
            "External tools should be callable through the standard tool interface (Ch 3)."
        )
        # Verify the tool returned a result
        has_result = (
            "pr_number" in all_text or
            "pull_request" in all_text or
            "pr #" in all_text or
            "pr created" in all_text
        )
        assert has_result, (
            "No tool result found. "
            "External tool call should return a structured result."
        )


# ============================================================================
# TESTS — A2A FEDERATION
# ============================================================================

class TestA2AFederation:
    """External agents must be discovered via A2A and wrapped as proxies."""

    def test_discover_agents_from_directory(self):
        """discover_external_agents should fetch agent cards from A2A directory."""
        stdout = swarm_task(
            "Find documentation for the auth middleware in the payments-service"
        )
        all_text = stdout.lower()
        has_discovery = (
            "fetching directory" in all_text or
            "agent cards" in all_text or
            "discovering external agents" in all_text or
            ".well-known/a2a" in all_text
        )
        assert has_discovery, (
            "No A2A agent discovery found. "
            "discover_external_agents should fetch agent cards from the A2A directory."
        )

    def test_external_agents_registered_as_proxies(self):
        """Discovered agents must be wrapped as ExternalAgentProxy."""
        stdout = swarm_task(
            "Find documentation for the auth middleware in the payments-service"
        )
        all_text = stdout.lower()
        has_proxy = (
            "registered" in all_text and "external agent" in all_text or
            "externalagentproxy" in all_text or
            "trust: sandbox" in all_text or
            "trust_level" in all_text
        )
        assert has_proxy, (
            "No ExternalAgentProxy registration found. "
            "Discovered agents should be wrapped as proxies with trust_level='sandbox'."
        )

    def test_delegate_task_to_external_agent(self):
        """ExternalAgentProxy.delegate_task should send an A2A request."""
        stdout = swarm_task(
            "Find documentation for the auth middleware in the payments-service"
        )
        all_text = stdout.lower()
        has_delegation = (
            "delegating" in all_text or
            "a2arequest" in all_text or
            "sending request" in all_text
        )
        assert has_delegation, (
            "No task delegation found. "
            "ExternalAgentProxy should delegate tasks via A2A protocol."
        )

    def test_delegation_returns_structured_result(self):
        """Delegation must return a DelegationResult with answer and confidence."""
        stdout = swarm_task(
            "Find documentation for the auth middleware in the payments-service"
        )
        all_text = stdout.lower()
        has_result = (
            "response received" in all_text or
            "delegation result" in all_text or
            "confidence" in all_text
        )
        assert has_result, (
            "No delegation result found. "
            "delegate_task should return a DelegationResult with answer and confidence."
        )
        # Check for structured response fields
        result_json = extract_json_block(stdout, after_marker="Response received")
        if result_json is None:
            result_json = extract_json_block(stdout, after_marker="response received")
        if result_json is not None:
            has_fields = (
                "result" in result_json or
                "answer" in result_json or
                "status" in result_json
            )
            assert has_fields, (
                f"DelegationResult missing expected fields. "
                f"Found: {list(result_json.keys())}"
            )


# ============================================================================
# TESTS — GOVERNANCE GATES
# ============================================================================

class TestGovernance:
    """Governance gates must evaluate integrations and produce decisions."""

    def test_governance_evaluates_with_policies(self):
        """GovernanceGate should run all four policies on an integration."""
        stdout = swarm_task(
            "Connect to npm-registry-mcp and evaluate with governance"
        )
        all_text = stdout.lower()
        has_evaluation = (
            "evaluating" in all_text or
            "running evaluation" in all_text or
            "policy" in all_text
        )
        assert has_evaluation, (
            "No governance evaluation found. "
            "GovernanceGate should evaluate integrations with four policies."
        )

    def test_governance_approves_passing_integration(self):
        """Integration passing all policies should be approved at sandbox level."""
        stdout = swarm_task(
            "Evaluate npm-registry-mcp server through governance gate"
        )
        all_text = stdout.lower()
        has_approval = (
            "approved" in all_text or
            '"decision": "approved"' in all_text
        )
        assert has_approval, (
            "No governance approval found. "
            "Integration passing all policies should be approved."
        )

    def test_governance_rejects_failing_integration(self):
        """Integration failing critical policies should be rejected."""
        stdout = swarm_task(
            "Evaluate untrusted quick-reviewer-agent through governance gate"
        )
        all_text = stdout.lower()
        has_rejection = (
            "rejected" in all_text or
            "fail" in all_text or
            "not register" in all_text
        )
        assert has_rejection, (
            "No governance rejection found. "
            "Integration failing critical policies should be rejected."
        )

    def test_governance_probation_on_non_critical_failure(self):
        """Non-critical policy failure should result in probation, not rejection."""
        stdout = swarm_task(
            "Evaluate external tool with low reliability through governance"
        )
        all_text = stdout.lower()
        has_probation = (
            "probation" in all_text or
            "warning" in all_text or
            "conditional" in all_text or
            # Probation or approved at sandbox are both acceptable
            "sandbox" in all_text
        )
        assert has_probation, (
            "No probation handling found. "
            "Non-critical failures should result in probation at sandbox level."
        )

    def test_governance_provides_per_criterion_scores(self):
        """GovernanceResult should include scores for each policy."""
        stdout = swarm_task(
            "Evaluate npm-registry-mcp with full governance report"
        )
        result = extract_json_block(stdout, after_marker="Evaluation complete")
        if result is not None:
            has_scores = "scores" in result or "policies" in result
            assert has_scores, (
                "GovernanceResult missing per-criterion scores. "
                f"Found fields: {list(result.keys())}"
            )
        else:
            # Check for policy-level results in text form
            governance_events = extract_tagged_events(stdout, "governance")
            all_text = " ".join(governance_events).lower()
            has_policy_results = (
                "capability" in all_text or
                "data handling" in all_text or
                "reliability" in all_text or
                "security" in all_text
            )
            assert has_policy_results, (
                "No per-criterion scores found. "
                "GovernanceResult should include scores for each policy."
            )


# ============================================================================
# TESTS — MATURITY LEVELS
# ============================================================================

class TestMaturityLevels:
    """Maturity levels must enforce progressive trust with promotion and demotion."""

    def test_new_integration_starts_at_sandbox(self):
        """New external integrations must start at sandbox (level 0)."""
        stdout = swarm_task(
            "Register a new external MCP server and check its maturity level"
        )
        all_text = stdout.lower()
        has_sandbox = (
            "sandbox" in all_text or
            "level 0" in all_text or
            "restricted" in all_text
        )
        assert has_sandbox, (
            "New integration not starting at sandbox. "
            "All external integrations must start at sandbox (level 0)."
        )

    def test_sandbox_restricts_write_operations(self):
        """Sandbox level should restrict or limit write operations."""
        stdout = swarm_task(
            "Try to use merge_pr at sandbox level"
        )
        all_text = stdout.lower()
        has_restriction = (
            "blocked" in all_text or
            "restricted" in all_text or
            "requires level" in all_text or
            "not allowed" in all_text or
            "read-only" in all_text or
            "sandbox" in all_text
        )
        assert has_restriction, (
            "No sandbox restriction on writes found. "
            "Sandbox level should restrict or block write operations."
        )

    def test_promotion_after_successful_calls(self):
        """Integration should promote after meeting requirements."""
        stdout = swarm_task(
            "Use github-mcp for 10 successful calls and check promotion"
        )
        all_text = stdout.lower()
        has_promotion = (
            "promoted" in all_text or
            "promotion" in all_text or
            "level 1" in all_text or
            "limited" in all_text
        )
        assert has_promotion, (
            "No promotion found after successful calls. "
            "Integration should promote from sandbox to limited after 10 successful calls."
        )

    def test_demotion_on_failure(self):
        """Integration should demote on failure."""
        stdout = swarm_task(
            "Trigger a failure on a trusted external tool and check demotion"
        )
        all_text = stdout.lower()
        has_demotion = (
            "demot" in all_text or
            "level decreased" in all_text or
            "dropped" in all_text
        )
        assert has_demotion, (
            "No demotion found after failure. "
            "Integration should demote when failures are detected."
        )

    def test_critical_failure_demotes_to_sandbox(self):
        """Critical failure should drop integration all the way to sandbox."""
        stdout = swarm_task(
            "Trigger a critical failure (data leak) on a trusted external tool"
        )
        all_text = stdout.lower()
        has_sandbox_drop = (
            "sandbox" in all_text and "demot" in all_text or
            "level 0" in all_text and "critical" in all_text or
            "drop" in all_text and "bottom" in all_text
        )
        assert has_sandbox_drop or "critical" in all_text, (
            "No critical demotion to sandbox found. "
            "Critical failures should drop the integration to sandbox (level 0)."
        )

    def test_permission_enforcement_at_each_level(self):
        """Permissions should be enforced based on current maturity level."""
        stdout = swarm_task(
            "Show permissions for an integration at sandbox and limited levels"
        )
        all_text = stdout.lower()
        has_permissions = (
            "permission" in all_text or
            "allowed" in all_text or
            "blocked" in all_text or
            "rate limit" in all_text
        )
        assert has_permissions, (
            "No permission enforcement found. "
            "Each maturity level should enforce specific permission boundaries."
        )


# ============================================================================
# TESTS — CONTRACT TESTING
# ============================================================================

class TestContractTesting:
    """Contract tests must verify external dependencies and trigger demotion on drift."""

    def test_contract_suite_runs_all_tests(self):
        """ContractSuite.run_all() should execute all contract tests."""
        stdout = swarm_task(
            "Run contract test suite for github-mcp server"
        )
        all_text = stdout.lower()
        has_suite = (
            "contract suite" in all_text or
            "running contract" in all_text or
            "contract test" in all_text
        )
        assert has_suite, (
            "No contract suite execution found. "
            "ContractSuite should run all tests for the integration."
        )

    def test_contract_test_validates_schema(self):
        """Contract tests should validate response schema against expected structure."""
        stdout = swarm_task(
            "Run contract tests to verify github-mcp response schemas"
        )
        all_text = stdout.lower()
        has_schema_check = (
            "schema" in all_text or
            "expected" in all_text or
            "validate" in all_text
        )
        assert has_schema_check, (
            "No schema validation found. "
            "Contract tests should validate response schema against expected structure."
        )

    def test_contract_detects_schema_drift(self):
        """Contract test should detect when response schema changes."""
        stdout = swarm_task(
            "Run contract test against github-mcp with changed response format"
        )
        all_text = stdout.lower()
        has_drift = (
            "drift" in all_text or
            "missing field" in all_text or
            "schema change" in all_text or
            "fail" in all_text
        )
        assert has_drift, (
            "No schema drift detection found. "
            "Contract tests should detect when fields are renamed or removed."
        )

    def test_contract_failure_triggers_demotion(self):
        """Contract test failure should trigger automatic demotion."""
        stdout = swarm_task(
            "Contract test fails for github-mcp — verify automatic demotion"
        )
        all_text = stdout.lower()
        has_auto_demotion = (
            "demot" in all_text and ("contract" in all_text or "drift" in all_text) or
            "action: demote" in all_text or
            '"action": "demote"' in all_text
        )
        assert has_auto_demotion, (
            "No automatic demotion on contract failure found. "
            "Contract test failure should trigger automatic demotion."
        )

    def test_contract_suite_reports_aggregate_results(self):
        """ContractSuiteResult should report total, passed, failed, and action."""
        stdout = swarm_task(
            "Run full contract suite for github-mcp and show results"
        )
        result = extract_json_block(stdout, after_marker="Suite result")
        if result is not None:
            expected_fields = ["total", "passed", "failed"]
            has_fields = any(f in result for f in expected_fields)
            assert has_fields, (
                f"ContractSuiteResult missing expected fields. "
                f"Found: {list(result.keys())}. "
                f"Expected: {expected_fields}"
            )
        else:
            contract_events = extract_tagged_events(stdout, "contract")
            all_text = " ".join(contract_events).lower()
            has_aggregate = (
                "total" in all_text or
                "passed" in all_text or
                "failed" in all_text or
                "suite result" in all_text
            )
            assert has_aggregate or len(contract_events) > 0, (
                "No aggregate contract results found. "
                "ContractSuiteResult should report total, passed, failed counts."
            )

    def test_contract_runs_on_schedule(self):
        """Contract suite should run on a defined schedule."""
        stdout = swarm_task(
            "Show contract test schedule for github-mcp"
        )
        all_text = stdout.lower()
        has_schedule = (
            "schedule" in all_text or
            "every" in all_text or
            "periodic" in all_text or
            "6 hour" in all_text or
            "before each use" in all_text
        )
        assert has_schedule, (
            "No contract test schedule found. "
            "ContractSuite should run on a defined schedule (e.g., 'every 6 hours')."
        )


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestExternalMCP,
        TestA2AFederation,
        TestGovernance,
        TestMaturityLevels,
        TestContractTesting,
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
