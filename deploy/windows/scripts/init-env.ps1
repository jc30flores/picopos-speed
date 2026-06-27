param(
    [int]$AppHttpPort = 9282,
    [string]$BindAddress = "127.0.0.1",
    [string]$DteBaseUrl = "replace-with-dte-api-base-url",
    [string]$DteApiToken = "replace-with-dte-api-token",
    [switch]$Force,
    [switch]$UsePlaceholders
)
. "$PSScriptRoot\common.ps1"
Assert-PowerShell
$envPath = Get-EnvPath
$example = Get-EnvExamplePath
if ((Test-Path $envPath) -and -not $Force) { throw ".env.docker ya existe. Usa -Force para regenerarlo." }
if (-not (Test-Path $example)) { throw "No existe .env.docker.example." }
if (-not $UsePlaceholders -and (($DteBaseUrl -like 'replace-with-*') -or ($DteApiToken -like 'replace-with-*'))) {
    Write-Warning 'Se usarán placeholders DTE. Esta configuración no es válida para producción DTE.'
}
$dbPassword = New-RandomSecret 36
$map = Read-EnvFile $example
$map['APP_HTTP_PORT'] = [string]$AppHttpPort
$map['APP_BIND_ADDRESS'] = $BindAddress
$map['DJANGO_SECRET_KEY'] = New-DjangoSecretKey
$map['DB_PASSWORD'] = $dbPassword
$map['POSTGRES_PASSWORD'] = $dbPassword
$map['DTE_BACKGROUND_MODE'] = 'external'
$map['DTE_BASE_URL'] = $DteBaseUrl
$map['DTE_API_TOKEN'] = $DteApiToken
$map['DTE_MONITOR_ENABLED'] = 'true'
$map['DTE_OUTBOX_WORKER_ENABLED'] = 'true'
$map['DTE_SENTINEL_ENABLED'] = 'true'
$map['DTE_MAX_RETRIES'] = '5'
Write-EnvMap $map $envPath
if (-not (Test-EnvIgnoredByGit)) { throw '.env.docker no está ignorado por Git.' }
if ($map['DB_PASSWORD'] -ne $map['POSTGRES_PASSWORD']) { throw 'DB_PASSWORD y POSTGRES_PASSWORD no coinciden.' }
if ([string]::IsNullOrWhiteSpace($map['DTE_BASE_URL']) -or [string]::IsNullOrWhiteSpace($map['DTE_API_TOKEN'])) { throw 'DTE_BASE_URL y DTE_API_TOKEN no pueden quedar vacíos.' }
Write-SafeHost 'Archivo .env.docker creado correctamente.'
Write-SafeHost 'DTE está configurado para ejecutarse como worker externo.'
Write-SafeHost 'Antes de producción, reemplaza los placeholders DTE por valores reales si aún no lo hiciste.'
Write-SafeHost "Puerto local: http://127.0.0.1:$AppHttpPort"
