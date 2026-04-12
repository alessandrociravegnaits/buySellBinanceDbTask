# Dati, Storage, OCO

## Persistenza
Storage SQLite con schema inizializzato automaticamente all'avvio (`CREATE TABLE IF NOT EXISTS`).

## Entita principali
- Ordini base: simple, function, trailing.
- OCO: `order_oco` (testata) + `order_oco_leg` (legs).
- Eventi: log audit di esecuzioni/fallimenti/transizioni.

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

## Aggiornamento 2026-04-12 - BTC Drop Protection

### Nuovo campo comune ordini
- Aggiunta colonna `orders.btc_alert_liquidate` (migrazione additiva).
- Campo propagato su salvataggio/caricamento ordini attivi e storico.
- Inclusa compatibilita' archivio mensile con nuovo attributo.

### Semantica side-aware
- Ordini SELL con `btc_alert_liquidate=true`: liquidazione market su drop BTC oltre soglia.
- Ordini BUY con `btc_alert_liquidate=true`: cancellazione preventiva su drop BTC oltre soglia.

### Config globale soglia
- Setting persistito: `btc_liquidation_drop_percent`.
- Gestito via comando runtime `/ad PERCENT` (`/ad 0` disabilita).
