#requires -Version 5.1

<#
.SYNOPSIS
Create, configure, and optionally launch a project-dedicated LDPlayer instance.

.DESCRIPTION
The project name is also the LDPlayer instance name and workspace directory
name. Only ASCII letters, digits, dot, underscore, and dash are allowed.
Index 0 is reserved for MAA and is never touched by this script.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$Project,

    [string]$Resolution = '1920,1080,320',
    [int]$Cpu = 4,
    [int]$Memory = 4096,
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$LdConsole = 'D:\leidian\LDPlayer9\ldconsole.exe'
$AdbExe = 'D:\leidian\LDPlayer9\adb.exe'
$MaaIndex = 0

function Assert-FileExists {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Output "ERR:${Label}_not_found:$Path"
        exit 1
    }
}

function Invoke-Ld {
    param(
        [Parameter(Mandatory = $true)][string[]]$LdArgs,
        [switch]$AllowNonZero
    )
    Assert-FileExists -Path $LdConsole -Label 'ldconsole'
    $out = & $LdConsole @LdArgs 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0 -and -not $AllowNonZero) {
        Write-Output "ERR:ldconsole_failed:$code"
        Write-Output "CMD:ldconsole $($LdArgs -join ' ')"
        if ($out) { Write-Output $out }
        exit $code
    } elseif ($code -ne 0) {
        Write-Output "WARN:ldconsole_nonzero_exit:$code cmd=ldconsole $($LdArgs -join ' ')"
    }
    if ($out -is [array]) { return $out }
    if ($out) { return @($out) }
    return @()
}

function Get-Instances {
    $raw = Invoke-Ld -LdArgs @('list2')
    $instances = @()
    foreach ($line in $raw) {
        if (-not $line.Trim()) { continue }
        $parts = $line -split ','
        if ($parts.Count -lt 10) { continue }
        $idx = [int]$parts[0]
        $instances += [PSCustomObject]@{
            Index = $idx
            Name = $parts[1]
            Running = [int]$parts[4] -eq 1
            Width = $parts[7]
            Height = $parts[8]
            Dpi = $parts[9]
            Adb = "emulator-$($idx * 2 + 5554)"
        }
    }
    return @($instances | Sort-Object Index)
}

function Test-AdbReady {
    param([string]$AdbAddr, [int]$TimeoutSec = 60)
    Assert-FileExists -Path $AdbExe -Label 'adb'
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $result = & $AdbExe -s $AdbAddr shell 'echo ready' 2>$null
        $ErrorActionPreference = $prev
        if ($result -match 'ready') { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

Write-Output ''
Write-Output "=== RE Instance Init: $Project ==="
Write-Output ''

$instances = Get-Instances
$existing = $instances | Where-Object { $_.Name -eq $Project } | Select-Object -First 1

if ($existing) {
    if ($existing.Index -eq $MaaIndex) {
        Write-Output "ERR:project_resolves_to_index_0_MAA:$Project"
        exit 1
    }

    Write-Output "Instance '$Project' already exists (index $($existing.Index))."

    if ($existing.Running) {
        Write-Output '  Status:   RUNNING'
        Write-Output "  ADB:      $($existing.Adb)"
        Write-Output ''
        Write-Output 'OK:ready (already running)'
        exit 0
    }

    Write-Output '  Status:   STOPPED - launching...'
    Invoke-Ld -LdArgs @('launch', '--index', [string]$existing.Index) | Out-Null

    Write-Output "  Waiting for ADB ($($existing.Adb))..."
    if (Test-AdbReady -AdbAddr $existing.Adb) {
        Write-Output ''
        Write-Output 'OK:ready'
        Write-Output "  Index: $($existing.Index)  Name: $Project  ADB: $($existing.Adb)"
        Write-Output "  Resolution: $($existing.Width)x$($existing.Height)@$($existing.Dpi)dpi"
    } else {
        Write-Output 'WARN:ADB_not_ready_after_60s'
        Write-Output "  Check: $AdbExe -s $($existing.Adb) shell echo ready"
    }
    exit 0
}

Write-Output "Creating new instance '$Project'..."
Invoke-Ld -LdArgs @('add', '--name', $Project) -AllowNonZero | Out-Null

Start-Sleep -Seconds 3
$newInst = Get-Instances | Where-Object { $_.Name -eq $Project } | Select-Object -First 1
if (-not $newInst) {
    Write-Output "ERR:failed_to_find_new_instance:$Project"
    exit 1
}
if ($newInst.Index -eq $MaaIndex) {
    Write-Output "ERR:new_instance_is_index_0_MAA:$Project"
    exit 1
}

Write-Output "  Created: index=$($newInst.Index) name=$Project"

Write-Output 'Configuring instance...'
Invoke-Ld -LdArgs @(
    'modify',
    '--index', [string]$newInst.Index,
    '--resolution', $Resolution,
    '--cpu', [string]$Cpu,
    '--memory', [string]$Memory,
    '--root', '1'
) | Out-Null
Write-Output '  Root:      ON'
Write-Output "  Resolution: $Resolution"
Write-Output "  CPU/Memory: $Cpu cores / ${Memory}MB"

if ($NoLaunch) {
    Write-Output ''
    Write-Output 'OK:created (not launched)'
    Write-Output "  Index: $($newInst.Index)  Name: $Project"
    Write-Output "  Launch with: $LdConsole launch --index $($newInst.Index)"
    exit 0
}

Write-Output 'Launching instance...'
Invoke-Ld -LdArgs @('launch', '--index', [string]$newInst.Index) | Out-Null

$adbAddr = "emulator-$($newInst.Index * 2 + 5554)"
Write-Output "Waiting for ADB ($adbAddr)..."
if (Test-AdbReady -AdbAddr $adbAddr -TimeoutSec 90) {
    Write-Output ''
    Write-Output 'OK:ready'
    Write-Output "  Index: $($newInst.Index)  Name: $Project  ADB: $adbAddr"
    Write-Output ''
    Write-Output 'Next steps:'
    Write-Output '  re-list.ps1'
    Write-Output "  re-proxy.ps1 -Project $Project -Action on"
} else {
    Write-Output 'WARN:ADB_not_ready_after_90s'
    Write-Output "  Check: $AdbExe -s $adbAddr shell echo ready"
}
