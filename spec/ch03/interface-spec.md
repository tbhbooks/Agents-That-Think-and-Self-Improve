# Chapter 3 — Interface Spec

## Overview

Introduce the `Tool` interface — the contract every tool satisfies — with two implementations: `SimpleTool` (local functions) and `MCPTool` (discovered via MCP protocol). A `ToolRegistry` manages all tools uniformly. The agent calls `execute(args) -> ToolResult` without knowing what's behind the interface.

Operates on the `todo-api` codebase (see `../todo-api/`).

---

## Tool Interface

### Core Contract

```
Tool:
    name: string                    # unique identifier, e.g. "read_file"
    description: string             # human-readable purpose for the LLM
    parameters: ParameterSchema     # typed parameter definitions
    permission: PermissionLevel     # safe | write | dangerous (used in Ch 5)

    execute(args: dict) -> ToolResult
```

Every tool — local, remote, composite — implements this interface. The agent never calls anything that isn't a `Tool`.

### ToolResult

```
ToolResult:
    output: any         # the tool's return value (string, list, dict, etc.)
    success: bool       # did the tool succeed?
    error: string | null  # error message if success is false
```

Every tool returns a `ToolResult`. The agent checks `success` before using `output`.

### ParameterSchema

```
ParameterSchema:
    params: ParameterDef[]

ParameterDef:
    name: string
    type: string          # "string", "int", "bool", "string[]", etc.
    description: string
    required: bool
    default: any | null
```

The LLM reads the schema to know what arguments to provide. Invalid arguments are rejected before `execute()` is called.

### PermissionLevel

```
PermissionLevel: enum("safe", "write", "dangerous")
```

In Ch 3, all tools are `safe` (read-only). Ch 5 introduces `write` and `dangerous` levels with action gates. The field exists now so the interface doesn't change later.

---

## SimpleTool

```
SimpleTool extends Tool:
    # A tool implemented as a local function
    # execute() runs the function directly — no network, no protocol
    handler: function(args: dict) -> any
```

### Implementation: read_file

```
read_file SimpleTool:
    name: "read_file"
    description: "Read the contents of a file at the given path"
    parameters:
        path: string (required) — "File path relative to codebase root"
    permission: safe

    execute({ path }) -> ToolResult:
        if not file_exists(codebase_root / path):
            return ToolResult(output=null, success=false, error="File not found: {path}")
        content = read(codebase_root / path)
        return ToolResult(output=content, success=true, error=null)
```

### Implementation: list_files

```
list_files SimpleTool:
    name: "list_files"
    description: "List files and directories at the given path"
    parameters:
        path: string (optional, default: ".") — "Directory path relative to codebase root"
        recursive: bool (optional, default: false) — "Include subdirectories"
    permission: safe

    execute({ path, recursive }) -> ToolResult:
        if not directory_exists(codebase_root / path):
            return ToolResult(output=null, success=false, error="Directory not found: {path}")
        entries = list_directory(codebase_root / path, recursive=recursive)
        return ToolResult(output=entries, success=true, error=null)
```

### Implementation: search_code

```
search_code SimpleTool:
    name: "search_code"
    description: "Search for a pattern in files across the codebase"
    parameters:
        pattern: string (required) — "Search pattern (regex or literal)"
        path: string (optional, default: ".") — "Directory to search in"
        file_pattern: string (optional, default: "*") — "Glob pattern for file names"
    permission: safe

    execute({ pattern, path, file_pattern }) -> ToolResult:
        matches = grep(pattern, codebase_root / path, file_pattern)
        results = []
        for match in matches:
            results.append({
                file: match.file,
                line: match.line_number,
                content: match.line_content
            })
        return ToolResult(output=results, success=true, error=null)
```

---

## ToolRegistry

```
ToolRegistry:
    tools: dict[string, Tool]       # name -> Tool

    register(tool: Tool) -> void
        # Add a tool to the registry
        # Raises error if name already registered
        tools[tool.name] = tool

    find(name: string) -> Tool | null
        # Look up a tool by name
        return tools.get(name, null)

    list() -> Tool[]
        # Return all registered tools
        return tools.values()

    list_schemas() -> dict[]
        # Return tool schemas for the LLM (name, description, parameters)
        return [{ name: t.name, description: t.description,
                  parameters: t.parameters } for t in tools.values()]

    match(task: string) -> Tool[]
        # Given a task description, return tools that might be relevant
        # Simple implementation: keyword matching against tool descriptions
        # More sophisticated: LLM-based selection
        return [t for t in tools.values()
                if any(keyword in t.description.lower()
                       for keyword in extract_keywords(task))]

    discover(server: MCPServer) -> Tool[]
        # Connect to an MCP server, discover its tools, wrap each as MCPTool
        # Register all discovered tools
        mcp_tools = []
        for tool_def in server.list_tools():
            mcp_tool = MCPTool(
                name=tool_def.name,
                description=tool_def.description,
                parameters=tool_def.parameters,
                server_url=server.url
            )
            register(mcp_tool)
            mcp_tools.append(mcp_tool)
        return mcp_tools
```

---

## MCPTool

```
MCPTool extends Tool:
    server_url: string              # MCP server this tool was discovered from
    transport: MCPTransport         # connection to the server

    execute(args: dict) -> ToolResult:
        # Same interface as SimpleTool, but routes through MCP protocol
        mcp_response = transport.call_tool(name, args)
        return ToolResult(
            output=mcp_response.content,
            success=not mcp_response.is_error,
            error=mcp_response.error if mcp_response.is_error else null
        )
```

