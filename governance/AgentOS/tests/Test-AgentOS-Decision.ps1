#Requires -Version 5.1

[CmdletBinding()]
param([string]$AgentOsRoot)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $AgentOsRoot) { $AgentOsRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')) }
$tool = Join-Path $AgentOsRoot 'bin\AgentOS-Decision.ps1'
. $tool
$policy = Get-DecisionPolicy-Ming
$fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ('AgentOS-Decision-test-' + [Guid]::NewGuid().ToString('N'))
$script:Checks = 0
$encoding = New-Object Text.UTF8Encoding($false)

function Assert-Decision-Ming {
    param([bool]$Condition, [string]$Name)
    if (-not $Condition) { throw "Decision test failed: $Name" }
    $script:Checks++
}

function Write-DecisionFixture-Ming {
    param([string]$Path, $Value)
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 12), $encoding)
}

function Invoke-DecisionFixture-Ming {
    param([string]$Action, [string]$Id = 'choice_01', [hashtable]$Extra = @{})
    $output = & $tool -Command $Action -ProjectRoot $fixtureRoot -DecisionId $Id @Extra
    return @(($output | Out-String | ConvertFrom-Json))[0]
}

function Assert-DecisionThrows-Ming {
    param([scriptblock]$Action, [string]$Name)
    $threw = $false
    try { & $Action | Out-Null } catch { $threw = $true }
    Assert-Decision-Ming $threw $Name
}

