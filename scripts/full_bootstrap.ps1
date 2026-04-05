<#
Full bootstrap script: clone + setup + optional tests/start
Usage (interactive):
  .\scripts\full_bootstrap.ps1

Non-interactive example:
  .\scripts\full_bootstrap.ps1 -RepoUrl "https://github.com/you/repo.git" -Destination "C:\dev\project" -Branch "main" -RunTests -StartBot -Yes

Note: This script is interactive by default and will NOT write a `.env` containing secrets unless you explicitly provide them via parameters.
#>
param(
    [string]$RepoUrl,
    [string]$Branch = "",
    [string]$Destination = "",
    [switch]$RunTests,
    [switch]$StartBot,
    [switch]$Yes
)

function Fail($msg){ Write-Host "ERROR: $msg" -ForegroundColor Red ; Exit 1 }
function Info($msg){ Write-Host "==> $msg" -ForegroundColor Cyan }
function Note($msg){ Write-Host "    $msg" -ForegroundColor Yellow }

# Step 1: Get repo URL and destination
if (-not $RepoUrl) {
    $RepoUrl = Read-Host "Repo URL to clone (leave empty to use current folder)"
}

if (-not $Destination) {
    $Destination = Read-Host "Destination folder (full path) or '.' for current folder"
}
if (-not $Destination) { $Destination = "." }

# Resolve destination path
if ($Destination -eq '.') { $destPath = Get-Location } else { $destPath = Resolve-Path -LiteralPath $Destination -ErrorAction SilentlyContinue }
if (-not $destPath) { $destPath = (Join-Path (Get-Location) $Destination) }
$destPath = [IO.Path]::GetFullPath($destPath.ToString())

Info "Target path: $destPath"

# Clone if RepoUrl provided
if ($RepoUrl -and $RepoUrl.Trim() -ne "") {
    # check git
    try {
        git --version > $null 2>&1
    } catch {
        Fail "git is required but not found in PATH. Install git and retry."
    }

    if (Test-Path $destPath -PathType Container -ErrorAction SilentlyContinue) {
        if ((Get-ChildItem -LiteralPath $destPath -Force | Measure-Object).Count -gt 0) {
            if (-not $Yes) {
                $ok = Read-Host "Destination exists and is non-empty. Overwrite/clean it? (y/N)"
                if ($ok -ne 'y' -and $ok -ne 'Y') {
                    Fail "Aborted by user: destination not empty."
                }
            }
            # attempt to remove contents
            Info "Cleaning destination folder..."
            Get-ChildItem -Path $destPath -Force | Remove-Item -Recurse -Force
        }
    } else {
        New-Item -ItemType Directory -Path $destPath | Out-Null
    }

    Info "Cloning $RepoUrl into $destPath"
    $cloneArgs = @($RepoUrl, $destPath)
    if ($Branch -and $Branch.Trim() -ne "") { $cloneArgs += "--branch"; $cloneArgs += $Branch }
    $proc = Start-Process -FilePath git -ArgumentList ("clone" + " " + ($cloneArgs -join ' ')) -NoNewWindow -Wait -PassThru -ErrorAction SilentlyContinue
    if ($proc.ExitCode -ne 0) {
        Fail "git clone failed (exit code $($proc.ExitCode))."
    }
} else {
    Info "Skipping clone; using existing folder $destPath"
}

# Change to project dir
Set-Location -Path $destPath

# Step 2: Create virtualenv
if (-not (Test-Path ".venv")) {
    Info "Creating virtual environment (.venv)..."
    python -m venv .venv 2>&1 | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) { Fail "Failed to create virtualenv. Ensure Python is on PATH." }
} else {
    Info "Virtualenv .venv already exists; skipping creation."
}

$pip = Join-Path ".venv\Scripts" "pip.exe"
$python = Join-Path ".venv\Scripts" "python.exe"

# Step 3: Install requirements
Info "Installing dependencies from requirements.txt..."
& $pip install --upgrade pip setuptools wheel | ForEach-Object { Write-Host $_ }
& $pip install -r requirements.txt | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) { Fail "Dependency installation failed." }

# Step 4: Create .env.sample if .env missing
if (-not (Test-Path ".env")) {
    Info "Creating .env.sample (please copy to .env and fill secrets)"
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
    Info ".env already present in repository. Secrets are not modified."
}

# Ensure data dir exists
if (-not (Test-Path "data")) { New-Item -ItemType Directory -Path data | Out-Null }

# Step 5: Run tests if requested
if ($RunTests) {
    Info "Running test suite..."
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { Fail "Tests failed. See output above." }
    Info "Tests passed."
}

# Step 6: Reminder to add secrets
Write-Host ""; Write-Host "IMPORTANT:" -ForegroundColor Yellow
Write-Host "  Add your secrets to .env (BOT_TOKEN, BINANCE_API_KEY, BINANCE_SECRET_KEY) before starting the bot." -ForegroundColor Yellow
Write-Host "  Example: copy .env.sample to .env and edit it." -ForegroundColor Yellow

# Step 7: Start bot if requested
if ($StartBot) {
    if (-not (Test-Path ".env")) { Fail ".env missing — create it with your secrets before starting the bot." }
    Info "Starting bot (python main.py) — logs will appear below. Press Ctrl+C to stop."
    & $python main.py
}

Info "Bootstrap finished. See docs/HANDOFF.md for more details." 
