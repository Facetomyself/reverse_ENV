#requires -Version 5.1

<#
.SYNOPSIS
Initialize a reverse-engineering LDPlayer instance for a project.
Creates a dedicated, isolated instance: configure → launch → ADB-ready.

.DESCRIPTION
Each RE project gets its own LDPlayer instance (name = project name).
If an instance already exists, it re-launches without re-creating.
MAA instance (index 0) is never touched.

.PARAMETER Project
Project name — also used as the instance name. (required)

.PARAMETER Resolution
Screen resolution "W,H,DPI". Default: "1920,1080,320"

.PARAMETER Cpu
CPU cores. Default: 4

.PARAMETER Memory
Memory in MB. Default: 4096

.PARAMETER NoLaunch
Create & configure only, don't launch.

Usage:
  powershell -File "re-init.ps1" -Project myapp
  powershell -File "re-init.ps1" -Project myapp -Resolution "1280,720,240" -Cpu 2 -Memory 2048
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [string]$Resolution = "1920,1080,320",
    [int]$Cpu = 4,
    [int]$Memory = 4096,
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# ── Paths ──────────────────────────────────────────────────────────
$LdConsole = 'D:\leidian\LDPlayer9\ldconsole.exe'
$AdbExe    = 'D:\leidian\LDPlayer9\adb.exe'
$MaaIndex  = 0

# ── Helpers ────────────────────────────────────────────────────────

function Invoke-Ld {
    param([string[]]$LdArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $out = & $LdConsole @LdArgs 2>$null
    $ErrorActionPreference = $prev
    if ($out -is [array]) { return $out }
    if ($out) { return @($out) }
    return @()
}

function Get-Instances {
    $raw = Invoke-Ld -LdArgs 'list2'
    $instances = @()
    foreach ($line in $raw) {
        if (-not $line.Trim()) { continue }
        $parts = $line -split ','
        if ($parts.Count -lt 5) { continue }
        $instances += [PSCustomObject]@{
            Index   = [int]$parts[0]
            Name    = $parts[1]
            Running = [int]$parts[4] -eq 1
            Width   = $parts[7]
            Height  = $parts[8]
            Dpi     = $parts[9]
            Adb     = "emulator-$([int]$parts[0] * 2 + 5554)"
        }
    }
    return $instances | Sort-Object Index
}

function Test-AdbReady {
    param([string]$AdbAddr, [int]$TimeoutSec = 60)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $result = & $AdbExe -s $AdbAddr shell 'echo ready' 2>$null
        if ($result -match 'ready') { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

# ── Main ───────────────────────────────────────────────────────────

Write-Output ''
Write-Output "=== RE Instance Init: $Project ==="
Write-Output ''

# 1. Check if project instance already exists
$instances = Get-Instances
$existing = $instances | Where-Object { $_.Name -eq $Project }

if ($existing) {
    Write-Output "Instance '$Project' already exists (index $($existing.Index))."

    if ($existing.Running) {
        Write-Output "  Status:   RUNNING"
        Write-Output "  ADB:      $($existing.Adb)"
        Write-Output ''
        Write-Output "OK:ready (already running)"
        exit 0
    }

    Write-Output "  Status:   STOPPED — launching..."
    Invoke-Ld -LdArgs @('launch', '--name', $Project) | Out-Null

    Write-Output "  Waiting for ADB ($($existing.Adb))..."
    if (Test-AdbReady -AdbAddr $existing.Adb) {
        Write-Output ''
        Write-Output "OK:ready"
        Write-Output "  Index: $($existing.Index)  Name: $Project  ADB: $($existing.Adb)"
        Write-Output "  Resolution: $($existing.Width)x$($existing.Height)@$($existing.Dpi)dpi"
    } else {
        Write-Output "WARN: ADB not ready after 60s — instance may still be booting"
        Write-Output "  Check: adb -s $($existing.Adb) shell echo ready"
    }
    exit 0
}

# 2. Create new instance
Write-Output "Creating new instance '$Project'..."
$before = Get-Instances | ForEach-Object { $_.Index }

$addResult = Invoke-Ld -LdArgs @('add', '--name', $Project)
Write-Output "  ldconsole add: $addResult"

# Find the new instance index
Start-Sleep -Seconds 3
$after = Get-Instances
$newInst = $after | Where-Object { $_.Name -eq $Project } | Select-Object -First 1

if (-not $newInst) {
    Write-Output "ERR: Failed to find new instance '$Project' after creation."
    Write-Output "  Try: ldconsole list2"
    exit 1
}

Write-Output "  Created:  index=$($newInst.Index)  name=$Project"

# 3. Configure
Write-Output "Configuring instance..."
$modArgs = @('modify', '--name', $Project,
             '--resolution', $Resolution,
             '--cpu', [string]$Cpu,
             '--memory', [string]$Memory,
             '--root', '1')
Invoke-Ld -LdArgs $modArgs | Out-Null
Write-Output "  Root:      ON"
Write-Output "  Resolution: $Resolution"
Write-Output "  CPU/Memory: $Cpu cores / ${Memory}MB"

if ($NoLaunch) {
    Write-Output ''
    Write-Output "OK:created (not launched — -NoLaunch)"
    Write-Output "  Index: $($newInst.Index)  Name: $Project"
    Write-Output "  Launch with: ldconsole launch --name $Project"
    exit 0
}

# 4. Launch
Write-Output "Launching instance..."
Invoke-Ld -LdArgs @('launch', '--name', $Project) | Out-Null

# 5. Wait for ADB
$adbAddr = "emulator-$($newInst.Index * 2 + 5554)"
Write-Output "Waiting for ADB ($adbAddr)..."
if (Test-AdbReady -AdbAddr $adbAddr -TimeoutSec 90) {
    Write-Output ''
    Write-Output "OK:ready"
    Write-Output "  Index: $($newInst.Index)  Name: $Project  ADB: $adbAddr"
    Write-Output ''
    Write-Output "Next steps:"
    Write-Output "  re-list.ps1            — check all instances"
    Write-Output "  re-proxy.ps1 -Project $Project -Action on  — enable HTTPS interception"
} else {
    Write-Output "WARN: ADB not ready after 90s"
    Write-Output "  Instance may still be booting. Check: adb -s $adbAddr shell echo ready"
}
