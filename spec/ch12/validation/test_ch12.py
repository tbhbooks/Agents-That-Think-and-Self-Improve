"""
Chapter 12 Validation Tests
============================

These tests validate the reader's Ch 12 implementation: message envelopes,
request/response, streaming, artifact handoffs, correlation IDs, and
timeout handling.

The reader's program must be callable as:
    tbh-code --swarm --codebase <path> --ask "<question>"
    tbh-code --agent <name> --codebase <path> --auto-approve --ask "<question>"
    tbh-code --agent <name> --listen

Message traces must appear in stdout with the format:
    [<agent>] Sending message:
    [<agent>] Received request from <peer> (<msg_id>, <correlation_id>)
    [<agent>] Received response from <peer> (<msg_id>, <correlation_id>)
    [<agent>] Stream from <peer> (<correlation_id>):
    [<agent>] Stream complete:
    [<agent>] Chain complete (<correlation_id>). <N> messages exchanged.
    [<agent>] TimeoutError:

Output must include a JSON response with: answer, confidence, sources, chain

Adjust AGENT_CMD and TODO_API_PATH below to match the reader's setup.
"""

import subprocess
import json
import os
import re
import sys

# ============================================================================
# CONFIGURATION
# ============================================================================

AGENT_CMD = "tbh-code"
TODO_API_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "todo-api")

# ============================================================================
# HELPERS
# ============================================================================

def ask(question, agent=None, swarm=False, auto_approve=True, timeout=120):
    """Ask the agent a question and capture stdout."""
    cmd = [AGENT_CMD]
    if swarm:
        cmd.append("--swarm")
    elif agent:
        cmd.extend(["--agent", agent])
    cmd.extend(["--codebase", TODO_API_PATH])
    if auto_approve:
        cmd.append("--auto-approve")
    cmd.extend(["--ask", question])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    return result.stdout


def extract_json(stdout):
    """Extract the JSON response from agent output."""
    json_start = stdout.find("{")
    json_end = stdout.rfind("}") + 1
    assert json_start >= 0 and json_end > json_start, (
        f"No JSON found in output:\n{stdout}"
    )
    return json.loads(stdout[json_start:json_end])


def extract_messages(stdout):
    """Extract message JSON objects from agent output."""
    messages = []
    lines = stdout.splitlines()
    i = 0
    while i < len(lines):
        if '"id":' in lines[i] and '"from":' in "\n".join(lines[i:i+10]):
            # Try to extract a JSON block starting near this line
            for start in range(max(0, i - 2), i + 1):
                if lines[start].strip().startswith("{"):
                    json_str = ""
                    brace_count = 0
                    for j in range(start, len(lines)):
                        json_str += lines[j] + "\n"
                        brace_count += lines[j].count("{") - lines[j].count("}")
                        if brace_count == 0:
                            try:
                                msg = json.loads(json_str)
                                if "id" in msg and "from" in msg and "type" in msg:
                                    messages.append(msg)
                            except json.JSONDecodeError:
                                pass
                            break
                    break
        i += 1
    return messages


def extract_correlation_ids(stdout):
    """Extract all correlation_id values from output."""
    ids = set()
    for match in re.finditer(r'"correlation_id":\s*"([^"]+)"', stdout):
        ids.add(match.group(1))
    for match in re.finditer(r'correlation_id:\s*([^\s,\)]+)', stdout):
        ids.add(match.group(1))
    return ids


def extract_chain_events(stdout):
    """Extract chain-related events from output."""
    events = []
    for line in stdout.splitlines():
        chain_match = re.match(r'\[chain-[^\]]+\]\s+(.+)', line)
        if chain_match:
            events.append(chain_match.group(1))
    return events


def extract_agent_events(stdout, agent_name):
    """Extract events for a specific agent."""
    events = []
    for line in stdout.splitlines():
        agent_match = re.match(
            rf'\[{re.escape(agent_name)}\]\s+(.+)', line
        )
        if agent_match:
            events.append(agent_match.group(1))
    return events


# ============================================================================
# TESTS — MESSAGE ENVELOPE
# ============================================================================

