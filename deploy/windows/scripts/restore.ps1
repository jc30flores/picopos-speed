param([Parameter(Mandatory=$true)][string]$BackupPath, [switch]$UseLocalBuild)
. "$PSScriptRoot\common.ps1"
$backup = Resolve-Path -LiteralPath $BackupPath
$manifestPath = Join-Path $backup.Path 'manifest.json'
if (-not (Test-Path $manifestPath)) { throw 'Backup inválido: falta manifest.json.' }
foreach ($file in @('postgres.dump.sql','media.tar.gz','dte_logs.tar.gz')) { if (-not (Test-Path (Join-Path $backup.Path $file))) { throw "Backup inválido: falta $file" } }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$project = Get-EnvValue 'COMPOSE_PROJECT_NAME' $Script:DefaultProjectName
Write-SafeHost "Backup: $($manifest.created_at) Proyecto: $($manifest.compose_project)"
Write-Warning 'Durante restore se detendrá el stack. Después de restaurar una base con DTE pendientes, el dte-worker podría procesarlos al iniciar si las credenciales DTE son reales.'
if (-not (Confirm-Danger 'Escribe RESTAURAR PICO DE GALLO para continuar' 'RESTAURAR PICO DE GALLO')) { throw 'Restauración cancelada.' }
Invoke-DockerCompose @('down') -UseLocalBuild:$UseLocalBuild | Out-Null
Invoke-DockerCompose @('up','-d','db') -UseLocalBuild:$UseLocalBuild | Out-Null
Start-Sleep -Seconds 10
Get-Content -LiteralPath (Join-Path $backup.Path 'postgres.dump.sql') | docker compose --env-file (Get-EnvPath) -f (Join-Path (Get-RepoRoot) 'compose.yaml') -f (Join-Path (Get-RepoRoot) 'compose.windows.yaml') exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB" && psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
if ($LASTEXITCODE -ne 0) { throw 'Restauración PostgreSQL falló.' }
& docker run --rm -v "${project}_media_data:/data" -v "$($backup.Path):/backup:ro" alpine:3.20 sh -c 'rm -rf /data/* && tar -C /data -xzf /backup/media.tar.gz'
if ($LASTEXITCODE -ne 0) { throw 'Restauración media_data falló.' }
& docker run --rm -v "${project}_dte_logs:/data" -v "$($backup.Path):/backup:ro" alpine:3.20 sh -c 'rm -rf /data/* && tar -C /data -xzf /backup/dte_logs.tar.gz'
if ($LASTEXITCODE -ne 0) { throw 'Restauración dte_logs falló.' }
Invoke-DockerCompose @('up','-d') -UseLocalBuild:$UseLocalBuild | Out-Null
Wait-ComposeHealthy -UseLocalBuild:$UseLocalBuild | Out-Null
Invoke-DockerCompose @('ps') -UseLocalBuild:$UseLocalBuild | Out-Null
Write-SafeHost 'Restore completado con verificación básica.'
