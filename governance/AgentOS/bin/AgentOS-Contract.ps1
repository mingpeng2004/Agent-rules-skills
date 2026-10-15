#Requires -Version 5.1

[CmdletBinding()]
param(
    [ValidateSet('init', 'set', 'confirm', 'amend-propose', 'amend-notify', 'amend-respond', 'amend-evaluate', 'check', 'status')]
    [string]$Command = 'status',
    [string]$ProjectRoot,
    [string]$Domain,
    [string]$Decision,
    [ValidateSet('confirmed', 'pending', 'deferred', 'not_applicable')]
    [string]$State = 'confirmed',
    [ValidateSet('user', 'project_ssot', 'derived', 'none')]
    [string]$SourceType = 'none',
    [string]$SourceRef,
    [string]$Rationale,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.-]{1,80}$')]
    [string]$AmendmentId,
    [string]$AmendmentPath,
    [string]$NoticeRef,
    [ValidateSet('approve', 'reject', 'pause', 'change')]
    [string]$Response,
    [string]$ResponseRef,
    [string]$WaiverRef
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:ContractOsRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))

function Get-ContractHash-Ming {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Get-ContractPolicy-Ming {
    $interactionPath = Join-Path $script:ContractOsRoot 'policies\INTERACTION-POLICY.json'
    $approvalPath = Join-Path $script:ContractOsRoot 'policies\APPROVAL-POLICY.json'
    $decisionPath = Join-Path $script:ContractOsRoot 'policies\DECISION-POLICY.json'
    $interaction = Get-Content -LiteralPath $interactionPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $approval = Get-Content -LiteralPath $approvalPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $decision = Get-Content -LiteralPath $decisionPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($interaction.tiers.preference.timeout_default_seconds -ne 300) { throw 'Unexpected preference deadline; review INTERACTION-POLICY before use.' }
    return [PSCustomObject]@{
        Interaction = $interaction
        Approval = $approval
        Decision = $decision
        Domains = @($interaction.tiers.contract.domains)
        Hash = ((Get-ContractHash-Ming $interactionPath) + ':' + (Get-ContractHash-Ming $approvalPath) + ':' + (Get-ContractHash-Ming $decisionPath))
    }
}

function Get-ContractRecordPath-Ming {
    param([string]$Root)
    return (Join-Path $Root '.agentos\contract\contract.json')
}

function New-ContractRecord-Ming {
    param([string]$Root, $Policy, [DateTimeOffset]$Now)
    $sections = [ordered]@{}
    foreach ($domain in $Policy.Domains) {
        $sections[$domain] = [PSCustomObject]@{
            state = 'pending'; decision = $null; rationale = $null
            source_type = 'none'; source_ref = $null; decided_at = $null
            decided_by = 'unassigned'; waiver_ref = $null
        }
    }
    return [PSCustomObject][ordered]@{
        schema = 'agentos-contract-v1'
        agentos_version = (Get-Content -LiteralPath (Join-Path $script:ContractOsRoot 'VERSION') -Raw -Encoding UTF8).Trim()
        project_root = $Root
        contract_version = 0
        status = 'draft'
        created_at = $Now.ToString('o')
        updated_at = $Now.ToString('o')
        confirmed_at = $null
        policy_hash = $Policy.Hash
        enforcement = 'advisory'
        sections = $sections
        amendments = @()
        history = @()
    }
}

function Save-ContractRecord-Ming {
    param([string]$Path, $Record, [string]$Event, [string]$Detail, [DateTimeOffset]$Now)
    $Record.updated_at = $Now.ToString('o')
    $Record.history = @($Record.history) + @([PSCustomObject]@{
        event = $Event; at = $Record.updated_at; version = $Record.contract_version
        status = $Record.status; detail = $Detail
    })
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $temporary = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    try {
        [IO.File]::WriteAllText($temporary, ($Record | ConvertTo-Json -Depth 14), (New-Object Text.UTF8Encoding($false)))
        if (Test-Path -LiteralPath $Path) { [IO.File]::Replace($temporary, $Path, [NullString]::Value) }
        else { [IO.File]::Move($temporary, $Path) }
    } finally {
        if (Test-Path -LiteralPath $temporary) { [IO.File]::Delete($temporary) }
    }
}

function Get-ContractUnresolved-Ming {
    param($Record)
    $unresolved = @()
    foreach ($property in $Record.sections.PSObject.Properties) {
        if ($property.Value.state -eq 'pending') { $unresolved += $property.Name }
    }
    return $unresolved
}

function Test-ContractDomainDecision-Ming {
    param($Record, $Policy, [string]$DomainName, [string]$NewState, [string]$DecisionText, [string]$NewSourceType, [string]$NewSourceRef, [string]$Waiver)
    if ($Policy.Domains -notcontains $DomainName) { throw "Unknown contract domain: $DomainName" }
    if ($NewState -eq 'confirmed' -and [string]::IsNullOrWhiteSpace($DecisionText)) { throw 'A confirmed domain requires a decision text.' }
    if ($NewState -eq 'confirmed' -and [string]::IsNullOrWhiteSpace($NewSourceRef)) { throw 'A confirmed domain requires a traceable source reference.' }
    if ($NewState -eq 'deferred' -and [string]::IsNullOrWhiteSpace($Waiver)) { throw 'A deferred domain requires an owner waiver reference.' }
    if ($NewSourceType -eq 'user' -and $NewState -eq 'confirmed' -and [string]::IsNullOrWhiteSpace($NewSourceRef)) {
        throw 'User-confirmed decisions require the real message reference.'
    }
    return $true
}

function Get-AmendmentOutcome-Ming {
    param($Amendment, $Proposal, $Policy, [DateTimeOffset]$Now)
    if ($Now -lt [DateTimeOffset]::Parse($Amendment.updated_at)) { return 'clock_rollback' }
    if ($Amendment.state -in @('rejected', 'paused', 'needs_revision', 'invalidated', 'applied')) { return $Amendment.state }
    if ($Amendment.response -eq 'reject') { return 'rejected' }
    if ($Amendment.response -eq 'pause') { return 'paused' }
    if ($Amendment.response -eq 'change') { return 'needs_revision' }
    if ($Amendment.response -eq 'approve') { return 'user_approved' }
    if ($Amendment.kind -eq 'contract') {
        if (-not $Amendment.notified_at) { return 'awaiting_notification' }
        return 'awaiting_user_confirmation'
    }
    if (-not $Amendment.notified_at) { return 'awaiting_notification' }
    $notified = [DateTimeOffset]::Parse($Amendment.notified_at)
    $deadline = [DateTimeOffset]::Parse($Amendment.deadline_at)
    if ($deadline -ne $notified.AddSeconds($Policy.Interaction.tiers.preference.timeout_default_seconds) -or $notified -gt $Now) { return 'invalid_timestamps' }
    if ($Now -lt $deadline) { return 'waiting_preference' }
    return 'delegated_default'
}

function Get-ContractDrift-Ming {
    param($Record, $Policy, [string]$Root, [string[]]$TaskFiles)
    $findings = @()
    if ($Record.status -eq 'confirmed') {
        $unresolved = @(Get-ContractUnresolved-Ming $Record)
        if ($unresolved.Count -gt 0) { $findings += [PSCustomObject]@{ code = 'confirmed_with_unresolved'; severity = 'blocking'; detail = ($unresolved -join ',') } }
    } elseif ($Record.status -eq 'draft') {
        $unresolved = @(Get-ContractUnresolved-Ming $Record)
        $severity = if ($Record.enforcement -eq 'required') { 'blocking' } else { 'advisory' }
        $findings += [PSCustomObject]@{ code = 'contract_draft'; severity = $severity; detail = "unresolved=$($unresolved.Count)" }
    }
    $pendingAmendments = @($Record.amendments | Where-Object { $_.state -in @('proposed', 'awaiting_notification', 'waiting_preference', 'awaiting_user_confirmation') })
    if ($pendingAmendments.Count -gt 0) {
        $findings += [PSCustomObject]@{ code = 'pending_amendments'; severity = 'blocking'; detail = (@($pendingAmendments | ForEach-Object { $_.amendment_id }) -join ',') }
    }
    foreach ($taskFile in $TaskFiles) {
        $content = Get-Content -LiteralPath $taskFile -Raw -Encoding UTF8
        $versionMatch = [regex]::Match($content, 'contract_version:\s*(\d+)')
        if (-not $versionMatch.Success) {
            $findings += [PSCustomObject]@{ code = 'unbound_task'; severity = 'informational'; detail = (Split-Path -Leaf $taskFile) }
            continue
        }
        $taskVersion = [int]$versionMatch.Groups[1].Value
        if ($taskVersion -gt $Record.contract_version) {
            $findings += [PSCustomObject]@{ code = 'task_ahead_of_contract'; severity = 'blocking'; detail = (Split-Path -Leaf $taskFile) }
            continue
        }
        if ($taskVersion -lt $Record.contract_version) {
            $scopeMatch = [regex]::Match($content, 'contract_sections_in_scope:\s*(.+)')
            $scope = if ($scopeMatch.Success) { @($scopeMatch.Groups[1].Value -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }) } else { @() }
            $changed = @()
            foreach ($applied in @($Record.amendments | Where-Object { $_.state -eq 'applied' })) {
                foreach ($section in $applied.sections_touched) { if ($scope -contains $section) { $changed += $section } }
            }
            $severity = if ($changed.Count -gt 0) { 'blocking' } else { 'advisory' }
            $findings += [PSCustomObject]@{ code = 'stale_task_contract'; severity = $severity; detail = "$((Split-Path -Leaf $taskFile)) task_v$taskVersion contract_v$($Record.contract_version) changed=$($changed -join ',')" }
        }
    }
    return $findings
}

