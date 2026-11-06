# One-click launcher for the four POCs (called by the .bat files next to this script).
# 1. Opens a Brave tab at once on a "Starting <name>" screen (start.html), which switches to the app the moment
#    its server answers. 2. Starts each server the app needs, hidden, only if it is not already running.
# Servers that are already up are reused, so a second click opens the app instantly.
# KPCL and RDPR are run from their own folders exactly as their handoff notes say, but with Python's bytecode cache
# switched off and the logs written here, so the launcher itself writes nothing into those read-only folders.
param([Parameter(Mandatory = $true)][ValidateSet('Mitra', 'WhatsApp', 'KPCL', 'RDPR')][string]$App, [switch]$NoWindow)   # -NoWindow: tests only

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Sakala = Split-Path -Parent $Here
$LogDir = Join-Path $env:LOCALAPPDATA 'POC Launchers\logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$POC = @{ Port = 8020; Dir = Join-Path $Sakala 'app'; Module = 'server.api:app'; Health = '/api/health'; Tag = 'sakala-poc'; ReadOnly = $false }
$Apps = @{
    Mitra    = @{ Name = 'Mitra'; Icon = 'mitra'; Accent = '#16c784'; Url = 'http://localhost:8030'; Ping = 'http://127.0.0.1:8030/api/health'
                  Servers = @($POC, @{ Port = 8030; Dir = Join-Path $Sakala 'mitra'; Module = 'server.main:app'; Health = '/api/health'; Tag = 'mitra'; ReadOnly = $false }) }
    WhatsApp = @{ Name = 'Sakala WhatsApp POC'; Icon = 'whatsapp_poc'; Accent = '#25d366'; Url = 'http://localhost:8020'; Ping = 'http://127.0.0.1:8020/api/health'
                  Servers = @($POC) }
    KPCL     = @{ Name = 'KPCL POC'; Icon = 'kpcl'; Accent = '#5b8fd9'; Url = 'http://127.0.0.1:8000/dashboard'; Ping = 'http://127.0.0.1:8000/health'
                  Servers = @(@{ Port = 8000; Dir = 'D:\KPCL POC\KPCL POC\webapp\kpcl-ai-app'; Module = 'app.main:app'; Health = '/health'; Tag = 'kpcl'; ReadOnly = $true }) }
    RDPR     = @{ Name = 'RDPR POC'; Icon = 'rdpr'; Accent = '#e9b949'; Url = 'http://127.0.0.1:8002/dashboard'; Ping = 'http://127.0.0.1:8002/health'
                  Servers = @(@{ Port = 8002; Dir = 'D:\RDPR POC\RDPR POC\ai_app'; Module = 'app.main:app'; Health = '/health'; Tag = 'rdpr'; ReadOnly = $true }) }
}
$A = $Apps[$App]
function Log([string]$m) { Add-Content -Path (Join-Path $LogDir 'launcher.log') -Value ("{0:yyyy-MM-dd HH:mm:ss.fff}  {1,-8} {2}" -f (Get-Date), $App, $m) -Encoding utf8 }
Log 'clicked'

function Test-Port([int]$Port) {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $iar = $c.BeginConnect('127.0.0.1', $Port, $null, $null); $ok = $iar.AsyncWaitHandle.WaitOne(150); if ($ok) { $c.EndConnect($iar) }; return $ok -and $c.Connected }
    catch { return $false } finally { $c.Close() }
}

# 1. the tab first: it shows "Starting ..." and switches to the app by itself
$q = 'name=' + [uri]::EscapeDataString($A.Name) + '&url=' + [uri]::EscapeDataString($A.Url) + '&ping=' + [uri]::EscapeDataString($A.Ping) +
     '&icon=' + [uri]::EscapeDataString("icons/$($A.Icon).png") + '&accent=' + [uri]::EscapeDataString($A.Accent) + '&log=' + [uri]::EscapeDataString($LogDir)
$splash = ([uri](Join-Path $Here 'start.html')).AbsoluteUri + '?' + $q
$already = $true
foreach ($s in $A.Servers) { if (-not (Test-Port $s.Port)) { $already = $false } }
$open = if ($already) { $A.Url } else { $splash }
# a Brave tab (F11 there = full screen); the default browser if Brave is not installed
$brave = @("$env:ProgramFiles\BraveSoftware\Brave-Browser\Application\brave.exe", "${env:ProgramFiles(x86)}\BraveSoftware\Brave-Browser\Application\brave.exe",
           "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\Application\brave.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
$what = if ($already) { 'the app (server already up)' } else { 'starting screen' }
if ($NoWindow) { }
elseif ($brave) { Start-Process -FilePath $brave -ArgumentList @($open); Log "Brave tab opened: $what" }
else { Start-Process $open; Log "default browser opened: $what" }

# 2. the servers, hidden, only those not already running
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
foreach ($s in $A.Servers) {
    if (Test-Port $s.Port) { continue }
    if (-not (Test-Path $s.Dir)) { continue }
    $env:PYTHONIOENCODING = 'utf-8'
    if ($s.ReadOnly) { $env:PYTHONDONTWRITEBYTECODE = '1' } else { Remove-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue }
    $out = Join-Path $LogDir "$($s.Tag).out.log"; $err = Join-Path $LogDir "$($s.Tag).err.log"
    Start-Process -FilePath $py -ArgumentList @('-m', 'uvicorn', $s.Module, '--host', '127.0.0.1', '--port', "$($s.Port)") `
        -WorkingDirectory $s.Dir -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err
    Log "started $($s.Tag) on port $($s.Port)"
}
