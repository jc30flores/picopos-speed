param(
    [ValidateSet('backend','web','db','bootstrap','dte-worker','dte-monitor','all')][string]$Service = 'all',
    [int]$Tail = 200,
    [switch]$Follow,
    [switch]$UseLocalBuild
)
. "$PSScriptRoot\common.ps1"
$args = @('logs','--no-color','--tail', [string]$Tail)
if ($Follow) { $args += '-f' }
if ($Service -ne 'all') { $args += $Service }
Invoke-DockerCompose $args -UseLocalBuild:$UseLocalBuild | Out-Null
