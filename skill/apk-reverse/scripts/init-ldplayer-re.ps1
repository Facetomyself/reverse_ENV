#requires -Version 5.1

<#
.SYNOPSIS
  Prepare one explicit LDPlayer ADB device for APK reverse engineering.

.DESCRIPTION
  Verifies ADB/root/ABI, checks the device frida-server version against the
  project Frida CLI, pushes the project server when missing (or when
  -ReplaceServer is explicitly supplied), starts it, and reports readiness.

.PARAMETER Instance
  Deprecated compatibility parameter. It is accepted only when it already is
  an ADB serial; LDPlayer names are resolved by ldplayer-control, not here.

.PARAMETER DeviceSerial
  ADB serial such as emulator-5560. Required when multiple devices are online.

.PARAMETER FridaServerPath
  Local Android frida-server binary. Defaults to D:\reverse_ENV\tools\frida-server.

.PARAMETER ReplaceServer
  Replace an existing device server when its version differs. Without this
  switch, version mismatch is reported and the script stops.
#>

[CmdletBinding()]
param(
    [string]$Instance = '',
    [string]$DeviceSerial = '',
    [string]$FridaServerPath = 'D:\reverse_ENV\tools\frida-server',
    [switch]$ReplaceServer
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$adb = 'D:\reverse_ENV\tools\adb\adb.exe'
$fridaCli = 'D:\reverse_ENV\.venv\Scripts\frida.exe'
$python = 'D:\reverse_ENV\.venv\Scripts\python.exe'

function Get-AdbDevices {
    $lines = & $adb devices 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "adb devices failed: $($lines -join "`n")"
    }

    $result = @()
    foreach ($line in $lines) {
        if ($line -match '^\s*(\S+)\s+device\s*$') {
            $result += $Matches[1]
        }
    }
    return @($result)
}

function Resolve-AdbSerial {
    param(
        [string]$RequestedSerial,
        [string]$RequestedInstance
    )

    $devices = @(Get-AdbDevices)
    if ($devices.Count -eq 0) {
        throw 'No ADB device found. Start the LDPlayer project instance first.'
    }

    if (-not [string]::IsNullOrWhiteSpace($RequestedInstance) -and [string]::IsNullOrWhiteSpace($RequestedSerial)) {
        if ($devices -contains $RequestedInstance) {
            Write-Warning '-Instance matched an ADB serial. Prefer -DeviceSerial.'
            return $RequestedInstance
        }
        throw "-Instance '$RequestedInstance' is not an ADB serial. Resolve the instance with ldplayer-control/re-list.ps1 and pass -DeviceSerial."
    }

    if (-not [string]::IsNullOrWhiteSpace($RequestedSerial)) {
        if ($devices -notcontains $RequestedSerial) {
            throw "ADB device '$RequestedSerial' is not connected. Connected serials: $($devices -join ', ')"
        }
        return $RequestedSerial
    }

    if ($devices.Count -ne 1) {
        throw "Multiple ADB devices connected; pass -DeviceSerial. Connected serials: $($devices -join ', ')"
    }
    return $devices[0]
}

function Invoke-Adb {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$AdbArgs)

    & $adb -s $DeviceSerial @AdbArgs
}

if (-not (Test-Path -LiteralPath $adb)) {
    throw "adb not found: $adb"
}
if (-not (Test-Path -LiteralPath $fridaCli)) {
    throw "Frida CLI not found: $fridaCli"
}
if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python not found: $python"
}

Write-Host '=== Step 1: ADB ==='
$DeviceSerial = Resolve-AdbSerial -RequestedSerial $DeviceSerial -RequestedInstance $Instance
Write-Host "[OK] Device connected: $DeviceSerial"

Write-Host "`n=== Step 2: Root ==="
$rootCheck = Invoke-Adb shell su -c id 2>&1
if ($LASTEXITCODE -ne 0 -or ($rootCheck -join "`n") -notmatch 'uid=0') {
    throw 'Root is unavailable. Use an RE template with Root enabled.'
}
Write-Host '[OK] Root access confirmed'

Write-Host "`n=== Step 3: Device profile ==="
$primaryAbi = (Invoke-Adb shell getprop ro.product.cpu.abi 2>&1 | Select-Object -First 1).Trim()
$abiList = (Invoke-Adb shell getprop ro.product.cpu.abilist 2>&1 | Select-Object -First 1).Trim()
$nativeBridge = (Invoke-Adb shell getprop ro.dalvik.vm.native.bridge 2>&1 | Select-Object -First 1).Trim()
$androidVersion = (Invoke-Adb shell getprop ro.build.version.release 2>&1 | Select-Object -First 1).Trim()
Write-Host "  Android:       $androidVersion"
Write-Host "  Primary ABI:   $primaryAbi"
Write-Host "  ABI list:      $abiList"
Write-Host "  Native bridge: $nativeBridge"

Write-Host "`n=== Step 4: Frida server ==="
$hostVersion = (& $fridaCli --version 2>&1 | Select-Object -First 1).Trim()
$remotePath = '/data/local/tmp/frida-server'
$remoteExists = (Invoke-Adb shell "test -f $remotePath && echo EXISTS" 2>&1 | Out-String) -match 'EXISTS'
$remoteVersion = ''
if ($remoteExists) {
    $remoteVersion = (Invoke-Adb shell su -c "$remotePath --version" 2>&1 | Select-Object -First 1).Trim()
}

$needsPush = -not $remoteExists
if ($remoteExists -and $remoteVersion -ne $hostVersion) {
    if (-not $ReplaceServer) {
        throw "Frida version mismatch: host=$hostVersion device=$remoteVersion. Pass a matching -FridaServerPath and -ReplaceServer to replace it explicitly."
    }
    $needsPush = $true
}

if ($needsPush) {
    if (-not (Test-Path -LiteralPath $FridaServerPath)) {
        throw "Frida server not found: $FridaServerPath (required version: $hostVersion)"
    }

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    Invoke-Adb shell su -c 'killall frida-server' 2>$null | Out-Null
    $ErrorActionPreference = $previousPreference
    Start-Sleep -Milliseconds 500

    Write-Host "Pushing frida-server from: $FridaServerPath"
    Invoke-Adb push $FridaServerPath $remotePath 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to push frida-server.'
    }
    Invoke-Adb shell su -c "chmod 755 $remotePath" 2>&1 | Out-Null
    $remoteVersion = (Invoke-Adb shell su -c "$remotePath --version" 2>&1 | Select-Object -First 1).Trim()
    if ($remoteVersion -ne $hostVersion) {
        throw "Pushed server version still mismatches: host=$hostVersion device=$remoteVersion"
    }
}
else {
    Write-Host "[OK] Existing server version matches host: $hostVersion"
}

$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
Invoke-Adb shell su -c 'killall frida-server' 2>$null | Out-Null
$ErrorActionPreference = $previousPreference
Start-Sleep -Milliseconds 500

Invoke-Adb shell su -c "nohup $remotePath -D >/dev/null 2>&1 &" 2>&1 | Out-Null
Start-Sleep -Seconds 2
$fridaPid = (Invoke-Adb shell su -c 'pidof frida-server' 2>&1 | Out-String).Trim()
if ([string]::IsNullOrWhiteSpace($fridaPid)) {
    throw 'frida-server failed to start.'
}

Write-Host "[OK] frida-server running: pid=$fridaPid version=$hostVersion"

Write-Host "`n=== Step 5: Host-to-device Frida handshake ==="
try {
    $env:APK_REVERSE_FRIDA_DEVICE = $DeviceSerial
    $handshakeCode = "import os,frida; d=frida.get_device_manager().get_device(os.environ['APK_REVERSE_FRIDA_DEVICE'], timeout=10); print(len(d.enumerate_processes()))"
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $handshakeOutput = @(& $python -c $handshakeCode 2>&1)
    $handshakeExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousPreference
    $processCount = if ($handshakeOutput.Count -gt 0) { ([string]$handshakeOutput[-1]).Trim() } else { '' }
    if ($handshakeExitCode -ne 0 -or $processCount -notmatch '^\d+$') {
        throw "Frida handshake failed for device '$DeviceSerial': $($handshakeOutput -join ' ')"
    }
}
finally {
    Remove-Item Env:APK_REVERSE_FRIDA_DEVICE -ErrorAction SilentlyContinue
}
Write-Host "[OK] Host Frida enumerated $processCount processes"

Write-Host "`n=== Environment Ready ==="
Write-Host "  Device:        $DeviceSerial"
Write-Host "  Root:          available"
Write-Host "  Frida:         $hostVersion"
Write-Host "  Primary ABI:   $primaryAbi"
Write-Host "  Native bridge: $nativeBridge"
Write-Host ''
Write-Host 'Next steps:'
Write-Host '  - DEX dump:  dump-dex.ps1 (panda-dex-dumper wrapper)'
Write-Host '  - Frida:    frida-run.ps1 -DeviceId <id> -Spawn -Package <pkg> -ScriptPath <script>'
Write-Host '  - HTTPS:    ldplayer-control/re-proxy.ps1 -Project <project> -Action on'
