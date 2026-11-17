param(
    [switch]$Help,
    [switch]$ModelsOnly,
    [switch]$ImageOnly,
    [string]$DeepSeekModel = 'deepseek-flash',
    [string]$SeedreamModel = 'doubao-seedream-5-0-pro-260628'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$seedreamIdPattern = '^(doubao-seedream-[a-z0-9-]+-[0-9]{6}|ep-[a-zA-Z0-9_-]+)$'

if ($Help) {
    Write-Host 'Run .\scripts\configure-ai.ps1 from PowerShell.'
    Write-Host 'Prompts for hidden API keys and model IDs; saves only host/ai-backend/.env.'
    Write-Host 'Empty input preserves the current value. No API request is sent.'
    Write-Host 'Use -ModelsOnly to repair model IDs without prompting for or changing API keys.'
    Write-Host 'Use -ImageOnly to update only ARK_API_KEY and ARK_IMAGE_MODEL.'
    exit 0
}

if ($ModelsOnly -and $ImageOnly) { throw 'Use either -ModelsOnly or -ImageOnly.' }

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
    Assert-ModelId 'ARK_IMAGE_MODEL' $SeedreamModel $seedreamIdPattern
    Set-LocalValue 'DEEPSEEK_CHAT_MODEL' $DeepSeekModel
    Set-LocalValue 'ARK_IMAGE_MODEL' $SeedreamModel
    [IO.File]::WriteAllLines($envPath, $lines, [Text.UTF8Encoding]::new($false))
    Write-Host 'Model IDs updated. API keys preserved. No API request was sent.'
    exit 0
}

Write-Host 'VelaPet local AI configuration. No paid calls will be made.'
Write-Host 'Keys are hidden; Enter preserves existing values.'
if (-not $ImageOnly) {
    Read-LocalSecret 'DEEPSEEK_API_KEY'
    $model = Read-Host 'DEEPSEEK_CHAT_MODEL (use your account model ID; Enter keeps existing)'
    if (-not [string]::IsNullOrWhiteSpace($model)) {
        Assert-ModelId 'DEEPSEEK_CHAT_MODEL' $model.Trim() '^deepseek-[a-zA-Z0-9._-]+$'
        Set-LocalValue 'DEEPSEEK_CHAT_MODEL' $model.Trim()
    }
}
Read-LocalSecret 'ARK_API_KEY'
$model = Read-Host 'ARK_IMAGE_MODEL (copy the full model ID from the API example; Enter keeps existing)'
if (-not [string]::IsNullOrWhiteSpace($model)) {
    Assert-ModelId 'ARK_IMAGE_MODEL' $model.Trim() $seedreamIdPattern
    Set-LocalValue 'ARK_IMAGE_MODEL' $model.Trim()
}
if (-not $ImageOnly) {
    Set-LocalValue 'VELAPET_CHAT_PROVIDER' 'deepseek'
    $imageMode = Read-Host 'Image provider: demo (no paid generation) or seedream (paid); Enter keeps existing'
    if (-not [string]::IsNullOrWhiteSpace($imageMode)) {
        $imageMode = $imageMode.Trim().ToLowerInvariant()
        if ($imageMode -notin @('demo', 'seedream')) { throw 'Image provider must be demo or seedream; file was not changed.' }
        Set-LocalValue 'VELAPET_IMAGE_PROVIDER' $imageMode
    }
}
[IO.File]::WriteAllLines($envPath, $lines, [Text.UTF8Encoding]::new($false))
Write-Host "Saved to $envPath"
Write-Host 'Keys were not printed. Restart the backend to load changes.'
if ($ImageOnly) {
    Write-Host 'Only the Ark key and model ID were prompted. No API request was sent.'
} else {
    Write-Host 'Do not share this file. Tell the developer when ready and specify your test-call budget.'
}
