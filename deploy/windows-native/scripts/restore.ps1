param([Parameter(Mandatory=$true)][string]$BackupPath)
. "$PSScriptRoot\common.ps1"
$backup=Resolve-Path $BackupPath
foreach($f in @('manifest.json','database.dump')){ if(-not(Test-Path (Join-Path $backup.Path $f))){ throw "Backup inválido: falta $f" } }
$answer=Read-Host 'Escribe RESTAURAR PICO DE GALLO para detener servicios y restaurar'
if($answer -ne 'RESTAURAR PICO DE GALLO'){ throw 'Restore cancelado.' }
& "$PSScriptRoot\stop.ps1"
$envs=Read-NativeEnv
$pgRestore=Join-Path $Script:ProgramFilesDir 'postgres\bin\pg_restore.exe'
$psql=Join-Path $Script:ProgramFilesDir 'postgres\bin\psql.exe'
if (-not (Test-Path $pgRestore)) { throw 'No existe pg_restore.exe.' }
& $psql -h $envs['DB_HOST'] -p $envs['DB_PORT'] -U $envs['DB_USER'] -d postgres -c "DROP DATABASE IF EXISTS $($envs['DB_NAME']);"
& $psql -h $envs['DB_HOST'] -p $envs['DB_PORT'] -U $envs['DB_USER'] -d postgres -c "CREATE DATABASE $($envs['DB_NAME']);"
& $pgRestore -h $envs['DB_HOST'] -p $envs['DB_PORT'] -U $envs['DB_USER'] -d $envs['DB_NAME'] (Join-Path $backup.Path 'database.dump')
Copy-Item (Join-Path $backup.Path 'media') (Join-Path $Script:ProgramDataDir 'media') -Recurse -Force
Copy-Item (Join-Path $backup.Path 'dte_logs') (Join-Path $Script:ProgramDataDir 'dte_logs') -Recurse -Force
& "$PSScriptRoot\start.ps1"
Write-Warning 'Si la base restaurada tiene DTE pendientes y credenciales reales, el worker puede procesarlos al iniciar.'
