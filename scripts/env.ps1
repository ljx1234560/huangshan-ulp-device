Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$localEnvironment = Join-Path $repoRoot '.env.local.ps1'

if (Test-Path -LiteralPath $localEnvironment) {
    . $localEnvironment
}

if ($env:SIFLI_BOOTSTRAP_PYTHON) {
    if (-not (Test-Path -LiteralPath $env:SIFLI_BOOTSTRAP_PYTHON)) {
        throw "Bootstrap Python not found: $env:SIFLI_BOOTSTRAP_PYTHON"
    }
    $pythonDirectory = Split-Path -Parent $env:SIFLI_BOOTSTRAP_PYTHON
    $pathEntries = @($env:Path -split ';')
    if (-not ($pathEntries -contains $pythonDirectory)) {
        $env:Path = "$pythonDirectory;$env:Path"
    }
}

$sdkRoot = $env:SIFLI_SDK_ROOT
if (-not $sdkRoot) {
    $sdkRoot = $env:SIFLI_SDK_PATH
}
if (-not $sdkRoot) {
    throw 'SIFLI_SDK_ROOT is not configured. Copy .env.example.ps1 to .env.local.ps1.'
}
if (-not (Test-Path -LiteralPath $sdkRoot -PathType Container)) {
    throw "SiFli-SDK directory not found: $sdkRoot"
}
if (-not $env:SIFLI_SDK_TOOLS_PATH) {
    throw 'SIFLI_SDK_TOOLS_PATH is not configured.'
}

$exportScript = Join-Path $sdkRoot 'export.ps1'
if (-not (Test-Path -LiteralPath $exportScript -PathType Leaf)) {
    throw "SiFli SDK export script not found: $exportScript"
}

Push-Location -LiteralPath $sdkRoot
try {
    . $exportScript
}
finally {
    Pop-Location
}

if (-not $env:SIFLI_SDK) {
    throw 'SiFli-SDK environment activation did not set SIFLI_SDK.'
}

$env:HUANGSHAN_REPO_ROOT = $repoRoot

