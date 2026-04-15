# Chapter 4 — Interface Spec

## Overview

Introduce `SkillTool` — a composite tool that extends the `Tool` interface from Ch 3. A SkillTool orchestrates a sequence of other tool calls according to a playbook (skill spec). The agent treats skills exactly like any other tool: `execute(args) -> ToolResult`.

Operates on the `todo-api` codebase (see `../todo-api/`).

---

## SkillTool

```
SkillTool extends Tool:
    name: string                    # e.g. "find-bug"
    description: string             # "Systematically search for bugs in a codebase area"
    parameters: ParameterSchema     # what the skill needs to start (e.g. "area", "symptom")
    permission: PermissionLevel     # highest permission of any tool it calls
    steps: SkillStep[]              # ordered playbook of tool calls
    tools_used: string[]            # names of tools this skill calls

    execute(args: dict) -> ToolResult:
        # Run through steps in order, calling tools from the registry
        context = { **args }        # accumulates outputs from each step
        for step in steps:
            tool = registry.find(step.tool)
            if tool is null:
                return ToolResult(
                    output=null,
                    success=false,
                    error="Skill requires tool '{step.tool}' but it is not registered"
                )
            resolved_args = resolve_template(step.args_template, context)
            result = tool.execute(resolved_args)
            if not result.success:
                return ToolResult(
                    output=context,
                    success=false,
                    error="Step '{step.description}' failed: {result.error}"
                )
            context[step.output_key] = result.output
        return ToolResult(
            output=context,
            success=true,
            error=null
        )
```

Key insight: `SkillTool.execute()` returns a `ToolResult` just like `SimpleTool.execute()` and `MCPTool.execute()`. The agent doesn't need to know it's running a multi-step playbook.

---

## SkillStep

```
SkillStep:
    description: string             # human-readable step description
    tool: string                    # name of the tool to call (from registry)
    args_template: dict             # argument template — may reference prior step outputs
    output_key: string              # key to store this step's output in the context
    optional: bool (default: false) # if true, failure doesn't stop the skill
```

### Argument Templates

Args can reference outputs from prior steps using `{output_key}` syntax:

```
steps:
  - description: "Search for the pattern"
    tool: "search_code"
    args_template: { pattern: "{symptom}", path: "{area}" }
    output_key: "search_results"

  - description: "Read the most relevant file"
    tool: "read_file"
    args_template: { path: "{search_results[0].file}" }
    output_key: "file_content"
```

The `resolve_template()` function replaces `{key}` references with values from the context dictionary.

---

## SkillSpec

The on-disk format for skill definitions. Loaded by SkillLoader, converted to SkillTool instances.

```
SkillSpec:
    name: string                    # unique identifier
    description: string             # what this skill does
    trigger: string                 # when to use this skill (matching hint)
    tools_used: string[]            # tools this skill requires
    constraints: string[]           # rules the skill follows
    steps: SkillStepSpec[]

SkillStepSpec:
    description: string
    tool: string
    args_template: dict
    output_key: string
    optional: bool (default: false)
```

### File Format

