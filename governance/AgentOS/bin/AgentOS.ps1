#Requires -Version 5.1

[CmdletBinding()]
param(
    [ValidateSet('install', 'diagnose', 'register', 'new-task', 'checkpoint', 'resume', 'grant-approval', 'revoke-approval', 'approval-status', 'evidence-status', 'validate-evidence', 'decision-status', 'evaluate-decisions', 'contract-status', 'contract-check')]
    [string]$Command = 'diagnose',
    [string]$ProjectRoot,
    [string]$TaskId,
    [string]$Title,
    [string]$NextAction,
    [string]$Status,
    [ValidateSet('turn', 'session', 'task')]
    [string]$ApprovalScope = 'session',
    [string]$SessionId,
    [string]$Reason = 'User-approved AgentOS development session',
    [int]$DurationMinutes,
    [switch]$ClientsOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:AgentOsRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'VERSION')) -and $env:AGENTOS_HOME) {
    $script:AgentOsRoot = [IO.Path]::GetFullPath($env:AGENTOS_HOME)
}
$script:AgentOsVersion = (Get-Content -LiteralPath (Join-Path $script:AgentOsRoot 'VERSION') -Raw -Encoding UTF8).Trim()

function Write-AgentOsText {
    param([string]$Path, [string]$Content)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, $Content, $utf8)
}

function Get-ProjectPath {
    param([string]$Path)
    if (-not $Path) { throw 'ProjectRoot is required.' }
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "ProjectRoot does not exist: $Path"
    }
    return [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).Path)
}

function Get-ManagedBlock {
    param([string]$Root)
    return @"
<!-- AGENTOS:BEGIN managed v$script:AgentOsVersion -->
## AgentOS 系统治理入口

AGOS-SKILLS：复杂任务读取 protocols/SKILL-MATRIX.md；agentos_skills.py 选主能力和必要约束、检查输入并 gate 产出；候选/缺失能力不冒充已部署，不预载全部。

本项目接入 `Agent Governance OS`。开始复杂任务前读取：

1. `AGENTS.md`、项目需求/契约 SSOT 和当前状态文件。
2. $Root\runtime\BOOT.md。
3. 项目 `.agentos\project.json`、当前任务和最近 checkpoint。

复杂任务必须外置任务状态、逐 Unit 验证并留下证据。没有测试、编译、实测或审计证据，不得声明完成；同类问题第二次失败换路，第三次列根因表，第四次升级。

AGOS-CONFIRM：开工前一次性定调开发与软件框架（12 域契约，需用户明确确认，不超时），落盘 .agentos\contract；后续需求以修订迭代，任务绑定 contract_version 并跑 AgentOS-Contract.ps1 check。读取 protocols/UPFRONT-CONFIRMATION.md。

AGOS-AUTO：已授权普通工作直接推进。完整推荐方案落盘并实际通知后，普通偏好 300 秒无反馈按既有委托采用，记录 delegated_default。安全、未知事实、锁定 SSOT、宿主权限和真实验收不超时放行。每个 Unit/恢复点先记录反馈，再 evaluate .agentos/decisions；等待期间推进独立工作。该明确用户授权更新旧的非安全无限等待规则。读取 protocols/DELEGATED-AUTONOMY.md。

AgentOS 目录：$Root（也可通过 `$env:AGENTOS_HOME` 定位）。客户端适配器、长程协议和安全宪法均以该目录为单一事实源。
<!-- AGENTOS:END managed -->
"@
}

