---
name: firmware-autonomous-dev
description: 系统级固件自主开发 skill。用户只提需求和给真机反馈，AI 自主跑"规格拆解→代码→编译→烧录→真机回读→验证→迭代"完整闭环。适用于任何 MCU / RTOS / 嵌入式 Linux 项目。
---

# Firmware Autonomous Dev

让 Claude 完整接手嵌入式固件开发的工程闭环：用户只描述需求、提供真机（或仿真器）作为反馈源，AI 负责把规格落地为可烧录、可上板验证、可回归的代码与构建系统。

## 何时调用

- 项目目标是嵌入式/IoT/边缘设备固件（裸机、RTOS、嵌入式 Linux、Zephyr、ESP-IDF、PlatformIO、STM32 HAL 等）。
- 用户希望 Claude 主导实现，自己只在两个节点介入：① 提交/澄清需求；② 在真机上观察 Claude 提交的结果并给出反馈。
- 项目有可调用的烧录/调试工具（openocd、stlink、esptool、pyOCD、J-Link、avrdude、uf2 拖拽等），或可观测的串口/JTAG/USB 通道。

## 输入契约（用户需提供）

| 字段 | 必填 | 说明 |
|------|------|------|
| `target_board` | 是 | 板卡名/型号（如 `esp32-c6-devkitc-1`、`stm32h743zi`） |
| `mcu` | 是 | MCU 型号 + 架构 + 主频 |
| `toolchain` | 是 | `esp-idf` / `platformio` / `zephyr` / `stm32cubeide` / `bare-gcc` / `cmake-arm-none-eabi` 等 |
| `requirements` | 是 | 功能 + 非功能需求（时延、功耗、通信协议、IO 表、电源域、安全等级） |
| `acceptance_criteria` | 是 | 可观测、可二值判定的验收清单（如"上电后 2s 内 UART0 输出 `READY\\n`"、"BLE 广播间隔 100ms ±10%"） |
| `debug_interface` | 是 | `uart0@115200` / `swd` / `jtag` / `usb-cdc` 等 |
| `flash_tool` | 是 | 烧录命令或脚本路径 |
| `repo_layout` | 否 | 项目目录约定；缺省用工具链默认结构 |
| `existing_code` | 否 | 是否在已有代码上增量开发；若是，附 git URL 或路径 |

## 工作流（AI 必须按顺序执行）

### Phase 1 — 规格拆解
- 把 `requirements` 拆成模块树（drivers / services / app），明确每个模块的接口契约（头文件 + 数据结构 + 状态机）。
- 输出 `spec.md`：模块列表、IO 表、时序图、状态机图、依赖图。
- **Check**：用户必须确认 `spec.md`，否则不进入 Phase 2。

### Phase 2 — 代码生成
- 按 `spec.md` 生成代码，遵循：① 编译警告视为错误；② 每个公共函数配最小单元测试或断言；③ 关键状态机用表驱动；④ 不引入未经声明的依赖。
- 同步生成 `CMakeLists.txt` / `idf.py` / `platformio.ini` / `Makefile` 等构建脚本。
- 同步生成 `README.md`（构建/烧录/调试命令速查）。

### Phase 3 — 静态验证
- 跑工具链编译，至少一次构建必须零警告通过。
- 跑 host-side 单元测试（mock 硬件层）。
- 跑 `clang-tidy` / `cppcheck`（若工具链支持）。

### Phase 4 — 烧录
- 调用 `flash_tool` 把产物写入目标板。
- 失败时自动重试一次，第二次失败则停下来报告硬件通路问题（不可硬扛）。

### Phase 5 — 真机回读（核心纪律）
- 通过 `debug_interface` 采集至少 N 秒日志（N 默认 30s，可配）。
- 必须捕获：启动日志、功能触发响应、稳态行为。
- 把日志作为"实机证据"附件保存到 `evidence/<run-id>/` 目录。

### Phase 6 — 验收对照
- 逐条比对 `acceptance_criteria`，输出 `verify_report.md`：每条 PASS / FAIL + 证据指向（日志文件 + 行号或时间戳）。
- **任一 FAIL → 回到 Phase 2 修订**，并在修订记录里写明上一轮失败原因，避免重复犯错。
- 全部 PASS 才算当前迭代完成。

### Phase 7 — 迭代收口
- 把本轮所有改动、决策、未决问题写入 `CHANGELOG.md`。
- 如果用户提供了新需求，回到 Phase 1 重启。

## 输出契约

每次完整迭代必须交付：
1. 源码树（git commit 或 diff）
2. 编译产物（`.elf` / `.bin` / `.uf2`）
3. `spec.md`、`verify_report.md`、`CHANGELOG.md`
4. 真机证据目录 `evidence/<run-id>/`（日志、截图、波形截图路径）
5. **明确的 PASS / FAIL 判定**，不允许"看起来好了"这种含糊结论。

## 工具/MCP 契约

skill 调用方需要在 MCP 中暴露以下工具（命名建议，可重命名但需在调用时映射）：

```
fw_build(target_dir) -> { status, artifact_path, warnings[] }
fw_flash(artifact_path, target) -> { status, error? }
fw_capture(interface, duration_s, output_path) -> { status, bytes_written }
fw_power_measure(duration_s) -> { avg_ma, peak_ma }   # 可选
fw_gpio_probe(pin, mode) -> { value }                # 可选
```

如果没有这些 MCP 工具，skill 退化为：仅完成 Phase 1–3，并把烧录/回读步骤写成命令清单让用户手动跑、把日志贴回来。

## 真机反馈纪律（不可妥协）

- **不许在没看到真机日志的情况下声称功能完成**。
- 每次 FAIL 必须引用证据（日志文件 + 行号）才能判定为真 FAIL，不可凭推测。
- 若硬件通路反复不通，停下来向用户报告，不允许无限循环重试烧录。

## 失败模式与升级

| 现象 | 处理 |
|------|------|
| 编译失败 | 自动 fix 一次；二次失败 → 报告 |
| 烧录失败 | 提示检查接线/驱动；不重试超过 2 次 |
| 上板无输出 | 检查时钟、复位、串口参数；不重试超过 3 次 |
| 部分验收 FAIL | 回 Phase 2 修订；同一条 FAIL 不允许出现 3 次仍未进展 |
| 工具链缺失 | 给出安装命令清单，不替用户装 |

## 示例调用

```
调用 firmware-autonomous-dev，目标 esp32-c6-devkitc-1，工具链 esp-idf v5.3，
需求：BLE 外设每秒广播一次心率数据，按键短按清零计数、长按 3s 恢复出厂。
验收：上电 2s 内开始广播；按键响应延迟 < 200ms；恢复出厂后 NVS 清除且重启。
debug: uart0@115200；flash: idf.py -p COM7 flash
```