---
name: source-command-commands
description: "Migrated source command `commands`"
---

# source-command-commands

Use this skill when the user asks to run the migrated source command `commands`.

## Command Template

# 全局指令定义（Global Commands）
> **版本**: 3.0 | **配套**: 全局 AGENTS.md 第 12 章

---

## 指令总览

| 指令 | 别名 | 行为 | 触发的文件读取 |
|:--|:--|:---|:---|
| `/where` | `/定位` | 三读协议 + 输出对齐声明 | 全局知识 + 项目治理 + 原点 |
| `/status` | `/状态` | 输出 PROJECT_GOVERNANCE.md 当前摘要 | 项目治理 |
| `/load` | `/加载` | 新会话快速恢复上下文 | 同 /where |
| `/lock <task_id>` | `/锁定` | L3 转 L 状态 + 触发知识蒸馏 | 项目治理 + 知识库 |
| `/fuse` | `/熔断` | 触发三振出局熔断 | 输出反思报告 |
| `/next` | `/下一个` | 推荐下一个可启动的 L3 任务 | 项目治理 |
| `/decompose <goal>` | `/拆解` | 把目标拆为 L0→L1→L2→L3 | 输出建议 |
| `/gsearch <keyword>` | `/搜库` | 全局知识库关键词搜索 | 全局知识 |
| `/init` | `/初始化` | 在当前目录初始化项目治理结构 | 创建文件 |

---

## /where — 三读协议

### 触发
- 用户在新会话开始
- 用户输入 `/where` 或 `/定位`

### AI 行为
1. 读取 `${USER_HOME}\.local\share\knowledge\INDEX.global.md`
2. 读取当前工作目录（或 git root）的 `PROJECT_GOVERNANCE.md`
3. 读取 `context/origin.md`（若存在）

### 输出格式（强制）
```
[坐标对齐]
- 全局知识: 已加载 N 条相关经验（关键词: xxx, yyy）
- 项目目标: L0=G-001 (状态: 🟡)
- 当前焦点: L3=AUTH.LOGIN.001 (状态: A)
- 阻塞项: 无
- 最近决策: [10:30] 决定使用 PyInstaller --onefile
```

---

## /status — 状态摘要

### 触发
用户输入 `/status` 或 `/状态`

### AI 行为
仅读取 PROJECT_GOVERNANCE.md，输出摘要。

### 输出格式
```
[项目状态摘要]
- 项目: [项目名]
- L0 目标: G-001 🟡 / G-002 🔴
- L1 里程碑: M-01 🟡 (3/4 完成)
- 当前活跃 L3: TASK-005 (A)
- 待验收: TASK-003 (R)
- 已锁定: 5 个 L3
```

---

## /load — 上下文加载

同 `/where`，但更彻底。适用于长时间中断后的恢复。

额外读取：
- 最近 3 个 `tasks/task_*.md`
- `STATUS.md`（若存在）

---

## /lock — 锁定任务

### 触发
用户输入 `/lock AUTH.LOGIN.001` 或 `/锁定 AUTH.LOGIN.001`

### AI 行为
1. 验证任务是否存在
2. 验证当前状态是否为 R
3. 执行锁定：
   - 状态 → L
   - 写入 `PROJECT_GOVERNANCE.md` 锁定清单
   - 触发知识蒸馏（A11 角色）
   - 更新 `INDEX.global.md` 或 `knowledge/INDEX.md`
4. 输出确认

### 输出格式
```
🔒 任务 AUTH.LOGIN.001 已锁定
- 锁定文件: src/handlers/login.py
- 知识蒸馏: ✅ 已写入 ~/.local/share/knowledge/facts/login_pattern.md
- INDEX 更新: ✅
```

---

## /fuse — 熔断

### 触发
- 自动：同点失败 3 次
- 手动：用户输入 `/fuse`

### AI 行为
立即停止当前编码操作，输出反思报告。

### 输出格式
```
⚠️ 熔断触发 — [原因]

[尝试历史]
1. [HH:MM] 方案 A: [描述] → ❌ [失败原因]
2. [HH:MM] 方案 B: [描述] → ❌ [失败原因]
3. [HH:MM] 方案 C: [描述] → ❌ [失败原因]

[根因假设列表]
- 假设 1: [描述]
- 假设 2: [描述]
- 假设 3: [描述]

[最小化回退方案]
- 是否可以先绕过这个细节，实现主流程？

[请求外部视角]
- 是否值得继续死磕？
- 是否需要用户/上级协助判断？
```

---

## /next — 推荐下一个任务

### 触发
用户输入 `/next` 或 `/下一个`

### AI 行为
扫描 PROJECT_GOVERNANCE.md，筛选：
- 状态 = P
- 所有依赖（前序 L3）状态 = L
- 按 ID 排序

### 输出
```
[下一个可启动 L3]
- TASK-006: 编写 JWT 签发函数
- 依赖: TASK-005 (L) ✅
- 预估工时: 2h
- 是否启动？(等待用户确认)
```

---

## /decompose — 目标拆解

### 触发
用户输入 `/decompose 实现用户登录` 或 `/拆解 实现用户登录`

### AI 行为
按 AGENTS.md 第 5 章的 5 项硬指标逐层拆解。

### 输出
```
[分层拆解建议]

L0 目标:
- G-001: 实现用户登录功能（验收: 双击 exe 弹出登录界面）

L1 里程碑:
- M-01: 用户认证模块

L2 模块:
- M-01-AUTH: 登录逻辑
- M-01-CRYPTO: 密码哈希
- M-01-API: 登录接口

L3 原子任务:
- AUTH.001: 编写 login_handler 函数（4h）
- AUTH.002: 实现密码 bcrypt 加密（2h）
- AUTH.003: 编写登录 API 接口（4h）

请确认是否写入 PROJECT_GOVERNANCE.md？
```

---

## /gsearch — 全局知识搜索

### 触发
用户输入 `/gsearch PyInstaller` 或 `/搜库 PyInstaller`

### AI 行为
1. 在 `~/.local/share/knowledge/` 中 grep
2. 提取相关条目
3. 输出摘要

---

## /init — 项目初始化

### 触发
用户在某个空目录输入 `/init`

### AI 行为
1. 询问项目基本信息（名称、目标）
2. 创建完整项目目录结构
3. 复制治理模板到对应位置
4. 初始化 PROJECT_GOVERNANCE.md
5. 创建首批 L1/L2 拆解建议

---

**指令铁律**: 任何指令执行必须输出标准化响应，禁止随意格式。
