# Chapter 5 — File System + Shell

## Scope

Implement the dangerous tools: `write_file`, `delete_file`, and `execute_shell` as SimpleTools with the same `Tool` interface. Add a permission model that classifies every tool by risk level and action gates that block dangerous operations without human approval. Make write operations idempotent.

## Learning Objectives

- Implement `write_file`, `delete_file`, `execute_shell` as SimpleTools with `execute(args) -> ToolResult`
- Classify tools by `PermissionLevel` (safe, write, dangerous)
- Build an `ActionGate` that intercepts tool execution for dangerous operations
- Understand idempotent writes — check before modify, safe to retry
- Experience the full loop: skill identifies bug -> tools fix it -> shell runs tests

## What You Build

1. **write_file SimpleTool:** Creates or overwrites a file with given content. Permission: write.
2. **delete_file SimpleTool:** Deletes a file at the given path. Permission: dangerous.
3. **execute_shell SimpleTool:** Runs a shell command with timeout, captures stdout/stderr/exit_code. Permission: dangerous.
4. **PermissionLevel on Tool:** Every tool already has a `permission` field (from Ch 3). Now it matters — write and dangerous tools go through gates.
5. **ActionGate:** Intercepts `execute()` calls on tools with write or dangerous permission. Requires human confirmation before proceeding.
6. **Idempotent writes:** `write_file` checks if the file already has the target content. If so, returns success without writing.
7. **End-to-end:** Agent uses "find-bug" skill to identify the auth bug, then writes a fix and runs tests.

## Key Interfaces

- `write_file SimpleTool { execute({ path, content }) -> ToolResult }`
- `delete_file SimpleTool { execute({ path }) -> ToolResult }`
- `execute_shell SimpleTool { execute({ command, timeout }) -> ToolResult }`
- `PermissionLevel: enum("safe", "write", "dangerous")`
- `ActionGate { check(tool, args) -> approved | denied }`

## Success Criteria

- write_file creates files and writes content correctly
- delete_file removes files
- execute_shell runs commands, captures stdout/stderr/exit_code
- Permission model classifies all tools correctly
- Action gates block dangerous operations without approval
- Idempotent writes skip when content is unchanged
- End-to-end: agent fixes the auth bug (write fix + run tests)

## Concepts Introduced

- Write and execute tools as SimpleTools (same Tool interface)
- Permission models — classifying tools by risk
- Action gates — human-in-the-loop for dangerous operations
- Idempotency — safe to retry, check before modify
- The full agent loop: observe (read) -> plan (skill) -> act (write/execute) -> verify (test)
