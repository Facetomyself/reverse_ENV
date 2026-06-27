#requires -Version 5.1

<#
.SYNOPSIS
LDPlayer 9 多实例管控（基于 ldconsole.exe CLI）

实例与 ADB 映射：leidian{N} ↔ emulator-{5554 + N*2}

.PARAMETER Action
list | status | launch | quit | reboot | add | copy | remove | modify | install | uninstall | runapp | adb
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('list', 'status', 'launch', 'quit', 'reboot',
                 'add', 'copy', 'remove', 'modify',
                 'install', 'uninstall', 'runapp', 'adb')]
    [string]$Action,

    [int]$Index = -1,
    [string]$Name,
    [string]$ApkPath,
    [string]$PackageName,
    [string]$Command,
    [string]$From,
    [string]$Title,
    [string]$Resolution,
    [string]$Cpu,
    [string]$Memory,
    [string]$Manufacturer,
    [string]$Model,
    [switch]$Root,
    [string]$FileName,
    [string]$Key,
    [string]$Value
)

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding           = [System.Text.UTF8Encoding]::new($false)

$LdConsole   = 'D:\leidian\LDPlayer9\ldconsole.exe'
$AdbExe      = 'D:\leidian\LDPlayer9\adb.exe'
$MaaIndex    = 0

# ── helpers ──────────────────────────────────────────────────────────

function Resolve-Target {
    $args = @()
    if ($Index -ge 0) { $args += '--index'; $args += $Index }
    elseif ($Name)    { $args += '--name';  $args += $Name }
    else              { $args += '--index'; $args += 0 }
    return $args
}

