. "$PSScriptRoot\common.ps1"
$stamp=Get-Date -Format 'yyyy-MM-dd-HHmmss'
$root=Join-Path (Get-DiagnosticsDir) "diag-$stamp"
New-DirectorySafe $root
function Save([string]$Name,[string]$Text){ Set-Content (Join-Path $root $Name) -Value (Protect-Text $Text) -Encoding UTF8 }
Save 'windows.txt' ([Environment]::OSVersion.VersionString)
Save 'powershell.txt' ($PSVersionTable | Out-String)
$serviceLines = foreach ($svc in $Script:Services) {
    $s = Get-ServiceSafe $svc
    if ($s) {
        "$svc $($s.Status)"
    } else {
        "$svc not-installed"
    }
}
Save 'services.txt' ($serviceLines -join "`n")
Save 'status.txt' ((& "$PSScriptRoot\status.ps1" 2>&1 | ForEach-Object { [string]$_ }) -join "`n")
$envs=Read-NativeEnv; $safe=[ordered]@{ APP_HTTP_PORT=$envs['APP_HTTP_PORT']; APP_BIND_ADDRESS=$envs['APP_BIND_ADDRESS']; DTE_BACKGROUND_MODE=$envs['DTE_BACKGROUND_MODE']; DTE_MONITOR_ENABLED=$envs['DTE_MONITOR_ENABLED']; DTE_OUTBOX_WORKER_ENABLED=$envs['DTE_OUTBOX_WORKER_ENABLED']; DTE_BASE_URL=$(if($envs['DTE_BASE_URL'] -like 'replace-with-*'){'placeholder'}else{'configured'}); DTE_API_TOKEN=$(if($envs['DTE_API_TOKEN'] -like 'replace-with-*'){'placeholder'}else{'configured'}) }
Save 'config-safe.json' ($safe | ConvertTo-Json -Depth 3)
foreach($log in Get-ChildItem (Get-LogsDir) -Filter '*.log' -ErrorAction SilentlyContinue){ Save "log-$($log.Name).txt" ((Get-Content $log.FullName -Tail 300) -join "`n") }
$zip=Join-Path (Get-DiagnosticsDir) "PicoDeGallo-Native-Diagnostico-$stamp.zip"
Compress-Archive -Path (Join-Path $root '*') -DestinationPath $zip -Force
Remove-Item $root -Recurse -Force
Write-SafeHost "Diagnóstico generado: $zip"
