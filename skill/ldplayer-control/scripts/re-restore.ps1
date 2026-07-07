#requires -Version 5.1

<#
.SYNOPSIS
  Restore a managed LDPlayer RE instance from storage\ldplayer-backups.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-restore.ps1" -Project target-xposed -BackupFile "D:\reverse_ENV\storage\ldplayer-backups\re-xposed.verified.20260707_104718.ldbk" -Force

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File "D:\reverse_ENV\skill\ldplayer-control\scripts\re-restore.ps1" -Project target-xposed -SourceProject re-xposed -Force
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [string]$SourceProject = "",

    [string]$BackupFile = "",

    [string]$BackupRoot = "D:\reverse_ENV\storage\ldplayer-backups",

    [switch]$Force
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

function Assert-ChildPath {
    param([string]$Child, [string]$Parent)
    $childFull = [System.IO.Path]::GetFullPath($Child).TrimEnd('\')
    $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\')
    if (-not ($childFull.Equals($parentFull, [System.StringComparison]::OrdinalIgnoreCase) -or $childFull.StartsWith($parentFull + '\', [System.StringComparison]::OrdinalIgnoreCase))) {
        throw "Path escapes backup root. Path=$childFull Root=$parentFull"
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
        $items += [pscustomobject]@{ Index = [int]$parts[0]; Name = $parts[1] }
    }
    return @($items)
}

Assert-ProjectName -Value $Project
if ($SourceProject) {
    Assert-ProjectName -Value $SourceProject
} else {
    $SourceProject = $Project
}
if (-not (Test-Path -LiteralPath $LdConsole)) {
    throw "ldconsole not found: $LdConsole"
}

$inst = Get-Instances | Where-Object { $_.Name -eq $Project } | Select-Object -First 1
if (-not $inst) { throw "Target instance must already exist: $Project" }
if ($inst.Index -eq $MaaIndex) { throw "Refusing to restore index 0 MAA instance." }

$backupRootFull = [System.IO.Path]::GetFullPath($BackupRoot)
if (-not $BackupFile) {
    $latest = Get-ChildItem -LiteralPath $BackupRoot -File -Filter "*.ldbk" |
        Where-Object { $_.Name -like "$SourceProject.*.ldbk" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $latest) {
        throw "No backup file found for source project: $SourceProject"
    }
    $BackupFile = $latest.FullName
}

if (-not (Test-Path -LiteralPath $BackupFile)) {
    throw "Backup file not found: $BackupFile"
}
Assert-ChildPath -Child $BackupFile -Parent $backupRootFull

if (-not $Force) {
    $confirm = Read-Host "Type $Project to restore into [$($inst.Index)] $Project from $BackupFile"
    if ($confirm -ne $Project) {
        Write-Output "Restore cancelled."
        exit 0
    }
}

& $LdConsole quit --index $inst.Index 2>&1 | Out-Null
Start-Sleep -Seconds 5

Write-Output "Restoring $BackupFile -> [$($inst.Index)] $Project"
& $LdConsole restore --index $inst.Index --file $BackupFile
if ($LASTEXITCODE -ne 0) {
    throw "ldconsole restore failed with exit code $LASTEXITCODE"
}

& $LdConsole rename --index $inst.Index --title $Project 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "ldconsole rename failed after restore with exit code $LASTEXITCODE"
}

$restored = Get-Instances | Where-Object { $_.Index -eq $inst.Index } | Select-Object -First 1
if (-not $restored) {
    throw "Restored instance index disappeared: $($inst.Index)"
}
if ($restored.Name -ne $Project) {
    throw "Restored instance name mismatch: index=$($inst.Index) expected=$Project actual=$($restored.Name)"
}

Write-Output "OK:restored $Project"
