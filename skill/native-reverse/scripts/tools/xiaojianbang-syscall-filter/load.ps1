param(
    [Parameter(Position = 0)]
    [string]$Action,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"

$Adb = if ($env:XJB_ADB) { $env:XJB_ADB } elseif ($env:ADB) { $env:ADB } else { "adb" }
$Kp = "/data/local/tmp/kpatch"
$SuperKey = if ($env:XJB_KP_SUPERKEY) { $env:XJB_KP_SUPERKEY } else { "xiaojianbang8888" }
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

function Show-Usage {
    Write-Host "用法: .\load.ps1 {load|unload|status|list|info|push|reload|ctl <cmd>}"
    Write-Host "环境变量: XJB_ADB=C:\path\adb.exe, XJB_KP_SUPERKEY=<superkey>"
}

switch ($Action) {
    "load" {
        Invoke-Dev "$Kp $SuperKey kpm load $KpmDev"
    }
    "unload" {
        Invoke-Dev "$Kp $SuperKey kpm unload $Name"
    }
    "status" {
        Invoke-Dev "$Kp $SuperKey kpm ctl0 $Name status >/dev/null"
        Invoke-Dev "dmesg | grep -E '\[scfilter\] status(_cat|_uid)?:' | tail -4"
        Write-Host ""
    }
    "list" {
        Invoke-Dev "$Kp $SuperKey kpm list"
        Write-Host ""
    }
    "info" {
        Invoke-Dev "$Kp $SuperKey kpm info $Name"
    }
    "ctl" {
        $CtlCommand = ($Rest -join " ")
        if (-not $CtlCommand) {
            Write-Error "ctl 需要一个无空格控制命令，例如: .\load.ps1 ctl resolve=on"
            exit 1
        }
        Invoke-Dev "$Kp $SuperKey kpm ctl0 $Name '$CtlCommand' >/dev/null"
        Invoke-Dev "dmesg | grep -E '\[scfilter\] status(_cat|_uid)?:' | tail -4"
        Write-Host ""
    }
    "push" {
        Invoke-Adb push $KpmLocal $KpmDev
        Write-Host "pushed"
    }
    "reload" {
        Invoke-Adb push $KpmLocal $KpmDev
        Invoke-Dev "$Kp $SuperKey kpm unload $Name 2>/dev/null; $Kp $SuperKey kpm load $KpmDev"
    }
    default {
        Show-Usage
        exit 1
    }
}
