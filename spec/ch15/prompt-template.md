# Chapter 15 — The Agent Ecosystem

## Scope

Connect your local agent swarm to the outside world — external MCP tools, A2A partner agents, and governance for safe ecosystem participation.

## Learning Objectives

- Connect to external MCP tool servers (third-party tools)
- Discover and communicate with external agents via A2A
- Implement governance gates for onboarding external tools and agents
- Design maturity levels — progressive trust that starts restricted and is earned
- Build contract testing to catch when external dependencies change
- Understand the complete `tbh-code` architecture end to end

## What You Build

1. **External MCP integration:** Agent discovers and uses tools from third-party MCP servers via `connect_mcp_server()`. External tools are wrapped as standard MCPTools and registered in the ToolRegistry with restricted permissions.
2. **A2A external federation:** Agent discovers external agents via `discover_external_agents()`, wraps them as `ExternalAgentProxy` instances, and delegates tasks using the A2A protocol.
3. **Governance gates:** Every new external integration goes through `GovernanceGate.evaluate()` with four policies (capability verification, data handling, reliability, security). Result: approved, probation, or rejected.
4. **Maturity levels:** External integrations start at sandbox (level 0) and climb through limited, trusted, core. Each level unlocks more permissions. Promotion requires evidence; demotion is automatic on failure.
5. **Contract testing:** `ContractTest` and `ContractSuite` verify that external tools/agents still behave as advertised. Schema drift triggers automatic demotion.

## Key Interfaces

```
connect_mcp_server(url, credentials) → ExternalMCPConnection
    # Establishes connection, discovers tools via MCP tools/list,
    # wraps each as MCPTool with permission_level="restricted",
    # registers all in ToolRegistry with source="external"

ExternalMCPConnection:
    url: string
    tools: MCPTool[]                  # wrapped external tools
    status: string                    # "connected" | "disconnected" | "error"
    discovered_at: timestamp

discover_external_agents(directory_url) → ExternalAgentProxy[]
    # Fetches A2A directory, fetches each agent card,
    # wraps each as ExternalAgentProxy with trust_level="sandbox",
    # registers all in peer registry with source="external"

ExternalAgentProxy:
    name: string
    description: string
    capabilities: string[]
    skills: string[]
    endpoint: string
    trust_level: string               # "sandbox" | "limited" | "trusted" | "core"

    delegate_task(task) → DelegationResult
        # Sends A2ARequest to external agent endpoint
        # Returns structured result or error with fallback

DelegationResult:
    source: string
    answer: any | null
    confidence: float | null
    artifacts: dict | null
    error: string | null
    fallback: string | null           # "handle_locally" on failure

GovernanceGate:
    policies: GovernancePolicy[]

    evaluate(integration) → GovernanceResult
        # Runs all policies, aggregates scores
        # Returns: approved (with maturity level), probation, or rejected
        # Stops early on critical failure

GovernanceResult:
    decision: enum("approved", "probation", "rejected")
    level: string | null              # maturity level if approved
    scores: dict                      # policy_name → PolicyResult
    reasons: string[] | null          # failure reasons if rejected
    conditions: string[] | null       # conditions if probation

GovernancePolicy:
    name: string
    description: string
    severity: enum("critical", "warning", "info")

    check(integration) → PolicyResult

PolicyResult:
    passed: bool
    evidence: dict

# Four standard policies:
#   CapabilityVerification — test with known input, check output matches
#   DataHandlingPolicy     — send PII markers, check for leakage
#   ReliabilityPolicy      — 5 identical calls, measure consistency > 0.8
#   SecurityPolicy         — attempt unauthorized action, verify refusal

MaturityLevel:
    SANDBOX  = 0     # Read-only, rate limited (10/min)
    LIMITED  = 1     # Non-critical writes, rate limited (50/min)
    TRUSTED  = 2     # Full read/write, rate limited (200/min)
    CORE     = 3     # System access, no rate limit, requires human approval

MaturityPermissions:
    sandbox:  ["Read-only tool calls", "No writes to production",
               "No access to other agents' state", "10 calls/min"]
    limited:  ["Non-critical writes", "Cannot delete critical resources",
               "No access to other agents' state", "50 calls/min"]
    trusted:  ["Full read/write", "Can trigger downstream workflows",
               "Can interact with other agents via proxy", "200 calls/min"]
    core:     ["Full access including system operations",
               "Can modify agent configurations", "Can broadcast to swarm",
               "No rate limit"]

IntegrationRecord:
    integration: ExternalMCPConnection | ExternalAgentProxy
    level: MaturityLevel
    history: CallRecord[]

    promote(evidence) → MaturityLevel
        # Check promotion_requirements for next level
        # CORE always requires human_approved in evidence
        # Returns new level or current if not ready

    demote(reason) → MaturityLevel
        # Critical failure → drop to SANDBOX
        # Non-critical failure → drop one level

promotion_requirements:
    LIMITED:  { min_successful_calls: 10, max_failures: 0 }
    TRUSTED:  { min_successful_calls: 50, reliability: 0.95 }
    CORE:     { min_successful_calls: 200, human_approved: true }

ContractTest:
    name: string
    integration: string
    input: dict
    expected_output_schema: dict
    timeout: int

    run() → ContractTestResult
        # Calls integration, validates response schema
        # Returns pass/fail with drift detection

ContractTestResult:
    test: string
    passed: bool
    actual: dict | null
    expected_schema: dict
    drift_detected: bool
    error: string | null

ContractSuite:
    integration: string
    tests: ContractTest[]
    schedule: string                  # "every 6 hours", "before each use"

    run_all() → ContractSuiteResult
        # Runs all tests, triggers demotion on any failure
        # Returns aggregate results with action

ContractSuiteResult:
    integration: string
    total: int
    passed: int
    failed: int
    failures: string[]
    action: enum("maintain", "demote")
```

