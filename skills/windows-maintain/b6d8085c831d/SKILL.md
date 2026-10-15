---
name: windows-maintain
description: "Windows 7×24 免维护稳健轻快编排器 — 任何涉及电源/服务/驱动/启动项/计划任务/异常重启/启动卡顿/蓝屏 dump/性能瓶颈的维护动作前必读 WINDOWS11_LTSC_SYSTEM_MAINTENANCE_MANUAL.md；执行手册 §14.4 Phase 0~5 取证流程；遵守 §14.9 三铁律（稳妥验证/单变量/可回滚）+ L1~L5 风险分级 + R1~R10 立即回滚触发器 + 安全第一。触发场景：用户报告'电脑异常重启'/'启动变慢'/'蓝屏'/'服务异常'/'卡顿'/'7×24 维护'/'看维护手册'/'分析 dump'/'定期维护'。**绝不**在不改手册的情况下改系统，所有变更必须落盘 WINDOWS11_LTSC_SYSTEM_MAINTENANCE_MANUAL.md 的 §12 修改记录与对应状态快照节。"
---

# windows-maintain — Windows 7×24 系统维护编排器

## 0. 核心钩子（每次执行前必走）

1. **读取 `WINDOWS11_LTSC_SYSTEM_MAINTENANCE_MANUAL.md`**（手册是唯一状态权威）
2. **读取 `.claude/CLAUDE.md`**（项目入口约束）
3. **读取 `context/status.md`**（最近 AI 操作流水）
4. **读取 `.claude/memory/project_current_state.md`**（机器状态快照）

## 1. 触发语义

| 用户输入 | 应该做 |
|---------|--------|
| "电脑重启了" / "突然关机" / "昨晚又重启了" | 立即执行 Phase 0 取证（§14.4），定位重启类型（41+6008 / 1074 / BugCheck） |
| "启动变慢" / "卡顿" / "开机很久" | 执行 B 轨 §15.2 启动项 / 计划任务清理 |
| "蓝屏了" / "BugCheck" / "dump" | 引导用户用 WinDbg 打开最新 `C:\WINDOWS\MEMORY.DMP` 跑 `!analyze -v` |
| "服务异常" / "服务不能启动" / "服务拒绝访问" | 检查 §12.7.2 关键服务状态，先 Cancel 一切 SCM 改动建议（Claude 进程权限不够），改用户手动管理员会话 |
| "7×24 维护" / "稳健运行" / "免维护" | 推 §15.3 整改顺序 + §14.4 Phase 0~5 |
| "每周维护" / "定期检查" | 调 `scripts/weekly_maintenance.ps1` + 注册每周计划任务 |
| "我不知道问题在哪，先看看手册" | 输出现状快照 + 三铁律 + 下一步唯一决策 |

## 2. 不可违反的安全铁律（§14.9.1）

### 2.1 三条铁律
1. **稳妥验证**：每条对策执行前定义"成功标准"，执行后用取证命令验证
2. **安全推进**：单变量原则，每次只动一个；L3+ 必须 ≥30 分钟观察，L4+ ≥24 小时
3. **可安全回滚**：每条对策执行前必须想好"怎么撤回到执行前状态"；回滚路径不通的修改一律禁止

### 2.2 五态流转（L3 原子任务）
P (Pending) → A (Active) → R (Reviewing) → L (Locked/已验收) → C (Change Request)
- 用户说"OK / 通过 / 验收" → L 锁定，绝对不可改
- 用户提新需求 → C 变更，先在 §12 修改记录登记影响范围

### 2.3 L1~L5 风险分级（§14.9.4）
| 等级 | 维护窗口 | 双确认 | 例子 |
|------|---------|--------|------|
| L1 极低 | 否 | 否 | `Get-*` 取证、查日志 |
| L2 低 | 否 | 否 | `powercfg /set*`、`Set-ScheduledTask -Trigger` |
| L3 中 | 推荐 | 是 | `Stop-Service`、`reg add/delete` |
| L4 高 | 必须 | 是 + 镜像 | BIOS、DDU 卸载驱动 |
| L5 极高 | 必须 + UPS | 是 + 备用 | 刷 BIOS/固件 |

### 2.4 R1~R10 立即回滚触发器（§14.9.2）
命中任意一条 → 立即停止 + 回滚到上一个 Known Good：
- R1 新 41/6008/1001 事件
- R2 新 1074（非维护窗口）
- R3 新蓝屏/BugCheck
- R4 新 Application Error (1000)
- R5 性能比改前恶化 >20%
- R6 温度突升 >10°C
- R7 关键服务无法启动
- R8 网络断连 / RDP 断开
- R9 计划外自动重启
- R10 **用户主观感受"比改之前更糟"** ← 用户一票否决

### 2.5 10 条红线（§14.9.9，永不违反）
- ❌ 没有回滚方案就做 L3+ 修改
- ❌ 一次性改 ≥2 个变量
- ❌ 没有 Known Good 备份就做 L3+ 修改
- ❌ 用户没明确同意就做 L4+ 修改
- ❌ 30 分钟观察期内有新异常仍继续推进
- ❌ 41/6008/1001 仍高频出现就做 L4+
- ❌ CCleaner / 注册表清理器 / 驱动全家桶
- ❌ 没有镜像备份就做磁盘/引导相关操作
- ❌ 跳过手册直接改系统（违反入口约束）
- ❌ 把"看起来没事"当成"已经恢复"

