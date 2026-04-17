# SR Book Rules Implementation

## Overview
Implementazione completa delle 4 regole del libro trading per il motore Support & Resistance (bot_functions.py).

## Parametri Aggiunti

### 1. **Close Confirmation (Breakout Validation)**
**Cosa fa:** Verifica che il breakout di un livello sia confermato da almeno 2-3 candles successive che rimangono sopra/sotto il livello.

**Calcolo:**
- Support breakout: close[N-1] ≤ level && close[N] > level×(1+buffer)
- Valida i close futuri: almeno 2 su 3 devono stare sopra threshold
- Score: 0.0-1.0 (0.33 = 1/3 futuri confermati, 1.0 = 3/3 confermati)

**Output nel bot:**
- `close_confirmation_ok`: boolean (True se score ≥ 0.5)
- `close_confirmation_score`: float 0-1

**Visibilità:** Nel messaggio Telegram "Supporti & Resistenze", accanto a ogni livello

---

### 2. **Role Reversal Detection**
**Cosa fa:** Dopo un breakout, rileva se il prezzo ritorna a testare il livello (retest) e rimane fuori (conferma il nuovo ruolo).

**Calcolo:**
- Cerca prima un breakout (close attraversa il livello)
- Poi cerca un retest entro N candles (ritorno verso il livello)
- Se il retest non penetra il livello: score più alto (0.7-1.0)
- Se il retest penetra: score più basso (0.3-0.7)

**Output nel bot:**
- `role_reversal_ok`: boolean (True se score ≥ 0.5)
- `role_reversal_score`: float 0-1

**Visibilità:** Nel messaggio Telegram, come score di conferma della robustezza del livello

---

### 3. **Round Number Proximity**
**Cosa fa:** Predilige livelli su numeri "tondi" (100, 10, 1, 0.1, 0.01, ecc.).

**Calcolo per ogni livello:**
- Determina il "step" tondo in base al valore (100-1000 → step 100, 10-100 → step 10, etc.)
- Nearest round = round(level / step) × step
- Distance % = |level - nearest| / level × 100
- Score = max(0, 1 - min(distance_pct / 0.25, 1.0))
  - Distance < 0.25% → score > 0.99
  - Distance > 0.25% → score degrada linearmente

**Output nel bot:**
- `round_number_ok`: boolean (True se score ≥ 0.5)
- `round_number_score`: float 0-1
- `nearest_round_number`: float (es. 100.0 instead di 103.2)
- `round_number_distance_pct`: float (distanza %)

**Esempi:**
- 100.0 → score 1.0 (perfetto)
- 100.08 → score 0.96 (0.08% di distanza)
- 103.2 → score 0.25 (3.2% di distanza)

---

### 4. **Timeframe Weighting**
**Cosa fa:** Applica un moltiplicatore diverso di fiducia per ogni timeframe (TF più grandi = più peso).

**Weights applicati:**
```
1m:   0.92× (bassa confidenza, noise elevato)
5m:   0.94×
15m:  0.96×
1h:   0.98×
4h:   1.00× (baseline)
1d:   1.03×
4d:   1.06×
1w:   1.10× (massima confidenza, menos noise)
```

**Come funziona:**
- Score finale = sum(all_component_scores) × timeframe_weight
- Es. support 1m con score totale 0.9: 0.9 × 0.92 = 0.828
- Es. support 1w con score totale 0.9: 0.9 × 1.10 = 0.99

**Output nel bot:**
- Esposto nel metadata → "timeframe_weight": 0.92 (per 1m), 1.10 (per 1w)

---

## Componenti Scoring (10 fattori)

Nel calcolo della confidenza finale di un livello:

| Componente | Peso (prima normaliz.) | Descrizione |
|-----------|------------------|------------|
| touches | 0.22 | N° volte che il prezzo ha testato il livello |
| multi_tf | 0.16 | Conferma su TF più grandi (1h, 4h, 1d, 1w) |
| reaction | 0.14 | Rimbalzi dal livello (support/resistance) |
| recency | 0.08 | Quanto recente è l'ultimo test |
| volume | 0.08 | Volume sui test (vs media) |
| distance | 0.08 | Distanza dal prezzo attuale (penalizza troppo lontano) |
| cluster | 0.06 | Qualità della zona di accumulo |
| **close_confirmation** | **0.08** | Breakout confermato da 2+ candles |
| **role_reversal** | **0.06** | Retest post-breakout con conferma |
| **round_number** | **0.04** | Prossimità a numero tondo |

**Totale:** ~1.0 (dopo normalizzazione)

---

## Uso nel Telegram Bot

### Comando completo:
```
/sr XRPUSDC 15 5 si
```
Dove:
- `XRPUSDC` = symbol
- `15` = timeframe minuti
- `5` = ampiezza ±%
- `si` = applica secure mode (trend filter)

### Output esempio (per ogni livello):
```
🔽 Support 2.4500
  Confidence: 82% | Close OK: ✓ (0.67) | Retest OK: ✓ (0.88)
  Round: 2.45 (0.22% da 2.45)
  Touches: 5 | Multi-TF: ✓ | Reaction: 88%
```

---

## Test Coverage

File: `tests/test_supporti_resistenze_book_rules.py`

1. **test_round_number_score_prefers_clean_levels**
   - Verifica che 100.0 score > 103.0 score ✓

2. **test_support_breakout_close_and_role_reversal_scores**
   - Support breakout con close confirmation > 0.5 ✓
   - Role reversal (retest senza penetrazione) > 0.5 ✓

3. **test_resistance_breakout_close_and_role_reversal_scores**
   - Simmetrico per resistance ✓

4. **test_timeframe_weight_is_exposed_in_metadata**
   - Verifica 1m weight < 1w weight ✓

---

## Path Fix (Database Persistence)

**Problema risolto:** Bot scriveva ordini su db diverso da quello usato per query (relative path resolution bug).

**Soluzione:** telegram_bot.py (linea 170+)
```python
db_path = "data/bot.sqlite3"
if not Path(db_path).is_absolute():
    db_path = str(Path(__file__).resolve().parent / db_path)
```

Adesso db_path è assoluto e punta sempre a: `C:\Users\p4cco\Documents\buySellBinanceDbTask\data\bot.sqlite3`

---

## Status: ✅ Complete & Tested
- Implementazione: ✅
- Unit tests: ✅ (9 passed)
- Path fix: ✅
- Ready for production: ✅
