# Architettura e Runtime

## Scopo
Trading rules engine controllato via Telegram, con persistenza SQLite, feed prezzi Binance e supporto OCO/trailing.

## Componenti principali
- `telegram_bot.py`: UI Telegram, parsing comandi, wizard, dispatch post-fill action.
- `core.py`: manager ordini, trigger/action, poller e coda esecuzione.
- `price_feeds.py`: feed mock e feed Binance su candele chiuse.
- `storage.py`: persistence SQLite, stato ordini, archivio mensile.

## Liquidazione BTC
- Alert visivo BTC: comando `/a` e soglia separata solo informativa.
- Liquidazione automatica BTC: comando `/ad`, trigger su caduta, default runtime 0.5%.
- La liquidazione colpisce solo ordini sell con flag persistito `btc_alert_liquidate`.
- La soglia viene letta da `bot_settings` con fallback env `BTC_LIQUIDATION_DROP_PERCENT`.

## Flusso runtime
1. `build_bot_from_env()` legge env e costruisce il bot.
2. `run()` avvia poller e applicazione Telegram.
3. Tick periodico valuta ordini con scheduling TF (`next_eval_at`).
4. In caso di trigger, esecuzione su exchange + eventi + notifiche.
5. Se presente post-fill action, viene creato OCO figlio.
6. Nel tick runtime viene valutata anche la caduta BTC e, se supera la soglia, vengono liquidati gli ordini sell flaggati.

## Timeframe
Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
Allineamento boundary UTC.

## Rischi principali
- Rate limit/transient error Binance.
- Necessità di mantenere valutazione ordini sequenziale.
- Coerenza prezzo candle chiusa nel feed.

Fonti: `ARCHITECTURE.md`, `README.md`, `docs/HANDOFF.md`
