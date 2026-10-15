using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: AssemblyVersion("1.4.0.0")]
[assembly: AssemblyFileVersion("1.4.0.0")]

namespace AgentOsSetup
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            if (args.Length > 0 && String.Equals(args[0], "--self-test", StringComparison.OrdinalIgnoreCase))
            {
                var lines = new List<string>();
                int result = SelfTest.Run(AppDomain.CurrentDomain.BaseDirectory, lines.Add);
                string report = args.Length > 1 ? Path.GetFullPath(args[1]) : Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "self-test.log");
                File.WriteAllLines(report, lines, new UTF8Encoding(false));
                return result;
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new InstallerForm());
            return 0;
        }
    }

    internal static class InstallerEngine
    {
        private const string ManagedBegin = "<!-- AGENTOS:BEGIN managed v1.4.0 -->";
        private const string ManagedEnd = "<!-- AGENTOS:END managed -->";
        private const string MiniMaxBegin = "<!-- AGENTOS:BEGIN minimax overlay -->";
        private const string MiniMaxEnd = "<!-- AGENTOS:END minimax overlay -->";

        private static readonly string[] ManagedPayloadPaths =
        {
            "README.md",
            "VERSION",
            "adapters",
            "bin",
            "constitution",
            "profiles",
            "policies",
            "protocols",
            "runtime",
            "templates",
            "tests",
            "skills"
        };

        public static void Install(
            string payloadRoot,
            string agentOsTarget,
            string miniMaxInstallDir,
            string kimiInstallDir,
            IEnumerable<string> projectRoots,
            string userHome,
            string approvalScope,
            Action<string> log,
            bool setUserEnvironment = true)
        {
            if (!Directory.Exists(payloadRoot)) throw new InvalidOperationException("找不到 AgentOS-Payload: " + payloadRoot);
            if (!File.Exists(Path.Combine(payloadRoot, "VERSION"))) throw new InvalidOperationException("AgentOS-Payload 缺少 VERSION 文件。");
            if (String.IsNullOrWhiteSpace(agentOsTarget)) throw new ArgumentException("AgentOS 目标目录不能为空。");
            if (String.IsNullOrWhiteSpace(userHome)) throw new ArgumentException("用户目录不能为空。");

            agentOsTarget = Path.GetFullPath(agentOsTarget.Trim());
            userHome = Path.GetFullPath(userHome.Trim());
            Directory.CreateDirectory(agentOsTarget);
            CopyManagedPayload(payloadRoot, agentOsTarget, log);
            SetApprovalScope(agentOsTarget, approvalScope, log);

            if (setUserEnvironment)
            {
                Environment.SetEnvironmentVariable("AGENTOS_HOME", agentOsTarget, EnvironmentVariableTarget.User);
                log("已设置用户环境变量 AGENTOS_HOME=" + agentOsTarget);
            }

            string miniMaxSkill = Path.Combine(userHome, ".minimax", "agents", "mavis", "skills", "agent-governance-os", "SKILL.md");
            string kimiSkill = Path.Combine(userHome, ".kimi", "skills", "agent-governance-os", "SKILL.md");
            string kimiCodeSkill = Path.Combine(userHome, ".kimi-code", "skills", "agent-governance-os", "SKILL.md");
            CopyFile(Path.Combine(agentOsTarget, "adapters", "minimax", "SKILL.md"), miniMaxSkill);
            CopyFile(Path.Combine(agentOsTarget, "adapters", "kimi", "SKILL.md"), kimiSkill);
            CopyFile(Path.Combine(agentOsTarget, "adapters", "kimi", "SKILL.md"), kimiCodeSkill);
            string method = Path.Combine(agentOsTarget, "skills", "production-skill-routing");
            foreach (string client in new[] {
                Path.Combine(userHome, ".codex", "skills"),
                Path.Combine(userHome, ".minimax", "agents", "mavis", "skills"),
                Path.Combine(userHome, ".kimi", "skills"), Path.Combine(userHome, ".kimi-code", "skills") })
            {
                string destination = Path.Combine(client, "production-skill-routing");
                if (Directory.Exists(destination))
                {
                    var expected = Directory.GetFiles(method, "*", SearchOption.AllDirectories);
                    if (expected.Length != Directory.GetFiles(destination, "*", SearchOption.AllDirectories).Length)
                        throw new InvalidOperationException("Existing method Skill differs; preserve and review: " + destination);
                    foreach (string source in expected)
                    {
                        string relative = source.Substring(method.Length).TrimStart(Path.DirectorySeparatorChar);
                        string installed = Path.Combine(destination, relative);
                        if (!File.Exists(installed) || !File.ReadAllBytes(source).SequenceEqual(File.ReadAllBytes(installed)))
                            throw new InvalidOperationException("Existing method Skill differs; preserve and review: " + destination);
                    }
                }
                else CopyDirectory(method, destination);
            }
            log("已安装 MiniMax、Kimi 和 Kimi Code 的 AgentOS skill。");

            string miniMaxAgent = Path.Combine(userHome, ".minimax", "agents", "mavis", "agent.md");
            if (Directory.Exists(Path.GetDirectoryName(miniMaxAgent)))
            {
                string content = File.Exists(miniMaxAgent) ? ReadUtf8(miniMaxAgent) : String.Empty;
                WriteUtf8(miniMaxAgent, UpsertBlock(content, MiniMaxBegin, MiniMaxEnd, GetMiniMaxBlock()));
                log("已更新 MiniMax Mavis 全局 overlay。");
            }
            else
            {
                log("未发现 MiniMax Mavis 配置目录，已保留 skill；请确认 MiniMax Code 已安装并重新运行安装器。");
            }

            if (!String.IsNullOrWhiteSpace(miniMaxInstallDir)) log("MiniMax Code 路径：" + miniMaxInstallDir.Trim());
            if (!String.IsNullOrWhiteSpace(kimiInstallDir)) log("Kimi Code 路径：" + kimiInstallDir.Trim());

            foreach (string project in projectRoots.Where(p => !String.IsNullOrWhiteSpace(p)).Select(p => Path.GetFullPath(p.Trim())).Distinct(StringComparer.OrdinalIgnoreCase))
            {
                RegisterProject(project, agentOsTarget, log);
            }
        }

        private static void CopyManagedPayload(string source, string target, Action<string> log)
        {
            foreach (string relative in ManagedPayloadPaths)
            {
                string from = Path.Combine(source, relative);
                string to = Path.Combine(target, relative);
                if (Directory.Exists(from)) CopyDirectory(from, to);
                else if (File.Exists(from)) CopyFile(from, to);
                else throw new InvalidOperationException("AgentOS-Payload 缺少：" + relative);
            }
            log("已复制可审计 AgentOS 文件到：" + target);
        }

        private static void CopyDirectory(string source, string target)
        {
            Directory.CreateDirectory(target);
            foreach (string file in Directory.GetFiles(source)) CopyFile(file, Path.Combine(target, Path.GetFileName(file)));
            foreach (string directory in Directory.GetDirectories(source)) CopyDirectory(directory, Path.Combine(target, Path.GetFileName(directory)));
        }

        private static void CopyFile(string source, string target)
        {
            string parent = Path.GetDirectoryName(target);
            if (!String.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
            File.Copy(source, target, true);
        }

        private static void RegisterProject(string projectRoot, string agentOsRoot, Action<string> log)
        {
            if (!Directory.Exists(projectRoot)) throw new DirectoryNotFoundException("项目目录不存在：" + projectRoot);
            string state = Path.Combine(projectRoot, ".agentos");
            Directory.CreateDirectory(Path.Combine(state, "tasks"));
            Directory.CreateDirectory(Path.Combine(state, "checkpoints"));
            Directory.CreateDirectory(Path.Combine(state, "evidence"));
            Directory.CreateDirectory(Path.Combine(state, "reports"));
            Directory.CreateDirectory(Path.Combine(state, "approvals"));
            Directory.CreateDirectory(Path.Combine(state, "decisions"));
            Directory.CreateDirectory(Path.Combine(state, "contract"));

            string projectJson = new JavaScriptSerializer().Serialize(new Dictionary<string, object>
            {
                { "agentos_version", "1.4.0" }, { "project_root", projectRoot },
                { "registered_at", DateTime.Now.ToString("o") },
                { "status_file", ".agentos\\status.json" }, { "task_dir", ".agentos\\tasks" },
                { "checkpoint_dir", ".agentos\\checkpoints" }, { "evidence_dir", ".agentos\\evidence" },
                { "evidence_ledger", ".agentos\\evidence\\claims.jsonl" },
                { "working_memory", ".agentos\\working-memory.json" },
                { "import_contract", "runtime\\AGENT-IMPORT.md" },
                { "truth_protocol", "protocols\\TRUTH-AND-EVIDENCE.md" },
                { "approvals_dir", ".agentos\\approvals" }, { "decisions_dir", ".agentos\\decisions" },
                { "autonomy_protocol", "protocols\\DELEGATED-AUTONOMY.md" }, { "contract_dir", ".agentos\\contract" }, { "interaction_policy", "policies\\INTERACTION-POLICY.json" }, { "confirmation_protocol", "protocols\\UPFRONT-CONFIRMATION.md" }, { "design_protocol", "protocols\\DESIGN-CONSISTENCY.md" }, { "governance_entry", "AGENTS.md" }
            });
            WriteUtf8(Path.Combine(state, "project.json"), projectJson);

            string status = Path.Combine(state, "status.json");
            if (!File.Exists(status))
            {
                WriteUtf8(status, "{\r\n" +
                    "  \"project\": " + JsonQuote(projectRoot) + ",\r\n" +
                    "  \"active_task\": null,\r\n" +
                    "  \"state\": \"ready\",\r\n" +
                    "  \"last_checkpoint\": null,\r\n" +
                    "  \"updated_at\": " + JsonQuote(DateTime.Now.ToString("o")) + "\r\n" +
                    "}\r\n");
            }

            string memory = Path.Combine(state, "working-memory.json");
            if (!File.Exists(memory))
            {
                WriteUtf8(memory, "{\r\n" +
                    "  \"schema\": \"agentos-working-memory-v1\",\r\n" +
                    "  \"agentos_version\": \"1.4.0\",\r\n" +
                    "  \"project_root\": " + JsonQuote(projectRoot) + ",\r\n" +
                    "  \"active_task\": null,\r\n" +
                    "  \"current_unit\": null,\r\n" +
                    "  \"verified_claim_ids\": [],\r\n" +
                    "  \"open_unknowns\": [],\r\n" +
                    "  \"conflicts\": [],\r\n" +
                    "  \"rejected_assumptions\": [],\r\n" +
                    "  \"last_checkpoint\": null,\r\n" +
                    "  \"next_action\": null,\r\n" +
                    "  \"updated_at\": " + JsonQuote(DateTime.Now.ToString("o")) + "\r\n" +
                    "}\r\n");
            }
            else
            {
                var data = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(ReadUtf8(memory));
                data["agentos_version"] = "1.4.0";
                WriteUtf8(memory, new JavaScriptSerializer().Serialize(data));
            }

            string agents = Path.Combine(projectRoot, "AGENTS.md");
            string content = File.Exists(agents) ? ReadUtf8(agents) : "# Project Agent Instructions\r\n";
            WriteUtf8(agents, UpsertBlock(content, ManagedBegin, ManagedEnd, GetProjectBlock(agentOsRoot)));
            log("已注册项目：" + projectRoot);
        }

        private static void SetApprovalScope(string agentOsRoot, string approvalScope, Action<string> log)
        {
            string[] allowed = { "turn", "session", "task" };
            if (!allowed.Contains(approvalScope)) throw new ArgumentException("无效的授权域：" + approvalScope);
            string policy = Path.Combine(agentOsRoot, "policies", "APPROVAL-POLICY.json");
            var data = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(ReadUtf8(policy));
            data["default_scope"] = approvalScope;
            WriteUtf8(policy, new JavaScriptSerializer().Serialize(data));
            log("默认授权域：" + approvalScope + "（高风险动作仍需单次确认）。");
        }

        private static string UpsertBlock(string content, string begin, string end, string block)
        {
            string prefix = begin == ManagedBegin ? "<!-- AGENTOS:BEGIN managed" : begin;
            int cursor = 0;
            bool inserted = false;
            var result = new StringBuilder();
            while (true)
            {
                int start = content.IndexOf(prefix, cursor, StringComparison.Ordinal);
                if (start < 0) break;
                int finish = content.IndexOf(end, start + prefix.Length, StringComparison.Ordinal);
                if (finish < 0) throw new InvalidOperationException("治理托管段不完整，请先检查文件：" + prefix);
                result.Append(content.Substring(cursor, start - cursor));
                if (!inserted) result.Append(block);
                inserted = true;
                cursor = finish + end.Length;
            }
            if (inserted) return result.Append(content.Substring(cursor)).ToString();
            return content.TrimEnd() + "\r\n\r\n" + block.Trim() + "\r\n";
        }

        private static string GetProjectBlock(string root)
        {
            return ManagedBegin + "\r\n" +
                "## AgentOS 系统治理入口\r\n\r\n" +
                "AGOS-SKILLS：复杂任务读取 protocols/SKILL-MATRIX.md；agentos_skills.py 按输入/输出契约选主能力和必要约束，gate 产出；候选能力保持未部署，不预载全部。\r\n\r\n" +
                "本项目接入 `Agent Governance OS`。开始复杂任务前读取：\r\n\r\n" +
                "1. `AGENTS.md`、项目需求/契约 SSOT 和当前状态文件。\r\n" +
                "2. `" + root + "\\runtime\\BOOT.md`。\r\n" +
                "3. 项目 `.agentos\\project.json`、当前任务和最近 checkpoint。\r\n\r\n" +
                "复杂任务必须外置任务状态、逐 Unit 验证并留下证据。没有测试、编译、实测或审计证据，不得声明完成；同类问题第二次失败换路，第三次列根因表，第四次升级。\r\n\r\n" +
                "AGOS-CONFIRM：开工前一次性定调开发与软件框架（12 域契约，用户明确确认，不超时），落盘 .agentos\\contract；后续需求以修订迭代，任务绑定 contract_version 并跑 AgentOS-Contract.ps1 check。\\r\\n\\r\\n" +
                "AGOS-AUTO：已授权普通工作直接推进。完整推荐落盘并实际通知后，普通偏好 300 秒无反馈按既有委托采用，记 delegated_default。安全、未知事实、锁定 SSOT、宿主权限和真实验收不超时放行。每个 Unit/恢复点先记录反馈再 evaluate .agentos/decisions，等待期间推进独立工作。该明确用户授权更新旧的非安全无限等待规则。读取 protocols/DELEGATED-AUTONOMY.md。\r\n\r\n" +
                "AgentOS 目录：" + root + "（也可通过 `$env:AGENTOS_HOME` 定位）。客户端适配器、长程协议和安全宪法均以该目录为单一事实源。\r\n" +
                "## AgentOS truth gate\r\n" +
                "No source means no verified fact. Synthetic, failed, stale or conflicted evidence cannot satisfy delivery.\r\n" +
                "Read runtime\\AGENT-IMPORT.md and protocols\\TRUTH-AND-EVIDENCE.md at every new conversation.\r\n" +
                ManagedEnd;
        }

        private static string GetMiniMaxBlock()
        {
            return MiniMaxBegin + "\r\n" +
                "## AgentOS 系统治理（托管 v1.4.0）\r\n\r\n" +
                "AGOS-SKILLS：复杂任务读取 protocols/SKILL-MATRIX.md；agentos_skills.py 按输入/输出契约选主能力和必要约束，gate 产出；候选能力保持未部署，不预载全部。\r\n" +
                "每次复杂任务先读取 `$env:AGENTOS_HOME\\runtime\\BOOT.md`，再按需读取 AgentOS 宪法和长程协议。项目 `AGENTS.md`、需求 SSOT、契约和决策记录提供项目事实。\r\n\r\n" +
                "长任务必须有 `.agentos\\tasks\\` 任务单和 `.agentos\\checkpoints\\` 检查点；每个 Unit 立即验证并记录机器证据。没有证据不得声明完成。同类问题第二次失败换路，第三次列至少三个根因，第四次升级决策台或用户。授权读取 `policies\\APPROVAL-POLICY.json`；高风险动作必须逐次确认。\r\n" +
                "AGOS-AUTO：已授权普通工作直接推进；普通偏好完整推荐实际通知后 300 秒无反馈按委托采用，记 delegated_default。先记录实际新反馈再执行 bin/AgentOS-Decision.ps1 evaluate；安全、未知事实、宿主权限和真实验收不超时放行。等待时推进独立工作；读取 protocols/DELEGATED-AUTONOMY.md。\r\n" +
                "## AgentOS truth gate\r\n" +
                "No source means no verified fact. Synthetic, failed, stale or conflicted evidence cannot satisfy delivery.\r\n" +
                "Read runtime\\AGENT-IMPORT.md and protocols\\TRUTH-AND-EVIDENCE.md at every new conversation.\r\n" +
                MiniMaxEnd;
        }

        private static string JsonQuote(string value)
        {
            return new JavaScriptSerializer().Serialize(value);
        }

        private static string ReadUtf8(string path)
        {
            return File.ReadAllText(path, new UTF8Encoding(false));
        }

        private static void WriteUtf8(string path, string content)
        {
            string parent = Path.GetDirectoryName(path);
            if (!String.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
            File.WriteAllText(path, content, new UTF8Encoding(false));
        }
    }

    internal sealed class InstallerForm : Form
    {
        private readonly string payloadRoot;
        private TextBox agentOsTarget;
        private TextBox miniMaxPath;
        private TextBox kimiPath;
        private TextBox projects;
        private TextBox logBox;
        private Button installButton;
        private ComboBox approvalScope;

        public InstallerForm()
        {
            payloadRoot = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "AgentOS-Payload");
            Text = "Agent Governance OS 安装器";
            Width = 820;
            Height = 650;
            MinimumSize = new Size(720, 560);
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            BuildControls();
            LoadDefaults();
        }

        private void BuildControls()
        {
            var title = new Label
            {
                Text = "Agent Governance OS",
                Font = new Font(Font.FontFamily, 16, FontStyle.Bold),
                AutoSize = true,
                Location = new Point(24, 18)
            };
            Controls.Add(title);

            var note = new Label
            {
                Text = "透明安装：不联网、不保存凭据、不启动子进程。安装器只写入 AgentOS、客户端 skill 和项目治理入口。",
                AutoSize = true,
                Location = new Point(26, 52)
            };
            Controls.Add(note);

            int y = 92;
            agentOsTarget = AddPathRow("AgentOS 目标目录", ref y, true);
            miniMaxPath = AddPathRow("MiniMax Code 安装目录", ref y, true);
            kimiPath = AddPathRow("Kimi Code 安装/配置目录", ref y, true);

            var approvalLabel = new Label { Text = "普通操作默认授权域", AutoSize = true, Location = new Point(26, y + 5) };
            Controls.Add(approvalLabel);
            approvalScope = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Location = new Point(220, y), Width = 250 };
            approvalScope.Items.Add("session");
            approvalScope.Items.Add("task");
            approvalScope.Items.Add("turn");
            approvalScope.SelectedIndex = 0;
            Controls.Add(approvalScope);
            var approvalNote = new Label { Text = "session = 当前对话；高风险动作始终逐次确认", AutoSize = true, Location = new Point(484, y + 5) };
            Controls.Add(approvalNote);
            y += 40;

            var projectLabel = new Label { Text = "项目目录（每行一个，可留空）", AutoSize = true, Location = new Point(26, y + 4) };
            Controls.Add(projectLabel);
            projects = new TextBox { Multiline = true, ScrollBars = ScrollBars.Vertical, Location = new Point(220, y), Width = 520, Height = 82 };
            Controls.Add(projects);
            y += 102;

            installButton = new Button { Text = "安装 / 更新 AgentOS", Width = 170, Height = 34, Location = new Point(220, y) };
            installButton.Click += delegate { Install(); };
            Controls.Add(installButton);

            var selfTest = new Label { Text = "安装器目录必须包含 AgentOS-Payload；其他电脑直接复制整个安装器目录即可。", AutoSize = true, Location = new Point(26, y + 9) };
            Controls.Add(selfTest);
            y += 52;

            logBox = new TextBox { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, Location = new Point(24, y), Width = 716, Height = 380, Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right };
            Controls.Add(logBox);
        }

        private TextBox AddPathRow(string labelText, ref int y, bool browse)
        {
            var label = new Label { Text = labelText, AutoSize = true, Location = new Point(26, y + 5) };
            Controls.Add(label);
            var box = new TextBox { Location = new Point(220, y), Width = 440 };
            Controls.Add(box);
            if (browse)
            {
                var button = new Button { Text = "浏览...", Width = 76, Location = new Point(666, y - 1) };
                button.Click += delegate
                {
                    using (var dialog = new FolderBrowserDialog())
                    {
                        dialog.SelectedPath = Directory.Exists(box.Text) ? box.Text : Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
                        if (dialog.ShowDialog(this) == DialogResult.OK) box.Text = dialog.SelectedPath;
                    }
                };
                Controls.Add(button);
            }
            y += 40;
            return box;
        }

        private void LoadDefaults()
        {
            string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            string configured = Environment.GetEnvironmentVariable("AGENTOS_HOME", EnvironmentVariableTarget.User);
            agentOsTarget.Text = String.IsNullOrWhiteSpace(configured) ? Path.Combine(home, ".agentos-system") : configured;
            miniMaxPath.Text = FindExisting(
                Path.Combine(home, "AppData", "Local", "Programs", "MiniMax Code"),
                Path.Combine(home, ".minimax"));
            kimiPath.Text = FindExisting(
                Path.Combine(home, ".kimi-code"),
                Path.Combine(home, ".vscode", "extensions"));
            AppendLog("Payload：" + payloadRoot);
            AppendLog("请选择路径后点击安装。已有 AgentOS 文件会按托管版本更新，项目代码不会被覆盖。");
        }

        private static string FindExisting(params string[] paths)
        {
            return paths.FirstOrDefault(Directory.Exists) ?? paths[0];
        }

        private void Install()
        {
            try
            {
                installButton.Enabled = false;
                var projectRoots = projects.Lines.Where(line => !String.IsNullOrWhiteSpace(line)).Select(line => line.Trim()).ToArray();
                foreach (string project in projectRoots)
                {
                    if (!Directory.Exists(project)) throw new DirectoryNotFoundException("项目目录不存在：" + project);
                }
                InstallerEngine.Install(
                    payloadRoot,
                    agentOsTarget.Text,
                    miniMaxPath.Text,
                    kimiPath.Text,
                    projectRoots,
                    Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                    approvalScope.SelectedItem.ToString(),
                    AppendLog);
                AppendLog("安装完成。请完全退出并重新打开 MiniMax Code、VS Code/Kimi Code。");
                MessageBox.Show(this, "AgentOS 安装完成。请重新打开客户端和项目。", "完成", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                AppendLog("失败：" + ex.Message);
                MessageBox.Show(this, ex.Message, "安装失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally
            {
                installButton.Enabled = true;
            }
        }

        private void AppendLog(string message)
        {
            if (logBox == null) return;
            logBox.AppendText("[" + DateTime.Now.ToString("HH:mm:ss") + "] " + message + Environment.NewLine);
        }
    }

    internal static class SelfTest
    {
        public static int Run(string baseDirectory, Action<string> log)
        {
            string payload = Path.Combine(baseDirectory, "AgentOS-Payload");
            string root = Path.Combine(Path.GetTempPath(), "AgentOS-Installer-selftest-" + Guid.NewGuid().ToString("N"));
            string user = Path.Combine(root, "user");
            string project = Path.Combine(root, "project");
            string target = Path.Combine(root, "installed-agentos");
            string previousHome = Environment.GetEnvironmentVariable("AGENTOS_HOME", EnvironmentVariableTarget.User);
            try
            {
                Directory.CreateDirectory(Path.Combine(user, ".minimax", "agents", "mavis"));
                Directory.CreateDirectory(Path.Combine(root, "MiniMax Code"));
                Directory.CreateDirectory(Path.Combine(root, "Kimi Code"));
                Directory.CreateDirectory(project);
                File.WriteAllText(Path.Combine(project, "AGENTS.md"), "# self test\r\n<!-- AGENTOS:BEGIN managed v1.0.0 -->\r\nold project entry\r\n<!-- AGENTOS:END managed -->\r\noriginal tail\r\n", new UTF8Encoding(false));
                string miniMaxAgent = Path.Combine(user, ".minimax", "agents", "mavis", "agent.md");
                string oldOverlay = "<!-- AGENTOS:BEGIN minimax overlay -->\r\nold overlay\r\n<!-- AGENTOS:END minimax overlay -->\r\n";
                File.WriteAllText(miniMaxAgent, "original agent\r\n" + oldOverlay + oldOverlay, new UTF8Encoding(false));
                InstallerEngine.Install(payload, target, Path.Combine(root, "MiniMax Code"), Path.Combine(root, "Kimi Code"), new[] { project }, user, "session", log, false);
                Require(File.Exists(Path.Combine(target, "VERSION")), "target VERSION");
                Require(File.Exists(Path.Combine(target, "runtime", "AGENT-IMPORT.md")), "import contract");
                Require(File.Exists(Path.Combine(target, "protocols", "TRUTH-AND-EVIDENCE.md")), "truth protocol");
                Require(File.Exists(Path.Combine(target, "bin", "AgentOS-Evidence.ps1")), "evidence tool");
                var serializer = new JavaScriptSerializer();
                Require((string)serializer.Deserialize<Dictionary<string, object>>(Read(Path.Combine(target, "policies", "APPROVAL-POLICY.json")))["default_scope"] == "session", "approval policy");
                Require(File.Exists(Path.Combine(user, ".minimax", "agents", "mavis", "agent.md")), "MiniMax overlay");
                Require(File.Exists(Path.Combine(user, ".minimax", "agents", "mavis", "skills", "agent-governance-os", "SKILL.md")), "MiniMax skill");
                Require(File.Exists(Path.Combine(user, ".kimi", "skills", "agent-governance-os", "SKILL.md")), "Kimi skill");
                Require(File.Exists(Path.Combine(user, ".kimi-code", "skills", "agent-governance-os", "SKILL.md")), "Kimi Code skill");
                Require(File.Exists(Path.Combine(project, ".agentos", "project.json")), "project state");
                Require(File.Exists(Path.Combine(project, ".agentos", "working-memory.json")), "working memory");
                Require(Directory.Exists(Path.Combine(project, ".agentos", "approvals")), "approval state");
                Require(Read(Path.Combine(project, "AGENTS.md")).Contains(ManagedMarker()), "project entry");
                Require(File.Exists(Path.Combine(target, "bin", "AgentOS-Decision.ps1")), "decision tool");
                Require(Directory.Exists(Path.Combine(project, ".agentos", "decisions")), "decision state");
                Require(Directory.Exists(Path.Combine(project, ".agentos", "contract")), "contract state");
                Require(File.Exists(Path.Combine(target, "bin", "AgentOS-Contract.ps1")), "contract tool");
                Require(File.Exists(Path.Combine(target, "protocols", "UPFRONT-CONFIRMATION.md")), "confirmation protocol");
                Require(File.Exists(Path.Combine(target, "policies", "INTERACTION-POLICY.json")), "interaction policy");
                Require(File.Exists(Path.Combine(target, "policies", "SKILL-REGISTRY.json")), "capability registry");
                Require(File.Exists(Path.Combine(target, "bin", "agentos_skills.py")), "capability inspector");
                foreach (string methodRoot in new[] {
                    Path.Combine(user, ".codex", "skills"),
                    Path.Combine(user, ".minimax", "agents", "mavis", "skills"),
                    Path.Combine(user, ".kimi", "skills"), Path.Combine(user, ".kimi-code", "skills") })
                    Require(File.Exists(Path.Combine(methodRoot, "production-skill-routing", "SKILL.md")), "method Skill for each client");
                var projectData = serializer.Deserialize<Dictionary<string, object>>(Read(Path.Combine(project, ".agentos", "project.json")));
                Require((string)projectData["project_root"] == project && (string)projectData["status_file"] == ".agentos\\status.json", "parsed project paths");
                string statusPath = Path.Combine(project, ".agentos", "status.json");
                string memoryPath = Path.Combine(project, ".agentos", "working-memory.json");
                var statusData = serializer.Deserialize<Dictionary<string, object>>(Read(statusPath));
                var memoryData = serializer.Deserialize<Dictionary<string, object>>(Read(memoryPath));
                Require((string)memoryData["agentos_version"] == "1.4.0", "new working-memory version");
                statusData["active_task"] = "preserved_task";
                memoryData["active_task"] = "preserved_task";
                File.WriteAllText(statusPath, serializer.Serialize(statusData), new UTF8Encoding(false));
                File.WriteAllText(memoryPath, serializer.Serialize(memoryData), new UTF8Encoding(false));
                string beforeStatus = Read(statusPath);
                string beforeAgent = Read(miniMaxAgent);
                InstallerEngine.Install(payload, target, "", "", new[] { project }, user, "task", log, false);
                Require(Read(statusPath) == beforeStatus, "status preservation");
                Require((string)serializer.Deserialize<Dictionary<string, object>>(Read(memoryPath))["active_task"] == "preserved_task", "working memory preservation");
                Require(Read(miniMaxAgent) == beforeAgent && Read(miniMaxAgent).Split(new[] { "AGENTOS:BEGIN minimax overlay" }, StringSplitOptions.None).Length == 2, "repeat overlay without duplicates");
                Require(Read(miniMaxAgent).Contains("original agent") && Read(Path.Combine(project, "AGENTS.md")).Contains("original tail"), "original instructions preserved");
                Require(Read(Path.Combine(project, "AGENTS.md")).Split(new[] { ManagedMarker() }, StringSplitOptions.None).Length == 2, "one upgraded project entry");
                Require(Read(Path.Combine(project, "AGENTS.md")).Contains("SKILL-MATRIX.md"), "skill router project import");
                string customMethod = Path.Combine(user, ".codex", "skills", "production-skill-routing", "local-note.md");
                File.WriteAllText(customMethod, "preserve local customization", new UTF8Encoding(false));
                bool customBlocked = false;
                try { InstallerEngine.Install(payload, target, "", "", new[] { project }, user, "task", log, false); }
                catch (InvalidOperationException) { customBlocked = true; }
                Require(customBlocked && Read(customMethod) == "preserve local customization", "modified method Skill preserved and blocked");
                Require((string)serializer.Deserialize<Dictionary<string, object>>(Read(Path.Combine(target, "policies", "APPROVAL-POLICY.json")))["default_scope"] == "task", "repeat scope selection");
                Require(Environment.GetEnvironmentVariable("AGENTOS_HOME", EnvironmentVariableTarget.User) == previousHome, "self-test leaves user environment unchanged");
                log("Parsed JSON, old-marker upgrade, duplicate cleanup, repeat install and task-state preservation passed.");
                log("Installer self-test passed.");
                return 0;
            }
            catch (Exception ex)
            {
                log("Installer self-test failed: " + ex.Message);
                return 1;
            }
            finally
            {
                string temporaryBase = Path.GetFullPath(Path.GetTempPath()).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
                if (!Path.GetFullPath(root).StartsWith(temporaryBase, StringComparison.OrdinalIgnoreCase) || !Path.GetFileName(root).StartsWith("AgentOS-Installer-selftest-", StringComparison.Ordinal))
                    throw new InvalidOperationException("Refusing cleanup outside self-test directory.");
                if (Directory.Exists(root)) Directory.Delete(root, true);
            }
        }

        private static string ManagedMarker() { return "AGENTOS:BEGIN managed"; }
        private static string Read(string path) { return File.ReadAllText(path, new UTF8Encoding(false)); }
        private static void Require(bool value, string name) { if (!value) throw new InvalidOperationException("missing " + name); }
    }
}
