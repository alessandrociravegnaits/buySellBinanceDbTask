# Contesto recuperato per progetto: buySellBinanceDbTask

USARE QUESTO BLOCCO COME FONTE PRIMARIA: se ci sono conflitti, privilegiare le informazioni qui riportate.
Quando citi, indica la sorgente come: [Titolo] chunk N/M.

**Consigli rapidi per scegliere i chunk (best practice):**
- Default consigliato: 3–6 chunk — buon equilibrio tra contesto e rumore.
- Usa lo score: preferisci chunk con score simile al migliore; se i punteggi calano rapidamente, evita chunk successivi.
- Se hai un limite di token, calcola il budget e riduci i chunk per restare sotto il limite.
- Rimuovi chunk ridondanti (dedup) o applica una soglia di similarità per evitare ripetizioni.
- Strategia iterativa: inizia con pochi chunk, valuta la risposta e aumenta se necessario.

---
--- [1] 05-sessione-corrente.md (2026-04-11) | chunk 1/6 | score=1.2207
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

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
# - Rate lim

--- [2] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 5/28 | score=1.3480
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

rsistenza SQLite, feed prezzi Binance e supporto OCO/trailing.
# 
# ## Componenti principali
# - `telegram_bot.py`: UI Telegram, parsing comandi, wizard, dispatch post-fill action.
# - `core.py`: ma

--- [4] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 4/11 | score=1.5003
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

istenza SQLite, feed prezzi Binance e supporto OCO/trailing.
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
# 
# ## Timeframe
# Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
# Allineamento boundary UTC.
# 
# ## Rischi principali
# - Rate limit

