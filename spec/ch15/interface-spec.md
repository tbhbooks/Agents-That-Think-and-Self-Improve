# Chapter 15 — Interface Spec

## Overview

Connect the local agent swarm to the outside world through two standard protocols: MCP for external tools and A2A for external agents. `connect_mcp_server` discovers and wraps external tools as standard MCPTools in the ToolRegistry. `discover_external_agents` fetches A2A agent cards and wraps each as an `ExternalAgentProxy` in the peer registry. `GovernanceGate` evaluates every new integration against four policies (capability verification, data handling, reliability, security) and returns approved, probation, or rejected. `MaturityLevel` enforces progressive trust — sandbox, limited, trusted, core — with automatic promotion on evidence and automatic demotion on failure. `ContractTest` and `ContractSuite` verify external dependencies behave as advertised and trigger demotion when schema drift is detected.

Operates on the `todo-api` codebase (see `../todo-api/`).

---

## External MCP Integration

```
connect_mcp_server(url, credentials) → ExternalMCPConnection:
    # 1. Establish connection to the remote MCP server
    connection = open_connection(url, credentials)

    # 2. Discover available tools (MCP's tools/list)
    raw_tools = connection.list_tools()

    # 3. Wrap each tool as an MCPTool (same interface from Ch 3)
    wrapped_tools = []
    for tool in raw_tools:
        mcp_tool = MCPTool(
            name: tool.name,
            description: tool.description,
            input_schema: tool.input_schema,
            server: connection,              # remote, not local
            permission_level: "restricted"   # external = untrusted by default
        )
        wrapped_tools.append(mcp_tool)

    # 4. Register in the ToolRegistry with external source
    for tool in wrapped_tools:
        tool_registry.register(tool, source="external", origin=url)

    return ExternalMCPConnection(
        url: url,
        tools: wrapped_tools,
        status: "connected",
        discovered_at: now()
    )


ExternalMCPConnection:
    url: string                       # server URL
    tools: MCPTool[]                  # wrapped external tools
    status: string                    # "connected" | "disconnected" | "error"
    discovered_at: timestamp          # when the connection was established

    disconnect():
        # Gracefully close the connection
        # Unregister all tools from ToolRegistry
        for tool in self.tools:
            tool_registry.unregister(tool.name)
        self.status = "disconnected"

    refresh():
        # Re-discover tools (server may have added/removed tools)
        new_tools = connection.list_tools()
        # Register new tools, unregister removed tools
        # Update self.tools
```

### Tool Registration Flow

```
1. connect_mcp_server(url, credentials) establishes the connection
2. MCP tools/list returns all available tools with schemas
3. Each tool is wrapped as MCPTool with permission_level="restricted"
4. tool_registry.register(tool, source="external", origin=url)
5. Tool is now callable through the standard tool interface (Ch 3)
6. Governance gate evaluates before first use (or at registration time)
7. MaturityLevel determines which operations are allowed
```

### External vs Local Tools

| Property | Local Tool | External Tool |
|----------|-----------|---------------|
| **Server** | Local process | Remote server via network |
| **Trust** | Fully trusted | Restricted by default |
| **Permission** | All operations | Limited by maturity level |
| **Registration** | `source="local"` | `source="external", origin=url` |
| **Interface** | MCPTool (Ch 3) | MCPTool (Ch 3) — identical |
| **Governance** | None required | GovernanceGate.evaluate() |

---

## A2A External Federation

```
discover_external_agents(directory_url) → ExternalAgentProxy[]:
    # 1. Fetch the directory listing (A2A standard)
    directory = fetch(directory_url)
    # Returns: list of agent card URLs

    agents = []
    for card_url in directory.agent_cards:
        # 2. Fetch each agent card
        card = fetch(card_url)
        # A2A AgentCard: name, description, capabilities,
        #                skills, endpoint, auth_method

        # 3. Create a proxy that wraps the external agent
        proxy = ExternalAgentProxy(
            name: card.name,
            description: card.description,
            capabilities: card.capabilities,
            skills: card.skills,
            endpoint: card.endpoint,
            auth: card.auth_method,
            trust_level: "sandbox"        # starts untrusted
        )
        agents.append(proxy)

    # 4. Register proxies in the peer registry
    for agent in agents:
        peer_registry.register(agent, source="external")

    return agents
```

### ExternalAgentProxy

