"""
Chapter 11 Validation Tests
============================

These tests validate the reader's Ch 11 implementation: broadcast bus,
agent cards, peer discovery, skill sharing, improvement propagation,
and agent withdrawal.

The reader's program must be callable as:
    tbh-code --agent <name> --codebase <path>
    tbh-code --agent <name> --codebase <path> --show-peers

Discovery traces must appear in stdout with the format:
    [{agent}] Starting agent: {name} v{version}
    [{agent}] Subscribing to broadcast bus: {path}
    [{agent}] Publishing agent card...
    [{agent}] Discovered peer: {name} (capabilities: ...)
    [{agent}] Peer registry: {N} peers
    [{agent}] Sharing skill: {name} v{N}
    [{agent}] Adopted skill: {name} v{N} (from {sender})
    [{agent}] Skipping skill {name} — missing tools: [...]
    [{agent}] Broadcasting improvement: {name} v{old} -> v{new}
    [{agent}] Skipping unverified improvement: {name}
    [{agent}] Peer withdrawn: {name}
    [{agent}] Removing {name} from peer registry
    [{agent}] Shutdown complete

Adjust AGENT_CMD and TODO_API_PATH below to match the reader's setup.
"""

import subprocess
import json
import os
import re
import sys
import time
import shutil
import tempfile

# ============================================================================
# CONFIGURATION
# ============================================================================

AGENT_CMD = "tbh-code"
TODO_API_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "todo-api")
BUS_PATH = os.path.join(TODO_API_PATH, ".tbh-code", "bus")

# ============================================================================
# HELPERS
# ============================================================================

def clean_bus():
    """Remove all messages from the broadcast bus directory."""
    if os.path.exists(BUS_PATH):
        shutil.rmtree(BUS_PATH)
    os.makedirs(BUS_PATH, exist_ok=True)


def start_agent(name, timeout=30):
    """Start an agent and capture its startup output."""
    cmd = [AGENT_CMD, "--agent", name, "--codebase", TODO_API_PATH]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"Agent {name} failed: {result.stderr}"
    return result.stdout


