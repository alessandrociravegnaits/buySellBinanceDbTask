HANDOFF — Migrazione progetto e avvio su nuova macchina

Scopo
- Fornire una checklist completa e ripetibile per spostare e avviare questo progetto su un'altra macchina (dev o server) e per ripristinare lo stato necessario per lo sviluppo o produzione.

Prerequisiti
- Accesso al repository Git del progetto.
- Credenziali per le API Binance (se vuoi usare il client autenticato).
- Accesso alla cartella `data/` se vuoi preservare DB (`bot.sqlite3`).

1) Copia repository
- Clona il repo e controlla il branch desiderato:

```powershell
git clone <repo_url> project
cd project
git checkout <branch>
```

2) Ambiente Python
- Creare e attivare ambiente virtuale (Windows PowerShell):

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3) Variabili ambiente e `.env`
- Crea un file `.env` nella root con almeno le seguenti variabili:

```
BOT_TOKEN=your_telegram_bot_token
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key
# opzionali
AUTHORIZED_CHAT_ID=123456789
BOT_DB_PATH=data/bot.sqlite3
```

- Non committare `.env`.

4) Creazione / migrazione DB
- Il DB viene creato automaticamente se mancante (`SQLiteStorage` esegue `CREATE TABLE IF NOT EXISTS`).
- Per ripristinare un DB esistente, copia `data/bot.sqlite3` nella cartella `data/`.

5) File importanti da conservare
- `data/bot.sqlite3` (stato ordini e mapping OCO)
- `data/archive/` (archivi mensili, opzionale)

6) Esecuzione test rapidi
- Eseguire test unitari principali per verificare l'integrità:

```powershell
.venv\Scripts\Activate.ps1
python -m pytest -q
```

7) Avviare l'app
- Per sviluppo (usa `.env`):

```powershell
. .\.venv\Scripts\Activate.ps1
python main.py
```

- Per debugging diretto del bot (es. senza avviare `main`):

```powershell
python telegram_bot.py
```

8) Controlli post-avvio
- Controlla i log di avvio per eventuali errori su .env o permessi API.
- Verifica che il bot risponda al comando `/start` (usa `AUTHORIZED_CHAT_ID` o leggi l'id dai log).

9) PASS1 — flusso di migrazione (opzionale)
- Se stai migrando runtime con stato attivo (stessa rete):
  - Stoppa il processo sul vecchio host.
  - Copia `data/bot.sqlite3` e `data/archive/` al nuovo host.
  - Avvia il bot sul nuovo host.

10) Dove guardare per debugging e handoff AI
- Docs handoff: `docs/HANDOFF.md` (questo file)
- Stato corrente e runbook PASS1: `docs/ai/AI_HANDOFF_CURRENT.md` e `docs/ai/AI_MIGRATION_PASS1_RUNBOOK.md`
- Registro IA (modifiche fatte dall'assistente): `/memories/ia_rules.md`

11) Check list rapida
- [ ] repo clonato e branch corretto
- [ ] venv creato e dipendenze installate
- [ ] `.env` con `BOT_TOKEN` presente
- [ ] `data/bot.sqlite3` copiato (se vuoi ripristinare stato)
- [ ] `python -m pytest` verde
- [ ] bot avviato e `/start` risponde

Note operative
- Le chiavi Binance sono sensibili: usa secret manager per produzione.
- Se non vuoi esporre chiavi in dev, rimuovi l'esecuzione delle parti che richiedono `_exchange_client` e usa il `MockPriceFeed` per test.

Contatti e riferimenti
- File principali: `telegram_bot.py`, `core.py`, `storage.py`, `price_feeds.py`.
- Test rapidi: `tests/test_account_menu.py`, `tests/test_cancel_order_ui.py`, `tests/test_oco_integration.py`.

Se vuoi, posso aggiungere script PowerShell/Batch per automatizzare i passaggi (clone->venv->install->test->start).

Script di bootstrap
- Abbiamo incluso uno script PowerShell di automazione in `scripts/bootstrap.ps1` per Windows PowerShell.
- Esempi d'uso:

Interactive (guidato):
```powershell
.\scripts\bootstrap.ps1
```

Non-interactive con test e avvio del bot (non raccomandato in produzione senza controlli):
```powershell
.\scripts\bootstrap.ps1 -NonInteractive -BotToken "<token>" -BinanceApiKey "<key>" -BinanceSecret "<secret>" -RunTests -StartBot
```

Lo script crea `.venv`, installa le dipendenze, scrive un `.env` se passi i parametri e può eseguire i test e avviare `main.py`.

Script completo di bootstrap (clone + setup)
- Se vuoi uno script che esegua anche la clonazione e mostri avanzamento interattivo, usa `scripts/full_bootstrap.ps1`.
- Questo script ti chiederà l'URL del repository, la cartella di destinazione, creerà `.venv`, installerà le dipendenze, genererà `.env.sample` (se manca), e può eseguire i test o avviare il bot su richiesta.

Esempio (interactive):
```powershell
.\scripts\full_bootstrap.ps1
```

Esempio (non-interactive):
```powershell
.\scripts\full_bootstrap.ps1 -RepoUrl "https://github.com/you/repo.git" -Destination "C:\dev\project" -Branch "main" -RunTests -StartBot -Yes
```

Importante: lo script NON scriverà segreti sensibili nella `.env` a meno che tu non lo faccia manualmente: alla fine mostra esplicitamente il promemoria per inserire `BOT_TOKEN`, `BINANCE_API_KEY` e `BINANCE_SECRET_KEY`.