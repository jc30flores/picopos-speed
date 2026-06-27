. "$PSScriptRoot\common.ps1"
Assert-PowerShell
New-DirectorySafe (Get-RuntimeDir)
$log = Join-Path (Get-RuntimeDir) 'preflight.log'
$results = New-Object System.Collections.Generic.List[string]
function Add-Result([string]$Text) { $results.Add((Protect-LogText $Text)); Write-Host (Protect-LogText $Text) }
try {
    $platform = [System.Environment]::OSVersion.Platform
    if ($platform -ne [System.PlatformID]::Win32NT) { Add-Result 'WARN: este preflight está diseñado para Windows.' }
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Windows 64 bits es requerido.' }
    if (-not (Test-CommandExists docker)) { throw 'Docker no está disponible. Instala Docker Desktop, activa WSL2 si Windows lo solicita, reinicia la PC si es necesario y vuelve a ejecutar este script.' }
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Docker no está disponible. Instala Docker Desktop, activa WSL2 si Windows lo solicita, reinicia la PC si es necesario y vuelve a ejecutar este script.' }
    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose no está disponible.' }
    $root = Get-RepoRoot
    foreach ($file in @('compose.yaml','compose.build.yaml','compose.windows.yaml')) { if (-not (Test-Path (Join-Path $root $file))) { throw "Falta $file" } }
    if (-not (Test-Path (Get-EnvPath))) { throw 'Falta .env.docker. Ejecuta deploy/windows/scripts/init-env.ps1.' }
    $envs = Read-EnvFile
    $portValue = if ($envs.Contains('APP_HTTP_PORT')) { $envs['APP_HTTP_PORT'] } else { '9282' }
    $bind = if ($envs.Contains('APP_BIND_ADDRESS')) { [string]$envs['APP_BIND_ADDRESS'] } else { '127.0.0.1' }
    $port = [int]$portValue
    if ($bind -notin @('127.0.0.1','0.0.0.0')) { throw 'APP_BIND_ADDRESS debe ser 127.0.0.1 u 0.0.0.0.' }
    if (-not (Test-PortAvailable $port $(if ($bind -eq '0.0.0.0') { '127.0.0.1' } else { $bind }))) { Add-Result "WARN: puerto $port parece ocupado." }
    if (-not (Test-EnvIgnoredByGit)) { throw '.env.docker no está ignorado por Git.' }
    $drive = Get-PSDrive -Name ((Get-RepoRoot).Substring(0,1)) -ErrorAction SilentlyContinue
    if ($drive -and $drive.Free -lt 5GB) { Add-Result 'WARN: espacio libre menor a 5GB.' }
    Add-Result 'OK: preflight completado.'
    $results | Set-Content -LiteralPath $log -Encoding UTF8
    exit 0
} catch {
    Add-Result "ERROR: $($_.Exception.Message)"
    $results | Set-Content -LiteralPath $log -Encoding UTF8
    exit 1
}
