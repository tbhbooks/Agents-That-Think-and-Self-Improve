# Cursor Instructions

This file exists because Cursor commonly checks `CURSOR.md` and `.cursor/rules/`.

Cursor startup order for TBH:

1. If `.cursor/rules/tbh-reader.mdc` exists, load it.
2. Read `AGENTS.md`.
3. Follow `AGENTS.md` for all command behavior.

Do not redefine setup/build/validate/hint/review logic in this file.
If this file conflicts with `AGENTS.md`, `AGENTS.md` wins.
