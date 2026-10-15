#Requires -Version 5.1

[CmdletBinding()]
param(
    [ValidateSet('propose', 'notify', 'respond', 'evaluate', 'status', 'invalidate')]
    [string]$Command = 'status',
    [string]$ProjectRoot,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.-]{1,80}$')]
    [string]$DecisionId,
    [string]$ProposalPath,
    [string]$NoticeRef,
    [ValidateSet('approve', 'reject', 'pause', 'change')]
    [string]$Response,
    [string]$ResponseRef,
    [string]$Reason
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:DecisionOsRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))

function Get-DecisionHash-Ming {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Get-DecisionPolicy-Ming {
    $decisionPath = Join-Path $script:DecisionOsRoot 'policies\DECISION-POLICY.json'
    $approvalPath = Join-Path $script:DecisionOsRoot 'policies\APPROVAL-POLICY.json'
    $decision = Get-Content -LiteralPath $decisionPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $approval = Get-Content -LiteralPath $approvalPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($decision.preference_wait_seconds -ne 300) { throw 'Unexpected preference deadline; review policy before adoption.' }
    return [PSCustomObject]@{
        Decision = $decision
        Approval = $approval
        Hash = (Get-DecisionHash-Ming $decisionPath) + ':' + (Get-DecisionHash-Ming $approvalPath)
    }
}

function Test-DecisionProposal-Ming {
    param($Proposal)
    foreach ($name in @('task_id', 'title', 'kind', 'recommendation', 'scope', 'impact', 'rollback')) {
        if (-not $Proposal.PSObject.Properties[$name] -or
            $Proposal.$name -isnot [string] -or [string]::IsNullOrWhiteSpace($Proposal.$name)) {
            throw "Missing proposal text: $name"
        }
    }
    if ($Proposal.task_id -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{1,80}$') { throw 'Unsafe task ID.' }
    foreach ($name in @('facts_ready', 'reversible', 'within_user_goal', 'changes_security_boundary')) {
        if (-not $Proposal.PSObject.Properties[$name] -or $Proposal.$name -isnot [bool]) {
            throw "Proposal requires an explicit boolean: $name"
        }
    }
    foreach ($name in @('operations', 'fact_sources')) {
        if (-not $Proposal.PSObject.Properties[$name] -or $Proposal.$name -isnot [Array] -or
            @($Proposal.$name).Count -eq 0) { throw "Proposal requires a nonempty array: $name" }
        foreach ($value in $Proposal.$name) {
            if ($value -isnot [string] -or [string]::IsNullOrWhiteSpace($value)) { throw "Invalid value in $name" }
        }
    }
}

function Get-DecisionEligibility-Ming {
    param($Proposal, $Policy)
    Test-DecisionProposal-Ming $Proposal
    if ($Proposal.kind -ne $Policy.Decision.eligible_kind) { return 'kind_requires_explicit_gate' }
    if (-not $Proposal.facts_ready) { return 'missing_verified_facts' }
    if (-not $Proposal.reversible) { return 'irreversible_change' }
    if (-not $Proposal.within_user_goal) { return 'outside_existing_goal' }
    if ($Proposal.changes_security_boundary) { return 'security_boundary_change' }
    $ordinary = @($Policy.Approval.normal_operations) + @($Policy.Decision.preference_operations)
    foreach ($operation in $Proposal.operations) {
        if ($operation -in @($Policy.Approval.always_single_approval)) { return 'safety_requires_explicit_gate' }
        if ($operation -notin $ordinary) { return 'unknown_operation' }
    }
    return 'eligible_preference'
}

# Pure transition logic accepts a clock only for deterministic boundary tests.
# The CLI below always supplies the actual UTC clock.
function Get-DecisionOutcome-Ming {
    param($Record, $Proposal, $Policy, [DateTimeOffset]$UtcNow)
    $eligible = Get-DecisionEligibility-Ming $Proposal $Policy
    if ($UtcNow -lt [DateTimeOffset]::Parse($Record.updated_at_utc)) { return 'clock_rollback' }
    if ($Record.state -in @('invalidated', 'rejected', 'paused', 'needs_revision')) { return $Record.state }
    if ($Record.response -eq 'reject') { return 'rejected' }
    if ($Record.response -eq 'pause') { return 'paused' }
    if ($Record.response -eq 'change') { return 'needs_revision' }
    if ($eligible -ne 'eligible_preference') { return 'requires_explicit_gate' }
    if ($Record.response -eq 'approve') { return 'user_approved' }
    if (-not $Record.notified_at_utc) { return 'awaiting_notification' }
    $notified = [DateTimeOffset]::Parse($Record.notified_at_utc)
    $deadline = [DateTimeOffset]::Parse($Record.deadline_at_utc)
    if ($deadline -ne $notified.AddSeconds($Policy.Decision.preference_wait_seconds) -or $notified -gt $UtcNow) {
        return 'invalid_timestamps'
    }
    if ($UtcNow -lt $deadline) { return 'waiting_preference' }
    return 'delegated_default'
}

function Write-DecisionRecord-Ming {
    param([string]$Path, $Record, [string]$Event, [string]$Detail, [DateTimeOffset]$UtcNow)
    $Record.updated_at_utc = $UtcNow.ToString('o')
    $Record.history = @($Record.history) + @([PSCustomObject]@{
        event = $Event; at_utc = $Record.updated_at_utc; state = $Record.state
        detail = $Detail; response = $Record.response; response_ref = $Record.response_ref
        notice_ref = $Record.notice_ref
    })
    $temporary = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    try {
        [IO.File]::WriteAllText($temporary, ($Record | ConvertTo-Json -Depth 12), (New-Object Text.UTF8Encoding($false)))
        if (Test-Path -LiteralPath $Path) { [IO.File]::Replace($temporary, $Path, [NullString]::Value) }
        else { [IO.File]::Move($temporary, $Path) }
    } finally {
        if (Test-Path -LiteralPath $temporary) { [IO.File]::Delete($temporary) }
    }
}

function Test-DecisionBinding-Ming {
    param($Record, $Policy, [string]$Root, [string]$Directory)
    if ($Record.project_root -ne $Root) { return 'project_changed' }
    if ($Record.policy_hash -ne $Policy.Hash) { return 'policy_changed' }
    $proposalFile = Join-Path $Directory ($Record.decision_id + '.proposal.json')
    if (-not (Test-Path -LiteralPath $proposalFile -PathType Leaf) -or
        (Get-DecisionHash-Ming $proposalFile) -ne $Record.proposal_hash) { return 'proposal_changed' }
    if (-not (Test-Path -LiteralPath (Join-Path $Root ('.agentos\tasks\' + $Record.task_id + '.md')))) {
        return 'task_missing'
    }
    if (@($Record.fact_sources).Count -eq 0) { return 'facts_missing' }
    foreach ($source in $Record.fact_sources) {
        if (-not (Test-Path -LiteralPath $source.path -PathType Leaf) -or
            (Get-DecisionHash-Ming $source.path) -ne $source.sha256) { return 'fact_source_changed' }
    }
    return 'valid'
}

function Invoke-DecisionTool-Ming {
    if (-not $ProjectRoot -or -not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
        throw 'An existing registered ProjectRoot is required.'
    }
    $root = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $ProjectRoot).Path).TrimEnd('\', '/')
    if (-not (Test-Path -LiteralPath (Join-Path $root '.agentos\project.json'))) { throw 'Register the project first.' }
    $directory = Join-Path $root '.agentos\decisions'
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $policy = Get-DecisionPolicy-Ming
    $lock = $null
    try {
        # A project lock serializes feedback and deadline evaluation across agents.
        $lock = [IO.File]::Open((Join-Path $directory '.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
        $now = [DateTimeOffset]::UtcNow
        if ($Command -notin @('status', 'evaluate') -and -not $DecisionId) { throw 'DecisionId is required.' }
        $path = if ($DecisionId) { Join-Path $directory ($DecisionId + '.json') } else { $null }
        if ($Command -eq 'propose') {
            if (Test-Path -LiteralPath $path) { throw 'Decision already exists; use a new ID for a revised proposal.' }
            if (-not $ProposalPath -or -not (Test-Path -LiteralPath $ProposalPath -PathType Leaf)) { throw 'ProposalPath is required.' }
            $proposal = Get-Content -LiteralPath $ProposalPath -Raw -Encoding UTF8 | ConvertFrom-Json
            Test-DecisionProposal-Ming $proposal
            $taskPath = Join-Path $root ('.agentos\tasks\' + $proposal.task_id + '.md')
            if (-not (Test-Path -LiteralPath $taskPath -PathType Leaf)) { throw 'Proposal must bind an existing task.' }
            $sources = @()
            foreach ($source in $proposal.fact_sources) {
                $sourcePath = [IO.Path]::GetFullPath((Join-Path $root $source))
                if (-not $sourcePath.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
                    -not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) { throw 'Fact sources must be existing files in this project.' }
                $sources += [PSCustomObject]@{ path = $sourcePath; sha256 = Get-DecisionHash-Ming $sourcePath }
            }
            $snapshot = Join-Path $directory ($DecisionId + '.proposal.json')
            [IO.File]::Copy([IO.Path]::GetFullPath($ProposalPath), $snapshot, $false)
            $record = [PSCustomObject][ordered]@{
                schema = 'agentos-decision-v1'; agentos_version = '1.2.0'
                decision_id = $DecisionId; project_root = $root; task_id = $proposal.task_id
                proposal_hash = Get-DecisionHash-Ming $snapshot; policy_hash = $policy.Hash
                fact_sources = $sources; state = 'proposed'; created_at_utc = $now.ToString('o')
                updated_at_utc = $now.ToString('o'); notified_at_utc = $null; deadline_at_utc = $null
                notice_ref = $null; response = $null; response_ref = $null
                adopted_at_utc = $null; adoption_basis = $null; history = @()
            }
            Write-DecisionRecord-Ming $path $record 'proposed' (Get-DecisionEligibility-Ming $proposal $policy) $now
        }
        $paths = if ($path) { @($path) } else {
            @(Get-ChildItem -LiteralPath $directory -Filter '*.json' -File | Where-Object { $_.Name -notlike '*.proposal.json' } | Select-Object -ExpandProperty FullName)
        }
        $reports = @()
        foreach ($currentPath in $paths) {
            if (-not (Test-Path -LiteralPath $currentPath -PathType Leaf)) { throw 'Decision does not exist.' }
            $record = Get-Content -LiteralPath $currentPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($record.decision_id -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{1,80}$' -or
                $record.schema -ne 'agentos-decision-v1') { throw 'Invalid decision record.' }
            if ($now -lt [DateTimeOffset]::Parse($record.updated_at_utc)) { throw 'Clock rollback blocks decision adoption.' }
            $binding = Test-DecisionBinding-Ming $record $policy $root $directory
            if ($Command -eq 'respond') {
                if (-not $Response -or [string]::IsNullOrWhiteSpace($ResponseRef)) { throw 'Real feedback and a traceable ResponseRef are required.' }
                if ($Response -eq 'approve' -and $record.state -in @('invalidated', 'rejected', 'needs_revision')) {
                    throw 'Stopped or revised decisions require a new proposal ID.'
                }
                if ($record.response -ne $Response -or $record.response_ref -ne $ResponseRef) {
                    $record.response = $Response; $record.response_ref = $ResponseRef
                    $record.state = switch ($Response) {
                        'reject' { 'rejected' }; 'pause' { 'paused' }; 'change' { 'needs_revision' }; 'approve' { 'user_approved' }
                    }
                    Write-DecisionRecord-Ming $currentPath $record 'user_feedback' 'Caller must provide actual user feedback; no inferred approval.' $now
                }
            }
            if ($Command -eq 'invalidate') {
                if ([string]::IsNullOrWhiteSpace($Reason)) { throw 'Invalidation Reason is required.' }
                if ($record.state -ne 'invalidated') {
                    $record.state = 'invalidated'
                    Write-DecisionRecord-Ming $currentPath $record 'invalidated' $Reason $now
                }
            }
            if ($binding -ne 'valid') {
                $outcome = 'invalidated'
                if ($Command -ne 'status' -and $record.state -notin @('invalidated', 'rejected', 'paused', 'needs_revision')) {
                    $record.state = 'invalidated'
                    Write-DecisionRecord-Ming $currentPath $record 'invalidated' $binding $now
                }
            } else {
                $proposal = Get-Content -LiteralPath (Join-Path $directory ($record.decision_id + '.proposal.json')) -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($Command -eq 'notify') {
                    if ([string]::IsNullOrWhiteSpace($NoticeRef)) { throw 'NoticeRef must identify the actual sent notice.' }
                    if ($record.state -in @('invalidated', 'rejected', 'paused', 'needs_revision')) { throw 'Cannot notify a stopped decision; create a revised proposal.' }
                    if (-not $record.notified_at_utc) {
                        $record.notified_at_utc = $now.ToString('o'); $record.notice_ref = $NoticeRef
                        $record.deadline_at_utc = $now.AddSeconds($policy.Decision.preference_wait_seconds).ToString('o')
                        Write-DecisionRecord-Ming $currentPath $record 'notified' 'Notice delivered before this call; deadline starts now.' $now
                    }
                }
                $outcome = Get-DecisionOutcome-Ming $record $proposal $policy $now
                if ($Command -eq 'evaluate' -and $outcome -ne $record.state) {
                    $record.state = $outcome
                    if ($outcome -in @('delegated_default', 'user_approved')) {
                        if (-not $record.adopted_at_utc) { $record.adopted_at_utc = $now.ToString('o') }
                        $record.adoption_basis = $outcome
                    }
                    Write-DecisionRecord-Ming $currentPath $record 'evaluated' (Get-DecisionEligibility-Ming $proposal $policy) $now
                }
            }
            $reports += [PSCustomObject]@{
                decision_id = $record.decision_id; task_id = $record.task_id
                state = $record.state; outcome = $outcome; binding = $binding
                proceed = ($binding -eq 'valid' -and $outcome -in @('delegated_default', 'user_approved') -and
                    $Command -ne 'status')
                deadline_at_utc = $record.deadline_at_utc; response = $record.response
                adoption_basis = $record.adoption_basis; record_path = $currentPath
                permission_note = 'Choice only. Required evidence, project safety and native tool permission gates remain in force.'
            }
        }
        ConvertTo-Json -InputObject @($reports) -Depth 8
    } finally {
        if ($lock) { $lock.Dispose() }
    }
}

if ($MyInvocation.InvocationName -ne '.') { Invoke-DecisionTool-Ming }
