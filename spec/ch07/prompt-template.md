# Chapter 7 — Planning & Reasoning

## Scope

Give the agent the ability to decompose complex tasks into ordered steps, execute them sequentially with results flowing forward, and adapt the plan when steps fail. The agent thinks before it acts.

## Learning Objectives

- Implement task decomposition — break a complex task into ordered subtasks
- Build a plan-then-execute loop where each step uses tools and skills from earlier chapters
- Handle plan failures with retry, skip, and replan strategies
- Make chain-of-thought reasoning explicit and visible in output
- Track which decomposition strategies work for which task types (self-improvement thread)

## What You Build

1. **Task decomposer:** Given a complex task, the agent produces a `Plan` with ordered `PlanStep` entries. Each step specifies what to do, which tool or skill to use, and what it depends on.
2. **Plan executor:** Execute steps sequentially. Each step receives results from prior steps. The executor tracks status per step.
3. **Failure handling:** When a step fails, the agent decides: retry (same approach), skip (move on), or replan (generate a new plan from the failure point). No crashes on failure.
4. **Chain-of-thought:** Before each step, the agent explains its reasoning. Visible in output as `[think]` traces.
5. **Strategy tracking:** After plan execution, log a `StrategyLog` entry to memory: task type, strategy used, step count, outcome. This feeds Ch 9.

## Key Interfaces

- `Plan { goal, steps: PlanStep[], status }`
- `PlanStep { description, tool_or_skill, args, depends_on, status, result }`
- `decompose(task) → Plan`
- `execute_plan(plan) → PlanResult`
- `replan(plan, failed_step, error) → Plan`
- `StrategyLog { task_type, strategy_used, steps_count, outcome }`

## Success Criteria

- Agent decomposes a multi-step coding task into 3+ ordered subtasks
- Steps execute in order, with results from earlier steps available to later ones
- A failing step triggers replan — the agent adapts instead of crashing
- Chain-of-thought reasoning is visible in agent output
- Strategy outcomes are saved to memory for future reference

## Concepts Introduced

- Task decomposition (big task to small steps)
- Plan-then-execute architecture
- Dependency tracking between steps
- Backtracking and replanning on failure
- Chain-of-thought as explicit reasoning trace
- Strategy tracking (feeds self-improvement)

## Self-Improvement Thread

Plans improve over time. This chapter introduces **strategy tracking**: after each plan execution, the agent records what decomposition approach it used and whether it worked. In Ch 9, the agent consults strategy history to choose better approaches for similar task types.

## What This Chapter Does NOT Include

- **No self-evaluation** — the agent executes the plan but doesn't score output quality (that's Ch 8)
- **No parallel execution** — steps execute sequentially, one at a time (parallel is Ch 13)
- **No sub-agents** — one agent does all steps (splitting into agents is Ch 10)
- **No plan optimization** — the first plan that works is good enough (optimizer pattern is Ch 9)
- **No user approval per step** — the plan executes end-to-end (step-level gates are a reader extension)
