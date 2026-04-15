# Handoff Integrazione Bot Supporti/Resistenze

Questo file serve come specifica operativa da copiare anche nell'altro bot. Se vuoi una sola cosa da portare, il file minimo e `bot_functions.py`.

## Cosa fa questo modulo

Il motore calcola supporti e resistenze in modo deterministico e hardcoded:

- pivot highs/lows
- clustering dei livelli
- conferma su piu finestre temporali
- score di affidabilita (`confidence`)
- selezione di `secure_support` e `secure_resistance`

La knowledge base del libro non serve piu per il calcolo numerico. Eventuali note dal libro sono opzionali e solo descrittive.

## File da copiare nell'altro bot

### Minimo indispensabile per essere operativo

1. `bot_functions.py`

Questo basta per calcolare i livelli e ricevere un output JSON completo.

### Se vuoi anche l'output leggibile e il runner CLI

2. `run_support_resistance.py`
3. `demo_support_resistance.py`

### Se vuoi anche le note dal libro o il layer knowledge

4. `knowledge_service.py`
5. La cartella LanceDB del libro, per esempio `~/.rag_pdf_kb/<nome_pdf>_<hash>.lancedb`

Nota: queste ultime due cose sono opzionali. Il motore funziona anche senza.

## Dipendenze minime

- `python`
- `pandas` se il bot legge CSV in autonomia
- nessuna dipendenza obbligatoria da LanceDB se usi solo `bot_functions.py`

Se vuoi anche la parte book/knowledge:

- `lancedb`
- `sentence-transformers`
- `pyarrow`

## Contratto di input

La funzione principale accetta una sequenza di candele OHLC.

### Formato consigliato

```python
candles = [
    {
        "timestamp": "2026-04-16T10:00:00Z",
        "open": 100.0,
        "high": 102.0,
        "low": 99.5,
        "close": 101.2,
        "volume": 1200,
    },
]
```

### Campi richiesti

- `timestamp` oppure `date`
- `open`
- `high`
- `low`
- `close`

### Campo opzionale

- `volume`

## Firma logica della funzione

La funzione da chiamare e questa:

```python
richiedi_supporti_resistenze(
    candles,
    symbol="BTCUSDT",
    timeframe="1h",
    max_levels=3,
    pivot_window=2,
    tolerance_pct=0.4,
    secure_threshold=None,
)
```

### Parametri principali

- `candles`: lista di candele OHLC
- `symbol`: simbolo/ticker
- `timeframe`: `1m`, `5m`, `15m`, `1h`, `4h`, `1d`, `1w`
- `max_levels`: quanti livelli finali vuoi
- `pivot_window`: finestra base di pivot
- `tolerance_pct`: tolleranza clustering
- `secure_threshold`: se `None`, usa la soglia di default del rulebook per timeframe

## Output

La funzione ritorna un dizionario JSON-like con questi campi:

- `symbol`
- `timeframe`
- `generated_at`
- `last_close`
- `supports`
- `resistances`
- `secure_support`
- `secure_resistance`
- `secure_support_ok`
- `secure_resistance_ok`
- `secure_threshold`
- `method`
- `knowledge_notes`
- `integration_hint`

## Come interpretare l'output

### Usa sempre questi campi nel bot

- `secure_support`
- `secure_resistance`
- `secure_support_ok`
- `secure_resistance_ok`
- `confidence`

### Regola pratica

- se `secure_support_ok == True`, il supporto e valido per il bot
- se `secure_resistance_ok == True`, la resistenza e valida per il bot
- se `False`, il livello esiste ma non deve essere trattato come affidabile senza ulteriori conferme

## Spiegazione leggibile

Se vuoi mostrare il risultato in linguaggio naturale, usa:

```python
spiega_supporti_resistenze(result)
```

Questa funzione non calcola nulla: converte solo il risultato tecnico in testo.

## Ordine operativo consigliato nell'altro bot

1. Recupera le candele OHLC.
2. Chiama `richiedi_supporti_resistenze(...)`.
3. Leggi `secure_support` e `secure_resistance`.
4. Se devi mostrare una spiegazione umana, chiama `spiega_supporti_resistenze(...)`.
5. Usa i livelli sicuri per logiche come ingresso, stop loss, take profit o avvisi.

## Esempio minimo di integrazione

```python
from bot_functions import richiedi_supporti_resistenze, spiega_supporti_resistenze

result = richiedi_supporti_resistenze(
    candles=my_candles,
    symbol="BTCUSDT",
    timeframe="1h",
)

if result["secure_support_ok"]:
    support = result["secure_support"]["level"]
else:
    support = None

print(spiega_supporti_resistenze(result))
```

## Regola importante per l'altro bot

Non passare testo libero al motore aspettandoti che calcoli livelli. Il motore vuole dati OHLC. Il testo serve solo per spiegazione o per scegliere il contesto.

## In una frase

Se vuoi solo che l'altro bot sia operativo, copia `bot_functions.py`. Se vuoi anche il layer libro/knowledge, aggiungi `knowledge_service.py` e il relativo `.lancedb`.
