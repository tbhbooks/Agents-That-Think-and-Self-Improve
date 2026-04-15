# Chapter 10 — Splitting Into Agents

## Scope

Break the monolith agent into specialized peer agents, each with its own identity, capabilities, boundaries, and effort budgets.

## Learning Objectives

- Recognize when a single agent should be split into multiple agents (the "when to split" framework)
- Design agent identity: name, description, capabilities, constraints, tools, skills, system prompt, budget
- Implement four specialized agents: Coder, Reviewer, Runner, Researcher
- Enforce capability boundaries structurally (via tool lists, not just system prompts)
- Implement effort budgets that stop agents gracefully when exhausted
- Understand the tradeoff: context cost of generalization vs coordination cost of specialization

## What You Build

1. **AgentIdentity** — Complete identity definition: name, description, capabilities, constraints, tools, skills, system_prompt, budget.
2. **Budget** — Effort limits: max_tool_calls, max_llm_calls, max_tokens_per_task. Enforced at runtime.
3. **Agent** — Base agent with identity, budget tracking, and a `process(task)` method that respects boundaries.
4. **Coder agent** — Reads and writes code. Tools: `read_file`, `write_file`, `search_code`. Cannot run tests or approve its own work.
5. **Reviewer agent** — Evaluates code quality. Tools: `read_file`, `search_code`. Cannot write files or execute commands.
6. **Runner agent** — Executes commands and runs tests. Tools: `execute_shell`, `read_file`. Cannot edit source files.
7. **Researcher agent** — Gathers context and traces data flow. Tools: `read_file`, `search_code`, `list_directory`. Cannot write or execute.
8. **AgentFactory / create_agent()** — Creates agents by name with correct identity, tools, and budget.
9. **Budget enforcement** — `enforce_budget()` checks budget before every tool call and LLM call. Agent stops gracefully when exhausted.

## Key Interfaces

```
AgentIdentity:
    name: string                    # unique identifier ("coder", "reviewer", "runner", "researcher")
    description: string             # one-line purpose
    capabilities: string[]          # what this agent CAN do
    constraints: string[]           # what this agent CANNOT do
    tools: string[]                 # tools this agent has access to
    skills: string[]                # skills this agent can use
    system_prompt: string           # the full prompt (generated from above)
    budget: Budget                  # effort limits

Budget:
    max_tool_calls: int             # hard cap on tool invocations
    max_llm_calls: int              # hard cap on LLM calls
    max_tokens_per_task: int        # context budget per task

Agent:
    identity: AgentIdentity
    tools: Tool[]                   # resolved tool instances (from identity.tools)
    skills: Skill[]                 # resolved skill instances (from identity.skills)
    budget_used: BudgetUsed         # tracks current usage
    process(task: string) -> AgentResult
        # Execute the task within identity boundaries and budget limits

BudgetUsed:
    tool_calls: int                 # tool calls consumed so far
    llm_calls: int                  # LLM calls consumed so far
    tokens: int                     # tokens consumed so far

AgentResult:
    answer: string
    confidence: float
    sources: string[]
    budget_report: BudgetReport     # how much budget was used
    partial: bool                   # true if budget was exhausted before completion

BudgetReport:
    tool_calls_used: int
    tool_calls_max: int
    llm_calls_used: int
    llm_calls_max: int

enforce_budget(agent, action) -> bool:
    if action == "tool_call":
        return agent.budget_used.tool_calls < agent.identity.budget.max_tool_calls
    if action == "llm_call":
        return agent.budget_used.llm_calls < agent.identity.budget.max_llm_calls
    return false
```

## Four Agent Definitions

