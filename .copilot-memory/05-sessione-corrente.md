# ==================================================================================
# [Contesto sessioni precedenti - progetto: buySellBinanceDbTask]
# 
# --- [1] 01-architettura-runtime.md (2026-04-06) | chunk 1/1 | score=1.5833 ---
# # Architettura e Runtime
# 
# ## Scopo
# Trading rules engine controllato via Telegram, con persistenza SQLite, feed prezzi Binance e supporto OCO/trailing.
# 
# ## Componenti principali
# - `telegram_bot.py`: UI Telegram, parsing comandi, wizard, dispatch post-fill action.
# - `core.py`: manager ordini, trigger/action, poller e coda esecuzione.
# - `price_feeds.py`: feed mock e feed Binance su candele chiuse.
# - `storage.py`: persistence SQLite, stato ordini, archivio mensile.
# 
# ## Flusso runtime
# 1. `build_bot_from_env()` legge env e costruisce il bot.
# 2. `run()` avvia poller e applicazione Telegram.
# 3. Tick periodico valuta ordini con scheduling TF (`next_eval_at`).
# 4. In caso di trigger, esecuzione su exchange + eventi + notifiche.
# 5. Se presente post-fill action, viene creato OCO figlio.
# 6.
# ## Timeframe
# Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
# Allineamento boundary UTC.
# 
# ## Rischi principali
# - Rate limit/transient error Binance.
# - Necessità di mantenere valutazione ordini sequenziale.
# - Coerenza prezzo candle chiusa nel feed.
# 
# Fonti: `ARCHITECTURE.md`, `README.md`, `docs/HANDOFF.md`
# 
# --- [2] 02-dati-storage-oco.md (2026-04-06) | chunk 1/1 | score=1.6971 ---
# # Dati, Storage, OCO
# 
# ## Persistenza
# Storage SQLite con schema inizializzato automaticamente all'avvio (`CREATE TABLE IF NOT EXISTS`).
# ## Entita principali
# - Ordini base: simple, function, trailing.
# - OCO: `order_oco` (testata) + `order_oco_leg` (legs).
# - Eventi: log audit di esecuzioni/fallimenti/transizioni.
# 
# ## Post-fill action
# Configurazione JSON (`post_fill_action`) su ordini di ingresso, usata per creare OCO automatico al fill.
# Modalita supportate:
# - `fixed`
# - `percent`
# - `trailing`
# 
# ## Logica OCO
# - Per ogni leg viene creato un ordine core associato (`core_order_id`).
# - Al fill di una leg: ordine OCO viene finalizzato e sibling cancellato (cancel-sibling).
# - Le leg trailing possono essere collegate a ordini trailing runtime.
# 
# ## Archiviazione
# Routine mensile sposta ordini chiusi in `data/archive`.
# 
# Fonti: `ARCHITECTURE.md`, `progettoOCO.md`, `docs/HANDOFF.md`
# 
# --- [3] README.md (2026-04-06) | chunk 1/1 | score=1.7924 ---
# # Copilot Memory (Project)
# 
# Questa cartella contiene riassunti di sessione e note operative in formato Markdown, organizzati per argomento.
# 
# ## Convenzione
# - Un file per argomento.
# - Contenuto sintetico, operativo, aggiornabile.
# - Fonti sempre riportate nel file `00-fonti-md.md`.
# 
# ## File correnti
# - `00-fonti-md.md`: inventario dei file Markdown del progetto.
# - `01-architettura-runtime.md`: panoramica componenti e ciclo runtime.
# - `02-dati-storage-oco.md`: modello dati, OCO, persistenza.
# - `03-operazioni-run.md`: bootstrap, run, test, comandi utili.
# - `04-ai-handoff-migrazione.md`: processo AI/handoff e passaggio macchina.
# - `05-sessione-corrente.md`: riassunto attività recenti.
# 
# ## Nota preferenza utente
# Da questa sessione in poi, i riassunti verranno salvati qui in `.copilot-memory/`, in formato MD e suddivisi per argomento.
# 
# --- [4] 00-fonti-md.md (2026-04-06) | chunk 1/1 | score=1.7943 ---
# # Inventario Fonti Markdown
# 
# ## Root
# - `ARCHITECTURE.md`: architettura runtime, OCO post-fill, schema e flussi.
# - `README.md`: setup, avvio, comandi base.
# - `progettoOCO.md`: specifica OCO e post_fill_action.
# - `python_telegram_bot_summary.md`: note libreria telegram bot.
# - `ISTRUZIONI_persistenza_contesto_cambio_macchina.md`: handoff tra macchine.
# - `PROMPTdiRineallineamento.md`: prompt di riallineamento contesto.
# 
# ## Docs
# - `docs/HANDOFF.md`: runbook e stato passaggio consegne.
# 
# ## Docs AI
# - `docs/ai/AI_HANDOFF_CURRENT.md`
# - `docs/ai/AI_DECISIONS_LOG.md`
# - `docs/ai/AI_MIGRATION_COMMAND.md`
# - `docs/ai/AI_MIGRATION_PASS1_RUNBOOK.md`
# - `docs/ai/AI_END_SESSION_CHECKLIST.md`
# - `docs/ai/AI_BOOTSTRAP_PROMPT_TEMPLATE.md`
# - `docs/ai/AI_HANDOFF_TEMPLATE.md`
# - `docs/ai/AI_PASS1_LAST_RUN.md`
# 
# Aggiornato: 2026-04-06