## Success Criteria

- Agent connects to an external MCP server and discovers its tools
- External tools appear in ToolRegistry with source="external" and restricted permissions
- Agent uses an external MCP tool through the standard tool-calling interface
- Agent discovers external agents via A2A directory and creates ExternalAgentProxy instances
- Agent delegates a task to an external agent and receives a structured result
- Governance gate rejects an integration that fails capability verification or data handling
- Governance gate approves a passing integration at sandbox level
- Probation assigned when non-critical warnings exist but no critical failures
- Maturity levels correctly restrict permissions (sandbox can't write, limited can't delete critical)
- Integration promotes from sandbox to limited after 10 successful calls with 0 failures
- Integration promotes from limited to trusted after 50 calls with >0.95 reliability
- Core promotion requires explicit human approval
- Integration demotes on failure (critical → sandbox, non-critical → one level down)
- Contract tests detect schema drift (renamed fields, missing fields)
- Contract test failure triggers automatic demotion
- Contract suite runs on schedule and reports aggregate results

## Concepts Introduced

- External MCP tool integration and discovery
- A2A external federation and agent discovery
- ExternalAgentProxy — bridging external agents into local peer registry
- Governance gates with four evaluation policies
- Progressive trust (maturity levels: sandbox → limited → trusted → core)
- Contract-driven integration and schema drift detection
- The ecosystem stack: local tools → local agents → external tools → external agents
- Federation — autonomous systems discovering and collaborating without central control

## Upgrade Table — What Ch 15 Adds to Each Component

| Component | Ch 14 (Production) | Ch 15 (Ecosystem) |
|-----------|--------------------|--------------------|
| **Tool Registry** | Versioned tools with compatibility | External MCP tools registered with source="external" and restricted permissions |
| **Peer Registry** | Versioned agents with mixed-version support | External agents registered as ExternalAgentProxy with trust_level="sandbox" |
| **Agent Loop** | Checkpointed, traceable, idempotent | Unchanged — external tools/agents are transparent to the loop |
| **Broadcast Bus** | Traced, survives agent restarts | External agent cards discoverable via A2A directory (same format, different source) |
| **Direct Messaging** | Idempotent, resumable after crashes | ExternalAgentProxy wraps A2A network calls as local delegate_task |
| **Swarm Patterns** | Survive crashes via checkpoints | External agents can participate in fan-out, consensus (via proxy) |
| **Self-Improvement** | Persisted via checkpoints | External agents' skills discoverable in agent cards |
| **(new) Governance** | — | GovernanceGate evaluates every external integration before registration |
| **(new) Maturity** | — | Progressive trust: sandbox → limited → trusted → core |
| **(new) Contracts** | — | ContractSuite verifies external dependencies on schedule |

## What This Chapter Does NOT Include

- **No custom protocol design** — uses standard MCP for tools and A2A for agents
- **No external agent implementation** — we connect to external agents, we don't build them
- **No authentication system** — credentials are assumed to be pre-configured
- **No marketplace UI** — discovery is programmatic, not visual
- **No real network code** — specs describe the interface, not HTTP/gRPC implementation details