--- [3

--- [3] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 4/28 | score=1.4177
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

-- [1] 01-architettura-runtime.md (2026-04-06) | chunk 1/1 | score=1.5833 ---
# # Architettura e Runtime
# 
# ## Scopo
# Trading rules engine controllato via Telegram, con persistenza SQLite, feed prezzi Binance e supporto OCO/trailing.
# 
# ## Componenti principali
# - `telegram_bot.py`: UI Telegram, parsing comandi, wizard, dispatch post-fill action.
# - `core.py`: manager ordini, trigger/action, poller e coda esecuzione.
# - `price_feeds.py`: feed mock e feed Binance su candele chiuse.
# - `storage.py`: persistence SQLite, stato ordini, arch

--- [2] 05-sessione-corrente.md (2026-04-06) | chunk 1/6 | score=1.2207
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

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
# - `core.py`: ma

--- [4] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 3/28 | score=1.4443
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

15806b18068cc69d0bab61

# Contesto recuperato per progetto: buySellBinanceDbTask

USARE QUESTO BLOCCO COME FONTE PRIMARIA: se ci sono conflitti, privilegiare le informazioni qui riportate.
Quando citi, indica la sorgente come: [Titolo] chunk N/M.

---
--- [1] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 1/5 | score=1.0568
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

[Contesto sessioni precedenti - progetto: buySellBinanceDbTask]

--- [1] 05-sessione-corrente.md (2026-04-06) | chunk 1/6 | score=1.2207 ---
# ==================================================================================
# [Contesto sessioni precedenti - progetto: buySellBinanceDbTask]
# 
# --- [1] 01-architettura-runtime.md (2026-04-06) | chunk 1/1 | score=1.5833 ---
# # Architettura e Runtime
# 
# ## Scopo
# Trading rules engine controllato via Telegram, con persistenza SQLite, feed p

--- [3] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 2/11 | score=1.4243
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

--- [1] 01-architettura-runtime.md (2026-04-06) | chunk 1/1 | score=1.5833 ---
# # Architettura e Runtime
# 
# ## Scopo
# Trading rules engine controllato via Telegram, con persistenza SQLite, feed pre

--- [5] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 8/28 | score=1.4518
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

core associato (`core_order_id`).
# - Al fill di una leg: ordine OCO viene finalizzato e sibling cancellato (cancel-sibling).
# - Le leg trailing

--- [7] 01-architettura-runtime.md (2026-04-06) | chunk 1/1 | score=1.5833
SOURCE_ID: 778f8617402fdd0d0db791c28961564d

# Architettura e Runtime

## Scopo
Trading rules engine controllato via Telegram, con persistenza SQLite, feed prezzi Binance e supporto OCO/trailing.

## Componenti principali
- `telegram_bot.py`: UI Telegram, parsing comandi, wizard, dispatch post-fill action.
- `core.py`: manager ordini, trigger/action, poller e coda esecuzione.
- `price_feeds.py`: feed mock e feed Binance su candele chiuse.
- `storage.py`: persistence SQLite, stato ordini, archivio mensile.

## Flusso runtime
1. `build_bot_from_env()` legge env e costruisce il bot.
2. `run()` avvia poller e applicazione Telegram.
3. Tick periodico valuta ordini con scheduling TF (`next_eval_at`).
4. In caso di trigger, esecuzione su exchange + eventi + notifiche.
5. Se presente post-fill action, viene creato OCO figlio.

## Timeframe
Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
Allineamento boundary UTC.

## Rischi principali
- Rate

--- [7] 99-inizioSes

--- [6] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 1/28 | score=1.5348
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

# Contesto recuperato per progetto: buySellBinanceDbTask

USARE QUESTO BLOCCO COME FONTE PRIMARIA: se ci sono conflitti, privilegiare le informazioni qui riportate.
Quando citi, indica la sorgente come: [Titolo] chunk N/M.

---
--- [1] 05-sessione-corrente.md (2026-04-06) | chunk 1/6 | score=1.2207
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

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
#

--- [7] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 14/28 | score=1.5685
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

.
# - `core.py`: man

--- [6] 05-sessione-corrente.md (2026-04-06) | chunk 2/6 | score=1.5762
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

e presente post-fill action, viene creato OCO figlio.
# 
# ## Timeframe
# Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
# Allineamento boundary UTC.
# 
# ## Rischi principali
# - Rate limit/transient error Binance.
# - Nec

--- [11] 02-dati-storage-oco.md (2026-04-06) | chunk 1/1 | score=1.6971
SOURCE_ID: 256f4518752ce96d17b3078a3424be16

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
- Le leg trailing possono essere coll

--- [8] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 24/28 | score=1.5770
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

CE_ID: 36cbc5916c15806b18068cc69d0bab61

ion.
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
# 
#

--- [21] 04-ai-handoff-migrazione.md (2026-04-06) | chunk 1/1 | score=1.8932
SOURCE_ID: 4412a24ea089b5cc173294724cf23f74

# AI Workflow, Handoff, Migrazione

## Obiettivo
Rendere trasferibile il contesto di lavoro tra sessioni/macchine senza perdere decisioni e stato.

## File guida
- `docs/ai/AI_HANDOFF_CURRENT.md`
- `docs/ai/AI_DECISIONS_LOG.md`
- `docs/ai/AI_MIGRATION_COMMAND.md`
- `docs/ai/AI_MIGRATION_PASS1_RUNBOOK.md`
- `docs/ai/AI_END_SESSION_CHECKLIST.md`
- `docs/ai/AI_BOOTSTRAP_PROMPT_TEMPLATE.md`

## Flusso sintetico
1. Prima di chiudere: test, aggiornamento handoff corrente, update decisi

--- [9] 05-sessione-corrente.md (2026-04-11) | chunk 2/6 | score=1.5811
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

e presente post-fill action, viene creato OCO figlio.
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
# - Le leg trailin

--- [10] 01-architettura-runtime.md (2026-04-11) | chunk 1/1 | score=1.5833
SOURCE_ID: 778f8617402fdd0d0db791c28961564d

# Architettura e Runtime

## Scopo
Trading rules engine controllato via Telegram, con persistenza SQLite, feed prezzi Binance e supporto OCO/trailing.

## Componenti principali
- `telegram_bot.py`: UI Telegram, parsing comandi, wizard, dispatch post-fill action.
- `core.py`: manager ordini, trigger/action, poller e coda esecuzione.
- `price_feeds.py`: feed mock e feed Binance su candele chiuse.
- `storage.py`: persistence SQLite, stato ordini, archivio mensile.

## Flusso runtime
1. `build_bot_from_env()` legge env e costruisce il bot.
2. `run()` avvia poller e applicazione Telegram.
3. Tick periodico valuta ordini con scheduling TF (`next_eval_at`).
4. In caso di trigger, esecuzione su exchange + eventi + notifiche.
5. Se presente post-fill action, viene creato OCO figlio.

## Timeframe
Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
Allineamento boundary UTC.

## Rischi principali
- Rate limit/transient error Binance.
- Necessità di mantenere valutazione ordini sequenziale.
- Coerenza prezzo candle chiusa nel feed.

Fonti: `ARCHITECTURE.md`, `README.md`, `docs/HANDOFF.md`

--- [11] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 12/28 | score=1.6085
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

controllato via Telegram, con persistenza SQLite, feed prezzi Binance e supporto OCO/trailing.

## Componenti principali
- `telegram_bot.py`: UI Telegram, parsing comandi, wizard, dispatch post-fill action.
- `core.py`: manager ordini, trigger/action, poller e coda esecuzione.
- `price_feeds.py`: feed mock e feed Binance su candele chiuse.
- `storage.py`: persistence SQLite, stato ordini, archivio mensile.

## Flusso runtime
1. `build_bot_from_env()` legge env e costruisce il bot.
2. `run()` avvia poller e applicazione Telegram.
3. Tick periodico valuta ordini con scheduling TF (`next_eval_at`).
4. In caso di trigger, esecuzione su exchange + eventi + notifiche.
5. Se presente post-fill action, viene creato OCO figlio.

## Timeframe
Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
Allineamento boundary UTC.

## Rischi principali
- Rate limit/transient error Binance.
- Necessità di mantenere valutazione ordini sequenziale.
- Coerenza prezzo candle chiusa nel feed.

Fonti: `ARCHITECTURE.md`, `README.md`, `docs/HANDOFF.md`

--- [10] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 7/11 | score=1.6064
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

Tick periodico valuta ordini

--- [12] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 15/28 | score=1.6704
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

- Per ogni leg viene creato un ordine core associato (`core_order_id`).
- Al fill di una leg: ordine OCO viene finalizzato e sibling cancellato (cancel-sibling).
- Le leg trailing possono essere collegate a ordini trailing runtime.

## Archiviazione
Routine mensile sposta ordini chiusi in `data/archive`.

Fonti: `ARCHITECTURE.md`, `progettoOCO.md`, `docs/HANDOFF.md`

--- [12] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 11/11 | score=1.7115
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

- `telegram_bot.py`: UI Telegram, parsing comandi, wizard, dispatch post-fill action.
- `core.py`: manager ordini, trigger/action, poller e coda esecuzione.
- `price_feeds.py`: feed mock e feed Binance su candele chiuse.
- `storage.py`: persistence SQLite, stato ordini, archivio mensile.

## Flusso runtime
1. `build_bot_from_env()` legge env e costruisce il bot.
2. `run()` avvia poller e applicazione Telegram.
3. Tick periodico valuta ordini con scheduling TF (`next_eval_at`).
4. In caso di trigger, esecuzione su exchange + eventi + notifiche.
5. Se presente post-fill action, viene creato OCO figlio.

## Timeframe
Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
Allineamento boundary U

--- [13] 02-dati-storage-oco.md (2026-04-11) | chunk 1/1 | score=1.6971
SOURCE_ID: 256f4518752ce96d17b3078a3424be16

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

--- [14] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 11/28 | score=1.7027
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

cs/HANDOFF.md`
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
# - Le leg trailing

--- [9] 01-architettura-runtime.md (2026-04-06) | chunk 1/1 | score=1.5833
SOURCE_ID: 778f8617402fdd0d0db791c28961564d

# Architettura e Runtime

## Scopo
Trading rules engine controllato via Telegram, con persistenza SQLite, feed prezzi Binance e supporto OCO/trailing.

## Componenti principali
- `telegram_bot.py`: UI Telegram, parsing comandi, wizard, dispatch post-fill

--- [15] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 2/28 | score=1.7169
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

`storage.py`: persistence SQLite, stato ordini, archivio mensile.
# 
# ## Flusso runtime
# 1. `build_bot_from_env()` legge env e costruisce il bot.
# 2. `run()` avvia poller e applicazione Telegram.
# 3. Tick periodico valuta ordini con scheduling TF (`next_eval_at`).
# 4. In caso di trigger, esecuzione su exchange + eventi + notifiche.
# 5. Se presente post-fill action, viene creato OCO figlio.
# 
# ## Timeframe
# Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
# Allineamento boundary UTC.
# 
# ## Rischi principali
# - Rate limit

--- [2] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 1/11 | score=1.3570
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

# Contesto recuperato per progetto: buySellBinanceDbTask

USARE QUESTO BLOCCO COME FONTE PRIMARIA: se ci sono conflitti, privilegiare le informazioni qui riportate.
Quando citi, indica la sorgente come: [Titolo] chunk N/M.

---
--- [1] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 1/6 | score=1.1936
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

# Contesto recuperato per progetto: buySellBinanceDbTask

USARE QUESTO BLOCCO COME FONTE PRIMARIA: se ci sono conflitti, privilegiare le informazioni qui riportate.
Quando citi

--- [16] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 23/28 | score=1.7221
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

rezzi Binance e supporto OCO/trailing.

## Componenti principali
- `telegram_bot.py`: UI Telegram, parsing comandi, wizard, dispatch post-fill action.
- `core.py`: manager ordini, trigger/action, poller e coda esecuzione.
- `price_feeds.py`: feed mock e feed Binanc

--- [20] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 6/11 | score=1.8754
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

: `order_oco` (testata) + `order_oco_leg` (legs).
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
# - Le leg trailing

--- [4] 01

--- [5] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 2/6 | score=1.5558
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

ion.
# - `core.py`: manager ordini, trigger/action, poller e coda esecuzione.
# - `price_feeds.py`: feed mock e feed Binance su candele chiuse.
# - `storage.py

--- [17] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 25/28 | score=1.7257
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

ION_PASS1_RUNBOOK.md`
- `docs/ai/AI_END_SESSION_CHECKLIST.md`
- `docs/ai/AI_BOOTSTRAP_PROMPT_TEMPLATE.md`

## Flusso sintetico
1. Prima di chiudere: test, aggiornamento handoff corrente, update decision log.
2. Passaggio macchina: clone, setup venv, env, test smoke.
3. Nuova sessione: leggere README + ARCHITECTURE + AI_HANDOFF_CURRENT.

## Rischi processo
- Handoff non aggiornato = perdita contesto.
- Decisioni non registrate = regressioni organizzative.
- Ambiente non allineato = test/run non riproducibili.

Fonti: `docs/ai/*.md`, `ISTRUZIONI_persistenza_contesto_cambio_macchina.md`

--- [22] 05-sessione-corrente.md (2026-04-06) | chunk 5/6 | score=1.8959
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

S_LOG.md`
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
- Impostare preferenza memoria per ria

--- [18] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 19/28 | score=1.7449
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

down

## Root
- `ARCHITECTURE.md`: architettura runtime, OCO post-fill, schema e flussi.
- `README.md`: setup, avvio, comandi base.
- `progettoOCO.md`: specifica OCO e post_fill_action.
- `python_telegram_bot_summary.md`: note libreria telegram bot.
- `ISTRUZIONI_persistenza_contesto_cambio_macchina.md`: handoff tra macchine.
- `PROMPTdiRineallineamento.md`: prompt di riallineamento contesto.

## Docs
- `docs/HANDOFF.md`: runbook e stato passaggio consegne.

## Docs AI
- `docs/ai/AI_HANDOFF_CURRENT.md`
- `docs/ai/AI_DECISIONS_LOG.md`
- `docs/ai/AI_MIGRATION_COMMAND.md`
- `docs/ai/AI_MIGRATION_PASS1_RUNBOOK.md`
- `docs/ai/AI_END_SESSION_CHECKLIST.md`
- `docs/ai/AI_BOOTSTRAP_PROMPT_TEMPLATE.md`
- `docs/ai/AI_HANDOFF_TEMPLATE.md`
- `docs/ai/AI_PASS1_LAST_RUN.md`

Aggiornato: 2026-04-06

--- [17] 03-operazioni-run.md (2026-04-06) | chunk 1/1 | score=1.8045
SOURCE_ID: 59f896109453534dc21b092b60b2576e

# Operazioni, Avvio, Test

## Setup locale
```powershell
python -m venv venv
. .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Variabili env principali
- `BOT_TOKEN`
- `AUTHORIZED_CHAT_ID`
- `BINANCE_API_KEY`
- `BINANCE_SECRET_KEY`
- `BOT_DB_PATH`

## Avvio
```powershel

--- [19] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 17/28 | score=1.7492
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

in `.copilot-memory/`, in formato MD e suddivisi per argomento.
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
# - `docs/ai/AI_HAND

--- [15] README.md (2026-04-06) | chunk 1/1 | score=1.7924
SOURCE_ID: 6d931e6cfa16e29a8e8d9111edb922a5

# Copilot Memory (Project)

Questa cartella contiene riassunti di sessione e note operative in formato Markdown, organizzati per argomento.

## Convenzione
- Un file per ar

--- [20] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 16/28 | score=1.7526
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

r, esecuzione su exchange + eventi + notifiche.
5. Se presente post-fill action, viene creato OCO figlio.

## Timeframe
Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
Allineamento boundary UTC.

## Ris

--- [13] 05-sessione-corrente.md (2026-04-06) | chunk 6/6 | score=1.7319
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

lizzabile.
- Struttura `.copilot-memory/` creata e pronta per riassunti futuri.

## Follow-up suggeriti
- Eseguire test completi (`python -m pytest -q`).
- Commit delle modifiche con identita git corretta (`user.email`).
- Aggiornare questo file a fine prossime sessioni.

--- [14] 05-sessione-corrente.md (2026-04-06) | chunk 4/6 | score=1.7766
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

oni-run.md`: bootstrap, run, test, comandi utili.
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
# - `ARCHITECTURE.md

--- [21] 05-sessione-corrente.md (2026-04-11) | chunk 4/6 | score=1.7632
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

zioni-run.md`: bootstrap, run, test, comandi utili.
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
# - `docs/ai/AI_HA

--- [22] 00-fonti-md.md (2026-04-11) | chunk 1/1 | score=1.7782
SOURCE_ID: 351e83fe7a0f6c5ca9b181a3b50ffd0b

# Inventario Fonti Markdown

## Root
- `ARCHITECTURE.md`: architettura runtime, OCO post-fill, schema e flussi.
- `README.md`: setup, avvio, comandi base.
- `.copilot-memory/06-ordinepulito-acquistopulito.md`: riassunto tematico su ordinepulito/acquistopulito.
- `progettoOCO.md`: specifica OCO e post_fill_action.
- `python_telegram_bot_summary.md`: note libreria telegram bot.
- `ISTRUZIONI_persistenza_contesto_cambio_macchina.md`: handoff tra macchine.
- `PROMPTdiRineallineamento.md`: prompt di riallineamento contesto.

## Docs
- `docs/HANDOFF.md`: runbook e stato passaggio consegne.

## Docs AI
- `docs/ai/AI_HANDOFF_CURRENT.md`
- `docs/ai/AI_DECISIONS_LOG.md`
- `docs/ai/AI_MIGRATION_COMMAND.md`
- `docs/ai/AI_MIGRATION_PASS1_RUNBOOK.md`
- `docs/ai/AI_END_SESSION_CHECKLIST.md`
- `docs/ai/AI_BOOTSTRAP_PROMPT_TEMPLATE.md`
- `docs/ai/AI_HANDOFF_TEMPLATE.md`
- `docs/ai/AI_PASS1_LAST_RUN.md`

Aggiornato: 2026-04-11

--- [23] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 20/28 | score=1.7821
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

pts\Activate.ps1
pip install -r requirements.txt
```

## Variabili env principali
- `BOT_TOKEN`
- `AUTHORIZED_CHAT_ID`
- `BINANCE_API_KEY`
- `BINANCE_SECRET_KEY`
- `BOT_DB_PATH`

## Avvio
```powershell
python main.py
```

## Test
```powershell
python -m pytest -q
```

## Nota Windows PowerShell
Se l'attivazione `Activate.ps1` e bloccata da execution policy:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
. .\venv\Scripts\Activate.ps1
```

## Terminale Bash classico
- Git Bash: `"C:\Program Files\Git\bin\bash.exe"`
- WSL Bash: `wsl -e bash`

Fonti: `README.md`, `docs/HANDOFF.md`

--- [18] 05-sessione-corrente.md (2026-04-06) | chunk 3/6 | score=1.8075
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

## Logica OCO
# - Per ogni leg viene creato un ordine core associato (`core_order_id`).
# - Al fill di una leg: ordine OCO viene finalizzato e sibling cancellato (cancel-sibling).
# - Le leg trailing possono essere collegate a ordini trailing runtime.
# 
# ## Archiviazione
# Routine mensile sposta ordini chiusi in `data/archive`.
# 
# Fonti: `ARCHITECTURE.md`, `progettoOCO.md`, `docs/HANDOFF.md`
# 
# --- [3] README.md (2026-04-06) | chunk 1/1 | score=1.7924 --

--- [24] 05-sessione-corrente.md (2026-04-11) | chunk 6/6 | score=1.7893
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

tilizzabile.
- Struttura `.copilot-memory/` creata e pronta per riassunti futuri.

## Follow-up suggeriti
- Eseguire test completi (`python -m pytest -q`).
- Commit delle modifiche con identita git corretta (`user.email`).
- Aggiornare questo file a fine prossime sessioni.

--- [25] README.md (2026-04-11) | chunk 1/1 | score=1.7924
SOURCE_ID: 6d931e6cfa16e29a8e8d9111edb922a5

# Copilot Memory (Project)

Questa cartella contiene riassunti di sessione e note operative in formato Markdown, organizzati per argomento.

## Convenzione
- Un file per argomento.
- Contenuto sintetico, operativo, aggiornabile.
- Fonti sempre riportate nel file `00-fonti-md.md`.

## File correnti
- `00-fonti-md.md`: inventario dei file Markdown del progetto.
- `01-architettura-runtime.md`: panoramica componenti e ciclo runtime.
- `02-dati-storage-oco.md`: modello dati, OCO, persistenza.
- `03-operazioni-run.md`: bootstrap, run, test, comandi utili.
- `04-ai-handoff-migrazione.md`: processo AI/handoff e passaggio macchina.
- `05-sessione-corrente.md`: riassunto attività recenti.
- `06-ordinepulito-acquistopulito.md`: configurazione globale clean-entry e gating buy/OCO.

## Nota preferenza utente
I riassunti di sessione vanno sempre salvati qui in `.copilot-memory/`, in formato MD e suddivisi per argomento.

--- [26] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 22/28 | score=1.7969
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

0/11 | score=1.8360
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

i + notifiche.
5. Se presente post-fill action, viene creato OCO figlio.

## Timeframe
Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
Allineamento boundary UTC.

## Rischi principali
- Rate limit/transient error Binance.
- Necessità di mantenere valutazione ordini sequenziale.
- Coerenza prezzo candle chiusa nel feed.

Fonti: `ARCHITECTURE.md`, `README.md`, `docs/HANDOFF.md`

--- [8] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 5/6 | score=1.6353
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

CO
# - Per ogni leg viene creato un ordine core associato (`core_order_id`).
# - Al fill di una leg: ordine OCO viene finalizzato e sibling cancellato (cancel-sibling).
# - Le leg trailing

--- [4] 01-architettura-runtime.md (2026-04-06) | chunk 1/1 | score=1.5833
SOURCE_ID: 778f8617402fdd0d0db791c28961564d

# Architettura e Runtime

## Scopo
Trading rules engine controllato via Telegram, con persistenza SQLite, feed prezzi Binance e supporto OCO/trailing.

## Componenti principali
- `telegram_bot.py`: UI Telegram, parsing comandi, wizard, dispatch post-fill action.
- `core.py`: manager ordini, trigger/action, poll

--- [27] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 18/28 | score=1.8003
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

6cfa16e29a8e8d9111edb922a5

# Copilot Memory (Project)

Questa cartella contiene riassunti di sessione e note operative in formato Markdown, organizzati per argomento.

## Convenzione
- Un file per argomento.
- Contenuto sintetico, operativo, aggiornabile.
- Fonti sempre riportate nel file `00-fonti-md.md`.

## File correnti
- `00-fonti-md.md`: inventario dei file Markdown del progetto.
- `01-architettura-runtime.md`: panoramica componenti e ciclo runtime.
- `02-dati-storage-oco.md`: modello dati, OCO, persistenza.
- `03-operazioni-run.md`: bootstrap, run, test, comandi utili.
- `04-ai-handoff-migrazione.md`: processo AI/handoff e passaggio macchina.
- `05-sessione-corrente.md`: riassunto attività recenti.

## Nota preferenza utente
Da questa sessione in poi, i riassunti verranno salvati qui in `.copilot-memory/`, in formato MD e suddivisi per argomento.

--- [16] 00-fonti-md.md (2026-04-06) | chunk 1/1 | score=1.7943
SOURCE_ID: 351e83fe7a0f6c5ca9b181a3b50ffd0b

# Inventario Fonti Markdown

## Root
- `ARCHITECTURE.md`: architettura runtime, OCO post-fill, schema e flussi.
- `README.md`: setup, avvio, comandi base.
- `progettoOCO.md`: specifica OCO e post_fill_action.
- `python_tele

--- [28] 05-sessione-corrente.md (2026-04-11) | chunk 3/6 | score=1.8011
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

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
# ## Nota

--- [29] 03-operazioni-run.md (2026-04-11) | chunk 1/1 | score=1.8045
SOURCE_ID: 59f896109453534dc21b092b60b2576e

# Operazioni, Avvio, Test

## Setup locale
```powershell
python -m venv venv
. .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Variabili env principali
- `BOT_TOKEN`
- `AUTHORIZED_CHAT_ID`
- `BINANCE_API_KEY`
- `BINANCE_SECRET_KEY`
- `BOT_DB_PATH`

## Avvio
```powershell
python main.py
```

## Test
```powershell
python -m pytest -q
```

## Nota Windows PowerShell
Se l'attivazione `Activate.ps1` e bloccata da execution policy:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
. .\venv\Scripts\Activate.ps1
```

## Terminale Bash classico
- Git Bash: `"C:\Program Files\Git\bin\bash.exe"`
- WSL Bash: `wsl -e bash`

Fonti: `README.md`, `docs/HANDOFF.md`

--- [30] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 7/28 | score=1.8101
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

nce SQLite, stato ordini, archivio mensile.
# 
# ## Flusso runtime
# 1. `build_bot_from_env()` legge env e costruisce il bot.
# 2. `run()` avvia poller e applicazione Telegram.
# 3. Tick periodico valuta ordini con scheduling TF (`next_eval_at`).
# 4. In caso di trigger, esecuzione su exchange + eventi + notifiche.
# 5. Se presente post-fill action, viene creato OCO figlio.
# 
# ## Timeframe
# Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
# Allineamento boundary UTC.
# 
# ## Rischi principali
# - Rate limit

--- [3] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 3/6 | score=1.5145
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

ersistenza SQLite, feed prezzi Binance e supporto OCO/trailing.
# 
# ## Componenti principali
# - `telegram_bot.py`: UI Telegram, parsing comandi, wizard, dispatch post-fill action.
# - `core.py`: manage

--- [6] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 9/11 | score=1.5224
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

ene creato un ordine core associato (`core_order_id`).
# - Al fill di una leg: ordine OCO viene finalizzato e sibling cancellato (cancel-sibling).
# - Le leg trailing

--- [7] 01-architettura-runtime.md (2026-04-06) | chu

--- [31] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 13/28 | score=1.8145
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

ITECTURE.md`, `README.md`, `docs/HANDOFF.md`

--- [10] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 7/11 | score=1.6064
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

Tick periodico valuta ordini con scheduling TF (`next_eval_at`).
# 4. In caso di trigger, esecuzione su exchange + eventi + notifiche.
# 5. Se presente post-fill action, viene creato OCO figlio.
# 
#

--- [2] 05-sessione-corrente.md (2026-04-06) | chunk 1/6 | score=1.2207
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

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
# - `core.py`: man

--- [6] 05-sessione-corrente.md (2026-04-06) | chunk 2/6 | score=1.5762
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

e presente post-fill action, viene creato OCO figlio.
# 
# ##

--- [32] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 21/28 | score=1.8221
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

iviazione
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
# ## Nota p

--- [19] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 10/11 | score=1.8360
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

i + notifiche.
5. Se presente post-fill action, viene creato OCO figlio.

## Timeframe
Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440

--- [33] 06-ordinepulito-acquistopulito.md (2026-04-11) | chunk 1/2 | score=1.8371
SOURCE_ID: 7f5dd36c17dd5c16f765f4152af5d3ef

# Ordinepulito / acquistopulito

## Obiettivo
Centralizzare la logica di ingresso pulito per gli ordini buy, mantenendo il comportamento legacy invariato quando il flag e la config globale non sono attivi.

## Cosa è stato fatto
- Aggiunta la classe `TechnicalIndicators` in `indicators.py` con RSI, ATR, ADX, OBV, SMA, EMA, volume MA e ATR stop.
- Persistenza del flag `acquistopulito` su ordini simple, function, trailing buy e OCO buy in `storage.py`.
- Propagazione del flag nel bot Telegram, nei wizard guidati e nei comandi slash.
- Gating runtime: gli ordini buy con `acquistopulito=true` passano prima da una valutazione indicatori; se non superano i criteri, vengono rimessi in attesa al boundary successivo.
- Supporto esteso anche a OCO buy, con blocco e riarmo della leg quando la verifica clean-entry fallisce.

## Config globale setPulito
- Introduzione di una config globale per i filtri clean-entry.
- Modalità supportate:
  - `Automatico`: preset `Conservativo`, `Bilanciato`, `Aggressivo`.
  - `Manuale`: modifica puntuale di RSI minimo, ADX minimo, numero minimo di check e toggle dei filtri trend/volume/prezzo sopra EMA.
- Comando legacy `/setpulito` e percorso GUI in `Impostazi

--- [34] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 26/28 | score=1.8679
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

e Corrente - 2026-04-06

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
- Commit delle modifiche con identita git corr

--- [23] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 5/11 | score=1.9530
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

t-fill action, viene creato OCO figlio.
# 
# ## Timeframe
# Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
# Allineamento boundary UTC.
# 
# ## Rischi p

--- [35] 04-ai-handoff-migrazione.md (2026-04-11) | chunk 1/1 | score=1.8932
SOURCE_ID: 4412a24ea089b5cc173294724cf23f74

# AI Workflow, Handoff, Migrazione

## Obiettivo
Rendere trasferibile il contesto di lavoro tra sessioni/macchine senza perdere decisioni e stato.

## File guida
- `docs/ai/AI_HANDOFF_CURRENT.md`
- `docs/ai/AI_DECISIONS_LOG.md`
- `docs/ai/AI_MIGRATION_COMMAND.md`
- `docs/ai/AI_MIGRATION_PASS1_RUNBOOK.md`
- `docs/ai/AI_END_SESSION_CHECKLIST.md`
- `docs/ai/AI_BOOTSTRAP_PROMPT_TEMPLATE.md`

## Flusso sintetico
1. Prima di chiudere: test, aggiornamento handoff corrente, update decision log.
2. Passaggio macchina: clone, setup venv, env, test smoke.
3. Nuova sessione: leggere README + ARCHITECTURE + AI_HANDOFF_CURRENT.

## Rischi processo
- Handoff non aggiornato = perdita contesto.
- Decisioni non registrate = regressioni organizzative.
- Ambiente non allineato = test/run non riproducibili.

Fonti: `docs/ai/*.md`, `ISTRUZIONI_persistenza_contesto_cambio_macchina.md`

--- [36] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 27/28 | score=1.9026
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

ID: 36cbc5916c15806b18068cc69d0bab61

t-fill action, viene creato OCO figlio.
# 
# ## Timeframe
# Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
# Allineamento boundary UTC.
# 
# ## Rischi principali
# - Rate limit/transient

--- [4] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 4/6 | score=1.5509
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

post-fill action, viene creato OCO figlio.
# 
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
# Configurazione JSON (`pos

--- [37] 05-sessione-corrente.md (2026-04-11) | chunk 5/6 | score=1.9060
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

ONS_LOG.md`
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
- Commit delle modifiche con identita git co

--- [38] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 10/28 | score=1.9348
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

g` (legs).
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
# - Le leg trailing

--- [7] 01-architettura-runtime.

--- [8] 05-sessione-corrente.md (2026-04-06) | chunk 2/6 | score=1.5762
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

e presente post-fill action, viene creato OCO figlio.
# 
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
# Storage SQLite con schema inizializzato automaticamente all'

--- [39] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 9/28 | score=1.9365
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

presente post-fill action, viene creato OCO figlio.

## Timeframe
Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
Allineamento boundary UTC.

## Rischi principali
- Rate

--- [7] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 8/11 | score=1.5688
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

e creato OCO figlio.
# 
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
# Configurazione JSON (`post_fill_action`) su ordini di ingresso, usata per creare OCO automatico al fil

--- [40] 06-ordinepulito-acquistopulito.md (2026-04-11) | chunk 2/2 | score=1.9490
SOURCE_ID: 7f5dd36c17dd5c16f765f4152af5d3ef

ssivo`.
  - `Manuale`: modifica puntuale di RSI minimo, ADX minimo, numero minimo di check e toggle dei filtri trend/volume/prezzo sopra EMA.
- Comando legacy `/setpulito` e percorso GUI in `Impostazioni -> setPulito`.
- I valori vengono salvati in `bot_settings` e ricaricati all’avvio.

## Default e compatibilità
- Se non esiste configurazione salvata, il bot parte con il preset `Bilanciato`.
- Il comportamento buy legacy resta identico quando `acquistopulito` è falso.
- La configurazione è globale, non per singolo ordine.

## Verifica
- Aggiunti test per persistenza flag, parsing comandi, gating runtime e preset/override di `setPulito`.
- Suite completa verificata con successo.

--- [41] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 6/28 | score=2.0036
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

te post-fill action, viene creato OCO figlio.
# 
# ## Timeframe
# Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
# Allineamento boundary UTC.
# 
# ## Rischi principali
# - Rate limit

--- [3] 05-sessione-corrente.md (2026-04-06) | chunk 2/6 | score=1.5762
SOURCE_ID: c5485500fcf5aef6495efca7bdfecba2

e presente post-fill action, viene creato OCO figlio.
# 
# ## Timeframe
# Valori ammessi: 1, 5, 15, 30, 60, 120, 240, 1440 minuti.
# Allineamento boundary UTC.
# 
# ## Rischi principali
# - Rate limit/transient

--

--- [5] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 3/11 | score=1.5097
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

persistenza SQLite, feed prezzi Binance e supporto OCO/trailing.
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
# 3. Tick periodico val

--- [42] 99-inizioSessioneVettoriale.md (2026-04-06) | chunk 28/28 | score=2.0043
SOURCE_ID: 36cbc5916c15806b18068cc69d0bab61

e: simple, function, trailing.
# - OCO: `order_oco` (testata) + `order_oco_leg` (legs).
# - Eventi: log audit di esecuzioni/fallimenti/transizioni.
# 
# ## Post-fill action
# Configurazione JSON (`post_fill_action`) su ordini di ingresso,