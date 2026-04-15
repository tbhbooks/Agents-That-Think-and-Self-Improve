# Chapter 9 — Interface Spec

## Overview

Build the self-improvement loop. A `MistakeJournal` logs structured failures with diagnosis and category. `refine_skill()` rewrites skill specs based on mistake patterns. An `EvaluatorOptimizerLoop` iterates between evaluation and optimization until quality threshold is met. `incorporate_feedback()` converts user corrections into persistent behavioral rules. `verify_improvement()` measures whether adaptations actually helped.

Operates on the `todo-api` codebase (see `../todo-api/`).

---

## MistakeJournal

```
MistakeJournal:
    entries: MistakeEntry[]
    storage_path: string            # .tbh-code/journal/

    log(entry: MistakeEntry) -> void
        # Add a mistake entry to the journal
        # Persists to disk immediately
        entries.append(entry)
        write_json(storage_path / "{entry.timestamp}.json", entry)

    query(filters: JournalFilters) -> MistakeEntry[]
        # Search journal entries by category, task type, or recency
        results = entries
        if filters.category:
            results = [e for e in results if e.category == filters.category]
        if filters.since:
            results = [e for e in results if e.timestamp >= filters.since]
        if filters.task_pattern:
            results = [e for e in results
                       if filters.task_pattern in e.task.lower()]
        return sorted(results, by=timestamp, descending=true)[:filters.limit]

    categories() -> dict[string, int]
        # Return mistake categories with counts
        counts = {}
        for entry in entries:
            counts[entry.category] = counts.get(entry.category, 0) + 1
        return counts

JournalFilters:
    category: string | null
    since: datetime | null
    task_pattern: string | null
    limit: int (default: 10)
```

---

## MistakeEntry

```
MistakeEntry:
    task: string                    # what the agent was trying to do
    output: string                  # what the agent produced (summary)
    diagnosis: string               # what went wrong and why
    suggested_fix: string           # what the agent should do differently
    category: MistakeCategory       # classification of the mistake type
    skill_used: string | null       # which skill was active (if any)
    eval_score: float | null        # evaluation score that triggered this entry
    timestamp: datetime

MistakeCategory: enum(
    "security",                     # security vulnerability introduced
    "incomplete",                   # missing requirements or edge cases
    "incorrect",                    # wrong approach or logic error
    "inefficient",                  # works but suboptimal approach
    "style",                        # code style or convention violation
    "regression"                    # broke something that was working
)
```

### When to Log Mistakes