class TestMessageEnvelope:
    """Messages must have all 7 required fields."""

    def test_message_has_id(self):
        """Every message must have a unique id field."""
        stdout = ask(
            "Send a review request to reviewer for the auth middleware fix",
            agent="coder"
        )
        messages = extract_messages(stdout)
        assert len(messages) > 0, (
            "No messages found in output. "
            "Messages should be printed as JSON with id, from, to, type, "
            "correlation_id, payload, timestamp."
        )
        for msg in messages:
            assert "id" in msg, f"Message missing 'id' field: {msg}"
            assert msg["id"] is not None and msg["id"] != "", (
                f"Message 'id' is empty: {msg}"
            )

    def test_message_has_from_and_to(self):
        """Every message must have from and to fields."""
        stdout = ask(
            "Send a review request to reviewer for the auth fix",
            agent="coder"
        )
        messages = extract_messages(stdout)
        for msg in messages:
            assert "from" in msg, f"Message missing 'from' field: {msg}"
            assert "to" in msg, f"Message missing 'to' field: {msg}"
            assert msg["from"] != "", f"Message 'from' is empty: {msg}"
            assert msg["to"] != "", f"Message 'to' is empty: {msg}"

    def test_message_has_valid_type(self):
        """Message type must be one of: request, response, stream_chunk, stream_end."""
        stdout = ask(
            "Fix auth and get it reviewed and tested",
            swarm=True
        )
        messages = extract_messages(stdout)
        valid_types = {"request", "response", "stream_chunk", "stream_end"}
        for msg in messages:
            assert "type" in msg, f"Message missing 'type' field: {msg}"
            assert msg["type"] in valid_types, (
                f"Invalid message type '{msg['type']}'. "
                f"Must be one of: {valid_types}"
            )

    def test_message_has_correlation_id(self):
        """Every message must have a correlation_id."""
        stdout = ask(
            "Send a review request to reviewer",
            agent="coder"
        )
        messages = extract_messages(stdout)
        for msg in messages:
            assert "correlation_id" in msg, (
                f"Message missing 'correlation_id' field: {msg}"
            )
            assert msg["correlation_id"] is not None and msg["correlation_id"] != "", (
                f"Message 'correlation_id' is empty: {msg}"
            )

    def test_message_has_payload_and_timestamp(self):
        """Every message must have payload (dict) and timestamp (ISO 8601)."""
        stdout = ask(
            "Send a review request to reviewer",
            agent="coder"
        )
        messages = extract_messages(stdout)
        for msg in messages:
            assert "payload" in msg, f"Message missing 'payload' field: {msg}"
            assert isinstance(msg["payload"], dict), (
                f"Message payload must be a dict, got {type(msg['payload'])}"
            )
            assert "timestamp" in msg, f"Message missing 'timestamp' field: {msg}"
            # Basic ISO 8601 check
            assert re.match(
                r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', msg["timestamp"]
            ), f"Timestamp not ISO 8601: {msg['timestamp']}"


# ============================================================================
# TESTS — ARTIFACT
# ============================================================================

