# Chapter 11 — Interface Spec

## Overview

Build broadcast-based peer discovery for a local agent swarm. A `BroadcastBus` uses the filesystem as a message queue — publish writes a JSON file, subscribe watches the directory. Each agent publishes an `AgentCard` (A2A-inspired) on startup. A `PeerRegistry` maintains discovered peers and supports queries by capability or skill. Skill sharing broadcasts full skill specs to peers, who adopt only when tool-compatible. Improvement sharing propagates verified skill refinements. Withdrawal removes agents from peer registries.

Operates on a shared `.tbh-code/bus/` directory visible to all agents on the same machine.

---

## BroadcastBus

```
BroadcastBus:
    channel_path: string                 # e.g., ".tbh-code/bus/"

    publish(message: BroadcastMessage) -> void
        # Write a JSON file to the bus directory
        # Filename format: "{timestamp}-{sender}-{type}.json"
        filename = "{message.timestamp}-{message.sender}-{message.type}.json"
        write_file(channel_path / filename, json_serialize(message))

    subscribe(callback: function(BroadcastMessage) -> void) -> void
        # Watch the bus directory for new files
        # When a new JSON file appears, deserialize and call callback
        watch_directory(channel_path, on_new_file=lambda path:
            callback(json_deserialize(read_file(path)))
        )

    unsubscribe() -> void
        # Stop watching the bus directory
        stop_watching(channel_path)

    read_existing() -> BroadcastMessage[]
        # Read all existing JSON files in the bus directory
        # Sorted by filename (which starts with timestamp)
        # Used on startup to discover agents that announced before us
        files = list_files(channel_path, pattern="*.json")
        files.sort()
        return [json_deserialize(read_file(f)) for f in files]
```

### Bus Directory Layout

```
.tbh-code/bus/
├── 2025-01-20T10:00:01Z-coder-announce.json
├── 2025-01-20T10:00:01Z-reviewer-announce.json
├── 2025-01-20T10:00:02Z-runner-announce.json
├── 2025-01-20T10:00:02Z-researcher-announce.json
└── 2025-01-20T10:00:05Z-reviewer-skill_share.json
```

---

## BroadcastMessage

```
BroadcastMessage:
    type: BroadcastType                  # what kind of message
    sender: string                       # agent name (e.g., "coder")
    payload: any                         # type-dependent content
    timestamp: string                    # ISO 8601 (e.g., "2025-01-20T10:00:01Z")
    message_id: string                   # UUID for deduplication

BroadcastType: enum(
    "announce",                          # agent is online, here's my card
    "withdraw",                          # agent is going offline
    "skill_share",                       # broadcasting a full skill spec
    "improvement"                        # broadcasting a verified skill refinement
)
```

### Payload by Type

```
type: "announce"
    payload: AgentCard                   # full agent card

type: "withdraw"
    payload: {
        reason: string                   # e.g., "clean shutdown"
    }

type: "skill_share"
    payload: {
        skill: SkillSpec                 # full skill spec with steps (from Ch 4/9)
        origin: string                   # who created/refined this skill
        context: string                  # why sharing (optional)
    }

type: "improvement"
    payload: {
        skill: SkillSpec                 # the improved skill spec
        parent_version: int              # version before improvement
        refinement_reason: string        # why the skill was refined
        journal_categories: string[]     # mistake categories that drove this
        verified: bool                   # did it pass before/after check?
    }
```

---

## AgentCard

```
AgentCard:
    name: string                         # unique agent name: "coder", "reviewer", "runner", "researcher"
    description: string                  # human-readable purpose
    version: string                      # agent version: "1.0.0"
    capabilities: string[]               # tool verbs the agent has
    skills: SkillSummary[]               # summaries of loaded skills
    connection: ConnectionInfo           # how to reach this agent (used in Ch 12)
    status: AgentStatus                  # current availability
    announced_at: string                 # ISO 8601 timestamp of this announcement
```

### AgentStatus

```
AgentStatus: enum(
    "available",                         # ready to accept work
    "busy",                              # currently processing
    "offline"                            # shutting down or unreachable
)
```

### Example AgentCards

