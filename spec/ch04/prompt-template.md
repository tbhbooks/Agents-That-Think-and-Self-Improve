# Chapter 4 — Skills: Teaching Your Agent What To Do

## Scope

Introduce `SkillTool` — a composite tool that orchestrates other tools through a playbook of steps. SkillTool extends the `Tool` interface from Ch 3, so the agent calls `execute()` on a skill the same way it calls any other tool. Tools are single capabilities (verbs: search, read, write). Skills are strategies (recipes: search → read → analyze → check tests).

## Learning Objectives

- Distinguish skills (strategies/recipes) from tools (single capabilities/verbs)
- Implement `SkillTool extends Tool` — skills are composite tools with the same interface
- Design skill specs as composable instructions with steps, triggers, and constraints
- Build a SkillLoader that reads skill files and registers SkillTools in the ToolRegistry
- Match tasks to the best matching skill
- Understand MCP prompts as a skill delivery mechanism

## What You Build

1. **SkillTool extends Tool:** A composite tool that executes a playbook of other tool calls. Same `execute(args) -> ToolResult` interface.
2. **SkillSpec format:** Name, description, trigger, steps, tools_used, constraints — the structure of a skill file.
3. **SkillStep:** An individual step within a skill — describes what tool to call and how.
4. **SkillLoader:** Reads skill files from a directory, creates SkillTool instances, registers them in the ToolRegistry.
5. **Skill matching:** Given a task, find the best matching SkillTool (or fall back to general reasoning).
6. **Three sample skills:** "Find Bug", "Add Endpoint", "Document Function".
7. **MCP prompts-as-skills:** Expose skills via MCP prompt primitive for external discovery.

## Key Interfaces

- `SkillTool extends Tool { steps, tools_used, execute(args) -> ToolResult }`
- `SkillSpec { name, description, trigger, steps[], tools_used[], constraints }`
- `SkillStep { description, tool, args_template, output_key }`
- `SkillLoader { load_directory(path) -> SkillTool[] }`
- `match_skill(task, registry) -> SkillTool | null`

## Success Criteria

- SkillTool implements the Tool interface — `execute(args) -> ToolResult`
- Agent loads skills from spec files on startup
- Skills are registered in the same ToolRegistry as SimpleTools and MCPTools
- Agent selects the correct skill for a given task
- Skill execution follows defined steps in order, calling the right tools
- Agent falls back gracefully when no skill matches
- Skills compose multiple tool calls into coherent workflows

## Concepts Introduced

- Skills vs tools (strategies/recipes vs single capabilities/verbs)
- SkillTool as a composite tool — same interface, orchestrates other tools
- Skill specs as composable instructions
- Skill matching and selection
- MCP prompts primitive as skill delivery
- The ToolRegistry as a unified catalog (SimpleTools + MCPTools + SkillTools)

## Thread: Skills Arc

This is the **first touch** of the skills thread:
- **Ch 4 (here):** Skills are static playbooks loaded from files. SkillTool extends Tool.
- **Ch 9:** Self-improvement — agent rewrites its own skill specs based on outcomes
- **Ch 11:** Skill sharing — agents broadcast skills to peers in the swarm
