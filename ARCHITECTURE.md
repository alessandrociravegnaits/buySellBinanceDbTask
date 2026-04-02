Ricevuto: creo un resoconto completo e puntuale sull'organizzazione dell'app.

## Aggiornamento Architetturale: Post-Fill Auto OCO

### Obiettivo
Consentire ad alcuni ordini di ingresso (`/b`, `/f`, `/B`) di innescare automaticamente la creazione di un ordine OCO al momento del fill.

### Modello Dati
- `order_simple.post_fill_action` (`TEXT`, JSON)
- `order_function.post_fill_action` (`TEXT`, JSON)
- `order_trailing.post_fill_action` (`TEXT`, JSON)
- `order_oco.parent_order_id` (`INTEGER`, riferimento logico ordine padre)
- `order_oco_leg.trail_percent` (`REAL`, usato per leg trailing)
- `order_trailing.oco_parent_order_id` / `order_trailing.oco_leg_index` (`INTEGER`, linkage runtime OCO<->Trailing)

### Flusso Runtime
1. Ordine ingresso viene eseguito su exchange.
2. Se `post_fill_action` e presente, dispatcher crea un OCO figlio (`type=oco`).
3. Leg TP: `limit` da `fixed` o `%`.
4. Leg SL:
  - `stop_limit` da `fixed` o `%`, oppure
  - `trailing` con riuso motore trailing esistente (`sl=trail:x%`).
5. Al fire di una leg OCO, il sibling viene cancellato (cancel-sibling) anche se il sibling e un trailing linked.

### Osservabilita
- Eventi principali: `post_fill_action_triggered`, `post_fill_action_failed`, `auto_oco_created`, `oco_leg_filled`, `oco_leg_cancelled`, `oco_trailing_leg_fired`.
- `/o` mostra post-fill action e linkage parent/legs.
- `/info` mostra conteggio trailing linked a OCO attivi.

### UX
La configurazione Auto OCO e disponibile anche via wizard guidato, senza obbligo di scrivere il token `oco:` manualmente.

Piano sintetico
- Raccogliere e descrivere i componenti principali del progetto (file, flussi, responsabilità).
- Documentare il modello dati (tabelle SQLite proposte) e come vengono persistiti gli ordini, i trigger, i runtime e lo storico.
- Descrivere l'event loop / poller e il suo ciclo di vita (avvio/chiusura) e come vengono valutati i timeframe (TF).
- Spiegare i concetti di pairhook e @pairhook e come influiscono sull'esecuzione.
- Fornire istruzioni operative: dove mettere dati sensibili, come avviare, dipendenze principali e suggerimenti di miglioramento.

Checklist (elementi che troverai nel file)
- [x] Panoramica componenti e responsabilità dei file
- [x] Flusso runtime: dalla ricezione comando Telegram fino all'esecuzione/archiviazione dell'ordine
- [x] Descrizione poller e job_queue: avvio una sola volta e stop a chiusura
- [x] Gestione TimeFrame (TF): valori consentiti, allineamento UTC strict, next_boundary logic
- [x] Proposta di schema SQLite (CREATE TABLE) con campi necessari
- [x] Pairhook: sintassi, semantica e DB impact
- [x] Dove mettere segreti e file da ignorare (gitignore)
- [x] Come avviare e note su dipendenze

Report dettagliato

1) Scopo dell'app e modello concettuale
L'app è un "trading rules engine" controllato via Telegram. Ogni ordine (order) è composto da:
- una o più condizioni di trigger (trigger) che osservano prezzi su un simbolo (watch symbol)
- una singola azione (action) che viene eseguita quando il trigger si attiva

Tipi di ordini implementati:
- simple orders (/s e /b): un singolo trigger (< o >) su un watch symbol che quando scatta esegue un action (sell o buy) su un simbolo di esecuzione (pairhook opzionale)
- function orders (/f): monitorano un crossing del trigger tra tick di timeframe (compra al trigger e poi crea un trailing sell)
- trailing orders (/S e /B): trailing sell / buy che si "armano" a seguito di condizioni e poi scattano quando la logica percentuale è soddisfatta

Ogni ordine ha uno stato (active, cancelled, filled) e campi di runtime (prev_price, armed, max_price, min_price, next_eval_at, last_eval_at).

