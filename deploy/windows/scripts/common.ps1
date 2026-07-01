$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Script:WindowsDeployDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Script:DefaultProjectName = "picopos_docker"
$Script:RequiredPhrase = "BORRAR DATOS PICO DE GALLO"

function Get-RepoRoot {
    $dir = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
    return $dir.Path
}

function Get-EnvPath { Join-Path (Get-RepoRoot) ".env.docker" }
function Get-EnvExamplePath { Join-Path (Get-RepoRoot) ".env.docker.example" }
function Get-RuntimeDir { Join-Path (Get-RepoRoot) "deploy\windows\runtime" }
function Get-BackupRoot { Join-Path (Get-RepoRoot) "deploy\windows\backups" }
function Get-DiagnosticRoot { Join-Path (Get-RepoRoot) "deploy\windows\diagnostics" }

function New-DirectorySafe([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { New-Item -ItemType Directory -Path $Path -Force | Out-Null }
}

function Assert-PowerShell {
    if ($PSVersionTable.PSVersion.Major -lt 5) { throw "PowerShell 5 o superior es requerido." }
}

function Read-EnvFile([string]$Path = (Get-EnvPath)) {
    $map = [ordered]@{}
    if (-not (Test-Path -LiteralPath $Path)) { return $map }
    Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#') -or -not $line.Contains('=')) { return }
        $parts = $line.Split('=', 2)
        $map[$parts[0].Trim()] = $parts[1].Trim()
    }
    return $map
}

function Get-EnvValue([string]$Name, [string]$Default = "") {
    $envs = Read-EnvFile
    if ($envs.Contains($Name)) { return [string]$envs[$Name] }
    return $Default
}

function Write-EnvMap([System.Collections.IDictionary]$Map, [string]$Path = (Get-EnvPath)) {
    $lines = @()
    foreach ($key in $Map.Keys) { $lines += "$key=$($Map[$key])" }
    [System.IO.File]::WriteAllLines($Path, $lines, [System.Text.UTF8Encoding]::new($false))
}

function Set-EnvValue([string]$Name, [string]$Value, [string]$Path = (Get-EnvPath)) {
    $map = Read-EnvFile $Path
    $map[$Name] = $Value
    Write-EnvMap $map $Path
}

function New-RandomSecret([int]$Bytes = 32) {
    $bytes = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($bytes).Replace('+','-').Replace('/','_').TrimEnd('=')
}

function New-DjangoSecretKey {
    return "django-insecure-$(New-RandomSecret 48)"
}

function Protect-LogText([string]$Text) {
    if ($null -eq $Text) { return "" }
    $patterns = @(
        '(DJANGO_SECRET_KEY\s*[=:]\s*)[^\s]+', '(DB_PASSWORD\s*[=:]\s*)[^\s]+', '(POSTGRES_PASSWORD\s*[=:]\s*)[^\s]+',
        '(DTE_API_TOKEN\s*[=:]\s*)[^\s]+', '(DTE_BRIDGE_TOKEN\s*[=:]\s*)[^\s]+', '(DELIVER_EMAIL_API_KEY\s*[=:]\s*)[^\s]+',
        '(EMAIL_API_KEY\s*[=:]\s*)[^\s]+', '(WHATSAPP_DTE_API_KEY\s*[=:]\s*)[^\s]+', '(WHATSAPP_API_KEY\s*[=:]\s*)[^\s]+',
        '(Authorization:\s*Bearer\s+)[^\s]+', '(Bearer\s+)[A-Za-z0-9._~+/-]+', '(?i)(token\s*[=:]\s*)[^\s]+',
        '(?i)(password\s*[=:]\s*)[^\s]+', '(?i)(secret\s*[=:]\s*)[^\s]+'
    )
    $out = $Text
    foreach ($pattern in $patterns) { $out = [regex]::Replace($out, $pattern, '$1***REDACTED***') }
    return $out
}

function Write-SafeHost([string]$Message) { Write-Host (Protect-LogText $Message) }

function Get-ComposeArgs([switch]$UseLocalBuild) {
    $root = Get-RepoRoot
    $args = @('compose', '--env-file', (Get-EnvPath), '-f', (Join-Path $root 'compose.yaml'))
    if ($UseLocalBuild) { $args += @('-f', (Join-Path $root 'compose.build.yaml')) }
    $args += @('-f', (Join-Path $root 'compose.windows.yaml'))
    return $args
}

