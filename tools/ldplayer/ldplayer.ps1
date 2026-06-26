#requires -Version 5.1

<#
.SYNOPSIS
LDPlayer 9 模拟器管控：启停、状态、ADB、快照

.PARAMETER Action
动作：start | start-gui | stop | stop-force | restart | status | adb | snapshot | restore

.PARAMETER Name
快照名称（snapshot/restore 时必填）
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('start', 'start-gui', 'stop', 'stop-force', 'restart', 'status', 'adb', 'snapshot', 'restore')]
    [string]$Action,

    [string]$Name
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
    $output = & $VBoxManage list runningvms 2>$null
    return ($output -match [regex]::Escape($VmName))
}

function Wait-ForAdb {
    param([int]$Timeout = 30)
    $deadline = (Get-Date).AddSeconds($Timeout)
    while ((Get-Date) -lt $deadline) {
        $devices = & $AdbExe devices 2>$null
        if ($devices -match $AdbAddr) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

# ── actions ──────────────────────────────────────────────────────────

switch ($Action) {

    'start' {
        if (Test-VmRunning) {
            Write-Output 'OK:already_running'
            exit 0
        }
        & $VBoxManage startvm $VmName --type headless 2>&1 | Out-Null
        Start-Sleep -Seconds 5
        if (Test-VmRunning) {
            Write-Output 'OK:started'
            & $AdbExe connect $AdbAddr 2>&1 | Out-Null
            if (Wait-ForAdb) { Write-Output 'OK:adb_connected' }
        } else {
            Write-Output 'ERR:start_failed'
            exit 1
        }
    }

    'start-gui' {
        if (Test-VmRunning) {
            Write-Output 'OK:already_running'
            exit 0
        }
        & $VBoxManage startvm $VmName 2>&1 | Out-Null
        Start-Sleep -Seconds 5
        if (Test-VmRunning) {
            Write-Output 'OK:started_gui'
            & $AdbExe connect $AdbAddr 2>&1 | Out-Null
        } else {
            Write-Output 'ERR:start_failed'
            exit 1
        }
    }

    'stop' {
        if (-not (Test-VmRunning)) {
            Write-Output 'OK:already_stopped'
            exit 0
        }
        & $VBoxManage controlvm $VmName acpipowerbutton 2>&1 | Out-Null
        Start-Sleep -Seconds 8
        if (Test-VmRunning) {
            Write-Output 'WARN:still_running_use_stop_force'
            exit 1
        }
        Write-Output 'OK:stopped'
    }

    'stop-force' {
        if (-not (Test-VmRunning)) {
            Write-Output 'OK:already_stopped'
            exit 0
        }
        & $VBoxManage controlvm $VmName poweroff 2>&1 | Out-Null
        Start-Sleep -Seconds 3
        if (-not (Test-VmRunning)) {
            Write-Output 'OK:force_stopped'
        } else {
            Write-Output 'ERR:force_stop_failed'
            exit 1
        }
    }

    'restart' {
        if (Test-VmRunning) {
            & $VBoxManage controlvm $VmName acpipowerbutton 2>&1 | Out-Null
            Start-Sleep -Seconds 8
            if (Test-VmRunning) {
                & $VBoxManage controlvm $VmName poweroff 2>&1 | Out-Null
                Start-Sleep -Seconds 3
            }
        }
        & $VBoxManage startvm $VmName --type headless 2>&1 | Out-Null
        Start-Sleep -Seconds 5
        if (Test-VmRunning) {
            Write-Output 'OK:restarted'
            & $AdbExe connect $AdbAddr 2>&1 | Out-Null
        } else {
            Write-Output 'ERR:restart_failed'
            exit 1
        }
    }

    'status' {
        if (Test-VmRunning) {
            Write-Output 'RUNNING'
            $devices = & $AdbExe devices 2>$null
            if ($devices -match $AdbAddr) {
                Write-Output "ADB:$AdbAddr"
            } else {
                Write-Output 'ADB:disconnected'
            }
        } else {
            Write-Output 'STOPPED'
        }
    }

    'adb' {
        & $AdbExe connect $AdbAddr 2>&1
        & $AdbExe devices 2>&1
    }

    'snapshot' {
        if (-not $Name) { Write-Output 'ERR:snapshot_requires_-Name'; exit 1 }
        if (Test-VmRunning) { Write-Output 'WARN:vm_running_snapshot_may_be_inconsistent' }
        & $VBoxManage snapshot $VmName take $Name 2>&1
        if ($LASTEXITCODE -eq 0) { Write-Output "OK:snapshot:$Name" }
        else { Write-Output 'ERR:snapshot_failed'; exit 1 }
    }

    'restore' {
        if (-not $Name) { Write-Output 'ERR:restore_requires_-Name'; exit 1 }
        if (Test-VmRunning) {
            & $VBoxManage controlvm $VmName poweroff 2>&1 | Out-Null
            Start-Sleep -Seconds 3
        }
        & $VBoxManage snapshot $VmName restore $Name 2>&1
        if ($LASTEXITCODE -eq 0) { Write-Output "OK:restored:$Name" }
        else { Write-Output 'ERR:restore_failed'; exit 1 }
    }

}
