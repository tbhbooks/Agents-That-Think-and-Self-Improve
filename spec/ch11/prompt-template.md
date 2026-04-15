# Chapter 11 — Broadcast & Discovery

## Scope

Build a broadcast system where agents announce their capabilities and skills on startup, discover peers without a central registry, share skills across agents, and propagate verified improvements.

## Learning Objectives

- Implement a file-based broadcast bus for agent announcements
- Design agent cards (A2A-inspired) that advertise capabilities and skills
- Build peer discovery — agents find each other by listening to broadcasts and reading history
- Enable skill sharing — agents broadcast full skill specs, peers adopt when tool-compatible
- Share verified improvements across agents — one agent learns, everyone benefits
- Handle agent withdrawal — graceful shutdown removes from peer registries

## What You Build

1. **BroadcastBus:** File-based message channel. Publish writes a JSON file to a shared directory. Subscribe watches the directory for new files. Simple, debuggable, sufficient for a local swarm.
2. **BroadcastMessage:** Structured envelope with type (`announce`, `withdraw`, `skill_share`, `improvement`), sender, payload, timestamp, and message_id for dedup.
3. **AgentCard:** A2A-inspired self-description — name, description, version, capabilities, skills (as SkillSummary[]), connection info, status, and announced_at timestamp.
4. **PeerRegistry:** Local index of discovered peers. Queryable by name, capability, or skill. Built from bus messages on startup.
5. **Skill sharing:** Agents broadcast full skill specs. Receiving agents check tool compatibility before adopting. Version conflicts resolved by keeping the newer version.
6. **Improvement sharing:** Agents broadcast refined skills with provenance — refinement reason, journal categories, and verified flag. Unverified improvements are rejected.
7. **Withdrawal protocol:** Agent publishes a withdraw message on shutdown. Peers remove it from their registry.

## Key Interfaces

```
BroadcastBus:
    channel_path: string                 # e.g., .tbh-code/bus/
    subscribe(callback) -> void          # start listening (file watcher)
    publish(message: BroadcastMessage) -> void   # write JSON file to bus
    unsubscribe() -> void                # stop listening

BroadcastMessage:
    type: enum("announce", "withdraw", "skill_share", "improvement")
    sender: string                       # agent name
    payload: any                         # depends on type
    timestamp: string                    # ISO 8601
    message_id: string                   # UUID for dedup

AgentCard:
    name: string                         # "coder", "reviewer", "runner", "researcher"
    description: string                  # what this agent does
    version: string                      # "1.0.0"
    capabilities: string[]               # tool verbs: ["read_file", "write_file", ...]
    skills: SkillSummary[]               # playbook summaries
    connection: ConnectionInfo           # how to reach this agent
    status: enum("available", "busy", "offline")
    announced_at: string                 # ISO 8601

SkillSummary:
    name: string                         # "find-bug", "code-review"
    version: int                         # skill version (from Ch 9)
    description: string                  # one-line summary

ConnectionInfo:
    protocol: string                     # "file", "socket", "http"
    address: string                      # path or URL

PeerRegistry:
    peers: dict[string, AgentCard]       # name -> card
    bus: BroadcastBus

    discover() -> void                   # subscribe + announce + read history
    get_peer(name: string) -> AgentCard | null
    get_peers() -> AgentCard[]
    get_peers_with_capability(cap: string) -> AgentCard[]
    get_peers_with_skill(skill_name: string) -> AgentCard[]
```

## Discovery Protocol

```
On startup:
  1. bus.subscribe(handle_broadcast)         # listen for new messages
  2. bus.publish(announce message)           # announce self
  3. for msg in read_existing(bus.channel_path):  # read history
       handle_broadcast(msg)

handle_broadcast(message):
  if type == "announce":  peers[sender] = payload
  if type == "withdraw":  delete peers[sender]
  if type == "skill_share":  handle_skill_share(message)
  if type == "improvement":  handle_improvement(message)
```

## Skill Sharing Protocol

```
share_skill(skill_spec):
  bus.publish({
    type: "skill_share",
    sender: agent.name,
    payload: { skill: skill_spec, origin: agent.name },
    ...
  })

handle_skill_share(message):
  skill = message.payload.skill
  missing_tools = [t for t in skill.tools_used if t not in agent.capabilities]
  if missing_tools: skip (incompatible)
  if existing version >= incoming version: skip (already up to date)
  else: adopt skill
```

## Improvement Sharing Protocol

