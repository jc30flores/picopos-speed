param([switch]$UseLocalBuild, [switch]$AllowDtePlaceholdersForLocalBuild)
. "$PSScriptRoot\common.ps1"
if (-not (Test-Path (Get-EnvPath))) { throw 'Falta .env.docker. Ejecuta init-env.ps1.' }
Test-DteConfiguration -AllowPlaceholders:$AllowDtePlaceholdersForLocalBuild | Out-Null
Invoke-DockerCompose @('up','-d') -UseLocalBuild:$UseLocalBuild | Out-Null
Wait-ComposeHealthy -UseLocalBuild:$UseLocalBuild | Out-Null
Invoke-DockerCompose @('ps') -UseLocalBuild:$UseLocalBuild | Out-Null
Write-SafeHost "URL: http://$(Get-EnvValue 'APP_BIND_ADDRESS' '127.0.0.1'):$(Get-EnvValue 'APP_HTTP_PORT' '9282')"
