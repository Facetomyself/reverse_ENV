param(
    [Alias("KpSuperKey")]
    [string]$SuperKey,

    [Parameter(Position = 0)]
    [string]$Action,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"

$Adb = if ($env:XJB_ADB) { $env:XJB_ADB } elseif ($env:ADB) { $env:ADB } else { "adb" }
$Kp = "/data/local/tmp/kpatch"
if (-not $SuperKey) {
    $SuperKey = if ($env:KP_SUPERKEY) { $env:KP_SUPERKEY } elseif ($env:XJB_KP_SUPERKEY) { $env:XJB_KP_SUPERKEY } else { "" }
}
$KpmLocal = Join-Path $PSScriptRoot "syscallhook.kpm"
$KpmDev = "/data/local/tmp/scfilter.kpm"
$Name = "xiaojianbang-syscall-filter"

function Invoke-Adb {
    & $Adb @args
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Invoke-Dev {
    param([Parameter(Mandatory = $true)][string]$Command)
    & $Adb shell su -c $Command
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Quote-DeviceShell {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + ($Value -replace "'", "'\\''") + "'"
}

function Assert-SuperKey {
    if (-not $SuperKey) {
        Write-Error "KernelPatch superkey 不能为空；请传 -SuperKey <key> 或设置 KP_SUPERKEY / XJB_KP_SUPERKEY"
        exit 1
    }
}

function Show-Usage {
    Write-Host "用法: .\load.ps1 [-SuperKey <key>] {load|unload|status|list|info|push|reload|ctl <cmd>}"
    Write-Host "环境变量: XJB_ADB=C:\path\adb.exe, KP_SUPERKEY=<superkey>, XJB_KP_SUPERKEY=<superkey>"
}

switch ($Action) {
    "load" {
        Assert-SuperKey
        Invoke-Dev "$(Quote-DeviceShell $Kp) $(Quote-DeviceShell $SuperKey) kpm load $(Quote-DeviceShell $KpmDev)"
    }
    "unload" {
        Assert-SuperKey
        Invoke-Dev "$(Quote-DeviceShell $Kp) $(Quote-DeviceShell $SuperKey) kpm unload $(Quote-DeviceShell $Name)"
    }
    "status" {
        Assert-SuperKey
        Invoke-Dev "$(Quote-DeviceShell $Kp) $(Quote-DeviceShell $SuperKey) kpm ctl0 $(Quote-DeviceShell $Name) status >/dev/null"
        Invoke-Dev "dmesg | grep -E '\[scfilter\] status(_cat|_uid)?:' | tail -4"
        Write-Host ""
    }
    "list" {
        Assert-SuperKey
        Invoke-Dev "$(Quote-DeviceShell $Kp) $(Quote-DeviceShell $SuperKey) kpm list"
        Write-Host ""
    }
    "info" {
        Assert-SuperKey
        Invoke-Dev "$(Quote-DeviceShell $Kp) $(Quote-DeviceShell $SuperKey) kpm info $(Quote-DeviceShell $Name)"
    }
    "ctl" {
        Assert-SuperKey
        $CtlCommand = ($Rest -join " ")
        if (-not $CtlCommand) {
            Write-Error "ctl 需要一个无空格控制命令，例如: .\load.ps1 ctl resolve=on"
            exit 1
        }
        Invoke-Dev "$(Quote-DeviceShell $Kp) $(Quote-DeviceShell $SuperKey) kpm ctl0 $(Quote-DeviceShell $Name) $(Quote-DeviceShell $CtlCommand) >/dev/null"
        Invoke-Dev "dmesg | grep -E '\[scfilter\] status(_cat|_uid)?:' | tail -4"
        Write-Host ""
    }
    "push" {
        Invoke-Adb push $KpmLocal $KpmDev
        Write-Host "pushed"
    }
    "reload" {
        Invoke-Adb push $KpmLocal $KpmDev
        Assert-SuperKey
        Invoke-Dev "$(Quote-DeviceShell $Kp) $(Quote-DeviceShell $SuperKey) kpm unload $(Quote-DeviceShell $Name) 2>/dev/null; $(Quote-DeviceShell $Kp) $(Quote-DeviceShell $SuperKey) kpm load $(Quote-DeviceShell $KpmDev)"
    }
    default {
        Show-Usage
        exit 1
    }
}
