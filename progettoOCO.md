Ottima direzione. Ragionando per passi senza codice:

---

## **Concetto centrale: "post-fill action"**

Invece di un semplice flag booleano, ti conviene pensarlo come una **post-fill action spec** — una specifica opzionale allegata a qualsiasi ordine che descrive cosa fare dopo il fill. L'OCO automatico è il primo caso, ma la struttura può crescere.

---

## **1\. Come modellare la spec nel DB**

Ogni tabella di ordine (`simple_orders`, `function_orders`, `trailing_buy_orders`) riceve una colonna aggiuntiva:

post\_fill\_action TEXT  \-- JSON blob oppure NULL se non presente

Un JSON blob è la scelta più flessibile qui perché la spec varia molto tra le modalità (%, valore fisso, trailing). Eviti di aggiungere 8 colonne sparse per ogni caso. Esempi di contenuto:

**Modalità percentuale:**

json  
{ "type": "oco", "tp": {"mode": "percent", "value": 3.0}, "sl": {"mode": "percent", "value": 1.5} }

**Modalità valore fisso:**

json  
{ "type": "oco", "tp": {"mode": "fixed", "value": 72000.0}, "sl": {"mode": "fixed", "value": 65000.0} }

**Modalità trailing sulla leg SL:**

json  
{ "type": "oco", "tp": {"mode": "fixed", "value": 72000.0}, "sl": {"mode": "trailing", "value": 1.5} }  
\`\`\`

In questo modo il parser della post-fill action sa sempre cosa costruire leggendo \`type\` prima di tutto, e le due leg TP/SL sono indipendenti nella loro modalità.

\---

\#\# 2. Come si specifica dal comando Telegram

Aggiungi una sintassi opzionale in coda al comando di buy esistente. L'utente che vuole l'OCO automatico appende qualcosa tipo:  
\`\`\`  
/b BTCUSDT \< 67000 0.001 oco:tp=3%,sl=1.5%  
/b BTCUSDT \< 67000 0.001 oco:tp=72000,sl=65000  
/b BTCUSDT \< 67000 0.001 oco:tp=3%,sl=trail:1.5%  
\`\`\`

Il parser in \`telegram\_bot.py\` legge questo token, costruisce il dict della post-fill action e lo serializza come JSON nella colonna. Se il token non c'è, la colonna resta NULL e non succede nulla dopo il fill.

\---

\#\# 3. Come si propaga al momento del fill

Nei metodi \`\_on\_simple\_fired\`, \`\_on\_function\_fired\`, \`\_on\_trailing\_buy\_fired\` già hai il riferimento all'ordine. L'ordine ora porta con sé la \`post\_fill\_action\`. Il flusso diventa:  
\`\`\`  
buy filled  
    │  
    ▼  
leggi order.post\_fill\_action  
    │  
    ├── None → fine, nessuna azione  
    │  
    └── presente → chiama \_dispatch\_post\_fill\_action(order, fill\_price)  
                        │  
                        └── legge "type"  
                               │  
                               └── "oco" → \_create\_auto\_oco(order, fill\_price, spec)  
\`\`\`

Il metodo \`\_dispatch\_post\_fill\_action\` è il punto di estensione futuro: domani puoi aggiungere \`"type": "notify\_only"\` o \`"type": "reopen"\` senza toccare i callback di fill.

\---

\#\# 4. Come costruisce l'OCO conoscendo la spec

Dentro \`\_create\_auto\_oco\` ricevi \`fill\_price\` e la \`spec\`. Per ogni leg:

\- se \`mode \== "percent"\` → calcoli \`fill\_price ± value%\`  
\- se \`mode \== "fixed"\` → usi direttamente \`value\`  
\- se \`mode \== "trailing"\` → non crei un core order semplice ma crei un \*\*trailing order\*\* (già presente nel motore come \`/S\`) e lo colleghi come leg SL dell'OCO

Quest'ultimo caso è il più interessante: la leg trailing non ha un prezzo fisso ma sfrutta la logica già esistente dei trailing orders. Il collegamento OCO rimane valido: quando il trailing scatta, triggera il cancel-sibling come farebbe qualsiasi altra leg.

\---

\#\# 5. Collegamento OCO ↔ ordine padre

Nella tabella \`order\_oco\` aggiungi una colonna \`parent\_order\_id\` che punta all'ordine che ha generato l'OCO. Questo ti serve per:

\- mostrare nella UI "questo OCO è nato dal buy \#42"  
\- nel \`/c a\` cancellare anche gli OCO figli se cancelli il padre (anche se il padre è già filled, è utile per audit)  
\- nell'archivio mensile mantenere la catena di causalità

\---

\#\# 6. Cosa cambia nelle tabelle

| Tabella | Modifica |  
|---|---|  
| \`simple\_orders\` | \+ colonna \`post\_fill\_action TEXT\` |  
| \`function\_orders\` | \+ colonna \`post\_fill\_action TEXT\` |  
| \`trailing\_buy\_orders\` | \+ colonna \`post\_fill\_action TEXT\` |  
| \`order\_oco\` | \+ colonna \`parent\_order\_id INTEGER\` |

Nient'altro nel DB. La logica di calcolo TP/SL/trailing vive tutta in Python.

\---

\#\# 7. Il caso trailing come leg SL — punto critico

Quando \`sl.mode \== "trailing"\`, devi decidere se:

\*\*Opzione A\*\* — La leg SL è un vero trailing order (\`/S\`) registrato nel motore normale, e il suo \`core\_order\_id\` nell'\`order\_oco\_leg\` punta a quell'ordine trailing. Quando scatta, il cancel-sibling annulla la leg TP. Questo riusa tutto il codice esistente senza duplicazioni.

\*\*Opzione B\*\* — Implementi la logica trailing direttamente dentro il motore OCO. Più complesso, meno riuso.

\*\*Consiglio: Opzione A.\*\* Il motore trailing esiste già, è testato, e il collegamento tramite \`core\_order\_id\` è già previsto dallo schema.

\---

\#\# Sintesi del flusso completo  
\`\`\`  
Comando /b con oco:...  
    → parsing → post\_fill\_action serializzato nel record ordine

Ordine buy valutato dal poller  
    → trigger scatta → \_on\_\*\_fired  
    → esegui buy (come ora)  
    → leggi post\_fill\_action  
    → \_dispatch\_post\_fill\_action  
        → \_create\_auto\_oco(fill\_price, spec)  
            → calcola prezzi TP e SL secondo mode  
            → save\_oco\_order (con parent\_order\_id)  
            → add\_oco\_leg TP → core order semplice "\>"  
            → add\_oco\_leg SL → core order trailing "/S" se mode=trailing  
                               oppure core order semplice "\<" se fixed/percent  
            → notifica Telegram

Una delle due leg scatta  
    → cancel-sibling (già implementato)  
    → OCO chiuso  