function Add-ManagedSection {
    param([string]$Path)
    $block = Get-ManagedBlock -Root $script:AgentOsRoot
    $truthBlock = "## AgentOS truth gate" + [Environment]::NewLine +
        "No source means no verified fact. Synthetic, failed, stale or conflicted evidence cannot satisfy delivery." + [Environment]::NewLine +
        "Read runtime\AGENT-IMPORT.md and protocols\TRUTH-AND-EVIDENCE.md at every new conversation."
    $block = $block.Replace('<!-- AGENTOS:END managed -->', $truthBlock + [Environment]::NewLine + '<!-- AGENTOS:END managed -->')
    if (Test-Path -LiteralPath $Path) {
        $content = [IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8)
    } else {
        $content = "# Project Agent Instructions`r`n"
    }
    $pattern = '(?s)<!-- AGENTOS:BEGIN managed.*?<!-- AGENTOS:END managed -->'
    if ($content -match $pattern) {
        $content = [regex]::Replace($content, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $block })
    } else {
        $content = $content.TrimEnd() + "`r`n`r`n" + $block.Trim() + "`r`n"
    }
    Write-AgentOsText -Path $Path -Content $content
}

function Add-MiniMaxOverlay {
    $path = Join-Path $env:USERPROFILE '.minimax\agents\mavis\agent.md'
    if (-not (Test-Path -LiteralPath (Split-Path -Parent $path))) { return $false }
    $begin = '<!-- AGENTOS:BEGIN minimax overlay -->'
    $end = '<!-- AGENTOS:END minimax overlay -->'
    $block = @"
$begin
## AgentOS 系统治理（托管 v$script:AgentOsVersion）

AGOS-SKILLS：复杂任务读取 protocols/SKILL-MATRIX.md；agentos_skills.py 选主能力和必要约束、检查输入并 gate 产出；候选/缺失能力不冒充已部署，不预载全部。

每次复杂任务先读取 `$env:AGENTOS_HOME\runtime\BOOT.md`，再按需读取 AgentOS 宪法和长程协议。项目 `AGENTS.md`、需求 SSOT、契约和决策记录提供项目事实。

长任务必须有 `.agentos\tasks\` 任务单和 `.agentos\checkpoints\` 检查点；每个 Unit 立即验证并记录机器证据。没有证据不得声明完成。同类问题第二次失败换路，第三次列至少三个根因，第四次升级决策台或用户。授权读取 `policies\APPROVAL-POLICY.json`；高风险动作必须逐次确认。

AGOS-CONFIRM：开工前一次性定调开发与软件框架（12 域契约，需用户明确确认，不超时），落盘 .agentos\contract；后续需求以修订迭代，任务绑定 contract_version 并跑 AgentOS-Contract.ps1 check。读取 protocols/UPFRONT-CONFIRMATION.md。

AGOS-AUTO：已授权普通工作直接推进。普通偏好落盘完整推荐并实际通知后 300 秒无反馈按既有委托采用，记录 delegated_default，不冒充用户同意。安全、未知事实、宿主权限和真实验收不超时放行。每个 Unit/恢复点先记录新反馈，再执行 bin/AgentOS-Decision.ps1 evaluate；等待期间推进独立工作。读取 protocols/DELEGATED-AUTONOMY.md。
$end
"@
    $block = $block.Replace($end, "## AgentOS truth gate" + [Environment]::NewLine +
        "No source means no verified fact. Synthetic, failed, stale or conflicted evidence cannot satisfy delivery." + [Environment]::NewLine +
        "Read runtime\AGENT-IMPORT.md and protocols\TRUTH-AND-EVIDENCE.md at every new conversation." + [Environment]::NewLine + $end)
    if (Test-Path -LiteralPath $path) {
        $content = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8)
    } else {
        $content = ""
    }
    $pattern = '(?s)<!-- AGENTOS:BEGIN minimax overlay -->.*?<!-- AGENTOS:END minimax overlay -->'
    if ($content -match $pattern) {
        $content = [regex]::Replace($content, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $block })
    } else {
        $content = $content.TrimEnd() + "`r`n`r`n" + $block.Trim() + "`r`n"
    }
    Write-AgentOsText -Path $path -Content $content
    return $true
}

function Install-ClientAdapters {
    $minimaxSkill = Join-Path $script:AgentOsRoot 'adapters\minimax\SKILL.md'
    $kimiSkill = Join-Path $script:AgentOsRoot 'adapters\kimi\SKILL.md'
    $targets = @(
        (Join-Path $env:USERPROFILE '.minimax\agents\mavis\skills\agent-governance-os\SKILL.md'),
        (Join-Path $env:USERPROFILE '.kimi\skills\agent-governance-os\SKILL.md'),
        (Join-Path $env:USERPROFILE '.kimi-code\skills\agent-governance-os\SKILL.md')
    )
    foreach ($target in $targets) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    }
    Copy-Item -LiteralPath $minimaxSkill -Destination $targets[0] -Force
    Copy-Item -LiteralPath $kimiSkill -Destination $targets[1] -Force
    Copy-Item -LiteralPath $kimiSkill -Destination $targets[2] -Force
    $methodSource = Join-Path $script:AgentOsRoot 'skills\production-skill-routing'
    foreach ($base in @('.codex\skills', '.minimax\agents\mavis\skills', '.kimi\skills', '.kimi-code\skills')) {
        $destination = Join-Path (Join-Path $env:USERPROFILE $base) 'production-skill-routing'
        if (Test-Path -LiteralPath $destination) {
            $sourceFiles = @(Get-ChildItem -LiteralPath $methodSource -Recurse -File)
            $installedFiles = @(Get-ChildItem -LiteralPath $destination -Recurse -File)
            if ($installedFiles.Count -ne $sourceFiles.Count) { throw "Existing method Skill differs; preserve and review: $destination" }
            foreach ($file in $sourceFiles) {
                $relative = $file.FullName.Substring($methodSource.Length).TrimStart('\', '/')
                $installed = Join-Path $destination $relative
                if (-not (Test-Path -LiteralPath $installed -PathType Leaf) -or
                    (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne
                    (Get-FileHash -LiteralPath $installed -Algorithm SHA256).Hash) {
                    throw "Existing method Skill differs; preserve and review: $destination"
                }
            }
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
            Copy-Item -LiteralPath $methodSource -Destination $destination -Recurse
        }
    }
    return Add-MiniMaxOverlay
}

function Register-AgentOsProject {
    param([string]$Path)
    $root = Get-ProjectPath -Path $Path
    $state = Join-Path $root '.agentos'
    foreach ($dir in @('tasks', 'checkpoints', 'evidence', 'reports', 'approvals', 'decisions', 'contract')) {
        New-Item -ItemType Directory -Force -Path (Join-Path $state $dir) | Out-Null
    }
    $project = [ordered]@{
        agentos_version = $script:AgentOsVersion
        project_root = $root
        registered_at = (Get-Date).ToString('o')
        status_file = '.agentos\status.json'
        task_dir = '.agentos\tasks'
        checkpoint_dir = '.agentos\checkpoints'
        evidence_dir = '.agentos\evidence'
        evidence_ledger = '.agentos\evidence\claims.jsonl'
        working_memory = '.agentos\working-memory.json'
        import_contract = 'runtime\AGENT-IMPORT.md'
        truth_protocol = 'protocols\TRUTH-AND-EVIDENCE.md'
        approvals_dir = '.agentos\approvals'
        decisions_dir = '.agentos\decisions'
        autonomy_protocol = 'protocols\DELEGATED-AUTONOMY.md'
        contract_dir = '.agentos\contract'
        interaction_policy = 'policies\INTERACTION-POLICY.json'
        confirmation_protocol = 'protocols\UPFRONT-CONFIRMATION.md'
        design_protocol = 'protocols\DESIGN-CONSISTENCY.md'
        skill_registry = 'policies\SKILL-REGISTRY.json'
        skill_router = 'bin\agentos_skills.py'
        governance_entry = 'AGENTS.md'
    }
    Write-AgentOsText -Path (Join-Path $state 'project.json') -Content ($project | ConvertTo-Json -Depth 5)
    if (-not (Test-Path -LiteralPath (Join-Path $state 'status.json'))) {
        Write-AgentOsText -Path (Join-Path $state 'status.json') -Content (([ordered]@{
            project = $root
            active_task = $null
            state = 'ready'
            last_checkpoint = $null
            updated_at = (Get-Date).ToString('o')
        }) | ConvertTo-Json -Depth 5)
    }
    if (-not (Test-Path -LiteralPath (Join-Path $state 'working-memory.json'))) {
        Write-AgentOsText -Path (Join-Path $state 'working-memory.json') -Content (([ordered]@{
            schema = 'agentos-working-memory-v1'
            agentos_version = $script:AgentOsVersion
            project_root = $root
            active_task = $null
            current_unit = $null
            verified_claim_ids = @()
            open_unknowns = @()
            conflicts = @()
            rejected_assumptions = @()
            last_checkpoint = $null
            next_action = $null
            updated_at = (Get-Date).ToString('o')
        }) | ConvertTo-Json -Depth 6)
    } else {
        $memoryPath = Join-Path $state 'working-memory.json'
        $memoryData = Get-Content -LiteralPath $memoryPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($memoryData.agentos_version -ne $script:AgentOsVersion) {
            $memoryData.agentos_version = $script:AgentOsVersion
            Write-AgentOsText -Path $memoryPath -Content ($memoryData | ConvertTo-Json -Depth 12)
        }
    }
    Add-ManagedSection -Path (Join-Path $root 'AGENTS.md')
    return $root
}

function New-AgentOsTask {
    $root = Register-AgentOsProject -Path (Get-ProjectPath -Path $ProjectRoot)
    if (-not $TaskId -or $TaskId -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{1,80}$') { throw 'TaskId must contain 2-81 safe characters.' }
    if (-not $Title) { throw 'Title is required.' }
    $taskPath = Join-Path $root ".agentos\tasks\$TaskId.md"
    if (Test-Path -LiteralPath $taskPath) { throw "Task already exists: $taskPath" }
    $template = [IO.File]::ReadAllText((Join-Path $script:AgentOsRoot 'templates\TASK.md'), [Text.Encoding]::UTF8)
    $content = $template.Replace('{{TASK_ID}}', $TaskId).Replace('{{TITLE}}', $Title).Replace('{{CREATED_AT}}', (Get-Date).ToString('o')).Replace('{{PROJECT_ROOT}}', $root)
    Write-AgentOsText -Path $taskPath -Content $content
    $statusPath = Join-Path $root '.agentos\status.json'
    $statusData = Get-Content -LiteralPath $statusPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $statusData.active_task = $TaskId
    $statusData.state = 'in_progress'
    $statusData.updated_at = (Get-Date).ToString('o')
    Write-AgentOsText -Path $statusPath -Content ($statusData | ConvertTo-Json -Depth 5)
    $memoryPath = Join-Path $root '.agentos\working-memory.json'
    if (Test-Path -LiteralPath $memoryPath) {
        $memoryData = Get-Content -LiteralPath $memoryPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $memoryData.active_task = $TaskId
        $memoryData.updated_at = (Get-Date).ToString('o')
        Write-AgentOsText -Path $memoryPath -Content ($memoryData | ConvertTo-Json -Depth 6)
    }
    Write-Host "Created task: $taskPath"
}

function New-AgentOsCheckpoint {
    $root = Get-ProjectPath -Path $ProjectRoot
    if (-not $TaskId) { throw 'TaskId is required.' }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $path = Join-Path $root ".agentos\checkpoints\$TaskId-$stamp.md"
    $template = [IO.File]::ReadAllText((Join-Path $script:AgentOsRoot 'templates\CHECKPOINT.md'), [Text.Encoding]::UTF8)
    $content = $template.Replace('{{TASK_ID}}', $TaskId).Replace('{{STAMP}}', $stamp)
    if ($NextAction) { $content = [regex]::Replace($content, '(?s)(## 下一步唯一动作\r?\n\r?\n)-', "`$1- $NextAction") }
    Write-AgentOsText -Path $path -Content $content
    $statusPath = Join-Path $root '.agentos\status.json'
    if (Test-Path -LiteralPath $statusPath) {
        $statusData = Get-Content -LiteralPath $statusPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $statusData.last_checkpoint = $path
        $statusData.state = 'in_progress'
        $statusData.updated_at = (Get-Date).ToString('o')
        Write-AgentOsText -Path $statusPath -Content ($statusData | ConvertTo-Json -Depth 5)
    }
    $memoryPath = Join-Path $root '.agentos\working-memory.json'
    if (Test-Path -LiteralPath $memoryPath) {
        $memoryData = Get-Content -LiteralPath $memoryPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $memoryData.last_checkpoint = $path
        $memoryData.updated_at = (Get-Date).ToString('o')
        if ($NextAction) { $memoryData.next_action = $NextAction }
        Write-AgentOsText -Path $memoryPath -Content ($memoryData | ConvertTo-Json -Depth 6)
    }
    Write-Host "Created checkpoint: $path"
}

