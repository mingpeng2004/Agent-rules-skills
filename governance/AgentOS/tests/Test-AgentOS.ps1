#Requires -Version 5.1

[CmdletBinding()]
param(
    [string]$AgentOsRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $AgentOsRoot) { $AgentOsRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')) }

$required = @(
    'VERSION',
    'README.md',
    'constitution\AGENTOS-CONSTITUTION.md',
    'runtime\BOOT.md',
    'protocols\LONG-HORIZON.md',
    'protocols\MODEL-ADAPTER.md',
    'protocols\ROLE-ROUTER.md',
    'protocols\QUALITY-GATE.md',
    'protocols\MEMORY.md',
    'profiles\EMBEDDED.md',
    'policies\APPROVAL-POLICY.json',
    'protocols\APPROVAL-SCOPE.md',
    'templates\TASK.md',
    'templates\CHECKPOINT.md',
    'runtime\AGENT-IMPORT.md',
    'runtime\IMPORT-MANIFEST.json',
    'protocols\TRUTH-AND-EVIDENCE.md',
    'protocols\TASK-PROTOCOL.md',
    'protocols\RECURSIVE-PLANNING.md',
    'protocols\CONTEXT-PIPELINE.md',
    'protocols\HARNESS-ENHANCEMENTS.md',
    'policies\EVIDENCE-POLICY.json',
    'adapters\minimax\SKILL.md',
    'adapters\kimi\SKILL.md',
    'bin\AgentOS.ps1',
    'bin\AgentOS-Evidence.ps1',
    'tests\Test-AgentOS-Evidence.ps1',
    'protocols\DELEGATED-AUTONOMY.md',
    'policies\DECISION-POLICY.json',
    'templates\DECISION.json',
    'bin\AgentOS-Decision.ps1',
    'tests\Test-AgentOS-Decision.ps1',
    'tests\Test-AgentOS-Contract.ps1',
    'protocols\UPFRONT-CONFIRMATION.md',
    'protocols\DESIGN-CONSISTENCY.md',
    'policies\INTERACTION-POLICY.json',
    'templates\CONFIRMATION-PACKET.md',
    'templates\DESIGN-CONTRACT.md',
    'templates\AMENDMENT.json',
    'bin\AgentOS-Contract.ps1',
    'bin\agentos_skills.py',
    'tests\test_agentos_skills.py',
    'policies\SKILL-REGISTRY.json',
    'protocols\SKILL-MATRIX.md',
    'skills\production-skill-routing\SKILL.md',
    'templates\ENGINEERING-REVIEW.md'
)

$failed = @()
foreach ($relative in $required) {
    $path = Join-Path $AgentOsRoot $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { $failed += "missing: $relative" }
}

$scriptPath = Join-Path $AgentOsRoot 'bin\AgentOS.ps1'
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) { $failed += "parse-errors: $($errors.Count)" }

$evidenceScriptPath = Join-Path $AgentOsRoot 'bin\AgentOS-Evidence.ps1'
$evidenceTokens = $null
$evidenceErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile($evidenceScriptPath, [ref]$evidenceTokens, [ref]$evidenceErrors) | Out-Null
if ($evidenceErrors.Count -gt 0) { $failed += "evidence-parse-errors: $($evidenceErrors.Count)" }

foreach ($path in @(Get-ChildItem -LiteralPath (Join-Path $AgentOsRoot 'bin') -Filter '*.ps1' -File) +
    @(Get-ChildItem -LiteralPath (Join-Path $AgentOsRoot 'tests') -Filter '*.ps1' -File)) {
    $parseTokens = $null; $parseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($path.FullName, [ref]$parseTokens, [ref]$parseErrors) | Out-Null
    if ($parseErrors.Count -gt 0) { $failed += "parse-errors: $($path.Name)" }
}

try {
    Get-Content -LiteralPath (Join-Path $AgentOsRoot 'policies\EVIDENCE-POLICY.json') -Raw -Encoding UTF8 | ConvertFrom-Json | Out-Null
} catch {
    $failed += 'evidence-policy-json-invalid'
}

$boot = Get-Content -LiteralPath (Join-Path $AgentOsRoot 'runtime\BOOT.md') -Raw -Encoding UTF8
foreach ($anchor in @('DoD', 'checkpoint', '证据', '第二次失败', '第三次', '第四次')) {
    if ($boot -notmatch [regex]::Escape($anchor)) { $failed += "boot-anchor: $anchor" }
}

if ($boot -notmatch 'truth') { $failed += 'boot-anchor: truth' }
foreach ($anchor in @('300', 'delegated_default', 'AgentOS-Decision.ps1', 'AGOS-CONFIRM', 'contract')) {
    if ($boot -notmatch [regex]::Escape($anchor)) { $failed += "boot-autonomy-anchor: $anchor" }
}
try {
    $policy = Get-Content -LiteralPath (Join-Path $AgentOsRoot 'policies\DECISION-POLICY.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($policy.preference_wait_seconds -ne 300) { $failed += 'decision-deadline-not-300' }
    $manifest = Get-Content -LiteralPath (Join-Path $AgentOsRoot 'runtime\IMPORT-MANIFEST.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($file in $manifest.required_files) {
        if (-not (Test-Path -LiteralPath (Join-Path $AgentOsRoot $file))) { $failed += "import-missing: $file" }
    }
    if ($manifest.agentos_version -ne (Get-Content -LiteralPath (Join-Path $AgentOsRoot 'VERSION') -Raw).Trim()) {
        $failed += 'import-version-drift'
    }
} catch { $failed += 'decision-policy-or-import-json-invalid' }

if ($failed.Count -gt 0) {
    $failed | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Host "AgentOS tests passed: $($required.Count) required files, PowerShell parse, boot anchors."