# Sessione Corrente - 2026-04-06

## Obiettivo sessione
- Verificare controllo accesso tramite `AUTHORIZED_CHAT_ID`.
- Sistemare uso ambiente Python (`venv`) e terminale.
- Impostare preferenza memoria per riassunti per argomento.

## Attivita svolte
- Controllato `.gitignore` e confermato esclusione `.env`.
- Aggiornato `telegram_bot.py` su flusso autorizzazione/cattura chat e bootstrap env.
- Eseguiti test mirati via `venv\\Scripts\\python.exe`.
- Risolto problema activation PowerShell con policy process-scope.
- Impostato workspace settings con default terminale Bash + `python.terminal.useEnvFile`.

## Esito
- Bot configurato per usare `AUTHORIZED_CHAT_ID` in avvio da env.
- Ambiente `venv` verificato e utilizzabile.
- Struttura `.copilot-memory/` creata e pronta per riassunti futuri.

## Follow-up suggeriti
- Eseguire test completi (`python -m pytest -q`).
- Commit delle modifiche con identita git corretta (`user.email`).
- Aggiornare questo file a fine prossime sessioni.

## Sessione 2026-04-08 - BTC liquidation default e storage

### Obiettivo
- Chiarire dove viene salvata la soglia di caduta BTC e aggiornare il default runtime a 0.5%.

### Decisioni e implementazione
- Il valore `btc_liquidation_drop_percent` viene salvato in `bot_settings` dentro il DB SQLite.
- Non e' stata creata una nuova tabella: si usa la tabella esistente `bot_settings` con chiave `btc_liquidation_drop_percent`.
- Il default runtime e' stato cambiato da `2.0` a `0.5` in `telegram_bot.py`.
- L'esempio operativo in `README.md` e' stato aggiornato da `/ad 2.0` a `/ad 0.5`.

### Comportamento risultante
- Se la soglia non e' presente in DB, il bot usa `BTC_LIQUIDATION_DROP_PERCENT` da env con fallback `0.5`.
- La liquidazione BTC resta separata dall'alert visivo `/a`.
- La soglia e' visibile nei comandi di stato come valore corrente del bot.

### Verifiche
- Test mirati su storage e integrazione OCO/liquidazione eseguiti con esito positivo.
- Nessun errore sintattico trovato dopo la modifica del fallback runtime.
 
