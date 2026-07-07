#requires -Version 5.1

<#
.SYNOPSIS
LDPlayer 9 multi-instance controller based on ldconsole.exe.

.DESCRIPTION
All target-aware actions resolve -Index / -Name to a concrete instance first.
Write operations refuse to touch index 0, which is reserved for MAA.

.PARAMETER Action
list | status | launch | quit | reboot | add | copy | remove | modify |
install | uninstall | runapp | adb | proxy-on | proxy-off
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('list', 'status', 'launch', 'quit', 'reboot',
                 'add', 'copy', 'remove', 'modify',
                 'install', 'uninstall', 'runapp', 'adb',
                 'proxy-on', 'proxy-off')]
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
    [string]$Value,
    [int]$ProxyPort = 8080,
    [string]$Project
)

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding           = [System.Text.UTF8Encoding]::new($false)

$LdConsole  = 'D:\leidian\LDPlayer9\ldconsole.exe'
$AdbExe     = 'D:\leidian\LDPlayer9\adb.exe'
$MaaIndex   = 0
$MitmProxy  = 'D:\reverse_ENV\.venv\Scripts\mitmdump.exe'
$Workspace  = 'D:\reverse_ENV\workspace'
$CaCert     = 'D:\reverse_ENV\tools\c8750f0d.0'
$CaHash     = 'c8750f0d'
$CertDir    = '/data/local/tmp/cacerts'
$CertSystem = '/system/etc/security/cacerts'

function Assert-FileExists {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Output "ERR:${Label}_not_found:$Path"
        exit 1
    }
}

function Assert-ProjectName {
    param([string]$Value)
    if (-not $Value -or $Value -notmatch '^[A-Za-z0-9._-]+$') {
        Write-Output "ERR:invalid_project_name:$Value"
        Write-Output 'HINT: use only ASCII letters, digits, dot, underscore, and dash.'
        exit 1
    }
}

function Invoke-Ld {
    param(
        [Parameter(Mandatory = $true)][string[]]$LdArgs,
        [switch]$AllowNonZero,
        [switch]$TreatPositiveExitCodeAsSuccess
    )
    Assert-FileExists -Path $LdConsole -Label 'ldconsole'
    $out = & $LdConsole @LdArgs 2>&1
    $code = $LASTEXITCODE
    if ($TreatPositiveExitCodeAsSuccess -and $code -gt 0) {
        $out = @($out) + "OK:ldconsole_returned_new_index:$code"
        $code = 0
    }
    if ($code -ne 0 -and -not $AllowNonZero) {
        Write-Output "ERR:ldconsole_failed:$code"
        Write-Output "CMD:ldconsole $($LdArgs -join ' ')"
        if ($out) { Write-Output $out }
        exit $code
    } elseif ($code -ne 0) {
        Write-Output "WARN:ldconsole_nonzero_exit:$code cmd=ldconsole $($LdArgs -join ' ')"
    }
    if ($out -is [array]) { return $out }
    if ($out) { return @($out) }
    return @()
}

function Get-AdbAddr {
    param([int]$I)
    return "emulator-$($I * 2 + 5554)"
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
            Index   = $idx
            Name    = $parts[1]
            Running = [int]$parts[4] -eq 1
            Width   = $parts[7]
            Height  = $parts[8]
            Dpi     = $parts[9]
            Adb     = Get-AdbAddr -I $idx
        }
    }
    return @($instances | Sort-Object Index)
}

function Resolve-Instance {
    param([switch]$Required)
    $instances = Get-Instances

    if ($Index -ge 0) {
        $inst = $instances | Where-Object { $_.Index -eq $Index } | Select-Object -First 1
    } elseif ($Name) {
        $inst = $instances | Where-Object { $_.Name -eq $Name } | Select-Object -First 1
    } else {
        $inst = $instances | Where-Object { $_.Index -eq $MaaIndex } | Select-Object -First 1
    }

    if ($Required -and -not $inst) {
        $target = if ($Index -ge 0) { "index=$Index" } elseif ($Name) { "name=$Name" } else { "index=$MaaIndex" }
        Write-Output "ERR:instance_not_found:$target"
        exit 1
    }
    return $inst
}

