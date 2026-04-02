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

## Guida rapida per neofiti (Windows)

1) Creare e attivare un ambiente virtuale

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Creare un file `.env` nella root del progetto con le variabili seguenti (non committare `.env`):

```
BOT_TOKEN=your_telegram_bot_token
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key
# opzionali
AUTHORIZED_CHAT_ID=123456789
BOT_DB_PATH=data/bot.sqlite3
```

3) Avviare l'app (consigliato tramite `main.py`):

```powershell
python main.py
```

Oppure per avviare solo il bot (sviluppo):

```powershell
python telegram_bot.py
```

4) Ottenere il proprio `AUTHORIZED_CHAT_ID` (opzionale):
- usa un bot come `@userinfobot` o manda `/start` al tuo bot e leggi l'id dai log del processo.

## Spiegazione del database

- File principale: `data/bot.sqlite3` (creato automaticamente all'avvio se mancante).
- Archivio mensile: `data/archive/archive_YYYY_MM.sqlite3` (la routine di archiviazione copia qui gli ordini chiusi di mesi passati).
- Se vuoi ricreare lo schema senza cancellare l'applicazione, puoi lanciare (con venv attivo):

```powershell
python -c "from storage import SQLiteStorage; SQLiteStorage('data/bot.sqlite3','data/archive')"
```

- Per cancellare completamente il DB e ricominciare (opzionale):

```powershell
Remove-Item -Path .\data\bot.sqlite3
```

- L'app usa `CREATE TABLE IF NOT EXISTS` quindi aggiunte future allo schema verranno applicate automaticamente al prossimo avvio.

## Uso delle chiavi API

- Telegram `BOT_TOKEN`: necessario per collegare il bot Telegram. Metti il token in `.env` come `BOT_TOKEN` o esportalo nell'ambiente. Non condividerlo.
- Binance `BINANCE_API_KEY` / `BINANCE_SECRET_KEY`: usate dal `Binance1mClosePriceFeed` per leggere le candlestick (e opzionalmente per eseguire ordini se aggiungi quella funzionalità). Metti le chiavi in `.env` o nelle variabili d'ambiente.

Buone pratiche:
- Non committare `.env` o i file `*.sqlite3` in Git.
- Per deployment usa secret manager o variabili d'ambiente del sistema.

## Note finali e dove guardare
- Interfaccia: `telegram_bot.py` (menu, wizard ordini, OCO, Info runtime).
- Motore: `core.py` (gestione ordini e poller).
- Storage: `storage.py` (persistence, archive, schema).

Se hai bisogno, posso aggiungere una sezione con esempi passo-passo per creare il primo ordine OCO via UI Telegram.

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

## Post-Fill Auto OCO (nuovo)

Disponibile sugli ordini di ingresso:
- `/b` (buy semplice)
- `/f` (function buy)
- `/B` (trailing buy)

Puoi configurarlo in 2 modi:
1. Tramite wizard guidato UI (senza scrivere token `oco:` a mano).
2. Tramite comando con token opzionale `oco:`.

Esempi comando:

```text
/b BTCUSDT < 67000 0.001 oco:tp=3%,sl=1.5%
/b BTCUSDT < 67000 0.001 oco:tp=72000,sl=65000
/b BTCUSDT < 67000 0.001 oco:tp=3%,sl=trail:1.5%
```

Formato supportato:
- `tp`: `%`, valore fisso, oppure `trail:x%`
- `sl`: `%`, valore fisso, oppure `trail:x%`

Le due gambe sono indipendenti: puoi scegliere liberamente il mode per ciascuna leg.

Comportamento:
- all'esecuzione del buy, il bot crea automaticamente un OCO figlio,
- ogni OCO figlio mantiene il riferimento al parent (`parent_order_id`),
- in caso `sl=trail:x%`, la leg SL usa il motore trailing esistente con linkage OCO->Trailing.

Visibilita runtime:
- `/o` mostra `post_fill_action`, `parent` OCO, dettagli leg trailing/core linkage.
- `/info` mostra il conteggio di trailing sell linked a OCO attivi.

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