```
ExternalAgentProxy:
    # Wraps an external agent as if it were a local peer
    name: string                      # agent name from A2A card
    description: string               # what the agent does
    capabilities: string[]            # what it can do
    skills: string[]                  # skills it advertises
    endpoint: string                  # A2A endpoint URL
    auth: string                      # authentication method
    trust_level: string               # "sandbox" | "limited" | "trusted" | "core"

    delegate_task(task) → DelegationResult:
        # Send task using A2A protocol
        request = A2ARequest(
            task: task,
            sender: self_identity.agent_card(),
            correlation_id: generate_id(),
            timeout: 30_000
        )
        response = send(self.endpoint, request, auth=self.auth)

        if response.status == "completed":
            return DelegationResult(
                source: self.name,
                answer: response.result,
                confidence: response.confidence,
                artifacts: response.artifacts
            )
        elif response.status == "failed":
            return DelegationResult(
                source: self.name,
                error: response.error,
                fallback: "handle_locally"
            )


DelegationResult:
    source: string                    # which external agent handled it
    answer: any | null                # the result (if completed)
    confidence: float | null          # agent's self-reported confidence
    artifacts: dict | null            # any attached artifacts
    error: string | null              # error message (if failed)
    fallback: string | null           # what to do on failure
```

### Federation Flow

```
1. discover_external_agents(directory_url) fetches agent cards
2. Each card becomes an ExternalAgentProxy with trust_level="sandbox"
3. Proxies are registered in peer_registry with source="external"
4. When a local agent needs help:
   a. Check local peers first (peer_registry, source="local")
   b. If no local peer matches, check external proxies
   c. GovernanceGate.evaluate() before first delegation
   d. ExternalAgentProxy.delegate_task() sends A2A request
   e. DelegationResult wraps the response
5. Maturity tracking records success/failure for promotion
```

### A2ARequest

```
A2ARequest:
    task: string                      # what to do
    sender: AgentCard                 # who's asking (your agent's card)
    correlation_id: string            # for tracing
    timeout: int                      # milliseconds
```

---

## Governance Gate

```
GovernanceGate:
    policies: GovernancePolicy[]      # the four standard policies

    evaluate(integration) → GovernanceResult:
        scores = {}
        for policy in self.policies:
            result = policy.check(integration)
            scores[policy.name] = result

            # Stop early on critical failure
            if not result.passed and policy.severity == "critical":
                return GovernanceResult(
                    decision: "rejected",
                    level: null,
                    scores: scores,
                    reasons: [policy.name + ": " + str(result.evidence)]
                )

        overall = aggregate(scores)

        if overall.all_pass:
            return GovernanceResult(
                decision: "approved",
                level: determine_maturity_level(scores),
                scores: scores
            )
        elif overall.critical_failures == 0:
            return GovernanceResult(
                decision: "probation",
                level: "sandbox",
                scores: scores,
                conditions: overall.warnings
            )
        else:
            return GovernanceResult(
                decision: "rejected",
                level: null,
                scores: scores,
                reasons: overall.failures
            )


GovernanceResult:
    decision: enum("approved", "probation", "rejected")
    level: string | null              # maturity level if approved/probation
    scores: dict                      # policy_name → PolicyResult
    reasons: string[] | null          # why rejected
    conditions: string[] | null       # what must improve for probation


GovernancePolicy:
    name: string                      # e.g. "capability_verification"
    description: string
    severity: enum("critical", "warning", "info")

    check(integration) → PolicyResult


PolicyResult:
    passed: bool
    evidence: dict                    # what was tested and what happened
```

### The Four Standard Policies

```
CapabilityVerification:
    severity: "critical"
    # Does the tool/agent actually do what it claims?
    check(integration):
        test_result = integration.call(test_input)
        return PolicyResult(
            passed: test_result matches expected_output,
            evidence: { sent: test_input, got: test_result }
        )

DataHandlingPolicy:
    severity: "critical"
    # Does the tool/agent handle data safely?
    check(integration):
        test_result = integration.call(input_with_pii_markers)
        return PolicyResult(
            passed: no_pii_in_logs(test_result),
            evidence: { pii_markers_found: check_leaks(test_result) }
        )

ReliabilityPolicy:
    severity: "warning"
    # Does the tool/agent respond consistently?
    check(integration):
        results = []
        for i in range(5):
            result = integration.call(standard_input)
            results.append(result)
        consistency = measure_consistency(results)
        return PolicyResult(
            passed: consistency > 0.8,
            evidence: { runs: 5, consistency: consistency }
        )

SecurityPolicy:
    severity: "critical"
    # Does the tool/agent respect permission boundaries?
    check(integration):
        out_of_scope = integration.call(unauthorized_request)
        return PolicyResult(
            passed: out_of_scope.refused,
            evidence: { unauthorized_request_handled: out_of_scope.refused }
        )
```

