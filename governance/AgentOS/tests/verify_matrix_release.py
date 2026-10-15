"""Verify real source/payload tests, package hashes and installed client assets.

Writes a new local evidence directory; never overwrites prior reports. No network,
hardware, provider execution or client restart. Synthetic test inputs remain labeled.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def run(arguments, output):
    environment = dict(os.environ)
    if Path(arguments[0]).name.lower() == "powershell.exe":
        # A Python child of pwsh inherits PS7 modules; PS5.1 needs its own builtins.
        modules = Path(os.environ["SYSTEMROOT"]) / "System32/WindowsPowerShell/v1.0/Modules"
        environment = {key: value for key, value in environment.items() if key.casefold() != "psmodulepath"}
        environment["PSMODULEPATH"] = str(modules)
    completed = subprocess.run(arguments, capture_output=True, timeout=180, env=environment)
    with output.open("xb") as stream:
        stream.write(completed.stdout + completed.stderr)
    require(completed.returncode == 0, "Verification failed; see " + str(output))
    return {"command": arguments, "exit_code": completed.returncode, "output_complete": True,
            "log": str(output), "sha256": sha(output), "finished_at": datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--objective", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    package = ROOT / "dist/AgentOS-Installer"
    payload = package / "AgentOS-Payload"
    version = (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip()
    results = []
    for label, root in [("source", ROOT), ("payload", payload)]:
        for test in ["Test-AgentOS.ps1", "Test-AgentOS-Decision.ps1", "Test-AgentOS-Contract.ps1", "Test-AgentOS-Evidence.ps1"]:
            path = root / "tests" / test
            results.append(run(["powershell.exe", "-NoProfile", "-File", str(path), "-AgentOsRoot", str(root)],
                               args.output / (label + "-" + test + ".log")))
        results.append(run([sys.executable, "-B", str(root / "tests/test_agentos_skills.py")],
                           args.output / (label + "-matrix-tests.log")))
    registry = json.loads((ROOT / "policies/SKILL-REGISTRY.json").read_text(encoding="utf-8-sig"))
    objective_text = args.objective.read_text(encoding="utf-8-sig")
    requested = set(re.findall(r"(?m)^((?:req|arch|plan|hw|mech|id|emb|sw|ui|qa|mfg|km|meta)-[a-z0-9-]+)\s", objective_text))
    actual = {x["id"] for x in registry["capabilities"]}
    require(len(requested) == 63 and actual == requested, "Objective capability IDs not fully accounted for")
    require({x["domain"] for x in registry["capabilities"]} == set("ABCDEFGH"), "Missing domain")

    verified_files = []
    for line in (package / "SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines():
        match = re.fullmatch(r"([A-Fa-f0-9]{64})  (.+)", line)
        require(match is not None, "Malformed hash manifest")
        relative = match[2].replace("\\", "/")
        path = (package / relative).resolve()
        require(package.resolve() in path.parents and sha(path).lower() == match[1].lower(), "Package hash mismatch: " + relative)
        verified_files.append(relative)
    actual_files = {x.relative_to(package).as_posix() for x in package.rglob("*") if x.is_file() and x.name != "SHA256SUMS.txt"}
    require(set(verified_files) == actual_files and len(verified_files) == len(set(verified_files)), "Hash inventory has gaps/duplicates")
    archive = ROOT / "dist/AgentOS-Installer.zip"
    with zipfile.ZipFile(archive) as zipped:
        expected_entries = {"AgentOS-Installer/" + x for x in actual_files | {"SHA256SUMS.txt"}}
        require({x.filename for x in zipped.infolist() if not x.is_dir()} == expected_entries, "ZIP inventory differs")
        for relative in actual_files | {"SHA256SUMS.txt"}:
            require(hashlib.sha256(zipped.read("AgentOS-Installer/" + relative)).hexdigest() == sha(package / relative), "ZIP content differs: " + relative)
    for directory in ["adapters", "bin", "constitution", "policies", "profiles", "protocols", "runtime", "templates", "tests", "skills"]:
        for source in (ROOT / directory).rglob("*"):
            if source.is_file():
                require(sha(source) == sha(payload / source.relative_to(ROOT)), "Payload drift: " + str(source))
    require((payload / "VERSION").read_text().strip() == version, "Payload version differs")

    users = {"codex": Path.home() / ".codex/skills", "minimax": Path.home() / ".minimax/agents/mavis/skills",
             "kimi": Path.home() / ".kimi/skills", "kimi-code": Path.home() / ".kimi-code/skills"}
    method_source = ROOT / "skills/production-skill-routing"
    source_tree = {p.relative_to(method_source).as_posix(): sha(p) for p in method_source.rglob("*") if p.is_file()}
    clients = []
    for client, base in users.items():
        method = base / "production-skill-routing"
        tree = {p.relative_to(method).as_posix(): sha(p) for p in method.rglob("*") if p.is_file()}
        require(tree == source_tree, "Installed method drift: " + client)
        if client != "codex":
            adapter = ROOT / "adapters" / ("minimax" if client == "minimax" else "kimi") / "SKILL.md"
            require(sha(base / "agent-governance-os/SKILL.md") == sha(adapter), "Adapter drift: " + client)
        output = args.output / (client + "-capabilities.json")
        result = run([sys.executable, "-B", str(ROOT / "bin/agentos_skills.py"), "catalog", "--project", str(args.project), "--client", client], output)
        catalog = json.loads(output.read_text(encoding="utf-8"))
        statuses = {}
        for entry in catalog["capabilities"]:
            statuses[entry["provider_status"]] = statuses.get(entry["provider_status"], 0) + 1
        require(statuses.get("available_files_only") == 36 and statuses.get("candidate_unavailable") == 27,
                "Live provider availability differs from declared deployment: " + client)
        clients.append({"client": client, "method_files": tree, "availability": statuses, "evidence": result})
    overlay = (Path.home() / ".minimax/agents/mavis/agent.md").read_text(encoding="utf-8-sig")
    require(overlay.count("<!-- AGENTOS:BEGIN minimax overlay -->") == 1 and "AGOS-SKILLS" in overlay, "MiniMax overlay missing or duplicated")
    audit = max((ROOT / "reports").glob("security-build-*.json"), key=lambda p: p.stat().st_mtime)
    audits = json.loads(audit.read_text(encoding="utf-8-sig"))
    audited_paths = {x["file"] for x in audits}
    for new_code in [ROOT / "bin/agentos_skills.py", ROOT / "tests/test_agentos_skills.py", Path(__file__).resolve()]:
        require(str(new_code) in audited_paths, "New code not covered by scanner: " + str(new_code))
    require(audits and all(x["summary"]["critical"] == 0 and x["summary"]["warning"] == 0 for x in audits), "Static scanner finding")
    require("Installer self-test passed." in (package / "installer-self-test.log").read_text(encoding="utf-8-sig"), "Missing installer success evidence")
    report = {"schema": "agentos-matrix-release-v1", "version": version,
              "generated_at": datetime.now(timezone.utc).isoformat(), "objective_sha256": sha(args.objective),
              "capability_count": len(actual), "domains": "ABCDEFGH", "test_suites": results,
              "package_files": len(verified_files), "zip_contents_match": True,
              "exe_sha256": sha(package / "AgentOS-Installer.exe"), "zip_sha256": sha(archive),
              "security": {"report": str(audit), "sha256": sha(audit), "files_scanned": len(audits), "critical": 0, "warning": 0},
              "clients": clients,
              "limits": ["Test input/feedback fixtures are synthetic; execution logs are actual software verification.",
                         "Provider availability is file inspection, not autonomous client invocation or specialist validation.",
                         "No model-quality gain, standards certification, physical acceptance or new scheduler is claimed."]}
    save(args.output / "release.json", report)
    print(json.dumps({"status": "verified", "suites": len(results), "capabilities": len(actual),
                      "package_files": len(verified_files), "report": str(args.output / "release.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
