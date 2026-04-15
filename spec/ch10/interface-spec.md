# Chapter 10 — Interface Spec

## Overview

Split the monolith agent into four specialized agents. Each agent has an `AgentIdentity` (name, description, capabilities, constraints, tools, skills, system_prompt, budget), a `Budget` with hard limits on tool calls / LLM calls / tokens, and a `process(task)` method that executes within boundaries. `enforce_budget()` checks limits before every action. An `AgentFactory` creates agents by name with correct configuration. Boundaries are structural — enforced by tool lists, not just system prompts.

Operates on the `todo-api` codebase (see `../todo-api/`).

---

## AgentIdentity

```
AgentIdentity:
    name: string                    # unique identifier
    description: string             # one-line purpose
    capabilities: string[]          # what this agent CAN do
    constraints: string[]           # what this agent CANNOT do
    tools: string[]                 # tools this agent has access to
    skills: string[]                # skills this agent can use
    system_prompt: string           # the full prompt (generated from above)
    budget: Budget                  # effort limits

    generate_system_prompt() -> string
        # Render identity fields into a system prompt
        # Capabilities become "You can..." lines
        # Constraints become "You must never..." lines
        # Tools and skills are listed explicitly

        prompt = "You are {name}. {description}\n\n"
        prompt += "Capabilities:\n"
        for cap in capabilities:
            prompt += "- You can: {cap}\n"
        prompt += "\nConstraints:\n"
        for con in constraints:
            prompt += "- You must never: {con}\n"
        prompt += "\nAvailable tools: {', '.join(tools)}\n"
        prompt += "Available skills: {', '.join(skills)}\n"
        prompt += "\nBudget: {budget.max_tool_calls} tool calls, "
        prompt += "{budget.max_llm_calls} LLM calls, "
        prompt += "{budget.max_tokens_per_task} tokens per task.\n"
        return prompt
```

### Required Fields

Every `AgentIdentity` must have all 8 fields populated:
- `name` — non-empty string
- `description` — non-empty string
- `capabilities` — at least one capability
- `constraints` — at least one constraint
- `tools` — at least one tool
- `skills` — at least one skill
- `system_prompt` — non-empty (generated or provided)
- `budget` — valid Budget with all three limits > 0

---

## Budget

```
Budget:
    max_tool_calls: int             # hard cap on tool invocations (> 0)
    max_llm_calls: int              # hard cap on LLM calls (> 0)
    max_tokens_per_task: int        # context budget per task (> 0)
```

### Budget Enforcement

```
BudgetUsed:
    tool_calls: int (default: 0)    # tool calls consumed so far
    llm_calls: int (default: 0)     # LLM calls consumed so far
    tokens: int (default: 0)        # tokens consumed so far

enforce_budget(agent, action) -> bool:
    # Returns true if the action is allowed, false if budget exhausted
    if action == "tool_call":
        return agent.budget_used.tool_calls < agent.identity.budget.max_tool_calls
    if action == "llm_call":
        return agent.budget_used.llm_calls < agent.identity.budget.max_llm_calls
    return false

record_usage(agent, action):
    # Increment the appropriate counter after an action completes
    if action == "tool_call":
        agent.budget_used.tool_calls += 1
    if action == "llm_call":
        agent.budget_used.llm_calls += 1
```

### Budget Exhaustion Behavior

When an agent's budget is exhausted:
1. The agent stops processing (does not crash)
2. Returns a partial result with `partial: true`
3. Includes a budget report showing usage vs limits
4. Reports what was accomplished and what remains

---

## Agent

