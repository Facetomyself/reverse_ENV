#requires -Version 5.1

<#
.SYNOPSIS
LDPlayer 9 多实例管控：列表、状态、ADB、关机、重启、安装

LDPlayer 9 实例与 ADB 地址映射：leidian{N} ↔ emulator-{5554 + N*2}
使用雷电自带 ADB（D:\leidian\LDPlayer9\adb.exe）。

.PARAMETER Action
list | status | adb | stop | reboot | install

.PARAMETER Index
实例编号（默认 0）。Index 0 = emulator-5554（MAA 正在使用，写操作需谨慎）

.PARAMETER ApkPath
install 时的 APK 路径
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('list', 'status', 'adb', 'stop', 'reboot', 'install')]
    [string]$Action,

    [int]$Index = 0,

    [string]$ApkPath
)

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding           = [System.Text.UTF8Encoding]::new($false)

$AdbExe      = 'D:\leidian\LDPlayer9\adb.exe'
$VBoxManage  = 'C:\Program Files\ldplayer9box\VBoxManage.exe'

# ADB address: emulator-5554 + index*2
function Get-AdbAddr { param([int]$I) return "emulator-$($I * 2 + 5554)" }
function Get-VmName  { param([int]$I) return "leidian$I" }

$AdbAddr = Get-AdbAddr -I $Index
$VmName  = Get-VmName  -I $Index

# ── helpers ──────────────────────────────────────────────────────────

# VBox VM-level query (no ADB needed — works even when device is off)
function Get-AllVms {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $list = & $VBoxManage list vms 2>$null
    $running = & $VBoxManage list runningvms 2>$null
    $ErrorActionPreference = $prev

    $vms = @()
    foreach ($line in $list) {
        if ($line -match '^"(leidian(\d+))"') {
            $name = $Matches[1]
            $idx  = [int]$Matches[2]
            $running = $running -match [regex]::Escape($name)
            $vms += @{
                Index   = $idx
                Name    = $name
                Adb     = Get-AdbAddr -I $idx
                Running = $running
            }
        }
    }
    $vms = $vms | Sort-Object Index
    return $vms
}

# ADB-level device check
function Test-AdbOnline {
    param([string]$Addr = $AdbAddr)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $devices = & $AdbExe devices 2>$null
    $ErrorActionPreference = $prev
    return ($devices -match "$Addr\s+device")
}

function Get-AdbProp {
    param([string]$Prop, [string]$Addr = $AdbAddr)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $val = & $AdbExe -s $Addr shell getprop $Prop 2>$null
    $ErrorActionPreference = $prev
    return ($val -replace "[\r\n]", "").Trim()
}

function Warn-MaaInstance {
    if ($Index -eq 0) {
        Write-Output 'WARN: index=0 is emulator-5554 — MAA is likely using this instance'
    }
}

# ── actions ──────────────────────────────────────────────────────────

switch ($Action) {

    'list' {
        $vms = Get-AllVms
        if (-not $vms) {
            Write-Output 'No LDPlayer instances found.'
            exit 0
        }
        Write-Output "LDPlayer instances ($($vms.Count) total):"
        Write-Output ''
        foreach ($vm in $vms) {
            $marker = ''
            if ($vm.Index -eq 0) { $marker = ' [MAA]' }
            $state = if ($vm.Running) { 'RUNNING' } else { 'STOPPED' }

            # Check ADB if running
            $adbStatus = ''
            if ($vm.Running) {
                if (Test-AdbOnline -Addr $vm.Adb) {
                    $model = Get-AdbProp -Prop 'ro.product.model' -Addr $vm.Adb
                    $adbStatus = " ADB=$($vm.Adb) model=$model"
                } else {
                    $adbStatus = " ADB=offline"
                }
            }

            Write-Output "  [$($vm.Index)] $($vm.Name)  $state$adbStatus$marker"
        }
    }

    'status' {
        $online = Test-AdbOnline
        $vmRunning = (Get-AllVms | Where-Object { $_.Index -eq $Index }).Running

        if ($online) {
            $model = Get-AdbProp -Prop 'ro.product.model'
            $dpi   = Get-AdbProp -Prop 'ro.sf.lcd_density'
            $sdk   = Get-AdbProp -Prop 'ro.build.version.sdk'
            Write-Output "Index:     $Index"
            Write-Output "VM:        $VmName"
            Write-Output "ADB:       $AdbAddr"
            Write-Output "Status:    RUNNING"
            Write-Output "Model:     $model"
            Write-Output "DPI:       $dpi"
            Write-Output "SDK:       $sdk"
            if ($Index -eq 0) { Write-Output "Note:      MAA is using this instance" }
        } elseif ($vmRunning) {
            Write-Output "Index:     $Index"
            Write-Output "VM:        $VmName (running, ADB offline — booting?)"
        } else {
            Write-Output "Index:     $Index"
            Write-Output "VM:        $VmName"
            Write-Output "Status:    STOPPED"
            Write-Output "HINT:      Start via LDPlayer Multi-instance Manager (dnmultiplayer.exe)"
        }
    }

    'adb' {
        $r = & $AdbExe devices -l 2>&1
        Write-Output $r
        if ($Index -ne 0) {
            Write-Output ''
            Write-Output "Target instance $Index : $AdbAddr"
            if ($r -match [regex]::Escape($AdbAddr)) {
                Write-Output "  -> online"
            } else {
                Write-Output "  -> NOT in device list"
            }
        }
    }

    'stop' {
        Warn-MaaInstance
        if (-not (Test-AdbOnline)) {
            Write-Output "OK:already_stopped ($AdbAddr)"
            exit 0
        }
        Write-Output "Shutting down $VmName ($AdbAddr)..."
        & $AdbExe -s $AdbAddr shell reboot -p 2>$null | Out-Null
        Start-Sleep -Seconds 8
        if (-not (Test-AdbOnline)) {
            Write-Output 'OK:stopped'
        } else {
            Write-Output 'WARN: still online (may need force via GUI)'
        }
    }

    'reboot' {
        Warn-MaaInstance
        if (-not (Test-AdbOnline)) {
            Write-Output "ERR:device_offline ($AdbAddr)"
            exit 1
        }
        Write-Output "Rebooting $VmName ($AdbAddr)..."
        & $AdbExe -s $AdbAddr reboot 2>$null | Out-Null
        Start-Sleep -Seconds 15
        if (Test-AdbOnline) { Write-Output 'OK:back_online' }
        else { Write-Output 'WARN:still_booting (may take 30-60s)' }
    }

    'install' {
        if (-not $ApkPath) { Write-Output 'ERR: -ApkPath required'; exit 1 }
        if (-not (Test-Path $ApkPath)) { Write-Output "ERR:file_not_found: $ApkPath"; exit 1 }
        if (-not (Test-AdbOnline)) { Write-Output "ERR:device_offline ($AdbAddr)"; exit 1 }

        Warn-MaaInstance
        & $AdbExe -s $AdbAddr install -r $ApkPath 2>&1
        if ($LASTEXITCODE -eq 0) { Write-Output 'OK:installed' }
        else { Write-Output 'ERR:install_failed'; exit 1 }
    }

}
