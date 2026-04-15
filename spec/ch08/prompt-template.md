# Chapter 8 — Evaluation & Guardrails

## Scope

Give the agent the ability to check its own work before presenting results. The agent scores output on correctness, completeness, and safety. Guardrails block dangerous actions unconditionally. Low-confidence results escalate to the human. Evaluation produces diagnostic feedback — not just pass/fail, but *what's wrong and what to try next*.

## Learning Objectives

- Build a self-evaluation step that scores agent output on multiple criteria
- Implement guardrails as hard rules that block specific dangerous actions
- Design fail-closed defaults — when uncertain, stop and ask
- Add human-in-the-loop escalation with real context (not just "approve?")
- Generate diagnostic feedback that explains issues and suggests fixes (self-improvement thread)

## What You Build

1. **Evaluator:** After producing output, the agent scores it on three criteria — correctness (does it work?), completeness (does it cover all requirements?), and safety (does it introduce security or data risks?). Each criterion gets a 0.0-1.0 score.
2. **Guardrails:** Hard rules that block specific actions regardless of context. Three built-in: no secrets in code, no destructive operations without gate, no known vulnerability patterns.
3. **Fail-closed gate:** If the overall evaluation score falls below a threshold (e.g., 0.7), the agent stops and escalates to the human instead of proceeding.
4. **Human escalation:** The agent presents what it did, what it's uncertain about, and options for the human to choose. Real context, not just a yes/no prompt.
5. **Diagnostic feedback:** Evaluation produces a `DiagnosticEntry` with specific issues found and actionable suggestions. This feeds Ch 9's self-improvement loop.

## Key Interfaces

- `Evaluator { evaluate(task, output) → EvalResult }`
- `EvalResult { score, criteria: CriterionResult[], diagnosis, passed }`
- `CriterionResult { name, score, explanation }`
- `Guardrail { name, check(action) → GateResult }`
- `escalate(context, options) → HumanDecision`
- `DiagnosticEntry { task, output, score, issues[], suggestions[] }`

## Success Criteria

- Agent evaluates its own output before presenting it to the user
- Each criterion (correctness, completeness, safety) gets an individual score with explanation
- Guardrails block dangerous actions with clear explanations — never silently passed
- Low-confidence outputs trigger human escalation with diagnostic context
- Diagnostic feedback includes specific issues and actionable suggestions
- Agent never proceeds past a failed guardrail check

## Concepts Introduced

- Self-evaluation as a distinct phase (act, then evaluate, then present)
- Scored criteria vs binary pass/fail
- Guardrails as non-negotiable safety boundaries
- Fail-closed defaults (uncertain = stop)
- Human-in-the-loop escalation with context
- Diagnostic feedback as structured learning data

## Self-Improvement Thread

Evaluation feeds self-improvement. This chapter introduces **diagnostic feedback**: the evaluator doesn't just say "score: 0.6" — it says "score: 0.6 because plaintext passwords detected; suggestion: use bcrypt hashing." The diagnosis is the input to Ch 9's self-improvement loop — without it, the agent knows it failed but not *how* to do better.

## What This Chapter Does NOT Include

- **No behavior change** — the agent diagnoses issues but doesn't adapt its future behavior (that's Ch 9)
- **No mistake journal** — diagnostics are produced but not logged as learning artifacts (that's Ch 9)
- **No evaluator-optimizer loop** — evaluation happens once, not iteratively (that's Ch 9)
- **No external validators** — evaluation is self-assessment, not linting or static analysis (reader extension)
- **No per-criterion thresholds** — one overall threshold for pass/fail (reader extension)