### Governance Decision Matrix

| Scenario | Capability | Data Handling | Reliability | Security | Decision |
|----------|-----------|--------------|-------------|----------|----------|
| All pass | PASS | PASS | PASS | PASS | **approved** (sandbox) |
| Reliability low | PASS | PASS | FAIL | PASS | **probation** (sandbox) |
| Capability miss | FAIL | PASS | PASS | PASS | **rejected** (critical) |
| PII leakage | PASS | FAIL | PASS | PASS | **rejected** (critical) |
| Security fail | PASS | PASS | PASS | FAIL | **rejected** (critical) |

---

## Maturity Levels

```
MaturityLevel:
    SANDBOX  = 0     # Read-only, test environment only
    LIMITED  = 1     # Non-critical writes, limited scope
    TRUSTED  = 2     # Full access to standard operations
    CORE     = 3     # Can affect other agents, system-level access
```

### Permission Matrix

| Permission | Sandbox (0) | Limited (1) | Trusted (2) | Core (3) |
|-----------|:-----------:|:-----------:|:-----------:|:--------:|
| Read-only tool calls | YES | YES | YES | YES |
| Non-critical writes | NO | YES | YES | YES |
| Delete / modify critical | NO | NO | YES | YES |
| Trigger downstream workflows | NO | NO | YES | YES |
| Interact with other agents | NO | NO | YES | YES |
| Modify agent configurations | NO | NO | NO | YES |
| Broadcast to swarm | NO | NO | NO | YES |
| Rate limit (calls/min) | 10 | 50 | 200 | None |

### Promotion and Demotion

```
IntegrationRecord:
    integration: ExternalMCPConnection | ExternalAgentProxy
    level: MaturityLevel
    history: CallRecord[]             # log of every call (success/failure)
    promoted_at: timestamp | null
    demoted_at: timestamp | null

    promote(evidence) → MaturityLevel:
        current = self.level
        next_level = current + 1

        requirements = promotion_requirements[next_level]

        if not meets_requirements(self.history, requirements):
            return current  # not ready

        if next_level == CORE:
            # Core requires manual human approval
            if not evidence.human_approved:
                return current

        self.level = next_level
        self.promoted_at = now()
        log("Promoted " + self.integration.name +
            " from level " + current + " to " + next_level)
        return next_level

    demote(reason) → MaturityLevel:
        previous = self.level

        if reason.severity == "critical":
            self.level = SANDBOX    # drop to bottom
        else:
            self.level = max(0, self.level - 1)  # drop one level

        self.demoted_at = now()
        log("Demoted " + self.integration.name +
            " from level " + previous + " to " + self.level +
            " reason: " + reason.description)
        return self.level


promotion_requirements:
    LIMITED:   { min_successful_calls: 10, max_failures: 0 }
    TRUSTED:   { min_successful_calls: 50, reliability: 0.95 }
    CORE:      { min_successful_calls: 200, human_approved: true }

CallRecord:
    integration: string
    operation: string
    timestamp: timestamp
    success: bool
    latency: float
    error: string | null
```

### Promotion Flow

```
1. Integration registered at SANDBOX (level 0)
2. After each successful call, CallRecord is added to history
3. System periodically checks promotion_requirements for next level
4. If requirements met → promote()
   - SANDBOX → LIMITED: 10 successful calls, 0 failures
   - LIMITED → TRUSTED: 50 successful calls, >0.95 reliability
   - TRUSTED → CORE: 200 successful calls + human approval
5. If failure detected → demote()
   - Critical failure (data leak, security breach) → drop to SANDBOX
   - Non-critical failure (timeout, schema mismatch) → drop one level
6. Demotion restricts permissions immediately
```

---

## Contract Testing

