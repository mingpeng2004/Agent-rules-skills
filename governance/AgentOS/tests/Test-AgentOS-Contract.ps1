#Requires -Version 5.1

[CmdletBinding()]
param([string]$AgentOsRoot)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $AgentOsRoot) { $AgentOsRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')) }
$tool = Join-Path $AgentOsRoot 'bin\AgentOS-Contract.ps1'
$script:toolUnderTest = $tool
. $tool
$policy = Get-ContractPolicy-Ming
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('AgentOS-Contract-test-' + [Guid]::NewGuid().ToString('N'))
$encoding = New-Object Text.UTF8Encoding($false)
$script:Checks = 0

function Assert-Contract-Ming {
    param([bool]$Condition, [string]$Name)
    if (-not $Condition) { throw "Contract test failed: $Name" }
    $script:Checks++
}

function Invoke-ContractFixture-Ming {
    param([string]$Action, [hashtable]$Extra = @{})
    $previous = $ErrorActionPreference
    $output = $null
    $code = 0
    try {
        $ErrorActionPreference = 'Continue'
        $global:LASTEXITCODE = 0
        $output = & $tool -Command $Action -ProjectRoot $tempRoot @Extra 2>&1 | Out-String
        $code = $LASTEXITCODE
    } catch {
        $output = $_.Exception.Message
        $code = 1
    } finally { $ErrorActionPreference = $previous }
    return [PSCustomObject]@{ ExitCode = $code; Output = $output }
}

function Invoke-ContractProcess-Ming {
    param([string[]]$ToolArguments)
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script:toolUnderTest @ToolArguments 2>&1 | Out-String
        $code = $LASTEXITCODE
    } catch { $out = $_.Exception.Message; $code = 1 } finally { $ErrorActionPreference = $previous }
    return [PSCustomObject]@{ ExitCode = $code; Output = $out }
}
function Assert-ContractThrows-Ming {
    param([scriptblock]$Action, [string]$Name)
    $threw = $false
    try { & $Action | Out-Null } catch { $threw = $true }
    Assert-Contract-Ming $threw $Name
}

function Write-ContractFixture-Ming {
    param([string]$Path, $Value)
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 12), $encoding)
}

function New-AmendmentFile-Ming {
    param([string]$Path, [string]$Kind, [string]$Domain, [string]$NewDecision, [string]$Summary)
    $json = [ordered]@{
        kind = $Kind
        summary = $Summary
        sections = [ordered]@{ $Domain = [ordered]@{ decision = $NewDecision; rationale = 'fixture rationale' } }
        impact = 'fixture impact'
        rollback = 'fixture rollback'
        fact_sources = @('docs/design/review.md')
        affected_tasks = @()
    }
    [IO.File]::WriteAllText($Path, ($json | ConvertTo-Json -Depth 8), $encoding)
}

function Set-AllDomains-Ming {
    param([string]$State = 'confirmed', [string]$SourceType = 'project_ssot', [string]$Ref = 'AGENTS.md')
    foreach ($domain in $policy.Domains) {
        $r = Invoke-ContractFixture-Ming 'set' @{ Domain = $domain; Decision = "seeded $domain"; State = $State; SourceType = $SourceType; SourceRef = $Ref; Rationale = 'fixture' }
        if ($r.ExitCode -ne 0) { throw ("seed failed for $domain : " + $r.Output) }
    }
}

