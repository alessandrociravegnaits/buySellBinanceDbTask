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
- Comando legacy `/setpulito` e percorso GUI in `Impostazioni -> setPulito`.
- I valori vengono salvati in `bot_settings` e ricaricati all’avvio.

## Default e compatibilità
- Se non esiste configurazione salvata, il bot parte con il preset `Bilanciato`.
- Il comportamento buy legacy resta identico quando `acquistopulito` è falso.
- La configurazione è globale, non per singolo ordine.

## Verifica
- Aggiunti test per persistenza flag, parsing comandi, gating runtime e preset/override di `setPulito`.
- Suite completa verificata con successo.
