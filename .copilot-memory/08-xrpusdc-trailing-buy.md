# XRPUSDC trailing buy - schema trasversale

## Obiettivo
Memorizzare un metodo riusabile per progettare un trailing buy su XRPUSDC o su un asset simile, partendo da dati mcp e traducendoli in parametri del bot.
Lo stesso flusso e' stato anche cristallizzato nello script `prevision.py` nella root del progetto.

## Prerequisito obbligatorio
- Prima di prendere decisioni di ingresso o di soglia, attivare sempre i tool `mcp finance` e usare i dati aggiornati del mercato.
- Se i tool `mcp finance` non sono attivi o non rispondono, fermare la procedura e ricordarlo esplicitamente prima di proseguire.

## Metodo di lettura mcp
- Se il pair diretto non e' disponibile, usare il ticker proxy piu' vicino per ricostruire il quadro tecnico.
- Nel caso specifico, `XRPUSDC` non era esposto dai tool finance e il riferimento coerente e' stato `XRP-USD`.
- Valutare insieme prezzo recente, retracement, RSI, MACD, ADX, volatilita' e sentiment macro.
- Cercare una zona di pullback dove il prezzo rientra in una fascia tecnica, ma senza considerarla un supporto assoluto.

## Criterio decisionale
- Evitare ingresso market quando il momentum e' ancora debole o misto.
- Preferire un ingresso condizionato su pullback e successivo rimbalzo confermato.
- Trattare la soglia di armamento come un gate operativo che puo' cambiare nel tempo, non come un numero fisso.

## Traduzione nel bot
- `tf_minutes`: scegliere un timeframe medio-breve, spesso `15`, per bilanciare rumore e reattivita'.
- `limit`: posizionarlo nella fascia tecnica del pullback osservato al momento dell'analisi.
- `percent`: usarlo come ampiezza del rimbalzo minimo richiesto prima del fill.
- `btc_alert`: tenerlo attivo quando il contesto macro crypto e' fragile o incerto.
- `oco`: predisporre gia' un'uscita automatica con take profit moderato e stop dinamico.
- `acquistopulito`: attivarlo solo se il mercato e' abbastanza pulito da giustificare un filtro piu' severo.

## Comando template
Sostituire i segnaposto con i valori correnti del momento:
```text
/B XRPUSDC <percent> QTY <limit> tf=<tf_minutes> btc_alert oco:tp=<tp>%,sl=trail:<sl>%
```

## Formula utile
- Quantita' in coin = `budget_usdc / limit`
- Esempio generale: con budget `100 USDC`, la size dipende dal `limit` scelto in quel momento.

## Nota importante
Le soglie sono sempre dinamiche: il numero usato oggi serve solo come fotografia dell'analisi corrente. La memoria utile e' la procedura, non il valore puntuale.
