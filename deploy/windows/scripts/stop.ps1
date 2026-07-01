param([switch]$UseLocalBuild, [switch]$AllowDtePlaceholdersForLocalBuild)
. "$PSScriptRoot\common.ps1"
Invoke-DockerCompose @('down') -UseLocalBuild:$UseLocalBuild | Out-Null
Write-SafeHost 'Servicios detenidos. Los datos se conservaron.'