```
Coder:
    name: "coder"
    description: "Reads and writes code. Applies edits, implements features, fixes bugs."
    version: "1.0.0"
    capabilities: ["read_file", "write_file", "search_code", "apply_diff"]
    skills: [
        { name: "find-bug", version: 2, description: "Locate and fix bugs with security awareness" },
        { name: "implement-feature", version: 1, description: "Add new functionality to existing codebase" }
    ]
    connection: { protocol: "file", address: ".tbh-code/agents/coder/inbox/" }
    status: "available"
    announced_at: "2025-01-20T10:00:01Z"

Reviewer:
    name: "reviewer"
    description: "Reviews code for quality, bugs, and best practices. Does not write code."
    version: "1.0.0"
    capabilities: ["read_file", "search_code", "evaluate_code"]
    skills: [
        { name: "code-review", version: 1, description: "Systematic code quality review" },
        { name: "refactor-safely", version: 1, description: "Identify safe refactoring opportunities" }
    ]
    connection: { protocol: "file", address: ".tbh-code/agents/reviewer/inbox/" }
    status: "available"
    announced_at: "2025-01-20T10:00:01Z"

Runner:
    name: "runner"
    description: "Runs commands and tests. Reports results."
    version: "1.0.0"
    capabilities: ["run_command", "run_tests"]
    skills: [
        { name: "test-suite", version: 1, description: "Run and report test results" }
    ]
    connection: { protocol: "file", address: ".tbh-code/agents/runner/inbox/" }
    status: "available"
    announced_at: "2025-01-20T10:00:02Z"

Researcher:
    name: "researcher"
    description: "Searches code and documentation. Provides context and analysis."
    version: "1.0.0"
    capabilities: ["read_file", "search_code", "search_docs"]
    skills: [
        { name: "find-context", version: 1, description: "Gather relevant code and documentation context" }
    ]
    connection: { protocol: "file", address: ".tbh-code/agents/researcher/inbox/" }
    status: "available"
    announced_at: "2025-01-20T10:00:02Z"
```

---

## SkillSummary

```
SkillSummary:
    name: string                         # skill identifier: "find-bug", "code-review"
    version: int                         # current version (from Ch 9 versioning)
    description: string                  # one-line summary of what the skill does
```

A summary is what appears on the agent card. The full `SkillSpec` (from Ch 4/9) is only sent in `skill_share` and `improvement` messages.

---

## ConnectionInfo

```
ConnectionInfo:
    protocol: string                     # transport protocol: "file", "socket", "http"
    address: string                      # path or URL to reach the agent

    # For a local file-based swarm:
    #   protocol: "file"
    #   address: ".tbh-code/agents/coder/inbox/"
    #
    # For socket-based (future):
    #   protocol: "socket"
    #   address: "/tmp/tbh-code-coder.sock"
    #
    # For HTTP-based (future):
    #   protocol: "http"
    #   address: "http://localhost:8001"
```

---

## PeerRegistry

```
PeerRegistry:
    peers: dict[string, AgentCard]       # agent name -> most recent card
    bus: BroadcastBus
    self_card: AgentCard                 # this agent's own card
    seen_message_ids: set[string]        # for deduplication

    discover() -> void
        # The three-step handshake:
        # 1. Subscribe to the bus (listen for new messages)
        bus.subscribe(callback=handle_broadcast)

        # 2. Announce self (publish own agent card)
        bus.publish(BroadcastMessage(
            type="announce",
            sender=self_card.name,
            payload=self_card,
            timestamp=now_iso8601(),
            message_id=uuid()
        ))

        # 3. Read existing messages (discover agents that started before us)
        for message in bus.read_existing():
            handle_broadcast(message)

    handle_broadcast(message: BroadcastMessage) -> void
        # Dedup: skip if we've already processed this message_id
        if message.message_id in seen_message_ids:
            return
        seen_message_ids.add(message.message_id)

        # Skip own messages
        if message.sender == self_card.name:
            return

        if message.type == "announce":
            # Add or update peer in registry
            peers[message.sender] = message.payload
            log("[{self_card.name}] Discovered peer: {message.sender} "
                "(capabilities: {message.payload.capabilities})")

        elif message.type == "withdraw":
            # Remove peer from registry
            if message.sender in peers:
                delete peers[message.sender]
                log("[{self_card.name}] Peer withdrawn: {message.sender}")

        elif message.type == "skill_share":
            handle_skill_share(message)

        elif message.type == "improvement":
            handle_improvement(message)

    get_peer(name: string) -> AgentCard | null
        return peers.get(name, null)

    get_peers() -> AgentCard[]
        return list(peers.values())

    get_peers_with_capability(cap: string) -> AgentCard[]
        # Return all peers that have the given capability
        return [card for card in peers.values() if cap in card.capabilities]

    get_peers_with_skill(skill_name: string) -> AgentCard[]
        # Return all peers that have the given skill (by name)
        return [card for card in peers.values()
                if any(s.name == skill_name for s in card.skills)]
```

---

## Skill Sharing

```
share_skill(skill_spec: SkillSpec) -> void
    # Broadcast a full skill spec for peers to adopt
    bus.publish(BroadcastMessage(
        type="skill_share",
        sender=self_card.name,
        payload={
            skill: skill_spec,
            origin: self_card.name,
            context: "Sharing skill that may be useful to peers"
        },
        timestamp=now_iso8601(),
        message_id=uuid()
    ))
    log("[{self_card.name}] Sharing skill: {skill_spec.name} v{skill_spec.version}")

handle_skill_share(message: BroadcastMessage) -> void
    skill = message.payload.skill
    required_tools = skill.tools_used

    # Tool compatibility check
    my_tools = self_card.capabilities
    missing = [t for t in required_tools if t not in my_tools]

    if missing:
        log("[{self_card.name}] Skipping skill {skill.name} — missing tools: {missing}")
        return

    # Version conflict check
    existing = self.skills.get(skill.name)
    if existing and existing.version >= skill.version:
        log("[{self_card.name}] Already have {skill.name} v{existing.version}, "
            "skipping v{skill.version}")
        return

    # Adopt the skill
    self.skills.add(skill)
    log("[{self_card.name}] Adopted skill: {skill.name} v{skill.version} "
        "(from {message.sender})")
```