function Invoke-Ld {
    param([string[]]$LdArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $out = & $LdConsole @LdArgs 2>$null
    $ErrorActionPreference = $prev
    if ($out -is [array]) { return $out }
    if ($out) { return @($out) }
    return @()
}

function Get-AdbAddr { param([int]$I) return "emulator-$($I * 2 + 5554)" }

function Get-Instances {
    # Parse ldconsole list2 output: index,name,pid1,pid2,running_flag,width,height,dpi
    $raw = Invoke-Ld -LdArgs 'list2'
    $instances = @()
    foreach ($line in $raw) {
        if (-not $line.Trim()) { continue }
        $parts = $line -split ','
        if ($parts.Count -lt 5) { continue }
        $idx = [int]$parts[0]
        $instances += @{
            Index    = $idx
            Name     = $parts[1]
            Running  = [int]$parts[4] -eq 1
            Width    = $parts[7]
            Height   = $parts[8]
            Dpi      = $parts[9]
            Adb      = Get-AdbAddr -I $idx
        }
    }
    return $instances | Sort-Object Index
}

function Warn-Maa {
    if ($Index -eq $MaaIndex -or ($Index -lt 0 -and -not $Name)) {
        Write-Output 'WARN: target is index 0 (MAA) — ensure MAA is idle'
    }
}

# ── actions ──────────────────────────────────────────────────────────

switch ($Action) {

    'list' {
        $instances = Get-Instances
        if (-not $instances) { Write-Output 'No instances found.'; exit 0 }
        Write-Output "LDPlayer instances ($($instances.Count) total):"
        Write-Output ''
        foreach ($i in $instances) {
            $marker = @('', ' [MAA]')[$i.Index -eq $MaaIndex]
            $state  = @('STOPPED', 'RUNNING')[$i.Running]
            $adb    = $i.Adb
            $line   = "  [$($i.Index)] $($i.Name)  $state  $adb  $($i.Width)x$($i.Height)@$($i.Dpi)dpi$marker"
            Write-Output $line
        }
    }

    'status' {
        $target = Resolve-Target
        $targetIdx = if ($Index -ge 0) { $Index } else { 0 }
        $instances = Get-Instances
        $inst = $instances | Where-Object { $_.Index -eq $targetIdx } | Select-Object -First 1
        if (-not $inst) { Write-Output "Instance not found: index=$targetIdx"; exit 1 }

        Write-Output "Index:     $($inst.Index)"
        Write-Output "Name:      $($inst.Name)"
        Write-Output "Status:    $(@('STOPPED','RUNNING')[$inst.Running])"
        Write-Output "ADB:       $($inst.Adb)"
        Write-Output "Resolution:$($inst.Width)x$($inst.Height)@$($inst.Dpi)dpi"

        if ($inst.Running) {
            $model = & $AdbExe -s $inst.Adb shell getprop ro.product.model 2>$null
            $sdk   = & $AdbExe -s $inst.Adb shell getprop ro.build.version.sdk 2>$null
            if ($model) { Write-Output "Model:     $($model.Trim())" }
            if ($sdk)   { Write-Output "SDK:       $($sdk.Trim())" }
        }
        if ($inst.Index -eq $MaaIndex) { Write-Output "Note:      MAA is using this instance" }
    }

    'launch' {
        if ($Index -eq $MaaIndex) {
            $running = Invoke-Ld -LdArgs 'isrunning', '--index', $MaaIndex
            if ($running -eq 'running') {
                Write-Output 'INFO: MAA instance already running, not re-launching'
                exit 0
            }
        }
        $target = Resolve-Target
        Invoke-Ld -LdArgs @('launch') + $target | Out-Null
        Write-Output 'OK:launched'
    }

    'quit' {
        Warn-Maa
        $target = Resolve-Target
        Invoke-Ld -LdArgs @('quit') + $target | Out-Null
        Write-Output 'OK:quit'
    }

    'reboot' {
        Warn-Maa
        $target = Resolve-Target
        Invoke-Ld -LdArgs @('reboot') + $target | Out-Null
        Write-Output 'OK:rebooting'
    }

    'add' {
        $args = @('add')
        if ($Name) { $args += '--name'; $args += $Name }
        $result = Invoke-Ld -LdArgs $args
        Write-Output $result
    }

    'copy' {
        if (-not $From) { Write-Output 'ERR: --From required (source index or name)'; exit 1 }
        $args = @('copy', '--from', $From)
        if ($Name) { $args += '--name'; $args += $Name }
        $result = Invoke-Ld -LdArgs $args
        Write-Output $result
    }

    'remove' {
        if ($Index -eq $MaaIndex) {
            Write-Output 'ERR: refusing to remove index 0 (MAA instance)'
            exit 1
        }
        $target = Resolve-Target
        Invoke-Ld -LdArgs @('remove') + $target | Out-Null
        Write-Output 'OK:removed'
    }

    'modify' {
        $args = @('modify')
        $args += Resolve-Target
        if ($Resolution)    { $args += '--resolution'; $args += $Resolution }
        if ($Cpu)           { $args += '--cpu';        $args += $Cpu }
        if ($Memory)        { $args += '--memory';     $args += $Memory }
        if ($Manufacturer)  { $args += '--manufacturer'; $args += $Manufacturer }
        if ($Model)         { $args += '--model';      $args += $Model }
        if ($Root)          { $args += '--root';       $args += '1' }
        Invoke-Ld -LdArgs $args | Out-Null
        Write-Output 'OK:modified'
    }

    'install' {
        if (-not $ApkPath) { Write-Output 'ERR: -ApkPath required'; exit 1 }
        if (-not (Test-Path $ApkPath)) { Write-Output "ERR:file_not_found: $ApkPath"; exit 1 }
        $target = Resolve-Target
        Invoke-Ld -LdArgs @('installapp') + $target + @('--filename', $ApkPath) | Out-Null
        Write-Output 'OK:installed'
    }

    'uninstall' {
        if (-not $PackageName) { Write-Output 'ERR: -PackageName required'; exit 1 }
        $target = Resolve-Target
        Invoke-Ld -LdArgs @('uninstallapp') + $target + @('--packagename', $PackageName) | Out-Null
        Write-Output 'OK:uninstalled'
    }

    'runapp' {
        if (-not $PackageName) { Write-Output 'ERR: -PackageName required'; exit 1 }
        $target = Resolve-Target
        Invoke-Ld -LdArgs @('runapp') + $target + @('--packagename', $PackageName) | Out-Null
        Write-Output 'OK:launched'
    }

    'adb' {
        if (-not $Command) { Write-Output 'ERR: -Command required (adb shell command)'; exit 1 }
        $target = Resolve-Target
        $result = Invoke-Ld -LdArgs @('adb') + $target + @('--command', $Command)
        Write-Output $result
    }

}
