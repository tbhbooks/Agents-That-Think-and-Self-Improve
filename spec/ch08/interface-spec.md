# Chapter 8 — Interface Spec

## Overview

Add self-evaluation and guardrails to the agent. An `Evaluator` scores output on correctness, completeness, and safety — producing an `EvalResult` with per-criterion scores and diagnostic feedback. `Guardrail` rules block specific dangerous actions unconditionally. When evaluation score drops below threshold, the agent escalates to the human with context and options. A `DiagnosticEntry` captures issues and suggestions for future learning.

Operates on the `todo-api` codebase (see `../todo-api/`).

---

## Evaluator

```
Evaluator:
    threshold: float                # minimum score to pass (default: 0.7)
    criteria: string[]              # evaluation criteria names

    evaluate(task: string, output: string, context: AgentContext) -> EvalResult
        # Score the agent's output on multiple criteria
        #
        # The LLM receives:
        #   - The original task
        #   - The output produced
        #   - The context (files modified, tools used, test results)
        #   - Evaluation criteria definitions
        #
        # The LLM returns scored criteria + diagnosis

        prompt = """
        Evaluate this agent output against the following criteria.
        For each criterion, provide a score (0.0 to 1.0) and explanation.

        Task: {task}
        Output: {output}
        Context: {context.summary()}

        Criteria:
        1. Correctness — Does the output actually solve the task? Are there bugs?
        2. Completeness — Does it cover all requirements? Any missing pieces?
        3. Safety — Does it introduce security risks, data exposure, or vulnerabilities?

        Also provide:
        - Overall diagnosis: what's good, what's wrong
        - Specific issues found (if any)
        - Actionable suggestions for improvement
        """

        result = llm.generate(prompt, response_format=EvalResult)
        result.passed = result.score >= threshold
        return result
```

---

## EvalResult

```
EvalResult:
    score: float                    # overall score (0.0 to 1.0) — average of criteria
    criteria: CriterionResult[]     # per-criterion scores
    diagnosis: string               # human-readable overall assessment
    passed: bool                    # score >= threshold
    issues: string[]                # specific problems found
    suggestions: string[]           # actionable improvement suggestions
```

### CriterionResult

```
CriterionResult:
    name: string                    # "correctness", "completeness", or "safety"
    score: float                    # 0.0 to 1.0
    explanation: string             # why this score was given
```

### Score Interpretation

| Score Range | Meaning |
|------------|---------|
| 0.9 - 1.0 | Excellent — no issues found |
| 0.7 - 0.9 | Good — minor issues, acceptable |
| 0.5 - 0.7 | Marginal — significant issues, needs improvement |
| 0.0 - 0.5 | Poor — major issues, should not proceed |

### Example EvalResult

```
EvalResult:
    score: 0.73
    criteria:
      - name: "correctness"
        score: 0.9
        explanation: "The fix correctly validates tokens and rejects invalid ones.
                     Token decoding logic is correct."
      - name: "completeness"
        score: 0.8
        explanation: "Covers the main cases (missing token, invalid token, valid token).
                     Missing: no test for expired tokens."
      - name: "safety"
        score: 0.5
        explanation: "Passwords are compared using string equality instead of
                     constant-time comparison. Vulnerable to timing attacks."
    diagnosis: "The auth fix is functionally correct and covers most cases, but
               has a security concern: timing-safe comparison not used for
               password verification."
    passed: true (0.73 >= 0.7)
    issues:
      - "String equality used for password comparison (timing attack risk)"
      - "No test for expired or revoked tokens"
    suggestions:
      - "Use constant-time string comparison for any secret comparison"
      - "Add test cases for expired tokens and revoked tokens"
```

---

## Guardrail

