# 借鉴来源登记（Sources）

> 评审体系与域清单的外部来源，全部为本轮调研实际读取的页面。尊重原创，便于追溯与后续升级对照。

| 来源 | 借鉴内容 | 链接 |
|---|---|---|
| Keitark/pcba-design-skills | 8 技能分拆、证据门禁、电路审计清单、布局分层审查、连接器成熟度、审批分离 | https://github.com/Keitark/pcba-design-skills |
| settchan2003-design/kicad-schematic-review-skill | 证据优先评审法（抽取→手册契约→实例审查）、域清单库结构、电流路径 70% 降额规则、"verified"禁令、发现五要素 | https://github.com/settchan2003-design/kicad-schematic-review-skill |
| Diode 硬件审查博客 | 审查分类体系（原理图/手册合规/电源完整性与保护/物理实现）、只读审查器定位 | https://github.com/diodeinc/blog/blob/main/hardware-review.mdx |
| KiCad Design Review (GitHub Action) | 40 检测器分类（电源反馈分压/时序/模拟/保护/数字接口/降额/PCB/生命周期）、降额数值（陶瓷 50%/电解 80%） | https://github.com/marketplace/actions/kicad-design-review |
| iwdfsolutions 高速 PCB 实践 | 回流路径/换层伴随回流过孔/缝合过孔/3W/阻抗 Coupon/去耦层级/单地平面临界实践 | http://iwdfsolutions.com/high-speed-pcb-design-best-practices-layout-guidelines-and-signal-integrity-tips |
| Ameba RTOS 硬件设计指南 | 分阶段流程（原理图→自查清单→布局→布局评审→bring-up） | https://github.com/Ameba-AIoT/ameba-rtos-pro2-doc/blob/master/source/hw_design/introduction.rst |
| Aivon EMC 布局实践 | 平面屏蔽/正交布线/Guard trace/接口滤波/层叠策略 | https://www.aivon.com/blog/pcb-knowledge/the-art-of-vending-machine-pcb-layout-optimizing-for-signal-integrity-and-emc/ |
| PCIe 设计指南(pcbmaster) | 3W 规则量化、过孔/背钻、转角半径 ≥3×线宽 | https://www.pcbmaster.com/news/pcie-pcb-design.html |
| aklofas/kicad-happy (kidoc) | 评审报告类型学（Design Review/EMC Report 等 8 类报告形态） | https://github.com/aklofas/kicad-happy/blob/main/CHANGELOG.md |
| mixelpixx/Konnect | KiCad 10 IPC API 自动化 + 217 工具（设计审查/制造导出）候选工具链 | https://github.com/mixelpixx/Konnect |

## 升级路径（后续可吸收）
- Konnect / KiCAD-MCP-Server：若迁 KiCad 10 原生 IPC API，可将评审清单部分工具化（去耦审计、电源轨审查）
- kidoc：评审报告可升级为 PDF/DOCX 正式格式（8 类报告模板）
- Tracewise：云端 AI 评审可作为第二意见（注意：文件外发需用户批准，涉密设计不用）
