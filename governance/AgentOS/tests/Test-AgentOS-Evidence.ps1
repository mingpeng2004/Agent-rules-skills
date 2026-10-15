#Requires -Version 5.1

[CmdletBinding()]
param(
    [string]$AgentOsRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $AgentOsRoot) { $AgentOsRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')) }

$tool = Join-Path $AgentOsRoot 'bin\AgentOS-Evidence.ps1'
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("AgentOS-Evidence-" + [Guid]::NewGuid().ToString('N'))
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Require-Condition {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "Evidence test failed: $Message" }
}

function New-TestProject {
    $root = Join-Path $tempRoot ([Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path (Join-Path $root '.agentos\evidence') | Out-Null
    return $root
}

function Invoke-EvidenceTool {
    param([string[]]$Arguments)
    $previousPreference = $ErrorActionPreference
    try {
        # Negative cases must preserve native stderr and exit code on PowerShell 5.1.
        $ErrorActionPreference = 'Continue'
        $output = & powershell.exe -NoProfile -File $tool @Arguments 2>&1 | Out-String
        $exitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    return [PSCustomObject]@{
        ExitCode = $exitCode
        Output = $output
    }
}

function Record-FileClaim {
    param(
        [string]$Project,
        [string]$Id,
        [string]$Claim,
        [string]$ClaimStatus = 'observed',
        [string]$Level = 'E1',
        [string]$UseCase = 'static',
        [string]$Expiry = ''
    )
    $args = @(
        '-Command', 'record-claim',
        '-ProjectRoot', $Project,
        '-ClaimId', $Id,
        '-ClaimText', $Claim,
        '-Status', $ClaimStatus,
        '-SourceType', 'file',
        '-Source', $script:artifact,
        '-DataClass', 'real',
        '-ValidationMethod', 'SHA256 file inspection',
        '-EvidenceLevel', $Level,
        '-Applicability', $UseCase
    )
    if ($Expiry) { $args += @('-ExpiresAt', $Expiry) }
    return Invoke-EvidenceTool $args
}

try {
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    $script:artifact = Join-Path $tempRoot 'artifact.txt'
    [IO.File]::WriteAllText($script:artifact, 'evidence fixture', $utf8)

    $good = New-TestProject
    $r = Record-FileClaim $good 'file_claim' 'The evidence artifact is present.' 'observed'
    Require-Condition ($r.ExitCode -eq 0) 'observed claim should record'
    $r = Invoke-EvidenceTool @(
        '-Command', 'verify-claim',
        '-ProjectRoot', $good,
        '-ClaimId', 'file_claim',
        '-Status', 'verified',
        '-SourceType', 'file',
        '-Source', $script:artifact,
        '-DataClass', 'real',
        '-ValidationMethod', 'recompute SHA256 and inspect file',
        '-EvidenceLevel', 'E1',
        '-Applicability', 'static'
    )
    Require-Condition ($r.ExitCode -eq 0) 'file claim should verify'
    $r = Invoke-EvidenceTool @('-Command', 'validate-ledger', '-ProjectRoot', $good)
    Require-Condition ($r.ExitCode -eq 0) 'valid ledger should pass'
    $r = Invoke-EvidenceTool @('-Command', 'evidence-status', '-ProjectRoot', $good)
    Require-Condition (($r.ExitCode -eq 0) -and ($r.Output -match 'file_claim')) 'status should show claim'

    $commandEvidence = New-TestProject
    $r = Invoke-EvidenceTool @(
        '-Command', 'record-claim',
        '-ProjectRoot', $commandEvidence,
        '-ClaimId', 'command_claim',
        '-ClaimText', 'A command produced a complete successful result.',
        '-Status', 'observed',
        '-SourceType', 'command',
        '-Source', 'test command fixture',
        '-DataClass', 'real',
        '-ValidationMethod', 'inspect saved complete output',
        '-EvidenceLevel', 'E2',
        '-Applicability', 'unit',
        '-ArtifactPath', $script:artifact
    )
    Require-Condition ($r.ExitCode -eq 0) 'command observation should record'
    $r = Invoke-EvidenceTool @(
        '-Command', 'verify-claim',
        '-ProjectRoot', $commandEvidence,
        '-ClaimId', 'command_claim',
        '-SourceType', 'command',
        '-Source', 'test command fixture',
        '-DataClass', 'real',
        '-ValidationMethod', 'inspect saved complete output',
        '-EvidenceLevel', 'E2',
        '-Applicability', 'unit',
        '-ArtifactPath', $script:artifact,
        '-ExpiresAt', (Get-Date).AddHours(1).ToString('o')
    )
    Require-Condition ($r.ExitCode -ne 0) 'command without exit metadata must fail'
    $r = Invoke-EvidenceTool @(
        '-Command', 'verify-claim',
        '-ProjectRoot', $commandEvidence,
        '-ClaimId', 'command_claim',
        '-SourceType', 'command',
        '-Source', 'test command fixture',
        '-DataClass', 'real',
        '-ValidationMethod', 'inspect saved complete output',
        '-EvidenceLevel', 'E2',
        '-Applicability', 'unit',
        '-ArtifactPath', $script:artifact,
        '-ExpiresAt', (Get-Date).AddHours(1).ToString('o'),
        '-OutputComplete'
    )
    Require-Condition ($r.ExitCode -ne 0) 'output completeness must not synthesize an exit code'
    $r = Invoke-EvidenceTool @(
        '-Command', 'verify-claim',
        '-ProjectRoot', $commandEvidence,
        '-ClaimId', 'command_claim',
        '-SourceType', 'command',
        '-Source', 'test command fixture',
        '-DataClass', 'real',
        '-ValidationMethod', 'inspect saved complete output',
        '-EvidenceLevel', 'E2',
        '-Applicability', 'unit',
        '-ArtifactPath', $script:artifact,
        '-ExpiresAt', (Get-Date).AddHours(1).ToString('o'),
        '-ExitCode', '0',
        '-OutputComplete'
    )
    Require-Condition ($r.ExitCode -eq 0) 'complete command evidence should verify'
    $r = Invoke-EvidenceTool @('-Command', 'validate-ledger', '-ProjectRoot', $commandEvidence)
    Require-Condition ($r.ExitCode -eq 0) 'complete command ledger should pass'

    [IO.File]::WriteAllText($script:artifact, 'tampered fixture', $utf8)
    $r = Invoke-EvidenceTool @('-Command', 'validate-ledger', '-ProjectRoot', $good)
    Require-Condition ($r.ExitCode -ne 0) 'hash change must fail validation'
    [IO.File]::WriteAllText($script:artifact, 'evidence fixture', $utf8)

    $missingSource = New-TestProject
    $r = Invoke-EvidenceTool @(
        '-Command', 'record-claim',
        '-ProjectRoot', $missingSource,
        '-ClaimId', 'no_source',
        '-ClaimText', 'This must not become a verified fact.',
        '-Status', 'verified',
        '-SourceType', 'none',
        '-DataClass', 'unknown',
        '-ValidationMethod', 'not available',
        '-EvidenceLevel', 'E1'
    )
    Require-Condition ($r.ExitCode -ne 0) 'missing source must be rejected'

    $duplicate = New-TestProject
    $r = Record-FileClaim $duplicate 'duplicate_claim' 'Duplicate initial record test.'
    Require-Condition ($r.ExitCode -eq 0) 'first initial record should pass'
    $r = Record-FileClaim $duplicate 'duplicate_claim' 'Duplicate initial record test.'
    Require-Condition ($r.ExitCode -ne 0) 'duplicate initial record must fail'

    $synthetic = New-TestProject
    $r = Invoke-EvidenceTool @(
        '-Command', 'record-claim',
        '-ProjectRoot', $synthetic,
        '-ClaimId', 'synthetic_device',
        '-ClaimText', 'Synthetic data represents a real device result.',
        '-Status', 'synthetic',
        '-SourceType', 'synthetic',
        '-DataClass', 'synthetic',
        '-EvidenceLevel', 'E3',
        '-Applicability', 'real_device'
    )
    Require-Condition ($r.ExitCode -eq 0) 'synthetic record should be allowed when labeled'
    $r = Invoke-EvidenceTool @('-Command', 'validate-ledger', '-ProjectRoot', $synthetic)
    Require-Condition ($r.ExitCode -ne 0) 'synthetic real-device gate must fail'

    $stale = New-TestProject
    $r = Record-FileClaim $stale 'stale_claim' 'Expired evidence test.' 'verified' 'E1' 'static' ((Get-Date).AddMinutes(-1).ToString('o'))
    Require-Condition ($r.ExitCode -eq 0) 'expired record can be stored for audit'
    $r = Invoke-EvidenceTool @('-Command', 'validate-ledger', '-ProjectRoot', $stale)
    Require-Condition ($r.ExitCode -ne 0) 'expired verified evidence must fail'

    $conflict = New-TestProject
    $r = Record-FileClaim $conflict 'conflicted_claim' 'Conflicting evidence test.'
    Require-Condition ($r.ExitCode -eq 0) 'conflict base record should pass'
    $r = Invoke-EvidenceTool @(
        '-Command', 'verify-claim',
        '-ProjectRoot', $conflict,
        '-ClaimId', 'conflicted_claim',
        '-Status', 'conflicted',
        '-SourceType', 'file',
        '-Source', $script:artifact,
        '-DataClass', 'real',
        '-ValidationMethod', 'independent result disagrees',
        '-EvidenceLevel', 'E1',
        '-Reason', 'Two applicable sources disagree.'
    )
    Require-Condition ($r.ExitCode -eq 0) 'conflict must be recordable'
    $r = Invoke-EvidenceTool @('-Command', 'validate-ledger', '-ProjectRoot', $conflict)
    Require-Condition ($r.ExitCode -ne 0) 'conflicted evidence must block validation'

    $hardwareGate = New-TestProject
    $r = Record-FileClaim $hardwareGate 'hardware_level' 'Real device result with insufficient level.' 'verified' 'E2' 'real_device'
    Require-Condition ($r.ExitCode -ne 0) 'real device must reject E2'

    $malformed = New-TestProject
    $ledgerPath = Join-Path $malformed '.agentos\evidence\claims.jsonl'
    [IO.File]::WriteAllText($ledgerPath, '{not-json' + [Environment]::NewLine, $utf8)
    $r = Invoke-EvidenceTool @('-Command', 'validate-ledger', '-ProjectRoot', $malformed)
    Require-Condition ($r.ExitCode -ne 0) 'malformed ledger must fail'

    Write-Host 'AgentOS evidence tests passed: source, hash, duplicate, synthetic, stale, conflict, level and parse gates.'
    exit 0
} catch {
    Write-Error $_.Exception.Message
    exit 1
} finally {
    $resolved = [IO.Path]::GetFullPath($tempRoot)
    $temporaryBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($temporaryBase, [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $resolved) -notlike 'AgentOS-Evidence-*') { throw 'Refusing cleanup outside evidence fixture directory.' }
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
