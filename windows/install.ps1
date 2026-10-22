# Bangla Bhai one-click installer for Windows 10/11
$ErrorActionPreference = "Stop"
$App = Split-Path -Parent $PSScriptRoot
Set-Location $App
Write-Host "=== Bangla Bhai installer ===" -ForegroundColor Cyan

function Have($c){ [bool](Get-Command $c -ErrorAction SilentlyContinue) }
function Refresh-Path { $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User") }

# 1. Python
$py = $null
if (Have "py") { $py = "py" } elseif (Have "python") { $py = "python" }
if (-not $py) {
  Write-Host "Installing Python 3.12 (winget)..."
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --scope user
  Refresh-Path
  if (Have "py") { $py = "py" } else { $py = "python" }
}

# 2. venv + requirements
if (-not (Test-Path "$App\venv\Scripts\python.exe")) { & $py -m venv "$App\venv" }
& "$App\venv\Scripts\python.exe" -m pip install --upgrade pip
& "$App\venv\Scripts\python.exe" -m pip install -r "$App\requirements.txt"
try { & "$App\venv\Scripts\python.exe" -m playwright install chromium } catch { Write-Host "playwright browser skipped" }

# 3. .env
if (-not (Test-Path "$App\.env")) {
  Copy-Item "$App\.env.example" "$App\.env"
  $lines = Get-Content "$App\.env"
  function SetKey($k,$v){ $script:lines = $script:lines | ForEach-Object { if ($_ -match "^$k=") { "$k=$v" } else { $_ } } }
  function AskSecret($prompt){ $s = Read-Host $prompt -AsSecureString; [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)) }
  $secret = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 48 | ForEach-Object {[char]$_})
  SetKey "BB_SESSION_SECRET" $secret
  $u = Read-Host "Owner username (Enter = royal)"; if (-not $u) { $u = "royal" }; SetKey "BB_USER" $u
  SetKey "BB_PASSWORD" (AskSecret "Owner password")
  Write-Host "Free keys: Groq console.groq.com/keys | Gemini aistudio.google.com/apikey | OpenRouter openrouter.ai/keys (Enter to skip)"
  SetKey "GROQ_API_KEY" (AskSecret "Groq API key")
  SetKey "GEMINI_API_KEY" (AskSecret "Gemini API key")
  SetKey "OPENROUTER_API_KEY" (AskSecret "OpenRouter API key")
  SetKey "RESEND_API_KEY" (AskSecret "Resend API key for login emails (optional)")
  $lines | Set-Content "$App\.env" -Encoding UTF8
  Write-Host ".env saved (edit later with Notepad)."
} else { Write-Host ".env already exists - kept." }

# 4. cloudflared
if (-not (Have "cloudflared")) {
  Write-Host "Installing cloudflared (winget)..."
  winget install -e --id Cloudflare.cloudflared --accept-package-agreements --accept-source-agreements
  Refresh-Path
}

# 5. Autostart at logon
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$App\start.bat`" hidden" -WorkingDirectory $App
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName "BanglaBhai" -Action $action -Trigger $trigger -Settings $settings -Description "Bangla Bhai app + Cloudflare tunnel" -Force | Out-Null
Write-Host "Autostart task 'BanglaBhai' registered." -ForegroundColor Green

Start-Process -FilePath "$App\start.bat" -WorkingDirectory $App
Write-Host "Done! Open http://127.0.0.1:8090 . For banglabhai.dpdns.org follow GUIDE_BN.md step 5." -ForegroundColor Green