function Invoke-DockerCompose([string[]]$Arguments, [switch]$UseLocalBuild, [switch]$Capture) {
    $args = (Get-ComposeArgs -UseLocalBuild:$UseLocalBuild) + $Arguments
    if ($Capture) { return (& docker @args 2>&1 | ForEach-Object { Protect-LogText ([string]$_) }) }
    & docker @args 2>&1 | ForEach-Object { Write-Host (Protect-LogText ([string]$_)) }
    if ($LASTEXITCODE -ne 0) { throw "docker compose falló con código $LASTEXITCODE" }
}

function Test-CommandExists([string]$Name) {
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-PortAvailable([int]$Port, [string]$BindAddress = '127.0.0.1') {
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse($BindAddress), $Port)
        $listener.Start(); $listener.Stop(); return $true
    } catch { return $false }
}

function Test-EnvIgnoredByGit {
    $root = Get-RepoRoot
    Push-Location $root
    try {
        & git check-ignore .env.docker *> $null
        return ($LASTEXITCODE -eq 0)
    } finally { Pop-Location }
}

function Get-DteStatus([System.Collections.IDictionary]$EnvMap) {
    $base = [string]$EnvMap['DTE_BASE_URL']
    $token = [string]$EnvMap['DTE_API_TOKEN']
    return [pscustomobject]@{
        BaseUrlState = $(if ([string]::IsNullOrWhiteSpace($base)) { 'empty' } elseif ($base -eq 'replace-with-dte-api-base-url') { 'placeholder' } else { 'configured' })
        TokenState = $(if ([string]::IsNullOrWhiteSpace($token)) { 'empty' } elseif ($token -eq 'replace-with-dte-api-token') { 'placeholder' } else { 'configured' })
    }
}

function Test-DteConfiguration([switch]$AllowPlaceholders) {
    $envs = Read-EnvFile
    $errors = @()
    if (($envs['DTE_BACKGROUND_MODE'] -ne 'external')) { $errors += 'DTE_BACKGROUND_MODE debe ser external.' }
    foreach ($name in @('DTE_MONITOR_ENABLED','DTE_OUTBOX_WORKER_ENABLED','DTE_SENTINEL_ENABLED')) {
        if (($envs[$name] -notin @('true','false','True','False','1','0'))) { $errors += "$name debe ser booleano." }
    }
    $retryValue = 0
    if (-not ([int]::TryParse([string]$envs['DTE_MAX_RETRIES'], [ref]$retryValue))) { $errors += 'DTE_MAX_RETRIES debe ser entero.' }
    $status = Get-DteStatus $envs
    if ($status.BaseUrlState -eq 'empty') { $errors += 'DTE_BASE_URL no puede quedar vacío.' }
    if ($status.TokenState -eq 'empty') { $errors += 'DTE_API_TOKEN no puede quedar vacío.' }
    if (-not $AllowPlaceholders -and $status.BaseUrlState -eq 'placeholder') { $errors += 'DTE_BASE_URL todavía tiene placeholder.' }
    if (-not $AllowPlaceholders -and $status.TokenState -eq 'placeholder') { $errors += 'DTE_API_TOKEN todavía tiene placeholder.' }
    if ($errors.Count -gt 0) { throw ($errors -join [Environment]::NewLine) }
    if ($AllowPlaceholders -and ($status.BaseUrlState -eq 'placeholder' -or $status.TokenState -eq 'placeholder')) {
        Write-Warning 'Esta ejecución no es válida para producción DTE.'
    }
    return $true
}

function Wait-ComposeHealthy([int]$Seconds = 180, [switch]$UseLocalBuild) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        $ps = Invoke-DockerCompose @('ps') -UseLocalBuild:$UseLocalBuild -Capture
        $text = ($ps -join "`n")
        if ($text -match 'backend.*healthy' -and $text -match 'web.*healthy' -and $text -match 'db.*healthy') { return $true }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)
    throw 'Los servicios no llegaron a healthy dentro del tiempo esperado.'
}

function Invoke-HealthRequest([string]$Path) {
    $port = Get-EnvValue 'APP_HTTP_PORT' '9282'
    $url = "http://127.0.0.1:$port$Path"
    try { return (Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 10).StatusCode } catch { return "ERROR" }
}

function Confirm-Danger([string]$Prompt, [string]$Expected) {
    $answer = Read-Host $Prompt
    return ($answer -eq $Expected)
}
