$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

Assert-Admin
if ($Script:PicoServiceAccountName -ne "PicoDeGalloSvc") {
    throw "Cuenta de servicio PostgreSQL inesperada: $Script:PicoServiceAccountName"
}

function Get-RequiredEnvValue {
    param(
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$Map,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $value = [string]$Map[$Name]
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Falta $Name en configuracion nativa."
    }
    return $value
}

function Get-NativeLogPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    New-DirectorySafe (Get-LogsDir)
    return (Join-Path (Get-LogsDir) $Name)
}

function Write-InstallLog {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [string]$LogName = "install-services.log"
    )

    $line = "[{0}] {1}" -f (Get-Date -Format o), (Protect-Text $Message)
    Add-Content -LiteralPath (Get-NativeLogPath $LogName) -Value $line -Encoding UTF8
}

function Format-CommandForLog {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @()
    )

    $parts = @($FilePath) + $ArgumentList
    $quoted = foreach ($part in $parts) {
        $text = [string]$part
        if ($text -match '\s') {
            '"' + $text.Replace('"', '\"') + '"'
        } else {
            $text
        }
    }
    return ($quoted -join " ")
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory = $true)][string]$LogName,
        [string]$WorkingDirectory,
        [hashtable]$Environment = @{},
        [switch]$ReturnStdout
    )

    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        throw "No existe ejecutable requerido: $FilePath"
    }

    $logPath = Get-NativeLogPath $LogName
    $stdout = Join-Path (Get-LogsDir) ("{0}.stdout.tmp" -f ([Guid]::NewGuid().ToString("N")))
    $stderr = Join-Path (Get-LogsDir) ("{0}.stderr.tmp" -f ([Guid]::NewGuid().ToString("N")))
    $oldEnvironment = @{}
    $exitCode = 0

    Write-InstallLog -LogName $LogName -Message ("RUN " + (Format-CommandForLog -FilePath $FilePath -ArgumentList $ArgumentList))

    try {
        foreach ($name in $Environment.Keys) {
            $oldEnvironment[$name] = [Environment]::GetEnvironmentVariable([string]$name, "Process")
            [Environment]::SetEnvironmentVariable([string]$name, [string]$Environment[$name], "Process")
        }

        if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
            Push-Location $WorkingDirectory
        }

        try {
            & $FilePath @ArgumentList > $stdout 2> $stderr
            $exitCode = $LASTEXITCODE
        } catch {
            Write-InstallLog -LogName $LogName -Message ("FAILED_TO_LAUNCH " + $_.Exception.Message)
            throw
        } finally {
            if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
                Pop-Location
            }
        }
    } finally {
        foreach ($name in $Environment.Keys) {
            [Environment]::SetEnvironmentVariable([string]$name, $oldEnvironment[$name], "Process")
        }
    }

    $stdoutText = ""
    $stderrText = ""
    if (Test-Path -LiteralPath $stdout -PathType Leaf) {
        $stdoutText = Get-Content -LiteralPath $stdout -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($stdoutText)) {
            Add-Content -LiteralPath $logPath -Value (Protect-Text $stdoutText) -Encoding UTF8
        }
    }
    if (Test-Path -LiteralPath $stderr -PathType Leaf) {
        $stderrText = Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($stderrText)) {
            Add-Content -LiteralPath $logPath -Value (Protect-Text $stderrText) -Encoding UTF8
        }
    }

    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue

    Write-InstallLog -LogName $LogName -Message ("EXIT_CODE " + $exitCode)
    if ($exitCode -ne 0) {
        throw "Comando fallo con codigo $exitCode. Revise $logPath"
    }

    if ($ReturnStdout) {
        return $stdoutText
    }
}

function Render-Template {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][hashtable]$Tokens
    )

    $content = Get-Content -LiteralPath $Source -Raw
    foreach ($key in $Tokens.Keys) {
        $content = $content.Replace("{{$key}}", [string]$Tokens[$key])
    }
    Set-Content -LiteralPath $Destination -Value $content -Encoding UTF8
}

function Get-ServiceWrapperPath {
    param([Parameter(Mandatory = $true)][string]$ServiceId)
    return (Join-Path (Join-Path $Script:ProgramFilesDir "services") "$ServiceId.exe")
}

