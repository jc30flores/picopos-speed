$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"
$stamp=Get-Date -Format 'yyyy-MM-dd-HHmmss'
$dir=Join-Path (Get-BackupsDir) "PicoDeGallo-Native-Backup-$stamp"
New-DirectorySafe $dir
$pgDump=Join-Path $Script:ProgramFilesDir 'postgres\bin\pg_dump.exe'
$envs=Read-NativeEnv
if (-not (Test-Path $pgDump)) { throw 'No existe pg_dump.exe en runtime PostgreSQL nativo.' }
& $pgDump -h $envs['DB_HOST'] -p $envs['DB_PORT'] -U $envs['DB_USER'] -d $envs['DB_NAME'] -Fc -f (Join-Path $dir 'database.dump')
Copy-Item (Join-Path $Script:ProgramDataDir 'media') (Join-Path $dir 'media') -Recurse -Force
Copy-Item (Join-Path $Script:ProgramDataDir 'dte_logs') (Join-Path $dir 'dte_logs') -Recurse -Force
@{createdAt=(Get-Date -Format o); services=$Script:Services; dteBackgroundMode=$envs['DTE_BACKGROUND_MODE']} | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $dir 'manifest.json') -Encoding UTF8
Write-SafeHost "Backup generado: $dir"
