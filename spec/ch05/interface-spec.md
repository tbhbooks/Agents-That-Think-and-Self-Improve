# Chapter 5 — Interface Spec

## Overview

Implement the "dangerous" tools: `write_file`, `delete_file`, and `execute_shell` as SimpleTools. Add a permission model (`PermissionLevel`) and action gates (`ActionGate`) to control when dangerous operations can execute. Make write operations idempotent. The agent can now fix bugs end-to-end: find the problem, write the fix, run the tests.

Operates on the `todo-api` codebase (see `../todo-api/`).

---

## New SimpleTools

### write_file

```
write_file SimpleTool:
    name: "write_file"
    description: "Write content to a file, creating it if it doesn't exist"
    parameters:
        path: string (required) — "File path relative to codebase root"
        content: string (required) — "Content to write to the file"
    permission: write

    execute({ path, content }) -> ToolResult:
        # Idempotency check: if file exists with same content, skip
        if file_exists(codebase_root / path):
            existing = read(codebase_root / path)
            if existing == content:
                return ToolResult(
                    output={ written: false, reason: "content unchanged" },
                    success=true,
                    error=null
                )

        # Create parent directories if needed
        ensure_parent_dirs(codebase_root / path)

        # Write the file
        write(codebase_root / path, content)

        # Verify the write
        actual = read(codebase_root / path)
        if actual != content:
            return ToolResult(
                output=null,
                success=false,
                error="Write verification failed — content mismatch"
            )

        return ToolResult(
            output={ written: true, path: path, bytes: len(content) },
            success=true,
            error=null
        )
```

### delete_file

```
delete_file SimpleTool:
    name: "delete_file"
    description: "Delete a file at the given path"
    parameters:
        path: string (required) — "File path relative to codebase root"
    permission: dangerous

    execute({ path }) -> ToolResult:
        if not file_exists(codebase_root / path):
            return ToolResult(
                output=null,
                success=false,
                error="File not found: {path}"
            )

        delete(codebase_root / path)

        # Verify deletion
        if file_exists(codebase_root / path):
            return ToolResult(
                output=null,
                success=false,
                error="Delete verification failed — file still exists"
            )

        return ToolResult(
            output={ deleted: true, path: path },
            success=true,
            error=null
        )
```

### execute_shell

```
execute_shell SimpleTool:
    name: "execute_shell"
    description: "Execute a shell command and capture output"
    parameters:
        command: string (required) — "The shell command to execute"
        timeout: int (optional, default: 30) — "Timeout in seconds"
        working_dir: string (optional, default: ".") — "Working directory"
    permission: dangerous

    execute({ command, timeout, working_dir }) -> ToolResult:
        try:
            result = run_process(
                command,
                cwd=codebase_root / working_dir,
                timeout=timeout,
                capture_stdout=true,
                capture_stderr=true
            )
            return ToolResult(
                output={
                    stdout: result.stdout,
                    stderr: result.stderr,
                    exit_code: result.exit_code
                },
                success=(result.exit_code == 0),
                error=null if result.exit_code == 0
                      else "Command exited with code {result.exit_code}"
            )
        except TimeoutError:
            return ToolResult(
                output=null,
                success=false,
                error="Command timed out after {timeout} seconds"
            )
```

---

## PermissionLevel

```
PermissionLevel: enum("safe", "write", "dangerous")
```

### Classification

| Tool | Permission | Reason |
|------|-----------|--------|
| read_file | safe | Read-only, no side effects |
| list_files | safe | Read-only, no side effects |
| search_code | safe | Read-only, no side effects |
| write_file | write | Creates or modifies files |
| delete_file | dangerous | Destroys data |
| execute_shell | dangerous | Arbitrary command execution |

### On the Tool Interface

The `permission` field was defined in Ch 3 but all tools were `safe`. Now it matters:

```
Tool:
    name: string
    description: string
    parameters: ParameterSchema
    permission: PermissionLevel     # <-- now enforced

    execute(args: dict) -> ToolResult
```

Skills inherit the highest permission level of any tool they use:

```
SkillTool.permission = max(
    registry.find(tool_name).permission
    for tool_name in skill.tools_used
)
```

For example, if a skill uses `read_file` (safe) and `write_file` (write), the skill's permission is `write`.

---

## ActionGate

```
ActionGate:
    check(tool: Tool, args: dict) -> GateResult

GateResult:
    approved: bool
    reason: string

    # Gate logic:
    # - safe tools: always approved
    # - write tools: approved with warning (or require confirmation)
    # - dangerous tools: require explicit human confirmation
```

### Gate Flow

```
agent_execute(tool: Tool, args: dict) -> ToolResult:
    # Before every tool.execute(), check the gate
    gate_result = action_gate.check(tool, args)

    if not gate_result.approved:
        return ToolResult(
            output=null,
            success=false,
            error="Action blocked: {gate_result.reason}"
        )

    return tool.execute(args)
```

### Gate Behavior by Permission Level

```
ActionGate.check(tool, args):
    if tool.permission == "safe":
        return GateResult(approved=true, reason="safe operation")

    if tool.permission == "write":
        # Show what will be written, proceed after brief warning
        display_warning("Agent wants to write: {args}")
        return GateResult(approved=prompt_user("Allow? [y/n]"), reason="write operation")

    if tool.permission == "dangerous":
        # Show full details, require explicit confirmation
        display_danger("DANGEROUS: Agent wants to execute: {args}")
        return GateResult(approved=prompt_user("Allow? [y/n]"), reason="dangerous operation")
```

