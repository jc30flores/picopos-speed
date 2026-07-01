$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Script:ProgramFilesDir = ${env:PICOPOS_PROGRAM_FILES_DIR}
if ([string]::IsNullOrWhiteSpace($Script:ProgramFilesDir)) {
    $Script:ProgramFilesDir = "C:\Program Files\PicoDeGallo"
}

$Script:ProgramDataDir = ${env:PICOPOS_PROGRAM_DATA_DIR}
if ([string]::IsNullOrWhiteSpace($Script:ProgramDataDir)) {
    $Script:ProgramDataDir = "C:\ProgramData\PicoDeGallo"
}

$Script:Services = @(
    "PicoDeGallo-PostgreSQL",
    "PicoDeGallo-Backend",
    "PicoDeGallo-DTE-Worker",
    "PicoDeGallo-DTE-Monitor",
    "PicoDeGallo-Caddy"
)
$Script:PicoServiceAccountName = "PicoDeGalloSvc"

function Get-EnvPath { Join-Path $Script:ProgramDataDir "config\.env" }
function Get-LogsDir { Join-Path $Script:ProgramDataDir "logs" }
function Get-BackupsDir { Join-Path $Script:ProgramDataDir "backups" }
function Get-DiagnosticsDir { Join-Path $Script:ProgramDataDir "diagnostics" }
function Get-InstallStatePath { Join-Path $Script:ProgramDataDir "install-state.json" }
function Get-RuntimePortsPath { Join-Path $Script:ProgramDataDir "config\runtime-ports.json" }

