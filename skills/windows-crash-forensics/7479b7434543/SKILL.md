---
name: windows-crash-forensics
description: "Windows 蓝屏与意外重启的取证与根因收敛。从一次『系统重启』反馈出发，分清『崩溃了但没留下证据』与『有 bugcheck 但转储失败』，读出真实 BugcheckCode，判定证据是否被销毁，并按可证伪顺序排列根因候选。适用于 Kernel-Power 41 / 6008 / BugCheck 1001 / volmgr 161 判读，Minidump 与 MEMORY.DMP 取证链诊断，现代待机（TDR）类崩溃，以及内存硬件诊断的现场编排。"
metadata:
  version: "1.0.1"
---

# Windows 崩溃取证与根因收敛

> **第一原则：把「崩溃事实」与「证据状态」分成两条独立的链，任何一条都不能替代另一条。**
> 本 skill 的每一条纪律都来自一次真实翻车——把两者混为一谈，
> 曾让本机的取证明细率**先被算成 0%（错的，实际 60%），再被修成 60%**。

---

## 1. 收到「系统重启了」之后，按这个顺序做

**不要先问用户「是不是蓝屏了」。** 用户看到的是黑屏重启，不是停止代码。

### 步骤 1：先钉死时间与次数（易失证据，优先取）

```powershell
$os = Get-CimInstance Win32_OperatingSystem
$os.LastBootUpTime; (Get-Date) - $os.LastBootUpTime
```

再用 **Kernel-Power 41** 的**全期计数**和增量确认「是不是又崩了一次」。
这是唯一不受用户表述影响的判据。

### 步骤 2：读出真实停止代码——**不要看有没有 dump**

```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; Id=41} -MaxEvents 10 |
  ForEach-Object {
    $x = [xml]$_.ToXml()
    [pscustomobject]@{
      Time = $_.TimeCreated
      Rec  = $_.RecordId
      Code = ($x.Event.EventData.Data | Where-Object Name -eq 'BugcheckCode').'#text'
      P1   = ($x.Event.EventData.Data | Where-Object Name -eq 'BugcheckParameter1').'#text'
      Stdby= ($x.Event.EventData.Data | Where-Object Name -eq 'ConnectedStandbyInProgress').'#text'
    }
  }
```

**41 事件的 `BugcheckCode` 才是权威停止代码。**

> ### ⚠️ 最容易犯的错：把「没有 dump」当成「没有蓝屏」
>
> 41 事件里 `BugcheckCode` 非 0 ⇒ 蓝屏**确实发生过**，哪怕：
> - Application 日志没有 BugCheck 1001 事件
> - `C:\Windows\Minidump` 是空的
> - `MEMORY.DMP` 没更新
>
> 这些**全都是转储失败的 _后果_**，不是「没崩」的证据。
> 2026-10-15 的 `0x119 VIDEO_TDR_FAILURE` 就是这样被一度误判成断电的。

### 步骤 3：判定证据状态（**四态，不是两态**）

见 [references/evidence-chain.md](references/evidence-chain.md)。核心是这张表：

| 观察 | 结论 | 含义 |
|---|---|---|
| 有 dump | `EVIDENCE_CAPTURED` | 正常 |
| 无 dump **且** 有 `volmgr 161` | `EVIDENCE_DESTROYED_DUMP_CREATE_FAILED` | **蓝屏了，证据在写入时失败，永久丢失** |
| 无 dump 且无 161 | `EVIDENCE_ABSENT_NO_DUMP` | 查转储配置 |
| 探测本身失败 | `EVIDENCE_UNKNOWN` | **绝不能报成「无失败」** |

> ### ⚠️ 头号误判：把 `volmgr 161` 当成「证据被销毁」
>
> **161 在成功产出 dump 的崩溃上照样出现。**
> 实测反例：09-07 / 10-11 / 10-12 三次**都有 dump**，却**同样报了 161**。
>
> **正确判据 = `161` ∧ `该崩溃确实没有 dump`。**
> 少一个合取项，就会把 5 次里的 3 次误判成事故，
> 并据此去改一个**当时完全正常**的配置。

