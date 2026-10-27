param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$outputDir = Join-Path $repoRoot 'test-results\unit'
$testExe = Join-Path $outputDir 'velapet_core_test.exe'

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

function ConvertTo-WslPath([string]$Path) {
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if ($fullPath -notmatch '^([A-Za-z]):\\(.*)$') {
        throw "Cannot map path to WSL: $fullPath"
    }

    $drive = $Matches[1].ToLowerInvariant()
    $tail = $Matches[2].Replace('\', '/')
    return "/mnt/$drive/$tail"
}

$compiler = Get-Command gcc -ErrorAction SilentlyContinue
if ($null -ne $compiler) {
    try {
        & $compiler.Source `
            -std=c11 `
            -Wall `
            -Wextra `
            -Werror `
            -pedantic `
            "-I$(Join-Path $repoRoot 'src\app')" `
            (Join-Path $repoRoot 'tests\unit\velapet_core_test.c') `
            (Join-Path $repoRoot 'src\app\velapet_core.c') `
            -o $testExe

        if ($LASTEXITCODE -ne 0) {
            throw "Native unit-test compilation failed with exit code $LASTEXITCODE."
        }

        & $testExe
        if ($LASTEXITCODE -ne 0) {
            throw "Native unit tests failed with exit code $LASTEXITCODE."
        }
        return
    }
    catch [System.Management.Automation.ResourceUnavailableException] {
        Write-Warning "Native GCC could not start; falling back to WSL GCC. $($_.Exception.Message)"
    }
}

$wsl = Get-Command wsl.exe -ErrorAction Stop
$wslRoot = ConvertTo-WslPath $repoRoot
$wslTest = "$wslRoot/test-results/unit/velapet_core_test"

& $wsl.Source -e gcc `
    -std=c11 `
    -Wall `
    -Wextra `
    -Werror `
    -pedantic `
    "-I$wslRoot/src/app" `
    "$wslRoot/tests/unit/velapet_core_test.c" `
    "$wslRoot/src/app/velapet_core.c" `
    -o $wslTest

if ($LASTEXITCODE -ne 0) {
    throw "WSL unit-test compilation failed with exit code $LASTEXITCODE."
}

& $wsl.Source -e $wslTest
if ($LASTEXITCODE -ne 0) {
    throw "WSL unit tests failed with exit code $LASTEXITCODE."
}
