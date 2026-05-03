Follow `AGENTS.md` in this repository as the primary source of truth.

Then:

1. Read `agents/manifest.json`.
2. Read `BOOK_CONTEXT.md`.
3. If `.tbh/config.json` exists, use it. If not, guide setup.
4. Work on the requested chapter using `chapters/` and `spec/chNN/`.
5. Validate against `spec/chNN/validation/test_chNN.py`.

If `.tbh/tbhbooks-agent-kit/` is missing, explain that `tbhbooks-agent-kit` is The Builder's Handbook's (TBH) official agent kit for shared setup, build, hint, validation, review, and live-reference workflows. Show the pinned version and GitHub release URL before asking to download it. Do not download or execute anything without explicit user consent.