function Invoke-WinSWCommand {
    param(
        [Parameter(Mandatory = $true)][string]$ServiceId,
        [Parameter(Mandatory = $true)][string]$Command
    )

    $wrapper = Get-ServiceWrapperPath -ServiceId $ServiceId
    Invoke-LoggedCommand `
        -FilePath $wrapper `
        -ArgumentList @($Command) `
        -LogName "service-install.log"
}

function New-SecureRandomPassword {
    param([int]$Length = 32)

    if ($Length -lt 20) {
        throw "New-SecureRandomPassword requiere al menos 20 caracteres."
    }

    $upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    $lower = "abcdefghijkmnopqrstuvwxyz"
    $digits = "23456789"
    $symbols = "!#$%+-_"
    $all = $upper + $lower + $digits + $symbols
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()

    function Get-RandomIndex {
        param(
            [Parameter(Mandatory = $true)]$Generator,
            [Parameter(Mandatory = $true)][int]$MaxExclusive
        )

        $bytes = [byte[]]::new(4)
        $max = [uint64]$MaxExclusive
        $uintMax = [uint64]([uint32]::MaxValue)
        $limit = $uintMax - ($uintMax % $max)
        do {
            $Generator.GetBytes($bytes)
            $value = [uint64][BitConverter]::ToUInt32($bytes, 0)
        } while ($value -ge $limit)
        return [int]($value % $max)
    }

    function Get-RandomChar {
        param(
            [Parameter(Mandatory = $true)]$Generator,
            [Parameter(Mandatory = $true)][string]$Characters
        )
        return $Characters[(Get-RandomIndex -Generator $Generator -MaxExclusive $Characters.Length)]
    }

    try {
        $chars = New-Object "System.Collections.Generic.List[char]"
        foreach ($set in @($upper, $lower, $digits, $symbols)) {
            $chars.Add((Get-RandomChar -Generator $rng -Characters $set)) | Out-Null
        }
        while ($chars.Count -lt $Length) {
            $chars.Add((Get-RandomChar -Generator $rng -Characters $all)) | Out-Null
        }
        for ($i = $chars.Count - 1; $i -gt 0; $i--) {
            $j = Get-RandomIndex -Generator $rng -MaxExclusive ($i + 1)
            $tmp = $chars[$i]
            $chars[$i] = $chars[$j]
            $chars[$j] = $tmp
        }
        return (-join $chars)
    } finally {
        $rng.Dispose()
    }
}

function ConvertTo-PicoSecureString {
    param([Parameter(Mandatory = $true)][string]$PlainText)
    return (ConvertTo-SecureString -String $PlainText -AsPlainText -Force)
}

function Get-BuiltinGroupName {
    param(
        [Parameter(Mandatory = $true)][string]$Sid,
        [Parameter(Mandatory = $true)][string]$Fallback
    )

    try {
        $sidObject = [System.Security.Principal.SecurityIdentifier]::new($Sid)
        $account = $sidObject.Translate([System.Security.Principal.NTAccount]).Value
        return (($account -split "\\")[-1])
    } catch {
        return $Fallback
    }
}

function Test-LocalAccountsCmdletsAvailable {
    foreach ($name in @("Get-LocalUser", "New-LocalUser", "Set-LocalUser", "Enable-LocalUser", "Get-LocalGroupMember", "Add-LocalGroupMember", "Remove-LocalGroupMember")) {
        if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
            return $false
        }
    }
    return $true
}

function Set-PicoAdsiUserPasswordAndFlags {
    param(
        [Parameter(Mandatory = $true)][string]$AccountName,
        [Parameter(Mandatory = $true)][string]$Password,
        [Parameter(Mandatory = $true)][string]$Description
    )

    $computer = [ADSI]("WinNT://{0}" -f $env:COMPUTERNAME)
    $user = $null
    try {
        $user = [ADSI]("WinNT://{0}/{1},user" -f $env:COMPUTERNAME, $AccountName)
        $null = $user.Name
    } catch {
        $user = $computer.Create("user", $AccountName)
        $user.SetInfo()
    }

    $user.SetPassword($Password)
    $user.Put("Description", $Description)
    $flags = 0x0200 -bor 0x10000
    try {
        $currentFlags = [int]$user.UserFlags.Value
        $flags = ($currentFlags -bor 0x0200 -bor 0x10000) -band (-bnot 0x0002)
    } catch {
    }
    $user.Put("UserFlags", $flags)
    $user.SetInfo()
}

function Test-PicoAdsiGroupMember {
    param(
        [Parameter(Mandatory = $true)][string]$GroupName,
        [Parameter(Mandatory = $true)][string]$AccountName
    )

    try {
        $group = [ADSI]("WinNT://{0}/{1},group" -f $env:COMPUTERNAME, $GroupName)
        foreach ($member in @($group.psbase.Invoke("Members"))) {
            $memberName = [string]$member.GetType().InvokeMember("Name", "GetProperty", $null, $member, $null)
            if ($memberName -ieq $AccountName) {
                return $true
            }
        }
    } catch {
    }
    return $false
}

function Ensure-PicoServiceAccountGroups {
    param([Parameter(Mandatory = $true)][string]$AccountName)

    $adminGroup = Get-BuiltinGroupName -Sid "S-1-5-32-544" -Fallback "Administrators"
    $usersGroup = Get-BuiltinGroupName -Sid "S-1-5-32-545" -Fallback "Users"
    $localAccount = "{0}\{1}" -f $env:COMPUTERNAME, $AccountName

    if (Test-LocalAccountsCmdletsAvailable) {
        $sid = $null
        try {
            $sid = ([System.Security.Principal.NTAccount]::new($env:COMPUTERNAME, $AccountName)).Translate([System.Security.Principal.SecurityIdentifier]).Value
        } catch {
        }

        foreach ($member in @(Get-LocalGroupMember -Group $adminGroup -ErrorAction SilentlyContinue)) {
            $memberSid = ""
            if ($member.SID) { $memberSid = [string]$member.SID.Value }
            if (($sid -and $memberSid -eq $sid) -or ([string]$member.Name -ieq $localAccount) -or ([string]$member.Name -ieq ".\$AccountName")) {
                Remove-LocalGroupMember -Group $adminGroup -Member $member.Name -ErrorAction Stop
                Write-InstallLog "PICO_SERVICE_ACCOUNT_REMOVED_FROM_ADMINISTRATORS name=$AccountName"
            }
        }

        try {
            Add-LocalGroupMember -Group $usersGroup -Member $AccountName -ErrorAction Stop
        } catch {
            if (-not (Test-PicoAdsiGroupMember -GroupName $usersGroup -AccountName $AccountName)) {
                Write-InstallLog "PICO_SERVICE_ACCOUNT_USERS_GROUP_SKIPPED name=$AccountName reason=$($_.Exception.Message)"
            }
        }
    } else {
        $userPath = "WinNT://{0}/{1},user" -f $env:COMPUTERNAME, $AccountName
        if (Test-PicoAdsiGroupMember -GroupName $adminGroup -AccountName $AccountName) {
            $group = [ADSI]("WinNT://{0}/{1},group" -f $env:COMPUTERNAME, $adminGroup)
            $group.Remove($userPath)
            Write-InstallLog "PICO_SERVICE_ACCOUNT_REMOVED_FROM_ADMINISTRATORS name=$AccountName"
        }
        if (-not (Test-PicoAdsiGroupMember -GroupName $usersGroup -AccountName $AccountName)) {
            try {
                $group = [ADSI]("WinNT://{0}/{1},group" -f $env:COMPUTERNAME, $usersGroup)
                $group.Add($userPath)
            } catch {
                Write-InstallLog "PICO_SERVICE_ACCOUNT_USERS_GROUP_SKIPPED name=$AccountName reason=$($_.Exception.Message)"
            }
        }
    }

    if (Test-PicoAdsiGroupMember -GroupName $adminGroup -AccountName $AccountName) {
        throw "La cuenta $AccountName pertenece al grupo Administrators. PostgreSQL no puede ejecutarse asi."
    }
}

function Ensure-PicoServiceAccount {
    $accountName = $Script:PicoServiceAccountName
    $description = "Servicio local no administrador para Pico de Gallo"
    $password = New-SecureRandomPassword
    $securePassword = ConvertTo-PicoSecureString -PlainText $password
    $provider = "ADSI"

    if (Test-LocalAccountsCmdletsAvailable) {
        $provider = "LocalAccounts"
        $existing = Get-LocalUser -Name $accountName -ErrorAction SilentlyContinue
        if ($existing) {
            $setParams = @{
                Name = $accountName
                Password = $securePassword
                Description = $description
            }
            $setCommand = Get-Command Set-LocalUser
            if ($setCommand.Parameters.ContainsKey("PasswordNeverExpires")) {
                $setParams["PasswordNeverExpires"] = $true
            }
            Set-LocalUser @setParams -ErrorAction Stop
            if ($setCommand.Parameters.ContainsKey("UserMayChangePassword")) {
                try {
                    Set-LocalUser -Name $accountName -UserMayChangePassword $false -ErrorAction Stop
                } catch {
                    Write-InstallLog "PICO_SERVICE_ACCOUNT_USER_MAY_CHANGE_PASSWORD_SKIPPED name=$accountName"
                }
            }
            if (-not $existing.Enabled) {
                Enable-LocalUser -Name $accountName -ErrorAction Stop
            }
            Write-InstallLog "PICO_SERVICE_ACCOUNT_PASSWORD_RESET name=$accountName"
        } else {
            $newParams = @{
                Name = $accountName
                Password = $securePassword
                Description = $description
                PasswordNeverExpires = $true
            }
            $newCommand = Get-Command New-LocalUser
            if ($newCommand.Parameters.ContainsKey("UserMayNotChangePassword")) {
                $newParams["UserMayNotChangePassword"] = $true
            }
            if ($newCommand.Parameters.ContainsKey("AccountNeverExpires")) {
                $newParams["AccountNeverExpires"] = $true
            }
            New-LocalUser @newParams -ErrorAction Stop | Out-Null
            Write-InstallLog "PICO_SERVICE_ACCOUNT_CREATED name=$accountName"
        }
    } else {
        Set-PicoAdsiUserPasswordAndFlags -AccountName $accountName -Password $password -Description $description
        Write-InstallLog "PICO_SERVICE_ACCOUNT_READY_ADSI name=$accountName"
    }

    Ensure-PicoServiceAccountGroups -AccountName $accountName
    Write-InstallLog "PICO_SERVICE_ACCOUNT_READY name=$accountName provider=$provider non_admin=true"
    return [System.Management.Automation.PSCredential]::new(".\$accountName", $securePassword)
}

function Invoke-IcaclsGrant {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Account,
        [Parameter(Mandatory = $true)][string]$Rights
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        New-DirectorySafe $Path
    }

    $icacls = Join-Path $env:SystemRoot "System32\icacls.exe"
    Invoke-LoggedCommand `
        -FilePath $icacls `
        -ArgumentList @($Path, "/grant", "$($Account):(OI)(CI)$Rights", "/T", "/C") `
        -LogName "permissions.log"
    Write-InstallLog -LogName "permissions.log" -Message "ACL_GRANTED path=$Path account=$Account rights=$Rights"
}

