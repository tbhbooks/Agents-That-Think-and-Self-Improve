# Chapter 7 — Interface Spec

## Overview

Add planning and reasoning to the agent. A `decompose()` function breaks complex tasks into ordered `PlanStep` entries. An `execute_plan()` function runs steps sequentially, passing results forward. When a step fails, `replan()` generates an adapted plan. A `StrategyLog` records what worked for future reference.

Operates on the `todo-api` codebase (see `../todo-api/`).

---

## Plan

```
Plan:
    goal: string                    # the original task description
    steps: PlanStep[]               # ordered list of steps
    status: PlanStatus              # overall plan status
    created_at: datetime
    completed_at: datetime | null

PlanStatus: enum("pending", "in_progress", "completed", "failed", "replanned")
```

A Plan is the output of decomposition. It contains an ordered sequence of steps that, executed in order, should accomplish the goal.

---

## PlanStep

```
PlanStep:
    id: int                         # step number (1-indexed)
    description: string             # human-readable description of what this step does
    tool_or_skill: string           # which tool or skill to use (e.g. "search_code", "find-bug")
    args: dict                      # arguments for the tool/skill (may reference prior step results)
    depends_on: int[]               # step IDs this step depends on (must complete first)
    status: StepStatus              # current status of this step
    result: ToolResult | null       # result after execution
    reasoning: string               # chain-of-thought: why this step is needed

StepStatus: enum("pending", "running", "completed", "failed", "skipped")
```

### Step Dependencies

Steps declare dependencies via `depends_on`. The executor runs steps in order and ensures all dependencies are satisfied before executing a step. For Ch 7, dependencies are linear (step N depends on step N-1), but the interface supports more complex DAGs for future use.

### Result References

Step arguments can reference results from prior steps:

```
# Step 3 uses the output from step 1
step_3.args = {
    "path": "$step_1.result.output[0].file"    # reference to step 1's result
}
```

The executor resolves `$step_N.result.*` references before executing each step.

---

## decompose()

```
decompose(task: string, context: AgentContext) -> Plan
    # Given a complex task, produce an ordered plan
    #
    # The LLM receives:
    #   - The task description
    #   - Available tools and skills (from ToolRegistry)
    #   - Retrieved memories (relevant strategies from past tasks)
    #   - Current codebase context
    #
    # The LLM returns a structured Plan

    prompt = """
    Decompose this task into ordered steps.
    For each step, specify:
    - What to do (description)
    - Which tool or skill to use
    - What arguments to pass
    - What this step depends on
    - Why this step is needed (reasoning)

    Available tools: {tool_schemas}
    Available skills: {skill_schemas}
    Relevant past strategies: {strategy_memories}

    Task: {task}
    """

    plan = llm.generate(prompt, response_format=Plan)
    plan.status = "pending"
    return plan
```

### Decomposition Rules

