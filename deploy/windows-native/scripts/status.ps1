. "$PSScriptRoot\common.ps1"
Write-SafeHost "URL: $(Get-AppUrl)"
foreach($svc in $Script:Services){ $s=Get-ServiceSafe $svc; if($s){ Write-SafeHost "$svc=$($s.Status)" } else { Write-SafeHost "$svc=not-installed" } }
$envs=Read-NativeEnv; Write-SafeHost "DTE_BACKGROUND_MODE=$($envs['DTE_BACKGROUND_MODE'])"; Write-SafeHost "DTE_BASE_URL=$(if($envs['DTE_BASE_URL'] -like 'replace-with-*'){'placeholder'}else{'configured'})"; Write-SafeHost "DTE_API_TOKEN=$(if($envs['DTE_API_TOKEN'] -like 'replace-with-*'){'placeholder'}else{'configured'})"
