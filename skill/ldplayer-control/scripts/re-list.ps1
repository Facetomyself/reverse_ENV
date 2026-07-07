#requires -Version 5.1

<#
.SYNOPSIS
List LDPlayer instances with RE project annotations.
#>

[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$Project
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
        $idx = [int]$parts[0]
        $instances += [PSCustomObject]@{
            Index = $idx
            Name = $parts[1]
            Running = [int]$parts[4] -eq 1
            Width = $parts[7]
            Height = $parts[8]
            Dpi = $parts[9]
            Adb = "emulator-$($idx * 2 + 5554)"
        }
    }
    return @($instances | Sort-Object Index)
}

$instances = @(Get-Instances)
if ($Project) {
    $instances = @($instances | Where-Object { $_.Name -eq $Project })
    if ($instances.Count -eq 0) {
        Write-Output "No instance found for project '$Project'."
        Write-Output "Create one: re-init.ps1 -Project $Project -Template re-xposed"
        exit 1
    }
}

if ($instances.Count -eq 0) {
    Write-Output 'No LDPlayer instances found.'
    Write-Output 'Create your first RE project instance: re-init.ps1 -Project <name> -Template re-xposed'
    exit 0
}

$classified = @($instances | ForEach-Object {
    $type = if ($_.Index -eq $MaaIndex) { 'MAA' }
            elseif ($_.Name -and $_.Name -match '^[A-Za-z0-9._-]+$') { 'RE' }
            elseif ($_.Name) { 'NONASCII' }
            else { 'ORPHAN' }
    $_ | Add-Member -NotePropertyName Type -NotePropertyValue $type -PassThru
})

$maaCount = @($classified | Where-Object { $_.Type -eq 'MAA' }).Count
$reCount = @($classified | Where-Object { $_.Type -eq 'RE' }).Count
$nonAsciiCount = @($classified | Where-Object { $_.Type -eq 'NONASCII' }).Count
$orphanCount = @($classified | Where-Object { $_.Type -eq 'ORPHAN' }).Count

Write-Output ''
Write-Output "=== LDPlayer Instances ($($classified.Count) total: $maaCount MAA, $reCount RE, $nonAsciiCount non-ascii, $orphanCount orphan) ==="
Write-Output ''

$header = "{0,-10} {1,-6} {2,-24} {3,-8} {4,-18} {5,-16} {6}" -f 'Type', 'Index', 'Name', 'Status', 'ADB', 'Resolution', 'Note'
Write-Output $header
Write-Output ('-' * 110)

foreach ($i in $classified) {
    $status = if ($i.Running) { 'RUNNING' } else { 'STOPPED' }
    $res = "$($i.Width)x$($i.Height)@$($i.Dpi)dpi"
    $note = switch ($i.Type) {
        'MAA' { 'DO NOT TOUCH' }
        'NONASCII' { 'not a managed RE project name' }
        'ORPHAN' { 'unnamed; review before removal' }
        default { "project: $($i.Name)" }
    }
    $line = "{0,-10} {1,-6} {2,-24} {3,-8} {4,-18} {5,-16} {6}" -f "[$($i.Type)]", $i.Index, $i.Name, $status, $i.Adb, $res, $note
    Write-Output $line
}

Write-Output ''
Write-Output 'Commands:'
Write-Output '  re-init.ps1    -Project <name> [-Template re-xposed]  create/copy and launch project instance'
Write-Output '  re-proxy.ps1   -Project <name> -Action on/off          proxy for project'
Write-Output '  re-backup.ps1  -Project <name> [-Tag verified]         back up instance'
Write-Output '  re-restore.ps1 -Project <name> [-SourceProject name]   restore by index and rename'
Write-Output '  re-destroy.ps1 -Project <name> [-Remove]               stop or delete project instance'
Write-Output ''
