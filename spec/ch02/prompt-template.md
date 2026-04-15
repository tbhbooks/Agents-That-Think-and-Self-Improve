# Chapter 2 — Your First Real Agent

## Scope

Build a working agent that can answer questions about a codebase by reading files and maintaining conversation context.

## Learning Objectives

- Build an Augmented LLM (LLM + retrieval + memory)
- Design effective system prompts that set agent identity and boundaries
- Manage conversation history as working memory
- Parse structured output from the LLM
- Understand context window limits and their implications

## What You Build

1. **System prompt:** Define the agent's identity, capabilities, and constraints.
2. **Conversation history:** Maintain message history across turns within a session.
3. **Codebase context:** Read files from a local directory and inject relevant content into the prompt.
4. **Structured output:** Parse the LLM's response into actionable parts (answer, confidence, sources).

## Key Interfaces

- `Agent { system_prompt, history, context }`
- `agent.chat(user_message) → structured_response`
- `load_context(directory) → file_contents`

## Success Criteria

- Agent answers questions about files it has read
- Agent maintains coherent multi-turn conversation
- Agent admits when it doesn't know (doesn't hallucinate file contents)
- Structured output is parseable and consistent

## Concepts Introduced

- Augmented LLM (the building block)
- System prompts as agent identity
- Conversation history as short-term memory
- Structured output parsing
- Context window management