function New-DirectorySafe {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Protect-Text {
    param([string]$Text)

    if ($null -eq $Text) { return "" }
    $out = $Text
    $patterns = @(
        "(?i)(password\s*[=:]\s*)[^\s;]+",
        "(?i)(secret\s*[=:]\s*)[^\s;]+",
        "(?i)(token\s*[=:]\s*)[^\s;]+",
        "(?i)(DB_PASSWORD\s*[=:]\s*)[^\s;]+",
        "(?i)(DJANGO_SECRET_KEY\s*[=:]\s*)[^\s;]+",
        "(?i)(DTE_API_TOKEN\s*[=:]\s*)[^\s;]+",
        "(?i)(PICO_BOOTSTRAP_ADMIN_PASSWORD\s*[=:]\s*)[^\s;]+",
        "(Authorization:\s*Bearer\s+)[^\s]+",
        "(Bearer\s+)[A-Za-z0-9._~+/-]+"
    )
    foreach ($pattern in $patterns) {
        $out = [regex]::Replace($out, $pattern, '$1***REDACTED***')
    }
    $out = [regex]::Replace($out, "(?is)(<password>).*?(</password>)", '$1***REDACTED***$2')
    return $out
}

function Write-SafeHost {
    param([string]$Message)
    Write-Host (Protect-Text $Message)
}

function Write-NativeLog {
    param(
        [Parameter(Mandatory = $true)][string]$LogName,
        [Parameter(Mandatory = $true)][string]$Message
    )

    New-DirectorySafe (Get-LogsDir)
    $line = "[{0}] {1}" -f (Get-Date -Format o), (Protect-Text $Message)
    Add-Content -LiteralPath (Join-Path (Get-LogsDir) $LogName) -Value $line -Encoding UTF8
}

function ConvertTo-WindowsCommandLineArgument {
    param([AllowEmptyString()][string]$Argument)

    $text = [string]$Argument
    if ($text.Length -gt 0 -and $text -notmatch '[\s"]') {
        return $text
    }

    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $backslashes = 0
    foreach ($char in $text.ToCharArray()) {
        if ($char -eq '\') {
            $backslashes += 1
            continue
        }
        if ($char -eq '"') {
            if ($backslashes -gt 0) {
                [void]$builder.Append("\" * ($backslashes * 2))
                $backslashes = 0
            }
            [void]$builder.Append('\"')
            continue
        }
        if ($backslashes -gt 0) {
            [void]$builder.Append("\" * $backslashes)
            $backslashes = 0
        }
        [void]$builder.Append($char)
    }
    if ($backslashes -gt 0) {
        [void]$builder.Append("\" * ($backslashes * 2))
    }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Join-WindowsCommandLineArguments {
    param([string[]]$ArgumentList = @())

    $escaped = foreach ($arg in $ArgumentList) {
        ConvertTo-WindowsCommandLineArgument -Argument ([string]$arg)
    }
    return ($escaped -join " ")
}

function ConvertTo-CaddyPath {
    param([AllowEmptyString()][string]$Path)

    return ([string]$Path).Replace("\", "/")
}

function ConvertTo-CaddyfileLiteral {
    param([AllowEmptyString()][string]$Text)

    $value = [string]$Text
    $value = $value.Replace("\", "\\").Replace('"', '\"')
    return '"' + $value + '"'
}

function Quote-CaddyPath {
    param([AllowEmptyString()][string]$Path)

    return (ConvertTo-CaddyfileLiteral -Text (ConvertTo-CaddyPath -Path $Path))
}

function Get-SafeInstallProfileValue {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$ScriptBlock,
        [string]$Fallback = "unknown"
    )

    try {
        $value = & $ScriptBlock
        if ($null -eq $value) {
            return $Fallback
        }
        $text = [string]$value
        if ([string]::IsNullOrWhiteSpace($text)) {
            return $Fallback
        }
        return $text
    } catch {
        return $Fallback
    }
}

function Test-CommandAvailableForProfile {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (Get-Command $Name -ErrorAction SilentlyContinue) {
        return "true"
    }
    return "false"
}

function Test-ExecutableRunsForProfile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string[]]$ArgumentList = @("--version")
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return "missing"
    }

    $process = New-Object System.Diagnostics.Process
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Path
        $psi.Arguments = Join-WindowsCommandLineArguments -ArgumentList $ArgumentList
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $process.StartInfo = $psi
        [void]$process.Start()
        if (-not $process.WaitForExit(5000)) {
            try { $process.Kill() } catch { }
            return "timeout"
        }
        return ("exitCode={0}" -f [int]$process.ExitCode)
    } catch {
        return ("error={0}" -f $_.Exception.GetType().Name)
    } finally {
        if ($process) {
            $process.Dispose()
        }
    }
}

function Get-WindowsInstallProfile {
    $os = $null
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    } catch {
    }

    $profile = [ordered]@{}
    $profile["WindowsCaption"] = Get-SafeInstallProfileValue { if ($os) { $os.Caption } else { [Environment]::OSVersion.VersionString } }
    $profile["WindowsVersion"] = Get-SafeInstallProfileValue { if ($os) { $os.Version } else { [Environment]::OSVersion.Version.ToString() } }
    $profile["BuildNumber"] = Get-SafeInstallProfileValue { if ($os) { $os.BuildNumber } else { [Environment]::OSVersion.Version.Build } }
    $profile["EditionID"] = Get-SafeInstallProfileValue { (Get-ItemProperty -LiteralPath "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -ErrorAction Stop).EditionID }
    $profile["OSArchitecture"] = Get-SafeInstallProfileValue { if ($os) { $os.OSArchitecture } else { "" } }
    $profile["Is64BitOperatingSystem"] = [string][Environment]::Is64BitOperatingSystem
    $profile["Is64BitProcess"] = [string][Environment]::Is64BitProcess
    $profile["PowerShellVersion"] = Get-SafeInstallProfileValue { $PSVersionTable.PSVersion.ToString() }
    $profile["PowerShellEdition"] = Get-SafeInstallProfileValue {
        if ($PSVersionTable.ContainsKey("PSEdition")) { $PSVersionTable.PSEdition } else { "Desktop" }
    }
    $profile["ClrVersion"] = Get-SafeInstallProfileValue { [Environment]::Version.ToString() }
    $profile["CurrentCulture"] = Get-SafeInstallProfileValue { [System.Globalization.CultureInfo]::CurrentCulture.Name }
    $profile["CurrentUICulture"] = Get-SafeInstallProfileValue { [System.Globalization.CultureInfo]::CurrentUICulture.Name }
    $profile["SystemLocale"] = Get-SafeInstallProfileValue {
        if (Get-Command Get-WinSystemLocale -ErrorAction SilentlyContinue) {
            (Get-WinSystemLocale).Name
        } else {
            [System.Globalization.CultureInfo]::InstalledUICulture.Name
        }
    }
    $profile["UILanguage"] = Get-SafeInstallProfileValue {
        if (Get-Command Get-WinUILanguageOverride -ErrorAction SilentlyContinue) {
            $lang = Get-WinUILanguageOverride
            if ($lang) { $lang.Name } else { [System.Globalization.CultureInfo]::CurrentUICulture.Name }
        } else {
            [System.Globalization.CultureInfo]::CurrentUICulture.Name
        }
    }
    $profile["ConsoleCodePage"] = Get-SafeInstallProfileValue { [Console]::OutputEncoding.CodePage }
    $profile["AnsiCodePage"] = Get-SafeInstallProfileValue { (Get-ItemProperty -LiteralPath "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage" -ErrorAction Stop).ACP }
    $profile["OemCodePage"] = Get-SafeInstallProfileValue { (Get-ItemProperty -LiteralPath "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage" -ErrorAction Stop).OEMCP }
    $profile["COMPUTERNAME"] = Get-SafeInstallProfileValue { $env:COMPUTERNAME }
    $profile["USERDOMAIN"] = Get-SafeInstallProfileValue { $env:USERDOMAIN }
    $profile["CurrentUser"] = Get-SafeInstallProfileValue { [Security.Principal.WindowsIdentity]::GetCurrent().Name }
    $profile["IsAdmin"] = Get-SafeInstallProfileValue {
        $id = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = [Security.Principal.WindowsPrincipal]::new($id)
        [string]$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    $profile["ProgramFiles"] = Get-SafeInstallProfileValue { $env:ProgramFiles }
    $profile["ProgramFilesX86"] = Get-SafeInstallProfileValue { ${env:ProgramFiles(x86)} }
    $profile["ProgramData"] = Get-SafeInstallProfileValue { $env:ProgramData }
    $profile["TEMP"] = Get-SafeInstallProfileValue { $env:TEMP }
    $profile["GetLocalUserAvailable"] = Test-CommandAvailableForProfile -Name "Get-LocalUser"
    $profile["seceditAvailable"] = Test-CommandAvailableForProfile -Name "secedit.exe"
    $profile["scAvailable"] = Test-CommandAvailableForProfile -Name "sc.exe"
    $profile["icaclsAvailable"] = Test-CommandAvailableForProfile -Name "icacls.exe"
    $profile["netAvailable"] = Test-CommandAvailableForProfile -Name "net.exe"
    $profile["WinSWExecutes"] = Test-ExecutableRunsForProfile -Path (Join-Path (Join-Path $Script:ProgramFilesDir "services") "winsw.exe") -ArgumentList @("--version")
    $profile["CaddyExecutes"] = Test-ExecutableRunsForProfile -Path (Join-Path $Script:ProgramFilesDir "caddy\caddy.exe") -ArgumentList @("version")
    $profile["PythonExecutes"] = Test-ExecutableRunsForProfile -Path (Join-Path $Script:ProgramFilesDir "python\python.exe") -ArgumentList @("--version")
    $profile["PostgreSQLExecutes"] = Test-ExecutableRunsForProfile -Path (Join-Path $Script:ProgramFilesDir "postgres\bin\postgres.exe") -ArgumentList @("--version")
    return $profile
}

function Read-NativeEnv {
    $map = [ordered]@{}
    $path = Get-EnvPath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return $map
    }

    Get-Content -LiteralPath $path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $map[$parts[0].Trim()] = $parts[1].Trim()
        }
    }
    return $map
}

function Write-NativeEnv {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Map)

    New-DirectorySafe (Split-Path (Get-EnvPath) -Parent)
    $lines = @()
    foreach ($key in $Map.Keys) {
        $lines += "$key=$($Map[$key])"
    }
    [System.IO.File]::WriteAllLines((Get-EnvPath), $lines, [System.Text.UTF8Encoding]::new($false))
}