```
Guardrail:
    name: string                    # human-readable guardrail name
    description: string             # what this guardrail checks
    severity: GuardrailSeverity     # how serious a violation is

    check(action: dict) -> GateResult
        # Check if an action violates this guardrail
        # action: { type, tool, args, output }
        # Returns pass or block with reason

GuardrailSeverity: enum("warning", "block")
    # warning: log the issue but allow (agent decides)
    # block: hard stop — action is prevented unconditionally

GateResult:
    passed: bool
    reason: string
```

### Built-in Guardrails

#### 1. no_secrets_in_code

```
no_secrets_in_code Guardrail:
    name: "no_secrets_in_code"
    description: "Block writing files that contain hardcoded secrets"
    severity: block

    check(action) -> GateResult:
        if action.type != "write_file":
            return GateResult(passed=true, reason="not a write operation")

        content = action.args.get("content", "")

        # Check for common secret patterns
        secret_patterns = [
            regex("(api[_-]?key|apikey)\s*[:=]\s*['\"][a-zA-Z0-9]{20,}"),
            regex("(password|passwd|pwd)\s*[:=]\s*['\"][^'\"]+"),
            regex("(secret|token)\s*[:=]\s*['\"][a-zA-Z0-9]{20,}"),
            regex("-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
            regex("(aws_access_key_id|aws_secret)\s*[:=]"),
        ]

        for pattern in secret_patterns:
            if pattern.match(content):
                return GateResult(
                    passed=false,
                    reason="Hardcoded secret detected: matches pattern '{pattern}'"
                )

        return GateResult(passed=true, reason="no secrets detected")
```

#### 2. no_destructive_without_gate

```
no_destructive_without_gate Guardrail:
    name: "no_destructive_without_gate"
    description: "Block destructive shell commands without explicit approval"
    severity: block

    check(action) -> GateResult:
        if action.type != "execute_shell":
            return GateResult(passed=true, reason="not a shell command")

        command = action.args.get("command", "")
        destructive_patterns = [
            "rm -rf", "rm -r", "drop table", "drop database",
            "truncate", "format", "mkfs", "> /dev/",
            "chmod 777", "dd if=",
        ]

        for pattern in destructive_patterns:
            if pattern in command.lower():
                return GateResult(
                    passed=false,
                    reason="Destructive command detected: '{pattern}' in '{command}'"
                )

        return GateResult(passed=true, reason="command appears safe")
```

#### 3. no_known_vulnerabilities

```
no_known_vulnerabilities Guardrail:
    name: "no_known_vulnerabilities"
    description: "Warn when code contains known vulnerability patterns"
    severity: warning

    check(action) -> GateResult:
        if action.type != "write_file":
            return GateResult(passed=true, reason="not a write operation")

        content = action.args.get("content", "")

        vulnerability_patterns = [
            { pattern: "eval(", name: "code injection via eval()" },
            { pattern: "exec(", name: "code injection via exec()" },
            { pattern: "innerHtml", name: "XSS via innerHTML" },
            { pattern: "sql = \"", name: "potential SQL injection (string concatenation)" },
            { pattern: "pickle.load", name: "insecure deserialization" },
        ]

        warnings = []
        for vuln in vulnerability_patterns:
            if vuln.pattern in content:
                warnings.append(vuln.name)

        if warnings:
            return GateResult(
                passed=false,
                reason="Known vulnerability patterns: " + ", ".join(warnings)
            )

        return GateResult(passed=true, reason="no known vulnerability patterns")
```

---

## Guardrail Integration

```
run_guardrails(action: dict, guardrails: Guardrail[]) -> GuardrailResult
    # Run all guardrails against an action
    results = []
    blocked = false
    warnings = []

    for guardrail in guardrails:
        result = guardrail.check(action)
        results.append({ guardrail: guardrail.name, result: result })

        if not result.passed:
            if guardrail.severity == "block":
                blocked = true
                print("[guardrail] BLOCKED by {guardrail.name}: {result.reason}")
            else:
                warnings.append(result.reason)
                print("[guardrail] WARNING from {guardrail.name}: {result.reason}")

    return GuardrailResult(
        blocked=blocked,
        warnings=warnings,
        details=results
    )

GuardrailResult:
    blocked: bool                   # any block-severity guardrail fired
    warnings: string[]              # warning-severity issues
    details: dict[]                 # per-guardrail results
```

