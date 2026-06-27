param([switch]$UseLocalBuild)
. "$PSScriptRoot\common.ps1"
New-DirectorySafe (Get-BackupRoot)
Write-Warning 'Si dte-worker está procesando documentos, este backup es en caliente. Para un backup completamente quieto, detén temporalmente servicios después de confirmar que no hay envíos DTE en curso.'
$stamp = Get-Date -Format 'yyyy-MM-dd-HHmmss'
$dir = Join-Path (Get-BackupRoot) "PicoDeGallo-Backup-$stamp"
New-DirectorySafe $dir
$envs = Read-EnvFile
$project = Get-EnvValue 'COMPOSE_PROJECT_NAME' $Script:DefaultProjectName
Invoke-DockerCompose @('ps') -UseLocalBuild:$UseLocalBuild | Out-Null
Invoke-DockerCompose @('exec','-T','db','sh','-c','pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"') -UseLocalBuild:$UseLocalBuild -Capture | Set-Content -LiteralPath (Join-Path $dir 'postgres.dump.sql') -Encoding UTF8
& docker run --rm -v "${project}_media_data:/data:ro" -v "${dir}:/backup" alpine:3.20 sh -c 'tar -C /data -czf /backup/media.tar.gz .'
if ($LASTEXITCODE -ne 0) { throw 'No se pudo respaldar media_data.' }
& docker run --rm -v "${project}_dte_logs:/data:ro" -v "${dir}:/backup" alpine:3.20 sh -c 'tar -C /data -czf /backup/dte_logs.tar.gz .'
if ($LASTEXITCODE -ne 0) { throw 'No se pudo respaldar dte_logs.' }
$manifest = [ordered]@{ created_at=(Get-Date -Format o); app_version=$envs['APP_VERSION']; compose_project=$project; services=@('db','bootstrap','backend','web','dte-worker','dte-monitor'); dte_background_mode=$envs['DTE_BACKGROUND_MODE']; dte_monitor_enabled=$envs['DTE_MONITOR_ENABLED']; dte_outbox_worker_enabled=$envs['DTE_OUTBOX_WORKER_ENABLED']; dte_sentinel_enabled=$envs['DTE_SENTINEL_ENABLED']; hot_backup=$true }
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $dir 'manifest.json') -Encoding UTF8
Write-SafeHost "Backup generado: $dir"
