. "$PSScriptRoot\common.ps1"
$envs = Read-EnvFile
Write-SafeHost "Fecha: $(Get-Date -Format o)"
Write-SafeHost "Docker CLI: $(if (Test-CommandExists docker) { 'available' } else { 'missing' })"
Write-SafeHost "Proyecto Compose: $(Get-EnvValue 'COMPOSE_PROJECT_NAME' 'picopos_docker')"
Write-SafeHost "Puerto local: $(Get-EnvValue 'APP_HTTP_PORT' '9282')"
Write-SafeHost "URL: http://$(Get-EnvValue 'APP_BIND_ADDRESS' '127.0.0.1'):$(Get-EnvValue 'APP_HTTP_PORT' '9282')"
foreach ($name in @('DTE_BACKGROUND_MODE','DTE_MONITOR_ENABLED','DTE_OUTBOX_WORKER_ENABLED','DTE_SENTINEL_ENABLED','DTE_MAX_RETRIES')) { Write-SafeHost "$name=$($envs[$name])" }
$dte = Get-DteStatus $envs
Write-SafeHost "DTE_BASE_URL=$($dte.BaseUrlState)"
Write-SafeHost "DTE_API_TOKEN=$($dte.TokenState)"
if (Test-CommandExists docker) { Invoke-DockerCompose @('ps') | Out-Null }
foreach ($path in @('/api/health/live/','/api/health/ready/')) { Write-SafeHost "HTTP $path => $(Invoke-HealthRequest $path)" }
$lastBackup = Get-ChildItem -LiteralPath (Get-BackupRoot) -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($lastBackup) { Write-SafeHost "Último backup: $($lastBackup.Name)" } else { Write-SafeHost 'Último backup: none' }
