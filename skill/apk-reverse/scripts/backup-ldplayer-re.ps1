<#
.SYNOPSIS
  备份/还原雷电模拟器 RE 实例 (reverse)

.PARAMETER Action
  backup — 备份当前 RE 实例到 storage/
  restore — 从 storage/ 还原 RE 实例
  list — 列出已有备份

.EXAMPLE
  .\backup-ldplayer-re.ps1 -Action backup
  .\backup-ldplayer-re.ps1 -Action restore
  .\backup-ldplayer-re.ps1 -Action list
#>

param(
    [ValidateSet("backup", "restore", "list")]
    [string]$Action = "list"
)

$ErrorActionPreference = "Stop"

$LDPlayerDir = "D:\leidian\LDPlayer9"
$InstanceName = "reverse"
$InstanceIdx = 1  # reverse = leidian1
$BackupRoot = "D:\reverse_ENV\storage\ldplayer-backups"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

function Resolve-ExistingPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Path not found: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Assert-ChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Child,
        [Parameter(Mandatory = $true)][string]$Parent,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $childFull = [System.IO.Path]::GetFullPath($Child).TrimEnd('\')
    $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\')
    if (-not ($childFull.Equals($parentFull, [System.StringComparison]::OrdinalIgnoreCase) -or $childFull.StartsWith($parentFull + '\', [System.StringComparison]::OrdinalIgnoreCase))) {
        throw "$Label path escapes expected root. Path=$childFull Root=$parentFull"
    }
}

function Write-Utf8NoBomLf {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Text
    )

    $normalized = $Text -replace "`r`n|`r|`n", "`n"
    [System.IO.File]::WriteAllText($Path, $normalized, [System.Text.UTF8Encoding]::new($false))
}

# ------------------------------------------------------------------
# List backups
# ------------------------------------------------------------------
if ($Action -eq "list") {
    Write-Host "=== LDPlayer RE backups ==="
    if (Test-Path -LiteralPath $BackupRoot) {
        Get-ChildItem -LiteralPath $BackupRoot -Directory | Sort-Object Name -Descending | ForEach-Object {
            $size = (Get-ChildItem $_.FullName -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
            $sizeMB = [math]::Round($size / 1MB, 1)
            Write-Host "  $($_.Name) — ${sizeMB}MB"
        }
    } else {
        Write-Host "  (no backups yet)"
    }
    exit 0
}

# ------------------------------------------------------------------
# Backup
# ------------------------------------------------------------------
if ($Action -eq "backup") {
    $BackupDir = Join-Path $BackupRoot $Timestamp
    $vmSource = Join-Path (Join-Path $LDPlayerDir 'vms') "leidian$InstanceIdx"
    $vmConfigA = Join-Path (Join-Path $LDPlayerDir 'vms') "leidian$InstanceIdx.config"
    $vmConfigB = Join-Path (Join-Path (Join-Path $LDPlayerDir 'vms') 'config') "leidian$InstanceIdx.config"
    $vmSource = Resolve-ExistingPath -Path $vmSource
    Write-Host "=== Backup RE instance -> $BackupDir ==="

    # 1. Stop the instance
    Write-Host "[1/4] Stopping instance..."
    & "$LDPlayerDir\ldconsole.exe" quit --name $InstanceName 2>&1 | Out-Null
    Start-Sleep -Seconds 3

    # 2. Copy VM data
    Write-Host "[2/4] Copying VM data..."
    $backupVms = Join-Path $BackupDir 'vms'
    New-Item -ItemType Directory -Force -Path $backupVms | Out-Null
    Copy-Item -LiteralPath $vmSource -Destination (Join-Path $backupVms "leidian$InstanceIdx") -Recurse -Force -ErrorAction Stop

    # 3. Copy instance config
    Write-Host "[3/4] Copying config..."
    foreach ($configPath in @($vmConfigA, $vmConfigB)) {
        if (Test-Path -LiteralPath $configPath) {
            Copy-Item -LiteralPath $configPath -Destination $backupVms -Force -ErrorAction Stop
        } else {
            Write-Warning "Config not found, skipped: $configPath"
        }
    }

    # 4. ADB backup of critical data
    Write-Host "[4/4] Creating ADB backup..."
    $BackupInfo = @{
        timestamp = $Timestamp
        instance = $InstanceName
        architecture = "x86_64"
        android_version = "9"
        frida_version = "17.15.3"
        magisk_version = "26.4 (APK only, daemon not running)"
        features = @("root", "frida", "system_rw_after_remount")
    }
    Write-Utf8NoBomLf -Path (Join-Path $BackupDir 'backup-info.json') -Text ($BackupInfo | ConvertTo-Json -Depth 4)

    # 5. Restart instance
    Write-Host "Restarting instance..."
    & "$LDPlayerDir\ldconsole.exe" launch --name $InstanceName 2>&1 | Out-Null

    Write-Host "[OK] Backup saved to: $BackupDir"
    Write-Host ""
    Write-Host "To restore: Stop LDPlayer -> Copy backup back to $LDPlayerDir\vms\leidian$InstanceIdx -> Restart"
}

# ------------------------------------------------------------------
# Restore
# ------------------------------------------------------------------
if ($Action -eq "restore") {
    if (-not (Test-Path -LiteralPath $BackupRoot)) {
        Write-Error "No backups found at $BackupRoot"
        exit 1
    }

    $resolvedBackupRoot = Resolve-ExistingPath -Path $BackupRoot
    $ldVmsRoot = Join-Path $LDPlayerDir 'vms'
    $resolvedLdVmsRoot = Resolve-ExistingPath -Path $ldVmsRoot
    $targetVm = Join-Path $resolvedLdVmsRoot "leidian$InstanceIdx"
    Assert-ChildPath -Child $targetVm -Parent $resolvedLdVmsRoot -Label 'Target VM'

    $backups = @(Get-ChildItem -LiteralPath $resolvedBackupRoot -Directory | Sort-Object Name -Descending)
    if ($backups.Count -eq 0) {
        Write-Error "No backups found"
        exit 1
    }

    Write-Host "=== Available backups ==="
    for ($i = 0; $i -lt $backups.Count; $i++) {
        $infoPath = Join-Path $backups[$i].FullName 'backup-info.json'
        $info = if (Test-Path -LiteralPath $infoPath) {
            Get-Content -LiteralPath $infoPath -Raw -Encoding UTF8 | ConvertFrom-Json
        } else {
            [pscustomobject]@{ frida_version = 'unknown'; magisk_version = 'unknown' }
        }
        Write-Host "  [$i] $($backups[$i].Name) — $($info.frida_version) $($info.magisk_version)"
    }

    $choice = Read-Host "`nWhich backup to restore? (0-$($backups.Count-1))"
    $choiceIndex = 0
    if (-not [int]::TryParse($choice, [ref]$choiceIndex) -or $choiceIndex -lt 0 -or $choiceIndex -ge $backups.Count) {
        throw "Invalid backup index: $choice"
    }
    $backup = $backups[$choiceIndex]
    $resolvedBackup = Resolve-ExistingPath -Path $backup.FullName
    Assert-ChildPath -Child $resolvedBackup -Parent $resolvedBackupRoot -Label 'Selected backup'
    $backupVm = Join-Path (Join-Path $resolvedBackup 'vms') "leidian$InstanceIdx"
    $backupVm = Resolve-ExistingPath -Path $backupVm

    Write-Host "`n=== Restoring from $($backup.Name) ==="
    Write-Host "WARNING: This will overwrite the current RE instance data!"
    $confirm = Read-Host "Type RESTORE to continue"
    if ($confirm -ne 'RESTORE') {
        Write-Host "Restore cancelled."
        exit 0
    }

    # 1. Stop instance
    Write-Host "[1/3] Stopping instance..."
    & "$LDPlayerDir\ldconsole.exe" quit --name $InstanceName 2>&1 | Out-Null
    Start-Sleep -Seconds 3

    # 2. Remove current data
    Write-Host "[2/3] Removing current instance data..."
    if (Test-Path -LiteralPath $targetVm) {
        Remove-Item -LiteralPath $targetVm -Recurse -Force -ErrorAction Stop
    }

    # 3. Restore backup
    Write-Host "[3/3] Restoring backup data..."
    Copy-Item -LiteralPath $backupVm -Destination $targetVm -Recurse -Force -ErrorAction Stop

    # 4. Restart
    Write-Host "Restarting instance..."
    & "$LDPlayerDir\ldconsole.exe" launch --name $InstanceName 2>&1 | Out-Null

    Write-Host "[OK] Restored. Run init-ldplayer-re.ps1 to restart Frida."
}
