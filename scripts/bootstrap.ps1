<#
Bootstrap script for Windows PowerShell
Usage (interactive):
  .\scripts\bootstrap.ps1

Usage (non-interactive):
  .\scripts\bootstrap.ps1 -NonInteractive -BotToken "x" -BinanceApiKey "k" -BinanceSecret "s" -AuthorizedChatId 123 -RunTests -StartBot
#>
param(
    [switch]$NonInteractive,
    [string]$BotToken,
    [string]$BinanceApiKey,
    [string]$BinanceSecret,
    [string]$AuthorizedChatId,
    [switch]$RunTests,
    [switch]$StartBot,
    [switch]$Yes
)

function Fail($msg){ Write-Host "ERROR: $msg" -ForegroundColor Red ; exit 1 }
function Info($msg){ Write-Host $msg -ForegroundColor Cyan }

# Ensure running from repo root
if (-not (Test-Path "README.md")) { Fail "Run this script from the repository root (where README.md is)." }

# Create virtualenv if missing
if (-not (Test-Path ".venv")) {
    Info "Creating virtualenv .venv..."
    python -m venv .venv || Fail "Failed to create virtualenv. Ensure Python is on PATH."
} else {
    Info "Using existing .venv"
}

$pip = Join-Path ".venv\Scripts" "pip.exe"
$python = Join-Path ".venv\Scripts" "python.exe"

Info "Upgrading pip and installing dependencies..."
& $pip install --upgrade pip setuptools wheel > $null
& $pip install -r requirements.txt || Fail "pip install failed"

# .env handling
$envPath = ".env"
if ($BotToken -or $BinanceApiKey -or $BinanceSecret) {
    Info "Writing .env from provided parameters"
    $lines = @()
    if ($BotToken) { $lines += "BOT_TOKEN=$BotToken" }
    if ($BinanceApiKey) { $lines += "BINANCE_API_KEY=$BinanceApiKey" }
    if ($BinanceSecret) { $lines += "BINANCE_SECRET_KEY=$BinanceSecret" }
    if ($AuthorizedChatId) { $lines += "AUTHORIZED_CHAT_ID=$AuthorizedChatId" }
    if (Test-Path $envPath) {
        if (-not $Yes -and -not $NonInteractive) {
            $ok = Read-Host ".env exists — overwrite? (y/N)"
            if ($ok -ne 'y' -and $ok -ne 'Y') { Info "Keeping existing .env" }
            else { $lines | Out-File -Encoding utf8 -FilePath $envPath }
        } else {
            $lines | Out-File -Encoding utf8 -FilePath $envPath
        }
    } else {
        $lines | Out-File -Encoding utf8 -FilePath $envPath
    }
} else {
    if (-not (Test-Path $envPath)) {
        Info "No secrets provided. Creating .env.sample — fill this file with your keys before starting."
        @(
            "# Copy to .env and fill secrets",
            "BOT_TOKEN=your_telegram_bot_token",
            "BINANCE_API_KEY=your_binance_api_key",
            "BINANCE_SECRET_KEY=your_binance_secret_key",
            "# Optional:",
            "AUTHORIZED_CHAT_ID=123456789",
            "BOT_DB_PATH=data/bot.sqlite3"
        ) | Out-File -Encoding utf8 -FilePath ".env.sample"
    } else {
        Info ".env already present — leaving as is."
    }
}

# Create data dir if missing
if (-not (Test-Path "data")) { New-Item -ItemType Directory -Path data | Out-Null }

# Run tests optionally
if ($RunTests) {
    Info "Running test suite (pytest)..."
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { Fail "Tests failed (exit code $LASTEXITCODE)" }
    Info "Tests passed."
}

# Start bot optionally
if ($StartBot) {
    if (-not (Test-Path $envPath)) { Fail ".env missing — create it or provide keys with -BotToken/-BinanceApiKey/-BinanceSecret" }
    Info "Starting bot (python main.py) ... Press Ctrl+C to stop"
    & $python main.py
}

Info "Bootstrap complete. See docs/HANDOFF.md for further notes."
