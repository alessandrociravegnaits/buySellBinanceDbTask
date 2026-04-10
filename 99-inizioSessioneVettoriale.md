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
--- [1] 05-sessione-corrente.md (2026-04-09) | chunk 1/7 | score=1.2207
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