function Grant-PicoServiceAccountPermissions {
    param([Parameter(Mandatory = $true)][System.Management.Automation.PSCredential]$Credential)

    $accountName = $Credential.UserName
    if ($accountName.StartsWith(".\")) {
        $accountName = "{0}\{1}" -f $env:COMPUTERNAME, $accountName.Substring(2)
    }

    Invoke-IcaclsGrant -Path (Join-Path $Script:ProgramDataDir "postgres") -Account $accountName -Rights "F"
    Invoke-IcaclsGrant -Path (Join-Path $Script:ProgramDataDir "logs") -Account $accountName -Rights "M"
    Invoke-IcaclsGrant -Path (Join-Path $Script:ProgramFilesDir "postgres") -Account $accountName -Rights "RX"
    Invoke-IcaclsGrant -Path (Join-Path $Script:ProgramFilesDir "services") -Account $accountName -Rights "RX"
}

function ConvertTo-StartProcessArgumentString {
    param([string[]]$ArgumentList = @())

    $escaped = foreach ($arg in $ArgumentList) {
        $text = [string]$arg
        if ($text -match '[\s"]') {
            '"' + $text.Replace('"', '\"') + '"'
        } else {
            $text
        }
    }
    return ($escaped -join " ")
}

function Invoke-AsPicoServiceAccount {
    param(
        [Parameter(Mandatory = $true)][System.Management.Automation.PSCredential]$Credential,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory = $true)][string]$LogName,
        [string]$WorkingDirectory,
        [string]$StdoutPath,
        [string]$StderrPath,
        [switch]$NoWait,
        [switch]$ReturnStdout
    )

    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        throw "No existe ejecutable requerido: $FilePath"
    }

    if ([string]::IsNullOrWhiteSpace($StdoutPath)) {
        $StdoutPath = Join-Path (Get-LogsDir) ("{0}.stdout.tmp" -f ([Guid]::NewGuid().ToString("N")))
    }
    if ([string]::IsNullOrWhiteSpace($StderrPath)) {
        $StderrPath = Join-Path (Get-LogsDir) ("{0}.stderr.tmp" -f ([Guid]::NewGuid().ToString("N")))
    }

    $argumentString = ConvertTo-StartProcessArgumentString -ArgumentList $ArgumentList
    Write-InstallLog -LogName $LogName -Message ("RUN_AS {0} {1}" -f $Script:PicoServiceAccountName, (Format-CommandForLog -FilePath $FilePath -ArgumentList $ArgumentList))

    $startParams = @{
        FilePath = $FilePath
        ArgumentList = $argumentString
        Credential = $Credential
        RedirectStandardOutput = $StdoutPath
        RedirectStandardError = $StderrPath
        WindowStyle = "Hidden"
        PassThru = $true
    }
    if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
        $startParams["WorkingDirectory"] = $WorkingDirectory
    }

    $process = Start-Process @startParams
    if ($NoWait) {
        return $process
    }

    $process.WaitForExit()
    $stdoutText = ""
    $stderrText = ""
    if (Test-Path -LiteralPath $StdoutPath -PathType Leaf) {
        $stdoutText = Get-Content -LiteralPath $StdoutPath -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($stdoutText)) {
            Add-Content -LiteralPath (Get-NativeLogPath $LogName) -Value (Protect-Text $stdoutText) -Encoding UTF8
        }
    }
    if (Test-Path -LiteralPath $StderrPath -PathType Leaf) {
        $stderrText = Get-Content -LiteralPath $StderrPath -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($stderrText)) {
            Add-Content -LiteralPath (Get-NativeLogPath $LogName) -Value (Protect-Text $stderrText) -Encoding UTF8
        }
    }
    Remove-Item -LiteralPath $StdoutPath, $StderrPath -Force -ErrorAction SilentlyContinue

    Write-InstallLog -LogName $LogName -Message ("EXIT_CODE " + $process.ExitCode)
    if ($process.ExitCode -ne 0) {
        throw "Comando como $Script:PicoServiceAccountName fallo con codigo $($process.ExitCode). Revise $(Get-NativeLogPath $LogName)"
    }
    if ($ReturnStdout) {
        return $stdoutText
    }
}

function Escape-XmlText {
    param([string]$Text)
    return [System.Security.SecurityElement]::Escape($Text)
}

function New-WinSWServiceAccountXml {
    param([string]$Password)

    $lines = @(
        "  <serviceaccount>",
        ("    <username>.\{0}</username>" -f (Escape-XmlText $Script:PicoServiceAccountName))
    )
    if (-not [string]::IsNullOrEmpty($Password)) {
        $lines += ("    <password>{0}</password>" -f (Escape-XmlText $Password))
    }
    $lines += "    <allowservicelogon>true</allowservicelogon>"
    $lines += "  </serviceaccount>"
    return ($lines -join "`r`n")
}

function Assert-SecretAbsentFromFiles {
    param(
        [Parameter(Mandatory = $true)][string]$Secret,
        [Parameter(Mandatory = $true)][string[]]$Paths
    )

    if ([string]::IsNullOrEmpty($Secret)) {
        return
    }

    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            continue
        }
        $text = Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue
        if ($text -and $text.Contains($Secret)) {
            Set-Content -LiteralPath $path -Value ($text.Replace($Secret, "***REDACTED***")) -Encoding UTF8
            throw "La contrasena de $Script:PicoServiceAccountName quedo persistida en $path. El valor fue redactado y la instalacion se detuvo."
        }
    }
}

function Assert-PostgresServiceAccount {
    $startName = Get-ServiceStartNameSafe -Name "PicoDeGallo-PostgreSQL"
    Write-InstallLog -LogName "postgres-service.log" -Message "POSTGRES_SERVICE_START_NAME $startName"
    if ($startName -notmatch [regex]::Escape($Script:PicoServiceAccountName)) {
        throw "PicoDeGallo-PostgreSQL quedo configurado como $startName; debe ejecutar como .\$Script:PicoServiceAccountName."
    }
    $privilegedPattern = ("Local" + "System") + "|" + ("NT AUTHORITY" + "\\SYSTEM") + "|Administrador|CAJA"
    if ($startName -match $privilegedPattern) {
        throw "PicoDeGallo-PostgreSQL no puede ejecutar como cuenta administrativa: $startName"
    }
}