function New-RandomSecret {
    param([int]$Bytes = 32)

    if ($Bytes -lt 16) {
        throw "New-RandomSecret requiere al menos 16 bytes."
    }

    $bytesValue = [byte[]]::new($Bytes)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytesValue)
    } finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($bytesValue).Replace("+", "-").Replace("/", "_").TrimEnd("=")
}

function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($id)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Ejecuta como Administrador."
    }
}

function Get-ServiceSafe {
    param([Parameter(Mandatory = $true)][string]$Name)
    Get-Service -Name $Name -ErrorAction SilentlyContinue
}

function Get-ServiceStartNameSafe {
    param([Parameter(Mandatory = $true)][string]$Name)

    try {
        $escaped = $Name.Replace("'", "''")
        $service = Get-CimInstance Win32_Service -Filter "Name='$escaped'" -ErrorAction Stop
        if ($service -and -not [string]::IsNullOrWhiteSpace([string]$service.StartName)) {
            return [string]$service.StartName
        }
    } catch {
        return "unknown"
    }
    return "unknown"
}

function Get-AppUrl {
    $envs = Read-NativeEnv
    $port = "9282"
    if ($envs.Contains("APP_HTTP_PORT") -and -not [string]::IsNullOrWhiteSpace([string]$envs["APP_HTTP_PORT"])) {
        $port = [string]$envs["APP_HTTP_PORT"]
    }
    return "http://127.0.0.1:$port"
}

