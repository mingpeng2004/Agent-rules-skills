# PCBA Skill — Proven Lessons (v5.2)

> 来源：CS5552_WCD_V4.1 项目 26 轮迭代实战记录（2026-07-21~23）
> 每一条都有具体数据支撑，不重复已验证的失败方案。

## 布线方法论

### ✅ 有效方法（按优先级排序）

| 方法 | 适用场景 | 成功率 | 注意事项 |
|---|---|---|---|
| **Freerouting 2.2.4 DSN/SES** | 全新布线（空白板） | **极高**（本案从 DRC 290→0） | 必须从空白开始；需 Java 运行环境 |
| **手术式修复** | Freerouting 产生的局部缺陷 | **高** | 先定位冲突区→只移除问题走线段→局部补线，**不重布整网** |
| **finish_gaps.py** | 残留 1-3 条飞线收尾 | **中等** | 只补小缺口；不适用于整网重布 |
| **板尺寸微调** | Freerouting 首轮残留飞线 ≤3 | **高**（18→19→20mm 飞线数 7→3→1→0） | 需用户确认；扩 1-2mm 通常足够 |

### ❌ 已验证失败的方法（不再尝试）

| 方法 | 失败原因 | 数据 |
|---|---|---|
| 手写 design.json routes 坐标 | 无法突破 DRC~140 地板 | 26 轮迭代，最低 140 非掩膜桥违规 |
| pcbnew API 直接画线（实时碰撞检测） | 碰撞检测不精确 + F/B 层焊盘密集 | DRC 443-579 |
| A* 网格寻路 | 网格分辨率与焊盘 BBox 不匹配 + 跨层路径找不到 | 45 焊盘未连接 |
| 单层总线架构 | 不同网总线在同层交叉 | DRC 400-506 |
| 内层路由（In1/In2） | 过孔从 F/B 到内层的桩造成碰撞 | DRC 236-482 |
| Freerouting 对已布线板"续跑" | 越修越差，引入新短路 | 已验证 2 次均失败 |
| 对 100% 已布线密集板"重新布线单个网络" | 其他 82 个网络占满空间，找不到路径 | 必须手术式修复 |

## 验证协议

### 引脚映射核对（CH32V003 教训）

**致命风险**：多封装芯片（QFN20/SOP16/SOP8/TSSOP20）的数据手册使用**合并引脚表**，不同封装在不同列。取错列 = 芯片不工作。

**协议**：
1. 读取数据手册原文，定位合并引脚表
2. **确认该设计使用的封装对应哪一列**
3. 逐引脚核对：引脚号 vs 功能 vs 所属网络
4. WebSearch 独立源交叉验证（如 wemos.cc、mikrocontroller.net）
5. 如发现任何不一致 → 标记为 D14/D15 级缺陷，修复后重建全部原理图

### 原理图标签验证（build_schematic 教训）

**致命风险**：build_schematic.py 可能按网络出现顺序摆放标签，而非按引脚号查表。127 个引脚标签全部错位。

**协议**：
1. 生成原理图后，取 3-5 个有特征的引脚（如 VDD/GND/NRST）逐一核对标签位置
2. 如发现位置错误 → 从符号库提取精确引脚坐标公式，删旧标、按 design.json 重建
3. 全量重建后跑 ERC 验证

## Freerouting 使用经验

### 命令行参数
```bash
java -jar freerouting-2.2.4.jar \
  -de board.dsn \     # 输入 DSN
  -do board.ses \     # 输出 SES
  --gui.enabled=false # 无界面批处理
```

### DSN 导出（KiCad）
```python
import pcbnew
board = pcbnew.LoadBoard("board.kicad_pcb")
pcbnew.ExportSpecctraDSN(board, "board.dsn")
```

### SES 导入（KiCad）
```python
pcbnew.ImportSpecctraSES(board, "board.ses")
# 重铺铜
from pcbnew import ZONE_FILLER
ZONE_FILLER(board).Fill(board.Zones())
board.Save("board.kicad_pcb")
```

### 已知限制
- Freerouting 自身也可能在细间距引脚（≤0.65mm）处产生短路，**不能盲目信任输出**
- 必须在导入 SES 后**立即跑 kicad-cli DRC** 确认
- 发现 Freerouting 缺陷 → 手术式修复（不是整网重布）
- 对已大部分布线完成的板"续跑"会让结果变差，**必须从空白重新布**

## 板尺寸与可布线性的量化关系（CS5552_WCD_V4.1 实测）

| 板宽 | Freerouting 首轮残留飞线 | 附加修复后最终飞线 |
|---|---|---|
| 18mm | 6~7 条 | 未追踪 |
| 19mm | 2~3 条 | 未追踪 |
| 20mm | 1 条 | 0 条（手术修复+finish_gaps） |

**结论**：板宽每增加 1mm，Freerouting 残留飞线减少约 50%。板宽 20mm 是本案的收敛阈值。

## 丝印与层序稽核（v5.3 新增）

### KiCad 10 标准层序（从下到上）
```
Board substrate
  → F.Cu (copper traces, layer 0)
  → F.Mask (solder mask/lacquer, layer 1) — 覆盖铜层，仅焊盘开窗
  → F.SilkS (silkscreen, layer 5) — 白字印刷，在阻焊层之上
  → F.Paste (solder paste, layer 13) — 钢网开孔
```

### 验证要点
1. **丝印必须在最外层**：F.SilkS (layer 5) > F.Mask > F.Cu
2. **阻焊层必须存在**：Gerber 输出必须含 F_Mask.gbr + B_Mask.gbr
3. **丝印文字大小**：JLC 最低 0.6mm，推荐 ≥0.8mm
4. **丝印线宽**：JLC 最低 0.12mm
5. **丝印-焊盘间距**：≥0.3mm（基于 bbox 实测）
6. **在密集板上丝印可能无法完美放置**——可接受少量压焊盘作为 cosmetic P1

### 丝印"在铜线下方"的视觉误导
KiCad 2D 渲染可能显示丝印在铜线"下方"——这是**渲染层序问题，不是制造层序问题**。
实际制造中丝印（白字）印在阻焊层（绿油）之上，物理上是最外层。Gerber 文件中各层独立，
层序由 PCB 厂商按标准工艺处理。验证方法：确认 F.SilkS 层号 > F.Mask 层号 > F.Cu 层号。

## 设计规则验证的诚实性

### 禁止行为
- 标记 `MANUAL` 但实际未检查
- 声称 PASS 但下次实测无法复现
- 信任上一轮的结论而不重新实测

### 要求
- 每条 PASS/FAIL 结论必须有**可复现的证据文件路径**
- 终审报告必须标注证据路径（如 `evidence/erc_2026-07-23_final_corrected.json`）
- 换机/换版本后必须重新实测全部门禁