Guardrails run BEFORE the action gate (Ch 5). If a guardrail blocks, the action never reaches the gate:

```
1. Agent wants to write a file
2. Guardrails check the content → BLOCKED (secret detected)
3. Action gate never reached
4. Tool never executed
5. Agent informed: "Action blocked by guardrail: no_secrets_in_code"
```

---

## Escalation

```
escalate(context: EscalationContext, options: string[]) -> HumanDecision
    # Present the situation to the human and get a decision
    #
    # context: what the agent did and why it's uncertain
    # options: possible actions the human can choose
    #
    # Returns the human's choice

EscalationContext:
    task: string                    # what the agent was trying to do
    output_summary: string          # what the agent produced
    eval_result: EvalResult         # evaluation scores and diagnosis
    specific_concern: string        # why the agent is escalating

HumanDecision:
    choice: string                  # which option the human selected
    feedback: string | null         # optional additional guidance
```

### Escalation Flow

```
1. Agent produces output
2. Evaluator scores output → EvalResult
3. If score < threshold (0.7):
   a. Build EscalationContext
   b. Present to human:

   [eval] Score: 0.55 (below threshold 0.7)
   [eval] Correctness: 0.8 — Fix looks right
   [eval] Completeness: 0.6 — Missing edge cases
   [eval] Safety: 0.3 — Plaintext password detected
   [eval] Issues:
     - Passwords stored in plaintext (security risk)
     - No test for SQL injection in user input
   [eval] Suggestions:
     - Use bcrypt or argon2 for password hashing
     - Add parameterized queries for user input

   [escalate] I'm not confident in this output. Options:
     1. Accept as-is (not recommended)
     2. Let me fix the issues and try again
     3. Cancel — I'll stop here

   > 2

   c. Agent proceeds based on human choice
```

### When to Escalate

Escalation triggers when:
1. Overall evaluation score < threshold (0.7)
2. Any single criterion score < 0.3 (critical failure)
3. A guardrail fires with severity "warning" (not "block")

---

## DiagnosticEntry

```
DiagnosticEntry:
    task: string                    # what the agent was trying to do
    output_summary: string          # brief description of what was produced
    score: float                    # overall evaluation score
    issues: string[]                # specific problems identified
    suggestions: string[]           # actionable improvement ideas
    criteria_scores: dict           # per-criterion scores
    timestamp: datetime
```

Diagnostic entries are stored in memory (type: "outcome") so they can be retrieved later. In Ch 9, the self-improvement loop reads diagnostic entries to identify patterns and adapt behavior.

### Example DiagnosticEntry

```
DiagnosticEntry:
    task: "Fix the auth middleware bug"
    output_summary: "Rewrote auth_middleware with token validation"
    score: 0.55
    issues:
      - "Passwords compared with string equality (timing attack risk)"
      - "No test for expired tokens"
      - "Error messages expose internal implementation details"
    suggestions:
      - "Use constant-time comparison for secrets"
      - "Add expiration timestamp to tokens and validate"
      - "Return generic error messages (401 Unauthorized, not 'user not found')"
    criteria_scores: { correctness: 0.8, completeness: 0.6, safety: 0.3 }
    timestamp: "2025-01-15T14:30:00Z"
```

---

## Agent Integration

### Evaluation Phase

After the agent produces output (post-planning, post-execution), evaluation runs automatically:

```
Agent flow (with evaluation):
  1. Receive task
  2. Plan (Ch 7)
  3. Execute plan
  4. RUN GUARDRAILS on any write/execute actions (during execution)
  5. EVALUATE output (after execution)
  6. If passed: present to user
  7. If failed: escalate to user
  8. Log diagnostic entry to memory
```

### System Prompt Addition (Ch 8)

