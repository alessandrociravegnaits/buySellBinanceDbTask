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

Per istruzioni di migrazione e handoff completo vedere: `docs/HANDOFF.md`

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
- `/t` `/a` `/ad` `/e` `/s` `/b` `/f` `/S` `/B` `/c ORDER_ID` oppure `/c a` `/o`

Nel menu `Impostazioni -> Cancella ordine` puoi ora toccare direttamente i bottoni sintetici `#id:pair:tipo` (es. `#42:BTCUSDT:buy`) senza digitare l'ID a mano.

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

## BTC Sell Drop Liquidation

La liquidazione automatica su BTC e separata dall'alert visivo (`/a`):

- `/a 0|1 [PERCENT]` resta un alert Telegram informativo.
- `/ad PERCENT` imposta la soglia percentuale di caduta BTC che attiva la liquidazione automatica.

Semantica trigger liquidazione:

- Il monitor BTC gira sempre nel job runtime.
- La liquidazione scatta solo su caduta, non su rialzo.
- Condizione: `variazione <= -PERCENT` rispetto al reference price del ciclo precedente.
- Finestra di valutazione: 60s (stessa cadenza del monitor alert).

Ambito ordini liquidati:

- Solo ordini con flag `btc_alert_liquidate=true`.
- Copertura: sell semplici, trailing sell e OCO sell (incluse leg/sibling cancellate prima del market sell finale).

Come impostare il flag ordine:

- Slash command: aggiungi `btc_alert=1` (equivalenti: `btc_alert`, `btc_liquidate`) ai comandi ordine.
- Wizard UI: dopo il timeframe viene chiesto se abilitare la liquidazione su caduta BTC per l'ordine corrente.

Esempi:

```text
/s ETHUSDT > 3000 0.25 tf=15 btc_alert=1
/S BNBUSDT 1.5 0.5 tf=15 btc_alert=1
/ad 0.5
```

Comportamento:
- all'esecuzione del buy, il bot crea automaticamente un OCO figlio,
- ogni OCO figlio mantiene il riferimento al parent (`parent_order_id`),
- in caso `sl=trail:x%`, la leg SL usa il motore trailing esistente con linkage OCO->Trailing.

Visibilita runtime:
- `/o` mostra `post_fill_action`, `parent` OCO, dettagli leg trailing/core linkage.
- `/info` mostra il conteggio di trailing sell linked a OCO attivi.

Nota: il comando `/info` ora mostra anche i valori correnti del bot (default TF, echo, alert, reference price e conteggi ordini attivi). Il comando `/c a` cancella tutti gli ordini attivi presenti nelle collezioni in memoria, inclusi gli OCO.

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

## Porting / Migrazione su altra macchina

Se vuoi spostare il progetto su un'altra macchina (oppure consegnarlo a un collega o a un'IA che non ha eseguito il lavoro), segui questi passi minimi per garantire che il nuovo ambiente abbia piena conoscenza del contesto e possa continuare lo sviluppo:

- Clona il repository nella nuova macchina.
- Crea e attiva un ambiente virtuale e installa le dipendenze:

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

- Crea un file `.env` nella root con almeno le seguenti variabili (NON committare `.env`):

```
BOT_TOKEN=your_telegram_bot_token
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key
AUTHORIZED_CHAT_ID=123456789  # opzionale
BOT_DB_PATH=data/bot.sqlite3   # opzionale
```

- Database:
	- Il motore applica `CREATE TABLE IF NOT EXISTS` all'avvio, quindi le nuove tabelle verranno create automaticamente al primo run.
	- Per preservare lo storico e lo stato runtime, copia `data/bot.sqlite3` dalla macchina sorgente nella stessa posizione sul nuovo host (o imposta `BOT_DB_PATH`).
	- Esempio copia file (PowerShell):

```powershell
Copy-Item -Path "C:\path\to\project\data\bot.sqlite3" -Destination "C:\path\to\new\project\data\bot.sqlite3"
```

- Test rapidi (consigliato): esegui la suite di test prima di avviare il bot:

```powershell
python -m pytest -q -s
```

- Avvio:

```powershell
python main.py
```

- Branch di handoff: per creare un branch di consegna usa `git checkout -b pass1-migrazione`, committa le modifiche locali e pushale su remote per aprire una PR.

- Punti di ingresso per continuare il lavoro:
	- `telegram_bot.py` — interfaccia, wizard e dispatcher `post_fill_action`.
	- `storage.py` — schema SQLite, metodi `save_oco_order`, `update_oco_leg_core_order_id`, `update_oco_leg_status`.
	- `core.py` — motore, mapping core_order_id ↔ `order_oco_leg`.
	- `tests/` — test di integrazione e storage (`test_oco_integration.py`, `test_oco_storage.py`).

Se preferisci, posso generare uno script di esportazione/import per `data/bot.sqlite3` e un `docs/HANDOFF.md` con checklist e comandi rapidi; dimmi se lo vuoi ora.

## Indicatori Tecnici (nuovo)

Il progetto include ora `indicators.py` con la classe `TechnicalIndicators`, pensata per essere richiamata dal bot nelle nuove regole operative.

Indicatori disponibili:
- `rsi(14)`
- `atr(14)`
- `adx(14)` con `plus_di` e `minus_di`
- `obv()`
- `volume_ma(20)`
- `sma(20)` / `ema(20)`
- `atr_stop()` per stop dinamici

Esempio rapido:

```python
import pandas as pd
from indicators import TechnicalIndicators

df = pd.DataFrame(
	{
		"timestamp": [...],
		"open": [...],
		"high": [...],
		"low": [...],
		"close": [...],
		"volume": [...],
	}
)

ti = TechnicalIndicators.from_ohlcv(df)
signals = ti.compute_default_set()
last = ti.latest_snapshot()

print(last["rsi_14"], last["adx_14"], last["volume_ma_20"])
```

Compatibilità MCP finance:
- puoi usare `TechnicalIndicators.from_mcp_price_history(payload)` passando una lista di record OHLCV o un dizionario con chiave `data`/`prices`/`ohlcv`.

