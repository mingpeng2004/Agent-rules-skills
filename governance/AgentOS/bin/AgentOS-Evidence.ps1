#Requires -Version 5.1

[CmdletBinding()]
param(
    [ValidateSet('record-claim', 'verify-claim', 'invalidate-claim', 'validate-ledger', 'evidence-status')]
    [string]$Command = 'evidence-status',
    [string]$ProjectRoot,
    [string]$ClaimId,
    [string]$ClaimText,
    [string]$Status,
    [string]$Source,
    [string]$SourceType,
    [string]$DataClass,
    [string]$ValidationMethod,
    [string]$EvidenceLevel,
    [string]$ArtifactPath,
    [string]$Applicability,
    [string]$ObservedAt,
    [string]$ExpiresAt,
    [string]$Reason,
    [string]$ParentClaimIds,
    [int]$ExitCode = -1,
    [switch]$OutputComplete,
    [switch]$Independent,
    [switch]$PrimarySource,
    [string]$Agent = 'agent'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:Statuses = @(
    'verified', 'observed', 'derived', 'user-stated', 'assumption',
    'proposal', 'synthetic', 'unknown', 'conflicted', 'stale'
)
$script:SourceTypes = @(
    'file', 'command', 'test', 'device', 'user', 'url', 'model', 'synthetic', 'none'
)
$script:DataClasses = @('real', 'synthetic', 'mixed', 'unknown')
$script:EvidenceLevels = @('E0', 'E1', 'E2', 'E3', 'E4')
$script:MinimumLevels = @{
    static = 'E1'
    unit = 'E2'
    compile = 'E2'
    integration = 'E3'
    simulation = 'E3'
    hardware_in_loop = 'E3'
    performance = 'E3'
    long_run = 'E3'
    real_device = 'E4'
    user_acceptance = 'E4'
    safety = 'E4'
}
$script:HighRiskApplicabilities = @(
    'real_device', 'user_acceptance', 'safety', 'performance', 'long_run'
)

function Get-OptionalProperty {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string]$Name,
        $Default = $null
    )
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
}

function Write-AgentOsUtf8 {
    param([string]$Path, [string]$Content)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    [IO.File]::WriteAllText($Path, $Content, (New-Object System.Text.UTF8Encoding($false)))
}

function Get-AgentOsProjectRoot {
    if (-not $ProjectRoot) { $ProjectRoot = (Get-Location).Path }
    if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
        throw "ProjectRoot does not exist: $ProjectRoot"
    }
    $root = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $ProjectRoot).Path)
    if (-not (Test-Path -LiteralPath (Join-Path $root '.agentos') -PathType Container)) {
        throw "Project is not registered with AgentOS: $root"
    }
    return $root
}

function Get-AgentOsLedgerPath {
    param([string]$Root, [switch]$Create)
    $directory = Join-Path $Root '.agentos\evidence'
    if ($Create) { New-Item -ItemType Directory -Force -Path $directory | Out-Null }
    return (Join-Path $directory 'claims.jsonl')
}

function Read-AgentOsLedger {
    param([string]$Path)
    $events = New-Object System.Collections.Generic.List[object]
    $issues = New-Object System.Collections.Generic.List[string]
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [PSCustomObject]@{ Events = @(); Issues = @() }
    }
    $lineNumber = 0
    foreach ($line in (Get-Content -LiteralPath $Path -Encoding UTF8)) {
        $lineNumber++
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try {
            $events.Add(($line | ConvertFrom-Json))
        } catch {
            $issues.Add("line $lineNumber is not valid JSON: $($_.Exception.Message)")
        }
    }
    return [PSCustomObject]@{
        Events = @($events.ToArray())
        Issues = @($issues.ToArray())
    }
}

