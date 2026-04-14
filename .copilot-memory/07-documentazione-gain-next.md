# Gain storico e sync `next`

## Obiettivo
Allineare la documentazione con le ultime modifiche implementate: visualizzazione del `gain%` nella cronologia ordini e aggiornamento coerente del campo `next` per i flussi schedulati, in particolare trailing sell.

## Cosa è stato implementato
- `storage.py` ricostruisce `entry_price` e `exit_price` dai fill registrati in `event_log` e calcola `gain_pct`.
- `telegram_bot.py` mostra nella cronologia ordini il `gain%` quando i dati sono disponibili.
- `telegram_bot.py` aggiorna `next_eval_at` anche per il trailing sell a ogni tick dovuto.
- `simple buy/sell` già seguivano la logica corretta di scheduling tramite `core.py` e la sync in memoria/DB.

## Verifiche svolte
- Aggiunta regressione per trailing sell: il `next` avanza e viene salvato nel DB.
- Aggiunta regressione per simple buy/sell: il `next` resta sincronizzato con il core engine.
- Suite completa eseguita con successo: `58 passed, 4 warnings`.

## Dove guardare nel codice
- `storage.py`: helper `get_order_gain_summary()` e lettura eventi storici.
- `telegram_bot.py`: `_cmd_history_orders`, `_eval_trailing_sell`, `_sync_simple_order_schedule`, `_mark_evaluated`.
- `core.py`: scheduling di base degli ordini nel motore runtime.

## Nota operativa
- Se in `event_log` non esistono fill con `price`, la cronologia mostrerà `N/A` per il gain.
- Per gli ordini attivi, la vista `next` si basa sul TF configurato e sugli aggiornamenti runtime/sync persistiti.

## Collegamenti utili
- `README.md`
- `docs/HANDOFF.md`
- `docs/ai/AI_HANDOFF_CURRENT.md`
- `docs/ai/AI_DECISIONS_LOG.md`