### Auto-Approve Mode

For automated testing and CI:

```
ActionGate:
    auto_approve: bool (default: false)

    # When auto_approve=true, all gates pass automatically
    # Use ONLY in testing — never in production
```

CLI flag: `tbh-code --auto-approve` or environment variable `TBH_AUTO_APPROVE=true`.

---

## Idempotent Writes

### Principle

A write operation should produce the same result whether run once or many times. This means:
1. Check if the file already has the target content
2. If yes, skip the write and return success
3. If no, write the content and verify

### Why It Matters

- Agent loops may retry failed operations
- Skills may re-execute after partial failure
- The user may run the same task twice
- Without idempotency, repeated writes could corrupt files or create duplicates

### Implementation (in write_file)

```
# Before writing
if file_exists(path) and read(path) == content:
    return ToolResult(
        output={ written: false, reason: "content unchanged" },
        success=true,
        error=null
    )
```

The `ToolResult.output.written` field tells the agent whether a write actually occurred, so it can report accurately.

---

## Updated ToolRegistry

With Ch 5 tools added:

```
Full ToolRegistry after Ch 5:

  SimpleTools:
    read_file       (safe)
    list_files      (safe)
    search_code     (safe)
    write_file      (write)       # NEW in Ch 5
    delete_file     (dangerous)   # NEW in Ch 5
    execute_shell   (dangerous)   # NEW in Ch 5

  MCPTools:
    (whatever MCP servers expose)

  SkillTools:
    find-bug        (safe — only uses read tools)
    add-endpoint    (write — uses write_file)     # NOW WORKS
    document-function (safe — only uses read tools)
```

Note: The "add-endpoint" skill from Ch 4 now works — `write_file` is registered.

---

## End-to-End: Fixing the Auth Bug

The payoff for Milestone 2. The agent uses skills + tools to actually fix the bug.

```
Flow:
1. User: "Fix the auth middleware bug and run the tests"
2. Agent matches "find-bug" skill (or reasons through manually)
3. search_code("auth_middleware") -> finds src/middleware/auth.pseudo
4. read_file("src/middleware/auth.pseudo") -> reads the buggy code
5. Agent identifies the bug: accepts any token, hardcodes user
6. Agent writes the fix:
   write_file("src/middleware/auth.pseudo", <fixed_content>)
   [ActionGate: "Agent wants to write src/middleware/auth.pseudo. Allow? [y/n]"]
   -> User approves
7. Agent writes a test:
   write_file("tests/middleware_test.pseudo", <test_content>)
   [ActionGate: "Agent wants to write tests/middleware_test.pseudo. Allow? [y/n]"]
   -> User approves
8. Agent runs the tests:
   execute_shell("run-tests tests/")
   [ActionGate: "DANGEROUS: Agent wants to execute 'run-tests tests/'. Allow? [y/n]"]
   -> User approves
9. Agent reads test output, reports results
```

---

## CLI Interface

```
# Same as Ch 4, but now with write/execute tools available
tbh-code --codebase ./todo-api --ask "Fix the auth middleware bug"

# With auto-approve for testing
tbh-code --codebase ./todo-api --auto-approve --ask "Fix the auth middleware bug"

# List tools now shows permission levels
tbh-code --codebase ./todo-api --list-tools
```

---

## Upgrade from Ch 4

| Capability | Ch 4 | Ch 5 |
|-----------|------|------|
| Tool interface | Yes | Yes |
| SimpleTool (read) | Yes (read_file, list_files, search_code) | Yes |
| SimpleTool (write) | No | Yes (write_file, delete_file) |
| SimpleTool (execute) | No | Yes (execute_shell) |
| MCPTool | Yes | Yes |
| SkillTool | Yes | Yes (add-endpoint skill now works) |
| ToolRegistry | Yes | Yes (6 SimpleTools + MCPTools + SkillTools) |
| PermissionLevel | Defined but unused | Enforced |
| ActionGate | No | Yes |
| Idempotent writes | No | Yes |
| End-to-end fix | No | Yes (find bug + write fix + run tests) |

---

## Test Task

```
Task: "Fix the auth middleware to properly validate tokens, then run the tests"

Expected flow:
1. search_code to find auth middleware
2. read_file to examine the buggy code
3. write_file to write the fix (gated)
4. write_file to add a test (gated)
5. execute_shell to run tests (gated)
6. Agent reports results

Expected: Agent should write a fix that at minimum:
- Decodes/parses the token
- Rejects empty or malformed tokens
- Sets req.user based on token content (not hardcoded)
```

---

## What This Chapter Does NOT Include

- **No persistent memory** — tool results and file changes don't persist across agent sessions (that's Ch 6)
- **No planning** — agent doesn't decompose complex tasks into subtasks (that's Ch 7)
- **No self-evaluation** — agent doesn't check its own fix quality (that's Ch 8)
- **No sandboxing** — file and shell operations happen in the real filesystem (production sandboxing is Ch 14)
- **No rollback** — if a write goes wrong, there's no automatic undo (the reader can add this)