> **H1 纪律**：「读到 0 条」和「没读到」是两回事。任何枚举失败、权限拒绝、
> 查询报错，都必须落成 `UNKNOWN`，**不得**降级成空集合冒充「一切正常」。

### 步骤 3b：算明细率之前，先证明新字段不会吞掉历史

本 skill 的作者在加 `evidence_status` 字段时踩中过：
6 行老台账**全无此字段**，聚合直接跳过 ⇒ **明细率被算成 0%**，
而实际有 3 个 dump 明明存在。**它不报错，只给一个看起来很合理的错数字。**

> **判别口**：老记录缺这个新字段时，**聚合结果会不会变？**
> 会变 ⇒ 必须从**原始字段回填推导**（如 `linked_minidump`），不能只读新字段。

### 步骤 4：算明细率，别只看最近一次

`确认蓝屏次数` 是分子还是分母，取决于**口径**——硬断电/挂死不产生 bugcheck，
不应计入分母，但**必须单独统计**，否则「无 bugcheck」会被误读成健康。

---

## 2. 取证链失效的排查顺序

当明细率低或 dump 缺失时，**按这个顺序**查，不要跳步：

```
1. 磁盘空间        C: 剩余（排除「写不下」）
2. 页面文件实际大小  vs 物理内存大小   ← 最高频真凶
3. AutomaticManagedPagefile 是否被关
4. CrashDumpEnabled 当前值 vs 它被改成什么、为什么改
5. Minidump 目录可访问性（区分「空」/「读不到」）
```

> ### 坑：为了解释未查清的现象，搭出一条「听起来完全合理」的因果链
>
> 2026-10-15 的**初版推论**（已被自查推翻，保留作反面教材）：
> ```
> 页面文件 3.75GB / 内存 64GB / 系统托管关闭
>   → CrashDumpEnabled=7（自动）写不下 → volmgr 161
>   → 有人改成 3（小转储）试图规避
>   → 小转储同样 161 → 取证「全灭」
> ```
>
> **推翻它的是一条实测**：归档目录里躺着三个 minidump，
> 文件名时间戳与崩溃时刻**精确到 0.2 分钟**。09-07 ~ 10-12 配置**相同**却成功产出过 dump。
>
> 更值得记的是：**这条链上的两个错误互相印证，差点一起蒙混过关**——
> 因果链说是「全灭」，而支撑它的明细率数字（0%）**恰恰也是我自己代码算错的**。
> 一个错结论配一个错数字，看起来像双重佐证，实际上是两个 bug。
>
> **每次改配置前连问两句**：
> ① 上一次失败的原因**被解决**了吗？
> ② **「失败」这个前提本身核实过吗？**
> 改配置前，先花十分钟把历史 dump 目录点一遍。

### ⚠️ 监控层 ≠ 证据层

「装了看护任务就能保住证据」是**错的**。看护任务负责**收割已存在的 dump**；
当 dump **从未被创建**时，收割层无从下手。
**修复点永远是转储配置本身，不是看护任务。**

---

## 3. 根因候选的排序纪律

### 3.1 「码各不相同」是强信号

若多次崩溃的 `BugcheckCode` **互不相同**（例如 0x50 / 0x12B / 0x133 / 0x3B / 0x119），
这**倾向于**一个共同底层（内存劣化、供电、固件不稳），
而不是若干个独立故障。单一驱动故障通常会**重复同一个码**。

### 3.2 候选按「可证伪性」排序，不按「像不像」排序

| 顺位 | 候选 | 证伪/证实手段 |
|---|---|---|
| 1 | 页面/转储配置缺陷 | 直接查配置即可证实，改配置后等下次崩溃验证 |
| 2 | 第三方驱动（尤其**虚拟显示、远控、杀软**） | 卸载/禁用后观察；先查是否出现在崩溃上下文 |
| 3 | 内存硬件 | **必须现场**：`mdsched` 需开机有人按 Enter；MemTest86 需插 U 盘 |
| 4 | 固件/BIOS/供电 | 需拆机或换件，**停止自动执行，转所有者** |

