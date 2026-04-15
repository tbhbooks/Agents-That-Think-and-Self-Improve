# Chapter 9 — Self-Improvement: Agents That Get Better

## Scope

Build the self-improvement loop: the agent evaluates its own performance, diagnoses weaknesses, adapts its behavior, and verifies the improvement worked. This is the culmination of threads planted in Ch 6 (outcome tracking), Ch 7 (strategy tracking), and Ch 8 (diagnostic feedback).

## Learning Objectives

- Implement the evaluate-diagnose-adapt-verify loop as a first-class agent capability
- Build a mistake journal that logs failures with structured diagnosis and category
- Enable the agent to rewrite its own skill specs based on outcome patterns
- Implement the evaluator-optimizer pattern — separate evaluator scores output, optimizer adjusts approach, loop until quality threshold
- Build a user feedback loop that converts corrections into persistent behavioral rules
- Verify that adaptations actually improve outcomes (before/after measurement)

## What You Build

1. **Mistake journal:** Structured log of failures with diagnosis, suggested fixes, and categories. Not a flat log — a learning artifact the agent queries before acting.
2. **Skill rewriting:** Agent reads its own skill specs (from Ch 4), checks the mistake journal for patterns, and rewrites underperforming skills with additional steps or constraints.
3. **Evaluator-optimizer loop:** Two roles in one loop. The evaluator (Ch 8) scores output. The optimizer reads the score + diagnosis and adjusts the approach. Loop repeats until the score meets the threshold or max rounds reached.
4. **User feedback incorporation:** When the user corrects the agent ("don't use mocks"), the correction is extracted as a behavioral rule, stored in long-term memory (type: rule), and consulted on future tasks.
5. **Improvement verification:** After adapting behavior (rewriting a skill, adding a rule), the agent runs the same task type again and compares before/after metrics. If not better, the adaptation is rolled back.

## Key Interfaces

- `MistakeJournal { entries: MistakeEntry[], log(), query(), categories() }`
- `MistakeEntry { task, output, diagnosis, suggested_fix, category, timestamp }`
- `refine_skill(skill, journal_entries) → SkillSpec`
- `EvaluatorOptimizerLoop { evaluator, optimizer, max_rounds, threshold }`
- `EvaluatorOptimizerLoop.run(task) → { final_output, rounds, score_history }`
- `incorporate_feedback(user_message) → MemoryEntry (type: rule)`
- `verify_improvement(task_type, before_metrics, after_metrics) → VerificationResult`

## Success Criteria

- Mistake journal captures structured failure data with categories
- Agent rewrites a skill spec — the updated version includes new steps or constraints based on past failures
- Evaluator-optimizer loop converges: score improves across rounds until threshold is met
- User corrections persist as behavioral rules and are consulted on future tasks
- Improvement is verified by before/after metrics comparison
- Adaptations that don't improve outcomes are rolled back

## Concepts Introduced

- The self-improvement loop: evaluate, diagnose, adapt, verify
- Mistake journals as structured learning (not flat logs)
- Skill evolution — static playbooks become living documents
- Evaluator-optimizer pattern (two roles, one loop)
- User feedback as behavioral change (not just conversation history)
- Meta-learning — the agent gets better at getting better
- Rollback-safe improvement (verify before committing changes)

## Thread: Skills Arc (Second Touch)

Skills evolve across the book:
- **Ch 4 (introduce):** Skills are static playbooks — loaded from files, never change
- **Ch 9 (here):** Skills become living documents — the agent rewrites them based on what works
- **Ch 11 (share):** Skills become shareable — agents broadcast skills alongside capabilities

## Thread: Self-Improvement (Dedicated Chapter)

This chapter ties together threads from:
- **Ch 6 (Memory):** Outcome tracking — raw data on what worked and what didn't
- **Ch 7 (Planning):** Strategy tracking — which decomposition approaches succeeded
- **Ch 8 (Evaluation):** Diagnostic feedback — specific issues and suggestions
- **Ch 9 (here):** The full loop that reads all of the above and adapts behavior

## What This Chapter Does NOT Include

- **No multi-agent improvement** — one agent improves itself (collective improvement is Ch 13)
- **No skill sharing** — improved skills stay local (sharing is Ch 11)
- **No automated retraining** — the agent adapts prompts and skills, not model weights
- **No A/B testing** — improvement is verified sequentially, not with parallel experiments
- **No human-written improvement rules** — the agent discovers its own adaptations (human feedback is incorporated, but the adaptation is agent-driven)
