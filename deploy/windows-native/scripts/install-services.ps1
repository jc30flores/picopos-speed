. "$PSScriptRoot\common.ps1"
Assert-Admin
foreach($dir in @('config','media','static','dte_logs','backups','diagnostics','logs','postgres\data')){ New-DirectorySafe (Join-Path $Script:ProgramDataDir $dir) }
if (-not (Test-Path (Get-EnvPath))) { & "$PSScriptRoot\init-env.ps1" }
Test-DteEnv | Out-Null
$postgresBin = Join-Path $Script:ProgramFilesDir 'postgres\bin'
$dataDir = Join-Path $Script:ProgramDataDir 'postgres\data'
$initdb = Join-Path $postgresBin 'initdb.exe'
$psql = Join-Path $postgresBin 'psql.exe'
if ((Test-Path $initdb) -and -not (Test-Path (Join-Path $dataDir 'PG_VERSION'))) {
    & $initdb -D $dataDir -E UTF8 --locale=C
    if ($LASTEXITCODE -ne 0) { throw 'initdb falló.' }
}
$template = Join-Path $Script:ProgramFilesDir 'caddy\Caddyfile.template'
$caddyfile = Join-Path $Script:ProgramFilesDir 'caddy\Caddyfile'
if (Test-Path $template) {
    $envs = Read-NativeEnv
    (Get-Content $template -Raw).Replace('{{APP_BIND_ADDRESS}}',$envs['APP_BIND_ADDRESS']).Replace('{{APP_HTTP_PORT}}',$envs['APP_HTTP_PORT']).Replace('{{PROGRAM_FILES_DIR}}',$Script:ProgramFilesDir.Replace('\\','/')).Replace('{{PROGRAM_DATA_DIR}}',$Script:ProgramDataDir.Replace('\\','/')) | Set-Content $caddyfile -Encoding UTF8
}
$python = Join-Path $Script:ProgramFilesDir 'python\python.exe'
$backend = Join-Path $Script:ProgramFilesDir 'backend'
if (Test-Path $python) {
    Push-Location $backend
    & $python manage.py check_runtime_config --strict
    & $python manage.py migrate --noinput
    & $python manage.py collectstatic --noinput
    Pop-Location
}
Write-Warning 'Este script registra/actualiza servicios cuando WinSW y los binarios ya fueron incluidos por package-release. No descarga binarios.'
foreach($svc in $Script:Services){ Write-SafeHost "Servicio previsto: $svc" }
