#requires -Version 5.1

<#
.SYNOPSIS
Stop and optionally remove a project-dedicated LDPlayer instance.

.DESCRIPTION
Index 0 is reserved for MAA and is never touched. -Remove requires typing the
project name unless -Force is supplied.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$Project,

    [switch]$Remove,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$LdConsole = 'D:\leidian\LDPlayer9\ldconsole.exe'
$MaaIndex = 0

function Invoke-Ld {
    param([Parameter(Mandatory = $true)][string[]]$LdArgs)
    if (-not (Test-Path -LiteralPath $LdConsole)) {
        Write-Output "ERR:ldconsole_not_found:$LdConsole"
        exit 1
    }
    $out = & $LdConsole @LdArgs 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        Write-Output "ERR:ldconsole_failed:$code"
        if ($out) { Write-Output $out }
        exit $code
    }
    if ($out -is [array]) { return $out }
    if ($out) { return @($out) }
    return @()
}

function Get-Instances {
    $raw = Invoke-Ld -LdArgs @('list2')
    $instances = @()
    foreach ($line in $raw) {
        if (-not $line.Trim()) { continue }
        $parts = $line -split ','
        if ($parts.Count -lt 10) { continue }
        $instances += [PSCustomObject]@{
            Index = [int]$parts[0]
            Name = $parts[1]
            Running = [int]$parts[4] -eq 1
        }
    }
    return @($instances)
}

$target = Get-Instances | Where-Object { $_.Name -eq $Project } | Select-Object -First 1
if (-not $target) {
    Write-Output "OK:instance_not_found_nothing_to_destroy:$Project"
    exit 0
}
if ($target.Index -eq $MaaIndex) {
    Write-Output "ERR:project_resolves_to_index_0_MAA:$Project"
    exit 1
}

Write-Output ''
Write-Output "=== Destroy: $Project (index $($target.Index)) ==="
Write-Output ''

if ($target.Running) {
    Write-Output "Stopping instance '$Project'..."
    Invoke-Ld -LdArgs @('quit', '--index', [string]$target.Index) | Out-Null
    Start-Sleep -Seconds 2

    $check = Get-Instances | Where-Object { $_.Index -eq $target.Index } | Select-Object -First 1
    if ($check -and $check.Running) {
        Write-Output 'WARN:instance_still_running_after_first_quit'
        Invoke-Ld -LdArgs @('quit', '--index', [string]$target.Index) | Out-Null
        Start-Sleep -Seconds 3
    }
    Write-Output '  Stopped.'
} else {
    Write-Output 'Instance already stopped.'
}

if ($Remove) {
    if (-not $Force) {
        Write-Output ''
        Write-Output "WARNING: This will permanently delete instance '$Project' (index $($target.Index))."
        Write-Output 'Workspace files are not removed, but the emulator VM is deleted.'
        Write-Output ''
        $confirm = Read-Host "Type '$Project' to confirm deletion"
        if ($confirm -ne $Project) {
            Write-Output "Deletion cancelled. Expected '$Project', got '$confirm'."
            exit 1
        }
    }

    Write-Output "Removing instance '$Project'..."
    Invoke-Ld -LdArgs @('remove', '--index', [string]$target.Index) | Out-Null
    Start-Sleep -Seconds 2

    $check = Get-Instances | Where-Object { $_.Index -eq $target.Index -or $_.Name -eq $Project } | Select-Object -First 1
    if (-not $check) {
        Write-Output '  Removed.'
        Write-Output ''
        Write-Output "OK:destroyed:$Project"
        Write-Output "  Workspace files in D:\reverse_ENV\workspace\$Project\ are untouched."
    } else {
        Write-Output 'WARN:instance_may_still_exist'
        exit 1
    }
} else {
    Write-Output ''
    Write-Output "OK:stopped:$Project"
    Write-Output "  To also delete: re-destroy.ps1 -Project $Project -Remove"
    Write-Output "  To restart:     re-init.ps1 -Project $Project"
    Write-Output "  To rebuild:     re-init.ps1 -Project $Project -Template re-xposed"
}
