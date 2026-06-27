#requires -Version 5.1

<#
.SYNOPSIS
LDPlayer 9 模拟器管控：状态、ADB、关机、重启

LDPlayer 9 的 ADB 地址为固定 emulator-5554（index 0）。
使用雷电自带 ADB（D:\leidian\LDPlayer9\adb.exe），与 MAA 兼容共存。

.PARAMETER Action
status | adb | stop | reboot | install
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('status', 'adb', 'stop', 'reboot', 'install')]
    [string]$Action,

    [string]$ApkPath
)

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding           = [System.Text.UTF8Encoding]::new($false)

# LDPlayer 9 uses emulator-5554 for index 0 (same convention as MAA)
$AdbExe     = 'D:\leidian\LDPlayer9\adb.exe'
$AdbAddr    = 'emulator-5554'

# ── helpers ──────────────────────────────────────────────────────────

function Test-AdbOnline {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $devices = & $AdbExe devices 2>$null
    $ErrorActionPreference = $prev
    return ($devices -match "$AdbAddr\s+device")
}

# ── actions ──────────────────────────────────────────────────────────

switch ($Action) {

    'status' {
        if (Test-AdbOnline) {
            Write-Output "RUNNING ($AdbAddr)"
            $info = & $AdbExe -s $AdbAddr shell getprop ro.product.model 2>$null
            if ($info) { Write-Output "Model: $info" }
        } else {
            Write-Output 'STOPPED'
        }
    }

    'adb' {
        & $AdbExe devices -l 2>&1
    }

    'stop' {
        if (-not (Test-AdbOnline)) {
            Write-Output 'OK:already_stopped'
            exit 0
        }
        Write-Output 'Shutting down via ADB...'
        & $AdbExe -s $AdbAddr shell reboot -p 2>$null | Out-Null
        Start-Sleep -Seconds 8
        if (-not (Test-AdbOnline)) {
            Write-Output 'OK:stopped'
        } else {
            Write-Output 'WARN: still online (may need force via GUI)'
        }
    }

    'reboot' {
        if (-not (Test-AdbOnline)) {
            Write-Output 'ERR:device_offline'
            exit 1
        }
        Write-Output 'Rebooting via ADB...'
        & $AdbExe -s $AdbAddr reboot 2>$null | Out-Null
        Start-Sleep -Seconds 15
        if (Test-AdbOnline) {
            Write-Output 'OK:back_online'
        } else {
            Write-Output 'WARN:still_booting'
        }
    }

    'install' {
        if (-not $ApkPath) {
            Write-Output 'ERR: -ApkPath required for install'
            exit 1
        }
        if (-not (Test-Path $ApkPath)) {
            Write-Output "ERR:file_not_found: $ApkPath"
            exit 1
        }
        if (-not (Test-AdbOnline)) {
            Write-Output 'ERR:device_offline'
            exit 1
        }
        & $AdbExe -s $AdbAddr install -r $ApkPath 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Output 'OK:installed'
        } else {
            Write-Output 'ERR:install_failed'
            exit 1
        }
    }

}