function Invoke-ContractTool-Ming {
    if (-not $ProjectRoot -or -not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) { throw 'An existing registered ProjectRoot is required.' }
    $root = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $ProjectRoot).Path).TrimEnd('\', '/')
    if (-not (Test-Path -LiteralPath (Join-Path $root '.agentos\project.json'))) { throw 'Register the project first.' }
    $contractDir = Join-Path $root '.agentos\contract'
    New-Item -ItemType Directory -Force -Path $contractDir | Out-Null
    $policy = Get-ContractPolicy-Ming
    $lock = $null
    try {
        $lock = [IO.File]::Open((Join-Path $contractDir '.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
        $now = [DateTimeOffset]::UtcNow
        $recordPath = Get-ContractRecordPath-Ming $root

        if ($Command -eq 'init') {
            if (Test-Path -LiteralPath $recordPath) { throw 'Contract already exists; use amend-propose to change it.' }
            $record = New-ContractRecord-Ming $root $policy $now
            Save-ContractRecord-Ming $recordPath $record 'init' ("domains=$($policy.Domains.Count)") $now
        }
        if (-not (Test-Path -LiteralPath $recordPath)) { throw 'No contract found; run init first.' }
        $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($record.project_root -ne $root) { throw 'Contract belongs to a different project root.' }
        if ($now -lt [DateTimeOffset]::Parse($record.updated_at)) { throw 'Clock rollback blocks contract updates.' }

        switch ($Command) {
            'init' { }
            'set' {
                if (-not $Domain) { throw 'Domain is required.' }
                $null = Test-ContractDomainDecision-Ming $record $policy $Domain $State $Decision $SourceType $SourceRef $WaiverRef
                $current = $record.sections.$Domain
                $same = ($current.state -eq $State) -and ($current.decision -eq $Decision) -and ($current.source_ref -eq $SourceRef) -and ($current.source_type -eq $SourceType)
                if (-not $same) {
                    $record.sections.$Domain = [PSCustomObject]@{
                        state = $State
                        decision = if ($State -eq 'pending') { $null } else { $Decision }
                        rationale = $Rationale
                        source_type = if ($State -eq 'pending') { 'none' } else { $SourceType }
                        source_ref = if ($State -eq 'pending') { $null } else { $SourceRef }
                        decided_at = if ($State -eq 'pending') { $null } else { $now.ToString('o') }
                        decided_by = if ($SourceType -eq 'user') { 'user' } elseif ($SourceType -eq 'project_ssot') { 'project_ssot' } else { 'agent' }
                        waiver_ref = if ($State -eq 'deferred') { $WaiverRef } else { $null }
                    }
                    Save-ContractRecord-Ming $recordPath $record 'domain_set' "$Domain=$State" $now
                }
            }
            'confirm' {
                if ($record.status -eq 'confirmed') {
                    if ($record.confirmed_at) { throw 'Contract is already confirmed; use amend-propose to change it.' }
                }
                $unresolved = @(Get-ContractUnresolved-Ming $record)
                if ($unresolved.Count -gt 0) { throw ("Contract cannot be sealed; unresolved domains: " + ($unresolved -join ', ')) }
                if ($record.status -ne 'confirmed') {
                    $record.status = 'confirmed'
                    $record.confirmed_at = $now.ToString('o')
                    if ($record.contract_version -lt 1) { $record.contract_version = 1 }
                    Save-ContractRecord-Ming $recordPath $record 'confirmed' "version=$($record.contract_version)" $now
                }
            }
            'amend-propose' {
                if (-not $AmendmentId) { throw 'AmendmentId is required.' }
                if (-not $AmendmentPath -or -not (Test-Path -LiteralPath $AmendmentPath -PathType Leaf)) { throw 'AmendmentPath must point to an existing proposal file.' }
                $proposal = Get-Content -LiteralPath $AmendmentPath -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($proposal.kind -notin @('contract', 'preference')) { throw 'Amendment kind must be contract or preference.' }
                if ([string]::IsNullOrWhiteSpace($proposal.summary)) { throw 'Amendment summary is required.' }
                if (-not $proposal.PSObject.Properties['sections'] -or -not $proposal.sections.PSObject.Properties) { throw 'Amendment must carry at least one section decision.' }
                $touched = @()
                foreach ($property in $proposal.sections.PSObject.Properties) {
                    if ($policy.Domains -notcontains $property.Name) { throw "Amendment touches unknown domain: $($property.Name)" }
                    $touched += $property.Name
                    if ($proposal.kind -eq 'contract' -and [string]::IsNullOrWhiteSpace($property.Value.decision)) { throw "Amendment section requires a decision: $($property.Name)" }
                }
                $sources = @()
                foreach ($source in @($proposal.fact_sources)) {
                    if ([string]::IsNullOrWhiteSpace($source)) { throw 'Amendment fact source entries must be non-empty.' }
                    $sources += $source
                }
                if (@($record.amendments | Where-Object { $_.amendment_id -eq $AmendmentId }).Count -gt 0) { throw 'Amendment id already exists; use a new id.' }
                $snapshot = Join-Path $contractDir ("amendment-$AmendmentId.json")
                Copy-Item -LiteralPath $AmendmentPath -Destination $snapshot -Force
                $record.amendments = @($record.amendments) + @([PSCustomObject][ordered]@{
                    amendment_id = $AmendmentId; kind = $proposal.kind; summary = $proposal.summary
                    sections_touched = $touched; proposal_snapshot = $snapshot
                    proposal_sha256 = Get-ContractHash-Ming $snapshot
                    impact = $proposal.impact; rollback = $proposal.rollback
                    fact_sources = $sources; affected_tasks = @($proposal.affected_tasks)
                    state = 'proposed'; response = $null; response_ref = $null
                    notified_at = $null; notice_ref = $null; deadline_at = $null
                    created_at = $now.ToString('o'); updated_at = $now.ToString('o')
                    decided_at = $null; outcome = $null; before = $null; after = $null
                })
                Save-ContractRecord-Ming $recordPath $record 'amend_propose' "$AmendmentId kind=$($proposal.kind) sections=$($touched -join ',')" $now
            }
            default {
                $amendment = @()
                if ($Command -notin @('check', 'status')) {
                    $amendment = @($record.amendments | Where-Object { $_.amendment_id -eq $AmendmentId })
                    if ($amendment.Count -eq 0) { throw "Amendment not found: $AmendmentId" }
                    $amendment = $amendment[0]
                }
                if ($Command -notin @('check', 'status') -and
                    (-not (Test-Path -LiteralPath $amendment.proposal_snapshot -PathType Leaf) -or
                    (Get-ContractHash-Ming $amendment.proposal_snapshot) -ne $amendment.proposal_sha256)) {
                    if ($amendment.state -ne 'invalidated') {
                        $amendment.state = 'invalidated'
                        $amendment.updated_at = $now.ToString('o')
                        Save-ContractRecord-Ming $recordPath $record 'amend_invalidated' "$AmendmentId proposal_changed" $now
                    }
                    throw 'Amendment proposal changed on disk; propose a new amendment id.'
                }
                switch ($Command) {
                    'amend-notify' {
                        if ([string]::IsNullOrWhiteSpace($NoticeRef)) { throw 'NoticeRef must identify the actual sent notice.' }
                        if ($amendment.state -in @('rejected', 'paused', 'needs_revision', 'invalidated', 'applied')) { throw 'Cannot notify a stopped amendment.' }
                        if (-not $amendment.notified_at) {
                            $amendment.notified_at = $now.ToString('o')
                            $amendment.notice_ref = $NoticeRef
                            if ($amendment.kind -eq 'preference') { $amendment.deadline_at = $now.AddSeconds($policy.Interaction.tiers.preference.timeout_default_seconds).ToString('o') }
                            else { $amendment.deadline_at = $null }
                            Save-ContractRecord-Ming $recordPath $record 'amend_notify' "$AmendmentId deadline=$($amendment.deadline_at)" $now
                        }
                    }
                    'amend-respond' {
                        if (-not $Response -or [string]::IsNullOrWhiteSpace($ResponseRef)) { throw 'Real feedback and a traceable ResponseRef are required.' }
                        if ($amendment.state -eq 'invalidated') { throw 'An invalidated amendment cannot be resurrected; propose a new id.' }
                        if ($amendment.response -ne $Response -or $amendment.response_ref -ne $ResponseRef) {
                            $amendment.response = $Response
                            $amendment.response_ref = $ResponseRef
                            $amendment.state = switch ($Response) { 'reject' { 'rejected' }; 'pause' { 'paused' }; 'change' { 'needs_revision' }; 'approve' { 'approved' } }
                            $amendment.updated_at = $now.ToString('o')
                            Save-ContractRecord-Ming $recordPath $record 'amend_feedback' "$AmendmentId response=$Response" $now
                        }
                    }
                    'amend-evaluate' {
                        $proposal = Get-Content -LiteralPath $amendment.proposal_snapshot -Raw -Encoding UTF8 | ConvertFrom-Json
                        $outcome = Get-AmendmentOutcome-Ming $amendment $proposal $policy $now
                        if ($outcome -in @('delegated_default', 'user_approved')) {
                            $before = [ordered]@{}
                            $after = [ordered]@{}
                            foreach ($property in $proposal.sections.PSObject.Properties) {
                                $before[$property.Name] = $record.sections.$($property.Name).decision
                                $record.sections.$($property.Name) = [PSCustomObject]@{
                                    state = 'confirmed'
                                    decision = $property.Value.decision
                                    rationale = $property.Value.rationale
                                    source_type = if ($amendment.kind -eq 'contract') { 'user' } else { 'derived' }
                                    source_ref = $amendment.response_ref
                                    decided_at = $now.ToString('o')
                                    decided_by = if ($amendment.kind -eq 'contract') { 'user' } else { 'agent_delegated' }
                                    waiver_ref = $null
                                }
                                $after[$property.Name] = $property.Value.decision
                            }
                            $amendment.before = [PSCustomObject]$before
                            $amendment.after = [PSCustomObject]$after
                            $amendment.state = 'applied'
                            $amendment.outcome = $outcome
                            $amendment.decided_at = $now.ToString('o')
                            $record.contract_version = [int]$record.contract_version + 1
                            $record.policy_hash = $policy.Hash
                            Save-ContractRecord-Ming $recordPath $record 'amend_applied' "$AmendmentId outcome=$outcome version=$($record.contract_version)" $now
                        } elseif ($outcome -ne $amendment.state) {
                            $amendment.state = $outcome
                            $amendment.outcome = $outcome
                            $amendment.updated_at = $now.ToString('o')
                            Save-ContractRecord-Ming $recordPath $record 'amend_evaluate' "$AmendmentId outcome=$outcome" $now
                        }
                    }
                    'check' {
                        $taskDir = Join-Path $root '.agentos\tasks'
                        $taskFiles = @()
                        if (Test-Path -LiteralPath $taskDir) { $taskFiles = @(Get-ChildItem -LiteralPath $taskDir -Filter '*.md' -File | Select-Object -ExpandProperty FullName) }
                        $findings = Get-ContractDrift-Ming $record $policy $root $taskFiles
                        $blocking = @($findings | Where-Object { $_.severity -eq 'blocking' })
                        $report = [ordered]@{
                            schema = 'agentos-contract-check-v1'
                            generated_at = $now.ToString('o')
                            project_root = $root
                            contract_version = $record.contract_version
                            status = $record.status
                            unresolved_domains = @(Get-ContractUnresolved-Ming $record)
                            pending_amendments = @($record.amendments | Where-Object { $_.state -in @('proposed', 'awaiting_notification', 'waiting_preference', 'awaiting_user_confirmation') } | ForEach-Object { $_.amendment_id })
                            findings = $findings
                            blocking_count = $blocking.Count
                            pass = ($blocking.Count -eq 0)
                        }
                        $report | ConvertTo-Json -Depth 10
                        if ($blocking.Count -gt 0) { exit 2 }
                        exit 0
                    }
                    'status' {
                        $taskDir = Join-Path $root '.agentos\tasks'
                        $taskFiles = @()
                        if (Test-Path -LiteralPath $taskDir) { $taskFiles = @(Get-ChildItem -LiteralPath $taskDir -Filter '*.md' -File | Select-Object -ExpandProperty FullName) }
                        $findings = Get-ContractDrift-Ming $record $policy $root $taskFiles
                        [ordered]@{
                            schema = 'agentos-contract-status-v1'
                            generated_at = $now.ToString('o')
                            project_root = $root
                            contract_version = $record.contract_version
                            status = $record.status
                            enforcement = $record.enforcement
                            confirmed_at = $record.confirmed_at
                            domains = @($record.sections.PSObject.Properties | ForEach-Object {
                                [ordered]@{ domain = $_.Name; state = $_.Value.state; source_type = $_.Value.source_type; source_ref = $_.Value.source_ref }
                            })
                            unresolved_domains = @(Get-ContractUnresolved-Ming $record)
                            amendments = @($record.amendments | ForEach-Object { [ordered]@{ id = $_.amendment_id; kind = $_.kind; state = $_.state; outcome = $_.outcome } })
                            drift_findings = $findings
                        } | ConvertTo-Json -Depth 10
                        return
                    }
                }
            }
        }

        $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
        [ordered]@{
            schema = 'agentos-contract-result-v1'
            command = $Command
            contract_version = $record.contract_version
            status = $record.status
            unresolved_domains = @(Get-ContractUnresolved-Ming $record)
            pending_amendments = @($record.amendments | Where-Object { $_.state -in @('proposed', 'awaiting_notification', 'waiting_preference', 'awaiting_user_confirmation') } | ForEach-Object { $_.amendment_id })
            record_path = $recordPath
        } | ConvertTo-Json -Depth 8
    } finally {
        if ($lock) { $lock.Dispose() }
    }
}

if ($MyInvocation.InvocationName -ne '.') { Invoke-ContractTool-Ming }