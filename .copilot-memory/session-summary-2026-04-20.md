# Session Summary 2026-04-20

## Focus
- Per-leg touch support for OCO and post-fill auto-OCO.
- UI wizard alignment for TP/SL touch choices.
- Storage/runtime alignment and migration safety.

## Completed
- Added `tp_touch` / `sl_touch` support to auto-OCO post-fill flows.
- Added separate touch prompts for OCO leg 1 and leg 2 in the standalone wizard.
- Persisted `orders.touch` and `order_oco_leg.touch`.
- Aligned runtime scheduling so touch-enabled OCOs run on 60s cadence.
- Added regression tests for parser, storage, runtime, and wizard UI.
- Updated repo docs and AI handoff notes.

## Validation
- `PYTHONPATH=. pytest -q` => `95 passed, 6 warnings`.

## Notes
- The legacy `oco(tp=...,sl=...)` display format remains compatible.
- The DB migrations are additive; a live DB is migrated on startup.
