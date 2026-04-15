# 5 wheChapter 3 — Tool Use + MCP

## Scope

Give the agent a unified `Tool` interface with multiple implementations. Build local tools as `SimpleTool`, introduce MCP for external tool discovery as `MCPTool`, and manage everything through a `ToolRegistry`. The agent calls `execute(args) -> ToolResult` on every tool — it never knows or cares what's behind the interface.

## Learning Objectives

- Design a `Tool` interface that abstracts over local and remote implementations
- Implement `SimpleTool` for local functionality (read_file, list_files, search_code)
- Understand MCP as the standard protocol for external/shared tool discovery
- Implement `MCPTool` that wraps MCP-discovered tools in the same interface
- Build a `ToolRegistry` for unified tool management
- Verify tool results against ground truth before trusting them

## What You Build

1. **Tool interface + ToolResult:** The contract every tool must satisfy — `execute(args) -> ToolResult`.
2. **ParameterSchema:** Typed parameter definitions so the LLM knows what arguments to provide.
3. **SimpleTool (3 implementations):** `read_file`, `list_files`, `search_code` — local functions wrapped in the Tool interface.
4. **ToolRegistry:** Central registry that holds all tools. Register, find, list, match.
5. **MCP server:** Expose your SimpleTools via MCP protocol for external discovery.
6. **MCP client:** Discover tools from an MCP server, wrap each as an `MCPTool`.
7. **MCPTool:** A Tool implementation that routes `execute()` calls over MCP transport.
8. **Ground-truth verification:** After a tool call, verify the result before trusting it.

## Key Interfaces

- `Tool { name, description, parameters, execute(args) -> ToolResult }`
- `SimpleTool extends Tool` — local implementation
- `MCPTool extends Tool` — MCP transport, same interface
- `ToolRegistry { register(), find(), list(), match(), discover() }`
- `MCPServer { list_tools(), call_tool(name, args) -> result }`
- `MCPClient { connect(server_url), discover_tools() -> MCPTool[] }`
- `verify(expected, actual) -> VerificationResult`

## Success Criteria

- Tool interface is defined with execute(args) -> ToolResult
- Three SimpleTools work: read_file reads files, list_files lists directories, search_code finds patterns
- ToolRegistry registers, finds, and lists tools
- MCP server exposes tools, MCP client discovers them as MCPTools
- Agent selects the right tool for a given task
- Agent verifies results before presenting them
- Invalid tool arguments are caught before execution

## Concepts Introduced

- Tool interface as abstraction (SimpleTool vs MCPTool — same contract)
- Tool schemas and parameter validation
- ToolRegistry as the single source of truth for available tools
- MCP protocol (tools, resources, prompts)
- Ground-truth verification
- The gap between "the LLM said it" and "the tool confirmed it"

## Thread: Tool Interface

This chapter introduces the Tool interface that carries through the rest of the book:

- **Ch 3 (here):** Tool, SimpleTool, MCPTool, ToolRegistry
- **Ch 4:** SkillTool extends Tool — composite tools that orchestrate other tools
- **Ch 5:** More SimpleTools (write_file, delete_file, execute_shell) with permission levels
- **Ch 9+:** Tools evolve, get shared across agents, etc.