Mistakes are logged when:
1. Evaluation score < threshold (from Ch 8's evaluator)
2. Tests fail after agent changes
3. User explicitly rejects or corrects agent output
4. Replan was needed during execution (from Ch 7)

### Example MistakeEntries

```
Entry 1:
    task: "Fix auth middleware token validation"
    output: "Rewrote middleware with base64 decoding and user lookup"
    diagnosis: "Used string equality for token comparison instead of constant-time comparison. Vulnerable to timing attacks."
    suggested_fix: "Use constant-time string comparison for any secret/token comparison"
    category: "security"
    skill_used: "find-bug"
    eval_score: 0.55
    timestamp: "2025-01-15T14:30:00Z"

Entry 2:
    task: "Add input validation to POST /tasks"
    output: "Added title length check to POST handler"
    diagnosis: "Only validated title field. Did not check for unexpected fields or validate field types. Missing: completed field should be boolean."
    suggested_fix: "When adding validation, check ALL fields in the request body, not just the one mentioned in the task"
    category: "incomplete"
    skill_used: null
    eval_score: 0.65
    timestamp: "2025-01-16T10:15:00Z"

Entry 3:
    task: "Refactor database layer to use connection pooling"
    output: "Replaced direct connections with pool of 10"
    diagnosis: "Pool doesn't evict dead connections. No health check on checkout. No graceful shutdown."
    suggested_fix: "When implementing resource pools, always include: health checks, eviction, graceful shutdown, and configurable timeouts"
    category: "incomplete"
    skill_used: null
    eval_score: 0.72
    timestamp: "2025-01-17T09:00:00Z"
```

---

## refine_skill()

```
refine_skill(skill: SkillSpec, journal_entries: MistakeEntry[]) -> SkillSpec
    # Given a skill and relevant mistake journal entries, produce an improved skill
    #
    # The LLM receives:
    #   - The current skill spec (from Ch 4)
    #   - Relevant mistake entries (filtered by skill_used or category)
    #   - The suggested fixes from each entry
    #
    # The LLM produces a revised skill spec with additional steps/constraints

    prompt = """
    You are improving a skill spec based on past mistakes.

    Current skill:
    {skill.to_spec_format()}

    Mistakes made when using this skill (or similar tasks):
    {format_journal_entries(journal_entries)}

    Rules:
    1. Keep all existing steps that worked well
    2. Add new steps or constraints to address the mistakes
    3. Do NOT remove steps unless they caused the mistake
    4. Each new step must reference which mistake it addresses
    5. The improved skill should prevent the same mistakes from recurring

    Produce the updated skill spec.
    """

    updated_skill = llm.generate(prompt, response_format=SkillSpec)

    # Preserve metadata
    updated_skill.name = skill.name
    updated_skill.version = skill.version + 1
    updated_skill.parent_version = skill.version
    updated_skill.refinement_reason = summarize_mistakes(journal_entries)

    return updated_skill
```

### Skill Versioning

```
SkillSpec:
    # Existing fields from Ch 4:
    name: string
    description: string
    steps: SkillStep[]
    tools_used: string[]

    # New fields for Ch 9:
    version: int (default: 1)
    parent_version: int | null
    refinement_reason: string | null
    refined_at: datetime | null
```

### Example: find-bug Skill Evolution

```
find-bug v1 (Ch 4 — original):
    Step 1: Search for code related to the symptom
    Step 2: Read the most relevant file
    Step 3: Search for related tests
    Step 4: Read the test file if found

find-bug v2 (Ch 9 — refined):
    Step 1: Search for code related to the symptom
    Step 2: Read the most relevant file
    Step 3: Search for related tests
    Step 4: Read the test file if found
    Step 5: Check for similar patterns in other files        ← NEW (from "incomplete" mistakes)
    Step 6: Verify fix doesn't use insecure patterns         ← NEW (from "security" mistakes)
            (string equality for secrets, plaintext storage,
             eval(), SQL concatenation)

    refinement_reason: "Past mistakes: incomplete fixes that missed similar issues in other files, and security oversights in string comparison and storage patterns."
```

---

## EvaluatorOptimizerLoop

```
EvaluatorOptimizerLoop:
    evaluator: Evaluator            # from Ch 8
    optimizer: Optimizer            # adjusts approach based on feedback
    max_rounds: int (default: 3)    # maximum iterations
    threshold: float (default: 0.8) # target score

    run(task: string, context: AgentContext) -> EvalOptResult
        # Iterate: produce output → evaluate → optimize → repeat
        score_history = []
        current_approach = initial_approach(task, context)

        for round in range(1, max_rounds + 1):
            # Produce output using current approach
            output = execute_approach(current_approach, context)

            # Evaluate
            eval_result = evaluator.evaluate(task, output, context)
            score_history.append(eval_result.score)

            print("[eval-opt] Round {round}: score {eval_result.score}")

            if eval_result.passed and eval_result.score >= threshold:
                print("[eval-opt] Threshold met. Done.")
                return EvalOptResult(
                    final_output=output,
                    rounds=round,
                    score_history=score_history,
                    converged=true
                )

            # Optimize: adjust approach based on evaluation feedback
            current_approach = optimizer.optimize(
                task=task,
                current_approach=current_approach,
                eval_result=eval_result,
                round=round
            )
            print("[eval-opt] Optimizer adjusted approach based on: {eval_result.issues}")

        # Max rounds reached
        print("[eval-opt] Max rounds ({max_rounds}) reached. Best score: {max(score_history)}")
        return EvalOptResult(
            final_output=output,
            rounds=max_rounds,
            score_history=score_history,
            converged=false
        )

EvalOptResult:
    final_output: string            # the best output produced
    rounds: int                     # how many rounds were needed
    score_history: float[]          # score at each round
    converged: bool                 # did it meet the threshold?
```

### Optimizer

```
Optimizer:
    optimize(task: string, current_approach: Approach,
             eval_result: EvalResult, round: int) -> Approach
        # Given the evaluation feedback, adjust the approach
        #
        # The LLM receives:
        #   - The original task
        #   - What the current approach did
        #   - The evaluation result (scores, issues, suggestions)
        #   - The round number
        #
        # The LLM produces a revised approach

        prompt = """
        Your previous approach scored {eval_result.score}.

        Issues found:
        {eval_result.issues}

        Suggestions:
        {eval_result.suggestions}

        Adjust your approach to address these specific issues.
        Focus on the lowest-scoring criterion: {lowest_criterion}.
        This is round {round} of {max_rounds} — be targeted, not wholesale.
        """

        return llm.generate(prompt, response_format=Approach)

Approach:
    strategy: string                # description of the approach
    focus_areas: string[]           # what to prioritize
    constraints: string[]           # what to avoid (learned from evaluation)
```

---

## incorporate_feedback()

```
incorporate_feedback(user_message: string, context: AgentContext) -> MemoryEntry
    # Extract a behavioral rule from user feedback and store it
    #
    # The LLM receives:
    #   - The user's message (correction or preference)
    #   - The current task context
    #
    # The LLM extracts a reusable rule

    prompt = """
    The user gave this feedback: "{user_message}"

    Extract a reusable behavioral rule that should apply to ALL future tasks,
    not just this one.

    Format:
    - Rule: <concise statement>
    - Applies to: <what kinds of tasks>
    - Reason: <why this matters>
    """

    rule = llm.generate(prompt)

    entry = MemoryEntry(
        key="rule/{generate_key(rule)}",
        content=rule.rule_text,
        type="rule",
        tags=["user-feedback", "behavioral-rule"] + rule.applies_to_tags,
        timestamp=now()
    )

    memory_store.save(entry)
    print("[feedback] Stored rule: {rule.rule_text}")
    print("[feedback] Applies to: {rule.applies_to}")

    return entry
```

### Rule Consultation

Before executing any task, the agent queries memory for applicable rules:

```
# In agent loop, before execution:
rules = memory_store.search(
    query=task,
    filters={ type: "rule" }
)
# Rules are injected into the system prompt:
# "Rules (always follow these): ..."
```

### Example Feedback Flow

```
User: "Don't use mocks in the tests — use the real database layer"

→ incorporate_feedback() extracts:
    Rule: "Use real implementations instead of mocks in tests"
    Applies to: tasks involving writing tests
    Reason: "User prefers integration-style tests over unit tests with mocks"

→ Stored as MemoryEntry(type="rule", tags=["testing", "user-feedback"])

→ Next task: "Write tests for the new endpoint"
→ Agent retrieves rule: "Use real implementations instead of mocks"
→ Agent writes tests using the real database layer
```

---

## verify_improvement()

```
verify_improvement(
    task_type: string,
    before_metrics: Metrics,
    after_metrics: Metrics
) -> VerificationResult
    # Compare metrics before and after an adaptation
    # Determine whether the change actually improved outcomes

    improved_criteria = []
    degraded_criteria = []
    unchanged_criteria = []

    for criterion in ["correctness", "completeness", "safety"]:
        before = before_metrics.get(criterion, 0)
        after = after_metrics.get(criterion, 0)
        delta = after - before

        if delta > 0.05:       # meaningful improvement
            improved_criteria.append({ criterion, before, after, delta })
        elif delta < -0.05:    # meaningful degradation
            degraded_criteria.append({ criterion, before, after, delta })
        else:
            unchanged_criteria.append({ criterion, before, after, delta })

    overall_before = before_metrics.get("overall", 0)
    overall_after = after_metrics.get("overall", 0)
    overall_improved = overall_after > overall_before + 0.05

    return VerificationResult(
        improved=overall_improved and len(degraded_criteria) == 0,
        overall_delta=overall_after - overall_before,
        improved_criteria=improved_criteria,
        degraded_criteria=degraded_criteria,
        unchanged_criteria=unchanged_criteria,
        recommendation="keep" if overall_improved else "rollback"
    )

VerificationResult:
    improved: bool                  # overall improvement without degradation
    overall_delta: float            # change in overall score
    improved_criteria: dict[]       # criteria that got better
    degraded_criteria: dict[]       # criteria that got worse
    unchanged_criteria: dict[]      # criteria that stayed the same
    recommendation: string          # "keep" or "rollback"

Metrics:
    overall: float
    correctness: float
    completeness: float
    safety: float
```

### Verification Flow

```
1. Agent identifies an adaptation (e.g., skill rewrite)
2. Before applying: run evaluation on a representative task → before_metrics
3. Apply the adaptation (rewrite skill, add rule)
4. After applying: run same evaluation → after_metrics
5. verify_improvement(before, after) → VerificationResult
6. If improved: keep the adaptation
7. If not improved: roll back to previous version

[improve] Verifying skill refinement: find-bug v1 → v2
[improve] Before (v1): overall=0.72, correctness=0.8, completeness=0.65, safety=0.7
[improve] After (v2):  overall=0.85, correctness=0.85, completeness=0.8, safety=0.9
[improve] Result: IMPROVED (+0.13 overall)
  Improved: completeness (+0.15), safety (+0.20)
  Unchanged: correctness (+0.05)
  Degraded: none
[improve] Recommendation: KEEP v2
```

---

## Self-Improvement Integration

### The Full Loop

```
Evaluate → Diagnose → Adapt → Verify

1. EVALUATE: Ch 8's evaluator scores output (correctness, completeness, safety)
2. DIAGNOSE: If score < threshold, log to mistake journal with category + suggested fix
3. ADAPT: Based on mistake patterns:
   a. Rewrite underperforming skills (refine_skill)
   b. Store user feedback as rules (incorporate_feedback)
   c. Use evaluator-optimizer loop for iterative improvement
4. VERIFY: Compare before/after metrics. Keep improvements, roll back regressions.
```

### System Prompt Addition (Ch 9)

Add to the Ch 8 system prompt:

```
You are capable of self-improvement. Before acting:

1. Check your mistake journal for similar past failures
2. Check behavioral rules from user feedback
3. If a similar task failed before, use the suggested fix from the journal

After acting:
1. If evaluation fails, log the mistake with diagnosis
2. If you see a pattern (same category 3+ times), refine the relevant skill
3. If the user corrects you, extract and store the rule

Self-improvement rules:
- Never change behavior without verification
- If an adaptation makes things worse, roll back
- Log everything — your future self depends on it
```

---

## CLI Interface

```
# Same as Ch 8 — self-improvement happens automatically
tbh-code --codebase ./todo-api --auto-approve --ask "..."

# View mistake journal
tbh-code --codebase ./todo-api --show-journal

# View learned rules
tbh-code --codebase ./todo-api --show-rules

# View skill versions
tbh-code --codebase ./todo-api --show-skills
```

---

## Upgrade from Ch 8

| Capability | Ch 8 | Ch 9 |
|-----------|------|------|
| Tool interface + SimpleTools | Yes | Yes |
| MCPTool + SkillTool | Yes | Yes (skills now versioned) |
| PermissionLevel + ActionGate | Yes | Yes |
| MemoryStore + Session | Yes | Yes (+ rules, journal entries) |
| ContextBudget | Yes | Yes |
| Planning + Execution | Yes | Yes |
| Self-evaluation | Yes | Yes (+ feeds improvement loop) |
| Guardrails | Yes | Yes |
| Mistake journal | No | Yes — structured failure log |
| Skill rewriting | No | Yes — agent rewrites its own skills |
| Evaluator-optimizer loop | No | Yes — iterative quality improvement |
| User feedback as rules | No | Yes — corrections become behavior |
| Improvement verification | No | Yes — before/after metrics |

---

## Test Task

```
Task: End-to-end self-improvement across todo-api work.

Phase 1 — Build mistake journal:
  Agent works on 3 tasks, makes mistakes, logs structured entries.

Phase 2 — Skill rewrite:
  Agent reviews find-bug skill against journal, adds security check step.

Phase 3 — Evaluator-optimizer loop:
  Agent does a code review task. Round 1: score 0.6. Round 2: score 0.75.
  Round 3: score 0.85. Converged.

Phase 4 — User feedback:
  User says "don't use mocks." Rule stored. Next test-writing task consults rule.

Phase 5 — Verification:
  Before/after metrics show improvement. Adaptation kept.
```

---

## What This Chapter Does NOT Include

- **No multi-agent improvement** — one agent improves itself (collective improvement is Ch 13)
- **No skill sharing** — improved skills stay local to this agent (sharing is Ch 11)
- **No automated retraining** — the agent adapts prompts, skills, and rules — not model weights
- **No A/B testing** — improvement is verified sequentially, not with parallel experiments
- **No genetic/evolutionary approaches** — adaptation is LLM-driven, not algorithmic mutation
- **No human-curated improvement** — the agent discovers adaptations itself (human feedback is input, not the adaptation mechanism)