function Show-AgentOsResume {
    $root = Get-ProjectPath -Path $ProjectRoot
    $statePath = Join-Path $root '.agentos\status.json'
    Write-Host "AgentOS project: $root"
    if (Test-Path -LiteralPath $statePath) { Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | Write-Host }
    $tasks = Get-ChildItem -LiteralPath (Join-Path $root '.agentos\tasks') -Filter '*.md' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    $checkpoints = Get-ChildItem -LiteralPath (Join-Path $root '.agentos\checkpoints') -Filter '*.md' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    if ($tasks) { Write-Host "Latest task: $($tasks[0].FullName)" }
    if ($checkpoints) { Write-Host "Latest checkpoint: $($checkpoints[0].FullName)" }
    $memoryPath = Join-Path $root '.agentos\working-memory.json'
    if (Test-Path -LiteralPath $memoryPath) { Write-Host "Working memory: $memoryPath" }
    Write-Host 'Saved decisions (read-only): ingest actual new feedback, then evaluate-decisions before dependent work.'
    & (Join-Path $script:AgentOsRoot 'bin\AgentOS-Decision.ps1') -Command status -ProjectRoot $root
}

function Grant-AgentOsApproval {
    $root = Get-ProjectPath -Path $ProjectRoot
    $approvalDir = Join-Path $root '.agentos\approvals'
    New-Item -ItemType Directory -Force -Path $approvalDir | Out-Null
    $id = if ($SessionId) { $SessionId } else { "session_$(Get-Date -Format 'yyyyMMdd-HHmmss')" }
    if ($id -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{1,80}$') { throw 'SessionId must contain 2-81 safe characters.' }
    $ttl = if ($DurationMinutes -gt 0) { $DurationMinutes } elseif ($ApprovalScope -eq 'session') { 480 } elseif ($ApprovalScope -eq 'task') { 240 } else { 15 }
    $grant = [ordered]@{
        agentos_version = $script:AgentOsVersion
        grant_id = $id
        scope = $ApprovalScope
        project_root = $root
        created_at = (Get-Date).ToString('o')
        expires_at = (Get-Date).AddMinutes($ttl).ToString('o')
        reason = $Reason
        critical_requires_single_confirm = $true
        normal_operations = @('read', 'edit_code', 'run_tests', 'build', 'inspect_logs', 'update_agentos_state')
    }
    $path = Join-Path $approvalDir "$id.json"
    Write-AgentOsText -Path $path -Content ($grant | ConvertTo-Json -Depth 5)
    Write-Host "Approval grant created: $path"
    Write-Host "Scope: $ApprovalScope; expires: $($grant.expires_at)"
}

function Revoke-AgentOsApproval {
    $root = Get-ProjectPath -Path $ProjectRoot
    if (-not $SessionId) { throw 'SessionId is required for revoke-approval.' }
    $path = Join-Path $root ".agentos\approvals\$SessionId.json"
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
        Write-Host "Approval grant revoked: $path"
    } else {
        Write-Host "Approval grant not found: $path"
    }
}

