<#
.SYNOPSIS
  LDPlayer RE 模拟器环境初始化脚本
  一键配置: Frida server + 可选 Magisk 引导

.PARAMETER Instance
  已废弃。不要用实例名猜测 ADB serial；请使用 -DeviceSerial。
.PARAMETER DeviceSerial
  ADB serial，例如 127.0.0.1:7555。未指定时只允许当前恰好一个 device。
.PARAMETER FridaServerPath
  frida-server 本地路径 (默认从 tools 自动匹配)

.EXAMPLE
  # 初始化默认 RE 实例
  init-ldplayer-re.ps1

  # 指定实例
  init-ldplayer-re.ps1 -DeviceSerial "127.0.0.1:7555"
#>

param(
    [string]$Instance = "",
    [string]$DeviceSerial = "",
    [string]$FridaServerPath = ""
)

$ErrorActionPreference = "Stop"
$ADB = "D:\reverse_ENV\tools\adb\adb.exe"

function Get-AdbDevices {
    $lines = & $ADB devices 2>&1
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
        throw "No ADB device found. Start LDPlayer first."
    }

    if (-not [string]::IsNullOrWhiteSpace($RequestedInstance) -and [string]::IsNullOrWhiteSpace($RequestedSerial)) {
        if ($devices -contains $RequestedInstance) {
            Write-Warning "-Instance matched an ADB serial. Prefer -DeviceSerial for clarity."
            return $RequestedInstance
        }
        throw "-Instance '$RequestedInstance' is not an ADB serial and this script does not map LDPlayer names to serials. Pass -DeviceSerial explicitly. Connected serials: $($devices -join ', ')"
    }

    if (-not [string]::IsNullOrWhiteSpace($RequestedSerial)) {
        if ($devices -notcontains $RequestedSerial) {
            throw "ADB device '$RequestedSerial' is not connected. Connected serials: $($devices -join ', ')"
        }
        return $RequestedSerial
    }

    if ($devices.Count -ne 1) {
        throw "Multiple ADB devices connected; pass -DeviceSerial explicitly. Connected serials: $($devices -join ', ')"
    }

    return $devices[0]
}

function Invoke-Adb {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$AdbArgs)

    & $ADB -s $DeviceSerial @AdbArgs
}

# ------------------------------------------------------------------
# 1. 确认模拟器连接
# ------------------------------------------------------------------
Write-Host "=== Step 1: Check ADB connection ==="
$DeviceSerial = Resolve-AdbSerial -RequestedSerial $DeviceSerial -RequestedInstance $Instance
Write-Host "[OK] Device connected: $DeviceSerial"

# ------------------------------------------------------------------
# 2. 确认 root 权限
# ------------------------------------------------------------------
Write-Host "`n=== Step 2: Verify root ==="
$rootCheck = Invoke-Adb shell "su -c 'echo ROOT_OK'" 2>&1
if ($rootCheck -match "ROOT_OK") {
    Write-Host "[OK] Root access confirmed"
} else {
    Write-Error "Root not available. Enable root in LDPlayer settings."
    exit 1
}

# ------------------------------------------------------------------
# 3. 确认系统可写
# ------------------------------------------------------------------
Write-Host "`n=== Step 3: Verify writable system ==="
$rwCheck = Invoke-Adb shell "su -c 'mount | grep /system'" 2>&1 | Select-String "rw,"
if ($rwCheck) {
    Write-Host "[OK] System partition is writable"
} else {
    Write-Warning "System might not be writable. Magisk direct install may fail."
}

# ------------------------------------------------------------------
# 4. 推送并启动 Frida server
# ------------------------------------------------------------------
Write-Host "`n=== Step 4: Frida server ==="

# Remount system rw (needed for some tools)
Write-Host "Remounting system as rw..."
Invoke-Adb shell "su -c 'mount -o rw,remount /'" 2>&1 | Out-Null

# Stop existing frida-server
Invoke-Adb shell "su -c 'killall frida-server'" 2>&1 | Out-Null
Start-Sleep -Seconds 1

# Push frida-server if not already on device
$fridaExists = Invoke-Adb shell "test -f /data/local/tmp/frida-server && echo EXISTS" 2>&1
if ($fridaExists -notmatch "EXISTS") {
    if (-not $FridaServerPath) {
        $FridaServerPath = "D:\reverse_ENV\temp\ldplayer-setup\frida-server"
    }
    if (-not (Test-Path $FridaServerPath)) {
        # Try to find matching version from GitHub
        $fridaVer = & D:\reverse_ENV\.venv\Scripts\frida.exe --version 2>&1
        Write-Error "Frida server not found at $FridaServerPath. Download frida-server-$fridaVer-android-x86_64.xz from GitHub releases."
        exit 1
    }
    Write-Host "Pushing frida-server..."
    Invoke-Adb push $FridaServerPath /data/local/tmp/frida-server 2>&1
    Invoke-Adb shell "su -c 'chmod 755 /data/local/tmp/frida-server'" 2>&1
}

# Start frida-server in background
Write-Host "Starting frida-server..."
Invoke-Adb shell "su -c 'nohup /data/local/tmp/frida-server -D &'" 2>&1
Start-Sleep -Seconds 2

# Verify
$fridaProc = Invoke-Adb shell "su -c 'ps -A | grep frida-server'" 2>&1
if ($fridaProc -match "frida-server") {
    Write-Host "[OK] Frida server running"
} else {
    Write-Error "Frida server failed to start"
    exit 1
}

# ------------------------------------------------------------------
# 5. 报告状态
# ------------------------------------------------------------------
Write-Host "`n=== Environment Ready ==="
Write-Host "  Frida:  running"
Write-Host "  Root:   available (su)"
Write-Host "  System: writable (rw)"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  - DEX dump:  frida -U -f <pkg> -l D:\reverse_ENV\skill\apk-reverse\scripts\dex-dump.js"
Write-Host "  - Magisk:    Launch Magisk app on emulator -> Install -> Direct Install"
Write-Host "  - SSL bypass: D:\reverse_ENV\tools\adb\adb.exe -s $DeviceSerial shell su -c ' ... '"
