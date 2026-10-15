# 长程任务协议 v1.0

## A. 开工包

建立 `.agentos/tasks/<task-id>.md`，至少填写：目标、范围、DoD、风险、依赖、当前状态、下一步和验收证据。复杂任务使用三级分解：

- Phase：阶段性结果，例如“建立通信层”。
- Task：可管理的工作包，例如“实现帧解析器”。
- Unit：一次可验证动作，例如“为 CRC 错误帧增加一个失败测试”。

## B. 状态机

`planned -> ready -> in_progress -> verifying -> verified`

异常路径：

`in_progress -> blocked -> resumed`

`verifying -> failed -> replanned`

`failed -> escalated`

`verified -> delivered` 在自主交付 DoD 满足时允许；如果任务明确要求用户/真机验收，单独标 `needs-user-acceptance`，不把等待回复当成验收通过。独立工作继续推进。

禁止从 `planned` 直接跳到 `delivered`，禁止从 `failed` 直接标记 `verified`。

## C. 每个 Unit 的最小记录

```text
Unit: U-xxx
Intent: 要改变什么
Precondition: 开始前必须成立什么
Action: 只做一个动作
Green: 什么机器结果算通过
Evidence: 命令、退出码、产物路径、时间
Next: 下一 Unit
```

## D. 检查点

检查点不是流水账。它必须让一个新会话在五分钟内恢复：

- 当前任务和状态
- 已完成 Unit 及证据
- 当前结论
- 被否假设及理由
- 未解决阻塞
- 下一步唯一动作
- 不可触碰的 SSOT 和安全前置
- 普通偏好决策 ID、实际通知时间、截止时间与用户反馈；不能重启计时。

## E. 模型调度

执行模型负责局部 Unit；决策模型负责跨模块方案、失败熔断和用户风险。执行模型遇到以下条件时生成 checkpoint 并升级：

- 同一问题第二次修复无效。
- 需要改协议、数据格式、公共 API 或硬件行为。
- 需要删除或覆盖用户资产。
- 证据互相矛盾。
- 需要猜测未记录的需求。

## F. 证据等级

| 等级 | 含义 |
|---|---|
| E0 | 模型判断，无机器证据 |
| E1 | 静态检查或文件存在 |
| E2 | 单元测试/编译通过 |
| E3 | 集成测试、模拟器或长跑验证 |
| E4 | 真实设备/用户验收 |

DoD 要求的等级必须在任务单中明确。E0/E1 不能替代 E2/E3/E4。

## G. 收尾门禁

收尾按以下顺序：

1. 对照 DoD 逐项填证据。
2. 检查版本、契约、文档和决策登记。
3. 清理或归档临时脚本、缓存、草稿和旧指针。
4. 记录衍生任务，不顺手扩大范围。
5. 运行项目治理检查和安全检查。
6. 分别声明 `verified`、`needs-user-acceptance` 和 `blocked`，不混用。
## v1.1 truth and recursive overlay

The task tree is refined from evidence. Plan the Phase/Task/Unit shape, execute
one ready Unit, record the actual result, validate its claim and then refine
the remaining Units. Never promote a predicted result to a completed result.

Every material statement uses the truth states and append-only ledger defined
in protocols/TRUTH-AND-EVIDENCE.md. The final gate rejects missing sources,
hash mismatches, stale or conflicted evidence, failed or truncated output and
synthetic data used for a real-world claim.

For context pressure, persist objective, constraints, current Unit, unknowns,
conflicts, claim IDs and the next action to .agentos/working-memory.json and a
checkpoint before continuing. Conversation history is not the system of
record.

## v1.2 delegated autonomy

Authorized routine work continues immediately. Ordinary notified preferences
default after 300 seconds as delegated_default, subject to unchanged factual
basis and constraints. Before every Unit/resume, ingest feedback and evaluate
persisted decisions. Continue independent Units during waits. Safety, missing
facts, host approvals and real acceptance never default. See
protocols/DELEGATED-AUTONOMY.md; no scheduler is created by these rules.
