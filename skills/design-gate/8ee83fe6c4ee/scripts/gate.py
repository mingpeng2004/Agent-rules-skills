#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""design-gate 执行器：意图校验 / 门禁执行 / 版本一致性核验。

Usage:
  gate.py intent-check          校验 design_intent.yaml 完整性（S0）
  gate.py run                   执行全门禁 → release_manifest.json + gate_report.md
  gate.py verify                磁盘文件哈希 vs manifest 比对（F-08/A-08）
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]          # 项目工作区根
try:
    import yaml
except ImportError:
    sys.exit("FAIL: 需要 pyyaml（托管 Python 已内置）")

INTENT = ROOT / "standards" / "design_intent.yaml"
GATES = ROOT / "standards" / "stage_gates.yaml"
OUT_DIR = ROOT / "outputs" / "release"
MANIFEST = OUT_DIR / "release_manifest.json"
REPORT = OUT_DIR / "gate_report.md"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def cmd_intent_check():
    d = yaml.safe_load(INTENT.read_text(encoding="utf-8"))
    errs = []
    ns = d.get("north_star", {})
    if not ns.get("hard_constraints"):
        errs.append("north_star.hard_constraints 为空")
    ats = d.get("acceptance_targets", [])
    if len(ats) < 1:
        errs.append("acceptance_targets 为空")
    for g in ats:
        for k in ("id", "metric", "target", "verify_by", "evidence"):
            if not g.get(k):
                errs.append(f"acceptance_targets[{g.get('id','?')}] 缺字段 {k}")
    eis = d.get("engineering_intent", [])
    if len(eis) < 1:
        errs.append("engineering_intent 为空")
    for e in eis:
        for k in ("id", "intent", "verify", "gate"):
            if not e.get(k):
                errs.append(f"engineering_intent[{e.get('id','?')}] 缺字段 {k}")
    if errs:
        for e in errs:
            print("  -", e)
        fail(f"design_intent.yaml 完整性校验：{len(errs)} 个问题")
    print(f"OK: design_intent.yaml 完整 — {len(ns.get('hard_constraints', []))} 硬约束 / "
          f"{len(ats)} 验收指标 / {len(eis)} 工程意图")


