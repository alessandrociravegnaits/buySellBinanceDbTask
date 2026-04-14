# Operazioni, Avvio, Test

## Setup locale
```powershell
python -m venv venv
. .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Variabili env principali
- `BOT_TOKEN`
- `AUTHORIZED_CHAT_ID`
- `BINANCE_API_KEY`
- `BINANCE_SECRET_KEY`
- `BOT_DB_PATH`

## Avvio
```powershell
python main.py
```

## Test
```powershell
python -m pytest -q
```

## Nota Windows PowerShell
Se l'attivazione `Activate.ps1` e bloccata da execution policy:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
. .\venv\Scripts\Activate.ps1
```

## Terminale Bash classico
- Git Bash: `"C:\Program Files\Git\bin\bash.exe"`
- WSL Bash: `wsl -e bash`

Fonti: `README.md`, `docs/HANDOFF.md`

## Aggiornamento 2026-04-12

### Comando validazione usato nel checkpoint
```powershell
PYTHONPATH=. pytest -q
```

### Esito checkpoint
- `54 passed, 4 warnings`
- Branch: `featureFinale00`
- HEAD: `a0e26e0`

### Note operative
- Nuovo comando runtime: `/ad PERCENT` per soglia BTC drop.
- `PERCENT=0` disabilita la protezione.

## Template trailing buy trasversale
```text
/B XRPUSDC <percent> QTY <limit> tf=<tf_minutes> btc_alert oco:tp=<tp>%,sl=trail:<sl>%
```

### Lettura rapida dei campi
- `limit` e' il gate di pullback, da ricalcolare sul contesto attuale.
- `percent` e' il rimbalzo minimo richiesto prima del fill.
- `btc_alert` resta attivo quando vuoi ridurre l'esposizione a un dump del mercato crypto.
- `oco` consente di arrivare gia' con una gestione uscita pronta dopo l'ingresso.