## 3. 重启分类与诊断决策树（§6 + §13.2 + §14.3）

### 3.1 三种重启模式
| 模式 | 事件链 | 真因嫌疑 | 第一行动 |
|------|--------|----------|----------|
| **掉电型** | 41+6008（无 1001 或 BugcheckCode=0） | 电源/散热/UPS | A-1 物理检查 → A-2 UPS |
| **驱动 BugCheck 型** | 41+1001（0xF7/0x1E/0x50/0x13A/0x9F 等） | 第三方内核态驱动 | WinDbg !analyze MEMORY.DMP → 定向卸驱动 |
| **受控型** | 1074 (User32) | 用户手动 / 更新 / 计划任务 | 查 1074 发起方 PID/进程名 |

### 3.2 每次重启的标准动作
```
1. 读 LastBootUpTime（Get-CimInstance Win32_OperatingSystem）
2. 取证最近 30 条 41/6008/1001/1074（Get-WinEvent）
3. 按时序回放：哪条 41 在前？哪条 1001 在前？哪条 6005 在后？
4. 判定重启模式（掉电 / 驱动 / 受控）
5. 落盘到手册 §11.x 取证复核节
6. 输出一条后续唯一决策 + 下一步诊断动作
```

## 4. 每周维护 SOP（由 `scripts/weekly_maintenance.ps1` 自动跑）

```
每周日凌晨 03:00:
  1. 取最近 7 天 41/6008/1001/1074 事件 → markdown 报告
  2. 取关键服务状态（PanGPS / RT2870 / WinHttpAutoProxySvc）→ 与手册 §12.7.2 对照
  3. 取 LastBootUpTime + 当前 uptime
  4. 取磁盘剩余空间 + SMART 健康
  5. 取最近 7 个 KB 更新
  6. 取非 Microsoft 启用计划任务总数
  7. 取启动项总数
  8. 取 Office 计划任务状态（B-2 复核）
  9. 取 AutoMaintenance_ProxyGuard + Hotpatch\Monitoring 状态（卡窗口嫌疑）
  10. 输出到 weekly_reports/YYYY-MM-DD.md
  11. 不修改任何系统状态（纯 L1 取证）
```

## 5. 输出格式强制（§15 对话级闭环）

每次回复必须按"四层三明治"：
```
【锚定层】当前手册状态速报（任务状态/取证据/进度百分比）
【响应层】针对用户问题的具体回答（必须关联到具体任务或目标）
【推进层】本次对话后的状态变更建议（已落盘/下一步可执行）
【复述层】下一步唯一需要用户做的决策（明确的一个问题）
```

## 6. 必须落盘到手冊的事

| 场景 | 必须更新 |
|------|----------|
| 完成任何 L1/L2/L3 动作 | §12 修改记录追加一行 |
| LastBootUpTime / 关键服务 / 启动项数 变化 | §1.1 / §12.7.2 对应字段 |
| 发现新根因（BugCheck 代码变化 / 5 核心服务停止 等） | §11.x 新增取证复核节 |
| Phase 0~5 任何阶段完成 | §14.4 对应行 + §15.4 执行结果归档 |
| 创建 / 修改 skill / 计划任务 | §15 新增 skill 节 + §12 修改记录 |

## 7. Claude 进程权限铁律（v3.0 新增，7/8 实战确认）

**Claude 工具启动的 PowerShell 进程为"中等完整性"令牌**（UAC 同意后仍被 SCM 拒访）：
- ❌ 在 Claude 会话内**统一无解**：sc.exe config / OpenService / reg delete HKLM / 服务进程 taskkill
- ✅ **必须**让用户手动以管理员 PowerShell（`Start-Process powershell -Verb RunAs`）执行 L3+ 动作
- ✅ Claude 会话内只能跑 L1 只读取证和 L2 低风险脚本
- ❌ 永远不要在 Claude 会话内尝试 sc.exe / OpenService 路径 — 会反复失败产生噪音

## 8. Skill 协作（按需）

- **Skill 自身**：window7x24-maintain（永久 7×24 编排）/ windows-maintenance-daily（日巡检）/ windows-maintenance-weekly（周维护）
- **子 skill**：dump-analyzer（WinDbg 引导）/ service-cleanup（服务清理）/ startup-optimizer（启动项优化）/ event-id-decoder（事件 ID 释义）

## 9. 触发关键词库

中文：维护/重启/关机/卡顿/蓝屏/驱动/服务/启动/计划任务/电源/散热/7×24/免维护/每周/定期/清理/优化/诊断
英文：windows/maintain/restart/shutdown/bsod/driver/service/startup/scheduled/task/power/thermal/7x24/maintenance/weekly/recurring/cleanup/optimize/diagnose

---

**【配套资源】**
- 主手册：`WINDOWS11_LTSC_SYSTEM_MAINTENANCE_MANUAL.md`（在项目根）
- 每周维护脚本：`scripts/weekly_maintenance.ps1`
- 计划任务注册：`scripts/register_weekly_task.ps1`
- 报告存档目录：`weekly_reports/`
- 记忆文件：`.claude/memory/feedback_maintenance_manual_first.md` + `feedback_safety_first_rollback.md` + `project_current_state.md`