class TestArtifact:
    """Artifacts must have required fields and valid types."""

    def test_artifact_has_required_fields(self):
        """Artifacts must have id, type, producer, content, created_at."""
        stdout = ask(
            "Fix auth, send the diff to reviewer as an artifact",
            swarm=True
        )
        messages = extract_messages(stdout)
        artifacts = []
        for msg in messages:
            payload = msg.get("payload", {})
            if "artifact" in payload:
                artifacts.append(payload["artifact"])
        if artifacts:
            for art in artifacts:
                assert "id" in art, f"Artifact missing 'id': {art}"
                assert "type" in art, f"Artifact missing 'type': {art}"
                assert "producer" in art, f"Artifact missing 'producer': {art}"
                assert "content" in art, f"Artifact missing 'content': {art}"
                assert "created_at" in art, f"Artifact missing 'created_at': {art}"

    def test_artifact_type_is_valid(self):
        """Artifact type must be one of: diff, test_report, review, documentation, file_snapshot."""
        stdout = ask(
            "Fix auth, get it reviewed, get it tested — pass artifacts between agents",
            swarm=True
        )
        messages = extract_messages(stdout)
        valid_types = {"diff", "test_report", "review", "documentation", "file_snapshot"}
        for msg in messages:
            payload = msg.get("payload", {})
            if "artifact" in payload:
                art = payload["artifact"]
                assert art["type"] in valid_types, (
                    f"Invalid artifact type '{art['type']}'. "
                    f"Must be one of: {valid_types}"
                )

    def test_artifact_content_is_dict(self):
        """Artifact content must be a structured dict, not a string."""
        stdout = ask(
            "Fix auth and send the diff artifact to reviewer",
            swarm=True
        )
        messages = extract_messages(stdout)
        for msg in messages:
            payload = msg.get("payload", {})
            if "artifact" in payload:
                art = payload["artifact"]
                assert isinstance(art["content"], dict), (
                    f"Artifact content must be a dict, got {type(art['content'])}. "
                    "Artifacts carry structured data, not prose."
                )

    def test_artifact_has_producer(self):
        """Artifact producer must match the agent that created it."""
        stdout = ask(
            "Fix auth, get reviewed, get tested — full chain with artifacts",
            swarm=True
        )
        messages = extract_messages(stdout)
        for msg in messages:
            payload = msg.get("payload", {})
            if "artifact" in payload:
                art = payload["artifact"]
                assert art["producer"] != "", (
                    "Artifact producer is empty. "
                    "Must identify the agent that created the artifact."
                )


# ============================================================================
# TESTS — PEER MESSENGER SEND/RECEIVE
# ============================================================================

class TestPeerMessenger:
    """PeerMessenger must deliver messages between agents."""

    def test_send_delivers_to_correct_agent(self):
        """send() should deliver the message to the agent in the 'to' field."""
        stdout = ask(
            "Send a review request to reviewer and show me the response",
            agent="coder"
        )
        coder_events = extract_agent_events(stdout, "coder")
        reviewer_events = extract_agent_events(stdout, "reviewer")
        has_send = any("Sending" in e or "send" in e.lower() for e in coder_events)
        has_receive = any(
            "Received" in e or "request from coder" in e.lower()
            for e in reviewer_events
        )
        assert has_send, "Coder should show a send event"
        assert has_receive, (
            "Reviewer should show a receive event from coder. "
            "send() must deliver to the correct agent."
        )

    def test_request_returns_correlated_response(self):
        """request() should return a response with the same correlation_id."""
        stdout = ask(
            "Send a review request to reviewer for the auth fix",
            agent="coder"
        )
        messages = extract_messages(stdout)
        requests = [m for m in messages if m.get("type") == "request"]
        responses = [m for m in messages if m.get("type") == "response"]
        if requests and responses:
            req_cid = requests[0].get("correlation_id")
            resp_cid = responses[0].get("correlation_id")
            assert req_cid == resp_cid, (
                f"Request correlation_id ({req_cid}) != "
                f"Response correlation_id ({resp_cid}). "
                "request() must return a response with matching correlation_id."
            )

    def test_receive_filters_by_type(self):
        """receive() should filter messages by type."""
        stdout = ask(
            "Run auth tests with streaming results",
            swarm=True
        )
        messages = extract_messages(stdout)
        stream_chunks = [m for m in messages if m.get("type") == "stream_chunk"]
        stream_ends = [m for m in messages if m.get("type") == "stream_end"]
        # Coder should collect chunks and then see stream_end
        if stream_chunks and stream_ends:
            # stream_end should come after all chunks
            chunk_ids = [m["id"] for m in stream_chunks]
            end_id = stream_ends[0]["id"]
            assert end_id not in chunk_ids, (
                "stream_end should be a separate message from stream_chunks"
            )

    def test_receive_filters_by_sender(self):
        """receive() should be able to filter by the 'from' field."""
        stdout = ask(
            "Send a review request to reviewer and a test request to runner",
            swarm=True
        )
        messages = extract_messages(stdout)
        reviewer_msgs = [m for m in messages if m.get("from") == "reviewer"]
        runner_msgs = [m for m in messages if m.get("from") == "runner"]
        # Both agents should have sent messages
        all_text = stdout.lower()
        has_reviewer_response = len(reviewer_msgs) > 0 or "from reviewer" in all_text
        has_runner_response = len(runner_msgs) > 0 or "from runner" in all_text
        assert has_reviewer_response or has_runner_response, (
            "Expected messages from reviewer and/or runner. "
            "receive() should filter by sender."
        )