```
Agent:
    identity: AgentIdentity
    tools: Tool[]                   # resolved tool instances (only those in identity.tools)
    skills: Skill[]                 # resolved skill instances (only those in identity.skills)
    budget_used: BudgetUsed         # tracks current usage

    process(task: string) -> AgentResult
        # Execute the task within identity boundaries and budget limits
        #
        # 1. Generate system prompt from identity
        # 2. Enter agent loop (from Ch 2)
        # 3. Before each tool call: check enforce_budget(self, "tool_call")
        # 4. Before each LLM call: check enforce_budget(self, "llm_call")
        # 5. If budget exhausted: stop gracefully, return partial result
        # 6. If tool not in identity.tools: reject the call (structural boundary)
        # 7. Return AgentResult with answer, confidence, sources, budget_report

        print("[{identity.name}] Starting task: {summarize(task)}")
        print("[{identity.name}] Budget: {identity.budget.max_tool_calls} tool calls, {identity.budget.max_llm_calls} LLM calls")

        while not done:
            # Check LLM budget
            if not enforce_budget(self, "llm_call"):
                print("[{identity.name}] Budget exhausted ({budget_used.llm_calls}/{identity.budget.max_llm_calls} LLM calls used)")
                return partial_result()

            llm_response = llm.generate(system_prompt, messages)
            record_usage(self, "llm_call")

            if llm_response.has_tool_call:
                tool_name = llm_response.tool_call.name

                # Structural boundary: reject tools not in identity.tools
                if tool_name not in identity.tools:
                    print("[{identity.name}] REJECTED: tool '{tool_name}' not in allowed tools {identity.tools}")
                    messages.append(error("Tool '{tool_name}' is not available to you."))
                    continue

                # Check tool budget
                if not enforce_budget(self, "tool_call"):
                    print("[{identity.name}] Budget exhausted ({budget_used.tool_calls}/{identity.budget.max_tool_calls} tool calls used)")
                    return partial_result()

                result = execute_tool(tool_name, llm_response.tool_call.args)
                record_usage(self, "tool_call")
                print("[{identity.name}] Tool call {budget_used.tool_calls}/{identity.budget.max_tool_calls}: {tool_name}")

            if llm_response.is_final:
                done = true

        return AgentResult(
            answer=llm_response.answer,
            confidence=llm_response.confidence,
            sources=llm_response.sources,
            budget_report=BudgetReport(
                tool_calls_used=budget_used.tool_calls,
                tool_calls_max=identity.budget.max_tool_calls,
                llm_calls_used=budget_used.llm_calls,
                llm_calls_max=identity.budget.max_llm_calls
            ),
            partial=false
        )

    partial_result() -> AgentResult
        # Return what was accomplished before budget exhaustion
        return AgentResult(
            answer="Budget exhausted. Partial results: {summarize_progress()}",
            confidence=0.5,
            sources=collected_sources,
            budget_report=BudgetReport(
                tool_calls_used=budget_used.tool_calls,
                tool_calls_max=identity.budget.max_tool_calls,
                llm_calls_used=budget_used.llm_calls,
                llm_calls_max=identity.budget.max_llm_calls
            ),
            partial=true
        )

AgentResult:
    answer: string
    confidence: float
    sources: string[]
    budget_report: BudgetReport
    partial: bool                   # true if budget was exhausted before completion

BudgetReport:
    tool_calls_used: int
    tool_calls_max: int
    llm_calls_used: int
    llm_calls_max: int
```

---

## Four Agent Definitions

### Coder

```
AgentIdentity:
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
    system_prompt: <generated from above>
    budget:
        max_tool_calls: 25
        max_llm_calls: 10
        max_tokens_per_task: 50000
```

### Reviewer

```
AgentIdentity:
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
    system_prompt: <generated from above>
    budget:
        max_tool_calls: 20
        max_llm_calls: 8
        max_tokens_per_task: 40000
```

### Runner

```
AgentIdentity:
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
    system_prompt: <generated from above>
    budget:
        max_tool_calls: 15
        max_llm_calls: 5
        max_tokens_per_task: 30000
```

### Researcher

```
AgentIdentity:
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
    system_prompt: <generated from above>
    budget:
        max_tool_calls: 30
        max_llm_calls: 10
        max_tokens_per_task: 60000
```

### Tool Access Matrix

```
              | read_file | write_file | search_code | execute_shell | list_directory |
Coder         |     Y     |      Y     |      Y      |               |                |
Reviewer      |     Y     |            |      Y      |               |                |
Runner        |     Y     |            |             |       Y       |                |
Researcher    |     Y     |            |      Y      |               |       Y        |
```

Key constraints:
- Only the **Coder** has `write_file` — it is the only agent that can modify files
- Only the **Runner** has `execute_shell` — it is the only agent that can run commands
- The **Reviewer** and **Researcher** are read-only — they cannot change anything
- All agents have `read_file` — everyone can read

---

## AgentFactory