```
share_improvement(skill_spec, refinement_reason):
  bus.publish({
    type: "improvement",
    sender: agent.name,
    payload: {
      skill: skill_spec,
      parent_version: skill_spec.parent_version,
      refinement_reason: refinement_reason,
      journal_categories: [...],
      verified: true
    },
    ...
  })

handle_improvement(message):
  if not verified: skip
  if skill not in agent's skill set: skip
  if existing version >= incoming version: skip
  if missing required tools: skip
  else: adopt improved skill
```

## Withdrawal Protocol

```
shutdown():
  bus.publish({ type: "withdraw", sender: agent.name, payload: { reason: "clean shutdown" } })
  bus.unsubscribe()

# Peers handle_broadcast removes the agent from peers dict
```

## Success Criteria

- Agents announce themselves on startup via the broadcast bus
- Other agents discover peers without configuration — subscribe + read history
- Agent cards contain name, capabilities, skills, connection info, and status
- Skills are shared and adopted only when the receiver has required tools
- Improvements propagate only when verified
- Duplicate announcements are handled idempotently (same agent re-announcing updates the entry)
- Agent withdrawal removes the agent from all peer registries
- Peer registry is queryable by capability and by skill name

## Concepts Introduced

- Broadcast-based discovery (no central registry)
- Agent cards (A2A-inspired)
- Capability and skill advertisement
- Skill sharing across agents (skills arc, third touch)
- Improvement propagation with verification as trust signal
- File-based message bus
- Gossip protocols — agents propagate peer information transitively (A tells B about C)
- Dynamic registry — a registry that updates automatically from broadcast events, as opposed to a static configuration file

## Thread: Skills Arc (Third Touch)

```
Ch 4:   Skills are static playbooks loaded from files
Ch 9:   Agent rewrites its own skills based on outcomes
Ch 11:  Agents broadcast skills to peers — skills become shareable assets
```

## Thread: Self-Improvement

```
Ch 9:   Individual agent improves itself
Ch 11:  Agents share improvements with peers — one agent's learned
        skill becomes another's starting point (only if verified)
```

## CLI Interface

```
# Start agents (each in a separate process)
tbh-code --agent coder --codebase ./todo-api
tbh-code --agent reviewer --codebase ./todo-api
tbh-code --agent runner --codebase ./todo-api
tbh-code --agent researcher --codebase ./todo-api

# Show discovered peers
tbh-code --agent coder --codebase ./todo-api --show-peers

# Share a skill
tbh-code --agent reviewer --codebase ./todo-api --share-skill security-review
```

## Upgrade from Ch 10

| Capability | Ch 10 | Ch 11 |
|-----------|-------|-------|
| Agent identity + system prompt | Yes | Yes |
| Capability boundaries | Yes | Yes |
| Effort budgets | Yes | Yes |
| Broadcast bus | No | Yes — file-based pub/sub |
| Agent cards | No | Yes — A2A-inspired self-description |
| Peer discovery | No | Yes — subscribe + announce + read history |
| Peer registry | No | Yes — queryable by capability and skill |
| Skill sharing | No | Yes — broadcast skills, tool-compatibility check |
| Improvement sharing | No | Yes — verified improvements propagate |
| Agent withdrawal | No | Yes — graceful shutdown removes from registry |

## Test Task

```
Task: End-to-end broadcast, discovery, skill sharing, and improvement propagation.

Phase 1 — Broadcast bus:
  Agent publishes a message. File appears in .tbh-code/bus/.

Phase 2 — Discovery:
  4 agents start, announce, discover each other. Each has 3 peers.

Phase 3 — Skill sharing:
  Reviewer shares "security-review" skill. Coder adopts (has tools).
  Runner skips (missing tools).

Phase 4 — Capability lookup:
  Coder queries registry for agents with "run_tests" capability. Gets Runner.

Phase 5 — Withdrawal:
  Coder shuts down. Peers remove Coder from registry.

Phase 6 — Improvement sharing:
  Coder broadcasts verified find-bug v2. Reviewer adopts (has skill + tools).
  Runner skips (doesn't have find-bug skill).
```

## What This Chapter Does NOT Include

- **No direct messaging** — agents discover each other but can't send messages yet (Ch 12)
- **No task delegation** — discovery is the address book, not the phone (Ch 12)
- **No central registry** — broadcast only, no coordinator
- **No heartbeat protocol** — lazy cleanup when messaging fails (Ch 12)
- **No external federation** — local swarm only (Ch 15)
- **No consensus** — no voting or conflict resolution on shared skills (Ch 13)