function Test-TcpPort {
    param(
        [string]$HostName = "127.0.0.1",
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutMilliseconds = 2000
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne([TimeSpan]::FromMilliseconds($TimeoutMilliseconds))) {
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

function Wait-TcpPort {
    param(
        [string]$HostName = "127.0.0.1",
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutSeconds = 60,
        [string]$LogName = "healthcheck.log"
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-TcpPort -HostName $HostName -Port $Port) {
            Write-NativeLog -LogName $LogName -Message "TCP_OK $HostName`:$Port"
            return $true
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    Write-NativeLog -LogName $LogName -Message "TCP_FAILED $HostName`:$Port"
    return $false
}

function Test-DteEnv {
    $envs = Read-NativeEnv
    if ($envs["DTE_BACKGROUND_MODE"] -ne "external") {
        throw "DTE_BACKGROUND_MODE debe ser external."
    }
    if ([string]::IsNullOrWhiteSpace([string]$envs["DTE_BASE_URL"])) {
        throw "DTE_BASE_URL no puede quedar vacio."
    }
    if ([string]::IsNullOrWhiteSpace([string]$envs["DTE_API_TOKEN"])) {
        throw "DTE_API_TOKEN no puede quedar vacio."
    }
    return $true
}

function Wait-HttpOk {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [string]$LogName = "healthcheck.log",
        [string]$Name = "http",
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = ""
    do {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
            $status = [int]$response.StatusCode
            if ($status -ge 200 -and $status -lt 300) {
                Write-NativeLog -LogName $LogName -Message "HTTP_OK $Name $Uri status=$status"
                return $true
            }
            $lastError = "status=$status"
        } catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    Write-NativeLog -LogName $LogName -Message "HTTP_FAILED $Name $Uri $lastError"
    return $false
}
