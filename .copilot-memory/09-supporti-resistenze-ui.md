# Supporti & Resistenze UI

## Obiettivo
Introdurre nel bot Telegram una feature dedicata per calcolare e mostrare supporti/resistenze vicini al prezzo corrente, usando il motore hardcoded in `bot_functions.py`.

## API principale
- Calcolo numerico: `richiedi_supporti_resistenze(candles, symbol, timeframe, max_levels, pivot_window, tolerance_pct, secure_threshold)`.
- Spiegazione umana (opzionale): `spiega_supporti_resistenze(result)`.

## Fonte dati runtime
- OHLCV da Binance API (`klines`) tramite client interno del bot.
- MCP Finance non usato a runtime per questa feature.

## Accesso utente
- Comando slash: `/sr SYMBOL [TF] [AMPIEZZA_PCT]`.
- Menu UI: `Supporti&Resistenze` con flow guidato:
  - symbol
  - timeframe
  - ampiezza %

## Regole input
- TF supportati: `1m`, `5m`, `15m`, `1h`, `4h`, `1d` (o minuti `1`, `5`, `15`, `60`, `240`, `1440`).
- Ampiezza valida: `0 < ampiezza <= 100`.

## Regole output
- Mostrare livelli supporto/resistenza solo se vicini al `last_close`:
  - `abs(distance_pct_from_last_close) <= ampiezza_pct`.
- Ordinare i livelli per vicinanza assoluta al prezzo corrente.
- Includere anche secure levels e confidenza:
  - `secure_support`, `secure_support_ok`
  - `secure_resistance`, `secure_resistance_ok`

## Policy error handling
- Fail-closed: se dati OHLC o input non validi, nessun risultato parziale.
- Il bot non si blocca: risponde con errore utente chiaro.
