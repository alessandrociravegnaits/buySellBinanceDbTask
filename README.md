# Trading Engine (prototype)

Motore ordini basato su:
- N ordini
- piu trigger per ordine
- una sola azione per ordine

## Price feed disponibili
- `MockPriceFeed`: feed manuale per test
- `Binance1mClosePriceFeed`: feed reale Binance (close candela 1m), ispirato a `lettura1mt` in `master.py`
 - `Binance1mClosePriceFeed`: feed reale Binance (close candela 1m), implementato in `price_feeds.py`

## Installazione dipendenze

```powershell
pip install -r requirements.txt
```

## Configurazione chiavi Binance
Puoi passare le chiavi nel costruttore oppure via env var:
- `BINANCE_API_KEY`
- `BINANCE_SECRET_KEY`

Esempio PowerShell:

```powershell
$env:BINANCE_API_KEY="your_api_key"
$env:BINANCE_SECRET_KEY="your_secret_key"
```

## Esecuzione demo locale (mock)

```powershell
python main.py
```

## Interfaccia Telegram

File principale: `telegram_bot.py` (launcher: `main.py`).

Storage:
- `data/bot.sqlite3` (operativo)
- `data/archive/archive_YYYY_MM.sqlite3` (archivio mensile)

Il database viene creato automaticamente all'avvio se mancante (`SQLiteStorage` esegue gli script `CREATE TABLE IF NOT EXISTS`).

Variabili ambiente richieste:
- `BOT_TOKEN`
- `BINANCE_API_KEY`
- `BINANCE_SECRET_KEY`

Variabili opzionali:
- `AUTHORIZED_CHAT_ID` (limita l'accesso)
- `BOT_DB_PATH` (default: `data/bot.sqlite3`)

Esempio PowerShell per avvio:

```powershell
$env:BOT_TOKEN="your_telegram_bot_token"
$env:BINANCE_API_KEY="your_api_key"
$env:BINANCE_SECRET_KEY="your_secret_key"
$env:AUTHORIZED_CHAT_ID="123456789"
python main.py
```

Comandi supportati (interfaccia Telegram):
- `/info` (mostra guida comandi e, nella sezione "Valori correnti", i runtime settings)
- `/t` `/a` `/e` `/s` `/b` `/f` `/S` `/B` `/c ORDER_ID` oppure `/c a` `/o`

Nota: il comando `/info` ora mostra anche i valori correnti del bot (default TF, echo, alert, reference price e conteggi ordini attivi). Il comando `/c a` cancella gli ordini presenti nelle collezioni in memoria (sell/buy/function/trailing) ma non include automaticamente gli OCO a meno che non venga esplicitamente aggiornato.

Timeframe ordini:
- Valori ammessi: `1,5,15,30,60,120,240,1440` (minuti)
- `/t MINUTI` imposta il default per i nuovi ordini
- Override per singolo ordine con `tf=MIN`, esempio:

```text
/s BTCUSDT < 65000 0.01 tf=15
```

Valutazione trigger:
- allineamento UTC strict su close candle
- restart dal prossimo boundary (no catch-up)

Pairhook (`@PAIRHOOK`):
- `watch` = simbolo usato per il trigger
- `exec` = simbolo di esecuzione (pairhook) se presente
- comandi: `/s`, `/b`, `/f`, `/S`

## Smoke test storage

```powershell
python storage_smoke_test.py
```

## Uso rapido feed Binance

```python
from core import build_engine
from price_feeds import Binance1mClosePriceFeed

feed = Binance1mClosePriceFeed(round_digits=8)
manager, poller = build_engine(symbols=["BTCUSDT"], price_feed=feed)
```

