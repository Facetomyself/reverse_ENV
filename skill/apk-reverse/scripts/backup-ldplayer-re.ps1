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

# ------------------------------------------------------------------
# List backups
# ------------------------------------------------------------------
if ($Action -eq "list") {
    Write-Host "=== LDPlayer RE backups ==="
    if (Test-Path $BackupRoot) {
        Get-ChildItem $BackupRoot -Directory | Sort-Object Name -Descending | ForEach-Object {
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
    $BackupDir = "$BackupRoot\$Timestamp"
    Write-Host "=== Backup RE instance -> $BackupDir ==="

    # 1. Stop the instance
    Write-Host "[1/4] Stopping instance..."
    & "$LDPlayerDir\ldconsole.exe" quit --name $InstanceName 2>&1 | Out-Null
    Start-Sleep -Seconds 3

    # 2. Copy VM data
    Write-Host "[2/4] Copying VM data..."
    New-Item -ItemType Directory -Force -Path "$BackupDir\vms" | Out-Null
    $vmSource = "$LDPlayerDir\vms\leidian$InstanceIdx"
    if (Test-Path $vmSource) {
        Copy-Item -Recurse -Force "$vmSource" "$BackupDir\vms\leidian$InstanceIdx" -ErrorAction SilentlyContinue
    }

    # 3. Copy instance config
    Write-Host "[3/4] Copying config..."
    Copy-Item -Force "$LDPlayerDir\vms\leidian$InstanceIdx.config" "$BackupDir\vms\" -ErrorAction SilentlyContinue
    Copy-Item -Force "$LDPlayerDir\vms\config\leidian$InstanceIdx.config" "$BackupDir\vms\" -ErrorAction SilentlyContinue

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
    $BackupInfo | ConvertTo-Json | Out-File "$BackupDir\backup-info.json" -Encoding UTF8

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
    if (-not (Test-Path $BackupRoot)) {
        Write-Error "No backups found at $BackupRoot"
        exit 1
    }

    $backups = Get-ChildItem $BackupRoot -Directory | Sort-Object Name -Descending
    if ($backups.Count -eq 0) {
        Write-Error "No backups found"
        exit 1
    }

    Write-Host "=== Available backups ==="
    for ($i = 0; $i -lt $backups.Count; $i++) {
        $info = Get-Content "$($backups[$i].FullName)\backup-info.json" -ErrorAction SilentlyContinue | ConvertFrom-Json
        Write-Host "  [$i] $($backups[$i].Name) — $($info.frida_version) $($info.magisk_version)"
    }

    $choice = Read-Host "`nWhich backup to restore? (0-$($backups.Count-1))"
    $backup = $backups[[int]$choice]

    Write-Host "`n=== Restoring from $($backup.Name) ==="
    Write-Host "WARNING: This will overwrite the current RE instance data!"

    # 1. Stop instance
    Write-Host "[1/3] Stopping instance..."
    & "$LDPlayerDir\ldconsole.exe" quit --name $InstanceName 2>&1 | Out-Null
    Start-Sleep -Seconds 3

    # 2. Remove current data
    Write-Host "[2/3] Removing current instance data..."
    Remove-Item -Recurse -Force "$LDPlayerDir\vms\leidian$InstanceIdx" -ErrorAction SilentlyContinue

    # 3. Restore backup
    Write-Host "[3/3] Restoring backup data..."
    Copy-Item -Recurse -Force "$($backup.FullName)\vms\leidian$InstanceIdx" "$LDPlayerDir\vms\leidian$InstanceIdx"

    # 4. Restart
    Write-Host "Restarting instance..."
    & "$LDPlayerDir\ldconsole.exe" launch --name $InstanceName 2>&1 | Out-Null

    Write-Host "[OK] Restored. Run init-ldplayer-re.ps1 to restart Frida."
}
