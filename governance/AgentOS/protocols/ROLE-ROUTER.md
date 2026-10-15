# AgentOS 角色路由协议 v1.0

角色分工前先按 SKILL-MATRIX.md 从 SKILL-REGISTRY.json 选当前 Unit 的方法与输入/输出
契约。角色不是独立模型数量；方法可以复用同一已注册 Skill 的不同引用。能力未部署或
输入不足保持阻塞，不能用多个角色的赞同替代编译/测试/实测与独立复核。

## Coordinator

唯一任务总编。负责北极星、任务树、依赖图、当前 Unit、升级和最终 DoD。Coordinator 不用自己的记忆代替任务文件。

## 十个角色

| 角色 | 默认触发 | 必须产物 |
|---|---|---|
| A1 需求分析 | 目标含糊、需求多、验收不明 | 目标句、范围、DoD、开放问题 |
| A2 架构设计 | 跨模块、协议、并发、数据格式、依赖 | 方案比较、取舍、回滚和影响面 |
| A3 代码工程 | 已有明确 Unit | 最小变更和实现证据 |
| A4 测试验证 | 新逻辑、bug、公共接口 | 正常/异常/边界测试和输出 |
| A5 质量审计 | 交付前、跨文件变更 | diff 风险、死代码、回归结论 |
| A6 文档编纂 | API、协议、操作流程改变 | 文档/变更记录/迁移说明 |
| A7 性能优化 | 延迟、吞吐、内存、CPU、长跑 | 基线、指标、优化前后数据 |
| A8 安全审计 | 外部依赖、权限、网络、凭据、设备 | 安全检查和未决风险 |
| A9 运维监控 | 服务、后台任务、7x24、部署 | 健康、日志、恢复和告警方案 |
| A10 集成验证 | 多角色产物汇合、真机、发布 | 集成结果、版本证人和交付意见 |

## 路由规则

- 小任务：Coordinator + A3 + 必要的 A4。
- 普通多文件任务：A1、A2、A3、A4、A5。
- 跨模块或硬件任务：A1、A2、A3、A4、A8、A10，必要时加 A7/A9。
- 7x24 或发布任务：A5、A6、A8、A9、A10 必须参与。
- 第三次同类失败：停止 A3 继续修改，交 A1/A2/A8 重新审视问题。

角色可以由同一个模型分阶段扮演，也可以由不同模型/客户端执行。角色名称不是权限，证据和门禁才是权限。
## v1.1 verification boundary

The coordinator owns task decomposition and delivery state. The worker owns
the current Unit. The verifier must inspect an external artifact, test,
compiler, device or user acceptance source; repeating the worker's assertion
is not independent verification. All roles use the same truth ledger, and no
role may override conflicted, stale, synthetic or missing evidence.
