#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pcba_gate — 通用 PCBA 阶段门禁引擎（跨案复用）。

Usage:
  pcba_gate.py intent-check --root <项目根>
  pcba_gate.py run --root <项目根> [--config standards/stage_gates.yaml]
  pcba_gate.py verify --root <项目根>

约定（项目根目录下）：
  standards/design_intent.yaml   设计意图登记册
  standards/stage_gates.yaml     门禁定义（exit_evidence + checks + 级联失效）
  outputs/release/               manifest 与报告输出
checks DSL: text_contains / zip_contains / file_empty / command
"""
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def log(msg):
    print(msg)


class GateEngine:
    def __init__(self, root: Path, config: Path | None = None):
        self.root = root
        self.intent_path = root / "standards" / "design_intent.yaml"
        self.config_path = config or (root / "standards" / "stage_gates.yaml")
        self.out_dir = root / "outputs" / "release"
        self.manifest_path = self.out_dir / "release_manifest.json"
        self.report_path = self.out_dir / "gate_report.md"

    # ── P0: 意图登记册完整性 ──
    def intent_check(self):
        d = yaml.safe_load(self.intent_path.read_text(encoding="utf-8"))
        errs = []
        if not d.get("north_star", {}).get("hard_constraints"):
            errs.append("north_star.hard_constraints 为空")
        ats, eis = d.get("acceptance_targets", []), d.get("engineering_intent", [])
        if not ats:
            errs.append("acceptance_targets 为空")
        for g in ats:
            for k in ("id", "metric", "target", "verify_by", "evidence"):
                if not g.get(k):
                    errs.append(f"acceptance_targets[{g.get('id','?')}] 缺 {k}")
        if not eis:
            errs.append("engineering_intent 为空")
        for e in eis:
            for k in ("id", "intent", "verify", "gate"):
                if not e.get(k):
                    errs.append(f"engineering_intent[{e.get('id','?')}] 缺 {k}")
        if errs:
            [log(f"  - {e}") for e in errs]
            sys.exit(f"FAIL: design_intent.yaml 有 {len(errs)} 个问题")
        log(f"OK: 意图登记册完整 — {len(ats)} 指标 / {len(eis)} 工程意图 / "
            f"{len(d['north_star']['hard_constraints'])} 硬约束")

    # ── 声明式检查 ──
    def run_check(self, c: dict) -> tuple[bool, str]:
        t = c.get("type")
        desc = c.get("desc", t or "?")
        try:
            if t == "text_contains":
                p = self.root / c["path"]
                ok = p.exists() and c["contains"] in p.read_text(encoding="utf-8", errors="ignore")
            elif t == "zip_contains":
                p = self.root / c["path"]
                ok = p.exists() and any(c["pattern"] in n for n in zipfile.ZipFile(p).namelist())
            elif t == "file_empty":
                p = self.root / c["path"]
                ok = p.exists() and not p.read_text(encoding="utf-8", errors="ignore").strip()
            elif t == "command":
                r = subprocess.run(c["run"], shell=True, cwd=self.root / c.get("cwd", "."),
                                   capture_output=True, timeout=c.get("timeout", 300))
                ok = r.returncode == 0
                if not ok:
                    return False, f"{desc}（退出码 {r.returncode}）"
            else:
                return False, f"{desc}（未知检查类型 {t}）"
        except Exception as e:  # noqa: BLE001
            return False, f"{desc}（异常 {e}）"
        return (True, desc) if ok else (False, f"{desc}【未通过】")

    # ── 全门禁（单遍：manifest 视为本遍生成物，不参与自身存在性/哈希） ──
    def collect(self):
        d = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        project = yaml.safe_load(self.intent_path.read_text(encoding="utf-8")).get("project") \
            if self.intent_path.exists() else None
        manifest = {"project": project,
                    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                    "config": str(self.config_path.relative_to(self.root)),
                    "gates": {}, "files": {}}
        lines = ["# 门禁执行报告（gate_report）",
                 f"> {manifest['generated_at']} | pcba_gate v1.0 | project={project}", "",
                 "| 门禁 | 名称 | 结果 | 证据/检查 |", "|---|---|---|---|"]
        overall = "PASS"
        for g in d.get("gates", []):
            gid, gname = g["id"], g["name"]
            missing, present, notes = [], [], []
            for ev in g.get("exit_evidence", []):
                p = self.root / ev["path"]
                if p.exists() or p == self.manifest_path:  # manifest 是本遍产物
                    present.append((ev["path"], ev.get("role", ""), p))
                else:
                    missing.append(ev["path"])
            verdict = "PASS" if not missing else "FAIL"
            for c in g.get("checks", []):
                ok, msg = self.run_check(c)
                notes.append(("✓ " if ok else "✘ ") + msg)
                if not ok:
                    verdict = "FAIL"
            if g.get("pending_if_missing") and missing:
                verdict = "PENDING"
                notes.append("样机/下游未完成，允许 PENDING")
            if verdict == "FAIL":
                overall = "FAIL"
            manifest["gates"][gid] = {"name": gname, "verdict": verdict,
                                      "checklist": g.get("checklist"),
                                      "evidence": {ev["path"]: ("present" if ((self.root / ev["path"]).exists()
                                                                               or (self.root / ev["path"]) == self.manifest_path)
                                                                else "MISSING")
                                                   for ev in g.get("exit_evidence", [])}}
            for path, role, p in present:
                if p == self.manifest_path:
                    continue
                manifest["files"][path] = {"sha256": "(目录)" if p.is_dir() else sha256(p),
                                           "role": role, "gate": gid}
            evs = f"证据 {len(present)}/{len(g.get('exit_evidence', []))}"
            if missing:
                evs += "；缺失: " + ", ".join(missing)
            if notes:
                evs += "；" + "；".join(notes)
            lines.append(f"| {gid} | {gname} | {verdict} | {evs} |")
        lines += ["", f"**总体结论：{overall}**", "",
                  "> 引擎核验证据在位/哈希/声明式检查；清单人工勾选须在 decisions 日志留痕。"]
        return manifest, overall, lines

    def run(self):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        manifest, overall, lines = self.collect()
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self.report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log(f"报告: {self.report_path}")
        log(f"清单: {self.manifest_path}（{len(manifest['files'])} 个文件哈希）")
        log(f"总体结论: {overall}")
        sys.exit(0 if overall == "PASS" else 2)

    def verify(self):
        if not self.manifest_path.exists():
            sys.exit("FAIL: manifest 不存在，先 run")
        m = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        drift = []
        for path, info in m["files"].items():
            if info["sha256"] == "(目录)":
                continue
            p = self.root / path
            if not p.exists():
                drift.append(f"缺失: {path}")
            elif sha256(p) != info["sha256"]:
                drift.append(f"哈希漂移: {path}")
        if drift:
            [log(f"  ✘ {x}") for x in drift]
            sys.exit(f"FAIL: {len(drift)} 处漂移 — 发布作废，按级联失效重跑门禁")
        log(f"OK: {len(m['files'])} 个关键文件哈希一致，发布有效")


def main():
    ap = argparse.ArgumentParser(description="pcba_gate 通用门禁引擎")
    ap.add_argument("cmd", choices=["intent-check", "run", "verify"])
    ap.add_argument("--root", default=".", help="项目根目录")
    ap.add_argument("--config", default=None, help="门禁定义 yaml（默认 <root>/standards/stage_gates.yaml）")
    a = ap.parse_args()
    eng = GateEngine(Path(a.root).resolve(), Path(a.config).resolve() if a.config else None)
    {"intent-check": eng.intent_check, "run": eng.run, "verify": eng.verify}[a.cmd]()


if __name__ == "__main__":
    main()