2) File e responsabilità (mappa dei principali file)
- `telegram_bot.py` — interfaccia utente Telegram, parsing comandi, costruzione degli order-spec, interazione con storage e motore (manager + poller), job scheduling per tick e invio notifiche.
- `core.py` — (presunto) logica del motore: manager di ordini, definizione di Order/Trigger/Action, Poller che gestisce la valutazione sequenziale dei core orders (qui si integra la richiesta di single-thread polling). (Controllare `core.py` per dettagli di implementazione. È il cuore che riceve add_order, get_order, cancel_order.)
- `price_feeds.py` — implementazioni delle sorgenti prezzi (nel codice corrente si usa `Binance1mClosePriceFeed`). Qui vanno le integrazioni con API exchange (python-binance) e la logica di allineamento candle.
- `storage.py` — wrapper SQLite per persistere ordini, runtime e storico; fornisce next_order_id(), save_*_order(), update_order_status(), update_order_schedule(), append_event(), load_active_orders(), archive_closed_orders_by_month(), set/get settings.
- `spunto.py` — codice storico / di riferimento (algoritmi e corner cases storici). Usarlo per portare identica logica su /S e /B e per allineare TF di 4h ecc.
- `main.py` — runner: avvia il bot (attualmente era test; va modificato per avviare l'app e tenere attivo il bot polling).
- `data/` — contiene `bot.sqlite3`, `test_bot.sqlite3` e `archive/` per archiviazione mensile.

3) Flusso runtime (end-to-end)
- Avvio: `build_bot_from_env()` carica .env e crea TelegramTradingBot.
- Bot.run(): avvia il `poller` (.start()), monta i job di Telegram job_queue (tick e flush notifications) e quindi `app.run_polling()`.
- Ogni secondo il job `_job_tick` viene eseguito (telegram job queue): chiama `_eval_function_orders`, `_eval_trailing_sell`, `_eval_trailing_buy`, `_sync_simple_order_schedule`, `_eval_alert`, `_eval_echo` — questi controllano ordini che hanno `next_eval_at` scaduto e li valutano uno alla volta.
- Quando un ordine scatta, viene eseguita l'Action associata (es. _on_simple_fired) che aggiorna stato in DB, appende evento allo storico e invia notifica (metodo message queue).
- Archiviazione: periodicamente `_job_tick` richiama `archive_closed_orders_by_month()` ogni ora per spostare ordini chiusi nello storage di archivio (file mensili separati secondo la tua preferenza).

4) Poller: ciclo di vita e dove si posiziona
- Poller è un componente che osserva simboli e fornisce prezzi (e per i `simple orders` tiene next_eval_at/last_eval_at sincronizzati). Nell'implementazione corrente si chiama `self._poller` in `TelegramTradingBot` e viene avviato con `self._poller.start()` prima di avviare `app.run_polling()` e fermato in finally con `self._poller.stop()`.
- Risposta alla tua domanda: il poller si crea/avvia una volta all'avvio dell'app e si ferma una volta alla chiusura (shutdown). Questo è corretto e desiderabile: start all'inizio, stop alla fine.
- Il job_tick (telegram job queue) è il place dove vengono valutati tutti gli ordini "uno alla volta" in un singolo thread del processo (bisogna verificare che `poller` non avvii internamente altri thread; se sì, valutare sincronizzazione). L'obiettivo richiesto di avere un singolo thread che fa polling di tutti gli ordini uno alla volta è ottenuto se:
  - Il poller non parallellizza valutazioni
  - Il job_tick esegue le valutazioni sequenziali (come nel codice attuale)

5) TimeFrame (TF) — gestione e allineamento
- Valori consentiti: 1,5,15,30,60,120,240,1440 minuti. Sono memorizzati come numero intero di minuti in `tf_minutes`.
- Motivo importante: i trigger/operatori devono essere valutati solo alla chiusura della candle del TF (es. 15m candle chiude a HH:00,HH:15,HH:30,HH:45 UTC). L'implementazione corrente usa `_next_boundary_epoch(tf_minutes)` che calcola il prossimo timestamp di boundary con la formula:
  next = (now // (tf_seconds) + 1) * tf_seconds
  dove tf_seconds = tf_minutes * 60
- Allineamento Exchange (decisione presa): usare UTC strict sulle chiusure candle (es. 00:00, 00:05, 00:15...).
- Esempi specifici:
  - TF=240 (4h): le chiusure sono a 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC.
  - TF=1440 (1d): la chiusura è alle 00:00 UTC di ogni giorno.
- Nota: la logica `_next_boundary_epoch` è corretta se il riferimento è epoch UTC; assicurarsi che il server giri in UTC o usare time.time() (che è UTC basato) e non locale. L'approccio di "ripartire dal prossimo boundary" (come hai detto: "riparto dal prossimo boundary") è implementato.
- Per funzionare robustamente: il price feed deve restituire il prezzo di chiusura della candle TF richiesta (es. `get_price(symbol, tf_minutes)` deve restituire close price all'ultimo closed candle coerente con UTC strict). Vedi `price_feeds.py` e `spunto.py` per le regole storiche.

6) Pairhook (@pairhook)
- Sintassi: appendere `@PAIRHOOK` come token nell'istruzione (/s /b /f /S) es. `/s BTCUSDT > 60000 0.001 @ETHUSDT tf=15`.
- Significato: il pairhook è il simbolo su cui viene effettivamente eseguita l'azione (action). Il watch symbol resta quello su cui si valuta il trigger. Quando presente, `exec_symbol = hook_symbol` viene usato nelle notifiche e nelle chiamate di esecuzione (vedi `_exec_symbol`).
- DB: memorizzare `hook_symbol` nel record dell'ordine.
- Impatto: e' già previsto e applicato nelle parti del codice che hai allegato (telegram_bot.py). L'azione fisica (order execution) deve usare `exec_symbol`.

7) Schema SQLite proposto
Proposta concreta (semplificata) — adattare ai metodi già presenti in `storage.py`:

CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE simple_orders (
  order_id INTEGER PRIMARY KEY,
  chat_id INTEGER,
  side TEXT,
  symbol TEXT,
  op TEXT,
  trigger_value REAL,
  qty REAL,
  hook_symbol TEXT,
  core_order_id INTEGER,
  tf_minutes INTEGER,
  next_eval_at INTEGER,
  last_eval_at INTEGER,
  status TEXT,
  created_at INTEGER DEFAULT (strftime('%s','now'))
);

CREATE TABLE function_orders (
  order_id INTEGER PRIMARY KEY,
  chat_id INTEGER,
  symbol TEXT,
  op TEXT,
  trigger_value REAL,
  qty REAL,
  percent REAL,
  hook_symbol TEXT,
  bought INTEGER,
  prev_price REAL,
  tf_minutes INTEGER,
  next_eval_at INTEGER,
  last_eval_at INTEGER,
  status TEXT,
  created_at INTEGER DEFAULT (strftime('%s','now'))
);

CREATE TABLE trailing_orders (
  order_id INTEGER PRIMARY KEY,
  chat_id INTEGER,
  side TEXT,
  symbol TEXT,
  qty REAL,
  percent REAL,
  limit_price REAL,
  hook_symbol TEXT,
  armed INTEGER,
  max_price REAL,
  min_price REAL,
  arm_op TEXT,
  tf_minutes INTEGER,
  next_eval_at INTEGER,
  last_eval_at INTEGER,
  status TEXT,
  created_at INTEGER DEFAULT (strftime('%s','now'))
);

CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT,
  order_id INTEGER,
  payload TEXT,
  ts INTEGER DEFAULT (strftime('%s','now'))
);

- Indici: creare indici su status, next_eval_at, tf_minutes per ricerche veloci.
- Archiviazione mensile: `archive_closed_orders_by_month()` può esportare le righe `WHERE status!='active'` in file CSV/JSON separati per mese e poi cancellare/archiviare i record o mantenerli in table archive.

7.1) OCO Orders (nuova feature)

- Schema aggiuntivo introdotto:

CREATE TABLE IF NOT EXISTS order_oco (
    order_id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    hook_symbol TEXT,
    FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS order_oco_leg (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    leg_index INTEGER NOT NULL,
    ordertype TEXT NOT NULL, -- limit|stop_limit|market
    price REAL, -- for limit
    stop_price REAL, -- for stop_limit
    limit_price REAL, -- for stop_limit's limit
    qty REAL NOT NULL,
    side TEXT NOT NULL,
    core_order_id INTEGER, -- core engine order id mapping
    status TEXT NOT NULL DEFAULT 'waiting',
    FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE
);

- Comportamento motore:
  - Per ogni leg OCO l'app crea un "core order" nel motore (Order in `core.py`) con un id interno (implementazione corrente usa id negativi per evitare collisioni con `order_id`).
  - Quando una leg viene eseguita (filled), l'handler marca la leg come `filled`, marca l'OCO come `filled` e annulla (cancel) le leg rimanenti nel motore in modo atomico (cancel-sibling). Gli aggiornamenti per leg/core id e status sono esposti tramite metodi `save_oco_order`, `update_oco_leg_core_order_id`, `update_oco_leg_status` in `storage.py`.
  - L'evento di esecuzione (`oco_leg_filled` / `oco_leg_cancelled`) è scritto su `event_log` per audit.

- Note operative:
  - `SQLiteStorage.__init__` esegue `_init_schema` e quindi usa `CREATE TABLE IF NOT EXISTS` — al prossimo avvio dell'app le nuove tabelle OCO verranno create automaticamente se mancanti. Non è necessario cancellare manualmente il DB per farle comparire.
  - La persistenza e la mappatura core_id ↔ leg sono mantenute in `order_oco_leg.core_order_id`.


8) Persistenza e DB auto-creazione
- Se il DB non esiste, `SQLiteStorage` dovrebbe creare il file e inizializzare le tabelle. Inserire la logica all'interno del costruttore di `SQLiteStorage` per creare `data/` se mancante e creare `bot.sqlite3` con gli schema sopra.
- La app deve controllare `if not os.path.exists(db_path): create_db_and_schema()` all'avvio.

