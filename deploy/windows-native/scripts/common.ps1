$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Script:ProgramFilesDir = ${env:PICOPOS_PROGRAM_FILES_DIR}
if ([string]::IsNullOrWhiteSpace($Script:ProgramFilesDir)) { $Script:ProgramFilesDir = "C:\Program Files\PicoDeGallo" }
$Script:ProgramDataDir = ${env:PICOPOS_PROGRAM_DATA_DIR}
if ([string]::IsNullOrWhiteSpace($Script:ProgramDataDir)) { $Script:ProgramDataDir = "C:\ProgramData\PicoDeGallo" }
$Script:Services = @('PicoDeGallo-PostgreSQL','PicoDeGallo-Backend','PicoDeGallo-DTE-Worker','PicoDeGallo-DTE-Monitor','PicoDeGallo-Caddy')
function Get-EnvPath { Join-Path $Script:ProgramDataDir 'config\.env' }
function Get-LogsDir { Join-Path $Script:ProgramDataDir 'logs' }
function Get-BackupsDir { Join-Path $Script:ProgramDataDir 'backups' }
function Get-DiagnosticsDir { Join-Path $Script:ProgramDataDir 'diagnostics' }
function New-DirectorySafe([string]$Path) { if (-not (Test-Path -LiteralPath $Path)) { New-Item -ItemType Directory -Path $Path -Force | Out-Null } }
function Read-NativeEnv { $map=[ordered]@{}; $path=Get-EnvPath; if (-not (Test-Path $path)) { return $map }; Get-Content $path -Encoding UTF8 | ForEach-Object { $line=$_.Trim(); if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) { $p=$line.Split('=',2); $map[$p[0].Trim()]=$p[1].Trim() } }; return $map }
function New-RandomSecret([int]$Bytes=32) { $bytes=New-Object byte[] $Bytes; $rng=[System.Security.Cryptography.RandomNumberGenerator]::Create(); try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }; [Convert]::ToBase64String($bytes).Replace('+','-').Replace('/','_').TrimEnd('=') }
function Write-NativeEnv([System.Collections.IDictionary]$Map) { New-DirectorySafe (Split-Path (Get-EnvPath) -Parent); $lines=@(); foreach($k in $Map.Keys){$lines += "$k=$($Map[$k])"}; [System.IO.File]::WriteAllLines((Get-EnvPath), $lines, [System.Text.UTF8Encoding]::new($false)) }
function Protect-Text([string]$Text) { if ($null -eq $Text) { return '' }; $out=$Text; foreach($p in @('(?i)(password\s*[=:]\s*)[^\s]+','(?i)(secret\s*[=:]\s*)[^\s]+','(?i)(token\s*[=:]\s*)[^\s]+','(Authorization:\s*Bearer\s+)[^\s]+','(Bearer\s+)[A-Za-z0-9._~+/-]+')) { $out=[regex]::Replace($out,$p,'$1***REDACTED***') }; return $out }
function Write-SafeHost([string]$Message) { Write-Host (Protect-Text $Message) }
function Assert-Admin { $id=[Security.Principal.WindowsIdentity]::GetCurrent(); $principal=[Security.Principal.WindowsPrincipal]::new($id); if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Ejecuta como Administrador.' } }
function Get-ServiceSafe([string]$Name) { Get-Service -Name $Name -ErrorAction SilentlyContinue }
function Get-AppUrl { $envs=Read-NativeEnv; $port= if ($envs.Contains('APP_HTTP_PORT')) { $envs['APP_HTTP_PORT'] } else { '9282' }; "http://127.0.0.1:$port" }
function Test-DteEnv { $envs=Read-NativeEnv; if ($envs['DTE_BACKGROUND_MODE'] -ne 'external') { throw 'DTE_BACKGROUND_MODE debe ser external.' }; if ([string]::IsNullOrWhiteSpace($envs['DTE_BASE_URL'])) { throw 'DTE_BASE_URL no puede quedar vacío.' }; if ([string]::IsNullOrWhiteSpace($envs['DTE_API_TOKEN'])) { throw 'DTE_API_TOKEN no puede quedar vacío.' }; return $true }
