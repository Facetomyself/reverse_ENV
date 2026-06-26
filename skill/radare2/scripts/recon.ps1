param(
    [Parameter(Mandatory = $true)]
    [string]$TargetPath,

    [int]$StringsLimit = 40,

    [int]$ImportsLimit = 80,

    [switch]$RunAnalysis
)

# 强制当前脚本使用 UTF-8 输出，尽量减少中文标题乱码。
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ErrorActionPreference = 'Stop'

$Radare2Bin = 'D:\reverse_ENV\tools\radare2\bin'

function Test-Tool {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    # 优先用本机安装的便携版路径
    $localPath = Join-Path $Radare2Bin "$Name.exe"
    if (Test-Path $localPath) {
        return $localPath
    }

    # fallback: PATH 中查找
    if (Get-Command -Name $Name -ErrorAction SilentlyContinue) {
        return $Name
    }

    throw "缺少命令：$Name（检查 $Radare2Bin）"
}

function Write-Section {
    param(
        [Parameter(Mandatory = $true)]
    [string]$Title
    )

    # 用固定分段标题，方便人看，也方便后续 grep。
    ""
    "=== $Title ==="
}

$rabin2Path = Test-Tool -Name 'rabin2'
$r2Path = if ($RunAnalysis) { Test-Tool -Name 'r2' } else { $null }

# 将输入路径规范化成绝对路径
$resolvedPath = Resolve-Path -LiteralPath $TargetPath
$target = $resolvedPath.Path

"目标文件: $target"

Write-Section -Title '基本信息'
& $rabin2Path -I -- "$target"

Write-Section -Title '节区'
& $rabin2Path -S -- "$target"

Write-Section -Title '导入'
& $rabin2Path -i -- "$target" | Select-Object -First $ImportsLimit

Write-Section -Title '导出'
& $rabin2Path -E -- "$target"

Write-Section -Title '字符串'
& $rabin2Path -zz -- "$target" | Select-Object -First $StringsLimit

if ($RunAnalysis) {
    Write-Section -Title '函数与入口分析'
    & $r2Path -A -q -c 's entry0;afl;iz;ii;q' -- "$target"
}
