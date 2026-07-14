#requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectDir,

    [string]$OutDir,

    [string]$BaseName,

    [string]$KeystorePath,

    [string]$KeyAlias = 'androiddebugkey',

    [string]$StorePass = 'android',

    [string]$KeyPass = 'android',

    [string]$DeviceSerial,

    [switch]$Install,

    [switch]$Reinstall,

    [switch]$Clean,

    [switch]$FailOn16KbRisk
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Get-ToolPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    $fallbacks = @{
        'apktool' = @(
            'D:\reverse_ENV\tools\apktool\apktool.bat'
        )
        'zipalign' = @(
            'D:\reverse_ENV\tools\android-sdk\build-tools\35.0.0\zipalign.exe',
            'D:\reverse_ENV\tools\adb\zipalign.exe'
        )
        'apksigner' = @(
            'D:\reverse_ENV\tools\android-sdk\build-tools\35.0.0\apksigner.bat',
            'D:\reverse_ENV\tools\adb\apksigner.bat'
        )
        'keytool' = @(
            'D:\reverse_ENV\tools\jdk\bin\keytool.exe'
        )
        'adb' = @(
            'D:\reverse_ENV\tools\adb\adb.exe'
        )
    }

    if ($fallbacks.Contains($Name)) {
        foreach ($candidate in $fallbacks[$Name]) {
            if (Test-Path -LiteralPath $candidate) {
                return $candidate
            }
        }
    }

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    throw "Missing required CLI tool: $Name"
}

function Ensure-DebugKeystore {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Keytool,
        [Parameter(Mandatory = $true)][string]$Alias,
        [Parameter(Mandatory = $true)][string]$StorePassword,
        [Parameter(Mandatory = $true)][string]$KeyPassword
    )

    if (Test-Path -LiteralPath $Path) {
        return
    }

    $parent = Split-Path -Path $Path -Parent
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    try {
        $env:APK_REVERSE_STORE_PASS = $StorePassword
        $env:APK_REVERSE_KEY_PASS = $KeyPassword
        & $Keytool -genkeypair -v -keystore $Path -storepass:env APK_REVERSE_STORE_PASS -keypass:env APK_REVERSE_KEY_PASS -alias $Alias -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=Android Debug,O=OpenCode,C=CN'
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to generate debug keystore.'
        }
    }
    finally {
        Remove-Item Env:APK_REVERSE_STORE_PASS -ErrorAction SilentlyContinue
        Remove-Item Env:APK_REVERSE_KEY_PASS -ErrorAction SilentlyContinue
    }
}

function Assert-ChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullParent = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\')
    if (-not $fullPath.StartsWith($fullParent + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Output path escapes OutDir: $fullPath"
    }
    return $fullPath
}

function Test-Elf16KbAlignment {
    param(
        [Parameter(Mandatory = $true)][string[]]$Libraries,
        [Parameter(Mandatory = $true)][string]$ReadElf
    )

    $risks = @()
    foreach ($library in $Libraries) {
        $programHeaders = & $ReadElf -lW $library 2>&1
        if ($LASTEXITCODE -ne 0) {
            $risks += [pscustomobject]@{ file = $library; reason = 'llvm-readelf-failed'; align = $null }
            continue
        }
        foreach ($line in $programHeaders) {
            if ($line -match '^\s*LOAD\s+' -and $line -match '(0x[0-9A-Fa-f]+)\s*$') {
                $align = [Convert]::ToUInt64($Matches[1].Substring(2), 16)
                if ($align -lt 0x4000) {
                    $risks += [pscustomobject]@{ file = $library; reason = 'PT_LOAD-align-below-0x4000'; align = ('0x{0:X}' -f $align) }
                    break
                }
            }
        }
    }
    return @($risks)
}

