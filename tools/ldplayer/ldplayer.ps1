#requires -Version 5.1

<#
.SYNOPSIS
LDPlayer 9 模拟器管控：状态、ADB连接、关机、重启

LDPlayer 9 由 Windows 服务 ldplayerservice 管理 VM 生命周期。
服务持有 VBox 会话锁时 VBoxManage 无法启停 VM。
- 启动：通过 LDPlayer GUI（本脚本无法绕过服务锁）
- 关机：优先 ADB reboot -p（Android 内优雅关机），兜底 VBoxManage poweroff
- 重启：ADB reboot

.PARAMETER Action
status | adb | stop | restart
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('status', 'adb', 'stop', 'restart')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding           = [System.Text.UTF8Encoding]::new($false)

$VBoxManage  = 'C:\Program Files\ldplayer9box\VBoxManage.exe'
$VmName      = 'leidian0'
$AdbExe      = 'D:\reverse_ENV\tools\adb\adb.exe'
$AdbAddr     = '127.0.0.1:5555'

# ── helpers ──────────────────────────────────────────────────────────

function Test-VmRunning {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $output = & $VBoxManage list runningvms 2>$null
    $ErrorActionPreference = $prev
    return ($output -match [regex]::Escape($VmName))
}

function Test-AdbOnline {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $devices = & $AdbExe devices 2>$null
    $ErrorActionPreference = $prev
    return ($devices -match "$AdbAddr\s+device")
}

function Invoke-VBoxSilent {
    param([string[]]$Args)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $result = & $VBoxManage @Args 2>&1
    $ErrorActionPreference = $prev
    return $result
}

# ── actions ──────────────────────────────────────────────────────────

switch ($Action) {

    'status' {
        if (Test-VmRunning) {
            Write-Output 'RUNNING'
            if (Test-AdbOnline) { Write-Output "ADB:$AdbAddr" }
            else { Write-Output 'ADB:offline' }
        } else {
            Write-Output 'STOPPED'
        }
    }

    'adb' {
        & $AdbExe connect $AdbAddr 2>&1
        Write-Output '---'
        & $AdbExe devices 2>&1
    }

    'stop' {
        if (-not (Test-VmRunning)) {
            Write-Output 'OK:already_stopped'
            exit 0
        }
        # Try ADB graceful shutdown first
        if (Test-AdbOnline) {
            Write-Output 'INFO:adb_reboot_shutdown'
            & $AdbExe -s $AdbAddr shell reboot -p 2>$null | Out-Null
            Start-Sleep -Seconds 8
            if (-not (Test-VmRunning)) {
                Write-Output 'OK:stopped_via_adb'
                exit 0
            }
            Write-Output 'WARN:adb_shutdown_no_effect'
        }
        # Fallback: VBoxManage poweroff
        Write-Output 'INFO:trying_poweroff'
        Invoke-VBoxSilent controlvm, $VmName, 'poweroff' | Out-Null
        Start-Sleep -Seconds 3
        if (-not (Test-VmRunning)) {
            Write-Output 'OK:poweroff'
        } else {
            Write-Output 'ERR:stop_failed'
            Write-Output 'HINT: LDPlayer service may be holding a lock'
            exit 1
        }
    }

    'restart' {
        if (-not (Test-VmRunning)) {
            Write-Output 'ERR:vm_not_running'
            Write-Output 'HINT: Start LDPlayer via GUI first'
            exit 1
        }
        if (-not (Test-AdbOnline)) {
            Write-Output 'ERR:adb_offline'
            exit 1
        }
        Write-Output 'INFO:adb_reboot'
        & $AdbExe -s $AdbAddr shell reboot 2>$null | Out-Null
        Start-Sleep -Seconds 12
        & $AdbExe connect $AdbAddr 2>$null | Out-Null
        if (Test-AdbOnline) {
            Write-Output 'OK:restarted_adb_reconnected'
        } else {
            Write-Output 'WARN:restarted_adb_not_yet'
        }
    }

}