try {
    New-Item -ItemType Directory -Force -Path (Join-Path $tempRoot '.agentos\tasks') | Out-Null
    Write-ContractFixture-Ming (Join-Path $tempRoot '.agentos\project.json') @{ fixture = $true }

    $r = Invoke-ContractFixture-Ming 'init'
    Assert-Contract-Ming ($r.ExitCode -eq 0) 'init succeeds'
    $recordPath = Get-ContractRecordPath-Ming $tempRoot
    Assert-Contract-Ming (Test-Path -LiteralPath $recordPath) 'contract file created'
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-Contract-Ming ($record.status -eq 'draft' -and $record.contract_version -eq 0) 'draft starts unconfirmed at version 0'
    Assert-Contract-Ming (@(Get-ContractUnresolved-Ming $record).Count -eq $policy.Domains.Count) 'all required domains pending'
    Assert-Contract-Ming (@($policy.Domains).Count -eq 12) 'twelve domains required'
    $r = Invoke-ContractFixture-Ming 'init'
    Assert-Contract-Ming ($r.ExitCode -ne 0 -or $r.Output -match 'already exists') 'init does not overwrite'

    $r = Invoke-ContractFixture-Ming 'confirm'
    Assert-Contract-Ming ($r.ExitCode -ne 0 -and $r.Output -match 'unresolved domains') 'cannot seal with all domains pending'
    $r = Invoke-ContractFixture-Ming 'set' @{ Domain = 'architecture'; Decision = 'x'; State = 'confirmed'; SourceType = 'user' }
    Assert-Contract-Ming ($r.ExitCode -ne 0 -and $r.Output -match 'traceable source reference') 'user confirmation requires message reference'
    $r = Invoke-ContractFixture-Ming 'set' @{ Domain = 'architecture'; State = 'confirmed' }
    Assert-Contract-Ming ($r.ExitCode -ne 0 -and $r.Output -match 'requires a decision text') 'confirmed requires decision text'
    $r = Invoke-ContractFixture-Ming 'set' @{ Domain = 'not_a_domain'; Decision = 'x'; SourceRef = 'ref' }
    Assert-Contract-Ming ($r.ExitCode -ne 0 -and $r.Output -match 'Unknown contract domain') 'unknown domain rejected'
    $r = Invoke-ContractFixture-Ming 'set' @{ Domain = 'ops_and_maintenance'; Decision = 'later'; State = 'deferred'; SourceRef = 'ref' }
    Assert-Contract-Ming ($r.ExitCode -ne 0 -and $r.Output -match 'owner waiver reference') 'deferred requires owner waiver'
    Assert-Contract-Ming (@(Get-ContractUnresolved-Ming (Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json)).Count -eq $policy.Domains.Count) 'rejected writes leave domains pending'

    Set-AllDomains-Ming
    Invoke-ContractFixture-Ming 'set' @{ Domain = 'product_goal'; Decision = 'seeded product_goal'; State = 'confirmed'; SourceType = 'project_ssot'; SourceRef = 'AGENTS.md'; Rationale = 'fixture' } | Out-Null
    $before = (Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json).history.Count
    Invoke-ContractFixture-Ming 'set' @{ Domain = 'product_goal'; Decision = 'seeded product_goal'; State = 'confirmed'; SourceType = 'project_ssot'; SourceRef = 'AGENTS.md'; Rationale = 'fixture' } | Out-Null
    $after = (Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json).history.Count
    Assert-Contract-Ming ($before -eq $after) 'identical set adds no history'

    $r = Invoke-ContractFixture-Ming 'confirm'
    Assert-Contract-Ming ($r.ExitCode -eq 0) 'seals when all domains resolved'
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-Contract-Ming ($record.status -eq 'confirmed' -and $record.contract_version -eq 1) 'confirmed at version 1'
    Assert-Contract-Ming ((-not [string]::IsNullOrEmpty([string]$record.confirmed_at))) 'confirmation timestamp recorded'
    $r = Invoke-ContractFixture-Ming 'confirm'
    Assert-Contract-Ming ($r.ExitCode -ne 0) 'double confirm refused'

    $r = Invoke-ContractProcess-Ming @('-Command', 'check', '-ProjectRoot', $tempRoot)
    Assert-Contract-Ming ($r.ExitCode -eq 0) 'check passes on clean contract'

    $contractPath = Join-Path $tempRoot 'contract-amendment.json'
    New-AmendmentFile-Ming $contractPath 'contract' 'architecture' 'Adopt layered service boundary' 'Change the architecture baseline'
    $r = Invoke-ContractFixture-Ming 'amend-propose' @{ AmendmentId = 'amend_c1'; AmendmentPath = $contractPath }
    Assert-Contract-Ming ($r.ExitCode -eq 0) 'contract amendment proposed'
    $r = Invoke-ContractFixture-Ming 'amend-notify' @{ AmendmentId = 'amend_c1'; NoticeRef = 'synthetic://contract-notice' }
    Assert-Contract-Ming ($r.ExitCode -eq 0) 'contract amendment notified'
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $amend = @($record.amendments | Where-Object { $_.amendment_id -eq 'amend_c1' })[0]
    Assert-Contract-Ming ($null -eq $amend.deadline_at) 'contract amendment never gets a deadline'
    Invoke-ContractFixture-Ming 'amend-evaluate' @{ AmendmentId = 'amend_c1' } | Out-Null
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $amend = @($record.amendments | Where-Object { $_.amendment_id -eq 'amend_c1' })[0]
    Assert-Contract-Ming ($amend.state -eq 'awaiting_user_confirmation' -and $record.contract_version -eq 1) 'contract amendment waits for explicit confirmation'
    $r = Invoke-ContractProcess-Ming @('-Command', 'check', '-ProjectRoot', $tempRoot)
    Assert-Contract-Ming ($r.ExitCode -eq 2 -and $r.Output -match 'pending_amendments') 'pending amendment blocks drift check'
    $r = Invoke-ContractFixture-Ming 'amend-respond' @{ AmendmentId = 'amend_c1'; Response = 'approve' }
    Assert-Contract-Ming ($r.ExitCode -ne 0 -and $r.Output -match 'traceable ResponseRef') 'response requires a reference'
    $r = Invoke-ContractFixture-Ming 'amend-respond' @{ AmendmentId = 'amend_c1'; Response = 'approve'; ResponseRef = 'synthetic://user-approved-c1' }
    Assert-Contract-Ming ($r.ExitCode -eq 0) 'explicit approval recorded'
    Invoke-ContractFixture-Ming 'amend-evaluate' @{ AmendmentId = 'amend_c1' } | Out-Null
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $amend = @($record.amendments | Where-Object { $_.amendment_id -eq 'amend_c1' })[0]
    Assert-Contract-Ming ($amend.state -eq 'applied' -and $amend.outcome -eq 'user_approved' -and $record.contract_version -eq 2) 'contract amendment applied with version bump'
    Assert-Contract-Ming ($record.sections.architecture.decided_by -eq 'user') 'contract amendment recorded as user decision'
    $r = Invoke-ContractProcess-Ming @('-Command', 'check', '-ProjectRoot', $tempRoot)
    Assert-Contract-Ming ($r.ExitCode -eq 0) 'check passes after applied amendment'

    $prefPath = Join-Path $tempRoot 'pref-amendment.json'
    New-AmendmentFile-Ming $prefPath 'preference' 'ops_and_maintenance' 'Name the directory logs/' 'Adjust naming of the log directory'
    Invoke-ContractFixture-Ming 'amend-propose' @{ AmendmentId = 'amend_p1'; AmendmentPath = $prefPath } | Out-Null
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $pref = @($record.amendments | Where-Object { $_.amendment_id -eq 'amend_p1' })[0]
    $prefProposal = Get-Content -LiteralPath $pref.proposal_snapshot -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-Contract-Ming ((Get-AmendmentOutcome-Ming $pref $prefProposal $policy ([DateTimeOffset]::UtcNow)) -eq 'awaiting_notification') 'preference waits for real notice first'
    Invoke-ContractFixture-Ming 'amend-notify' @{ AmendmentId = 'amend_p1'; NoticeRef = 'synthetic://pref-notice' } | Out-Null
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $pref = @($record.amendments | Where-Object { $_.amendment_id -eq 'amend_p1' })[0]
    $notified = [DateTimeOffset]::Parse($pref.notified_at)
    Assert-Contract-Ming (([DateTimeOffset]::Parse($pref.deadline_at) - $notified).TotalSeconds -eq 300) 'preference deadline is exactly 300 seconds'
    Assert-Contract-Ming ((Get-AmendmentOutcome-Ming $pref $prefProposal $policy $notified.AddSeconds(299)) -eq 'waiting_preference') '299 seconds cannot default'
    Assert-Contract-Ming ((Get-AmendmentOutcome-Ming $pref $prefProposal $policy $notified.AddSeconds(300)) -eq 'delegated_default') '300 seconds defaults by delegation'
    Assert-Contract-Ming ((Get-AmendmentOutcome-Ming $pref $prefProposal $policy $notified.AddSeconds(-1)) -eq 'clock_rollback') 'clock rollback blocked'

    [IO.File]::AppendAllText((Join-Path $tempRoot '.agentos\contract\amendment-amend_p1.json'), ' ', $encoding)
    $r = Invoke-ContractFixture-Ming 'amend-evaluate' @{ AmendmentId = 'amend_p1' }
    Assert-Contract-Ming ($r.ExitCode -ne 0 -and $r.Output -match 'proposal changed on disk') 'edited amendment proposal invalidated'

    $secondPath = Join-Path $tempRoot 'pref2.json'
    New-AmendmentFile-Ming $secondPath 'preference' 'ops_and_maintenance' 'Use logs/' 'Adopt delegated naming'
    Invoke-ContractFixture-Ming 'amend-propose' @{ AmendmentId = 'amend_p2'; AmendmentPath = $secondPath } | Out-Null
    Invoke-ContractFixture-Ming 'amend-notify' @{ AmendmentId = 'amend_p2'; NoticeRef = 'synthetic://pref2-notice' } | Out-Null
    $r = Invoke-ContractFixture-Ming 'amend-evaluate' @{ AmendmentId = 'amend_p2' }
    Assert-Contract-Ming ($r.ExitCode -eq 0) 'preference evaluate runs'
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $pref2 = @($record.amendments | Where-Object { $_.amendment_id -eq 'amend_p2' })[0]
    Assert-Contract-Ming ($pref2.state -eq 'waiting_preference') 'freshly notified preference keeps waiting'
    Assert-Contract-Ming ($null -eq $pref2.response) 'timeout never fabricates feedback'
    Invoke-ContractFixture-Ming 'amend-respond' @{ AmendmentId = 'amend_p2'; Response = 'reject'; ResponseRef = 'synthetic://user-rejected-p2' } | Out-Null
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $pref2 = @($record.amendments | Where-Object { $_.amendment_id -eq 'amend_p2' })[0]
    Assert-Contract-Ming ($pref2.state -eq 'rejected') 'user rejection wins over the default'
    Invoke-ContractFixture-Ming 'amend-evaluate' @{ AmendmentId = 'amend_p2' } | Out-Null
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-Contract-Ming ($record.contract_version -eq 2 -and $record.sections.ops_and_maintenance.decision -ne 'Use logs/') 'rejected amendment changes nothing'

    $taskOld = Join-Path $tempRoot '.agentos\tasks\task_old.md'
    [IO.File]::WriteAllText($taskOld, "contract_version: 1`ncontract_sections_in_scope: architecture`n", $encoding)
    $taskCurrent = Join-Path $tempRoot '.agentos\tasks\task_current.md'
    [IO.File]::WriteAllText($taskCurrent, "contract_version: 2`ncontract_sections_in_scope: quality_bar`n", $encoding)
    $taskLegacy = Join-Path $tempRoot '.agentos\tasks\task_legacy.md'
    [IO.File]::WriteAllText($taskLegacy, "# legacy task without contract binding`n", $encoding)
    $taskAhead = Join-Path $tempRoot '.agentos\tasks\task_ahead.md'
    [IO.File]::WriteAllText($taskAhead, "contract_version: 9`ncontract_sections_in_scope: architecture`n", $encoding)
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $findings = Get-ContractDrift-Ming $record $policy $tempRoot @($taskOld, $taskCurrent, $taskLegacy, $taskAhead)
    $stale = @($findings | Where-Object { $_.code -eq 'stale_task_contract' -and $_.severity -eq 'blocking' })
    Assert-Contract-Ming ($stale.Count -eq 1 -and $stale[0].detail -match 'changed=architecture') 'task bound to a changed domain is stale and blocking'
    Assert-Contract-Ming (@($findings | Where-Object { $_.code -eq 'unbound_task' -and $_.severity -eq 'informational' }).Count -eq 1) 'legacy task is informational only'
    Assert-Contract-Ming (@($findings | Where-Object { $_.code -eq 'task_ahead_of_contract' -and $_.severity -eq 'blocking' }).Count -eq 1) 'task ahead of contract is blocking'
    Assert-Contract-Ming (@($findings | Where-Object { $_.code -eq 'stale_task_contract' -and $_.detail -match 'task_current' }).Count -eq 0) 'current task is not stale'
    $r = Invoke-ContractProcess-Ming @('-Command', 'check', '-ProjectRoot', $tempRoot)
    Assert-Contract-Ming ($r.ExitCode -eq 2) 'check blocks on stale and ahead tasks'

    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $record.enforcement = 'required'
    $record.status = 'draft'
    $record.sections.quality_bar.state = 'pending'
    Save-ContractRecord-Ming $recordPath $record 'fixture' 'required draft' ([DateTimeOffset]::UtcNow)
    Remove-Item -LiteralPath $taskOld, $taskCurrent, $taskLegacy, $taskAhead -Force
    $r = Invoke-ContractProcess-Ming @('-Command', 'check', '-ProjectRoot', $tempRoot)
    Assert-Contract-Ming ($r.ExitCode -eq 2 -and $r.Output -match 'contract_draft') 'required draft contract blocks'
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $record.enforcement = 'advisory'
    Save-ContractRecord-Ming $recordPath $record 'fixture' 'advisory draft' ([DateTimeOffset]::UtcNow)
    $r = Invoke-ContractProcess-Ming @('-Command', 'check', '-ProjectRoot', $tempRoot)
    Assert-Contract-Ming ($r.ExitCode -eq 0 -and $r.Output -match 'contract_draft') 'advisory draft warns without blocking'

    $statusHashBefore = (Get-FileHash -LiteralPath $recordPath -Algorithm SHA256).Hash
    Invoke-ContractFixture-Ming 'status' | Out-Null
    Assert-Contract-Ming ((Get-FileHash -LiteralPath $recordPath -Algorithm SHA256).Hash -eq $statusHashBefore) 'status is read-only'

    $parameters = (Get-Command $tool).Parameters
    Assert-Contract-Ming (-not $parameters.ContainsKey('UtcNow') -and -not $parameters.ContainsKey('Now')) 'production CLI has no clock override'
    Assert-Contract-Ming ($policy.Interaction.tiers.contract.timeout_allowed -eq $false) 'contract tier never times out'
    Assert-Contract-Ming ($policy.Interaction.tiers.preference.timeout_default_seconds -eq 300) 'preference tier is 300 seconds'

    Write-Host "Contract tests passed: $script:Checks checks. Clock and feedback values are synthetic fixtures; no device or user-acceptance evidence."
} finally {
    $resolved = [IO.Path]::GetFullPath($tempRoot)
    $temporaryBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($temporaryBase, [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $resolved) -notlike 'AgentOS-Contract-test-*') { throw 'Refusing cleanup outside fixture directory.' }
    if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}