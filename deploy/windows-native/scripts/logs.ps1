param([ValidateSet('backend','dte-worker','dte-monitor','caddy','postgres','all')][string]$Service='all',[int]$Tail=200)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"
$files = if($Service -eq 'all'){ Get-ChildItem (Get-LogsDir) -Filter '*.log' -ErrorAction SilentlyContinue } else { Get-ChildItem (Get-LogsDir) -Filter "*$Service*.log" -ErrorAction SilentlyContinue }
foreach($f in $files){ Write-SafeHost "--- $($f.Name) ---"; Get-Content $f.FullName -Tail $Tail | ForEach-Object { Write-SafeHost $_ } }
