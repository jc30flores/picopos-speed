param(
    [switch]$UseLocalBuild,
    [switch]$PullImages,
    [int]$AppHttpPort = 9282,
    [string]$BindAddress = '127.0.0.1',
    [switch]$SkipBuild,
    [switch]$AllowDtePlaceholdersForLocalBuild
)
. "$PSScriptRoot\common.ps1"
if (-not (Test-Path (Get-EnvPath))) { & "$PSScriptRoot\init-env.ps1" -AppHttpPort $AppHttpPort -BindAddress $BindAddress -UsePlaceholders }
& "$PSScriptRoot\preflight.ps1"
if ($LASTEXITCODE -ne 0) { throw 'Preflight falló.' }
Test-DteConfiguration -AllowPlaceholders:$AllowDtePlaceholdersForLocalBuild | Out-Null
Write-Warning 'Si hay documentos DTE pendientes y credenciales reales, dte-worker podría procesarlos al iniciar.'
Invoke-DockerCompose @('config') -UseLocalBuild:$UseLocalBuild | Out-Null
if ($PullImages) { Invoke-DockerCompose @('pull') | Out-Null }
if ($UseLocalBuild -and -not $SkipBuild) { Invoke-DockerCompose @('build') -UseLocalBuild | Out-Null }
Invoke-DockerCompose @('up','-d') -UseLocalBuild:$UseLocalBuild | Out-Null
Wait-ComposeHealthy -UseLocalBuild:$UseLocalBuild | Out-Null
Invoke-DockerCompose @('ps') -UseLocalBuild:$UseLocalBuild | Out-Null
foreach ($path in @('/','/api/health/live/','/api/health/ready/')) { Write-SafeHost "HTTP $path => $(Invoke-HealthRequest $path)" }
Write-SafeHost "Pico de Gallo disponible en http://$(Get-EnvValue 'APP_BIND_ADDRESS' '127.0.0.1'):$(Get-EnvValue 'APP_HTTP_PORT' '9282')"