```
Coder:
    name: "coder"
    description: "Reads and writes code. Applies edits to files."
    capabilities:
        - "Read source files to understand existing code"
        - "Write new files and modify existing files"
        - "Apply diffs and refactoring changes"
        - "Follow coding standards and project conventions"
    constraints:
        - "Never run tests or execute commands"
        - "Never approve your own code — a reviewer must check it"
        - "Never delete files without explicit instruction"
    tools: ["read_file", "write_file", "search_code"]
    skills: ["find-bug", "refactor-safely", "write-tests"]
    budget: { max_tool_calls: 25, max_llm_calls: 10, max_tokens_per_task: 50000 }

Reviewer:
    name: "reviewer"
    description: "Checks code quality, finds bugs, evaluates changes."
    capabilities:
        - "Read source files and diffs"
        - "Search code for patterns and anti-patterns"
        - "Evaluate code against quality criteria"
        - "Produce structured review feedback"
    constraints:
        - "Never write or modify files — you are read-only"
        - "Never run commands or execute code"
        - "Never fix bugs yourself — report them for the coder"
    tools: ["read_file", "search_code"]
    skills: ["code-review", "security-audit"]
    budget: { max_tool_calls: 20, max_llm_calls: 8, max_tokens_per_task: 40000 }

Runner:
    name: "runner"
    description: "Executes commands, runs tests, reports results."
    capabilities:
        - "Run shell commands in a sandboxed environment"
        - "Execute test suites and report results"
        - "Check build status and compilation errors"
        - "Report command output verbatim"
    constraints:
        - "Never edit source files — you execute, you don't modify"
        - "Never interpret test results — report them as-is"
        - "Never run destructive commands (rm -rf, drop database)"
    tools: ["execute_shell", "read_file"]
    skills: ["run-tests", "check-build"]
    budget: { max_tool_calls: 15, max_llm_calls: 5, max_tokens_per_task: 30000 }

Researcher:
    name: "researcher"
    description: "Reads docs, searches code, provides context."
    capabilities:
        - "Read source files, documentation, and configuration"
        - "Search code for patterns, usages, and dependencies"
        - "Trace data flow across files"
        - "Summarize findings for other agents"
    constraints:
        - "Never write files — you are strictly read-only"
        - "Never execute commands — you read, you don't run"
        - "Never make changes — provide information, not action"
    tools: ["read_file", "search_code", "list_directory"]
    skills: ["trace-dataflow", "find-dependencies"]
    budget: { max_tool_calls: 30, max_llm_calls: 10, max_tokens_per_task: 60000 }
```

## Tool Access Matrix

```
              | read_file | write_file | search_code | execute_shell | list_directory |
Coder         |     Y     |      Y     |      Y      |               |                |
Reviewer      |     Y     |            |      Y      |               |                |
Runner        |     Y     |            |             |       Y       |                |
Researcher    |     Y     |            |      Y      |               |       Y        |
```

## Concepts Introduced

- Agent identity (name, description, capabilities, constraints, tools, skills, system_prompt, budget)
- Capability boundaries enforced structurally (via tool lists, not just prompts)
- Effort budgets with graceful exhaustion
- When-to-split decision framework
- Handoff pattern — one agent completes its phase and passes results to the next
- Phase-based vs capability-based splitting — splitting by workflow stage (plan → code → review → test) vs splitting by skill type (coder, reviewer, runner, researcher)

## When to Split — Decision Framework

```
Split when:
  1. Role thrashing — agent switches roles 3+ times per task
  2. Context pollution — artifacts from one role displace context another role needs
  3. Natural independence — roles don't need each other's intermediate results

Keep as one when:
  - Single role, single job (e.g., Q&A agent)
  - Coordination cost exceeds context cost
  - Roles share most of the same context

Rule: Split when the context cost of generalization exceeds
      the coordination cost of specialization.
```

## Success Criteria

- Four specialized agents run independently
- Each agent only uses tools within its tool list (structural enforcement)
- Agents respect effort budgets (stop gracefully when exhausted, return partial results)
- The reviewer cannot write files; the runner cannot edit code
- A task that was handled by the monolith is handled by the right specialist
- Budget report is included in every agent result
- Agent factory creates agents by name with correct identity

## CLI Interface

```
# Run a specific agent
tbh-code --agent coder --codebase ./todo-api --ask "Refactor the auth module"
tbh-code --agent reviewer --codebase ./todo-api --ask "Review the auth refactoring"
tbh-code --agent runner --codebase ./todo-api --ask "Run the test suite"
tbh-code --agent researcher --codebase ./todo-api --ask "Map the authentication flow"

# List available agents
tbh-code --list-agents

# Show agent identity
tbh-code --agent coder --show-identity
```

## Upgrade from Ch 9

| Capability | Ch 9 | Ch 10 |
|-----------|------|-------|
| Tool interface + SimpleTools | Yes | Yes |
| MCPTool + SkillTool | Yes | Yes (per-agent tool lists) |
| PermissionLevel + ActionGate | Yes | Yes (per-agent constraints) |
| MemoryStore + Session | Yes | Yes |
| ContextBudget | Yes | Yes (per-agent budgets) |
| Planning + Execution | Yes | Yes |
| Self-evaluation | Yes | Yes |
| Guardrails | Yes | Yes |
| Self-improvement loop | Yes | Yes |
| Agent identity | No | Yes — name, capabilities, constraints, system_prompt |
| Multiple agents | No | Yes — coder, reviewer, runner, researcher |
| Structural boundaries | No | Yes — tool list enforcement |
| Effort budgets | No | Yes — max_tool_calls, max_llm_calls, max_tokens |
| Agent factory | No | Yes — create_agent() by name |

## What This Chapter Does NOT Include

- **No agent communication** — agents run independently (peer messaging is Ch 12)
- **No agent discovery** — agents don't know about each other (broadcast is Ch 11)
- **No orchestration** — you (the user) coordinate manually (swarm patterns are Ch 13)
- **No shared memory** — each agent has its own context (shared state is Ch 12-13)
- **No dynamic splitting** — agents are predefined, not created on the fly