1. Each step should be accomplishable with a single tool or skill call
2. Steps should be ordered by dependency (read before write, search before edit)
3. A plan should have at minimum 2 steps (otherwise it's not worth planning)
4. Each step must include reasoning (chain-of-thought)

---

## execute_plan()

```
execute_plan(plan: Plan, agent: Agent) -> PlanResult
    # Execute a plan step by step
    #
    # For each step:
    #   1. Check dependencies are satisfied
    #   2. Resolve result references in args
    #   3. Display chain-of-thought reasoning
    #   4. Execute the tool or skill
    #   5. Record the result
    #   6. If failed: decide retry, skip, or replan

    plan.status = "in_progress"

    for step in plan.steps:
        # Check dependencies
        for dep_id in step.depends_on:
            dep_step = plan.steps[dep_id - 1]
            if dep_step.status not in ("completed", "skipped"):
                step.status = "failed"
                step.result = ToolResult(
                    output=null, success=false,
                    error="Dependency step {dep_id} not completed"
                )
                break

        # Display reasoning
        print("[think] Step {step.id}: {step.reasoning}")

        # Resolve references
        resolved_args = resolve_references(step.args, plan.steps)

        # Execute
        step.status = "running"
        tool_or_skill = agent.registry.find(step.tool_or_skill)
        step.result = tool_or_skill.execute(resolved_args)

        if step.result.success:
            step.status = "completed"
            print("[plan] Step {step.id} completed: {step.description}")
        else:
            step.status = "failed"
            print("[plan] Step {step.id} FAILED: {step.result.error}")

            # Decide how to handle failure
            decision = handle_failure(plan, step)
            if decision == "retry":
                # Re-execute same step (max 1 retry)
                step.result = tool_or_skill.execute(resolved_args)
                step.status = "completed" if step.result.success else "failed"
            elif decision == "skip":
                step.status = "skipped"
            elif decision == "replan":
                new_plan = replan(plan, step, step.result.error)
                return execute_plan(new_plan, agent)

    plan.status = "completed" if all_steps_done(plan) else "failed"
    plan.completed_at = now()

    # Log strategy to memory
    log_strategy(plan)

    return PlanResult(
        plan=plan,
        completed_steps=[s for s in plan.steps if s.status == "completed"],
        failed_steps=[s for s in plan.steps if s.status == "failed"],
        skipped_steps=[s for s in plan.steps if s.status == "skipped"]
    )

PlanResult:
    plan: Plan
    completed_steps: PlanStep[]
    failed_steps: PlanStep[]
    skipped_steps: PlanStep[]
```

---

## replan()

```
replan(plan: Plan, failed_step: PlanStep, error: string) -> Plan
    # Generate a new plan that adapts to the failure
    #
    # The LLM receives:
    #   - The original goal
    #   - Steps completed so far (with results)
    #   - The failed step and its error
    #   - Available tools and skills
    #
    # The LLM produces a new plan starting from the failure point,
    # using a different approach

    completed = [s for s in plan.steps if s.status == "completed"]

    prompt = """
    The original plan failed at step {failed_step.id}.

    Goal: {plan.goal}

    Completed steps:
    {format_completed_steps(completed)}

    Failed step: {failed_step.description}
    Error: {error}

    Generate a new plan to accomplish the goal, starting from where
    we left off. Use a different approach for the failed step.

    Available tools: {tool_schemas}
    Available skills: {skill_schemas}
    """

    new_plan = llm.generate(prompt, response_format=Plan)
    new_plan.goal = plan.goal
    new_plan.status = "pending"

    # Preserve completed steps
    for completed_step in completed:
        new_plan.steps.insert(0, completed_step)

    return new_plan
```

### Failure Handling Decision Logic

```
handle_failure(plan: Plan, failed_step: PlanStep) -> string
    # Decide how to handle a failed step
    #
    # Rules:
    # 1. If it's a transient error (timeout, network), retry
    # 2. If the step is optional (no other steps depend on it), skip
    # 3. If the step is critical (other steps depend on it), replan

    if is_transient_error(failed_step.result.error):
        return "retry"

    has_dependents = any(
        failed_step.id in s.depends_on
        for s in plan.steps if s.status == "pending"
    )

    if not has_dependents:
        return "skip"

    return "replan"
```

---

## StrategyLog

```
StrategyLog:
    task_type: string               # category of task, e.g. "add-feature", "fix-bug", "refactor"
    strategy_used: string           # description of the decomposition approach
    steps_count: int                # how many steps the plan had
    steps_completed: int            # how many steps succeeded
    outcome: string                 # "success", "partial", "failed"
    replanned: bool                 # whether replanning was needed
    timestamp: datetime
```

### Logging Strategy

```
log_strategy(plan: Plan) -> void
    # After plan execution, log the strategy to memory
    strategy = StrategyLog(
        task_type=classify_task(plan.goal),
        strategy_used=summarize_approach(plan.steps),
        steps_count=len(plan.steps),
        steps_completed=count(s for s in plan.steps if s.status == "completed"),
        outcome="success" if plan.status == "completed" else "failed",
        replanned=(plan.status == "replanned"),
        timestamp=now()
    )

    memory_store.save(MemoryEntry(
        key="strategy/{strategy.task_type}/{timestamp}",
        content=serialize(strategy),
        type="outcome",
        tags=["strategy", strategy.task_type, strategy.outcome]
    ))
```

### Using Past Strategies

When decomposing a new task, the agent queries memory for strategies that worked on similar task types:

```
# In decompose():
past_strategies = memory_store.search(
    query=task,
    filters={ tags: ["strategy"], type: "outcome" }
)
# Past strategies are included in the decomposition prompt
```

---

## Agent Integration

### Plan Visibility

The agent shows the full plan before executing:

```
[plan] Decomposing task: "Add input validation to POST /tasks"
[plan] Generated plan (5 steps):
  Step 1: Read the current POST /tasks handler [read_file]
  Step 2: Read existing validation patterns in codebase [search_code]
  Step 3: Write updated handler with validation [write_file]
  Step 4: Write test for validation [write_file]
  Step 5: Run tests to verify [execute_shell]
[plan] Executing...
```

### Chain-of-Thought Traces

Each step shows reasoning before execution:

```
[think] Step 1: I need to read the current handler first to understand
        the existing code structure before making changes.
[tool] Agent selected: read_file
[tool] Arguments: { "path": "src/routes/tasks.pseudo" }
[tool] Result: success=true
[plan] Step 1 completed: Read the current POST /tasks handler
```

---

## CLI Interface

```
# Same as Ch 6, but planning happens automatically for complex tasks
tbh-code --codebase ./todo-api --ask "Add input validation to POST /tasks"

# Simple tasks still execute directly (no plan needed)
tbh-code --codebase ./todo-api --ask "What files are in src/?"
```

The agent decides whether to plan based on task complexity. Simple questions (single tool call) skip planning. Complex tasks (multiple steps, multiple tools) trigger decomposition.

---

## Upgrade from Ch 6

| Capability | Ch 6 | Ch 7 |
|-----------|------|------|
| Tool interface + SimpleTools | Yes | Yes |
| MCPTool + SkillTool | Yes | Yes |
| PermissionLevel + ActionGate | Yes | Yes |
| MemoryStore | Yes | Yes (+ strategy entries) |
| Session persistence | Yes | Yes |
| ContextBudget | Yes | Yes |
| Task decomposition | No | Yes — decompose(task) → Plan |
| Plan execution | No | Yes — step-by-step with result flow |
| Failure handling | No | Yes — retry, skip, replan |
| Chain-of-thought | No | Yes — [think] traces before each step |
| Strategy tracking | No | Yes — logged to memory for future reference |

---

## Test Task

```
Task: "Add input validation to POST /tasks — title must be non-empty and under 200 chars"

Expected plan:
  Step 1: Read src/routes/tasks.pseudo to understand current POST handler
  Step 2: Search for existing validation patterns in the codebase
  Step 3: Write updated POST handler with title validation
  Step 4: Write test for title validation (empty title, long title, valid title)
  Step 5: Run test suite to verify nothing broke

Expected flow:
  1. Agent decomposes task into 5 steps
  2. Steps execute in order, results flow forward
  3. If step 5 (tests) fails, agent replans: adjust the validation code
  4. Strategy logged to memory

Expected answer: Agent reports validation added, tests pass,
references specific files and line changes.
```

---

## What This Chapter Does NOT Include

- **No self-evaluation** — plan executes but agent doesn't score output quality (that's Ch 8)
- **No parallel execution** — steps run sequentially (parallel fan-out is Ch 13)
- **No sub-agents** — one agent does everything (splitting is Ch 10)
- **No plan optimization** — first working plan is accepted (evaluator-optimizer is Ch 9)
- **No step-level human gates** — plan executes end-to-end once started (reader extension)
- **No plan caching** — each task gets a fresh decomposition (reader extension)