### 3.3 WHEA 安静**不能**用来排除内存

非 ECC 内存（`Win32_PhysicalMemory` 的 `TotalWidth == DataWidth`，常见值 64/64）
**没有纠错，就没有硬件错误上报通道**——WHEA 0 条是**预期行为**，
不是「内存没问题」的证据。

> 这是本类问题里最容易产生**假排除**的地方。反过来，
> 若内存是 ECC（TotalWidth=72）而 WHEA 仍为 0 条，那才是真异常。

### 3.4 现代待机（TDR）类崩溃

`ConnectedStandbyInProgress=true` 表示崩溃发生在**现代待机**期间。
这是独立的一类问题，常见于笔记本 / 紧凑主机平台的电源管理与显示驱动路径。

- `0x116 / 0x117 / 0x119 / 0x141` 属 **TDR / 显示引擎超时**族
- 采集了这个字段却从不判读，等于把信号扔掉——**必须参与告警与趋势统计**

---

## 4. 判读纪律（七条，每条都有真实代价）

1. **停止代码只从 41 事件读**，不从「有没有 dump」推断。
2. **`BugcheckCode=0` 与「节点缺失」必须区分**：前者是真·硬断电，后者是读不到（H1）。
3. **`volmgr 161` 必须与「确实没有 dump」同时成立**才有意义——单独出现什么都不证明。
4. **码表要能重推导**：台账/日志通常是只追加的，早期写入的错误标签不会自愈。
   聚合时**从原始数值重新推导名字**，不要信任存储字段——
   既不改写历史，又拿到正确结论。
5. **只追加的 schema × `Set-StrictMode -Version Latest` = 定时炸弹**：
   新字段上线后，读取老记录会抛 `PropertyNotFoundException`。
   必须用安全取属性函数兜底（如返回 `$null` 而非抛错）。
6. **新增统计字段必须从原始字段回填**：老行缺新字段时被静默跳过，
   会让历史数据在报表里**蒸发**且**不报错**——比抛异常危险得多。
7. **诊断工具不得毁掉自己的历史**：`-FullScan` 只应重置水位线，
   不应清零运行计数——否则你正在用它查的历史，被它自己抹掉了。

---

## 5. 权限与提权边界

以下动作**一律属安全确认域，需所有者明确批准，不超时放行**：

- 修改 `CrashDumpEnabled` / 页面文件大小 / `AutomaticManagedPagefile`
- 注册 / 删除计划任务与服务
- 读取 Security 日志、卷影副本
- 卸载或禁用设备驱动

**非提权会话下可以做的**（本 skill 全部取证步骤都在此范围内）：

- 读 System / Application 事件日志（41 / 6008 / 1001 / 161 / 219）
- 读 `Win32_PhysicalMemory` / `Win32_VideoController` / `Win32_PnPEntity`
- 读 `HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl` 与 Memory Management
- 对**副本**做 AST 解析与单元测试

> **读 Minidump 目录本身可能抛 `UnauthorizedAccessException`**——
> 这**不代表目录是空的**，也不代表有 dump。这正是 H1 最典型的现场。
> 多路探测（`cmd dir` / .NET / `Get-Acl`）结果**可能互相矛盾**；
> 矛盾时**如实报告矛盾**，不要挑一个信。

---

## 6. 参考资料

| 文件 | 内容 |
|---|---|
| [references/evidence-chain.md](references/evidence-chain.md) | 取证链：三态判定、volmgr 161、页面文件/转储配置排查 |
| [references/bugcheck-codes.md](references/bugcheck-codes.md) | 停止代码码表与判读要点 |
| [references/triage-playbook.md](references/triage-playbook.md) | 从反馈到复盘的分步流程与交付物清单 |