function Install-WinSWServiceWithAccount {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Tokens,
        [Parameter(Mandatory = $true)][string]$Template,
        [Parameter(Mandatory = $true)][string]$TargetXml,
        [Parameter(Mandatory = $true)][string]$TargetExe,
        [Parameter(Mandatory = $true)][string]$WinSWSource,
        [Parameter(Mandatory = $true)][System.Management.Automation.PSCredential]$Credential,
        [Parameter(Mandatory = $true)][string]$ServiceId
    )

    $password = $Credential.GetNetworkCredential().Password
    $installTokens = $Tokens.Clone()
    $installTokens["PICO_SERVICE_ACCOUNT_XML"] = New-WinSWServiceAccountXml -Password $password
    $finalTokens = $Tokens.Clone()
    $finalTokens["PICO_SERVICE_ACCOUNT_XML"] = New-WinSWServiceAccountXml

    try {
        Render-Template -Source $Template -Destination $TargetXml -Tokens $installTokens
        if ((Get-Content -LiteralPath $TargetXml -Raw).Contains("{{")) {
            throw "XML WinSW renderizado contiene placeholders sin resolver: $TargetXml"
        }
        Copy-Item -LiteralPath $WinSWSource -Destination $TargetExe -Force
        Invoke-WinSWCommand -ServiceId $ServiceId -Command "install"
    } finally {
        Render-Template -Source $Template -Destination $TargetXml -Tokens $finalTokens
        Assert-SecretAbsentFromFiles -Secret $password -Paths @($TargetXml)
    }

    Assert-SecretAbsentFromFiles -Secret $password -Paths @(
        (Get-NativeLogPath "service-install.log"),
        (Get-NativeLogPath "install-services.log"),
        (Get-NativeLogPath "postgres-service.log")
    )
    Wait-ServiceStatus -ServiceId $ServiceId -DesiredStatus "Stopped" -TimeoutSeconds 30
    Assert-PostgresServiceAccount
}

function Stop-ExistingServicesForLogArchive {
    $serviceIds = @($Script:Services)
    [array]::Reverse($serviceIds)

    foreach ($serviceId in $serviceIds) {
        $service = Get-ServiceSafe $serviceId
        if ($service -and $service.Status -eq "Running") {
            Write-SafeHost "Deteniendo servicio existente antes de archivar logs: $serviceId"
            Stop-Service -Name $serviceId -ErrorAction Stop
            $service.WaitForStatus([System.ServiceProcess.ServiceControllerStatus]::Stopped, [TimeSpan]::FromSeconds(90))
        }
    }
}

function Archive-ExistingNativeLogs {
    $logsDir = Get-LogsDir
    if (-not (Test-Path -LiteralPath $logsDir -PathType Container)) {
        return
    }

    $items = @(Get-ChildItem -LiteralPath $logsDir -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne "archive" })
    if ($items.Count -eq 0) {
        return
    }

    $archiveRoot = Join-Path $logsDir "archive"
    New-DirectorySafe $archiveRoot
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $archiveDir = Join-Path $archiveRoot $stamp
    $suffix = 0
    while (Test-Path -LiteralPath $archiveDir) {
        $suffix++
        $archiveDir = Join-Path $archiveRoot ("{0}-{1}" -f $stamp, $suffix)
    }
    New-DirectorySafe $archiveDir

    foreach ($item in $items) {
        Move-Item -LiteralPath $item.FullName -Destination $archiveDir -Force -ErrorAction Stop
    }

    Write-SafeHost "Logs anteriores archivados en $archiveDir"
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

function Write-LogTail {
    param(
        [Parameter(Mandatory = $true)][string]$LogName,
        [int]$Lines = 80,
        [string]$TargetLogName = "service-install.log"
    )

    $path = Join-Path (Get-LogsDir) $LogName
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Write-InstallLog -LogName $TargetLogName -Message "LOG_TAIL_MISSING $LogName"
        return
    }

    Write-InstallLog -LogName $TargetLogName -Message "LOG_TAIL_BEGIN $LogName"
    $tail = Get-Content -LiteralPath $path -Tail $Lines -ErrorAction SilentlyContinue
    if ($tail) {
        Add-Content -LiteralPath (Get-NativeLogPath $TargetLogName) -Value (Protect-Text (($tail | ForEach-Object { [string]$_ }) -join "`n")) -Encoding UTF8
    }
    Write-InstallLog -LogName $TargetLogName -Message "LOG_TAIL_END $LogName"
}

function Write-ServiceFailureDiagnostics {
    param(
        [Parameter(Mandatory = $true)][string]$ServiceId,
        [int]$Port = 0,
        [string]$HostName = "127.0.0.1"
    )

    $service = Get-ServiceSafe $ServiceId
    $status = if ($service) { [string]$service.Status } else { "not-installed" }
    Write-InstallLog -LogName "service-install.log" -Message "SERVICE_FAILURE $ServiceId status=$status"
    Write-InstallLog -LogName "install-services.log" -Message "SERVICE_FAILURE $ServiceId status=$status"
    if ($Port -gt 0) {
        $portStatus = if (Test-TcpPort -HostName $HostName -Port $Port) { "listening" } else { "closed" }
        Write-InstallLog -LogName "healthcheck.log" -Message "TCP_STATUS $HostName`:$Port $portStatus"
    }

    foreach ($logName in @(
        "$ServiceId.wrapper.log",
        "$ServiceId.err.log",
        "$ServiceId.out.log",
        "postgres-foreground-test.err.log",
        "postgres-foreground-test.out.log",
        "postgres-version.log",
        "initdb-version.log",
        "psql-version.log",
        "postgres-init.log",
        "postgres-service.log"
    )) {
        Write-LogTail -LogName $logName -TargetLogName "service-install.log"
    }
}