function Show-AgentOsApprovalStatus {
    $root = Get-ProjectPath -Path $ProjectRoot
    $approvalDir = Join-Path $root '.agentos\approvals'
    if (-not (Test-Path -LiteralPath $approvalDir)) { Write-Host 'No approval grants.'; return }
    $now = Get-Date
    foreach ($file in (Get-ChildItem -LiteralPath $approvalDir -Filter '*.json' | Sort-Object LastWriteTime -Descending)) {
        try {
            $grant = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
            $expired = ([DateTime]$grant.expires_at) -le $now
            Write-Host ("{0} scope={1} expires={2} expired={3}" -f $grant.grant_id, $grant.scope, $grant.expires_at, $expired)
        } catch {
            Write-Host "Invalid approval record: $($file.FullName)"
        }
    }
}

function Invoke-AgentOsDiagnose {
    $script:diagnoseChecks = @()
    function Add-Check { param([string]$Name, [bool]$Pass, [string]$Detail) $script:diagnoseChecks += [ordered]@{ name = $Name; pass = $Pass; detail = $Detail } }
    Add-Check 'core-import-contract' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'runtime\AGENT-IMPORT.md')) 'next-session import contract'
    Add-Check 'core-boot' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'runtime\BOOT.md')) (Join-Path $script:AgentOsRoot 'runtime\BOOT.md')
    Add-Check 'truth-protocol' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'protocols\TRUTH-AND-EVIDENCE.md')) 'truth protocol'
    Add-Check 'evidence-policy' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'policies\EVIDENCE-POLICY.json')) 'evidence policy'
    Add-Check 'evidence-tool' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'bin\AgentOS-Evidence.ps1')) 'evidence ledger tool'
    Add-Check 'task-protocol' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'protocols\TASK-PROTOCOL.md')) 'structured task protocol'
    Add-Check 'context-pipeline' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'protocols\CONTEXT-PIPELINE.md')) 'context pipeline'
    Add-Check 'autonomy-protocol' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'protocols\DELEGATED-AUTONOMY.md')) 'delegated preference deadlines'
    Add-Check 'decision-policy' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'policies\DECISION-POLICY.json')) '300-second preference policy'
    Add-Check 'decision-tool' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'bin\AgentOS-Decision.ps1')) 'durable decision state machine'
    Add-Check 'contract-protocol' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'protocols\UPFRONT-CONFIRMATION.md')) 'upfront confirmation'
    Add-Check 'skill-matrix' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'protocols\SKILL-MATRIX.md')) 'capability contract workflow'
    Add-Check 'skill-registry' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'policies\SKILL-REGISTRY.json')) '63-capability coverage registry'
    Add-Check 'skill-inspector' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'bin\agentos_skills.py')) 'stdlib input and output gate'
    Add-Check 'interaction-policy' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'policies\INTERACTION-POLICY.json')) 'confirmation tiers'
    Add-Check 'contract-tool' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'bin\AgentOS-Contract.ps1')) 'contract state machine'
    Add-Check 'design-protocol' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'protocols\DESIGN-CONSISTENCY.md')) 'design consistency'
    Add-Check 'constitution' (Test-Path -LiteralPath (Join-Path $script:AgentOsRoot 'constitution\AGENTOS-CONSTITUTION.md')) 'constitution present'
    Add-Check 'minimax-skill' (Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.minimax\agents\mavis\skills\agent-governance-os\SKILL.md')) 'MiniMax skill'
    $miniMaxAgentPath = Join-Path $env:USERPROFILE '.minimax\agents\mavis\agent.md'
    Add-Check 'minimax-overlay' ((Test-Path -LiteralPath $miniMaxAgentPath) -and ((Get-Content -LiteralPath $miniMaxAgentPath -Raw -Encoding UTF8) -match 'AGENTOS:BEGIN minimax overlay')) 'MiniMax overlay'
    Add-Check 'kimi-user-skill' (Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.kimi\skills\agent-governance-os\SKILL.md')) 'Kimi user skill'
    Add-Check 'kimi-code-skill' (Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.kimi-code\skills\agent-governance-os\SKILL.md')) 'Kimi Code skill'
    $skillPairs = @(
        @('adapters\minimax\SKILL.md', '.minimax\agents\mavis\skills\agent-governance-os\SKILL.md'),
        @('adapters\kimi\SKILL.md', '.kimi\skills\agent-governance-os\SKILL.md'),
        @('adapters\kimi\SKILL.md', '.kimi-code\skills\agent-governance-os\SKILL.md')
    )
    foreach ($pair in $skillPairs) {
        $sourcePath = Join-Path $script:AgentOsRoot $pair[0]
        $targetPath = Join-Path $env:USERPROFILE $pair[1]
        $same = (Test-Path -LiteralPath $targetPath) -and
            (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash
        Add-Check ('skill-current:' + $pair[1]) $same 'Installed adapter hash matches current source; live client import is not attested.'
    }
    $checks = @($script:diagnoseChecks)
    $report = [ordered]@{ generated_at = (Get-Date).ToString('o'); root = $script:AgentOsRoot; checks = $checks; pass = @($checks | Where-Object { -not $_.pass }).Count -eq 0 }
    $path = Join-Path $script:AgentOsRoot "reports\diagnose-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
    Write-AgentOsText -Path $path -Content ($report | ConvertTo-Json -Depth 5)
    $report | ConvertTo-Json -Depth 5 | Write-Host
    Write-Host "Report: $path"
    if (-not $report.pass) { exit 1 }
}

switch ($Command) {
    'install' {
        [Environment]::SetEnvironmentVariable('AGENTOS_HOME', $script:AgentOsRoot, 'User')
        $env:AGENTOS_HOME = $script:AgentOsRoot
        Install-ClientAdapters | Out-Null
        $known = @(
            '${PROJECT_PATH}',
            '${PROJECT_PATH}'
        )
        if ($ProjectRoot) { $known += $ProjectRoot }
        if (-not $ClientsOnly) {
            foreach ($item in ($known | Select-Object -Unique)) {
                if (Test-Path -LiteralPath $item -PathType Container) { Register-AgentOsProject -Path $item | Out-Null }
            }
        }
        Invoke-AgentOsDiagnose
    }
    'diagnose' { Invoke-AgentOsDiagnose }
    'register' { Register-AgentOsProject -Path $ProjectRoot | Write-Host }
    'new-task' { New-AgentOsTask }
    'checkpoint' { New-AgentOsCheckpoint }
    'resume' { Show-AgentOsResume }
    'grant-approval' { Grant-AgentOsApproval }
    'revoke-approval' { Revoke-AgentOsApproval }
    'approval-status' { Show-AgentOsApprovalStatus }
    'decision-status' {
        & (Join-Path $script:AgentOsRoot 'bin\AgentOS-Decision.ps1') -Command status -ProjectRoot $ProjectRoot
    }
    'contract-status' {
        & (Join-Path $script:AgentOsRoot 'bin\AgentOS-Contract.ps1') -Command status -ProjectRoot $ProjectRoot
    }
    'contract-check' {
        & (Join-Path $script:AgentOsRoot 'bin\AgentOS-Contract.ps1') -Command check -ProjectRoot $ProjectRoot
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    'evaluate-decisions' {
        & (Join-Path $script:AgentOsRoot 'bin\AgentOS-Decision.ps1') -Command evaluate -ProjectRoot $ProjectRoot
    }
    'evidence-status' {
        & (Join-Path $script:AgentOsRoot 'bin\AgentOS-Evidence.ps1') -Command evidence-status -ProjectRoot $ProjectRoot
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    'validate-evidence' {
        & (Join-Path $script:AgentOsRoot 'bin\AgentOS-Evidence.ps1') -Command validate-ledger -ProjectRoot $ProjectRoot
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}
