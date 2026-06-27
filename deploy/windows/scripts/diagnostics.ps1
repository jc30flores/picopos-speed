param([switch]$UseLocalBuild)
. "$PSScriptRoot\common.ps1"
New-DirectorySafe (Get-DiagnosticRoot)
$stamp = Get-Date -Format 'yyyy-MM-dd-HHmmss'
$tmp = Join-Path (Get-DiagnosticRoot) "diag-$stamp"
New-DirectorySafe $tmp
function Save-Text([string]$Name, [string]$Text) { Set-Content -LiteralPath (Join-Path $tmp $Name) -Value (Protect-LogText $Text) -Encoding UTF8 }
Save-Text 'windows.txt' ([System.Environment]::OSVersion.VersionString)
Save-Text 'powershell.txt' ($PSVersionTable | Out-String)
if (Test-CommandExists docker) {
    Save-Text 'docker-version.txt' ((& docker version 2>&1) -join "`n")
    Save-Text 'docker-compose-version.txt' ((& docker compose version 2>&1) -join "`n")
    Save-Text 'docker-info.txt' ((& docker info 2>&1) -join "`n")
    Save-Text 'compose-config.txt' ((Invoke-DockerCompose @('config') -UseLocalBuild:$UseLocalBuild -Capture) -join "`n")
    Save-Text 'compose-ps.txt' ((Invoke-DockerCompose @('ps') -UseLocalBuild:$UseLocalBuild -Capture) -join "`n")
    foreach ($svc in @('db','bootstrap','backend','web','dte-worker','dte-monitor')) { Save-Text "logs-$svc.txt" ((Invoke-DockerCompose @('logs','--no-color','--tail','300',$svc) -UseLocalBuild:$UseLocalBuild -Capture) -join "`n") }
}
Save-Text 'status.txt' ((& "$PSScriptRoot\status.ps1" 2>&1 | ForEach-Object { [string]$_ }) -join "`n")
Save-Text 'health.txt' ("/=$(Invoke-HealthRequest '/')`n/live=$(Invoke-HealthRequest '/api/health/live/')`n/ready=$(Invoke-HealthRequest '/api/health/ready/')")
$envs = Read-EnvFile
$nonSensitive = [ordered]@{}
foreach ($name in @('COMPOSE_PROJECT_NAME','APP_VERSION','APP_HTTP_PORT','APP_BIND_ADDRESS','DTE_BACKGROUND_MODE','DTE_MONITOR_ENABLED','DTE_OUTBOX_WORKER_ENABLED','DTE_SENTINEL_ENABLED','DTE_MAX_RETRIES','DJANGO_CONFIG_MODE','DJANGO_DEBUG','ALLOWED_HOSTS','CORS_ALLOWED_ORIGINS','CSRF_TRUSTED_ORIGINS','PRINTER_ENABLED','CASH_DRAWER_ENABLED')) { $nonSensitive[$name] = $envs[$name] }
$dte = Get-DteStatus $envs
$nonSensitive['DTE_BASE_URL'] = $dte.BaseUrlState
$nonSensitive['DTE_API_TOKEN'] = $dte.TokenState
Save-Text 'env-nonsensitive.json' ($nonSensitive | ConvertTo-Json -Depth 3)
$zip = Join-Path (Get-DiagnosticRoot) "PicoDeGallo-Diagnostico-$stamp.zip"
Compress-Archive -Path (Join-Path $tmp '*') -DestinationPath $zip -Force
Remove-Item -LiteralPath $tmp -Recurse -Force
Write-SafeHost "Diagnóstico generado: $zip"
