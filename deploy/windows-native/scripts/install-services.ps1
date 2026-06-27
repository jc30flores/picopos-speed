. "$PSScriptRoot\common.ps1"
Assert-Admin
foreach($dir in @('config','media','static','dte_logs','backups','diagnostics','logs','postgres-data')){ New-DirectorySafe (Join-Path $Script:ProgramDataDir $dir) }
if (-not (Test-Path (Get-EnvPath))) { & "$PSScriptRoot\init-env.ps1" }
Test-DteEnv | Out-Null
Write-Warning 'Este script registra servicios cuando WinSW y los binarios ya fueron incluidos por package-release. No descarga binarios.'
foreach($svc in $Script:Services){ Write-SafeHost "Servicio previsto: $svc" }
