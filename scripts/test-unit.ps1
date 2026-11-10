param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$outputDir = 'test-results\unit'

# 平台无关业务代码在主机上即可验证，无需烧录开发板。
# 注意：全部使用相对路径，gcc 在 Windows 下处理含中文的绝对路径会失败。
$testNames = @('velapet_core_test', 'velapet_service_test')
$sources = @('src/app/velapet_core.c', 'src/app/velapet_service.c')

New-Item -ItemType Directory -Path (Join-Path $repoRoot $outputDir) -Force | Out-Null

function ConvertTo-WslPath([string]$Path) {
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if ($fullPath -notmatch '^([A-Za-z]):\\(.*)$') {
        throw "Cannot map path to WSL: $fullPath"
    }

    $drive = $Matches[1].ToLowerInvariant()
    $tail = $Matches[2].Replace('\', '/')
    return "/mnt/$drive/$tail"
}

function Invoke-NativeTests {
    Push-Location $repoRoot
    try {
        foreach ($name in $testNames) {
            $testExe = Join-Path $outputDir "$name.exe"
            & gcc `
                -std=c11 `
                -Wall `
                -Wextra `
                -Werror `
                -pedantic `
                -Isrc/app `
                "tests/unit/$name.c" `
                @sources `
                -o $testExe

            if ($LASTEXITCODE -ne 0) {
                throw "Native unit-test compilation failed for $name (exit code $LASTEXITCODE)."
            }

            & (Join-Path '.' $testExe)
            if ($LASTEXITCODE -ne 0) {
                throw "Native unit tests failed for $name (exit code $LASTEXITCODE)."
            }
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-WslTests {
    $wslRoot = ConvertTo-WslPath $repoRoot
    $wslSources = $sources | ForEach-Object { "$wslRoot/$_" }

    foreach ($name in $testNames) {
        $wslTest = "$wslRoot/test-results/unit/$name"

        & wsl.exe -e gcc `
            -std=c11 `
            -Wall `
            -Wextra `
            -Werror `
            -pedantic `
            "-I$wslRoot/src/app" `
            "$wslRoot/tests/unit/$name.c" `
            @wslSources `
            -o $wslTest

        if ($LASTEXITCODE -ne 0) {
            throw "WSL unit-test compilation failed for $name (exit code $LASTEXITCODE)."
        }

        & wsl.exe -e $wslTest
        if ($LASTEXITCODE -ne 0) {
            throw "WSL unit tests failed for $name (exit code $LASTEXITCODE)."
        }
    }
}

$compiler = Get-Command gcc -ErrorAction SilentlyContinue
if ($null -ne $compiler) {
    try {
        Invoke-NativeTests
        return
    }
    catch {
        Write-Warning "Native GCC path failed; falling back to WSL GCC. $($_.Exception.Message)"
    }
}

Invoke-WslTests
