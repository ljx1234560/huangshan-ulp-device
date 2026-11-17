param([string]$Compiler = 'gcc')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root 'test-results/ai-mailbox'
New-Item -ItemType Directory -Force $out | Out-Null
Push-Location $root
try {
    $flags = @('-std=c99', '-Wall', '-Wextra', '-Werror', '-Itests/ai-chat-host/stubs',
               '-Isrc/app', '-Isrc/services', '-Isrc/ui', 'src/services/velapet_ai_chat.c',
               'src/ui/ui_ai_bridge.c', 'tests/ai-chat-host/test_ai_mailbox.c')
    foreach ($mode in @('formal', 'mock')) {
        $exe = Join-Path $out "ai-mailbox-$mode.exe"
        $defs = @()
        if ($mode -eq 'mock') { $defs += '-DVELAPET_UI_AI_MOCK' }
        & $Compiler @flags @defs -o $exe
        if ($LASTEXITCODE -ne 0) { throw "Compiler failed in $mode mode." }
        & $exe
        if ($LASTEXITCODE -ne 0) { throw "Mailbox test failed in $mode mode." }
        Write-Host "AI_MAILBOX $mode PASS"
    }
} finally { Pop-Location }
