#requires -Version 5.1

[CmdletBinding()]
param(
    [string]$Package,

    [string]$Process,

    [int]$ProcessId,

    [string]$DeviceId,

    [string]$RemoteHost = '127.0.0.1:27042',

    [string]$ScriptPath,

    [switch]$Usb,

    [switch]$Spawn,

    [switch]$Pause,

    [switch]$ListDevices,

    [switch]$ListProcesses,

    [switch]$ListApplications,

    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Get-ToolPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    $fallbacks = @{
        'frida-ls-devices' = 'D:\reverse_ENV\.venv\Scripts\frida-ls-devices.exe'
        'frida-ps' = 'D:\reverse_ENV\.venv\Scripts\frida-ps.exe'
        'frida' = 'D:\reverse_ENV\.venv\Scripts\frida.exe'
        'python' = 'D:\reverse_ENV\.venv\Scripts\python.exe'
    }

    if ($fallbacks.ContainsKey($Name) -and (Test-Path -LiteralPath $fallbacks[$Name])) {
        return $fallbacks[$Name]
    }

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    throw "Missing required CLI tool: $Name"
}

function Get-DeviceArgs {
    if ($Usb -and -not [string]::IsNullOrWhiteSpace($DeviceId)) {
        throw 'Use either -Usb or -DeviceId, not both.'
    }

    if (-not [string]::IsNullOrWhiteSpace($DeviceId)) {
        return @('-D', $DeviceId)
    }
    if ($Usb) {
        return @('-U')
    }
    return @('-H', $RemoteHost)
}

function Format-CommandLine {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$Arguments
    )

    $formatted = @($Executable)
    foreach ($arg in $Arguments) {
        if ($arg -match '[\s"]') {
            $formatted += ('"' + ($arg -replace '"', '\"') + '"')
        }
        else {
            $formatted += $arg
        }
    }
    return ($formatted -join ' ')
}

$deviceArgs = @(Get-DeviceArgs)

if ($ListDevices) {
    # frida-ls-devices uses a console renderer that can fail in redirected
    # Codex/CI sessions. The Python API produces stable non-TUI output.
    $tool = Get-ToolPath -Name 'python'
    $listCode = "import frida; print('ID\tTYPE\tNAME'); [print(f'{d.id}\t{d.type}\t{d.name}') for d in frida.get_device_manager().enumerate_devices()]"
    if ($DryRun) {
        "command=$(Format-CommandLine -Executable $tool -Arguments @('-c', $listCode))"
        exit 0
    }
    & $tool -c $listCode
    exit $LASTEXITCODE
}

if ($ListProcesses -or $ListApplications) {
    $tool = Get-ToolPath -Name 'frida-ps'
    $args = @($deviceArgs)
    if ($ListApplications) {
        $args += '-a'
    }
    if ($DryRun) {
        "command=$(Format-CommandLine -Executable $tool -Arguments $args)"
        exit 0
    }
    & $tool @args
    exit $LASTEXITCODE
}

$targetModes = @(
    -not [string]::IsNullOrWhiteSpace($Package),
    -not [string]::IsNullOrWhiteSpace($Process),
    $ProcessId -gt 0
).Where({ $_ }).Count

if ($targetModes -ne 1) {
    throw 'Provide exactly one target: -Package, -Process, or -ProcessId.'
}
if ($Spawn -and [string]::IsNullOrWhiteSpace($Package)) {
    throw '-Spawn requires -Package.'
}
if ($Pause -and -not $Spawn) {
    throw '-Pause is only valid with -Spawn.'
}
if ([string]::IsNullOrWhiteSpace($ScriptPath)) {
    throw 'Provide -ScriptPath for injection.'
}
if (-not (Test-Path -LiteralPath $ScriptPath)) {
    throw "Frida script not found: $ScriptPath"
}

$resolvedScript = (Resolve-Path -LiteralPath $ScriptPath).Path
$frida = Get-ToolPath -Name 'frida'
$args = @($deviceArgs)

if ($Spawn) {
    $args += @('-f', $Package)
}
elseif ($ProcessId -gt 0) {
    $args += @('-p', [string]$ProcessId)
}
elseif (-not [string]::IsNullOrWhiteSpace($Package)) {
    $args += @('-N', $Package)
}
else {
    $args += @('-n', $Process)
}

$args += @('-l', $resolvedScript)
if ($Pause) {
    $args += '--pause'
}

if ($DryRun) {
    "command=$(Format-CommandLine -Executable $frida -Arguments $args)"
    exit 0
}

& $frida @args
exit $LASTEXITCODE