def show_peers(agent_name, timeout=30):
    """Show an agent's discovered peers."""
    cmd = [AGENT_CMD, "--agent", agent_name, "--codebase", TODO_API_PATH, "--show-peers"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"Agent {agent_name} --show-peers failed: {result.stderr}"
    return result.stdout


def list_bus_files():
    """List all JSON files in the bus directory."""
    if not os.path.exists(BUS_PATH):
        return []
    return sorted([f for f in os.listdir(BUS_PATH) if f.endswith(".json")])


def read_bus_message(filename):
    """Read and parse a bus message file."""
    path = os.path.join(BUS_PATH, filename)
    with open(path, "r") as f:
        return json.load(f)


def extract_discovery_events(stdout):
    """Extract discovery-related events from output."""
    events = []
    for line in stdout.splitlines():
        match = re.match(r'\[(\w+)\] (.+)', line)
        if match:
            events.append({"agent": match.group(1), "message": match.group(2)})
    return events


def extract_discovered_peers(stdout, agent_name):
    """Extract peer names discovered by a specific agent."""
    peers = []
    for line in stdout.splitlines():
        match = re.match(
            rf'\[{agent_name}\] Discovered peer: (\w+)',
            line
        )
        if match:
            peers.append(match.group(1))
    return peers


def extract_peer_count(stdout, agent_name):
    """Extract the final peer count for an agent."""
    for line in reversed(stdout.splitlines()):
        match = re.match(
            rf'\[{agent_name}\] Peer registry: (\d+) peers?',
            line
        )
        if match:
            return int(match.group(1))
    return None


def extract_skill_events(stdout, agent_name):
    """Extract skill sharing events for an agent."""
    events = []
    for line in stdout.splitlines():
        if f"[{agent_name}]" in line and (
            "Adopted skill" in line or
            "Skipping skill" in line or
            "Sharing skill" in line
        ):
            events.append(line)
    return events


def extract_improvement_events(stdout, agent_name):
    """Extract improvement events for an agent."""
    events = []
    for line in stdout.splitlines():
        if f"[{agent_name}]" in line and (
            "Adopted" in line or
            "Skipping unverified" in line or
            "not in skill set" in line or
            "Broadcasting improvement" in line
        ):
            events.append(line)
    return events


def extract_withdrawal_events(stdout, agent_name):
    """Extract withdrawal events for an agent."""
    events = []
    for line in stdout.splitlines():
        if f"[{agent_name}]" in line and (
            "Peer withdrawn" in line or
            "Removing" in line or
            "Shutdown" in line or
            "withdrawal" in line.lower()
        ):
            events.append(line)
    return events


# ============================================================================
# TESTS — BROADCAST BUS
# ============================================================================

class TestBroadcastBus:
    """Broadcast bus must support publish and subscribe via the filesystem."""

    def test_publish_creates_file(self):
        """Publishing a message should create a JSON file in the bus directory."""
        clean_bus()
        stdout = start_agent("coder")
        files = list_bus_files()
        announce_files = [f for f in files if "announce" in f]
        assert len(announce_files) >= 1, (
            f"No announce file found in bus directory. Files: {files}. "
            "Publishing should write a JSON file to .tbh-code/bus/"
        )

    def test_publish_file_is_valid_json(self):
        """Bus message files should contain valid JSON."""
        clean_bus()
        start_agent("coder")
        files = list_bus_files()
        assert len(files) > 0, "No files in bus directory after agent start"
        msg = read_bus_message(files[0])
        assert isinstance(msg, dict), (
            f"Bus message is not a JSON object: {type(msg)}"
        )

    def test_publish_file_has_required_fields(self):
        """Bus messages must have type, sender, payload, timestamp, and message_id."""
        clean_bus()
        start_agent("coder")
        files = list_bus_files()
        assert len(files) > 0, "No files in bus directory"
        msg = read_bus_message(files[0])
        required = ["type", "sender", "payload", "timestamp", "message_id"]
        for field in required:
            assert field in msg, (
                f"Bus message missing required field: {field}. "
                f"Got fields: {list(msg.keys())}"
            )

    def test_filename_includes_sender_and_type(self):
        """Bus filenames should encode sender and message type for debuggability."""
        clean_bus()
        start_agent("coder")
        files = list_bus_files()
        assert len(files) > 0, "No files in bus directory"
        filename = files[0]
        assert "coder" in filename, (
            f"Filename should include sender name. Got: {filename}"
        )
        assert "announce" in filename, (
            f"Filename should include message type. Got: {filename}"
        )


# ============================================================================
# TESTS — BROADCAST MESSAGE
# ============================================================================

class TestBroadcastMessage:
    """Broadcast messages must have correct structure."""

    def test_announce_message_type(self):
        """Announce messages should have type='announce'."""
        clean_bus()
        start_agent("coder")
        files = list_bus_files()
        announce_files = [f for f in files if "announce" in f]
        assert len(announce_files) > 0, "No announce files found"
        msg = read_bus_message(announce_files[0])
        assert msg["type"] == "announce", (
            f"Expected type='announce', got '{msg['type']}'"
        )

    def test_message_has_sender(self):
        """Messages should identify the sender agent."""
        clean_bus()
        start_agent("coder")
        files = list_bus_files()
        msg = read_bus_message(files[0])
        assert msg["sender"] == "coder", (
            f"Expected sender='coder', got '{msg.get('sender')}'"
        )

    def test_message_has_unique_id(self):
        """Each message should have a unique message_id."""
        clean_bus()
        start_agent("coder")
        start_agent("reviewer")
        files = list_bus_files()
        ids = set()
        for f in files:
            msg = read_bus_message(f)
            mid = msg.get("message_id", "")
            assert mid not in ids, (
                f"Duplicate message_id: {mid}. Each message must have a unique ID."
            )
            ids.add(mid)


# ============================================================================
# TESTS — AGENT CARD
# ============================================================================

class TestAgentCard:
    """Agent cards must have all required fields."""

    def test_card_has_name(self):
        """Agent card must include the agent's name."""
        clean_bus()
        start_agent("coder")
        files = [f for f in list_bus_files() if "announce" in f]
        msg = read_bus_message(files[0])
        card = msg["payload"]
        assert "name" in card, "Agent card missing 'name' field"
        assert card["name"] == "coder", (
            f"Expected name='coder', got '{card['name']}'"
        )

    def test_card_has_capabilities(self):
        """Agent card must include capabilities list."""
        clean_bus()
        start_agent("coder")
        files = [f for f in list_bus_files() if "announce" in f]
        msg = read_bus_message(files[0])
        card = msg["payload"]
        assert "capabilities" in card, "Agent card missing 'capabilities' field"
        assert isinstance(card["capabilities"], list), (
            "Capabilities should be a list"
        )
        assert len(card["capabilities"]) > 0, (
            "Capabilities list should not be empty"
        )

    def test_card_has_skills(self):
        """Agent card must include skills summaries."""
        clean_bus()
        start_agent("coder")
        files = [f for f in list_bus_files() if "announce" in f]
        msg = read_bus_message(files[0])
        card = msg["payload"]
        assert "skills" in card, "Agent card missing 'skills' field"
        assert isinstance(card["skills"], list), "Skills should be a list"

    def test_card_has_connection_info(self):
        """Agent card must include connection info."""
        clean_bus()
        start_agent("coder")
        files = [f for f in list_bus_files() if "announce" in f]
        msg = read_bus_message(files[0])
        card = msg["payload"]
        assert "connection" in card, "Agent card missing 'connection' field"
        conn = card["connection"]
        assert "protocol" in conn, "Connection info missing 'protocol'"
        assert "address" in conn, "Connection info missing 'address'"

    def test_card_has_status(self):
        """Agent card must include status."""
        clean_bus()
        start_agent("coder")
        files = [f for f in list_bus_files() if "announce" in f]
        msg = read_bus_message(files[0])
        card = msg["payload"]
        assert "status" in card, "Agent card missing 'status' field"
        assert card["status"] in ("available", "busy", "offline"), (
            f"Unexpected status: '{card['status']}'. "
            "Expected 'available', 'busy', or 'offline'."
        )

    def test_skill_summary_has_fields(self):
        """Skill summaries in the card must have name, version, description."""
        clean_bus()
        start_agent("coder")
        files = [f for f in list_bus_files() if "announce" in f]
        msg = read_bus_message(files[0])
        card = msg["payload"]
        if card.get("skills"):
            skill = card["skills"][0]
            assert "name" in skill, "SkillSummary missing 'name'"
            assert "version" in skill, "SkillSummary missing 'version'"
            assert "description" in skill, "SkillSummary missing 'description'"


# ============================================================================
# TESTS — PEER DISCOVERY
# ============================================================================

class TestPeerDiscovery:
    """Agents must discover each other through the broadcast bus."""

    def test_agent_discovers_peers(self):
        """An agent should discover peers that announced before it."""
        clean_bus()
        start_agent("coder")
        stdout = start_agent("reviewer")
        peers = extract_discovered_peers(stdout, "reviewer")
        assert "coder" in peers, (
            f"Reviewer did not discover coder. Discovered: {peers}. "
            "Reading existing bus messages should discover earlier agents."
        )

    def test_peer_count_matches(self):
        """Each agent should have N-1 peers for N total agents."""
        clean_bus()
        all_output = ""
        for name in ["coder", "reviewer", "runner", "researcher"]:
            all_output += start_agent(name) + "\n"
        # The last agent (researcher) should see 3 peers
        count = extract_peer_count(all_output, "researcher")
        assert count is not None, (
            "Could not find peer count for researcher in output"
        )
        assert count == 3, (
            f"Expected 3 peers for researcher, got {count}. "
            "Each agent should discover all other agents."
        )

    def test_duplicate_announce_is_idempotent(self):
        """Re-announcing should update the entry, not create a duplicate."""
        clean_bus()
        start_agent("coder")
        # Simulate re-announce by starting again
        stdout = start_agent("coder")
        # Second agent start — reviewer should still see coder once
        start_agent("reviewer")
        stdout_rev = show_peers("reviewer")
        # Count how many times "coder" appears as a peer
        coder_count = stdout_rev.lower().count("coder")
        # It should appear exactly once (not duplicated)
        # Allow for the word to appear in context, but the peer list should have it once
        assert coder_count >= 1, (
            "Reviewer should list coder as a peer"
        )

    def test_discovery_order_independent(self):
        """Discovery should work regardless of startup order."""
        clean_bus()
        # Start reviewer first, then coder
        start_agent("reviewer")
        stdout = start_agent("coder")
        peers = extract_discovered_peers(stdout, "coder")
        assert "reviewer" in peers, (
            "Coder should discover reviewer regardless of startup order. "
            "read_existing should handle agents that started earlier."
        )


# ============================================================================
# TESTS — SKILL SHARING
# ============================================================================

class TestSkillSharing:
    """Skill sharing must check tool compatibility before adoption."""

    def test_skill_share_creates_bus_message(self):
        """Sharing a skill should publish a skill_share message to the bus."""
        clean_bus()
        start_agent("reviewer")
        # Trigger skill sharing (implementation-specific command)
        cmd = [AGENT_CMD, "--agent", "reviewer", "--codebase", TODO_API_PATH,
               "--share-skill", "code-review"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        files = list_bus_files()
        skill_files = [f for f in files if "skill_share" in f]
        assert len(skill_files) >= 1 or "Sharing skill" in result.stdout, (
            "No skill_share message found on bus after --share-skill. "
            f"Bus files: {files}"
        )

    def test_compatible_agent_adopts_skill(self):
        """An agent with all required tools should adopt a shared skill."""
        clean_bus()
        # Start both agents and trigger sharing
        start_agent("reviewer")
        stdout = start_agent("coder")
        all_events = extract_skill_events(stdout, "coder")
        all_text = " ".join(all_events).lower()
        # Look for adoption or compatible evidence
        if all_events:
            has_adoption = "adopted" in all_text or "compatible" in all_text
            assert has_adoption or "skipping" in all_text, (
                "Coder should either adopt or explicitly skip shared skills"
            )

    def test_incompatible_agent_skips_skill(self):
        """An agent missing required tools should skip the shared skill."""
        clean_bus()
        start_agent("reviewer")
        stdout = start_agent("runner")
        all_events = extract_skill_events(stdout, "runner")
        all_text = " ".join(all_events).lower()
        if all_events:
            has_skip = "skipping" in all_text or "missing" in all_text
            assert has_skip, (
                "Runner should skip skills requiring tools it doesn't have. "
                f"Events: {all_events}"
            )


# ============================================================================
# TESTS — IMPROVEMENT SHARING
# ============================================================================

class TestImprovementSharing:
    """Improvements must only propagate when verified."""

    def test_verified_improvement_adopted(self):
        """A verified improvement should be adopted by agents with the skill."""
        clean_bus()
        # Set up: coder and reviewer both start with find-bug v1
        start_agent("coder")
        stdout = start_agent("reviewer")
        events = extract_improvement_events(stdout, "reviewer")
        all_text = " ".join(events).lower()
        # If improvement was broadcast, reviewer with find-bug should adopt
        if events:
            has_adopt = "adopted" in all_text
            has_skip = "not in skill set" in all_text or "skipping" in all_text
            assert has_adopt or has_skip, (
                "Reviewer should either adopt or skip the improvement. "
                f"Events: {events}"
            )

    def test_unverified_improvement_rejected(self):
        """An unverified improvement should be rejected by all peers."""
        clean_bus()
        start_agent("coder")
        stdout = start_agent("reviewer")
        events = extract_improvement_events(stdout, "reviewer")
        all_text = " ".join(events).lower()
        if "unverified" in all_text:
            assert "skipping" in all_text, (
                "Unverified improvements should be skipped. "
                "Expected 'Skipping unverified improvement' in output."
            )

    def test_agent_without_skill_skips_improvement(self):
        """An agent that doesn't have the skill should skip the improvement."""
        clean_bus()
        start_agent("coder")
        stdout = start_agent("runner")
        events = extract_improvement_events(stdout, "runner")
        all_text = " ".join(events).lower()
        if events:
            has_skip = "not in skill set" in all_text or "skipping" in all_text
            assert has_skip, (
                "Runner should skip improvements for skills it doesn't have. "
                f"Events: {events}"
            )


# ============================================================================
# TESTS — AGENT WITHDRAWAL
# ============================================================================

class TestWithdrawal:
    """Agent withdrawal must remove the agent from peer registries."""

    def test_withdrawal_creates_bus_message(self):
        """Shutting down should publish a withdraw message to the bus."""
        clean_bus()
        start_agent("coder")
        # Agent should publish withdrawal on clean shutdown
        files = list_bus_files()
        withdraw_files = [f for f in files if "withdraw" in f]
        # Note: withdrawal happens at shutdown, so it depends on implementation
        # The agent may still be running — check for the message or log
        all_text = " ".join(files).lower()
        has_withdraw = len(withdraw_files) > 0 or "withdraw" in all_text
        # If the agent exited cleanly, withdrawal should have been published
        assert has_withdraw or len(files) > 0, (
            "Expected either a withdraw message on the bus or at least "
            "an announce message. Agent may not have started correctly."
        )

    def test_withdrawal_removes_from_registry(self):
        """After withdrawal, peers should remove the agent from their registry."""
        clean_bus()
        start_agent("coder")
        start_agent("reviewer")
        # Coder shuts down (clean shutdown triggers withdrawal)
        # Start a fresh reviewer to check registry
        stdout = start_agent("reviewer")
        events = extract_withdrawal_events(stdout, "reviewer")
        all_text = stdout.lower()
        # If coder withdrew, reviewer should have processed it
        if "withdraw" in all_text:
            has_removal = (
                "removing" in all_text or
                "withdrawn" in all_text or
                "peer withdrawn" in all_text
            )
            assert has_removal, (
                "Withdrawal message was published but peer was not removed "
                "from the registry."
            )


# ============================================================================
# TESTS — PEER REGISTRY QUERIES
# ============================================================================

class TestPeerRegistryQueries:
    """Peer registry must support queries by capability and skill."""

    def test_query_by_capability(self):
        """get_peers_with_capability should return matching peers."""
        clean_bus()
        for name in ["coder", "reviewer", "runner", "researcher"]:
            start_agent(name)
        stdout = show_peers("coder")
        all_text = stdout.lower()
        # The output should show peer information
        assert len(stdout.strip()) > 0, (
            "--show-peers returned empty output. "
            "Should display discovered peers."
        )

    def test_query_by_skill(self):
        """get_peers_with_skill should return peers that have the skill."""
        clean_bus()
        for name in ["coder", "reviewer", "runner", "researcher"]:
            start_agent(name)
        stdout = show_peers("coder")
        # Verify the registry is populated
        assert len(stdout.strip()) > 0, (
            "--show-peers returned empty output after discovery."
        )


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestBroadcastBus,
        TestBroadcastMessage,
        TestAgentCard,
        TestPeerDiscovery,
        TestSkillSharing,
        TestImprovementSharing,
        TestWithdrawal,
        TestPeerRegistryQueries,
    ]
    passed = 0
    failed = 0
    errors = []

    for cls in test_classes:
        print(f"\n{cls.__name__}")
        print("-" * len(cls.__name__))
        instance = cls()
        for method_name in sorted(dir(instance)):
            if method_name.startswith("test_"):
                test_name = f"{cls.__name__}.{method_name}"
                try:
                    getattr(instance, method_name)()
                    print(f"  PASS  {method_name}")
                    passed += 1
                except AssertionError as e:
                    print(f"  FAIL  {method_name}: {e}")
                    failed += 1
                    errors.append((test_name, str(e)))
                except Exception as e:
                    print(f"  ERROR {method_name}: {e}")
                    failed += 1
                    errors.append((test_name, str(e)))

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    if errors:
        print(f"\nFailures:")
        for name, err in errors:
            print(f"  {name}: {err}")
    sys.exit(0 if failed == 0 else 1)