Skill specs are stored as structured files (JSON, YAML, or TOML — reader's choice). Example in JSON:

```
{
  "name": "find-bug",
  "description": "Systematically search for bugs in a specific area of the codebase",
  "trigger": "find bug, debug, investigate error, what's wrong with",
  "tools_used": ["search_code", "read_file", "list_files"],
  "constraints": [
    "Always search before reading — don't guess file paths",
    "Read the actual code before diagnosing",
    "Report specific file paths and line numbers"
  ],
  "steps": [
    {
      "description": "Search for code related to the symptom",
      "tool": "search_code",
      "args_template": { "pattern": "{symptom}", "path": "{area}" },
      "output_key": "search_results"
    },
    {
      "description": "Read the most relevant file",
      "tool": "read_file",
      "args_template": { "path": "{search_results[0].file}" },
      "output_key": "source_code"
    },
    {
      "description": "Search for related tests",
      "tool": "search_code",
      "args_template": { "pattern": "{symptom}", "path": "tests/" },
      "output_key": "test_results",
      "optional": true
    },
    {
      "description": "Read the test file if found",
      "tool": "read_file",
      "args_template": { "path": "{test_results[0].file}" },
      "output_key": "test_code",
      "optional": true
    }
  ]
}
```

---

## Three Sample Skills

### Skill 1: Find Bug

```
name: "find-bug"
description: "Systematically search for bugs in a specific area of the codebase"
trigger: "find bug, debug, investigate, what's wrong, vulnerability, error"
tools_used: ["search_code", "read_file", "list_files"]
parameters:
    area: string (required) — "Area of the codebase to investigate (e.g. 'auth', 'tasks')"
    symptom: string (required) — "What's going wrong or what to look for"
constraints:
    - "Always search before reading — don't guess file paths"
    - "Read the actual code before diagnosing"
    - "Check for related tests"
    - "Report specific file paths and line numbers"
steps:
    1. Search for code matching the symptom in the target area
    2. Read the most relevant source file
    3. Search for related tests (optional)
    4. Read the test file if found (optional)
```

### Skill 2: Add Endpoint

```
name: "add-endpoint"
description: "Add a new API endpoint to the codebase"
trigger: "add endpoint, new route, create API, add API"
tools_used: ["list_files", "read_file", "search_code", "write_file"]
parameters:
    endpoint: string (required) — "The endpoint path (e.g. '/tasks/:id/tags')"
    method: string (required) — "HTTP method (GET, POST, PUT, DELETE)"
    description: string (required) — "What the endpoint does"
constraints:
    - "Follow existing code patterns in the codebase"
    - "Update the router to register the new route"
    - "Add corresponding test file"
steps:
    1. List existing route files to understand structure
    2. Read an existing route file as a template
    3. Search for the router setup to know where to register
    4. Write the new route file (requires write_file — Ch 5)
    5. Update the router (requires write_file — Ch 5)
    6. Write a test file (requires write_file — Ch 5)
```

Note: Steps 4-6 require `write_file` which is not implemented until Ch 5. The skill spec defines these steps, but they will fail with "tool not found" until Ch 5. This is intentional — it's the bridge to Ch 5.

### Skill 3: Document Function

```
name: "document-function"
description: "Generate documentation for a specific function"
trigger: "document, explain function, add docs, describe function"
tools_used: ["search_code", "read_file"]
parameters:
    function_name: string (required) — "Name of the function to document"
constraints:
    - "Read the actual function code before documenting"
    - "Include parameter types, return type, and purpose"
    - "Note any side effects or dependencies"
steps:
    1. Search for the function definition
    2. Read the file containing the function
    3. Search for usages of the function (optional)
    4. Search for tests of the function (optional)
```

---

## SkillLoader

```
SkillLoader:
    load_directory(path: string) -> SkillTool[]
        # Read all skill spec files from a directory
        # Parse each into a SkillSpec
        # Convert each SkillSpec into a SkillTool
        # Return the list of SkillTools
        skills = []
        for file in list_files(path, pattern="*.json"):  # or *.yaml, *.toml
            spec = parse_skill_spec(file)
            skill_tool = SkillTool(
                name=spec.name,
                description=spec.description,
                parameters=derive_parameters(spec),
                permission=derive_permission(spec, registry),
                steps=spec.steps,
                tools_used=spec.tools_used
            )
            skills.append(skill_tool)
        return skills

    load_and_register(path: string, registry: ToolRegistry) -> int
        # Load skills and register them in the ToolRegistry
        skills = load_directory(path)
        for skill in skills:
            registry.register(skill)
        return len(skills)
```

### Skill Directory Structure

```
skills/
  find-bug.json
  add-endpoint.json
  document-function.json
```

---

## Skill Matching

```
match_skill(task: string, registry: ToolRegistry) -> SkillTool | null
    # Find the best matching skill for a task
    # Returns null if no skill matches (agent falls back to general reasoning)

    skill_tools = [t for t in registry.list() if isinstance(t, SkillTool)]
    if not skill_tools:
        return null

    best_match = null
    best_score = 0

    for skill in skill_tools:
        score = compute_match_score(task, skill.trigger_keywords)
        if score > best_score:
            best_score = score
            best_match = skill

    if best_score < MATCH_THRESHOLD:
        return null

    return best_match
```

### Match Score Computation

Simple approach: keyword overlap between the task description and the skill's trigger string. Count how many trigger keywords appear in the task.

```
compute_match_score(task: string, trigger: string) -> float
    task_words = lowercase_tokenize(task)
    trigger_words = lowercase_tokenize(trigger)
    overlap = len(set(task_words) & set(trigger_words))
    return overlap / len(trigger_words) if trigger_words else 0
```

More sophisticated approaches (for the reader to explore):
- LLM-based matching: ask the LLM which skill fits best
- Embedding similarity: embed the task and skill descriptions, compute cosine similarity

---

## MCP Prompts-as-Skills

MCP's `prompt` primitive can deliver skills to external agents.

```
MCPPromptAsSkill:
    # Expose a SkillTool as an MCP prompt
    # External agents can discover and use the skill via MCP

    to_mcp_prompt(skill: SkillTool) -> MCPPrompt:
        return MCPPrompt(
            name=skill.name,
            description=skill.description,
            arguments=skill.parameters,
            template=format_skill_as_instructions(skill)
        )

MCPPrompt:
    name: string
    description: string
    arguments: ParameterSchema
    template: string                # the skill steps as natural language instructions
```

This means skills can be:
1. Loaded from local files (SkillLoader)
2. Discovered from MCP servers (MCPClient discovers MCPPrompts, converts to SkillTools)
3. Exposed via MCP server (your skills become discoverable by other agents)

---

## Agent Integration

### Startup Flow

```
1. Create ToolRegistry
2. Register SimpleTools (read_file, list_files, search_code)
3. Connect to MCP servers, discover MCPTools, register them
4. Load skills from skills/ directory via SkillLoader, register as SkillTools
5. Agent now has a unified registry of SimpleTools + MCPTools + SkillTools
```

### Task Execution Flow

```
1. Agent receives task from user
2. Try match_skill(task, registry)
3. If skill found:
   a. Agent calls skill.execute(args) — same as any other tool
   b. SkillTool runs through its steps, calling other tools
   c. Agent gets back a ToolResult with aggregated output
4. If no skill found:
   a. Agent falls back to general reasoning with individual tools
   b. LLM selects tools one at a time (Ch 3 behavior)
```

---

## CLI Interface

```
# Default — skills loaded automatically from skills/ directory
tbh-code --codebase ./todo-api --ask "Find the bug in the auth system"

# Explicit skill selection
tbh-code --codebase ./todo-api --skill "find-bug" --task "investigate auth middleware"

# List available skills
tbh-code --codebase ./todo-api --list-skills

# Show skill details
tbh-code --codebase ./todo-api --show-skill "find-bug"
```

---

## Upgrade from Ch 3

| Capability | Ch 3 | Ch 4 |
|-----------|------|------|
| Tool interface | Yes | Yes |
| SimpleTool | Yes (read_file, list_files, search_code) | Yes |
| MCPTool | Yes | Yes |
| ToolRegistry | Yes | Yes (now also holds SkillTools) |
| SkillTool | No | Yes — composite tools that orchestrate other tools |
| Skill specs | No | Yes — loaded from files |
| Skill matching | No | Yes — task -> best skill |
| Skill execution | No | Yes — step-by-step playbook |
| MCP prompts-as-skills | No | Yes |

---

## Test Task

```
Task: "Find the bug in the auth middleware"

Expected flow:
1. match_skill() matches to "find-bug" skill
2. Agent calls find-bug.execute({ area: "src/middleware", symptom: "auth" })
3. SkillTool runs steps:
   Step 1: search_code({ pattern: "auth", path: "src/middleware" }) -> matches
   Step 2: read_file({ path: "src/middleware/auth.pseudo" }) -> source code
   Step 3: search_code({ pattern: "auth", path: "tests/" }) -> test matches
   Step 4: read_file({ path: "tests/auth_test.pseudo" }) -> test code
4. SkillTool returns ToolResult with aggregated context
5. Agent analyzes the context and identifies the bug

Expected answer should identify:
- The auth_middleware function accepts any non-empty token
- No signature verification, no expiry check, hardcoded user
- Test gap: no tests for the middleware itself
```

### Fallback Test

```
Task: "What is the meaning of life?"

Expected flow:
1. match_skill() returns null — no skill matches
2. Agent falls back to general reasoning (no tools needed)
3. Agent responds without using any skill
```

---

## What This Chapter Does NOT Include

- **No file writing** — skills can reference write_file but it's not implemented yet (that's Ch 5)
- **No shell execution** — skills can reference execute_shell but it's not implemented yet (that's Ch 5)
- **No skill generation** — skills are static files, not generated by the agent (that's Ch 9)
- **No skill sharing** — skills are local, not broadcast to peers (that's Ch 11)
- **No persistent memory** — skill execution results don't persist across sessions (that's Ch 6)