```
AgentFactory:
    agent_definitions: dict[string, AgentIdentity]
        # Pre-loaded definitions for: "coder", "reviewer", "runner", "researcher"

    create_agent(name: string) -> Agent
        # Create an agent by name with correct identity, tools, and budget
        if name not in agent_definitions:
            raise error("Unknown agent: {name}. Available: {list(agent_definitions.keys())}")

        identity = agent_definitions[name]
        tools = resolve_tools(identity.tools)       # load Tool instances
        skills = resolve_skills(identity.skills)     # load Skill instances
        identity.system_prompt = identity.generate_system_prompt()

        return Agent(
            identity=identity,
            tools=tools,
            skills=skills,
            budget_used=BudgetUsed(tool_calls=0, llm_calls=0, tokens=0)
        )

    list_agents() -> string[]
        # Return available agent names
        return list(agent_definitions.keys())

    get_identity(name: string) -> AgentIdentity
        # Return the identity definition for an agent
        return agent_definitions[name]
```

---

## When to Split — Decision Framework

```
should_split(task_analysis) -> bool:
    # Decision criteria for splitting a monolith into agents

    role_switches = count_role_switches(task_analysis)
    context_pollution = measure_context_overlap(task_analysis)
    natural_independence = assess_independence(task_analysis)

    # Split when:
    #   1. Role thrashing — agent switches roles 3+ times per task
    #   2. Context pollution — artifacts from one role displace context another needs
    #   3. Natural independence — roles don't need each other's intermediate results

    if role_switches >= 3:
        return true     # too much role switching
    if context_pollution > 0.5:
        return true     # context from different roles competing
    if natural_independence > 0.7:
        return true     # roles can work in parallel

    return false        # keep as one agent

    # Rule: split when the context cost of generalization exceeds
    #        the coordination cost of specialization
```

---

## CLI Interface

```
# Run a specific agent
tbh-code --agent <name> --codebase <path> --ask "<question>"

# List available agents
tbh-code --list-agents

# Show agent identity
tbh-code --agent <name> --show-identity

# Standard format (no --agent flag = monolith mode for comparison)
tbh-code --codebase <path> --ask "<question>"
```

### Agent Output Format

Agent traces must appear in stdout with the format:
```
[<agent-name>] Starting task: <summary>
[<agent-name>] Budget: <max_tool_calls> tool calls, <max_llm_calls> LLM calls
[tool] Agent selected: <tool_name>
[tool] Arguments: { ... }
[tool] Result: ...
[<agent-name>] Tool call N/M: <tool_name>
[<agent-name>] Budget exhausted (N/M tool calls used)
[<agent-name>] REJECTED: tool '<name>' not in allowed tools [...]
```

Output must include a JSON response with: answer, confidence, sources, budget_report

---

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

---

## Test Task

```
Task: End-to-end agent splitting across todo-api work.

Phase 1 — Agent creation:
  Create all 4 agents via factory. Verify each has correct identity fields.

Phase 2 — Monolith vs specialists:
  Run the same auth refactoring task with the monolith (one agent) and then
  with the 4 specialists. Compare context usage and output quality.

Phase 3 — Budget enforcement:
  Give the runner a task that requires more tool calls than its budget allows.
  Verify it stops at 15/15 and returns partial results.

Phase 4 — Boundary enforcement:
  Ask the reviewer to fix a bug. Verify it reports the bug but does NOT
  write any files (write_file not in its tool list).

Phase 5 — Full refactoring:
  Researcher maps auth flow → Coder writes fix → Reviewer evaluates →
  Runner tests. Each agent operates within its boundaries.
```

---

## Additional Patterns

**Handoff pattern:** One agent completes its phase of work and explicitly passes its output to the next agent. The handoff includes context, artifacts produced, and what the next agent should do. This is the foundation for the multi-agent chains built in Ch 12 — agents don't just run independently, they pass the baton.

**Phase-based vs capability-based splitting:** Two ways to draw agent boundaries. *Capability-based* splitting (what this chapter builds) groups by skill type — coder, reviewer, runner, researcher. *Phase-based* splitting groups by workflow stage — a "planner" agent, a "doer" agent, a "checker" agent. Capability-based is more flexible (agents can be reused across workflows); phase-based is simpler when workflows are fixed. Most real systems use a hybrid.

---

## What This Chapter Does NOT Include

- **No agent communication** — agents run independently (peer messaging is Ch 12)
- **No agent discovery** — agents don't know about each other (broadcast is Ch 11)
- **No orchestration** — you (the user) coordinate manually (swarm patterns are Ch 13)
- **No shared memory** — each agent has its own context (shared state is Ch 12-13)
- **No dynamic splitting** — agents are predefined, not created on the fly