def collect(skip_manifest_check=False):
    d = yaml.safe_load(GATES.read_text(encoding="utf-8"))
    manifest = {
        "project": yaml.safe_load(INTENT.read_text(encoding="utf-8")).get("project"),
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "gates": {},
        "files": {},
    }
    report_lines = [
        "# 门禁执行报告（gate_report）",
        f"> 生成时间: {manifest['generated_at']} | 执行器: design-gate v1.0",
        "",
        "| 门禁 | 名称 | 结果 | 证据情况 |",
        "|---|---|---|---|",
    ]
    overall = "PASS"
    for g in d.get("gates", []):
        gid, gname = g["id"], g["name"]
        missing, present = [], []
        for ev in g.get("exit_evidence", []):
            p = ROOT / ev["path"]
            if skip_manifest_check and p == MANIFEST:
                present.append((ev["path"], ev.get("role", ""), p))
            elif p.exists():
                present.append((ev["path"], ev.get("role", ""), p))
            else:
                missing.append(ev["path"])
        verdict = "PASS" if not missing else "FAIL"
        notes = []
        # S6 专项：缺料清单必须为空（清单 A-01 的机器化）
        if gid == "S6":
            miss = sorted((ROOT / "workspaces/CS5552_WCD_v4/kicad/mfg").glob("*_MISSING_LCSC.txt"))
            if miss and miss[0].read_text(encoding="utf-8", errors="ignore").strip():
                verdict, overall = "FAIL", "FAIL"
                notes.append(f"缺 LCSC 料号（见 {miss[0].relative_to(ROOT)}）")
        # S5 专项：Gerber 实际层数与 ORDER_README 声明一致（D23 2层误写事故防护）
        if gid == "S5":
            zips = sorted((ROOT / "workspaces/CS5552_WCD_v4/kicad/mfg").glob("*_JLC_Gerber.zip"))
            readme = ROOT / "workspaces/CS5552_WCD_v4/kicad/mfg/ORDER_README.md"
            if zips and readme.exists():
                import zipfile
                names = zipfile.ZipFile(zips[-1]).namelist()
                has_in1 = any("In1_Cu" in n for n in names)
                readme_txt = readme.read_text(encoding="utf-8", errors="ignore")
                if not has_in1 or "4 层" not in readme_txt:
                    verdict, overall = "FAIL", "FAIL"
                    notes.append("Gerber 层数与 ORDER_README 声明不一致（F-04 否决）")
        # S7：样机未回测 → PENDING（不算 FAIL，但设计未落地）
        if gid == "S7" and g.get("pending_if_missing") and missing:
            verdict = "PENDING"
            notes.append("样机实测未完成")
        if verdict == "FAIL":
            overall = "FAIL"
        manifest["gates"][gid] = {
            "name": gname,
            "verdict": verdict,
            "checklist": g.get("checklist"),
            "evidence": {ev["path"]: ("present" if ((ROOT / ev["path"]).exists() or
                                                   (skip_manifest_check and (ROOT / ev["path"]) == MANIFEST))
                                     else "MISSING")
                         for ev in g.get("exit_evidence", [])},
            "pass_rule": g.get("pass_rule"),
        }
        for path, role, p in present:
            if p == MANIFEST:
                continue  # 清单不能包含自身哈希（写入即失效），verify 也跳过
            if p.is_dir():
                manifest["files"][path] = {"sha256": "(目录)", "role": role, "gate": gid}
            else:
                manifest["files"][path] = {"sha256": sha256(p), "role": role, "gate": gid}
        ev_summary = f"{len(present)}/{len(g.get('exit_evidence', []))} 证据在位"
        if notes:
            ev_summary += "；" + "；".join(notes)
        if missing:
            ev_summary += "；缺失: " + ", ".join(missing)
        report_lines.append(f"| {gid} | {gname} | {verdict} | {ev_summary} |")
    report_lines += ["", f"**总体结论：{overall}**", "",
                     "> 注：本报告只核验证据文件在位与哈希；清单条目（checklists/*.md）",
                     "> 的人工勾选由执行者在 decisions.log 留痕，二者结合才算门禁通过。"]
    return manifest, overall, report_lines


def cmd_run():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # 两遍执行：第一遍生成 manifest（豁免 manifest 自身存在性检查），
    # 第二遍用落盘的 manifest 重新核验，消除自引用悖论
    manifest, overall, _ = collect(skip_manifest_check=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest, overall, report_lines = collect()
    REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"gate_report: {REPORT}")
    print(f"manifest:    {MANIFEST}（{len(manifest['files'])} 个文件哈希）")
    print(f"总体结论: {overall}")
    sys.exit(0 if overall == "PASS" else 2)


def cmd_verify():
    if not MANIFEST.exists():
        fail("manifest 不存在，先 run")
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    drift = []
    for path, info in m["files"].items():
        if info["sha256"] == "(目录)":
            continue
        p = ROOT / path
        if not p.exists():
            drift.append(f"缺失: {path}")
        elif sha256(p) != info["sha256"]:
            drift.append(f"哈希漂移: {path}（manifest {info['sha256'][:12]}… ≠ 磁盘 {sha256(p)[:12]}…）")
    if drift:
        for dline in drift:
            print("  ✘", dline)
        fail(f"版本一致性核验失败：{len(drift)} 处漂移 — 本次发布作废，按级联失效重跑门禁")
    print(f"OK: {len(m['files'])} 个关键文件哈希全部一致，发布版本有效")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    {"intent-check": cmd_intent_check, "run": cmd_run, "verify": cmd_verify}.get(
        cmd, lambda: fail(f"未知命令 {cmd}（intent-check/run/verify）"))()
