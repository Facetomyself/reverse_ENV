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

.PARAMETER DurationSeconds
非交互 headless 采集时长。到时通过 WebDriver BiDi `browser.close`
优雅退出并等待 trace flush；0 表示保持原交互模式。

.PARAMETER ProcessTypes
传给 `MOZ_DOM_TRACE_PTYPE` 的进程类型列表。默认 `parent,tab`。

.PARAMETER RemoteDebuggingPort
定时采集使用的 Remote Agent 端口；`0` 表示自动选择 loopback 空闲端口。
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

    [switch]$KeepProcessFiles,

    [ValidateRange(0, 86400)]
    [int]$DurationSeconds = 0,

    [string]$ProcessTypes = 'parent,tab',

    [ValidateRange(0, 65535)]
    [int]$RemoteDebuggingPort = 0
)

$FirefoxDir = 'D:\reverse_ENV\tools\ruyitrace\firefox'
$FirefoxExe = Join-Path $FirefoxDir 'firefox.exe'
$PythonExe = 'D:\reverse_ENV\.venv\Scripts\python.exe'
$BidiCloseScript = 'D:\reverse_ENV\tools\ruyitrace\bidi_close.py'

if ($DurationSeconds -gt 0 -and -not $Headless) {
    throw '-DurationSeconds requires -Headless because timed capture is non-interactive.'
}
if ($RemoteDebuggingPort -gt 0 -and $DurationSeconds -eq 0) {
    throw '-RemoteDebuggingPort is only valid with -DurationSeconds.'
}

if (-not (Test-Path $FirefoxExe)) {
    Write-Output "ERR: firefox.exe not found at $FirefoxExe"
    exit 1
}
if ($DurationSeconds -gt 0 -and -not (Test-Path -LiteralPath $PythonExe)) {
    Write-Output "ERR: project Python not found at $PythonExe"
    exit 1
}
if ($DurationSeconds -gt 0 -and -not (Test-Path -LiteralPath $BidiCloseScript)) {
    Write-Output "ERR: BiDi close helper not found at $BidiCloseScript"
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

function Get-FreeLoopbackPort {
    $Listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    try {
        $Listener.Start()
        return ([Net.IPEndPoint]$Listener.LocalEndpoint).Port
    } finally {
        $Listener.Stop()
    }
}

function ConvertTo-NativeArgument {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ($Value.Contains('"')) {
        throw "Native argument contains an unsupported quote: $Value"
    }
    return '"' + $Value + '"'
}

function Get-SessionFirefoxProcesses {
    param(
        [Parameter(Mandatory = $true)][int]$RootPid,
        [Parameter(Mandatory = $true)][string]$ProfilePath
    )

    $AllFirefox = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.ExecutablePath -and $_.ExecutablePath.Equals($FirefoxExe, [StringComparison]::OrdinalIgnoreCase)
    })
    $Ids = New-Object 'System.Collections.Generic.HashSet[int]'
    [void]$Ids.Add($RootPid)
    foreach ($Process in $AllFirefox) {
        if ($Process.CommandLine -and $Process.CommandLine.IndexOf($ProfilePath, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            [void]$Ids.Add([int]$Process.ProcessId)
        }
    }
    do {
        $Added = $false
        foreach ($Process in $AllFirefox) {
            if ($Ids.Contains([int]$Process.ParentProcessId) -and -not $Ids.Contains([int]$Process.ProcessId)) {
                [void]$Ids.Add([int]$Process.ProcessId)
                $Added = $true
            }
        }
    } while ($Added)
    return @($AllFirefox | Where-Object { $Ids.Contains([int]$_.ProcessId) })
}

