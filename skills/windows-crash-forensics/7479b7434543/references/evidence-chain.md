# 取证链诊断：dump 缺失的完整排查

> 核心命题：**「没有 dump」有四种完全不同的成因，补救路径互不相同。**
> 混为一谈会让修复方向从根上就跑偏。

---

## 1. 四态模型

```
                        ┌─ 有 dump ──────────────────→ EVIDENCE_CAPTURED
   崩溃事件 41 存在 ────┤
                        ├─ 无 dump + volmgr 161 ─────→ EVIDENCE_DESTROYED_DUMP_CREATE_FAILED
                        │                                （蓝屏了，证据在写入时失败，永久丢失）
                        ├─ 无 dump + 无 161 ─────────→ EVIDENCE_ABSENT_NO_DUMP
                        │                                （查转储配置是否压根没开）
                        └─ 探测本身失败 ─────────────→ EVIDENCE_UNKNOWN
                                                 （绝不能报成「无失败」）
```

**只有第一种是健康的。** 第四种必须保留为独立状态——
把查询失败降级成「没有发现问题」，就是典型的静默失败。

### ⚠️ `volmgr 161` 不能单独定罪（本 skill 的头号误判）

**161 在成功产出 dump 的崩溃上照样出现。** 实测反例：

| 崩溃 | volmgr 161 | dump | 结论 |
|---|---|---|---|
| 09-07 `0x50` | 有 | ✅ 有 | **161 与「有 dump」共存** |
| 10-11 `0x12B` | 有 | ✅ 有 | 同上 |
| 10-12 `0x133` | 有 | ✅ 有 | 同上 |
| 10-13 `0x3B` | 有 | ❌ 无 | 161 ∧ 无 dump ⇒ 成立 |
| 10-15 `0x119` | 有 | ❌ 无 | 161 ∧ 无 dump ⇒ 成立 |

**正确判据 = `161` ∧ `该崩溃确实没有 dump`。** 两者同时成立才有意义。
161 更可能是**次级/回退**转储尝试失败，而非主转储失败。

> 把 161 单独当成「证据被销毁」的判据，会把 5 次崩溃里的 3 次**误判为事故**，
> 并据此去改一个**当时完全正常**的配置。

---

## 2. 判定命令

### 2.1 蓝屏是否发生（权威判据）

```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; Id=41} -MaxEvents 20 |
  ForEach-Object {
    $d = ([xml]$_.ToXml()).Event.EventData.Data
    [pscustomobject]@{
      Time  = $_.TimeCreated
      Code  = [int]($d | Where-Object Name -eq 'BugcheckCode'  | Select-Object -ExpandProperty '#text')
      Stdby = ($d | Where-Object Name -eq 'ConnectedStandbyInProgress' | Select-Object -ExpandProperty '#text')
    }
  }
```

`Code` 非 0 ⇒ **蓝屏确实发生过**，与 dump 是否存在无关。

> **三态，别把 0 一律当断电**
> ```
> Code = 0 且节点存在  → NO_BUGCHECK_HARD_RESET   （真·硬断电/挂死）
> Code = 非 0          → BUGCHECK_CODE_PRESENT
> 节点缺失             → BUGCHECK_CODE_UNREADABLE（读不到，≠ 断电）
> ```
> 把第三种写成第一种，归因方向会直接错。实现上要单独记一个「节点是否读到」的布尔量。

### 2.2 转储是否被销毁

```powershell
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='volmgr'; Id=161} |
  Select-Object TimeCreated, Message
```

事件文本形如：

```
转储文件创建失败，因为在创建转储期间出错。BugCheckProgress 为： 0x00000045
```

**同一 `BugCheckProgress` 值反复出现 = 系统性的配置问题，不是偶发。**

---

## 3. 配置排查顺序（不要跳步）

### 3.1 磁盘空间

```powershell
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' |
  Select-Object DeviceID,
    @{n='FreeGB';e={[math]::Round($_.FreeSpace/1GB,2)}},
    @{n='FreePct';e={[math]::Round(100*$_.FreeSpace/$_.Size,2)}}
```

排除「写不下」。**实测排除过一次就不要反复怀疑**——
2026-10-15 实测 C: 空闲 70.18 GB（18.19%），空间充足，
真正的真凶是页面文件而非磁盘。

### 3.2 页面文件 vs 物理内存（最高频真凶）

```powershell
Get-CimInstance Win32_ComputerSystem | Select-Object AutomaticManagedPagefile
Get-CimInstance Win32_PageFileUsage | Select-Object Name, AllocatedBaseSize, CurrentUsage, PeakUsage
Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management' |
  Select-Object PagingFiles, ExistingPageFiles
```

**判据**：`页面文件实际大小 ≪ 物理内存` 且 `AutomaticManagedPagefile = False`
⇒ 系统级转储写不下。实测案例：**3.75 GB 页面文件 / 64 GB 内存**。

> 页面文件**峰值使用 0** 是另一个信号：它根本没被用起来，
> 说明存在更严重的提交量问题或配置被人为固定住了。

### 3.3 CrashDumpEnabled

```
0=None  1=Complete  2=Kernel  3=Small  7=Automatic  10=Active
```

```powershell
Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl'
```

**同时看 `MinidumpsCount` 与 `DumpFile`**，确认落点。

> ### ⚠️ 改配置前必问：上一次失败的原因解决了吗？
>
> 2026-10-15 实测的失败放大链：
> ```
> 页面文件不足 → CrashDumpEnabled=7 写不下 → volmgr 161
>              → 改成 3（小转储）规避
>              → 小转储同样 161 → 部分丢失恶化为全灭
> ```
> 只换症状不换病因，故障面只会扩大。

### 3.4 Minidump 目录可访问性（**结果可能自相矛盾**）

```powershell
$md = 'C:\Windows\Minidump'
Test-Path -LiteralPath $md
[System.IO.Directory]::GetFiles($md)        # 可能 UnauthorizedAccessException
Get-Acl -LiteralPath $md                     # 可能 UnauthorizedAccessException
cmd /c "dir /a `"$md`""                      # 可能"成功"并显示无文件
```

2026-10-15 实测：`cmd dir` **成功枚举并显示无文件**，
而 .NET 枚举与 `Get-Acl` **抛 UnauthorizedAccessException**。

> **两者矛盾时如实报告矛盾，不要挑一个信，更不要写成「目录为空」。**
> 该结论需提权才能判定。在判定前，一切基于「目录为空」的推断都不成立。

---

## 4. 两个必须区分的「丢失」

| | 转储未创建 | 转储创建失败 |
|---|---|---|
| 信号 | 无 161，目录无新文件 | **有 161**，BugCheckProgress 某值 |
| 含义 | 系统压根没尝试 | **尝试了，失败，证据永久销毁** |
| 补救 | 查 CrashDumpEnabled 是否开启 | 查磁盘/页面文件/写入路径 |
| 紧迫性 | 中 | **高——这是唯一一次机会被浪费** |

把后者读成前者，等于把「**证据被销毁**」降级成「**本来就没有**」，
前者是事故，后者是常态——归因完全不同。

---

## 5. 权限边界

修改 CrashDumpEnabled / 页面文件 / AutomaticManagedPagefile **一律需提权 + 重启**，
属安全确认域。本 skill 的**全部诊断步骤都在非提权范围内可完成**——
先在无权限条件下把结论收敛到「根因是配置且具体是哪一项」，
再一次性向所有者申请所需的提权动作，而不是反复半途申请。
