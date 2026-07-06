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

    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Get-ToolPath {
    param([Parameter(Mandatory = $true)][string]$Name)

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $fallbacks = @{
        'apktool' = @(
            'D:\reverse_ENV\tools\apktool\apktool.bat'
        )
        'zipalign' = @(
            'D:\reverse_ENV\tools\adb\zipalign.exe'
        )
        'apksigner' = @(
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

    & $Keytool -genkeypair -v -keystore $Path -storepass $StorePassword -keypass $KeyPassword -alias $Alias -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=Android Debug,O=OpenCode,C=CN'
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to generate debug keystore.'
    }
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

if ([string]::IsNullOrWhiteSpace($KeystorePath)) {
    $KeystorePath = Get-DefaultKeystorePath -ResolvedProjectDir $ProjectDir -ResolvedOutDir $OutDir
}

Ensure-DebugKeystore -Path $KeystorePath -Keytool $keytool -Alias $KeyAlias -StorePassword $StorePass -KeyPassword $KeyPass

$name = if ($BaseName) { $BaseName } else { Split-Path -Path $ProjectDir -Leaf }
$unsignedApk = Join-Path $OutDir ($name + '-unsigned.apk')
$alignedApk = Join-Path $OutDir ($name + '-aligned.apk')
$signedApk = Join-Path $OutDir ($name + '-signed.apk')

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

& $zipalign -f -p 4 $unsignedApk $alignedApk
if ($LASTEXITCODE -ne 0) {
    throw 'zipalign failed.'
}

Copy-Item -LiteralPath $alignedApk -Destination $signedApk -Force
& $apksigner sign --ks $KeystorePath --ks-key-alias $KeyAlias --ks-pass "pass:$StorePass" --key-pass "pass:$KeyPass" --out $signedApk $alignedApk
if ($LASTEXITCODE -ne 0) {
    throw 'apksigner sign failed.'
}

& $apksigner verify --print-certs $signedApk
if ($LASTEXITCODE -ne 0) {
    throw 'apksigner verify failed.'
}

"unsigned_apk=$unsignedApk"
"aligned_apk=$alignedApk"
"signed_apk=$signedApk"
"keystore=debug-only; path omitted"

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
