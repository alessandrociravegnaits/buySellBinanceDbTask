# AI Decisions Log

- 2026-04-02: Standardizzato comando `/pass1-migrazione` per chiusura e migrazione contesto cross-machine. Motivo: ridurre perdita di contesto e rendere ripetibile il handoff.

- 2026-04-12: Implementata BTC Drop Protection side-aware.
	- SELL con `btc_alert_liquidate=true`: liquidazione market su drop BTC.
	- BUY con `btc_alert_liquidate=true`: cancellazione preventiva su drop BTC.
	- Motivo: mitigare rischio su entrambi i lati senza chiusure massive indiscriminate.

- 2026-04-12: Aggiunto comando runtime `/ad PERCENT` con persistenza setting `btc_liquidation_drop_percent` (`/ad 0` disabilita).
	- Motivo: tuning operativo rapido e sicuro senza modifica codice.

- 2026-04-12: Aggiornato schema storage con `orders.btc_alert_liquidate` + migrazione additiva.
	- Propagazione completata su save/load ordini, storico e archivio.
	- Motivo: coerenza tra runtime, UI e audit.

- 2026-04-12: Estesa copertura test su parser/wizard e integrazione side-aware BTC drop.
	- Evidenza: `PYTHONPATH=. pytest -q` => `54 passed, 4 warnings`.

- 2026-04-13: Aggiunta ricostruzione storico `gain%` da `event_log` e visualizzazione nella cronologia ordini.
	- Motivo: rendere visibile il profitto storico senza migrazione schema.

- 2026-04-14: Corretto update di `next_eval_at` per trailing sell e verificata la coerenza dei flussi simple buy/sell.
	- Evidenza: `PYTHONPATH=. pytest -q` => `58 passed, 4 warnings`.
