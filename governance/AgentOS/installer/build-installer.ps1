#Requires -Version 5.1

[CmdletBinding()]
param(
    [string]$Configuration = 'Release',
    [string]$SecurityCheckPath = '${PROJECT_PATH}'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$dist = Join-Path $root 'dist\AgentOS-Installer'
$zip = Join-Path $root 'dist\AgentOS-Installer.zip'
$payload = Join-Path $dist 'AgentOS-Payload'
$sourceOut = Join-Path $dist 'Source'
$source = Join-Path $PSScriptRoot 'AgentOS.Setup.cs'
$exe = Join-Path $dist 'AgentOS-Installer.exe'
$csc = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'

if (-not (Test-Path -LiteralPath $csc)) { $csc = 'C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe' }
if (-not (Test-Path -LiteralPath $csc)) { throw '找不到 .NET Framework csc.exe，无法构建透明安装器。' }

if (-not (Test-Path -LiteralPath $SecurityCheckPath)) { throw 'SecurityCheckPath is required before packaging.' }
. $SecurityCheckPath
$auditResults = @()
foreach ($candidate in @($source, $PSCommandPath) +
    @(Get-ChildItem -LiteralPath (Join-Path $root 'bin') -Filter '*.ps1' -File | Select-Object -ExpandProperty FullName) +
    @(Get-ChildItem -LiteralPath (Join-Path $root 'bin') -Filter '*.py' -File | Select-Object -ExpandProperty FullName) +
    @(Get-ChildItem -LiteralPath (Join-Path $root 'tests') -Filter '*.py' -File | Select-Object -ExpandProperty FullName) +
    @(Get-ChildItem -LiteralPath (Join-Path $root 'tests') -Filter '*.ps1' -File | Select-Object -ExpandProperty FullName)) {
    $audit = Invoke-MingSecurityCheck -FilePath $candidate -ProjectRoot $root -Quiet
    $auditResults += [ordered]@{ file = $candidate; summary = $audit.Summary; findings = @($audit.Findings) }
    if ($audit.Summary.critical -gt 0 -or $audit.Summary.warning -gt 0) { throw "Security audit blocked packaging: $candidate" }
}
$utf8 = New-Object System.Text.UTF8Encoding($false)
New-Item -ItemType Directory -Force -Path (Join-Path $root 'reports') | Out-Null
$auditReport = Join-Path $root ('reports\security-build-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
[IO.File]::WriteAllText($auditReport, ($auditResults | ConvertTo-Json -Depth 8), $utf8)

$expectedDist = [IO.Path]::GetFullPath((Join-Path $root 'dist\AgentOS-Installer'))
if ([IO.Path]::GetFullPath($dist) -ne $expectedDist -or
    (Split-Path -Parent $expectedDist) -ne [IO.Path]::GetFullPath((Join-Path $root 'dist'))) {
    throw 'Refusing cleanup outside the installer output directory.'
}
if (Test-Path -LiteralPath $zip) {
    $archiveDir = Join-Path $root 'dist\archives'
    New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null
    $archive = Join-Path $archiveDir ('AgentOS-Installer-before-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.zip')
    Copy-Item -LiteralPath $zip -Destination $archive -ErrorAction Stop
}
if (Test-Path -LiteralPath $dist) { Remove-Item -LiteralPath $dist -Recurse -Force }
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
New-Item -ItemType Directory -Force -Path $payload, $sourceOut | Out-Null

$managedFiles = @('README.md', 'VERSION')
$managedDirs = @('adapters', 'bin', 'constitution', 'policies', 'profiles', 'protocols', 'runtime', 'templates', 'tests', 'skills')
foreach ($file in $managedFiles) { Copy-Item -LiteralPath (Join-Path $root $file) -Destination (Join-Path $payload $file) -Force }
foreach ($dir in $managedDirs) { Copy-Item -LiteralPath (Join-Path $root $dir) -Destination (Join-Path $payload $dir) -Recurse -Force }
Copy-Item -LiteralPath $source -Destination (Join-Path $sourceOut 'AgentOS.Setup.cs') -Force
Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $sourceOut 'build-installer.ps1') -Force
if (@(Get-ChildItem -LiteralPath $payload -Recurse -Directory -Filter '__pycache__').Count -gt 0) {
    throw 'Python cache must not be packaged. Clean source cache separately before building.'
}

$arguments = @(
    '/nologo',
    '/target:winexe',
    '/optimize+',
    '/debug-',
    "/out:$exe",
    '/r:System.dll',
    '/r:System.Drawing.dll',
    '/r:System.Windows.Forms.dll',
    '/r:System.Web.Extensions.dll',
    $source
)
& $csc @arguments
if ($LASTEXITCODE -ne 0) { throw "csc failed with exit code $LASTEXITCODE" }

$readme = @"
Agent Governance OS Installer

运行 AgentOS-Installer.exe，选择：
1. AgentOS 目标目录
2. MiniMax Code 安装目录
3. Kimi Code 安装/配置目录
4. 要接入的项目目录（每行一个）
5. 普通操作默认授权域：session / task / turn

安装器是透明的：AgentOS-Payload 和 Source 目录保留在旁边；安装器不联网、不保存凭据、不启动子进程。
普通开发操作可以使用会话授权；删除、凭据、网络、远程、服务、真实硬件、固件烧录和安全控制始终需要逐次确认。
开工前一次性定调开发与软件框架（12 域契约，用户明确确认，不超时），落盘 .agentos\contract；后续需求以修订迭代。
普通偏好完整推荐实际通知后 300 秒无反馈按既有委托采用，记录 delegated_default；不视作用户已同意或验收。
技能矩阵按需选择一个主能力和至多两个约束，候选能力不冒充已部署；新增本地检查工具需 Python 3.9+（不自动安装）。
截止时间和事实来源保存于项目 .agentos\decisions；恢复后先记录用户新反馈再评估。无活动执行循环/调度器时，不自动唤醒关闭的对话。
安装完成后必须完全退出并重新打开 MiniMax Code、VS Code/Kimi Code。

命令行自测：
AgentOS-Installer.exe --self-test
"@
[IO.File]::WriteAllText((Join-Path $dist 'README.txt'), $readme, $utf8)

$manifest = @{
    product = 'Agent Governance OS Installer'
    agentos_version = (Get-Content -LiteralPath (Join-Path $payload 'VERSION') -Raw -Encoding UTF8).Trim()
    package_format = 'transparent-exe-plus-auditable-payload'
    network_access = $false
    child_process_at_install_runtime = $false
    default_approval_scope = 'session'
    high_risk_actions = @((Get-Content -LiteralPath (Join-Path $payload 'policies\APPROVAL-POLICY.json') -Raw -Encoding UTF8 | ConvertFrom-Json).always_single_approval)
    confirmation_domains = 12
    contract_dir = '.agentos/contract'
    preference_wait_seconds = 300
    safety_timeout_allowed = $false
    unattended_wakeup_service = $false
    payload_directory = 'AgentOS-Payload'
    source_directory = 'Source'
}
[IO.File]::WriteAllText((Join-Path $dist 'MANIFEST.json'), ($manifest | ConvertTo-Json -Depth 5), $utf8)

$selfTestReport = Join-Path $dist 'installer-self-test.log'
$selfTest = Start-Process -FilePath $exe -ArgumentList @('--self-test', ('"' + $selfTestReport + '"')) -WindowStyle Hidden -PassThru
try {
    if (-not $selfTest.WaitForExit(60000)) { $selfTest.Kill(); throw 'Installer self-test timed out after 60 seconds.' }
    $selfTest.Refresh()
    if ($selfTest.ExitCode -ne 0) { throw "Installer self-test failed with exit code $($selfTest.ExitCode)" }
    if (-not (Test-Path -LiteralPath $selfTestReport) -or
        (Get-Content -LiteralPath $selfTestReport -Raw -Encoding UTF8) -notmatch 'Installer self-test passed\.') {
        throw 'Installer self-test did not produce a complete success report.'
    }
} finally { $selfTest.Dispose() }

$hashLines = Get-ChildItem -LiteralPath $dist -File -Recurse | Sort-Object FullName | ForEach-Object {
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    $relative = $_.FullName.Substring($dist.Length).TrimStart('\', '/')
    "$hash  $relative"
}
[IO.File]::WriteAllLines((Join-Path $dist 'SHA256SUMS.txt'), $hashLines, $utf8)

Write-Host "Installer built: $exe"
Write-Host "Payload: $payload"
Write-Host "Checksums: $(Join-Path $dist 'SHA256SUMS.txt')"
Compress-Archive -Path $dist -DestinationPath $zip -CompressionLevel Optimal
Write-Host "Transfer package: $zip"
Write-Host "Security audit: $auditReport"
