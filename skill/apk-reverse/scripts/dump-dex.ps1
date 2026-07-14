#requires -Version 5.1

[CmdletBinding()]
param(
    [string]$Project,

    [string]$OutputDir,

    [Parameter(Mandatory = $true)]
    [string]$Package,

    [string]$DeviceSerial,

    [int]$ProcessId,

    [switch]$Launch,

    [ValidateRange(0, 120)]
    [int]$WaitSeconds = 5,

    [ValidateRange(10, 1800)]
    [int]$DumpTimeoutSeconds = 180,

    [string]$DumperPath = 'D:\reverse_ENV\tools\panda-dex-dumper\panda-dex-dumper',

    [switch]$KeepDeviceArtifacts,

    [switch]$AllowExternalOutputDir,

    [switch]$CleanOutput
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$adb = 'D:\reverse_ENV\tools\adb\adb.exe'
$workspaceRoot = 'D:\reverse_ENV\workspace'
$resolvedSerial = $null
$remoteTool = $null
$remoteOutput = $null
$launchedByScript = $false
$localDexValidated = $false
$remoteDumpCompleted = $false

function Test-PathWithin {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Root
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    return $fullPath.Equals($fullRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        $fullPath.StartsWith($fullRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)
}

function Resolve-AdbSerial {
    param([string]$RequestedSerial)

    $lines = & $adb devices 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "adb devices failed: $($lines -join "`n")"
    }

    $devices = @()
    foreach ($line in $lines) {
        if ($line -match '^\s*(\S+)\s+device\s*$') {
            $devices += $Matches[1]
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($RequestedSerial)) {
        if ($devices -notcontains $RequestedSerial) {
            throw "ADB device '$RequestedSerial' is not connected. Connected serials: $($devices -join ', ')"
        }
        return $RequestedSerial
    }

    if ($devices.Count -ne 1) {
        throw "Pass -DeviceSerial; connected device count is $($devices.Count). Connected serials: $($devices -join ', ')"
    }
    return $devices[0]
}

function Invoke-Adb {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$AdbArgs)

    # adb/monkey writes informational lines to stderr. Keep native exit codes as
    # the success gate instead of promoting every stderr line to a terminating
    # PowerShell ErrorRecord.
    $ErrorActionPreference = 'Continue'
    & $adb -s $resolvedSerial @AdbArgs
}

function Get-U32 {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$Offset
    )

    if ($Bytes.Length -lt ($Offset + 4)) {
        return $null
    }
    return [BitConverter]::ToUInt32($Bytes, $Offset)
}

function Get-U16 {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$Offset
    )

    if ($Bytes.Length -lt ($Offset + 2)) {
        return $null
    }
    return [BitConverter]::ToUInt16($Bytes, $Offset)
}

function Write-Utf8Lf {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )

    $normalized = $Content -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText($Path, $normalized, [System.Text.UTF8Encoding]::new($false))
}

function Invoke-PandaWithTimeout {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds,
        [Parameter(Mandatory = $true)][string]$LogRoot
    )

    $stdoutPath = Join-Path $LogRoot 'panda.stdout.log'
    $stderrPath = Join-Path $LogRoot 'panda.stderr.log'
    $arguments = @('-s', $resolvedSerial, 'shell', 'su', '-c', ('"' + $Command + '"'))
    $process = Start-Process -FilePath $adb -ArgumentList $arguments -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try { $process.Kill() } catch {}
        & $adb -s $resolvedSerial shell su -c "pkill -f $remoteTool" 2>$null | Out-Null
        throw "panda-dex-dumper exceeded timeout (${TimeoutSeconds}s). Device output was kept at: $remoteOutput"
    }

    $process.Refresh()
    if (Test-Path -LiteralPath $stdoutPath) {
        Get-Content -LiteralPath $stdoutPath -Encoding UTF8 | Out-Host
    }
    if (Test-Path -LiteralPath $stderrPath) {
        Get-Content -LiteralPath $stderrPath -Encoding UTF8 | Out-Host
    }
    return $process.ExitCode
}

if (-not (Test-Path -LiteralPath $adb)) {
    throw "adb not found: $adb"
}
if (-not (Test-Path -LiteralPath $DumperPath)) {
    throw "panda-dex-dumper not found: $DumperPath"
}
if ($Package -notmatch '^[A-Za-z0-9_][A-Za-z0-9_.]*$') {
    throw "Invalid Android package name: $Package"
}
if ([string]::IsNullOrWhiteSpace($Project) -eq [string]::IsNullOrWhiteSpace($OutputDir)) {
    throw 'Provide exactly one of -Project or -OutputDir.'
}

$workspaceFull = [System.IO.Path]::GetFullPath($workspaceRoot).TrimEnd('\')
if (-not [string]::IsNullOrWhiteSpace($Project)) {
    if ($Project -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$' -or $Project -in @('.', '..')) {
        throw 'Project must use only ASCII letters, digits, dot, underscore, or hyphen.'
    }
    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $OutputDir = Join-Path (Join-Path (Join-Path $workspaceRoot $Project) 'artifacts\dex-dump') $timestamp
}

$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
if (-not $AllowExternalOutputDir -and -not (Test-PathWithin -Path $OutputDir -Root $workspaceFull)) {
    throw "OutputDir must stay under $workspaceFull. Pass -AllowExternalOutputDir only for isolated tests."
}
if (-not (Test-Path -LiteralPath $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}
$OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path
$rawDir = Join-Path $OutputDir 'dex'
if (Test-Path -LiteralPath $rawDir) {
    $oldItems = @(Get-ChildItem -LiteralPath $rawDir -Force -ErrorAction SilentlyContinue)
    if ($oldItems.Count -gt 0) {
        if (-not $CleanOutput) {
            throw "Output contains previous DEX artifacts: $rawDir. Choose a new directory or pass -CleanOutput."
        }
        if (-not (Test-PathWithin -Path $rawDir -Root $OutputDir)) {
            throw "Refusing to clean path outside output directory: $rawDir"
        }
        Remove-Item -LiteralPath $rawDir -Recurse -Force
    }
}
New-Item -ItemType Directory -Path $rawDir -Force | Out-Null

$dumperBytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $DumperPath).Path)
if ($dumperBytes.Length -lt 20 -or $dumperBytes[0] -ne 0x7F -or $dumperBytes[1] -ne 0x45 -or
    $dumperBytes[2] -ne 0x4C -or $dumperBytes[3] -ne 0x46) {
    throw "Dumper is not an ELF binary: $DumperPath"
}
$dumperMachineId = Get-U16 -Bytes $dumperBytes -Offset 18
$dumperMachine = switch ($dumperMachineId) {
    183 { 'AArch64' }
    62 { 'x86_64' }
    40 { 'ARM' }
    3 { 'x86' }
    default { "ELF-machine-$dumperMachineId" }
}

try {
    $resolvedSerial = Resolve-AdbSerial -RequestedSerial $DeviceSerial
    $rootCheck = Invoke-Adb shell su -c id 2>&1
    if ($LASTEXITCODE -ne 0 -or ($rootCheck -join "`n") -notmatch 'uid=0') {
        throw "Root is required for /proc/<pid>/mem access. Device output: $($rootCheck -join ' ')"
    }

    $primaryAbi = (Invoke-Adb shell getprop ro.product.cpu.abi 2>&1 | Select-Object -First 1).Trim()
    $abiList = (Invoke-Adb shell getprop ro.product.cpu.abilist 2>&1 | Select-Object -First 1).Trim()
    $nativeBridge = (Invoke-Adb shell getprop ro.dalvik.vm.native.bridge 2>&1 | Select-Object -First 1).Trim()

    if ($dumperMachine -eq 'AArch64') {
        $hasArm64Abi = ($abiList -split ',') -contains 'arm64-v8a' -or $primaryAbi -eq 'arm64-v8a'
        $hasNativeBridge = -not [string]::IsNullOrWhiteSpace($nativeBridge) -and $nativeBridge -notin @('0', 'null')
        if (-not $hasArm64Abi -and -not $hasNativeBridge) {
            throw "AArch64 panda binary cannot run on device primaryAbi=$primaryAbi abiList=$abiList nativeBridge=$nativeBridge"
        }
    }

    if ($Launch) {
        Invoke-Adb shell monkey -p $Package -c android.intent.category.LAUNCHER 1 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to launch package: $Package"
        }
        $launchedByScript = $true
        if ($WaitSeconds -gt 0) {
            Start-Sleep -Seconds $WaitSeconds
        }
    }

    if ($ProcessId -le 0) {
        $pidText = (Invoke-Adb shell pidof $Package 2>&1 | Out-String).Trim()
        if ([string]::IsNullOrWhiteSpace($pidText)) {
            throw "Target process is not running: $Package. Start it or pass -Launch."
        }
        $pids = @($pidText -split '\s+' | Where-Object { $_ -match '^\d+$' })
        if ($pids.Count -ne 1) {
            throw "Package has multiple processes ($($pids -join ', ')); pass the intended -ProcessId explicitly."
        }
        $ProcessId = [int]$pids[0]
    }

    $cmdlineRaw = (Invoke-Adb shell su -c "cat /proc/$ProcessId/cmdline" 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($cmdlineRaw)) {
        throw "Cannot read /proc/$ProcessId/cmdline; verify the PID is alive and root is working."
    }
    $processCmdline = ($cmdlineRaw -replace "`0", ' ').Trim()
    $processName = ($processCmdline -split '\s+')[0]
    if ($processName -ne $Package -and -not $processName.StartsWith($Package + ':', [System.StringComparison]::Ordinal)) {
        throw "PID $ProcessId belongs to '$processName', not package '$Package'."
    }

    $remoteTool = "/data/local/tmp/panda-dex-dumper-$ProcessId"
    $remoteOutput = "/data/local/tmp/panda-dex-$ProcessId-$(Get-Date -Format 'yyyyMMddHHmmss')"

    Invoke-Adb push $DumperPath $remoteTool 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to push panda-dex-dumper.'
    }
    Invoke-Adb shell chmod 755 $remoteTool 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to chmod panda-dex-dumper.'
    }

    Write-Host "Running panda-dex-dumper: package=$Package pid=$ProcessId device=$resolvedSerial timeout=${DumpTimeoutSeconds}s"
    $dumperExitCode = Invoke-PandaWithTimeout -Command "$remoteTool -p $ProcessId -o $remoteOutput" `
        -TimeoutSeconds $DumpTimeoutSeconds -LogRoot $OutputDir
    $remoteDumpCompleted = $dumperExitCode -eq 0

    $pullOutput = Invoke-Adb pull "$remoteOutput/." $rawDir 2>&1
    $pullExitCode = $LASTEXITCODE
    $pullOutput | Out-Host

    $dexFiles = @(Get-ChildItem -LiteralPath $rawDir -Recurse -File -Filter '*.dex' | Sort-Object FullName)
    $fileMetadata = @()
    $hashOwners = @{}
    $validCount = 0
    foreach ($file in $dexFiles) {
        $bytes = [System.IO.File]::ReadAllBytes($file.FullName)
        $magicValid = $bytes.Length -ge 8 -and
            $bytes[0] -eq 0x64 -and $bytes[1] -eq 0x65 -and $bytes[2] -eq 0x78 -and $bytes[3] -eq 0x0A -and
            $bytes[4] -eq 0x30 -and $bytes[5] -ge 0x30 -and $bytes[5] -le 0x39 -and
            $bytes[6] -ge 0x30 -and $bytes[6] -le 0x39 -and $bytes[7] -eq 0x00
        $headerFileSize = Get-U32 -Bytes $bytes -Offset 0x20
        $headerSize = Get-U32 -Bytes $bytes -Offset 0x24
        $stringIds = Get-U32 -Bytes $bytes -Offset 0x38
        $methodIds = Get-U32 -Bytes $bytes -Offset 0x58
        $classDefs = Get-U32 -Bytes $bytes -Offset 0x60
        $sizeMatches = $null -ne $headerFileSize -and [uint64]$headerFileSize -eq [uint64]$file.Length
        $structureValid = $magicValid -and $headerSize -eq 0x70 -and $sizeMatches -and $classDefs -gt 0
        if ($structureValid) { $validCount++ }

        $sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash
        $relativeFile = $file.FullName.Substring($OutputDir.Length).TrimStart('\')
        $duplicateOf = $null
        if ($hashOwners.ContainsKey($sha256)) {
            $duplicateOf = $hashOwners[$sha256]
        }
        else {
            $hashOwners[$sha256] = $relativeFile
        }

        $invalidReasons = @()
        if (-not $magicValid) { $invalidReasons += 'invalid-dex-magic' }
        if ($headerSize -ne 0x70) { $invalidReasons += 'header-size-not-0x70' }
        if (-not $sizeMatches) { $invalidReasons += 'file-size-header-mismatch' }
        if ($classDefs -le 0) { $invalidReasons += 'no-class-defs' }

        $fileMetadata += [ordered]@{
            file = $relativeFile
            size = $file.Length
            sha256 = $sha256
            duplicate_of = $duplicateOf
            dex_magic = $magicValid
            header_file_size = $headerFileSize
            header_size = $headerSize
            size_matches_header = $sizeMatches
            string_ids = $stringIds
            method_ids = $methodIds
            class_defs = $classDefs
            structure_valid = $structureValid
            invalid_reasons = $invalidReasons
        }
    }

    $localDexValidated = $validCount -gt 0
    $status = if ($dexFiles.Count -eq 0) {
        'no-dex'
    }
    elseif (-not $localDexValidated) {
        'invalid'
    }
    elseif ($validCount -lt $dexFiles.Count -or $dumperExitCode -ne 0 -or $pullExitCode -ne 0) {
        'partial'
    }
    else {
        'complete-enough'
    }
    $totalBytes = if ($dexFiles.Count -gt 0) { [uint64](($dexFiles | Measure-Object Length -Sum).Sum) } else { [uint64]0 }

    $metadata = [ordered]@{
        generated_at = [DateTimeOffset]::Now.ToString('o')
        status = $status
        package = $Package
        pid = $ProcessId
        process_cmdline = $processCmdline
        device = $resolvedSerial
        device_primary_abi = $primaryAbi
        device_abi_list = $abiList
        native_bridge = $nativeBridge
        dumper_path = (Resolve-Path -LiteralPath $DumperPath).Path
        dumper_machine = $dumperMachine
        dumper_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $DumperPath).Hash
        dumper_exit_code = $dumperExitCode
        pull_exit_code = $pullExitCode
        output_dir = $OutputDir
        dex_count = $dexFiles.Count
        valid_dex_count = $validCount
        unique_sha256_count = $hashOwners.Count
        total_bytes = $totalBytes
        files = $fileMetadata
        limitation = 'complete-enough means locally well-formed whole DEX, not complete unpacking. Method extraction, CDEX, VMP, Dex2C, anti-dump, and lazy loading require separate validation.'
    }

    $metadataPath = Join-Path $OutputDir 'metadata.json'
    Write-Utf8Lf -Path $metadataPath -Content (($metadata | ConvertTo-Json -Depth 8) + "`n")

    "output_dir=$OutputDir"
    "metadata=$metadataPath"
    "status=$status"
    "device=$resolvedSerial"
    "pid=$ProcessId"
    "dex_count=$($dexFiles.Count)"
    "valid_dex_count=$validCount"
    "total_bytes=$totalBytes"

    if ($dumperExitCode -ne 0) {
        throw "panda-dex-dumper failed with exit code $dumperExitCode; local artifacts and device evidence were retained."
    }
    if ($pullExitCode -ne 0) {
        throw 'Failed to pull dumped DEX files; device evidence was retained.'
    }
    if (-not $localDexValidated) {
        throw 'No structurally valid DEX was dumped. Check load timing, PID, protector type, CDEX/VMP/Dex2C, and anti-dump behavior.'
    }
}
finally {
    # panda-dex-dumper sends SIGSTOP before scanning. Its own panic path may
    # skip SIGCONT, so always resume the target best-effort from the wrapper.
    if (-not [string]::IsNullOrWhiteSpace($resolvedSerial) -and $ProcessId -gt 0) {
        & $adb -s $resolvedSerial shell su -c "kill -CONT $ProcessId" 2>$null | Out-Null
    }

    if (-not $KeepDeviceArtifacts -and -not [string]::IsNullOrWhiteSpace($resolvedSerial)) {
        if ($localDexValidated -and $remoteDumpCompleted -and -not [string]::IsNullOrWhiteSpace($remoteOutput) -and
            $remoteOutput -like '/data/local/tmp/panda-dex-*') {
            & $adb -s $resolvedSerial shell su -c "rm -rf $remoteOutput" 2>$null | Out-Null
        }
        if (-not [string]::IsNullOrWhiteSpace($remoteTool) -and $remoteTool -like '/data/local/tmp/panda-dex-dumper-*') {
            & $adb -s $resolvedSerial shell su -c "rm -f $remoteTool" 2>$null | Out-Null
        }
    }

    if ((-not $localDexValidated -or -not $remoteDumpCompleted) -and -not [string]::IsNullOrWhiteSpace($remoteOutput)) {
        Write-Warning "DEX validation did not complete cleanly; device evidence was kept at: $remoteOutput"
    }

    if ($launchedByScript) {
        Write-Verbose "Package was launched by this script and left running for follow-up analysis: $Package"
    }
}