The agent calls `execute()` on an MCPTool exactly the same way it calls `execute()` on a SimpleTool. The transport is hidden behind the interface.

---

## MCP Server

```
MCPServer:
    name: string                    # server identity
    tools: Tool[]                   # tools this server exposes
    url: string                     # endpoint URL

    list_tools() -> ToolDefinition[]
        # Return schemas for all tools this server exposes
        return [{ name: t.name, description: t.description,
                  parameters: t.parameters } for t in tools]

    call_tool(name: string, args: dict) -> MCPResponse
        # Execute a tool by name and return the result
        tool = find_tool(name)
        if tool is null:
            return MCPResponse(content=null, is_error=true, error="Unknown tool: {name}")
        result = tool.execute(args)
        return MCPResponse(
            content=result.output,
            is_error=not result.success,
            error=result.error
        )

MCPResponse:
    content: any
    is_error: bool
    error: string | null

ToolDefinition:
    name: string
    description: string
    parameters: ParameterSchema
```

### What the Server Exposes

In Ch 3, the MCP server wraps the three SimpleTools:
- `read_file` — read file contents
- `list_files` — list directory entries
- `search_code` — search for patterns

External agents or clients can discover and call these via MCP protocol.

---

## MCP Client

```
MCPClient:
    servers: MCPServerConnection[]

    connect(server_url: string) -> MCPServerConnection
        # Establish connection to an MCP server
        connection = MCPServerConnection(url=server_url)
        connection.initialize()
        servers.append(connection)
        return connection

    discover_tools(connection: MCPServerConnection) -> MCPTool[]
        # Discover all tools from a connected server
        tool_defs = connection.list_tools()
        return [MCPTool(
            name=td.name,
            description=td.description,
            parameters=td.parameters,
            server_url=connection.url
        ) for td in tool_defs]

MCPServerConnection:
    url: string
    initialized: bool

    initialize() -> void
    list_tools() -> ToolDefinition[]
    call_tool(name: string, args: dict) -> MCPResponse
```

---

## Verification

```
verify(expected: any, actual: ToolResult) -> VerificationResult

VerificationResult:
    passed: bool
    details: string
```

### Verification Strategies

1. **Existence check:** Tool says file exists — verify it's in the file system.
2. **Content check:** Tool returns file content — verify it contains expected patterns.
3. **Count check:** Tool returns search results — verify the count is plausible.
4. **Cross-tool check:** Use one tool's output to verify another's claim (e.g., `search_code` finds a function, `read_file` confirms it exists at that line).

### Example

```
# Agent calls search_code to find auth_middleware
result = registry.find("search_code").execute({
    pattern: "auth_middleware",
    path: "src/"
})

# Verify: does the file actually contain the function?
verification = verify(
    expected="auth_middleware function definition",
    actual=result
)
# verification.passed = true if result.output contains matching entries
# verification.passed = false if result.output is empty or malformed
```

---

## Agent Integration

### Tool Selection Flow

```
1. Agent receives task from user
2. Agent asks ToolRegistry for available tools (list_schemas())
3. LLM reads tool schemas + task description
4. LLM selects a tool and provides arguments
5. Agent validates arguments against ParameterSchema
6. Agent calls tool.execute(args)
7. Agent reads ToolResult
8. Agent optionally verifies result
9. Agent incorporates result into reasoning
10. Agent may select another tool (loop continues)
```

### System Prompt Addition (Ch 3)

Add to the Ch 2 system prompt:

```
You have access to the following tools:
{tool_schemas}

To use a tool, respond with:
{
  "tool": "tool_name",
  "args": { "param1": "value1", ... }
}

After receiving a tool result, analyze it and either:
- Use another tool if needed
- Provide your final answer

Always verify tool results before trusting them.
```

---

## CLI Interface

```
# Same as Ch 2, but now with tools
tbh-code --codebase ./todo-api --ask "Find all functions that take a User parameter"

# With MCP server discovery
tbh-code --codebase ./todo-api --mcp-server http://localhost:3001 --ask "..."

# List available tools
tbh-code --codebase ./todo-api --list-tools
```

---

## Upgrade from Ch 2

| Capability | Ch 2 | Ch 3 |
|-----------|------|------|
| LLM call | Yes | Yes |
| File reading (built-in) | Yes | Yes (now also via Tool interface) |
| Conversation history | Yes | Yes |
| Structured output | Yes | Yes |
| Tool interface | No | Yes — Tool, SimpleTool, MCPTool |
| ToolRegistry | No | Yes |
| Tool calling (LLM selects + calls tools) | No | Yes |
| MCP server/client | No | Yes |
| Result verification | No | Yes |

---

## Test Task

```
Task: "Find all functions in todo-api that take a User parameter."

Expected flow:
1. Agent selects search_code tool
2. Calls search_code({ pattern: "User", path: "src/" })
3. Gets matches in multiple files
4. Optionally calls read_file to examine each match
5. Verifies results by cross-referencing
6. Returns structured answer with specific file:line references

Expected answer should identify:
- Functions/methods that accept User as a parameter
- Correct file paths and line numbers
- No hallucinated functions
```

---

## What This Chapter Does NOT Include

- **No file writing** — all tools are read-only (that's Ch 5)
- **No shell execution** — no running commands (that's Ch 5)
- **No skills** — tools are called individually, not composed into playbooks (that's Ch 4)
- **No permission gates** — all Ch 3 tools are safe/read-only (that's Ch 5)
- **No persistent memory** — tool results don't persist across sessions (that's Ch 6)