try {
    New-Item -ItemType Directory -Path (Join-Path $fixtureRoot '.agentos\tasks') -Force | Out-Null
    Write-DecisionFixture-Ming (Join-Path $fixtureRoot '.agentos\project.json') @{ fixture = $true }
    [IO.File]::WriteAllText((Join-Path $fixtureRoot '.agentos\tasks\fixture_task.md'), 'Synthetic test task only', $encoding)
    [IO.File]::WriteAllText((Join-Path $fixtureRoot 'facts.txt'), 'Synthetic test basis only', $encoding)
    $proposal = [PSCustomObject]@{
        task_id = 'fixture_task'; title = 'Synthetic preference fixture'; kind = 'preference'
        recommendation = 'Use local reversible implementation'; scope = 'Fixture project'
        impact = 'No external effect'; rollback = 'Restore fixture'
        operations = @('implementation_choice', 'edit_code', 'run_tests')
        facts_ready = $true; reversible = $true; within_user_goal = $true
        changes_security_boundary = $false; fact_sources = @('facts.txt')
    }
    $inputFile = Join-Path $fixtureRoot 'input.json'
    Write-DecisionFixture-Ming $inputFile $proposal
    $r = Invoke-DecisionFixture-Ming 'propose' 'choice_01' @{ ProposalPath = $inputFile }
    Assert-Decision-Ming (-not $r.proceed -and $r.outcome -eq 'awaiting_notification') 'proposal does not imply delivery or approval'
    Assert-DecisionThrows-Ming { Invoke-DecisionFixture-Ming 'notify' 'choice_01' } 'no notification reference'
    Assert-DecisionThrows-Ming { Invoke-DecisionFixture-Ming 'respond' 'choice_01' @{ Response = 'approve' } } 'no feedback reference'
    $r = Invoke-DecisionFixture-Ming 'notify' 'choice_01' @{ NoticeRef = 'synthetic://test-notification' }
    Assert-Decision-Ming (-not $r.proceed -and $r.outcome -eq 'waiting_preference') 'real CLI starts in waiting state'
    $recordPath = Join-Path $fixtureRoot '.agentos\decisions\choice_01.json'
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $notified = [DateTimeOffset]::Parse($record.notified_at_utc)
    Assert-Decision-Ming (([DateTimeOffset]::Parse($record.deadline_at_utc) - $notified).TotalSeconds -eq 300) 'deadline exactly 300 seconds'
    $r = Invoke-DecisionFixture-Ming 'notify' 'choice_01' @{ NoticeRef = 'synthetic://repeat' }
    $again = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-Decision-Ming ($again.notified_at_utc -eq $record.notified_at_utc -and $again.history.Count -eq $record.history.Count) 'repeat notification preserves original clock'

    Assert-Decision-Ming ((Get-DecisionOutcome-Ming $record $proposal $policy $notified.AddSeconds(299)) -eq 'waiting_preference') '299 seconds cannot default'
    Assert-Decision-Ming ((Get-DecisionOutcome-Ming $record $proposal $policy $notified.AddSeconds(300)) -eq 'delegated_default') '300 seconds defaults by delegation'
    Assert-Decision-Ming ((Get-DecisionOutcome-Ming $again $proposal $policy $notified.AddSeconds(500)) -eq 'delegated_default') 'reloaded record preserves deadline'
    Assert-Decision-Ming ((Get-DecisionOutcome-Ming $record $proposal $policy $notified.AddSeconds(-1)) -eq 'clock_rollback') 'backward clock blocks'
    $record.notified_at_utc = $null
    Assert-Decision-Ming ((Get-DecisionOutcome-Ming $record $proposal $policy $notified.AddDays(2)) -eq 'awaiting_notification') 'unnotified proposal never defaults'
    $record.notified_at_utc = $notified.ToString('o')
    foreach ($kind in @('safety', 'missing_facts', 'host_approval', 'user_acceptance', 'unknown', 'unrecognized')) {
        $proposal.kind = $kind
        Assert-Decision-Ming ((Get-DecisionOutcome-Ming $record $proposal $policy $notified.AddDays(2)) -eq 'requires_explicit_gate') "blocked kind: $kind"
    }
    $proposal.kind = 'preference'
    foreach ($operation in @($policy.Approval.always_single_approval) + @('unknown_action')) {
        $proposal.operations = @('edit_code', $operation)
        Assert-Decision-Ming ((Get-DecisionOutcome-Ming $record $proposal $policy $notified.AddDays(2)) -eq 'requires_explicit_gate') "blocked operation: $operation"
    }
    $proposal.operations = @('implementation_choice', 'edit_code', 'run_tests')
    foreach ($name in @('facts_ready', 'reversible', 'within_user_goal', 'changes_security_boundary')) {
        $original = $proposal.$name
        $proposal.$name = -not $original
        Assert-Decision-Ming ((Get-DecisionOutcome-Ming $record $proposal $policy $notified.AddDays(2)) -eq 'requires_explicit_gate') "blocked flag: $name"
        $proposal.$name = $original
    }
    foreach ($response in @('reject', 'pause', 'change')) {
        $record.response = $response
        $expected = @{ reject = 'rejected'; pause = 'paused'; change = 'needs_revision' }[$response]
        Assert-Decision-Ming ((Get-DecisionOutcome-Ming $record $proposal $policy $notified.AddDays(2)) -eq $expected) "late feedback wins: $response"
    }
    $record.response = $null
    $record.deadline_at_utc = $notified.AddSeconds(299).ToString('o')
    Assert-Decision-Ming ((Get-DecisionOutcome-Ming $record $proposal $policy $notified.AddDays(2)) -eq 'invalid_timestamps') 'shortened deadline invalid'
    $record.deadline_at_utc = $notified.AddSeconds(300).ToString('o')
    $changedPolicy = [PSCustomObject]@{ Decision = $policy.Decision; Approval = $policy.Approval; Hash = 'changed' }
    Assert-Decision-Ming ((Test-DecisionBinding-Ming $record $changedPolicy $fixtureRoot (Join-Path $fixtureRoot '.agentos\decisions')) -eq 'policy_changed') 'policy version change blocks old choice'

    $r = Invoke-DecisionFixture-Ming 'evaluate'
    $firstEvaluation = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $r = Invoke-DecisionFixture-Ming 'evaluate'
    $secondEvaluation = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-Decision-Ming ($firstEvaluation.history.Count -eq $secondEvaluation.history.Count) 'unchanged evaluation is idempotent'
    $r = Invoke-DecisionFixture-Ming 'respond' 'choice_01' @{ Response = 'approve'; ResponseRef = 'synthetic://user-approve-fixture' }
    Assert-Decision-Ming ($r.proceed -and $r.outcome -eq 'user_approved') 'ordinary explicit feedback can proceed'
    $r = Invoke-DecisionFixture-Ming 'respond' 'choice_01' @{ Response = 'pause'; ResponseRef = 'synthetic://user-pause-fixture' }
    Assert-Decision-Ming (-not $r.proceed -and $r.outcome -eq 'paused') 'pause stops future work'
    $r = Invoke-DecisionFixture-Ming 'propose' 'due_01' @{ ProposalPath = $inputFile }
    $duePath = Join-Path $fixtureRoot '.agentos\decisions\due_01.json'
    $due = Get-Content -LiteralPath $duePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $syntheticNotice = [DateTimeOffset]::UtcNow.AddSeconds(-301)
    $due.notified_at_utc = $syntheticNotice.ToString('o')
    $due.deadline_at_utc = $syntheticNotice.AddSeconds(300).ToString('o')
    $due.updated_at_utc = $syntheticNotice.ToString('o')
    $due.notice_ref = 'synthetic://past-notice-test-fixture'
    Write-DecisionFixture-Ming $duePath $due
    $r = Invoke-DecisionFixture-Ming 'evaluate' 'due_01'
    Assert-Decision-Ming ($r.proceed -and $r.outcome -eq 'delegated_default' -and $r.adoption_basis -eq 'delegated_default') 'elapsed synthetic record persists delegated adoption'
    $savedDue = Get-Content -LiteralPath $duePath -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-Decision-Ming ($null -eq $savedDue.response -and $null -ne $savedDue.adopted_at_utc) 'timeout does not fabricate feedback'
    $r = Invoke-DecisionFixture-Ming 'evaluate' 'due_01'
    $againDue = Get-Content -LiteralPath $duePath -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-Decision-Ming ($againDue.history.Count -eq $savedDue.history.Count) 'delegated adoption repeat is idempotent'
    $r = Invoke-DecisionFixture-Ming 'respond' 'due_01' @{ Response = 'reject'; ResponseRef = 'synthetic://late-rejection-fixture' }
    Assert-Decision-Ming (-not $r.proceed -and $r.outcome -eq 'rejected' -and $r.adoption_basis -eq 'delegated_default') 'late rejection stops and retains prior basis'
    $heldLock = [IO.File]::Open((Join-Path $fixtureRoot '.agentos\decisions\.lock'), 'Open', 'ReadWrite', 'None')
    try { Assert-DecisionThrows-Ming { Invoke-DecisionFixture-Ming 'evaluate' 'due_01' } 'concurrent caller fails rather than races' }
    finally { $heldLock.Dispose() }
    $r = Invoke-DecisionFixture-Ming 'propose' 'choice_02' @{ ProposalPath = $inputFile }
    [IO.File]::AppendAllText((Join-Path $fixtureRoot '.agentos\decisions\choice_02.proposal.json'), "`n", $encoding)
    $r = Invoke-DecisionFixture-Ming 'evaluate' 'choice_02'
    Assert-Decision-Ming (-not $r.proceed -and $r.binding -eq 'proposal_changed') 'changed proposal invalidates'
    $r = Invoke-DecisionFixture-Ming 'propose' 'choice_03' @{ ProposalPath = $inputFile }
    [IO.File]::AppendAllText((Join-Path $fixtureRoot 'facts.txt'), ' changed', $encoding)
    $r = Invoke-DecisionFixture-Ming 'evaluate' 'choice_03'
    Assert-Decision-Ming (-not $r.proceed -and $r.binding -eq 'fact_source_changed') 'changed fact source invalidates'

    $proposal.kind = 'safety'; $proposal.operations = @('firmware_flash')
    Write-DecisionFixture-Ming $inputFile $proposal
    $r = Invoke-DecisionFixture-Ming 'propose' 'safety_01' @{ ProposalPath = $inputFile }
    $r = Invoke-DecisionFixture-Ming 'respond' 'safety_01' @{ Response = 'approve'; ResponseRef = 'synthetic://safety-feedback-fixture' }
    Assert-Decision-Ming (-not $r.proceed -and $r.outcome -eq 'requires_explicit_gate') 'safety feedback does not bypass operation gate'
    $r = Invoke-DecisionFixture-Ming 'invalidate' 'safety_01' @{ Reason = 'fixture stopped' }
    Assert-DecisionThrows-Ming { Invoke-DecisionFixture-Ming 'respond' 'safety_01' @{ Response = 'approve'; ResponseRef = 'synthetic://later-feedback' } } 'invalidated decision cannot be resurrected'
    $proposal.kind = 'preference'; $proposal.fact_sources = @('..\outside.txt')
    Write-DecisionFixture-Ming $inputFile $proposal
    Assert-DecisionThrows-Ming { Invoke-DecisionFixture-Ming 'propose' 'unsafe_01' @{ ProposalPath = $inputFile } } 'out-of-project fact path refused'
    $proposal.facts_ready = 'true'
    Assert-DecisionThrows-Ming { Test-DecisionProposal-Ming $proposal } 'truthy string is not boolean evidence'
    $parameters = (Get-Command $tool).Parameters
    Assert-Decision-Ming (-not $parameters.ContainsKey('UtcNow') -and -not $parameters.ContainsKey('Now')) 'production CLI has no clock override'
    Write-Host "Decision tests passed: $script:Checks checks. Clock fixtures and feedback are synthetic; no device/user-acceptance evidence."
} finally {
    $resolved = [IO.Path]::GetFullPath($fixtureRoot)
    $temporaryBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($temporaryBase, [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $resolved) -notlike 'AgentOS-Decision-test-*') { throw 'Refusing cleanup outside fixture directory.' }
    if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}