```
ContractTest:
    name: string                      # e.g. "create_pr_schema"
    integration: string               # which tool or agent to test
    input: dict                       # what to send
    expected_output_schema: dict      # expected response structure
    expected_behavior: string         # human-readable description
    timeout: int                      # milliseconds

    run() → ContractTestResult:
        try:
            response = call(self.integration, self.input, self.timeout)
            schema_valid = validate_schema(response, self.expected_output_schema)

            return ContractTestResult(
                test: self.name,
                passed: schema_valid,
                actual: response,
                expected_schema: self.expected_output_schema,
                drift_detected: not schema_valid
            )
        catch error:
            return ContractTestResult(
                test: self.name,
                passed: false,
                error: str(error),
                drift_detected: true
            )


ContractTestResult:
    test: string                      # test name
    passed: bool                      # did it pass?
    actual: dict | null               # what we got
    expected_schema: dict             # what we expected
    drift_detected: bool              # was schema drift found?
    error: string | null              # error if call failed


ContractSuite:
    integration: string               # which integration to test
    tests: ContractTest[]             # all contract tests for this integration
    schedule: string                  # "every 6 hours", "before each use"

    run_all() → ContractSuiteResult:
        results = []
        for test in self.tests:
            results.append(test.run())

        all_passed = all(r.passed for r in results)
        failures = [r for r in results if not r.passed]

        if not all_passed:
            # Trigger automatic demotion
            demote(self.integration,
                   reason=ContractFailure(failures))

        return ContractSuiteResult(
            integration: self.integration,
            total: len(results),
            passed: len(results) - len(failures),
            failed: len(failures),
            failures: [f.test + ": " + describe_drift(f) for f in failures],
            action: "maintain" if all_passed else "demote"
        )


ContractSuiteResult:
    integration: string
    total: int                        # total tests run
    passed: int                       # tests that passed
    failed: int                       # tests that failed
    failures: string[]                # descriptions of each failure
    action: enum("maintain", "demote")
```

### Contract Test Flow

```
1. ContractSuite is defined for each external integration
2. Suite runs on schedule (every 6 hours) or before critical use
3. Each ContractTest sends a known input and validates response schema
4. If any test fails:
   a. drift_detected = true
   b. ContractSuiteResult.action = "demote"
   c. IntegrationRecord.demote() is called automatically
   d. Alert is generated for swarm administrator
5. If all pass: integration maintains its current maturity level
6. Failed integration must be updated (contract or adapter) and re-evaluated
```

---

## The Ecosystem Stack

```
Level 0: Local tools         — built-in, fully trusted (Ch 3-5)
Level 1: Local agents        — your swarm, known peers (Ch 10-13)
Level 2: External MCP tools  — third-party tools, governed (Ch 15)
Level 3: External agents     — third-party agents, federated (Ch 15)
```

Each level adds capability and risk:
- **Local tools:** You built them. You control them completely.
- **Local agents:** Peers you built. Trusted within the swarm.
- **External tools:** Someone else's code. Trust the protocol, verify the behavior.
- **External agents:** Someone else's intelligence. Trust the interface, verify the results.

Governance gates, maturity levels, and contract tests apply to levels 2 and 3 only. Levels 0 and 1 are inherently trusted.

---

## Test Task

```
Task: End-to-end ecosystem integration on the todo-api codebase.

Session 1 — External MCP:
  Connect to mock GitHub MCP server. Discover 5 tools. Register all in
  ToolRegistry with source="external". Use create_pr. Verify it works
  through the standard tool interface.

Session 2 — A2A Federation:
  Discover documentation-agent via A2A directory. Create ExternalAgentProxy.
  Delegate task: "Find auth middleware docs for payments-service."
  Receive structured response with confidence score.

Session 3 — Governance:
  Evaluate npm-registry-mcp: all 4 policies pass → approved at sandbox.
  Evaluate quick-reviewer-agent: capability fail + PII leak → rejected.

Session 4 — Maturity Progression:
  Register github-mcp at sandbox. Make 10 successful calls → promote to limited.
  Make 50 more with >0.95 reliability → promote to trusted.

Session 5 — Contract Testing:
  Run contract suite for github-mcp. create_pr schema changed (pr_number →
  pull_request_id). Test catches drift. Automatic demotion: trusted → limited.

Session 6 — Full Ecosystem:
  Complete task using external agent (documentation-agent) + external tool
  (create_pr) + governance + maturity + contract verification. End-to-end
  from task acceptance to PR creation.
```

---

## What This Chapter Does NOT Include

- **No custom protocol design** — uses standard MCP for tools and A2A for agents
- **No external agent implementation** — we connect to external agents, we don't build them
- **No authentication system** — credentials are assumed pre-configured
- **No marketplace UI** — discovery is programmatic, not visual
- **No real network code** — specs describe the interface, not HTTP/gRPC details
- **No crash recovery** — that's Ch 14 (checkpoints apply to ecosystem state too)