9) Dove mettere i dati sensibili
- Usare un file `.env` (NON committare) per:
  - BOT_TOKEN
  - AUTHORIZED_CHAT_ID
  - BOT_DB_PATH (opzionale)
  - BINANCE_API_KEY, BINANCE_SECRET (se serve)
- Aggiungere `.env` e `data/*.sqlite3` a `.gitignore`.
- Per deployment, preferire variabili d'ambiente del sistema o secret manager.

10) Dipendenze e come avviare
Dipendenze principali (da inserire in `requirements.txt`):
- python-telegram-bot>=20.0
- python-dotenv
- python-binance (per il price feed)
- (opzionale) requests, aiohttp se feed asincroni
- (sqlite3 è nella stdlib)

Comandi per eseguire localmente (powershell):
```
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# creare .env con BOT_TOKEN e altri segreti
python main.py
```

11) Aree di attenzione / miglioramenti suggeriti
- Verificare che `price_feeds.Binance1mClosePriceFeed.get_price(symbol, tf_minutes)` restituisca close price della candle corretta (allineamento UTC strict). Confronta `spunto.py` per replicare perfettamente gli corner case storici.
- Uniformare il comportamento di `/S` e `/B` al 100% con la logica storica in `spunto.py`, specialmente sui corner case (advertised requirement: riga-per-riga match).
- Assicurarsi che `poller` non spawni thread multipli che possano valutare gli stessi ordini in parallelo. Tutte le valutazioni devono rimanere sequenziali nel job `_job_tick`.
- Test automatici: creare unit test per i tick della timeframe (TF boundaries), per la logica di trailing e per la corretta creazione/archiviazione mensile.
- Backup e rotazione DB: consigliata archiviazione mensile separata già richiesta.

12) Conclusione e passi successivi raccomandati
- Implementare (se non fatto) la creazione automatica del DB all'avvio (`SQLiteStorage`).
- Verificare/integrare feed prezzi per restituire i close price all'ultimo candle chiuso coerente con UTC.
- Allineare /S e /B alla logica di `spunto.py` (eseguire test di regressione su dati storici).
- Aggiungere `.env` a .gitignore e documentare dove mettere le chiavi.

13) Aggiornamenti recenti (sintesi)

- `Info` UI: il bottone del menu principale è stato rinominato in `Info` (prima era `Help`) e ora la vista mostra due sezioni: una guida sintetica ai comandi e una sezione "Valori correnti" che riporta i runtime settings attuali del bot (default TF, timeframe seconds, echo, alert, alert percent/reference price e conteggio ordini attivi per tipo inclusi OCO). Questo permette di vedere le impostazioni reali in uso senza aprire il codice.

- OCO (One-Cancels-the-Other): implementate le tabelle `order_oco` e `order_oco_leg` in storage; aggiunti i metodi `save_oco_order`, `update_oco_leg_core_order_id`, `update_oco_leg_status`. L'app crea core orders per ciascuna leg (mappati in `order_oco_leg.core_order_id`) e sul fill di una leg esegue il comportamento cancel-sibling (marca leg come `filled`, marca OCO come `filled` e cancella le leg rimanenti nel motore). Eventi `oco_leg_filled` e `oco_leg_cancelled` vengono scritti in `event_log`.

- Migrazione/creazione schema: `SQLiteStorage.__init__` esegue `_init_schema` e `CREATE TABLE IF NOT EXISTS` per tutte le tabelle; le nuove tabelle OCO verranno create automaticamente al prossimo avvio dell'app se mancanti. Non è necessario cancellare manualmente il DB per applicare queste modifiche.

- Archiviazione: la routine `archive_closed_orders_by_month()` sposta ordini con `status != 'active'` e `updated_at` appartenenti a mesi precedenti in file `data/archive/archive_YYYY_MM.sqlite3`. Un ordine cancellato verrà quindi archiviato solo dopo che il mese è passato rispetto a `updated_at`.

- Nota operativa: il comando Telegram `/c a` (cancella tutti) attualmente itera le collezioni in memoria (`_sell_orders`, `_buy_orders`, `_function_orders`, `_trailing_sell_orders`, `_trailing_buy_orders`) e invoca la cancellazione — attualmente non include esplicitamente la collezione `_oco_orders`. Se desideri che `/c a` annulli anche OCO, posso aggiornarlo.

Se vuoi, procedo subito a:
- implementare lo schema SQL in `storage.py` e fare la creazione automatica del DB,
- aggiornare `requirements.txt` e `.gitignore`,
- estrarre e documentare le chiamate `price_feeds` necessarie per ottenere il close price allineato.

Dimmi quali passi vuoi che esegua adesso: procedo ad applicare modifiche al codice e creare i file necessari (DB schema, .gitignore, requirements aggiornato) oppure preferisci prima che generi test/unit?

