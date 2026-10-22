# Bangla Bhai one-click installer for Windows 10/11
# Clones GitHub main to %USERPROFILE%\bangla_bhai, creates venv, installs requirements, writes .env, optional Cloudflare tunnel, autostart.
$ErrorActionPreference = "Stop"
$Repo = "https://github.com/Royel999/bangla-bhai.git"
$App = Join-Path $env:USERPROFILE "bangla_bhai"
Write-Host "=== Bangla Bhai installer ===" -ForegroundColor Cyan

function Test-Cmd([string]$Name) { [bool](Get-Command $Name -ErrorAction SilentlyContinue) }
function Update-SessionPath { $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User") }
function Install-WithWinget([string]$Id) {
    winget install -e --id $Id --accept-package-agreements --accept-source-agreements --scope user
    Update-SessionPath
}
function Read-Secret([string]$Prompt) {
    $s = Read-Host $Prompt -AsSecureString
    $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
}

# 1. Git + code from GitHub main
if (-not (Test-Cmd "git")) { Write-Host "Installing Git..."; Install-WithWinget "Git.Git" }
if (Test-Path (Join-Path $App ".git")) {
    Write-Host "Updating existing copy in $App"
    git -C $App pull --ff-only origin main
} else {
    Write-Host "Downloading Bangla Bhai to $App"
    git clone --branch main $Repo $App
}
Set-Location $App

# 2. Python + venv + requirements
$py = $null
if (Test-Cmd "py") { $py = "py" } elseif (Test-Cmd "python") { $py = "python" }
if (-not $py) {
    Write-Host "Installing Python 3.12..."
    Install-WithWinget "Python.Python.3.12"
    if (Test-Cmd "py") { $py = "py" } else { $py = "python" }
}
$venvPy = Join-Path $App "venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { & $py -m venv (Join-Path $App "venv") }
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r (Join-Path $App "requirements.txt")
try { & $venvPy -m playwright install chromium } catch { Write-Host "Playwright browser skipped" }

# 3. .env from .env.example (values typed by the owner, hidden)
$envFile = Join-Path $App ".env"
if (-not (Test-Path $envFile)) {
    $script:lines = Get-Content (Join-Path $App ".env.example")
    function Set-EnvKey([string]$Key, [string]$Value) {
        if (-not $Value) { return }
        $script:lines = $script:lines | ForEach-Object { if ($_ -match "^$Key=") { "$Key=$Value" } else { $_ } }
    }
    $chars = [char[]]((48..57) + (65..90) + (97..122))
    $secret = -join (1..48 | ForEach-Object { $chars | Get-Random })
    Set-EnvKey "BB_SESSION_SECRET" $secret
    $u = Read-Host "Owner username (Enter = royal)"; if (-not $u) { $u = "royal" }
    Set-EnvKey "BB_USER" $u
    do { $pw = Read-Secret "Owner password (min 8 characters)" } while ($pw.Length -lt 8)
    Set-EnvKey "BB_PASSWORD" $pw
    Set-EnvKey "BB_OWNER_EMAIL" (Read-Host "Owner email (for email-code login)")
    Write-Host "Free keys: console.groq.com/keys | aistudio.google.com/apikey | openrouter.ai/keys  (Enter = skip)"
    Set-EnvKey "GROQ_API_KEY" (Read-Secret "Groq API key")
    Set-EnvKey "GEMINI_API_KEY" (Read-Secret "Gemini API key")
    Set-EnvKey "OPENROUTER_API_KEY" (Read-Secret "OpenRouter API key")
    Set-EnvKey "RESEND_API_KEY" (Read-Secret "Resend API key for login emails (optional)")
    Set-EnvKey "BB_TELEGRAM_TOKEN" (Read-Secret "Telegram bot token (optional)")
    $script:lines | Set-Content $envFile -Encoding UTF8
    Write-Host ".env saved. Edit later with Notepad; never share it."
} else { Write-Host ".env already exists - kept." }

# 4. Cloudflare tunnel (optional)
$ans = Read-Host "Install Cloudflare tunnel (cloudflared) for banglabhai.dpdns.org? (y/N)"
if ($ans -match "^[yY]") {
    if (-not (Test-Cmd "cloudflared")) { Install-WithWinget "Cloudflare.cloudflared" }
    Write-Host "cloudflared installed. Finish the one-time setup in windows\GUIDE_BN.md step 5."
}

# 5. Autostart at logon
$startBat = Join-Path $App "windows\start.bat"
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$startBat`" hidden" -WorkingDirectory $App
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName "BanglaBhai" -Action $action -Trigger $trigger -Settings $settings -Description "Bangla Bhai app + Cloudflare tunnel" -Force | Out-Null
Write-Host "Autostart task 'BanglaBhai' registered." -ForegroundColor Green

Start-Process -FilePath $startBat -WorkingDirectory $App
Write-Host "Done! Open http://localhost:8090" -ForegroundColor Green
