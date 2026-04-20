# AI Handoff Current

## Project Snapshot
- Project: Telegram trading bot with Binance price feed and SQLite persistence.
- Goal: Trigger-based orders via Telegram with runtime execution on Binance.
- Checkpoint branch: `featureFinale00`.
- Checkpoint HEAD: `a0e26e0`.

## Current Status (2026-04-20)
- BTC Drop Protection implemented side-aware:
  - SELL flagged (`btc_alert_liquidate=true`) => market liquidation on BTC drop.
  - BUY flagged (`btc_alert_liquidate=true`) => preventive cancellation on BTC drop.
- Runtime command `/ad PERCENT` available (`/ad 0` disables protection).
- Flag input supported from slash tokens and guided wizard.
- Storage schema updated with `orders.btc_alert_liquidate` + migration additive.
- Order views (`/o`) and historical view include `btc_alert` visibility.
- Historical orders now show reconstructed `gain%` when fill prices exist in `event_log`.
- Trailing sell schedule now advances `next_eval_at` on each due tick, matching the other scheduled order flows.
- Auto-OCO now supports independent `tp_touch` / `sl_touch` and the standalone OCO wizard asks touch separately for leg 1 and leg 2.
- Storage/runtime now carry `orders.touch` and `order_oco_leg.touch`; if at least one leg uses touch, the OCO parent schedules intrabar at 60s.

## Files changed in this checkpoint
- `storage.py`
- `telegram_bot.py`
- `README.md`
- `tests/test_oco_integration.py`
- `tests/test_oco_storage.py`
- `tests/test_btc_drop_ui_flag.py` (new)
- `tests/test_history_menu.py`
- `telegram_bot.py`
- `storage.py`
- `ARCHITECTURE.md`
- `progettoOCO.md`
- `docs/HANDOFF.md`
- `ISTRUZIONI_persistenza_contesto_cambio_macchina.md`
- `BOT_HANDOFF.md`
- `.copilot-memory/01-architettura-runtime.md`
- `.copilot-memory/02-dati-storage-oco.md`

## Validation
- Command: `PYTHONPATH=. pytest -q`
- Result: `95 passed, 6 warnings`.

## Known Risks / Watch Points
1. Race between runtime BTC-drop action and manual cancel command in same interval.
2. Behavior under exchange transient failures (no retry policy yet).
3. Boundary behavior around rapid wick movements (single-sample trigger every 60s).

## Next Safe Tasks
1. Add idempotent guard tests for cancel-vs-drop race windows.
2. Add optional retry policy for `btc_alert_liquidation_failed` paths.
3. Add optional debounce policy (2 consecutive samples below threshold).
4. Review whether historical `gain%` should be fee-adjusted or gross-only in UI labels.
5. Consider whether `/c a` should explicitly include `_oco_orders` in the in-memory cancellation sweep.

## Required Env
- `BOT_TOKEN`
- `BINANCE_API_KEY`
- `BINANCE_SECRET_KEY`
- Optional: `AUTHORIZED_CHAT_ID`, `BOT_DB_PATH`, `BTC_LIQUIDATION_DROP_PERCENT`

## Reopen Prompt (recommended)
"Apri README.md, ARCHITECTURE.md, progettoOCO.md, docs/HANDOFF.md e docs/ai/AI_HANDOFF_CURRENT.md. Conferma branch/HEAD, riesegui PYTHONPATH=. pytest -q, poi verifica che il wizard OCO mostri tp_touch/sl_touch o touch per leg e proponi il prossimo step minimo sicuro con test."
