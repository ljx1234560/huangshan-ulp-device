<#
VelaPet Web 一键启动脚本

用法：
  .\start-web.cmd                  # Mock 模式，启动用户端 + 管理端
  .\start-web.cmd -Mode real       # 启动 SQLite 后端 + 用户端 + 管理端
  .\start-web.cmd -NoAdmin         # 只启动用户端
  .\start-web.cmd -NoBrowser       # 不自动打开浏览器
  .\start-web.cmd -Reinstall       # 强制重装前端/后端依赖

说明：
  - Mock 模式不需要后端，数据保存在浏览器 localStorage。
  - Real 模式使用 SQLite（server/velapet.db）并自动执行 Alembic 迁移。
  - 每次运行会生成 host/web/.env.local；已有文件会先备份。
#>

param(
    [ValidateSet('mock', 'real')]
    [string]$Mode = 'mock',
    [switch]$NoAdmin,
    [switch]$NoBrowser,
    [switch]$Reinstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$webRoot = $PSScriptRoot
$serverDir = Join-Path $webRoot 'server'
$apiBaseUrl = 'http://localhost:8000'
$userUrl = 'http://localhost:5173'
$adminUrl = 'http://localhost:5174'

function Write-Step([string]$Message) {
    Write-Host "[VelaPet] $Message" -ForegroundColor Cyan
}

function Fail([string]$Message) {
    Write-Host "[VelaPet] 错误：$Message" -ForegroundColor Red
    exit 1
}

function Find-PnpmCmd {
    $command = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    $candidate = Join-Path (Join-Path $env:APPDATA 'npm') 'pnpm.cmd'
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }
    $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($null -ne $npmCmd) {
        $prefix = (& $npmCmd.Source prefix -g 2>$null)
        if ($LASTEXITCODE -eq 0 -and $prefix) {
            $candidate = Join-Path $prefix.Trim() 'pnpm.cmd'
            if (Test-Path -LiteralPath $candidate) {
                return $candidate
            }
        }
    }
    return $null
}

function Test-Port([int]$Port, [string]$Target = '127.0.0.1') {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($Target, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(300)) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Wait-Port([int]$Port, [int]$Seconds, [string]$Label) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $Port) {
            return $true
        }
        Start-Sleep -Milliseconds 700
    }
    Write-Host "[VelaPet] $Label 在 $Seconds 秒内未就绪，请查看启动窗口日志。" -ForegroundColor Yellow
    return $false
}

Write-Host ''
Write-Host '========================================' -ForegroundColor DarkCyan
Write-Host '  VelaPet Web 一键启动' -ForegroundColor White
Write-Host "  模式：$Mode" -ForegroundColor Gray
Write-Host '========================================' -ForegroundColor DarkCyan
Write-Host ''

# --- Node.js ---
$node = Get-Command node -ErrorAction SilentlyContinue
if ($null -eq $node) {
    Fail '未找到 Node.js。请安装 Node.js 20 或更高版本：https://nodejs.org/'
}
$nodeVersion = (& node --version).TrimStart('v')
$nodeMajor = [int]($nodeVersion.Split('.')[0])
if ($nodeMajor -lt 20) {
    Fail "Node.js 版本过低（$nodeVersion），需要 20 或更高版本。"
}
Write-Step "Node.js $nodeVersion"

# --- pnpm ---
$pnpmCmd = Find-PnpmCmd
if ($null -eq $pnpmCmd) {
    Write-Step '未找到 pnpm，正在通过 corepack 安装...'
    $corepack = Get-Command corepack -ErrorAction SilentlyContinue
    if ($null -ne $corepack) {
        try {
            & corepack enable 2>$null
            & corepack prepare pnpm@11.25.0 --activate 2>$null
        }
        catch {
            Write-Warning "corepack 安装失败：$($_.Exception.Message)"
        }
    }
    $pnpmCmd = Find-PnpmCmd
}
if ($null -eq $pnpmCmd) {
    Write-Step '改用 npm 全局安装 pnpm...'
    $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($null -eq $npmCmd) {
        $npmCmdPath = Join-Path (Join-Path $env:ProgramFiles 'nodejs') 'npm.cmd'
        if (-not (Test-Path -LiteralPath $npmCmdPath)) {
            Fail '未找到 npm.cmd，请重新安装 Node.js。'
        }
        $npmExe = $npmCmdPath
    }
    else {
        $npmExe = $npmCmd.Source
    }
    & $npmExe install -g pnpm@11.25.0
    if ($LASTEXITCODE -ne 0) {
        Fail 'pnpm 安装失败。请手动执行：npm install -g pnpm@11.25.0'
    }
    $npmPrefix = (& $npmExe prefix -g).Trim()
    if ($npmPrefix -and -not (($env:Path -split ';') -contains $npmPrefix)) {
        $env:Path = "$npmPrefix;$env:Path"
    }
    $pnpmCmd = Find-PnpmCmd
}
if ($null -eq $pnpmCmd) {
    Fail '无法定位 pnpm.cmd，请重新打开终端后重试。'
}
$pnpmDir = Split-Path -Parent $pnpmCmd
if (-not (($env:Path -split ';') -contains $pnpmDir)) {
    $env:Path = "$pnpmDir;$env:Path"
}
Write-Step "pnpm：$pnpmCmd"

