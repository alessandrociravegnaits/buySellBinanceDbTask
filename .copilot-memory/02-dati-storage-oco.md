# Dati, Storage, OCO

## Persistenza
Storage SQLite con schema inizializzato automaticamente all'avvio (`CREATE TABLE IF NOT EXISTS`).

## Bot settings
- La tabella `bot_settings` contiene impostazioni runtime persistite come `default_tf_minutes`, `timeframe_seconds`, `echo_enabled`, `alert_enabled`, `alert_percent` e `btc_liquidation_drop_percent`.
- `btc_liquidation_drop_percent` viene usata per la soglia BTC di liquidazione automatica.

## Entita principali
- Ordini base: simple, function, trailing.
- OCO: `order_oco` (testata) + `order_oco_leg` (legs).
- Eventi: log audit di esecuzioni/fallimenti/transizioni.

## Flag BTC liquidation
- Gli ordini possono avere `btc_alert_liquidate` salvato nella tabella `orders`.
- Il flag viene caricato al restore e propagato ai figli OCO/trailing quando creati dal runtime.

## Post-fill action
Configurazione JSON (`post_fill_action`) su ordini di ingresso, usata per creare OCO automatico al fill.
Modalita supportate:
- `fixed`
- `percent`
- `trailing`

## Logica OCO
- Per ogni leg viene creato un ordine core associato (`core_order_id`).
- Al fill di una leg: ordine OCO viene finalizzato e sibling cancellato (cancel-sibling).
- Le leg trailing possono essere collegate a ordini trailing runtime.

## Archiviazione
Routine mensile sposta ordini chiusi in `data/archive`.

Fonti: `ARCHITECTURE.md`, `progettoOCO.md`, `docs/HANDOFF.md`
