# Book Context: Agents That Think and Self-Improve

## Book

- id: `agents`
- project built by reader: `tbh-code`
- chapters: `ch00` to `ch15`

## What The Reader Builds

A CLI coding agent that evolves from a simple one-shot wrapper to a multi-agent system with memory, planning, evaluation, and production concerns.

## Chapter Progression

- Early chapters: one-shot limitations and agent loop foundations.
- Middle chapters: tool use, file/shell actions, memory, planning, evaluation.
- Later chapters: multi-agent patterns, production architecture, ecosystem integration.

## Key Paths

- chapter content: `chapters/`
- chapter specs: `spec/chNN/`
- validation: `spec/chNN/validation/test_chNN.py`

## Validation Notes

Validation tests use pytest and command-driven behaviors. Readers may implement in different languages, but expected behavior comes from chapter specs.

## Agent Guidance

- Keep guidance concrete and chapter-scoped.
- Prefer referencing specific spec sections.
- Avoid skipping ahead to future chapter architecture unless the reader asks.
