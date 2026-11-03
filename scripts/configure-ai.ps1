param(
    [switch]$Help,
    [switch]$ModelsOnly,
    [string]$DeepSeekModel = 'deepseek-flash',
    [string]$SeedreamModel = 'doubao-seedream-5-0-pro-260628'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Help) {
    Write-Host 'Run .\scripts\configure-ai.ps1 from PowerShell.'
    Write-Host 'Prompts for hidden API keys and model IDs; saves only host/ai-backend/.env.'
    Write-Host 'Empty input preserves the current value. No API request is sent.'
    Write-Host 'Use -ModelsOnly to repair model IDs without prompting for or changing API keys.'
    exit 0
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot 'host/ai-backend/.env'
$examplePath = Join-Path $repoRoot 'host/ai-backend/.env.example'
$lines = [System.Collections.Generic.List[string]]::new()
$source = if (Test-Path -LiteralPath $envPath) { $envPath } else { $examplePath }
foreach ($line in [IO.File]::ReadAllLines($source)) { $lines.Add($line) }

function Set-LocalValue([string]$Name, [string]$Value) {
    if ($Value.Contains("`n") -or $Value.Contains("`r")) { throw 'Values must be a single line.' }
    # Dotenv single-quoted values protect special characters and whitespace.
    $escaped = $Value.Replace('\', '\\').Replace("'", "\'")
    $replacement = $Name + "='" + $escaped + "'"
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].StartsWith($Name + '=')) {
            $lines[$i] = $replacement
            return
        }
    }
    $lines.Add($replacement)
}

function Read-LocalSecret([string]$Name) {
    $secure = Read-Host "$Name (hidden; Enter keeps existing)" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        if (-not [string]::IsNullOrWhiteSpace($value)) { Set-LocalValue $Name $value.Trim() }
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        $secure.Dispose()
        $value = $null
    }
}

function Assert-ModelId([string]$Name, [string]$Value, [string]$Pattern) {
    if ($Value -notmatch $Pattern) {
        # Never echo an invalid value: it may be a mistakenly pasted credential.
        throw "$Name must be a model ID, not an API key. File was not changed."
    }
}

if ($ModelsOnly) {
    Assert-ModelId 'DEEPSEEK_CHAT_MODEL' $DeepSeekModel '^deepseek-[a-zA-Z0-9._-]+$'
    Assert-ModelId 'SEEDREAM_MODEL' $SeedreamModel '^(doubao-seedream-[a-zA-Z0-9._-]+|ep-[a-zA-Z0-9_-]+)$'
    Set-LocalValue 'DEEPSEEK_CHAT_MODEL' $DeepSeekModel
    Set-LocalValue 'SEEDREAM_MODEL' $SeedreamModel
    [IO.File]::WriteAllLines($envPath, $lines, [Text.UTF8Encoding]::new($false))
    Write-Host 'Model IDs updated. API keys preserved. No API request was sent.'
    exit 0
}

Write-Host 'VelaPet local AI configuration. No paid calls will be made.'
Write-Host 'Keys are hidden; Enter preserves existing values.'
Read-LocalSecret 'DEEPSEEK_API_KEY'
$model = Read-Host 'DEEPSEEK_CHAT_MODEL (use your account model ID; Enter keeps existing)'
if (-not [string]::IsNullOrWhiteSpace($model)) {
    Assert-ModelId 'DEEPSEEK_CHAT_MODEL' $model.Trim() '^deepseek-[a-zA-Z0-9._-]+$'
    Set-LocalValue 'DEEPSEEK_CHAT_MODEL' $model.Trim()
}
Read-LocalSecret 'ARK_API_KEY'
$model = Read-Host 'SEEDREAM_MODEL (use Ark console model ID; Enter keeps existing)'
if (-not [string]::IsNullOrWhiteSpace($model)) {
    Assert-ModelId 'SEEDREAM_MODEL' $model.Trim() '^(doubao-seedream-[a-zA-Z0-9._-]+|ep-[a-zA-Z0-9_-]+)$'
    Set-LocalValue 'SEEDREAM_MODEL' $model.Trim()
}
Set-LocalValue 'VELAPET_CHAT_PROVIDER' 'deepseek'
$imageMode = Read-Host 'Image provider: demo (no paid generation) or seedream (paid); Enter keeps existing'
if (-not [string]::IsNullOrWhiteSpace($imageMode)) {
    $imageMode = $imageMode.Trim().ToLowerInvariant()
    if ($imageMode -notin @('demo', 'seedream')) { throw 'Image provider must be demo or seedream; file was not changed.' }
    Set-LocalValue 'VELAPET_IMAGE_PROVIDER' $imageMode
}
[IO.File]::WriteAllLines($envPath, $lines, [Text.UTF8Encoding]::new($false))
Write-Host "Saved to $envPath"
Write-Host 'Keys were not printed. Restart the backend to load changes.'
Write-Host 'Do not share this file. Tell the developer when ready and specify your test-call budget.'