# --- 前端依赖 ---
$nodeModules = Join-Path $webRoot 'node_modules'
if ($Reinstall -or -not (Test-Path -LiteralPath $nodeModules)) {
    Write-Step '安装前端依赖（首次运行可能需要几分钟）...'
    Push-Location -LiteralPath $webRoot
    try {
        & $pnpmCmd install
        if ($LASTEXITCODE -ne 0) {
            Fail 'pnpm install 失败。请检查网络或锁文件后重试。'
        }
    }
    finally {
        Pop-Location
    }
}

# --- 环境文件 ---
$envFile = Join-Path $webRoot '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath (Join-Path $webRoot '.env.example') -Destination $envFile
    Write-Step '已创建 .env（来自 .env.example）'
}

$envLocal = Join-Path $webRoot '.env.local'
if (Test-Path -LiteralPath $envLocal) {
    $backup = $envLocal + '.bak-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    Copy-Item -LiteralPath $envLocal -Destination $backup
    Write-Step "已备份现有 .env.local 为 $(Split-Path -Leaf $backup)"
}
$envContent = "VITE_API_MODE=$Mode`r`nVITE_API_BASE_URL=$apiBaseUrl`r`n"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($envLocal, $envContent, $utf8NoBom)
$env:VITE_API_MODE = $Mode
$env:VITE_API_BASE_URL = $apiBaseUrl

# --- Real 模式后端 ---
if ($Mode -eq 'real') {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        Fail 'Real 模式需要 Python 3.11 或更高版本。'
    }

    $venvDir = Join-Path $serverDir '.venv'
    $venvPython = Join-Path $venvDir 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Step '创建后端虚拟环境...'
        $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
        if ($null -ne $pyLauncher) {
            & py -3.12 -m venv $venvDir
            if ($LASTEXITCODE -ne 0) {
                & python -m venv $venvDir
            }
        }
        else {
            & python -m venv $venvDir
        }
        if (-not (Test-Path -LiteralPath $venvPython)) {
            Fail 'Python 虚拟环境创建失败。'
        }
    }

    $uvicornExe = Join-Path $venvDir 'Scripts\uvicorn.exe'
    if ($Reinstall -or -not (Test-Path -LiteralPath $uvicornExe)) {
        Write-Step '安装后端依赖（首次运行可能需要几分钟）...'
        Push-Location -LiteralPath $serverDir
        try {
            & $venvPython -m pip install -e '.[dev]'
            if ($LASTEXITCODE -ne 0) {
                Fail '后端依赖安装失败。'
            }
        }
        finally {
            Pop-Location
        }
    }

    $env:VELAPET_DATABASE_URL = 'sqlite:///./velapet.db'
    $env:VELAPET_SEED_DEMO = 'true'

    Write-Step '执行数据库迁移...'
    Push-Location -LiteralPath $serverDir
    try {
        & $venvPython -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) {
            Fail '数据库迁移失败。'
        }
    }
    finally {
        Pop-Location
    }

    if (Test-Port 8000) {
        Write-Step '8000 端口已有服务，跳过启动后端。'
    }
    else {
        Write-Step '启动后端 FastAPI（新窗口）...'
        Start-Process -FilePath $venvPython `
            -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000') `
            -WorkingDirectory $serverDir | Out-Null
        if (-not (Wait-Port 8000 60 '后端')) {
            Fail '后端未就绪，请查看新窗口中的错误日志。'
        }
    }
}

# --- 前端 ---
if (Test-Port 5173) {
    Write-Step '5173 端口已有用户端，跳过启动。'
}
else {
    Write-Step '启动用户端（新窗口）...'
    Start-Process -FilePath $pnpmCmd -ArgumentList @('dev:user') -WorkingDirectory $webRoot | Out-Null
    if (-not (Wait-Port 5173 90 '用户端')) {
        Fail '用户端未就绪，请查看新窗口中的错误日志。'
    }
}

if (-not $NoAdmin) {
    if (Test-Port 5174) {
        Write-Step '5174 端口已有管理端，跳过启动。'
    }
    else {
        Write-Step '启动管理端（新窗口）...'
        Start-Process -FilePath $pnpmCmd -ArgumentList @('dev:admin') -WorkingDirectory $webRoot | Out-Null
        if (-not (Wait-Port 5174 90 '管理端')) {
            Fail '管理端未就绪，请查看新窗口中的错误日志。'
        }
    }
}

# --- 打开浏览器 ---
if (-not $NoBrowser) {
    Start-Process $userUrl | Out-Null
    if (-not $NoAdmin) {
        Start-Sleep -Milliseconds 500
        Start-Process $adminUrl | Out-Null
    }
}

Write-Host ''
Write-Host '启动完成：' -ForegroundColor Green
Write-Host "  用户端  $userUrl" -ForegroundColor White
if (-not $NoAdmin) {
    Write-Host "  管理端  $adminUrl" -ForegroundColor White
}
if ($Mode -eq 'real') {
    Write-Host "  后端    $apiBaseUrl/health" -ForegroundColor White
    Write-Host '  用户     demo@velapet.cn / VelaPetDemo123!' -ForegroundColor Gray
    Write-Host '  管理员   admin@velapet.cn / VelaPetAdmin123!' -ForegroundColor Gray
}
else {
    Write-Host '  用户     demo@velapet.cn / velapet-demo' -ForegroundColor Gray
    Write-Host '  管理员   admin@velapet.cn / velapet-admin-demo' -ForegroundColor Gray
}
Write-Host ''
Write-Host '关闭对应的启动窗口即可停止服务。' -ForegroundColor DarkGray