function Get-TargetArgs {
    param([Parameter(Mandatory = $true)]$Instance)
    return @('--index', [string]$Instance.Index)
}

function Assert-NotMaa {
    param($Instance, [string]$Operation)
    if ($Instance.Index -eq $MaaIndex) {
        Write-Output "ERR:refusing_${Operation}_index_0_MAA"
        exit 1
    }
}

function Get-ProjectDir {
    param([string]$ProjectName, [switch]$Create)
    $dir = Join-Path $Workspace $ProjectName
    if ($Create -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    return $dir
}

function Get-ProxyPidFile {
    param([string]$ProjectName, [switch]$Create)
    return (Join-Path (Get-ProjectDir -ProjectName $ProjectName -Create:$Create) 'mitmdump.pid')
}

function Test-ProcessAlive {
    param([int]$ProcessId)
    return [bool](Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Invoke-AdbQuiet {
    param([Parameter(Mandatory = $true)][string[]]$AdbArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $AdbExe @AdbArgs 2>$null | Out-Null
    $ErrorActionPreference = $prev
}

switch ($Action) {
    'list' {
        $instances = Get-Instances
        if (-not $instances) { Write-Output 'No instances found.'; exit 0 }
        Write-Output "LDPlayer instances ($($instances.Count) total):"
        Write-Output ''
        foreach ($i in $instances) {
            $marker = if ($i.Index -eq $MaaIndex) { ' [MAA]' } else { '' }
            $state = if ($i.Running) { 'RUNNING' } else { 'STOPPED' }
            Write-Output "  [$($i.Index)] $($i.Name)  $state  $($i.Adb)  $($i.Width)x$($i.Height)@$($i.Dpi)dpi$marker"
        }
    }

    'status' {
        $inst = Resolve-Instance -Required
        $state = if ($inst.Running) { 'RUNNING' } else { 'STOPPED' }
        Write-Output "Index:     $($inst.Index)"
        Write-Output "Name:      $($inst.Name)"
        Write-Output "Status:    $state"
        Write-Output "ADB:       $($inst.Adb)"
        Write-Output "Resolution:$($inst.Width)x$($inst.Height)@$($inst.Dpi)dpi"
        if ($inst.Running) {
            Assert-FileExists -Path $AdbExe -Label 'adb'
            $model = & $AdbExe -s $inst.Adb shell getprop ro.product.model 2>$null
            $sdk = & $AdbExe -s $inst.Adb shell getprop ro.build.version.sdk 2>$null
            if ($model) { Write-Output "Model:     $($model.Trim())" }
            if ($sdk) { Write-Output "SDK:       $($sdk.Trim())" }
        }
        if ($inst.Index -eq $MaaIndex) { Write-Output 'Note:      MAA is using this instance' }
    }

    'launch' {
        $inst = Resolve-Instance -Required
        Assert-NotMaa -Instance $inst -Operation 'launch'
        Invoke-Ld -LdArgs (@('launch') + (Get-TargetArgs -Instance $inst)) | Out-Null
        Write-Output 'OK:launched'
    }

    'quit' {
        $inst = Resolve-Instance -Required
        Assert-NotMaa -Instance $inst -Operation 'quit'
        Invoke-Ld -LdArgs (@('quit') + (Get-TargetArgs -Instance $inst)) | Out-Null
        Write-Output 'OK:quit'
    }

    'reboot' {
        $inst = Resolve-Instance -Required
        Assert-NotMaa -Instance $inst -Operation 'reboot'
        Invoke-Ld -LdArgs (@('reboot') + (Get-TargetArgs -Instance $inst)) | Out-Null
        Write-Output 'OK:rebooting'
    }

    'add' {
        if ($Name) { Assert-ProjectName -Value $Name }
        $args = @('add')
        if ($Name) { $args += @('--name', $Name) }
        Invoke-Ld -LdArgs $args -AllowNonZero
    }

    'copy' {
        if (-not $From) { Write-Output 'ERR:-From required'; exit 1 }
        if ($Name) { Assert-ProjectName -Value $Name }
        $args = @('copy')
        if ($Name) { $args += @('--name', $Name) }
        $args += @('--from', $From)
        Invoke-Ld -LdArgs $args -TreatPositiveExitCodeAsSuccess | Out-Null
        if ($Name) {
            $created = Get-Instances | Where-Object { $_.Name -eq $Name } | Select-Object -First 1
            if (-not $created) {
                Write-Output "ERR:copy_did_not_create_instance:$Name"
                exit 1
            }
            Write-Output "OK:copied index=$($created.Index) name=$Name from=$From"
        } else {
            Write-Output 'OK:copy_requested'
        }
    }

    'remove' {
        $inst = Resolve-Instance -Required
        Assert-NotMaa -Instance $inst -Operation 'remove'
        Invoke-Ld -LdArgs (@('remove') + (Get-TargetArgs -Instance $inst)) | Out-Null
        Write-Output 'OK:removed'
    }

    'modify' {
        $inst = Resolve-Instance -Required
        Assert-NotMaa -Instance $inst -Operation 'modify'
        $args = @('modify') + (Get-TargetArgs -Instance $inst)
        if ($Resolution) { $args += @('--resolution', $Resolution) }
        if ($Cpu) { $args += @('--cpu', $Cpu) }
        if ($Memory) { $args += @('--memory', $Memory) }
        if ($Manufacturer) { $args += @('--manufacturer', $Manufacturer) }
        if ($Model) { $args += @('--model', $Model) }
        if ($Root) { $args += @('--root', '1') }
        Invoke-Ld -LdArgs $args | Out-Null
        Write-Output 'OK:modified'
    }

    'install' {
        if (-not $ApkPath) { Write-Output 'ERR:-ApkPath required'; exit 1 }
        if (-not (Test-Path -LiteralPath $ApkPath)) { Write-Output "ERR:file_not_found:$ApkPath"; exit 1 }
        $inst = Resolve-Instance -Required
        Assert-NotMaa -Instance $inst -Operation 'install'
        Invoke-Ld -LdArgs (@('installapp') + (Get-TargetArgs -Instance $inst) + @('--filename', $ApkPath)) | Out-Null
        Write-Output 'OK:installed'
    }

    'uninstall' {
        if (-not $PackageName) { Write-Output 'ERR:-PackageName required'; exit 1 }
        $inst = Resolve-Instance -Required
        Assert-NotMaa -Instance $inst -Operation 'uninstall'
        Invoke-Ld -LdArgs (@('uninstallapp') + (Get-TargetArgs -Instance $inst) + @('--packagename', $PackageName)) | Out-Null
        Write-Output 'OK:uninstalled'
    }

    'runapp' {
        if (-not $PackageName) { Write-Output 'ERR:-PackageName required'; exit 1 }
        $inst = Resolve-Instance -Required
        Assert-NotMaa -Instance $inst -Operation 'runapp'
        Invoke-Ld -LdArgs (@('runapp') + (Get-TargetArgs -Instance $inst) + @('--packagename', $PackageName)) | Out-Null
        Write-Output 'OK:launched'
    }

    'adb' {
        if (-not $Command) { Write-Output 'ERR:-Command required'; exit 1 }
        $inst = Resolve-Instance -Required
        Assert-NotMaa -Instance $inst -Operation 'adb'
        Invoke-Ld -LdArgs (@('adb') + (Get-TargetArgs -Instance $inst) + @('--command', $Command))
    }

    'proxy-on' {
        if (-not $Project) { Write-Output 'ERR:-Project required'; exit 1 }
        Assert-ProjectName -Value $Project
        $inst = Resolve-Instance -Required
        Assert-NotMaa -Instance $inst -Operation 'proxy_on'
        if (-not $inst.Running) { Write-Output "ERR:instance_not_running:index=$($inst.Index)"; exit 1 }
        Assert-FileExists -Path $AdbExe -Label 'adb'
        Assert-FileExists -Path $MitmProxy -Label 'mitmdump'
        Assert-FileExists -Path $CaCert -Label 'mitmproxy_ca'

        $adbAddr = $inst.Adb
        $projectDir = Get-ProjectDir -ProjectName $Project -Create
        $flowFile = Join-Path $projectDir 'mitmproxy_traffic.flow'
        $pidFile = Get-ProxyPidFile -ProjectName $Project -Create

        Write-Output 'Installing CA cert...'
        Invoke-AdbQuiet -AdbArgs @('-s', $adbAddr, 'push', $CaCert, "/sdcard/$CaHash.0")
        Invoke-AdbQuiet -AdbArgs @('-s', $adbAddr, 'root')
        Start-Sleep -Seconds 1

        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $bindResult = & $AdbExe -s $adbAddr shell "su -c '
            if [ ! -d $CertDir ]; then
                cp -r $CertSystem $CertDir
            fi
            cp /sdcard/$CaHash.0 $CertDir/
            chmod 644 $CertDir/$CaHash.0
            mount --bind $CertDir $CertSystem 2>/dev/null
            ls $CertSystem/$CaHash.0
        '" 2>$null
        $ErrorActionPreference = $prev

        if ($bindResult -match $CaHash) {
            Write-Output 'OK:ca_cert_installed'
        } else {
            Write-Output "WARN:ca_cert_may_not_be_active:$bindResult"
        }

        Invoke-AdbQuiet -AdbArgs @('-s', $adbAddr, 'reverse', "tcp:$ProxyPort", "tcp:$ProxyPort")
        Write-Output "OK:adb_reverse tcp:$ProxyPort"

        Invoke-AdbQuiet -AdbArgs @('-s', $adbAddr, 'shell', "settings put global http_proxy 127.0.0.1:$ProxyPort")
        Write-Output "OK:proxy_set 127.0.0.1:$ProxyPort"

        $existingPid = $null
        if (Test-Path -LiteralPath $pidFile) {
            $rawPid = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($rawPid -match '^\d+$') { $existingPid = [int]$rawPid }
        }

        if ($existingPid -and (Test-ProcessAlive -ProcessId $existingPid)) {
            Write-Output "OK:mitmdump_already_running pid=$existingPid flow=$flowFile"
        } else {
            $proc = Start-Process -WindowStyle Hidden -FilePath $MitmProxy `
                -ArgumentList @('-p', [string]$ProxyPort, '-w', $flowFile, '--set', 'stream_large_bodies=10m') `
                -PassThru
            Set-Content -LiteralPath $pidFile -Value $proc.Id -Encoding ASCII
            Start-Sleep -Seconds 2
            Write-Output "OK:mitmdump_started pid=$($proc.Id) flow=$flowFile"
        }

        Write-Output ''
        Write-Output '=== HTTPS interception ACTIVE ==='
        Write-Output "Instance: [$($inst.Index)] $($inst.Name)"
        Write-Output "Proxy:    127.0.0.1:$ProxyPort"
        Write-Output "Project:  $Project"
        Write-Output "Traffic:  $flowFile"
        Write-Output "PidFile:  $pidFile"
    }

    'proxy-off' {
        if (-not $Project) { Write-Output 'ERR:-Project required'; exit 1 }
        Assert-ProjectName -Value $Project
        $inst = Resolve-Instance -Required
        Assert-NotMaa -Instance $inst -Operation 'proxy_off'
        Assert-FileExists -Path $AdbExe -Label 'adb'

        $adbAddr = $inst.Adb
        $pidFile = Get-ProxyPidFile -ProjectName $Project

        Invoke-AdbQuiet -AdbArgs @('-s', $adbAddr, 'shell', 'settings delete global http_proxy')
        Write-Output 'OK:proxy_cleared'

        Invoke-AdbQuiet -AdbArgs @('-s', $adbAddr, 'reverse', '--remove', "tcp:$ProxyPort")
        Write-Output 'OK:adb_reverse_removed'

        if (Test-Path -LiteralPath $pidFile) {
            $rawPid = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($rawPid -match '^\d+$' -and (Test-ProcessAlive -ProcessId ([int]$rawPid))) {
                Stop-Process -Id ([int]$rawPid) -Force
                Write-Output "OK:mitmdump_stopped pid=$rawPid"
            } else {
                Write-Output 'OK:mitmdump_not_running'
            }
            Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
        } else {
            Write-Output 'OK:mitmdump_pidfile_not_found'
        }

        Write-Output ''
        Write-Output '=== HTTPS interception OFF ==='
    }
}
