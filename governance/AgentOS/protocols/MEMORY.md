# AgentOS 三层记忆协议 v1.0

## 工作记忆

当前任务、当前 Unit、最新输出、下一步和阻塞，放在 `.agentos/status.json`、任务单和 checkpoint。它可以重建当前会话。

## 经验记忆

项目中已有的 `knowledge/`、`lessons/`、`engineering_lessons`、故障报告和已验证的测试结论。只记录可复用的事实、触发条件和证据路径，不保存未经验证的猜测。

## 系统记忆

AgentOS 宪法、协议、适配器和已接受的系统级决策。系统记忆必须短、带版本和锚点；重大调整保留旧版本或决策记录。

## 记忆晋升

`观察 -> 证据 -> 可复现结论 -> 项目经验 -> 系统规则`

一次偶然现象不能直接变成系统规则。规则如果与项目 SSOT 冲突，保留为候选经验并标记冲突。

## 稀疏上下文纪律

不变红线和系统入口放在首部；当前状态和下一步放在尾部；历史细节放在有锚点的独立文件中。引用必须使用 `DEC-*`、`task_*`、路径、函数名或参数名。
## v1.1 durable truth projection

Working memory is a compact projection of the task and is never a substitute
for the evidence ledger. Store claim IDs and source paths, not copied results.
Refresh it after a ledger event and before a checkpoint. See
protocols/CONTEXT-PIPELINE.md and runtime/AGENT-IMPORT.md.