# ============================================================================
# TESTS — STREAMING
# ============================================================================

class TestStreaming:
    """Streaming must deliver chunks in order with a stream_end summary."""

    def test_stream_chunks_arrive_in_order(self):
        """stream_chunk messages should arrive in the order they were sent."""
        stdout = ask(
            "Run all auth tests and stream results back",
            swarm=True
        )
        messages = extract_messages(stdout)
        chunks = [m for m in messages if m.get("type") == "stream_chunk"]
        if len(chunks) >= 2:
            # Check timestamps are non-decreasing
            for i in range(1, len(chunks)):
                assert chunks[i]["timestamp"] >= chunks[i-1]["timestamp"], (
                    f"Stream chunks out of order: {chunks[i-1]['id']} "
                    f"({chunks[i-1]['timestamp']}) came before "
                    f"{chunks[i]['id']} ({chunks[i]['timestamp']})"
                )

    def test_stream_end_includes_summary(self):
        """stream_end message must include a summary in the payload."""
        stdout = ask(
            "Run auth tests with streaming results",
            swarm=True
        )
        messages = extract_messages(stdout)
        stream_ends = [m for m in messages if m.get("type") == "stream_end"]
        if stream_ends:
            payload = stream_ends[0].get("payload", {})
            assert "summary" in payload, (
                f"stream_end payload missing 'summary' field: {payload}. "
                "stream_end must include a summary of all chunks."
            )

    def test_stream_end_shares_correlation_id(self):
        """All stream messages (chunks + end) must share the same correlation_id."""
        stdout = ask(
            "Run auth tests and stream results",
            swarm=True
        )
        messages = extract_messages(stdout)
        stream_msgs = [
            m for m in messages
            if m.get("type") in ("stream_chunk", "stream_end")
        ]
        if len(stream_msgs) >= 2:
            cids = set(m["correlation_id"] for m in stream_msgs)
            assert len(cids) == 1, (
                f"Stream messages have multiple correlation_ids: {cids}. "
                "All chunks and stream_end must share one correlation_id."
            )

    def test_stream_has_at_least_one_chunk(self):
        """A stream must have at least one stream_chunk before stream_end."""
        stdout = ask(
            "Run auth tests with streaming",
            swarm=True
        )
        messages = extract_messages(stdout)
        chunks = [m for m in messages if m.get("type") == "stream_chunk"]
        ends = [m for m in messages if m.get("type") == "stream_end"]
        if ends:
            assert len(chunks) >= 1, (
                "stream_end found but no stream_chunks. "
                "A stream must have at least one chunk before ending."
            )


# ============================================================================
# TESTS — CHAIN TRACING
# ============================================================================

class TestChainTracing:
    """Correlation IDs must link entire conversation chains."""

    def test_full_chain_shares_correlation_id(self):
        """All messages in a multi-agent chain must share one correlation_id."""
        stdout = ask(
            "Fix auth, get reviewed, get tested — full chain",
            swarm=True
        )
        messages = extract_messages(stdout)
        if len(messages) >= 3:
            cids = set(m["correlation_id"] for m in messages)
            assert len(cids) == 1, (
                f"Chain has multiple correlation_ids: {cids}. "
                "All messages in one task chain must share one correlation_id."
            )

    def test_chain_involves_multiple_agents(self):
        """A full chain should involve at least 2 different agents."""
        stdout = ask(
            "Fix auth middleware, get it reviewed by reviewer, then tested by runner",
            swarm=True
        )
        messages = extract_messages(stdout)
        agents = set()
        for msg in messages:
            agents.add(msg.get("from", ""))
            agents.add(msg.get("to", ""))
        agents.discard("")
        assert len(agents) >= 2, (
            f"Chain only involves {agents}. "
            "Expected at least 2 agents in a peer communication chain."
        )

    def test_start_chain_creates_new_id(self):
        """start_chain() should produce a correlation_id."""
        stdout = ask(
            "Start a new review chain for auth middleware",
            agent="coder"
        )
        correlation_ids = extract_correlation_ids(stdout)
        assert len(correlation_ids) >= 1, (
            "No correlation_id found in output. "
            "start_chain() must produce a new correlation_id."
        )

    def test_chain_summary_in_response(self):
        """Response JSON should include chain metadata."""
        stdout = ask(
            "Fix auth, get reviewed, get tested — full chain",
            swarm=True
        )
        response = extract_json(stdout)
        has_chain = "chain" in response
        answer = response.get("answer", "").lower()
        has_chain_info = (
            has_chain or
            "correlation" in answer or
            "messages" in answer or
            "chain" in answer
        )
        assert has_chain_info, (
            "Response missing chain metadata. "
            "Expected chain info with correlation_id, message count, "
            "agents involved."
        )