function Add-AgentOsEvent {
    param([string]$Path, [hashtable]$Event)
    $json = $Event | ConvertTo-Json -Depth 12 -Compress
    [IO.File]::AppendAllText(
        $Path,
        $json + [Environment]::NewLine,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

function Parse-AgentOsDate {
    param([string]$Value, [switch]$AllowEmpty)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        if ($AllowEmpty) { return $null }
        return (Get-Date)
    }
    try {
        return [DateTime]::Parse(
            $Value,
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind
        )
    } catch {
        throw "Invalid date: $Value"
    }
}

function Resolve-AgentOsArtifact {
    param(
        [string]$Root,
        [string]$EffectiveSourceType,
        [string]$EffectiveSource,
        [string]$EffectiveArtifactPath
    )
    $candidate = $EffectiveArtifactPath
    if (-not $candidate -and $EffectiveSourceType -eq 'file') {
        $candidate = $EffectiveSource
    }
    if (-not $candidate) {
        return [ordered]@{ artifact_path = $null; sha256 = $null }
    }
    if (-not [IO.Path]::IsPathRooted($candidate)) {
        $candidate = Join-Path $Root $candidate
    }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
    if ($resolved -eq (Get-AgentOsLedgerPath $Root)) { throw 'Evidence artifact must not be the ledger file itself: appending an event would change its own hash.' }
        throw "Evidence artifact does not exist: $candidate"
    }
    $resolved = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $candidate).Path)
    $hash = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
    return [ordered]@{ artifact_path = $resolved; sha256 = $hash }
}

function Get-EventValue {
    param($Event, [string]$Name, $Default = $null)
    return Get-OptionalProperty -Object $Event -Name $Name -Default $Default
}

function Get-AgentOsCurrentClaim {
    param([object[]]$Events, [string]$Id)
    $matching = @($Events | Where-Object { [string](Get-EventValue $_ 'claim_id' '') -eq $Id })
    if ($matching.Count -eq 0) { return $null }
    return $matching[$matching.Count - 1]
}

