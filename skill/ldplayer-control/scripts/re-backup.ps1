#requires -Version 5.1

<#
.SYNOPSIS
  Back up a managed LDPlayer RE instance to storage\ldplayer-backups.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-backup.ps1" -Project re-xposed -Tag verified
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [string]$Tag = "verified",

    [string]$BackupRoot = "D:\reverse_ENV\storage\ldplayer-backups",

    [switch]$NoStop
)

$ErrorActionPreference = "Stop"
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding           = [System.Text.UTF8Encoding]::new($false)

$LdConsole = "D:\leidian\LDPlayer9\ldconsole.exe"
$MaaIndex = 0

function Assert-ProjectName {
    param([string]$Value)
    if (-not $Value -or $Value -notmatch '^[A-Za-z0-9._-]+$') {
        throw "Invalid project name: $Value"
    }
}

function Get-Instances {
    $raw = & $LdConsole list2 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "ldconsole list2 failed: $($raw -join "`n")"
    }
    $items = @()
    foreach ($line in $raw) {
        if (-not $line.Trim()) { continue }
        $parts = $line -split ','
        if ($parts.Count -lt 10) { continue }
        $items += [pscustomobject]@{
            Index = [int]$parts[0]
            Name = $parts[1]
            Running = [int]$parts[4] -eq 1
            Width = $parts[7]
            Height = $parts[8]
            Dpi = $parts[9]
        }
    }
    return @($items)
}

function Write-Utf8NoBomLf {
    param([string]$Path, [string]$Text)
    $normalized = $Text -replace "`r`n|`r|`n", "`n"
    [System.IO.File]::WriteAllText($Path, $normalized, [System.Text.UTF8Encoding]::new($false))
}

Assert-ProjectName -Value $Project
Assert-ProjectName -Value $Tag
if (-not (Test-Path -LiteralPath $LdConsole)) {
    throw "ldconsole not found: $LdConsole"
}

$inst = Get-Instances | Where-Object { $_.Name -eq $Project } | Select-Object -First 1
if (-not $inst) { throw "Instance not found: $Project" }
if ($inst.Index -eq $MaaIndex) { throw "Refusing to back up index 0 MAA instance." }

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path $BackupRoot "$Project.$Tag.$stamp.ldbk"
$metaFile = "$backupFile.json"

if (-not $NoStop) {
    & $LdConsole quit --name $Project 2>&1 | Out-Null
    Start-Sleep -Seconds 5
}

Write-Output "Backing up [$($inst.Index)] $Project -> $backupFile"
& $LdConsole backup --name $Project --file $backupFile
if ($LASTEXITCODE -ne 0) {
    throw "ldconsole backup failed with exit code $LASTEXITCODE"
}

$meta = [ordered]@{
    project = $Project
    tag = $Tag
    timestamp = $stamp
    source_index = $inst.Index
    resolution = "$($inst.Width)x$($inst.Height)@$($inst.Dpi)dpi"
    backup_file = $backupFile
}
Write-Utf8NoBomLf -Path $metaFile -Text ($meta | ConvertTo-Json -Depth 4)

Write-Output "OK:backup_saved $backupFile"
Write-Output "OK:metadata_saved $metaFile"