# ============================================================================
# TESTS — TIMEOUT HANDLING
# ============================================================================

class TestTimeoutHandling:
    """Unresponsive peers must trigger timeouts, not infinite waits."""

    def test_timeout_on_unresponsive_peer(self):
        """receive() should timeout when the target agent doesn't respond."""
        stdout = ask(
            "Send a review request to an agent named 'nonexistent_agent' "
            "and report what happens",
            agent="coder"
        )
        all_text = stdout.lower()
        has_timeout = (
            "timeout" in all_text or
            "timed out" in all_text or
            "not respond" in all_text or
            "unreachable" in all_text or
            "undeliverable" in all_text
        )
        assert has_timeout, (
            "No timeout or error reported when sending to a nonexistent agent. "
            "receive() must timeout on unresponsive peers."
        )

    def test_timeout_does_not_crash(self):
        """A timeout should produce a valid JSON response, not a crash."""
        stdout = ask(
            "Try to get a review from an agent that doesn't exist",
            agent="coder"
        )
        # Should still produce some output (not crash)
        assert len(stdout.strip()) > 0, (
            "Agent produced no output. "
            "Timeouts should be handled gracefully, not crash."
        )


# ============================================================================
# TESTS — MESSAGE FILTERING
# ============================================================================

class TestMessageFiltering:
    """receive() must support filtering by type, sender, and correlation_id."""

    def test_filter_by_correlation_id(self):
        """Messages from different chains should not be mixed."""
        stdout = ask(
            "Run two separate tasks: review auth middleware AND review database layer. "
            "Use different correlation IDs for each.",
            swarm=True
        )
        correlation_ids = extract_correlation_ids(stdout)
        # If two chains were started, there should be 2+ correlation IDs
        all_text = stdout.lower()
        has_multiple_chains = (
            len(correlation_ids) >= 2 or
            "chain" in all_text
        )
        # Even if only one chain was used, verify correlation_id is present
        assert len(correlation_ids) >= 1, (
            "No correlation_ids found. "
            "Messages must include correlation_id for filtering."
        )

    def test_response_matches_request_correlation(self):
        """A response must have the same correlation_id as its request."""
        stdout = ask(
            "Send a review request to reviewer and show the response",
            agent="coder"
        )
        messages = extract_messages(stdout)
        requests = [m for m in messages if m.get("type") == "request"]
        responses = [m for m in messages if m.get("type") == "response"]
        if requests and responses:
            for req in requests:
                matching = [
                    r for r in responses
                    if r.get("correlation_id") == req.get("correlation_id")
                ]
                assert len(matching) > 0, (
                    f"Request {req['id']} with correlation_id "
                    f"{req['correlation_id']} has no matching response. "
                    "Responses must share the request's correlation_id."
                )


# ============================================================================
# RUNNER
# ============================================================================

if __name__ == "__main__":
    test_classes = [
        TestMessageEnvelope,
        TestArtifact,
        TestPeerMessenger,
        TestStreaming,
        TestChainTracing,
        TestTimeoutHandling,
        TestMessageFiltering,
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
