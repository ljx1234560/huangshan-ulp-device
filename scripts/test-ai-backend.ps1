param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repoRoot 'host\ai-backend'
$venvRoot = Join-Path $repoRoot 'test-results\ai-backend-venv-host'
$pytestTemp = Join-Path $repoRoot 'test-results\pytest-ai-backend'
$python = Join-Path $venvRoot 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw "AI backend environment is missing. Create $venvRoot and install host/ai-backend/requirements-dev.txt."
}

$env:PYTHONDONTWRITEBYTECODE = '1'
Push-Location $backendRoot
try {
    & $python -m pytest -q -p no:cacheprovider --basetemp $pytestTemp tests
    if ($LASTEXITCODE -ne 0) {
        throw "AI backend tests failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