function Wait-SessionFirefoxExit {
    param(
        [Parameter(Mandatory = $true)][int]$RootPid,
        [Parameter(Mandatory = $true)][string]$ProfilePath,
        [int]$TimeoutMilliseconds = 15000
    )

    $Deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMilliseconds)
    do {
        $Remaining = @(Get-SessionFirefoxProcesses -RootPid $RootPid -ProfilePath $ProfilePath)
        if ($Remaining.Count -eq 0) {
            return $true
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $Deadline)
    return $false
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
if ($DurationSeconds -gt 0 -and $AutoProfile) {
    $UserJsPath = Join-Path $Profile 'user.js'
    [IO.File]::WriteAllText(
        $UserJsPath,
        "user_pref(`"remote.prefs.recommended`", true);`n",
        [Text.UTF8Encoding]::new($false)
    )
}

# Set environment variables for trace kernel. The custom Firefox appends the
# process ID to MOZ_DOM_TRACE_FILE, so one session may create multiple files.
$TraceEnvNames = @(
    'MOZ_DOM_TRACE',
    'MOZ_DOM_TRACE_FILE',
    'MOZ_DOM_TRACE_LIMIT',
    'MOZ_DOM_TRACE_PTYPE',
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
if ($ProcessTypes) {
    $env:MOZ_DOM_TRACE_PTYPE = $ProcessTypes
} else {
    Remove-Item Env:MOZ_DOM_TRACE_PTYPE -ErrorAction SilentlyContinue
}

Write-Output "========================================="
Write-Output "ruyiTrace v1.2 (Firefox 151 trace kernel)"
Write-Output "========================================="
Write-Output "Target:  $Url"
Write-Output "Output:  $Output"
Write-Output "Profile: $Profile"
if ($Headless) { Write-Output "Mode:    headless" }
if ($Limit -gt 0) { Write-Output "Limit:   $Limit lines/process" }
if ($DurationSeconds -gt 0) { Write-Output "Duration: $DurationSeconds seconds" }
if ($ProcessTypes) { Write-Output "Process types: $ProcessTypes" }
$CapturePort = 0
if ($DurationSeconds -gt 0) {
    $CapturePort = if ($RemoteDebuggingPort -gt 0) { $RemoteDebuggingPort } else { Get-FreeLoopbackPort }
    Write-Output "Remote Agent: 127.0.0.1:$CapturePort"
}
Write-Output "========================================="
Write-Output "Starting Firefox..."
if ($DurationSeconds -gt 0) {
    Write-Output "Timed mode will reload after Trace initialization and close through WebDriver BiDi."
} else {
    Write-Output "Close Firefox window when done to stop tracing."
}
Write-Output ""

$FirefoxArgs = @('-profile', $Profile, '-no-remote')
if ($DurationSeconds -eq 0) {
    $FirefoxArgs += '-new-instance'
}
if ($DurationSeconds -gt 0) {
    $FirefoxArgs = @("--remote-debugging-port=$CapturePort") + $FirefoxArgs
}
if ($Headless) { $FirefoxArgs += '--headless' }
$FirefoxArgs += $Url
$CaptureExitCode = 0

try {
    if ($DurationSeconds -gt 0) {
        $ArgumentLine = @($FirefoxArgs | ForEach-Object { ConvertTo-NativeArgument ([string]$_) }) -join ' '
        $TraceProcess = Start-Process -FilePath $FirefoxExe -ArgumentList $ArgumentLine -PassThru -WindowStyle Hidden
        $CloseOutput = & $PythonExe $BidiCloseScript --host '127.0.0.1' --port $CapturePort --timeout 30 --reload --duration $DurationSeconds
        $CloseExitCode = $LASTEXITCODE
        foreach ($Line in @($CloseOutput)) {
            Write-Output "INFO: BiDi lifecycle: $Line"
        }
        if ($CloseExitCode -ne 0) {
            Write-Output "WARN: BiDi navigate/browser.close failed with exit code $CloseExitCode"
            $CaptureExitCode = 2
        }
        if (-not (Wait-SessionFirefoxExit -RootPid $TraceProcess.Id -ProfilePath $Profile -TimeoutMilliseconds 15000)) {
            $Remaining = @(Get-SessionFirefoxProcesses -RootPid $TraceProcess.Id -ProfilePath $Profile)
            $RemainingIds = @($Remaining | Select-Object -ExpandProperty ProcessId)
            Write-Output "WARN: graceful close timed out; stopping only launched Firefox PIDs $($RemainingIds -join ',')"
            foreach ($ProcessId in $RemainingIds) {
                Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
            }
            $CaptureExitCode = 2
        }
    } else {
        & $FirefoxExe @FirefoxArgs
    }
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
    $CaptureExitCode = 1
}

if ($AutoProfile -and (Test-Path -LiteralPath $Profile)) {
    $ResolvedTemp = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    $ResolvedProfile = [IO.Path]::GetFullPath($Profile)
    if ($ResolvedProfile.StartsWith($ResolvedTemp, [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $ResolvedProfile -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        Write-Output "WARN: refusing to remove auto profile outside TEMP: $ResolvedProfile"
    }
}

if ($CaptureExitCode -ne 0) {
    exit $CaptureExitCode
}
