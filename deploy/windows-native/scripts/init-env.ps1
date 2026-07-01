param(
    [switch]$Force,
    [string]$DteBaseUrl = "replace-with-dte-api-base-url",
    [string]$DteApiToken = "replace-with-dte-api-token"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

$target = Get-EnvPath
New-DirectorySafe (Get-LogsDir)
Write-NativeLog -LogName "init-env.log" -Message "INIT_ENV_BEGIN target=$target"

if ((Test-Path -LiteralPath $target -PathType Leaf) -and -not $Force) {
    Write-NativeLog -LogName "init-env.log" -Message "INIT_ENV_EXISTS target=$target"
    throw "El archivo de configuracion ya existe. Usa -Force para regenerar."
}

$template = Join-Path $Script:ProgramFilesDir ".env.windows.example"
if (-not (Test-Path -LiteralPath $template -PathType Leaf)) {
    $template = Join-Path (Split-Path $PSScriptRoot -Parent) ".env.windows.example"
}
if (-not (Test-Path -LiteralPath $template -PathType Leaf)) {
    throw "No existe template .env.windows.example."
}

$map = [ordered]@{}
Get-Content -LiteralPath $template -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $parts = $line.Split("=", 2)
        $map[$parts[0].Trim()] = $parts[1].Trim()
    }
}

$map["DJANGO_SECRET_KEY"] = "django-insecure-" + (New-RandomSecret 48)
$map["DB_PASSWORD"] = New-RandomSecret 36
$map["DB_HOST"] = "127.0.0.1"
$map["DB_PORT"] = "5432"
$map["DB_NAME"] = "picopos"
$map["DB_USER"] = "picopos"
$map["PICO_PORT_MODE"] = "auto"
$map["BACKEND_HTTP_PORT"] = "8000"
$map["APP_HTTP_PORT"] = "9282"
$map["APP_BIND_ADDRESS"] = "127.0.0.1"
$map["DTE_BACKGROUND_MODE"] = "external"
$map["DTE_BASE_URL"] = $DteBaseUrl
$map["DTE_API_TOKEN"] = $DteApiToken
$map["PICO_BOOTSTRAP_ADMIN_ENABLED"] = "true"
$map["PICO_BOOTSTRAP_ADMIN_USERNAME"] = "admin"
$map["PICO_BOOTSTRAP_ADMIN_PASSWORD"] = "000000"

Write-NativeEnv $map
Write-NativeLog -LogName "init-env.log" -Message "INIT_ENV_SUCCESS target=$target"
Write-SafeHost "Configuracion nativa creada en $target. Reemplaza placeholders DTE y admin de prueba antes de produccion."
