# AI Handoff Current

## Project Snapshot
- Project: Telegram trading bot with Binance price feed and SQLite persistence.
- Goal: Manage trigger-based orders from Telegram and execute on Binance.
- Current branch: check with `git branch`.

## Current Status
- Works:
  - Guided Telegram menu flow (including normalized emoji input handling).
  - Simple order trigger pipeline with storage and event log.
  - Monthly archive for closed orders.
  - PASS1 migration flow documented in `docs/ai` with command trigger.
- Recent implementation:
  - Simple order execution now calls Binance Spot `create_order` MARKET.
  - Exchange errors are logged and user is notified.
  - Added command-driven cross-machine migration kit (`/pass1-migrazione`).
  - PASS1 migration executed: tests passed and handoff/checklist updated. See `docs/ai/AI_PASS1_LAST_RUN.md` for details.
- Watch points:
  - Requires `BINANCE_API_KEY` and `BINANCE_SECRET_KEY`.
  - Runtime may fail at startup if env/token config is missing.

## Recent Technical Decisions
- Use `python-binance` directly in bot runtime for simple order execution.
- Keep normalized schema: `orders` as parent status, kind-specific details in child tables.
- Keep archival strategy month-based (not rolling 30-day window).

## Top 3 Next Tasks
1. Add optional retry policy for transient Binance failures.
2. Add command to inspect last exchange error by `order_id`.
3. Add dry-run/test-mode switch for safe validation.

## Run and Verify
```bash
.venv\Scripts\activate
python -m pytest -q
python telegram_bot.py
```

Last validation:
- 2026-04-02: `python -m pytest -q` => `2 passed, 4 warnings`.

- 2026-04-05: Implemented Binance symbol validator in `telegram_bot.py` (in-memory cache TTL, exception handling). Added targeted tests and ran `tests/test_cancel_order_ui.py` → `4 passed, 4 warnings`.


## Required Env
- `BOT_TOKEN`
- `BINANCE_API_KEY`
- `BINANCE_SECRET_KEY`
- Optional: `AUTHORIZED_CHAT_ID`, `BOT_DB_PATH`

## First Prompt For New Session
"Read README.md, ARCHITECTURE.md, and docs/ai/AI_HANDOFF_CURRENT.md. Summarize state in 6 bullets, list top 3 risks, then implement the smallest safe next step with tests."

## Migration Command
- Trigger command: `/pass1-migrazione`
- Rule source: `docs/ai/AI_MIGRATION_COMMAND.md`
- Reopen prompt:
  "Apri README.md, ARCHITECTURE.md, docs/ai/AI_HANDOFF_CURRENT.md e docs/ai/AI_MIGRATION_COMMAND.md. Esegui il flusso PASS1, poi proponi il prossimo passo minimo sicuro."

Files touched in this PASS1 setup:
- `docs/ai/AI_END_SESSION_CHECKLIST.md`
- `docs/ai/AI_MIGRATION_COMMAND.md`
- `docs/ai/AI_MIGRATION_PASS1_RUNBOOK.md`
- `docs/ai/AI_DECISIONS_LOG.md`
- `docs/ai/AI_BOOTSTRAP_PROMPT_TEMPLATE.md`
- `docs/ai/AI_HANDOFF_CURRENT.md`