---

## Improvement Sharing

```
share_improvement(skill_spec: SkillSpec, refinement_reason: string) -> void
    # Broadcast a verified skill improvement
    bus.publish(BroadcastMessage(
        type="improvement",
        sender=self_card.name,
        payload={
            skill: skill_spec,
            parent_version: skill_spec.parent_version,
            refinement_reason: refinement_reason,
            journal_categories: skill_spec.journal_categories or [],
            verified: true          # only share if verified
        },
        timestamp=now_iso8601(),
        message_id=uuid()
    ))
    log("[{self_card.name}] Broadcasting improvement: "
        "{skill_spec.name} v{skill_spec.parent_version} -> v{skill_spec.version}")

handle_improvement(message: BroadcastMessage) -> void
    improvement = message.payload
    skill = improvement.skill

    # Must be verified — unverified improvements don't propagate
    if not improvement.verified:
        log("[{self_card.name}] Skipping unverified improvement: {skill.name}")
        return

    # Must already have the skill (improvements upgrade, they don't introduce)
    existing = self.skills.get(skill.name)
    if existing is null:
        log("[{self_card.name}] {skill.name} not in skill set — skipping")
        return

    # Must be a newer version
    if existing.version >= skill.version:
        log("[{self_card.name}] Already at v{existing.version}, "
            "skipping v{skill.version}")
        return

    # Tool compatibility check
    missing = [t for t in skill.tools_used if t not in self_card.capabilities]
    if missing:
        log("[{self_card.name}] Cannot adopt improvement — missing tools: {missing}")
        return

    # Adopt the improvement
    self.skills.update(skill)
    log("[{self_card.name}] Adopted {skill.name} v{skill.version} "
        "(from {message.sender})")
```

---

## Withdrawal Protocol

```
shutdown() -> void
    # Announce departure before disconnecting
    bus.publish(BroadcastMessage(
        type="withdraw",
        sender=self_card.name,
        payload={ reason: "clean shutdown" },
        timestamp=now_iso8601(),
        message_id=uuid()
    ))
    bus.unsubscribe()
    log("[{self_card.name}] Shutdown complete")
```

### Crash Recovery (Lazy Cleanup)

```
# No heartbeat. If an agent crashes without withdrawing:
# - Stale entry remains in peer registries
# - When Ch 12 messaging tries to send to the crashed agent and fails,
#   the sender removes the stale peer from its registry
# - Cleanup happens on demand, not on a timer
```

---

## Discovery Protocol Flow

```
Agent A starts:
  1. A subscribes to bus
  2. A publishes announce(A's card)
  3. A reads existing messages → finds nothing (first agent)

Agent B starts (after A):
  1. B subscribes to bus
  2. B publishes announce(B's card)
  3. B reads existing messages → finds A's announce → adds A to registry

A receives B's announce (via subscription):
  → A adds B to registry

Result: A knows B, B knows A. Order doesn't matter.
```

---

## Log Format

Traces must appear in stdout with these prefixes:

```
[{agent_name}] Starting agent: {name} v{version}
[{agent_name}] Subscribing to broadcast bus: {channel_path}
[{agent_name}] Publishing agent card...
[{agent_name}] Discovered peer: {peer_name} (capabilities: {caps})
[{agent_name}] Peer registry: {count} peers
[{agent_name}] Sharing skill: {skill_name} v{version}
[{agent_name}] Adopted skill: {skill_name} v{version} (from {sender})
[{agent_name}] Skipping skill {skill_name} — missing tools: {tools}
[{agent_name}] Broadcasting improvement: {skill_name} v{old} -> v{new}
[{agent_name}] Adopted {skill_name} v{version} (from {sender})
[{agent_name}] Skipping unverified improvement: {skill_name}
[{agent_name}] {skill_name} not in skill set — skipping
[{agent_name}] Peer withdrawn: {peer_name}
[{agent_name}] Removing {peer_name} from peer registry
[{agent_name}] Peer registry: {count} peers ({peer_names})
[{agent_name}] Shutting down...
[{agent_name}] Publishing withdrawal...
[{agent_name}] Shutdown complete
```

---

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

---

## Discovery at Scale

The file-based broadcast bus works well for a local swarm of 4-10 agents. At larger scales, two alternative patterns become relevant:

**Gossip protocols:** Instead of every agent reading every broadcast message, agents propagate peer information transitively. Agent A discovers Agent B, then tells Agent C about B when they communicate. Information spreads epidemically — no single agent needs to see all messages. Useful when the bus becomes a bottleneck or agents span multiple machines.

**Dynamic registry:** A lightweight service that agents register with on startup and query for peer lookups. Unlike a static config file, the registry updates automatically as agents announce and withdraw. This is a middle ground between pure broadcast (no central component) and a full orchestrator (central control). The registry is a phone book, not a dispatcher — it answers "who can do X?" but doesn't assign work.
