# Task {{TASK_ID}} — {{TITLE}}

```yaml
contract_ref: .agentos/contract/contract.json
contract_version: 0
contract_sections_in_scope: none
agentos_version: 1.4.0
task_id: {{TASK_ID}}
status: planned
created_at: {{CREATED_AT}}
owner: agent
project_root: {{PROJECT_ROOT}}
```

## Truth contract

- Primary capability / necessary constraints:
- Route report / input source hashes:
- Declared result / risk and minimum evidence level:
- Gate report / current ledger claims / independent verifier reference:

- Objective state: proposal / active / verified / blocked
- Required evidence level:
- Evidence ledger: .agentos/evidence/claims.jsonl
- Real data sources:
- Synthetic/mock/demo data used: none / listed below
- Unknowns that must not be guessed:
- Conflicts or stale evidence:

## Structured input

### Instructions

- Allowed actions:
- Approval boundary:
- Stop conditions:

### Facts and data

| Item | State | Source or claim ID | Data class | Freshness |
|---|---|---|---|---|
|  | unknown |  | unknown |  |

## 目标

一句话描述用户目标：

## DoD

- [ ]

Each DoD item must name its minimum evidence level and claim ID before it can
be marked verified.

## Recursive plan

| Unit | Depends on | Green condition | Evidence level | Ready |
|---|---|---|---|---|
| U-001 |  |  | E0 | yes |

Only one Unit is ready for execution at a time. Refine the remaining rows
after the ready Unit has actual evidence.

## 范围与边界

- 包含：
- 不包含：
- 用户需要决定：
- 安全确认（明确回复，无超时默认）：
- 普通偏好（推荐已通知，300 秒无反馈委托默认）：
- 决策记录：.agentos/decisions/
- 待决策期间可独立推进的 Unit：

## 风险与依赖

- 风险：
- 依赖：
- 安全前置：

## 分解

| ID | Unit | 绿条件 | 状态 | 证据 |
|---|---|---|---|---|
| U-001 |  |  | planned |  |

## 失败与假设表

| 尝试 | 假设 | 结果 | 结论 |
|---|---|---|---|

## 当前状态

最后更新时间：
当前 Unit：
下一步唯一动作：
阻塞：无

## 收尾

- [ ] DoD 证据齐全
- [ ] 测试/编译/安全检查已记录
- [ ] 版本与决策登记已同步
- [ ] 临时文件已处理
- [ ] 用户验收状态已明确