function Get-DefaultKeystorePath {
    param(
        [Parameter(Mandatory = $true)][string]$ResolvedProjectDir,
        [Parameter(Mandatory = $true)][string]$ResolvedOutDir
    )

    $workspaceRoot = 'D:\reverse_ENV\workspace'
    $workspaceFull = [System.IO.Path]::GetFullPath($workspaceRoot).TrimEnd('\')
    $projectFull = [System.IO.Path]::GetFullPath($ResolvedProjectDir)

    if ($projectFull.StartsWith($workspaceFull + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        $relative = $projectFull.Substring($workspaceFull.Length + 1)
        $projectName = $relative.Split([char]'\')[0]
        if (-not [string]::IsNullOrWhiteSpace($projectName)) {
            return (Join-Path (Join-Path $workspaceFull $projectName) 'debug.keystore')
        }
    }

    return (Join-Path $ResolvedOutDir 'debug.keystore')
}

function Get-AdbInstallSerial {
    param(
        [Parameter(Mandatory = $true)][string]$AdbPath,
        [string]$RequestedSerial
    )

    $lines = & $AdbPath devices 2>&1
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
        throw "Pass -DeviceSerial for install; connected device count is $($devices.Count). Connected serials: $($devices -join ', ')"
    }

    return $devices[0]
}

if (-not (Test-Path -LiteralPath $ProjectDir)) {
    throw "Project directory not found: $ProjectDir"
}

$ProjectDir = (Resolve-Path -LiteralPath $ProjectDir).Path

if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $projectParent = Split-Path -Path $ProjectDir -Parent
    if ([string]::IsNullOrWhiteSpace($projectParent)) {
        $projectParent = [System.IO.Directory]::GetCurrentDirectory()
    }
    $OutDir = $projectParent
}

if (-not (Test-Path -LiteralPath $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}
$OutDir = (Resolve-Path -LiteralPath $OutDir).Path

$apktool = Get-ToolPath -Name 'apktool'
$zipalign = Get-ToolPath -Name 'zipalign'
$apksigner = Get-ToolPath -Name 'apksigner'
$keytool = Get-ToolPath -Name 'keytool'
$adb = Get-ToolPath -Name 'adb'
$readelf = 'D:\reverse_ENV\tools\android-ndk\toolchains\llvm\prebuilt\windows-x86_64\bin\llvm-readelf.exe'

if ([string]::IsNullOrWhiteSpace($KeystorePath)) {
    $KeystorePath = Get-DefaultKeystorePath -ResolvedProjectDir $ProjectDir -ResolvedOutDir $OutDir
}

Ensure-DebugKeystore -Path $KeystorePath -Keytool $keytool -Alias $KeyAlias -StorePassword $StorePass -KeyPassword $KeyPass

$name = if ($BaseName) { $BaseName } else { Split-Path -Path $ProjectDir -Leaf }
if ($name -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$' -or $name -in @('.', '..')) {
    throw 'BaseName must use only ASCII letters, digits, dot, underscore, or hyphen and cannot be dot segments.'
}
$unsignedApk = Assert-ChildPath -Path (Join-Path $OutDir ($name + '-unsigned.apk')) -Parent $OutDir
$alignedApk = Assert-ChildPath -Path (Join-Path $OutDir ($name + '-aligned.apk')) -Parent $OutDir
$signedApk = Assert-ChildPath -Path (Join-Path $OutDir ($name + '-signed.apk')) -Parent $OutDir

if ($Clean) {
    foreach ($path in @($unsignedApk, $alignedApk, $signedApk)) {
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Force
        }
    }
}

& $apktool b $ProjectDir -o $unsignedApk
if ($LASTEXITCODE -ne 0) {
    throw 'apktool build failed.'
}

$nativeLibraries = @(Get-ChildItem -LiteralPath $ProjectDir -Recurse -File -Filter '*.so' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
$hasNativeLibraries = $nativeLibraries.Count -gt 0
$elfRisks = @()
if ($hasNativeLibraries) {
    $zipalignUsage = (& $zipalign 2>&1 | Out-String)
    if ($zipalignUsage -notmatch '-P\s+<pagesize_kb>') {
        throw "Selected zipalign does not support Android 15 16 KB alignment (-P 16): $zipalign"
    }
    if (Test-Path -LiteralPath $readelf) {
        $elfRisks = @(Test-Elf16KbAlignment -Libraries $nativeLibraries -ReadElf $readelf)
    }
    else {
        $elfRisks = @([pscustomobject]@{ file = '(all native libraries)'; reason = 'llvm-readelf-missing'; align = $null })
    }
    foreach ($risk in $elfRisks) {
        Write-Warning "Android 15 16 KB ELF risk: $($risk.file) reason=$($risk.reason) align=$($risk.align)"
    }
    if ($FailOn16KbRisk -and $elfRisks.Count -gt 0) {
        throw 'Native libraries are not verified for Android 15 16 KB page size.'
    }
}

if ($hasNativeLibraries) {
    & $zipalign -P 16 -f -v 4 $unsignedApk $alignedApk
}
else {
    & $zipalign -f -v 4 $unsignedApk $alignedApk
}
if ($LASTEXITCODE -ne 0) {
    throw 'zipalign failed.'
}

if ($hasNativeLibraries) {
    & $zipalign -c -P 16 -v 4 $alignedApk
}
else {
    & $zipalign -c -v 4 $alignedApk
}
if ($LASTEXITCODE -ne 0) {
    throw 'zipalign verification failed.'
}

try {
    $env:APK_REVERSE_STORE_PASS = $StorePass
    $env:APK_REVERSE_KEY_PASS = $KeyPass
    & $apksigner sign --ks $KeystorePath --ks-key-alias $KeyAlias --ks-pass env:APK_REVERSE_STORE_PASS --key-pass env:APK_REVERSE_KEY_PASS --out $signedApk $alignedApk
    if ($LASTEXITCODE -ne 0) {
        throw 'apksigner sign failed.'
    }
}
finally {
    Remove-Item Env:APK_REVERSE_STORE_PASS -ErrorAction SilentlyContinue
    Remove-Item Env:APK_REVERSE_KEY_PASS -ErrorAction SilentlyContinue
}

& $apksigner verify --print-certs $signedApk
if ($LASTEXITCODE -ne 0) {
    throw 'apksigner verify failed.'
}

"unsigned_apk=$unsignedApk"
"aligned_apk=$alignedApk"
"signed_apk=$signedApk"
"keystore=debug-only; path omitted"
"native_libraries=$($nativeLibraries.Count)"
"zipalign_page_size=$(if ($hasNativeLibraries) { '16KB' } else { 'standard' })"
"elf_16kb_risk_count=$($elfRisks.Count)"

if ($Install) {
    $resolvedDeviceSerial = Get-AdbInstallSerial -AdbPath $adb -RequestedSerial $DeviceSerial
    $installArgs = @('-s', $resolvedDeviceSerial)
    $installArgs += 'install'
    if ($Reinstall) {
        $installArgs += '-r'
    }
    $installArgs += $signedApk

    & $adb @installArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'adb install failed.'
    }

    "install_device=$resolvedDeviceSerial"
}
