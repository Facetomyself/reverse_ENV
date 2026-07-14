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

.PARAMETER Limit
每个 Firefox 进程最多记录的 NDJSON 行数（0 表示使用内核默认值）

.PARAMETER KeepProcessFiles
保留内核生成的 `<output>_<PID>.ndjson` 分片；默认合并后删除
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Url,

    [string]$Output = "$PWD\trace_out.ndjson",

    [string]$Profile,

    [switch]$Headless,

    [ValidateRange(0, 2147483647)]
    [int]$Limit = 0,

    [switch]$KeepProcessFiles
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

$Output = [IO.Path]::GetFullPath($Output)
$OutputDir = Split-Path -Parent $Output
if (-not (Test-Path -LiteralPath $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$OutputStem = [IO.Path]::GetFileNameWithoutExtension($Output)
$OutputExt = [IO.Path]::GetExtension($Output)
$FragmentPattern = "${OutputStem}_*${OutputExt}"

function Get-TraceCandidates {
    $items = @()
    if (Test-Path -LiteralPath $Output) {
        $items += Get-Item -LiteralPath $Output
    }
    $items += @(Get-ChildItem -LiteralPath $OutputDir -Filter $FragmentPattern -File -ErrorAction SilentlyContinue)
    return @($items | Sort-Object FullName -Unique)
}

$BeforeState = @{}
foreach ($item in @(Get-TraceCandidates)) {
    $BeforeState[$item.FullName] = "{0}:{1}" -f $item.LastWriteTimeUtc.Ticks, $item.Length
}

# Setup profile directory
$AutoProfile = -not $Profile
if (-not $Profile) {
    $Profile = Join-Path $env:TEMP "ruyitrace_profile_$(Get-Random)"
    New-Item -ItemType Directory -Path $Profile -Force | Out-Null
    Write-Output "INFO: temp profile: $Profile"
}

# Set environment variables for trace kernel. The custom Firefox appends the
# process ID to MOZ_DOM_TRACE_FILE, so one session may create multiple files.
$TraceEnvNames = @(
    'MOZ_DOM_TRACE',
    'MOZ_DOM_TRACE_FILE',
    'MOZ_DOM_TRACE_LIMIT',
    'MOZ_DISABLE_LAUNCHER_PROCESS'
)
$PreviousTraceEnv = @{}
foreach ($name in $TraceEnvNames) {
    $PreviousTraceEnv[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$env:MOZ_DOM_TRACE = '1'
$env:MOZ_DOM_TRACE_FILE = $Output
$env:MOZ_DISABLE_LAUNCHER_PROCESS = '1'
if ($Limit -gt 0) {
    $env:MOZ_DOM_TRACE_LIMIT = [string]$Limit
} else {
    Remove-Item Env:MOZ_DOM_TRACE_LIMIT -ErrorAction SilentlyContinue
}

Write-Output "========================================="
Write-Output "ruyiTrace v1.2 (Firefox 151 trace kernel)"
Write-Output "========================================="
Write-Output "Target:  $Url"
Write-Output "Output:  $Output"
Write-Output "Profile: $Profile"
if ($Headless) { Write-Output "Mode:    headless" }
if ($Limit -gt 0) { Write-Output "Limit:   $Limit lines/process" }
Write-Output "========================================="
Write-Output "Starting Firefox..."
Write-Output "Close Firefox window when done to stop tracing."
Write-Output ""

$args = @('-profile', $Profile, '-no-remote', '-new-instance')
if ($Headless) { $args += '--headless' }
$args += $Url

try {
    & $FirefoxExe @args
} finally {
    foreach ($name in $TraceEnvNames) {
        [Environment]::SetEnvironmentVariable($name, $PreviousTraceEnv[$name], 'Process')
    }
}

Write-Output ""
$GeneratedFiles = @()
$StableSignature = $null
$StablePasses = 0
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 250
    $ChangedFiles = @()
    foreach ($item in @(Get-TraceCandidates)) {
        $currentState = "{0}:{1}" -f $item.LastWriteTimeUtc.Ticks, $item.Length
        if (-not $BeforeState.ContainsKey($item.FullName) -or $BeforeState[$item.FullName] -ne $currentState) {
            $ChangedFiles += $item
        }
    }

    $Signature = @($ChangedFiles | ForEach-Object {
        "{0}:{1}:{2}" -f $_.FullName, $_.LastWriteTimeUtc.Ticks, $_.Length
    }) -join '|'
    if ($ChangedFiles.Count -gt 0 -and $Signature -eq $StableSignature) {
        $StablePasses++
    } else {
        $StablePasses = 0
    }
    $StableSignature = $Signature
    $GeneratedFiles = @($ChangedFiles | Where-Object { $_.Length -gt 0 })
    if ($StablePasses -ge 8) {
        break
    }
}

if ($GeneratedFiles.Count -gt 0) {
    $MergePath = "$Output.merge.$PID.tmp"
    $Destination = [IO.File]::Open($MergePath, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        foreach ($file in @($GeneratedFiles | Sort-Object FullName)) {
            $Source = [IO.File]::Open($file.FullName, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
            try {
                $LastByte = -1
                if ($Source.Length -gt 0) {
                    $Source.Position = $Source.Length - 1
                    $LastByte = $Source.ReadByte()
                    $Source.Position = 0
                    $Source.CopyTo($Destination)
                }
                if ($LastByte -ne 10) {
                    $Destination.WriteByte(10)
                }
            } finally {
                $Source.Dispose()
            }
        }
    } finally {
        $Destination.Dispose()
    }

    Move-Item -LiteralPath $MergePath -Destination $Output -Force

    if (-not $KeepProcessFiles) {
        foreach ($file in $GeneratedFiles) {
            if ($file.FullName -ne $Output) {
                Remove-Item -LiteralPath $file.FullName -Force -ErrorAction SilentlyContinue
            }
        }
    }

    $size = (Get-Item -LiteralPath $Output).Length
    $lines = (Get-Content -LiteralPath $Output -Encoding UTF8 | Measure-Object -Line).Lines
    Write-Output "OK: trace saved — $lines lines, $size bytes from $($GeneratedFiles.Count) process file(s) → $Output"
    Write-Output "Analyze: python tools\ruyitrace\trace_analyzer.py `"$Output`""
} else {
    Write-Output "WARN: no trace output file created"
}

if ($AutoProfile -and (Test-Path -LiteralPath $Profile)) {
    Remove-Item -LiteralPath $Profile -Recurse -Force -ErrorAction SilentlyContinue
}