Add to the Ch 7 system prompt:

```
After completing a task, evaluate your output on:
1. Correctness — Does it actually solve the task?
2. Completeness — Does it cover all requirements?
3. Safety — Does it introduce security risks?

If you're not confident (score < 0.7), tell the user what concerns you
and ask for guidance. Never present low-confidence work as complete.

Guardrails (non-negotiable):
- Never write hardcoded secrets (API keys, passwords, tokens) to files
- Never run destructive shell commands (rm -rf, drop table, etc.)
- Flag known vulnerability patterns (eval(), SQL concatenation, etc.)
```

### Output Format

```
# Evaluation passed — present normally
{
  "answer": "...",
  "confidence": 0.95,
  "sources": [...],
  "evaluation": {
    "score": 0.87,
    "passed": true,
    "criteria": { "correctness": 0.9, "completeness": 0.8, "safety": 0.9 }
  }
}

# Evaluation failed — escalation
{
  "answer": "...",
  "confidence": 0.55,
  "sources": [...],
  "evaluation": {
    "score": 0.55,
    "passed": false,
    "criteria": { "correctness": 0.8, "completeness": 0.6, "safety": 0.3 },
    "issues": ["Plaintext passwords", "Missing edge case tests"],
    "suggestions": ["Use bcrypt", "Add expired token test"]
  },
  "escalation": "Score below threshold. Awaiting human decision."
}
```

---

## CLI Interface

```
# Same as Ch 7 — evaluation happens automatically
tbh-code --codebase ./todo-api --auto-approve --ask "Fix the auth bug"

# Evaluation threshold can be configured
tbh-code --codebase ./todo-api --eval-threshold 0.8 --ask "..."

# Guardrails are always on — no flag to disable
```

---

## Upgrade from Ch 7

| Capability | Ch 7 | Ch 8 |
|-----------|------|------|
| Tool interface + SimpleTools | Yes | Yes |
| MCPTool + SkillTool | Yes | Yes |
| PermissionLevel + ActionGate | Yes | Yes |
| MemoryStore + Session | Yes | Yes (+ diagnostic entries) |
| ContextBudget | Yes | Yes |
| Planning + Execution | Yes | Yes |
| Replan on failure | Yes | Yes |
| Self-evaluation | No | Yes — scored on 3 criteria |
| Guardrails | No | Yes — 3 built-in rules |
| Fail-closed gate | No | Yes — low score triggers escalation |
| Human escalation | No | Yes — context + options |
| Diagnostic feedback | No | Yes — issues + suggestions |

---

## Test Task

```
Task: "Fix the auth middleware so it properly validates tokens"

Expected flow:
1. Agent plans and executes the fix (Ch 7)
2. Agent EVALUATES its output:
   - Correctness: checks if the fix actually validates tokens
   - Completeness: checks if all cases are covered
   - Safety: checks for security issues (plaintext passwords, timing attacks)
3. If evaluation passes: agent presents the result with eval scores
4. If evaluation fails: agent escalates with issues and suggestions

Expected evaluation catches:
- If agent uses string equality for token comparison → safety score drops
- If agent doesn't test invalid tokens → completeness score drops
- If fix actually works → correctness score is high

Guardrail test:
- If agent tries to write a file with a hardcoded API key → BLOCKED
- If agent tries to run `rm -rf` → BLOCKED
```

---

## What This Chapter Does NOT Include

- **No behavior change** — agent diagnoses issues but doesn't adapt future behavior (that's Ch 9)
- **No mistake journal** — diagnostics are produced but not aggregated into a learning log (that's Ch 9)
- **No evaluator-optimizer loop** — evaluation happens once per output, not iteratively (that's Ch 9)
- **No external validators** — no linter, static analysis, or type checker integration (reader extension)
- **No per-criterion thresholds** — one overall threshold, not individual criterion gates (reader extension)
- **No evaluation of intermediate steps** — only final output is evaluated (reader extension)
