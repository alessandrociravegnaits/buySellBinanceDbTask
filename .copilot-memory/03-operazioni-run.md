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
- `BTC_LIQUIDATION_DROP_PERCENT` (fallback per la soglia BTC, default 0.5%)

## Avvio
```powershell
python main.py
```

## Comandi utili Telegram
- `/info` mostra anche la soglia BTC di liquidazione corrente.
- `/ad PERCENT` imposta la soglia di caduta BTC per la liquidazione automatica.
- `/a 0|1 [PERCENT]` resta separato come alert visivo.

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