function Get-AgentOsParentIds {
    if ([string]::IsNullOrWhiteSpace($ParentClaimIds)) { return @() }
    return @($ParentClaimIds.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Get-AgentOsLevelNumber {
    param([string]$Level)
    if ([string]::IsNullOrWhiteSpace($Level)) { return 0 }
    return [int]$Level.Substring(1)
}

function Get-AgentOsExitCode {
    param($Event)
    $value = Get-EventValue $Event 'exit_code' $null
    if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) { return -1 }
    try { return [int]$value } catch { return -1 }
}

function Test-AgentOsAllowedValue {
    param([string]$Name, [string]$Value, [string[]]$Allowed)
    if ($Allowed -notcontains $Value) {
        throw "$Name must be one of: $($Allowed -join ', ')"
    }
}

function Test-AgentOsClaimInput {
    param(
        [string]$EffectiveStatus,
        [string]$EffectiveSourceType,
        [string]$EffectiveSource,
        [string]$EffectiveDataClass,
        [string]$EffectiveValidationMethod,
        [string]$EffectiveEvidenceLevel,
        [string]$EffectiveApplicability,
        [string]$EffectiveExpiresAt,
        [int]$EffectiveExitCode,
        [bool]$EffectiveOutputComplete,
        [hashtable]$Artifact
    )
    Test-AgentOsAllowedValue 'Status' $EffectiveStatus $script:Statuses
    Test-AgentOsAllowedValue 'SourceType' $EffectiveSourceType $script:SourceTypes
    Test-AgentOsAllowedValue 'DataClass' $EffectiveDataClass $script:DataClasses
    Test-AgentOsAllowedValue 'EvidenceLevel' $EffectiveEvidenceLevel $script:EvidenceLevels

    if ($EffectiveStatus -eq 'synthetic' -and $EffectiveDataClass -ne 'synthetic') {
        throw 'Synthetic status requires data_class=synthetic.'
    }
    if ($EffectiveSourceType -eq 'synthetic' -and $EffectiveDataClass -ne 'synthetic') {
        throw 'Synthetic source requires data_class=synthetic.'
    }
    if ($EffectiveStatus -eq 'derived' -and (Get-AgentOsParentIds).Count -eq 0) {
        throw 'Derived claims require ParentClaimIds.'
    }
    if ($EffectiveStatus -eq 'verified') {
        if ([string]::IsNullOrWhiteSpace($EffectiveSource)) {
            throw 'Verified claims require a non-empty source.'
        }
        if (@('none', 'model', 'user', 'synthetic') -contains $EffectiveSourceType) {
            throw "Source type $EffectiveSourceType cannot produce a verified machine fact."
        }
        if ($EffectiveDataClass -eq 'synthetic') {
            throw 'Synthetic data cannot be marked verified.'
        }
        if ([string]::IsNullOrWhiteSpace($EffectiveValidationMethod)) {
            throw 'Verified claims require ValidationMethod.'
        }
        if ((Get-AgentOsLevelNumber $EffectiveEvidenceLevel) -lt 1) {
            throw 'Verified claims require evidence level E1 or above.'
        }
        if ($EffectiveSourceType -in @('command', 'test', 'device', 'url')) {
            if (-not $Artifact.artifact_path) {
                throw "Verified $EffectiveSourceType evidence requires a complete output artifact."
            }
            if ([string]::IsNullOrWhiteSpace($EffectiveExpiresAt)) {
                throw "Verified $EffectiveSourceType evidence requires ExpiresAt."
            }
        }
        if ($EffectiveSourceType -in @('command', 'test', 'device')) {
            if ($EffectiveExitCode -ne 0) { throw "Verified $EffectiveSourceType evidence requires exit code 0." }
            if (-not $EffectiveOutputComplete) { throw "Verified $EffectiveSourceType evidence requires OutputComplete." }
        }
        if ($EffectiveSourceType -eq 'url' -and -not $EffectiveOutputComplete) {
            throw 'Verified URL evidence requires OutputComplete for the saved snapshot.'
        }
    }
    if ($EffectiveEvidenceLevel -eq 'E4' -and $EffectiveDataClass -eq 'synthetic') {
        throw 'Synthetic data cannot be assigned E4.'
    }
    if ($EffectiveStatus -eq 'verified' -and $script:MinimumLevels.ContainsKey($EffectiveApplicability)) {
        $requiredLevel = Get-AgentOsLevelNumber $script:MinimumLevels[$EffectiveApplicability]
        if ((Get-AgentOsLevelNumber $EffectiveEvidenceLevel) -lt $requiredLevel) {
            throw "Applicability $EffectiveApplicability requires evidence level $($script:MinimumLevels[$EffectiveApplicability])."
        }
    }
    if ($EffectiveStatus -eq 'verified' -and
        $EffectiveApplicability -in @('real_device', 'user_acceptance', 'safety') -and
        $EffectiveDataClass -eq 'synthetic') {
        throw "Synthetic data cannot satisfy $EffectiveApplicability."
    }
}

function New-AgentOsClaimEvent {
    param(
        [string]$EventType,
        [string]$EffectiveStatus,
        [string]$EffectiveClaimText,
        [string]$EffectiveSource,
        [string]$EffectiveSourceType,
        [string]$EffectiveDataClass,
        [string]$EffectiveValidationMethod,
        [string]$EffectiveEvidenceLevel,
        [string]$EffectiveApplicability,
        [string]$EffectiveObservedAt,
        [string]$EffectiveExpiresAt,
        [int]$EffectiveExitCode,
        [bool]$EffectiveOutputComplete,
        [hashtable]$Artifact,
        [string]$EffectiveReason
    )
    $now = (Get-Date).ToString('o')
    $event = [ordered]@{
        schema = 'agentos-evidence-event-v1'
        event_id = ([Guid]::NewGuid().ToString('N'))
        event_type = $EventType
        claim_id = $ClaimId
        claim_text = $EffectiveClaimText
        status = $EffectiveStatus
        source = if ($EffectiveSource) { $EffectiveSource } else { $null }
        source_type = $EffectiveSourceType
        data_class = $EffectiveDataClass
        observed_at = $EffectiveObservedAt
        validated_at = $now
        validation_method = if ($EffectiveValidationMethod) { $EffectiveValidationMethod } else { $null }
        evidence_level = $EffectiveEvidenceLevel
        artifact_path = $Artifact.artifact_path
        sha256 = $Artifact.sha256
        applicability = if ($EffectiveApplicability) { $EffectiveApplicability } else { 'project' }
        expires_at = if ($EffectiveExpiresAt) { $EffectiveExpiresAt } else { $null }
        exit_code = if ($EffectiveExitCode -ge 0) { $EffectiveExitCode } else { $null }
        output_complete = $EffectiveOutputComplete
        independent = [bool]$Independent
        primary_source = [bool]$PrimarySource
        parent_claim_ids = @(Get-AgentOsParentIds)
        reason = if ($EffectiveReason) { $EffectiveReason } else { $null }
        agent = $Agent
    }
    return $event
}

function Invoke-AgentOsRecordClaim {
    param([string]$Root, [object[]]$Events)
    if ([string]::IsNullOrWhiteSpace($ClaimId) -or $ClaimId -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{1,100}$') {
        throw 'ClaimId must contain 2-101 safe characters.'
    }
    if ([string]::IsNullOrWhiteSpace($ClaimText)) { throw 'ClaimText is required.' }
    if (@($Events | Where-Object {
        [string](Get-EventValue $_ 'event_type' '') -eq 'claim_recorded' -and
        [string](Get-EventValue $_ 'claim_id' '') -eq $ClaimId
    }).Count -gt 0) {
        throw "Claim already has an initial record: $ClaimId"
    }
    $effectiveStatus = if ($Status) { $Status } elseif ($Source) { 'observed' } else { 'unknown' }
    $effectiveSourceType = if ($SourceType) { $SourceType } else { 'none' }
    $effectiveDataClass = if ($DataClass) { $DataClass } else { 'unknown' }
    $effectiveLevel = if ($EvidenceLevel) { $EvidenceLevel } else { 'E0' }
    $observed = (Parse-AgentOsDate $ObservedAt).ToString('o')
    $expires = (Parse-AgentOsDate $ExpiresAt -AllowEmpty)
    $expiresText = if ($expires) { $expires.ToString('o') } else { '' }
    $artifact = Resolve-AgentOsArtifact $Root $effectiveSourceType $Source $ArtifactPath
    Test-AgentOsClaimInput $effectiveStatus $effectiveSourceType $Source $effectiveDataClass $ValidationMethod $effectiveLevel $Applicability $expiresText $ExitCode ([bool]$OutputComplete) $artifact
    $event = New-AgentOsClaimEvent 'claim_recorded' $effectiveStatus $ClaimText $Source $effectiveSourceType $effectiveDataClass $ValidationMethod $effectiveLevel $Applicability $observed $expiresText $ExitCode ([bool]$OutputComplete) $artifact $Reason
    Add-AgentOsEvent (Get-AgentOsLedgerPath $Root -Create) $event
    $event | ConvertTo-Json -Depth 12
}

function Invoke-AgentOsVerifyClaim {
    param([string]$Root, [object[]]$Events)
    if ([string]::IsNullOrWhiteSpace($ClaimId)) { throw 'ClaimId is required.' }
    $current = Get-AgentOsCurrentClaim $Events $ClaimId
    if ($null -eq $current) { throw "Claim not found: $ClaimId" }
    $effectiveText = if ($ClaimText) { $ClaimText } else { [string](Get-EventValue $current 'claim_text' '') }
    $effectiveSource = if ($Source) { $Source } else { [string](Get-EventValue $current 'source' '') }
    $effectiveSourceType = if ($SourceType) { $SourceType } else { [string](Get-EventValue $current 'source_type' 'none') }
    $effectiveDataClass = if ($DataClass) { $DataClass } else { [string](Get-EventValue $current 'data_class' 'unknown') }
    $effectiveMethod = if ($ValidationMethod) { $ValidationMethod } else { [string](Get-EventValue $current 'validation_method' '') }
    $effectiveLevel = if ($EvidenceLevel) { $EvidenceLevel } else { [string](Get-EventValue $current 'evidence_level' 'E0') }
    $effectiveApplicability = if ($Applicability) { $Applicability } else { [string](Get-EventValue $current 'applicability' 'project') }
    $effectiveArtifact = if ($ArtifactPath) { $ArtifactPath } else { [string](Get-EventValue $current 'artifact_path' '') }
    $effectiveStatus = if ($Status) { $Status } else { 'verified' }
    $observed = (Parse-AgentOsDate $ObservedAt).ToString('o')
    $expiresValue = Parse-AgentOsDate $ExpiresAt -AllowEmpty
    if ($null -eq $expiresValue -and $effectiveSourceType -in @('command', 'test', 'device', 'url')) {
        $existingExpiry = [string](Get-EventValue $current 'expires_at' '')
        $expiresValue = Parse-AgentOsDate $existingExpiry -AllowEmpty
    }
    $expiresText = if ($expiresValue) { $expiresValue.ToString('o') } else { '' }
    $effectiveExitCode = if ($ExitCode -ge 0) { $ExitCode } else { Get-AgentOsExitCode $current }
    $effectiveOutputComplete = if ($OutputComplete) { $true } else { [bool](Get-EventValue $current 'output_complete' $false) }
    $artifact = Resolve-AgentOsArtifact $Root $effectiveSourceType $effectiveSource $effectiveArtifact
    $savedIndependent = [bool](Get-EventValue $current 'independent' $false)
    $savedPrimary = [bool](Get-EventValue $current 'primary_source' $false)
    if (-not $Independent -and $savedIndependent) { $Independent = $true }
    if (-not $PrimarySource -and $savedPrimary) { $PrimarySource = $true }
    Test-AgentOsClaimInput $effectiveStatus $effectiveSourceType $effectiveSource $effectiveDataClass $effectiveMethod $effectiveLevel $effectiveApplicability $expiresText $effectiveExitCode $effectiveOutputComplete $artifact
    $eventType = if ($effectiveStatus -eq 'conflicted') { 'claim_conflicted' } else { 'claim_verified' }
    $event = New-AgentOsClaimEvent $eventType $effectiveStatus $effectiveText $effectiveSource $effectiveSourceType $effectiveDataClass $effectiveMethod $effectiveLevel $effectiveApplicability $observed $expiresText $effectiveExitCode $effectiveOutputComplete $artifact $Reason
    Add-AgentOsEvent (Get-AgentOsLedgerPath $Root -Create) $event
    $event | ConvertTo-Json -Depth 12
}

function Invoke-AgentOsInvalidateClaim {
    param([string]$Root, [object[]]$Events)
    if ([string]::IsNullOrWhiteSpace($ClaimId)) { throw 'ClaimId is required.' }
    $current = Get-AgentOsCurrentClaim $Events $ClaimId
    if ($null -eq $current) { throw "Claim not found: $ClaimId" }
    if ([string]::IsNullOrWhiteSpace($Reason)) { throw 'Reason is required for invalidation.' }
    $event = [ordered]@{
        schema = 'agentos-evidence-event-v1'
        event_id = ([Guid]::NewGuid().ToString('N'))
        event_type = 'claim_invalidated'
        claim_id = $ClaimId
        claim_text = [string](Get-EventValue $current 'claim_text' '')
        status = 'unknown'
        source = $null
        source_type = 'none'
        data_class = 'unknown'
        observed_at = (Get-Date).ToString('o')
        validated_at = (Get-Date).ToString('o')
        validation_method = $null
        evidence_level = 'E0'
        artifact_path = $null
        sha256 = $null
        applicability = [string](Get-EventValue $current 'applicability' 'project')
        expires_at = $null
        exit_code = $null
        output_complete = $false
        independent = $false
        primary_source = $false
        parent_claim_ids = @()
        reason = $Reason
        agent = $Agent
    }
    Add-AgentOsEvent (Get-AgentOsLedgerPath $Root -Create) $event
    $event | ConvertTo-Json -Depth 12
}

function Add-ValidationIssue {
    param([System.Collections.Generic.List[string]]$Issues, [string]$Message)
    $Issues.Add($Message)
}

function Test-AgentOsEventShape {
    param(
        [object]$Event,
        [System.Collections.Generic.List[string]]$Issues,
        [int]$Index,
        [string[]]$SupersededClaims = @(),
        [int[]]$HistoricalIndexes = @()
    )
    # An invalidated claim keeps its history for audit, but its replaced artifact is
    # reported as superseded instead of blocking the whole ledger.
    $claimSuperseded = $SupersededClaims -contains [string](Get-EventValue $Event 'claim_id' '')
    $isHistorical = $HistoricalIndexes -contains $Index
    foreach ($name in @('event_type', 'claim_id', 'status', 'source_type', 'data_class', 'observed_at', 'validated_at', 'evidence_level')) {
        if ([string]::IsNullOrWhiteSpace([string](Get-EventValue $Event $name ''))) {
            Add-ValidationIssue $Issues "event $Index missing $name"
        }
    }
    $statusValue = [string](Get-EventValue $Event 'status' '')
    $sourceTypeValue = [string](Get-EventValue $Event 'source_type' '')
    $dataClassValue = [string](Get-EventValue $Event 'data_class' '')
    $levelValue = [string](Get-EventValue $Event 'evidence_level' '')
    if ($script:Statuses -notcontains $statusValue) { Add-ValidationIssue $Issues "event $Index has invalid status $statusValue" }
    if ($script:SourceTypes -notcontains $sourceTypeValue) { Add-ValidationIssue $Issues "event $Index has invalid source_type $sourceTypeValue" }
    if ($script:DataClasses -notcontains $dataClassValue) { Add-ValidationIssue $Issues "event $Index has invalid data_class $dataClassValue" }
    if ($script:EvidenceLevels -notcontains $levelValue) { Add-ValidationIssue $Issues "event $Index has invalid evidence_level $levelValue" }
    $artifact = [string](Get-EventValue $Event 'artifact_path' '')
    $savedHash = [string](Get-EventValue $Event 'sha256' '')
    if ($artifact -and $claimSuperseded) {
        # superseded claim: no hash gate, history retained
    } elseif ($artifact -and $isHistorical) {
        # historical event of the same claim: current state is the latest event
        # superseded: no hash gate, history retained
    } elseif ($artifact) {
        if (-not (Test-Path -LiteralPath $artifact -PathType Leaf)) {
            Add-ValidationIssue $Issues "event $Index artifact missing: $artifact"
        } elseif (-not $savedHash) {
            Add-ValidationIssue $Issues "event $Index artifact has no SHA256"
        } else {
            $actualHash = (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actualHash -ne $savedHash.ToLowerInvariant()) {
                Add-ValidationIssue $Issues "event $Index artifact hash mismatch: $artifact"
            }
        }
    }
    if ($statusValue -eq 'verified') {
        $sourceValue = [string](Get-EventValue $Event 'source' '')
        $methodValue = [string](Get-EventValue $Event 'validation_method' '')
        if (-not $sourceValue) { Add-ValidationIssue $Issues "event $Index verified without source" }
        if (@('none', 'model', 'user', 'synthetic') -contains $sourceTypeValue) {
            Add-ValidationIssue $Issues "event $Index verified with disallowed source_type $sourceTypeValue"
        }
        if ($dataClassValue -eq 'synthetic') { Add-ValidationIssue $Issues "event $Index verified synthetic data" }
        if (-not $methodValue) { Add-ValidationIssue $Issues "event $Index verified without validation_method" }
        if ((Get-AgentOsLevelNumber $levelValue) -lt 1) { Add-ValidationIssue $Issues "event $Index verified at E0" }
        if ($script:MinimumLevels.ContainsKey([string](Get-EventValue $Event 'applicability' ''))) {
            $requiredLevel = Get-AgentOsLevelNumber $script:MinimumLevels[[string](Get-EventValue $Event 'applicability' '')]
            if ((Get-AgentOsLevelNumber $levelValue) -lt $requiredLevel) {
                Add-ValidationIssue $Issues "event $Index evidence level is below applicability minimum"
            }
        }
        if ($sourceTypeValue -in @('command', 'test', 'device', 'url')) {
            if (-not $artifact) { Add-ValidationIssue $Issues "event $Index dynamic evidence has no complete artifact" }
            if (-not [string](Get-EventValue $Event 'expires_at' '')) { Add-ValidationIssue $Issues "event $Index dynamic evidence has no expiration" }
        }
        if ($sourceTypeValue -in @('command', 'test', 'device')) {
            if ((Get-AgentOsExitCode $Event) -ne 0) { Add-ValidationIssue $Issues "event $Index command evidence exit code is not 0" }
            if (-not [bool](Get-EventValue $Event 'output_complete' $false)) { Add-ValidationIssue $Issues "event $Index command evidence is not complete" }
        }
        if ($sourceTypeValue -eq 'url' -and -not [bool](Get-EventValue $Event 'output_complete' $false)) {
            Add-ValidationIssue $Issues "event $Index URL snapshot is not marked complete"
        }
    }
}

function Invoke-AgentOsValidateLedger {
    param([string]$Root, [object]$Ledger)
    $issues = New-Object System.Collections.Generic.List[string]
    foreach ($parseIssue in @($Ledger.Issues)) { Add-ValidationIssue $issues $parseIssue }
    $events = @($Ledger.Events)
    $superseded = @($events | Where-Object { [string](Get-EventValue $_ 'event_type' '') -eq 'claim_invalidated' } | ForEach-Object { [string](Get-EventValue $_ 'claim_id' '') })
    $lastEventIndex = @{}
    for ($i = 0; $i -lt $events.Count; $i++) { $lastEventIndex[[string](Get-EventValue $events[$i] 'claim_id' '')] = $i }
    $historicalIndexes = @(0..([Math]::Max(0, $events.Count - 1)) | Where-Object { $lastEventIndex[[string](Get-EventValue $events[$_] 'claim_id' '')] -ne $_ } | ForEach-Object { $_ + 1 })
    $initialById = @{}
    for ($i = 0; $i -lt $events.Count; $i++) {
        Test-AgentOsEventShape $events[$i] $issues ($i + 1) $superseded $historicalIndexes
        $id = [string](Get-EventValue $events[$i] 'claim_id' '')
        $eventType = [string](Get-EventValue $events[$i] 'event_type' '')
        if ($eventType -eq 'claim_recorded') {
            if ($initialById.ContainsKey($id)) {
                Add-ValidationIssue $issues "claim has duplicate initial records: $id"
            } else {
                $initialById[$id] = $true
            }
        }
    }
    $currentById = @{}
    foreach ($event in $events) {
        $id = [string](Get-EventValue $event 'claim_id' '')
        if ($id) { $currentById[$id] = $event }
    }
    foreach ($id in $currentById.Keys) {
        $current = $currentById[$id]
        $statusValue = [string](Get-EventValue $current 'status' '')
        $app = [string](Get-EventValue $current 'applicability' 'project')
        $dataClassValue = [string](Get-EventValue $current 'data_class' 'unknown')
        if ($statusValue -eq 'conflicted') {
            Add-ValidationIssue $issues "claim is conflicted: $id"
        }
        $expires = Parse-AgentOsDate ([string](Get-EventValue $current 'expires_at' '')) -AllowEmpty
        if ($expires -and $expires -le (Get-Date) -and $statusValue -eq 'verified') {
            Add-ValidationIssue $issues "claim is stale: $id"
        }
        if ($app -in $script:HighRiskApplicabilities -and $statusValue -eq 'verified') {
            if ($dataClassValue -eq 'synthetic') {
                Add-ValidationIssue $issues "high-risk claim uses synthetic data: $id"
            }
            $evidence = @($events | Where-Object {
                [string](Get-EventValue $_ 'claim_id' '') -eq $id -and
                [string](Get-EventValue $_ 'status' '') -eq 'verified' -and
                [bool](Get-EventValue $_ 'independent' $false)
            })
            $keys = @($evidence | ForEach-Object {
                $hash = [string](Get-EventValue $_ 'sha256' '')
                if ($hash) { $hash } else { [string](Get-EventValue $_ 'source' '') }
            } | Where-Object { $_ } | Select-Object -Unique)
            $hasPrimary = @($evidence | Where-Object { [bool](Get-EventValue $_ 'primary_source' $false) }).Count -gt 0
            if ($keys.Count -lt 2 -and -not $hasPrimary) {
                Add-ValidationIssue $issues "high-risk claim lacks two independent sources or a primary source: $id"
            }
        }
        if ($dataClassValue -eq 'synthetic' -and $app -in @('real_device', 'user_acceptance', 'safety', 'performance')) {
            Add-ValidationIssue $issues ("synthetic data cannot satisfy real-world applicability " + $app + ": " + $id)
        }
    }
    $report = [ordered]@{
        schema = 'agentos-evidence-validation-v1'
        generated_at = (Get-Date).ToString('o')
        project_root = $Root
        ledger = (Get-AgentOsLedgerPath $Root)
        event_count = $events.Count
        claim_count = $currentById.Count
        empty = ($events.Count -eq 0)
        valid = ($issues.Count -eq 0)
        issues = @($issues.ToArray())
    }
    $reportPath = Join-Path $Root ".agentos\evidence\validation-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
    Write-AgentOsUtf8 $reportPath ($report | ConvertTo-Json -Depth 10)
    $report | ConvertTo-Json -Depth 10
    if (-not $report.valid) { exit 1 }
}

function Invoke-AgentOsEvidenceStatus {
    param([string]$Root, [object]$Ledger)
    $currentById = @{}
    foreach ($event in @($Ledger.Events)) {
        $id = [string](Get-EventValue $event 'claim_id' '')
        if ($id) { $currentById[$id] = $event }
    }
    $items = @($currentById.GetEnumerator() | Sort-Object Name | ForEach-Object {
        $event = $_.Value
        $expiry = Parse-AgentOsDate ([string](Get-EventValue $event 'expires_at' '')) -AllowEmpty
        [ordered]@{
            claim_id = $_.Key
            claim_text = [string](Get-EventValue $event 'claim_text' '')
            status = [string](Get-EventValue $event 'status' 'unknown')
            evidence_level = [string](Get-EventValue $event 'evidence_level' 'E0')
            source_type = [string](Get-EventValue $event 'source_type' 'none')
            data_class = [string](Get-EventValue $event 'data_class' 'unknown')
            applicability = [string](Get-EventValue $event 'applicability' 'project')
            expires_at = if ($expiry) { $expiry.ToString('o') } else { $null }
        }
    })
    [ordered]@{
        schema = 'agentos-evidence-status-v1'
        generated_at = (Get-Date).ToString('o')
        project_root = $Root
        ledger = (Get-AgentOsLedgerPath $Root)
        claim_count = $items.Count
        claims = $items
        parse_issues = @($Ledger.Issues)
    } | ConvertTo-Json -Depth 10
}

try {
    $root = Get-AgentOsProjectRoot
    $ledgerPath = Get-AgentOsLedgerPath $root
    $ledger = Read-AgentOsLedger $ledgerPath
    switch ($Command) {
        'record-claim' { Invoke-AgentOsRecordClaim $root @($ledger.Events) }
        'verify-claim' { Invoke-AgentOsVerifyClaim $root @($ledger.Events) }
        'invalidate-claim' { Invoke-AgentOsInvalidateClaim $root @($ledger.Events) }
        'validate-ledger' { Invoke-AgentOsValidateLedger $root $ledger }
        'evidence-status' { Invoke-AgentOsEvidenceStatus $root $ledger }
    }
} catch {
    Write-Error $_.Exception.Message
    exit 1
}

