# AGENTS.md

Rules for AI coding agents working on this codebase.

## Code organisation

- If a function is used in only one place, keep it in the calling file. Do not
  create a separate module (e.g. `services.py`) just for the sake of separation.
