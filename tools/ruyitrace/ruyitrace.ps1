#requires -Version 5.1

<#
.SYNOPSIS
ruyiTrace CLI — 启动定制 Firefox 并记录 DOM/JS API 调用

使用 MOZ_DOM_TRACE 环境变量驱动 Firefox 内核级别的 API 追踪，
输出 NDJSON 格式的调用日志。不依赖 Electron GUI。

.PARAMETER Url
要访问的目标 URL（必填）

.PARAMETER Output
NDJSON 输出文件路径（默认: trace_out.ndjson）

.PARAMETER Profile
Firefox 用户配置文件目录（可选，默认自动创建临时目录）

.PARAMETER Headless
无头模式（可选）
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Url,

    [string]$Output = "$PWD\trace_out.ndjson",

    [string]$Profile,

    [switch]$Headless
)

$FirefoxDir = 'D:\reverse_ENV\tools\ruyitrace\firefox'
$FirefoxExe = Join-Path $FirefoxDir 'firefox.exe'

if (-not (Test-Path $FirefoxExe)) {
    Write-Output "ERR: firefox.exe not found at $FirefoxExe"
    exit 1
}

# Verify marker file
$MarkerFile = Join-Path $FirefoxDir 'RUYI_DOMTRACE.txt'
if (-not (Test-Path $MarkerFile)) {
    Write-Output "ERR: RUYI_DOMTRACE.txt marker missing — trace kernel may be corrupted"
    exit 1
}

# Setup profile directory
if (-not $Profile) {
    $Profile = Join-Path $env:TEMP "ruyitrace_profile_$(Get-Random)"
    New-Item -ItemType Directory -Path $Profile -Force | Out-Null
    Write-Output "INFO: temp profile: $Profile"
}

# Set environment variables for trace kernel
$env:MOZ_DOM_TRACE = "1"
$env:MOZ_DOM_TRACE_FILE = $Output

Write-Output "========================================="
Write-Output "ruyiTrace v1.2 (Firefox 151 trace kernel)"
Write-Output "========================================="
Write-Output "Target:  $Url"
Write-Output "Output:  $Output"
Write-Output "Profile: $Profile"
if ($Headless) { Write-Output "Mode:    headless" }
Write-Output "========================================="
Write-Output "Starting Firefox..."
Write-Output "Close Firefox window when done to stop tracing."
Write-Output ""

$args = @('-profile', $Profile, '-no-remote', '-new-instance')
if ($Headless) { $args += '--headless' }
$args += $Url

& $FirefoxExe @args

Write-Output ""
if (Test-Path $Output) {
    $size = (Get-Item $Output).Length
    $lines = (Get-Content $Output | Measure-Object -Line).Lines
    Write-Output "OK: trace saved — $lines lines, $size bytes → $Output"
    Write-Output "Analyze: python tools\ruyitrace\trace_analyzer.py $Output"
} else {
    Write-Output "WARN: no trace output file created"
}
