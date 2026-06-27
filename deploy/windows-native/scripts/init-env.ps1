param([switch]$Force,[string]$DteBaseUrl='replace-with-dte-api-base-url',[string]$DteApiToken='replace-with-dte-api-token')
. "$PSScriptRoot\common.ps1"
$target=Get-EnvPath
if ((Test-Path $target) -and -not $Force) { throw 'El archivo de configuración ya existe. Usa -Force para regenerar.' }
$template=Join-Path $Script:ProgramFilesDir '.env.windows.example'
if (-not (Test-Path $template)) { $template=Join-Path (Split-Path $PSScriptRoot -Parent) '.env.windows.example' }
$map=[ordered]@{}
Get-Content $template -Encoding UTF8 | ForEach-Object { $line=$_.Trim(); if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) { $p=$line.Split('=',2); $map[$p[0]]=$p[1] } }
$db=New-RandomSecret 36
$map['DJANGO_SECRET_KEY']='django-insecure-'+(New-RandomSecret 48)
$map['DB_PASSWORD']=$db
$map['DTE_BACKGROUND_MODE']='external'
$map['DTE_BASE_URL']=$DteBaseUrl
$map['DTE_API_TOKEN']=$DteApiToken
Write-NativeEnv $map
Write-SafeHost "Configuración nativa creada en $target. Reemplaza placeholders DTE antes de producción."
