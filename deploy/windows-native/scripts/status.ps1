$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

function Test-TcpPort {
    param([string]$HostName = "127.0.0.1", [int]$Port = 9282)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne([TimeSpan]::FromSeconds(2))) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Get-HttpStatus {
    param([Parameter(Mandatory = $true)][string]$Uri)
    try {
        $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
        return [string]$response.StatusCode
    } catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            return [string][int]$_.Exception.Response.StatusCode
        }
        return "error"
    }
}

$envs = Read-NativeEnv
$appUrl = Get-AppUrl
$port = "9282"
if ($envs.Contains("APP_HTTP_PORT") -and -not [string]::IsNullOrWhiteSpace([string]$envs["APP_HTTP_PORT"])) {
    $port = [string]$envs["APP_HTTP_PORT"]
}

Write-SafeHost "URL: $appUrl"
foreach ($svc in $Script:Services) {
    $service = Get-ServiceSafe $svc
    if ($service) {
        Write-SafeHost "$svc=$($service.Status)"
    } else {
        Write-SafeHost "$svc=not-installed"
    }
}

$liveUrl = $appUrl + "/api/health/live/"
$readyUrl = $appUrl + "/api/health/ready/"
Write-SafeHost "PORT_$port=$(if (Test-TcpPort -Port ([int]$port)) { 'listening' } else { 'closed' })"
Write-SafeHost "HEALTH_LIVE=$(Get-HttpStatus -Uri $liveUrl)"
Write-SafeHost "HEALTH_READY=$(Get-HttpStatus -Uri $readyUrl)"
Write-SafeHost "DTE_BACKGROUND_MODE=$($envs['DTE_BACKGROUND_MODE'])"
Write-SafeHost "DTE_BASE_URL=$(if ($envs['DTE_BASE_URL'] -like 'replace-with-*') { 'placeholder' } else { 'configured' })"
Write-SafeHost "DTE_API_TOKEN=$(if ($envs['DTE_API_TOKEN'] -like 'replace-with-*') { 'placeholder' } else { 'configured' })"
Write-SafeHost "BOOTSTRAP_ADMIN_ENABLED=$(if ($envs['PICO_BOOTSTRAP_ADMIN_ENABLED'] -eq 'true') { 'yes' } else { 'no' })"
Write-SafeHost "BOOTSTRAP_ADMIN_USERNAME=$(if ([string]::IsNullOrWhiteSpace([string]$envs['PICO_BOOTSTRAP_ADMIN_USERNAME'])) { 'not-configured' } else { 'configured' })"