function Wait-TcpPort {
    param(
        [string]$HostName = "127.0.0.1",
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutSeconds = 60,
        [string]$ServiceId
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-TcpPort -HostName $HostName -Port $Port) {
            Write-InstallLog -LogName "healthcheck.log" -Message "TCP_OK $HostName`:$Port"
            return
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    Write-InstallLog -LogName "healthcheck.log" -Message "TCP_FAILED $HostName`:$Port"
    if (-not [string]::IsNullOrWhiteSpace($ServiceId)) {
        Write-ServiceFailureDiagnostics -ServiceId $ServiceId -HostName $HostName -Port $Port
    }
    throw "Puerto TCP no quedo escuchando: $HostName`:$Port"
}

function Wait-ServiceStatus {
    param(
        [Parameter(Mandatory = $true)][string]$ServiceId,
        [Parameter(Mandatory = $true)][string]$DesiredStatus,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $service = Get-ServiceSafe $ServiceId
        if ($service -and ([string]$service.Status) -eq $DesiredStatus) {
            Write-InstallLog "SERVICE_STATUS $ServiceId $DesiredStatus"
            return
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    $current = Get-ServiceSafe $ServiceId
    $status = if ($current) { [string]$current.Status } else { "not-installed" }
    Write-ServiceFailureDiagnostics -ServiceId $ServiceId
    throw "Servicio $ServiceId no llego a estado $DesiredStatus. Estado actual: $status"
}

function Wait-ServiceRemoved {
    param(
        [Parameter(Mandatory = $true)][string]$ServiceId,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (-not (Get-ServiceSafe $ServiceId)) {
            Write-InstallLog -LogName "service-install.log" -Message "SERVICE_REMOVED $ServiceId"
            return
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    throw "Servicio $ServiceId no fue eliminado completamente despues de uninstall."
}

function Start-WinSWService {
    param([Parameter(Mandatory = $true)][string]$ServiceId)

    $service = Get-ServiceSafe $ServiceId
    if (-not $service) {
        throw "Servicio requerido no instalado: $ServiceId"
    }
    if ($service.Status -eq "Running") {
        Write-InstallLog "SERVICE_ALREADY_RUNNING $ServiceId"
        if ($ServiceId -eq "PicoDeGallo-PostgreSQL") {
            Write-InstallLog -LogName "postgres-service.log" -Message "SERVICE_ALREADY_RUNNING $ServiceId"
        }
        return
    }

    try {
        Invoke-WinSWCommand -ServiceId $ServiceId -Command "start"
    } catch {
        $service = Get-ServiceSafe $ServiceId
        if (-not $service -or $service.Status -ne "Running") {
            Write-ServiceFailureDiagnostics -ServiceId $ServiceId
            throw
        }
    }

    Wait-ServiceStatus -ServiceId $ServiceId -DesiredStatus "Running" -TimeoutSeconds 90
    if ($ServiceId -eq "PicoDeGallo-PostgreSQL") {
        Write-InstallLog -LogName "postgres-service.log" -Message "SERVICE_RUNNING $ServiceId"
    }
    Write-SafeHost "Servicio iniciado: $ServiceId"
}

function Assert-AllServicesInstalled {
    foreach ($serviceId in $Script:Services) {
        if (-not (Get-ServiceSafe $serviceId)) {
            throw "Servicio requerido no instalado: $serviceId"
        }
    }
}

function Assert-AllServicesRunning {
    foreach ($serviceId in $Script:Services) {
        Wait-ServiceStatus -ServiceId $serviceId -DesiredStatus "Running" -TimeoutSeconds 30
    }
}

function Install-WinSWServices {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Tokens,
        [string[]]$ServiceIds = $Script:Services,
        [System.Management.Automation.PSCredential]$PicoServiceCredential
    )

    $serviceDir = Join-Path $Script:ProgramFilesDir "services"
    $templateDir = Join-Path $serviceDir "templates"
    $winswSource = Join-Path $serviceDir "winsw.exe"

    if (-not (Test-Path -LiteralPath $winswSource -PathType Leaf)) {
        throw "No existe WinSW en $winswSource"
    }
    if (-not (Test-Path -LiteralPath $templateDir -PathType Container)) {
        throw "No existen templates de servicios en $templateDir"
    }

    foreach ($serviceId in $ServiceIds) {
        $template = Join-Path $templateDir "$serviceId.xml"
        if (-not (Test-Path -LiteralPath $template -PathType Leaf)) {
            throw "Falta template WinSW para $serviceId"
        }

        $targetXml = Join-Path $serviceDir "$serviceId.xml"
        $targetExe = Get-ServiceWrapperPath -ServiceId $serviceId
        $existingService = Get-ServiceSafe $serviceId

        if ($existingService) {
            if ($existingService.Status -eq "Running") {
                Write-InstallLog -LogName "service-install.log" -Message "SERVICE_STOP_FOR_UPDATE $serviceId"
                Stop-Service -Name $serviceId -ErrorAction Stop
                Wait-ServiceStatus -ServiceId $serviceId -DesiredStatus "Stopped" -TimeoutSeconds 90
            }

            Write-InstallLog -LogName "service-install.log" -Message "SERVICE_UNINSTALL_FOR_UPDATE $serviceId"
            if (Test-Path -LiteralPath $targetExe -PathType Leaf) {
                try {
                    Invoke-LoggedCommand `
                        -FilePath $targetExe `
                        -ArgumentList @("uninstall") `
                        -LogName "service-install.log"
                } catch {
                    if (Get-ServiceSafe $serviceId) {
                        Write-InstallLog -LogName "service-install.log" -Message ("SERVICE_UNINSTALL_FALLBACK_SC $serviceId " + $_.Exception.Message)
                        $scExe = Join-Path $env:SystemRoot "System32\sc.exe"
                        Invoke-LoggedCommand `
                            -FilePath $scExe `
                            -ArgumentList @("delete", $serviceId) `
                            -LogName "service-install.log"
                    } else {
                        Write-InstallLog -LogName "service-install.log" -Message "SERVICE_UNINSTALL_EXIT_IGNORED $serviceId service_already_removed"
                    }
                }
            } else {
                $scExe = Join-Path $env:SystemRoot "System32\sc.exe"
                Invoke-LoggedCommand `
                    -FilePath $scExe `
                    -ArgumentList @("delete", $serviceId) `
                    -LogName "service-install.log"
            }
            Wait-ServiceRemoved -ServiceId $serviceId -TimeoutSeconds 90
        }

        if ($serviceId -eq "PicoDeGallo-PostgreSQL") {
            if (-not $PicoServiceCredential) {
                throw "PicoDeGallo-PostgreSQL requiere credencial de $Script:PicoServiceAccountName."
            }
            Install-WinSWServiceWithAccount `
                -Tokens $Tokens `
                -Template $template `
                -TargetXml $targetXml `
                -TargetExe $targetExe `
                -WinSWSource $winswSource `
                -Credential $PicoServiceCredential `
                -ServiceId $serviceId
        } else {
            Render-Template -Source $template -Destination $targetXml -Tokens $Tokens
            if ((Get-Content -LiteralPath $targetXml -Raw).Contains("{{")) {
                throw "XML WinSW renderizado contiene placeholders sin resolver: $targetXml"
            }
            Copy-Item -LiteralPath $winswSource -Destination $targetExe -Force

            Invoke-WinSWCommand -ServiceId $serviceId -Command "install"
            Wait-ServiceStatus -ServiceId $serviceId -DesiredStatus "Stopped" -TimeoutSeconds 30
        }
        Write-SafeHost "Servicio instalado: $serviceId"
    }

    foreach ($serviceId in $ServiceIds) {
        if (-not (Get-ServiceSafe $serviceId)) {
            throw "Servicio requerido no instalado: $serviceId"
        }
    }
}

function Quote-PostgresIdentifier {
    param([Parameter(Mandatory = $true)][string]$Value)
    return ('"' + $Value.Replace('"', '""') + '"')
}

function Quote-PostgresLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return ("'" + $Value.Replace("'", "''") + "'")
}

function Initialize-PostgresDataDirectory {
    param(
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap,
        [Parameter(Mandatory = $true)][System.Management.Automation.PSCredential]$Credential
    )

    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $dataDir = Join-Path $Script:ProgramDataDir "postgres\data"
    $initdb = Join-Path $postgresBin "initdb.exe"

    if (-not (Test-Path -LiteralPath $initdb -PathType Leaf)) {
        throw "No existe initdb.exe en runtime PostgreSQL nativo."
    }
    if (Test-Path -LiteralPath (Join-Path $dataDir "PG_VERSION") -PathType Leaf) {
        Write-InstallLog "POSTGRES_DATA_EXISTS $dataDir"
        return
    }

    $existing = Get-ChildItem -LiteralPath $dataDir -Force -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing) {
        throw "El directorio de datos PostgreSQL existe pero no contiene PG_VERSION: $dataDir"
    }

    $dbUser = Get-RequiredEnvValue -Map $EnvMap -Name "DB_USER"
    $dbPassword = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PASSWORD"
    $pwFile = Join-Path (Join-Path $Script:ProgramDataDir "postgres") ("picopos-pg-" + [Guid]::NewGuid().ToString("N") + ".pw")

    try {
        Set-Content -LiteralPath $pwFile -Value $dbPassword -Encoding ASCII
        Invoke-AsPicoServiceAccount `
            -Credential $Credential `
            -FilePath $initdb `
            -ArgumentList @("-D", $dataDir, "-E", "UTF8", "--locale=C", "--username=$dbUser", "--pwfile=$pwFile", "--auth=scram-sha-256") `
            -WorkingDirectory $postgresBin `
            -LogName "postgres-init.log"
        Write-InstallLog -LogName "postgres-init.log" -Message "POSTGRES_INITDB_RUN_AS $Script:PicoServiceAccountName"
    } finally {
        Remove-Item -LiteralPath $pwFile -Force -ErrorAction SilentlyContinue
    }
}

function Assert-PostgresRuntimeTools {
    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    foreach ($tool in @("postgres.exe", "pg_ctl.exe", "initdb.exe", "psql.exe", "pg_dump.exe", "pg_restore.exe", "createdb.exe")) {
        $path = Join-Path $postgresBin $tool
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Falta herramienta PostgreSQL requerida: $path"
        }
    }
}

function Invoke-PostgresRuntimeVersionChecks {
    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $checks = @(
        @{ Tool = "postgres.exe"; Command = "postgres.exe --version"; LogName = "postgres-version.log" },
        @{ Tool = "initdb.exe"; Command = "initdb.exe --version"; LogName = "initdb-version.log" },
        @{ Tool = "psql.exe"; Command = "psql.exe --version"; LogName = "psql-version.log" }
    )

    foreach ($check in $checks) {
        $tool = [string]$check.Tool
        $exe = Join-Path $postgresBin $tool
        Invoke-LoggedCommand `
            -FilePath $exe `
            -ArgumentList @("--version") `
            -WorkingDirectory $postgresBin `
            -LogName ([string]$check.LogName)
        Write-InstallLog -LogName "postgres-service.log" -Message ("POSTGRES_RUNTIME_VERSION_OK " + [string]$check.Command)
    }
}

function Set-PostgresConfigValue {
    param(
        [Parameter(Mandatory = $true)][string]$ConfigPath,
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$Value
    )

    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        throw "No existe archivo de configuracion PostgreSQL: $ConfigPath"
    }

    $escaped = [regex]::Escape($Key)
    $line = "$Key = $Value"
    $content = Get-Content -LiteralPath $ConfigPath -Encoding UTF8
    $updated = $false
    $newContent = @(foreach ($item in $content) {
        if ($item -match "^\s*#?\s*$escaped\s*=") {
            $updated = $true
            $line
        } else {
            $item
        }
    })
    if (-not $updated) {
        $newContent += $line
    }
    Set-Content -LiteralPath $ConfigPath -Value $newContent -Encoding UTF8
}

function Set-PostgresHbaHostAuth {
    param([Parameter(Mandatory = $true)][string]$HbaPath)

    if (-not (Test-Path -LiteralPath $HbaPath -PathType Leaf)) {
        throw "No existe archivo pg_hba.conf: $HbaPath"
    }

    $desired = [ordered]@{
        "127.0.0.1/32" = "host all all 127.0.0.1/32 scram-sha-256"
        "::1/128" = "host all all ::1/128 scram-sha-256"
    }
    $seen = @{}
    $content = Get-Content -LiteralPath $HbaPath -Encoding UTF8
    $newContent = @()

    foreach ($line in $content) {
        $matched = $false
        foreach ($address in $desired.Keys) {
            $escapedAddress = [regex]::Escape([string]$address)
            if ($line -match "^\s*host\s+all\s+all\s+$escapedAddress\s+") {
                if (-not $seen.ContainsKey($address)) {
                    $newContent += [string]$desired[$address]
                    $seen[$address] = $true
                }
                $matched = $true
                break
            }
        }
        if (-not $matched) {
            $newContent += $line
        }
    }

    foreach ($address in $desired.Keys) {
        if (-not $seen.ContainsKey($address)) {
            $newContent += [string]$desired[$address]
        }
    }

    Set-Content -LiteralPath $HbaPath -Value $newContent -Encoding UTF8
}

function Configure-PostgresDataDirectory {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $dataDir = Join-Path $Script:ProgramDataDir "postgres\data"
    $config = Join-Path $dataDir "postgresql.conf"
    $hba = Join-Path $dataDir "pg_hba.conf"
    $dbPort = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PORT"

    Set-PostgresConfigValue -ConfigPath $config -Key "port" -Value $dbPort
    Set-PostgresConfigValue -ConfigPath $config -Key "listen_addresses" -Value "'127.0.0.1'"
    Set-PostgresConfigValue -ConfigPath $config -Key "timezone" -Value "'America/El_Salvador'"
    Set-PostgresConfigValue -ConfigPath $config -Key "logging_collector" -Value "off"
    Set-PostgresHbaHostAuth -HbaPath $hba
    Write-InstallLog -LogName "postgres-init.log" -Message "POSTGRES_CONFIGURED port=$dbPort listen_addresses=127.0.0.1 timezone=America/El_Salvador logging_collector=off hba=scram-loopback"
}

function Get-LogTailText {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$Lines = 80
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return ""
    }
    $tail = Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction SilentlyContinue
    if (-not $tail) {
        return ""
    }
    return (($tail | ForEach-Object { [string]$_ }) -join "`n")
}

function Stop-PostgresForegroundTest {
    param(
        [Parameter(Mandatory = $true)]$Process,
        [Parameter(Mandatory = $true)][string]$DataDir,
        [Parameter(Mandatory = $true)][string]$PostgresBin,
        [Parameter(Mandatory = $true)][System.Management.Automation.PSCredential]$Credential
    )

    $pgCtl = Join-Path $PostgresBin "pg_ctl.exe"
    if (Test-Path -LiteralPath $pgCtl -PathType Leaf) {
        try {
            Invoke-AsPicoServiceAccount `
                -Credential $Credential `
                -FilePath $pgCtl `
                -ArgumentList @("-D", $DataDir, "-m", "fast", "-w", "stop") `
                -WorkingDirectory $PostgresBin `
                -LogName "postgres-foreground-test.stop.log"
        } catch {
            Write-InstallLog -LogName "postgres-foreground-test.stop.log" -Message ("PG_CTL_STOP_FAILED " + $_.Exception.Message)
        }
    }

    $Process.Refresh()
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $Process.Id -Timeout 20 -ErrorAction SilentlyContinue
    }
}

function Test-PostgresForegroundStartup {
    param([Parameter(Mandatory = $true)][System.Management.Automation.PSCredential]$Credential)

    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $postgres = Join-Path $postgresBin "postgres.exe"
    $dataDir = Join-Path $Script:ProgramDataDir "postgres\data"
    $stdout = Get-NativeLogPath "postgres-foreground-test.out.log"
    $stderr = Get-NativeLogPath "postgres-foreground-test.err.log"
    $waitSeconds = 10

    if (-not (Test-Path -LiteralPath $postgres -PathType Leaf)) {
        throw "No existe postgres.exe en runtime PostgreSQL nativo."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $dataDir "PG_VERSION") -PathType Leaf)) {
        throw "No existe PG_VERSION en directorio de datos PostgreSQL: $dataDir"
    }

    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    Write-InstallLog -LogName "postgres-service.log" -Message "POSTGRES_FOREGROUND_TEST_BEGIN seconds=$waitSeconds"
    Write-InstallLog -LogName "postgres-service.log" -Message "POSTGRES_FOREGROUND_TEST_RUN_AS $Script:PicoServiceAccountName"
    Write-InstallLog -LogName "install-services.log" -Message "POSTGRES_FOREGROUND_TEST_BEGIN stdout=$stdout stderr=$stderr"

    $process = Invoke-AsPicoServiceAccount `
        -Credential $Credential `
        -FilePath $postgres `
        -ArgumentList @("-D", $dataDir) `
        -WorkingDirectory $postgresBin `
        -StdoutPath $stdout `
        -StderrPath $stderr `
        -LogName "postgres-service.log" `
        -NoWait

    Start-Sleep -Seconds $waitSeconds
    $process.Refresh()
    if (-not $process.HasExited) {
        Write-InstallLog -LogName "postgres-service.log" -Message "POSTGRES_FOREGROUND_TEST_OK pid=$($process.Id)"
        Stop-PostgresForegroundTest -Process $process -DataDir $dataDir -PostgresBin $postgresBin -Credential $Credential
        return
    }

    $exitCode = $process.ExitCode
    $stdoutTail = Get-LogTailText -Path $stdout -Lines 80
    $stderrTail = Get-LogTailText -Path $stderr -Lines 80
    Write-InstallLog -LogName "postgres-service.log" -Message "POSTGRES_FOREGROUND_TEST_FAILED exitCode=$exitCode"
    Write-InstallLog -LogName "service-install.log" -Message "POSTGRES_FOREGROUND_TEST_FAILED exitCode=$exitCode"
    if (-not [string]::IsNullOrWhiteSpace($stdoutTail)) {
        Write-InstallLog -LogName "service-install.log" -Message ("POSTGRES_FOREGROUND_STDOUT_TAIL`n" + $stdoutTail)
    }
    if (-not [string]::IsNullOrWhiteSpace($stderrTail)) {
        Write-InstallLog -LogName "service-install.log" -Message ("POSTGRES_FOREGROUND_STDERR_TAIL`n" + $stderrTail)
    }
    Write-SafeHost "PostgreSQL foreground test fallo con codigo $exitCode."
    if (-not [string]::IsNullOrWhiteSpace($stderrTail)) {
        Write-SafeHost $stderrTail
    }
    if ($stderrTail -match "Execution of PostgreSQL by a user with administrative permissions is not permitted") {
        throw "PostgreSQL todavia se ejecuto como usuario administrador. La prueba foreground debe correr como .\$Script:PicoServiceAccountName. Revise $stderr"
    }
    throw "PostgreSQL foreground test fallo con codigo $exitCode. Revise $stderr"
}

function Wait-PostgresReady {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $pgIsReady = Join-Path $postgresBin "pg_isready.exe"
    if (-not (Test-Path -LiteralPath $pgIsReady -PathType Leaf)) {
        throw "Falta pg_isready.exe en runtime PostgreSQL nativo."
    }

    $dbHost = Get-RequiredEnvValue -Map $EnvMap -Name "DB_HOST"
    $dbPort = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PORT"
    $dbUser = Get-RequiredEnvValue -Map $EnvMap -Name "DB_USER"

    for ($i = 0; $i -lt 60; $i++) {
        & $pgIsReady -h $dbHost -p $dbPort -U $dbUser | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-InstallLog "POSTGRES_READY $dbHost`:$dbPort"
            Write-InstallLog -LogName "postgres-service.log" -Message "POSTGRES_READY $dbHost`:$dbPort"
            return
        }
        Start-Sleep -Seconds 2
    }

    throw "PostgreSQL no quedo listo para configuracion inicial."
}

function Ensure-ApplicationDatabase {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $postgresBin = Join-Path $Script:ProgramFilesDir "postgres\bin"
    $psql = Join-Path $postgresBin "psql.exe"
    $createdb = Join-Path $postgresBin "createdb.exe"
    foreach ($tool in @($psql, $createdb)) {
        if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
            throw "Falta herramienta PostgreSQL: $tool"
        }
    }

    $dbHost = Get-RequiredEnvValue -Map $EnvMap -Name "DB_HOST"
    $dbPort = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PORT"
    $dbName = Get-RequiredEnvValue -Map $EnvMap -Name "DB_NAME"
    $dbUser = Get-RequiredEnvValue -Map $EnvMap -Name "DB_USER"
    $dbPassword = Get-RequiredEnvValue -Map $EnvMap -Name "DB_PASSWORD"
    $pgEnv = @{ PGPASSWORD = $dbPassword }
    $roleSql = Join-Path ([System.IO.Path]::GetTempPath()) ("picopos-role-" + [Guid]::NewGuid().ToString("N") + ".sql")
    $escapedDbUser = $dbUser.Replace("'", "''")

    $roleExists = Invoke-LoggedCommand `
        -FilePath $psql `
        -ArgumentList @("-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-d", "postgres", "-tAc", "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '$escapedDbUser';") `
        -LogName "db-setup.log" `
        -Environment $pgEnv `
        -ReturnStdout
    if (($roleExists -join "").Trim() -eq "1") {
        Write-InstallLog -LogName "db-setup.log" -Message "DB_ROLE_EXISTS name=$dbUser"
    } else {
        Write-InstallLog -LogName "db-setup.log" -Message "DB_ROLE_MISSING_WILL_CREATE name=$dbUser"
    }

    try {
        $roleNameLiteral = Quote-PostgresLiteral -Value $dbUser
        $roleNameIdentifier = Quote-PostgresIdentifier -Value $dbUser
        $passwordLiteral = Quote-PostgresLiteral -Value $dbPassword
        @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = $roleNameLiteral) THEN
        CREATE ROLE $roleNameIdentifier WITH LOGIN PASSWORD $passwordLiteral;
    ELSE
        ALTER ROLE $roleNameIdentifier WITH LOGIN PASSWORD $passwordLiteral;
    END IF;
END
`$`$;
"@ | Set-Content -LiteralPath $roleSql -Encoding UTF8

        Invoke-LoggedCommand `
            -FilePath $psql `
            -ArgumentList @("-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-f", $roleSql) `
            -LogName "db-setup.log" `
            -Environment $pgEnv
    } finally {
        Remove-Item -LiteralPath $roleSql -Force -ErrorAction SilentlyContinue
    }

    $escapedDbName = $dbName.Replace("'", "''")
    $exists = Invoke-LoggedCommand `
        -FilePath $psql `
        -ArgumentList @("-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-d", "postgres", "-tAc", "SELECT 1 FROM pg_database WHERE datname = '$escapedDbName';") `
        -LogName "db-setup.log" `
        -Environment $pgEnv `
        -ReturnStdout

    if (($exists -join "").Trim() -ne "1") {
        Write-InstallLog -LogName "db-setup.log" -Message "DB_MISSING_WILL_CREATE name=$dbName owner=$dbUser"
        Invoke-LoggedCommand `
            -FilePath $createdb `
            -ArgumentList @("-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-O", $dbUser, $dbName) `
            -LogName "db-setup.log" `
            -Environment $pgEnv
    } else {
        Write-InstallLog -LogName "db-setup.log" -Message "DB_EXISTS name=$dbName"
    }
}

function Render-Caddyfile {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$EnvMap)

    $template = Join-Path $Script:ProgramFilesDir "caddy\Caddyfile.template"
    $caddyfile = Join-Path $Script:ProgramFilesDir "caddy\Caddyfile"
    if (-not (Test-Path -LiteralPath $template -PathType Leaf)) {
        throw "Falta Caddyfile.template en runtime nativo."
    }

    $bind = [string]$EnvMap["APP_BIND_ADDRESS"]
    if ([string]::IsNullOrWhiteSpace($bind)) { $bind = "127.0.0.1" }
    $port = [string]$EnvMap["APP_HTTP_PORT"]
    if ([string]::IsNullOrWhiteSpace($port)) { $port = "9282" }

    (Get-Content -LiteralPath $template -Raw).
        Replace("{{APP_BIND_ADDRESS}}", $bind).
        Replace("{{APP_HTTP_PORT}}", $port).
        Replace("{{PROGRAM_FILES_DIR}}", $Script:ProgramFilesDir.Replace("\", "/")).
        Replace("{{PROGRAM_DATA_DIR}}", $Script:ProgramDataDir.Replace("\", "/")) |
        Set-Content -LiteralPath $caddyfile -Encoding UTF8

    Write-InstallLog "CADDYFILE_RENDERED $caddyfile"
}

function Validate-EmbeddedPythonImports {
    $python = Join-Path $Script:ProgramFilesDir "python\python.exe"
    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList @("-c", "import django, waitress, psycopg2, requests; print('Python runtime OK')") `
        -LogName "python-runtime.log"
}

function Get-DjangoEnvironment {
    return @{
        DJANGO_ENV_FILE = (Get-EnvPath)
        DOTENV_OVERRIDE = "false"
        DJANGO_SETTINGS_MODULE = "config.settings"
        PYTHONUNBUFFERED = "1"
    }
}

function Run-DjangoSetup {
    $python = Join-Path $Script:ProgramFilesDir "python\python.exe"
    $backend = Join-Path $Script:ProgramFilesDir "backend"
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "No existe python.exe en runtime nativo."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $backend "manage.py") -PathType Leaf)) {
        throw "No existe backend Django en $backend"
    }

    $djangoEnv = Get-DjangoEnvironment

    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList @("manage.py", "check_runtime_config", "--strict") `
        -WorkingDirectory $backend `
        -Environment $djangoEnv `
        -LogName "check-runtime-config.log"

    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList @("manage.py", "migrate", "--noinput") `
        -WorkingDirectory $backend `
        -Environment $djangoEnv `
        -LogName "migrate.log"

    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList @("manage.py", "collectstatic", "--noinput") `
        -WorkingDirectory $backend `
        -Environment $djangoEnv `
        -LogName "collectstatic.log"
}

function Run-InitialAdminBootstrap {
    $python = Join-Path $Script:ProgramFilesDir "python\python.exe"
    $backend = Join-Path $Script:ProgramFilesDir "backend"
    Invoke-LoggedCommand `
        -FilePath $python `
        -ArgumentList @("manage.py", "bootstrap_initial_admin") `
        -WorkingDirectory $backend `
        -Environment (Get-DjangoEnvironment) `
        -LogName "bootstrap-admin.log"
}

function Wait-HttpOk {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$Name,
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = ""
    do {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
            $status = [int]$response.StatusCode
            if ($status -ge 200 -and $status -lt 300) {
                Write-InstallLog -LogName "healthcheck.log" -Message "HTTP_OK $Name $Uri status=$status"
                return
            }
            $lastError = "status=$status"
        } catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    Write-InstallLog -LogName "healthcheck.log" -Message "HTTP_FAILED $Name $Uri $lastError"
    throw "Validacion HTTP fallo para $Name ($Uri): $lastError"
}

function Start-BackendService {
    Start-WinSWService -ServiceId "PicoDeGallo-Backend"
    Wait-HttpOk -Name "backend-ready-direct" -Uri "http://127.0.0.1:8000/api/health/ready/" -TimeoutSeconds 120
}

function Start-DteServices {
    Start-WinSWService -ServiceId "PicoDeGallo-DTE-Worker"
    Start-WinSWService -ServiceId "PicoDeGallo-DTE-Monitor"
}

function Start-CaddyService {
    Start-WinSWService -ServiceId "PicoDeGallo-Caddy"
}

function Validate-PostInstall {
    $appUrl = Get-AppUrl
    Wait-HttpOk -Name "caddy-root" -Uri $appUrl -TimeoutSeconds 120
    Wait-HttpOk -Name "health-live" -Uri "$appUrl/api/health/live/" -TimeoutSeconds 120
    Wait-HttpOk -Name "health-ready" -Uri "$appUrl/api/health/ready/" -TimeoutSeconds 120
    Assert-AllServicesRunning
}

foreach ($dir in @("config", "media", "static", "dte_logs", "backups", "diagnostics", "logs", "postgres\data")) {
    New-DirectorySafe (Join-Path $Script:ProgramDataDir $dir)
}

Stop-ExistingServicesForLogArchive
Archive-ExistingNativeLogs
Write-InstallLog "INSTALL_SERVICES_BEGIN ProgramFiles=$Script:ProgramFilesDir ProgramData=$Script:ProgramDataDir"

if (-not (Test-Path -LiteralPath (Get-EnvPath) -PathType Leaf)) {
    & "$PSScriptRoot\init-env.ps1"
}

$envs = Read-NativeEnv
Test-DteEnv | Out-Null
$picoServiceCredential = Ensure-PicoServiceAccount
Grant-PicoServiceAccountPermissions -Credential $picoServiceCredential

$tokens = @{
    PROGRAM_FILES_DIR = $Script:ProgramFilesDir
    PROGRAM_DATA_DIR = $Script:ProgramDataDir
    POSTGRES_BIN_DIR = (Join-Path $Script:ProgramFilesDir "postgres\bin")
    POSTGRES_DATA_DIR = (Join-Path $Script:ProgramDataDir "postgres\data")
    PICO_SERVICE_ACCOUNT_XML = New-WinSWServiceAccountXml
    PYTHON_EXE = (Join-Path $Script:ProgramFilesDir "python\python.exe")
    BACKEND_DIR = (Join-Path $Script:ProgramFilesDir "backend")
    ENV_FILE = (Get-EnvPath)
    CADDY_EXE = (Join-Path $Script:ProgramFilesDir "caddy\caddy.exe")
    APP_HTTP_PORT = if ([string]::IsNullOrWhiteSpace([string]$envs["APP_HTTP_PORT"])) { "9282" } else { [string]$envs["APP_HTTP_PORT"] }
    APP_BIND_ADDRESS = if ([string]::IsNullOrWhiteSpace([string]$envs["APP_BIND_ADDRESS"])) { "127.0.0.1" } else { [string]$envs["APP_BIND_ADDRESS"] }
}

Validate-EmbeddedPythonImports
Assert-PostgresRuntimeTools
Invoke-PostgresRuntimeVersionChecks
Initialize-PostgresDataDirectory -EnvMap $envs -Credential $picoServiceCredential
Configure-PostgresDataDirectory -EnvMap $envs
Grant-PicoServiceAccountPermissions -Credential $picoServiceCredential
Test-PostgresForegroundStartup -Credential $picoServiceCredential
Install-WinSWServices -Tokens $tokens -ServiceIds @("PicoDeGallo-PostgreSQL") -PicoServiceCredential $picoServiceCredential
Start-WinSWService -ServiceId "PicoDeGallo-PostgreSQL"
$dbHost = Get-RequiredEnvValue -Map $envs -Name "DB_HOST"
$dbPort = [int](Get-RequiredEnvValue -Map $envs -Name "DB_PORT")
Wait-TcpPort -HostName $dbHost -Port $dbPort -TimeoutSeconds 60 -ServiceId "PicoDeGallo-PostgreSQL"
Wait-PostgresReady -EnvMap $envs
Ensure-ApplicationDatabase -EnvMap $envs
Run-DjangoSetup
Run-InitialAdminBootstrap
Install-WinSWServices -Tokens $tokens -ServiceIds @("PicoDeGallo-Backend")
Start-BackendService
Install-WinSWServices -Tokens $tokens -ServiceIds @("PicoDeGallo-DTE-Worker", "PicoDeGallo-DTE-Monitor")
Start-DteServices
Render-Caddyfile -EnvMap $envs
Install-WinSWServices -Tokens $tokens -ServiceIds @("PicoDeGallo-Caddy")
Start-CaddyService
Validate-PostInstall

foreach ($svc in $Script:Services) {
    Write-SafeHost "Servicio listo: $svc"
}

Write-InstallLog "INSTALL_SERVICES_SUCCESS"
