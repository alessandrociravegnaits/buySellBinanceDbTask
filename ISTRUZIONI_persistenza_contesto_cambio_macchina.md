Quando ricevo `/pass1-migrazione`, preparo la consegna completa per spostare il progetto su un'altra macchina o per farlo riprendere da un altro sviluppatore/IA.

Checklist PASS1 (operazioni che eseguo prima della consegna):

1. Eseguo i test minimi locali (`pytest`) e raccolgo l'output.
2. Creo/aggiorno un handoff sintetico (file `README.md`/`ARCHITECTURE.md`) con lo stato corrente, file toccati e istruzioni di avvio.
3. Verifico che il DB (`data/bot.sqlite3`) sia accessibile e segnalo come copiarlo, oppure preparo istruzioni per inizializzare una istanza vuota.
4. Creo una nota operativa rapida con i comandi `git` consigliati (branch di handoff, commit message standard, push e PR).
5. Aggiungo una voce nel registro IA (`/memories/ia_rules.md`) con la data e i file modificati.

Comandi e passi da eseguire su altra macchina (destinatario dell'handoff):

- Clona il repository:

```powershell
git clone <repo_url>
cd <repo_dir>
```

- Crea e attiva venv e installa dipendenze:

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

- Copia il database (opzionale ma consigliato per preservare stato e storico):

```powershell
# dalla macchina sorgente
Copy-Item -Path "C:\path\to\project\data\bot.sqlite3" -Destination "C:\path\to\new\project\data\bot.sqlite3"
```

- Crea il file `.env` con variabili sensibili necessarie (non committare):

```
BOT_TOKEN=...
BINANCE_API_KEY=...
BINANCE_SECRET_KEY=...
AUTHORIZED_CHAT_ID=...
BOT_DB_PATH=data/bot.sqlite3
```

- Verifica che il DB abbia le tabelle attese (opzionale): apri `sqlite3` e lancia `SELECT name FROM sqlite_master WHERE type='table';`.

- Esegui i test:

```powershell
python -m pytest -q -s
```

- Avvia il bot per integrazione manuale:

```powershell
python main.py
```

Punti di contesto e file utili per ripresa sviluppo:

- `telegram_bot.py` — wizard e dispatcher `post_fill_action` (auto-OCO), punti in cui costruire nuovi OCO o linkare trailing orders.
- `storage.py` — logica di persistenza SQLite, ricerca delle funzioni `save_oco_order`, `update_oco_leg_core_order_id`, `update_oco_leg_status`.
- `core.py` — dove il motore crea e gestisce `core_order_id` e come mappare questi id alle righe `order_oco_leg`.
- `tests/` — i test esistenti che coprono integrazione OCO e persistenza.

Nota sui DB/migrazioni:
- Lo schema usa `CREATE TABLE IF NOT EXISTS`, quindi al primo avvio eventuali nuove tabelle vengono create automaticamente. Tuttavia, per operazioni di migrazione più complesse (es. cambi di tipo di colonna) consigliamo di eseguire un dump SQL e applicare alterazioni in modo controllato.

Se vuoi che generi automaticamente un file `docs/HANDOFF.md` con comandi pronti `git` + `ps` per esportare/importare il DB e un playbook passo-passo, posso crearlo subito.