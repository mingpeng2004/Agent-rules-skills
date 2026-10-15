"""Local capability contracts, selective routing and result gates; stdlib only.

No command in this module executes a provider, contacts a network or grants
permissions. Reports are local inspection evidence, not authenticated authority.
"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid


ROOT = Path(__file__).resolve().parent.parent
ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
PROVIDER_FIELDS = {"id", "skill", "bundled"}
CAP_FIELDS = {"id", "domain", "group", "availability", "provider", "triggers",
              "scenarios", "inputs", "outputs", "workflow", "acceptance",
              "failure_modes", "upstream", "downstream", "resources", "limits"}
RISKS = {"static": "E1", "software": "E2", "integration": "E3",
         "physical": "E4", "production": "E4"}
CLIENTS = {"codex": ".codex/skills", "minimax": ".minimax/agents/mavis/skills",
           "kimi": ".kimi/skills", "kimi-code": ".kimi-code/skills"}


class Blocked(ValueError):
    pass


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Blocked("duplicate JSON field: " + key)
            result[key] = value
        return result
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)
    except (ValueError, OSError) as exc:
        raise Blocked("unreadable/invalid JSON: " + str(path) + ": " + str(exc)) from exc


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def time_value(text):
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise Blocked("invalid timestamp") from exc
    if value.tzinfo is None:
        raise Blocked("timestamp requires timezone")
    return value


def contained(base, relative, must_exist=True):
    base = Path(base)
    if base.is_symlink() or (hasattr(base, "is_junction") and base.is_junction()):
        raise Blocked("root link/junction rejected")
    base = base.resolve()
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise Blocked("expected a contained relative path: " + str(relative))
    target = base / rel
    for node in [target, *target.parents]:
        if node == base:
            break
        if node.is_symlink() or (hasattr(node, "is_junction") and node.is_junction()):
            raise Blocked("link/junction rejected: " + str(node))
    target = target.resolve()
    if base not in target.parents:
        raise Blocked("path escapes root")
    if must_exist and not target.is_file():
        raise Blocked("required file missing: " + str(target))
    return target


def asset(base, relative):
    path = contained(base, relative)
    return {"path": str(path), "sha256": digest(path)}


def check_assets(items):
    if not items:
        raise Blocked("empty source binding")
    for item in items:
        path = Path(item["path"])
        if not path.is_file() or digest(path) != item["sha256"]:
            raise Blocked("source changed/missing: " + str(path))


def text_list(value, label, empty=False):
    if not isinstance(value, list) or (not value and not empty) or any(
            not isinstance(x, str) or not x.strip() for x in value):
        raise Blocked("invalid string array: " + label)


def registry(path):
    data = read_json(path)
    expected = {"schema", "version", "agentos_version", "selection", "providers", "capabilities"}
    if set(data) != expected or data["schema"] != "agentos-skill-registry-v1":
        raise Blocked("invalid registry envelope/unknown fields")
    if data["selection"] != {"max_constraints": 2, "tie": "blocked_ambiguous",
                             "precedence": ["project", "client", "bundled"], "unknown": "blocked"}:
        raise Blocked("unsupported selection policy")
    providers = {}
    for provider in data["providers"]:
        if set(provider) != PROVIDER_FIELDS or not ID.fullmatch(provider["id"]) or not ID.fullmatch(provider["skill"]):
            raise Blocked("invalid provider contract")
        if provider["id"] in providers:
            raise Blocked("duplicate provider")
        if provider["bundled"]:
            if Path(provider["bundled"]).is_absolute() or ".." in Path(provider["bundled"]).parts:
                raise Blocked("invalid bundled provider path")
        providers[provider["id"]] = provider
    caps, triggers = {}, {}
    for cap in data["capabilities"]:
        if set(cap) != CAP_FIELDS or not ID.fullmatch(cap["id"]):
            raise Blocked("incomplete capability contract or unknown field")
        if cap["id"] in caps or cap["domain"] not in "ABCDEFGH" or len(cap["domain"]) != 1:
            raise Blocked("duplicate ID or invalid domain")
        for field in ("triggers", "scenarios", "inputs", "workflow", "acceptance"):
            text_list(cap[field], field)
        for field in ("upstream", "downstream", "resources"):
            text_list(cap[field], field, empty=True)
        if cap["inputs"] != ["task", "goals", "constraints"]:
            raise Blocked("unsupported input roles")
        if cap["availability"] not in {"mapped", "protocol", "candidate"}:
            raise Blocked("invalid availability")
        if cap["availability"] == "candidate":
            if cap["provider"] is not None or cap["resources"]:
                raise Blocked("candidate cannot advertise an executable provider")
        elif cap["provider"] not in providers or not cap["resources"]:
            raise Blocked("provider/resources missing")
        if not isinstance(cap["limits"], str) or not cap["limits"].strip():
            raise Blocked("limits missing")
        if not cap["outputs"] or any(set(x) != {"id", "format", "purpose"} or
                any(not isinstance(v, str) or not v.strip() for v in x.values()) for x in cap["outputs"]):
            raise Blocked("invalid output contract")
        if len(cap["outputs"]) != 1 or cap["outputs"][0]["id"] != "result":
            raise Blocked("unsupported output role")
        if len(cap["failure_modes"]) < 3 or any(set(x) != {"failure", "response"} or
                any(not isinstance(v, str) or not v.strip() for v in x.values()) for x in cap["failure_modes"]):
            raise Blocked("failure-mode contract incomplete")
        for trigger in cap["triggers"]:
            key = trigger.casefold()
            if key in triggers:
                raise Blocked("trigger conflict: " + trigger + " with " + triggers[key])
            triggers[key] = cap["id"]
        caps[cap["id"]] = cap
    if not caps:
        raise Blocked("empty registry cannot pass")
    for cap in caps.values():
        if any(x not in caps or x == cap["id"] for x in cap["upstream"] + cap["downstream"]):
            raise Blocked("unknown/self graph edge")
        for parent in cap["upstream"]:
            if cap["id"] not in caps[parent]["downstream"]:
                raise Blocked("nonreciprocal graph edge")
        for child in cap["downstream"]:
            if cap["id"] not in caps[child]["upstream"]:
                raise Blocked("nonreciprocal graph edge")
    def visit(key, visiting, done):
        if key in visiting:
            raise Blocked("cyclic skill graph")
        if key not in done:
            visiting.add(key)
            for parent in caps[key]["upstream"]:
                visit(parent, visiting, done)
            visiting.remove(key)
            done.add(key)
    done = set()
    for key in caps:
        visit(key, set(), done)
    return data, caps, providers


def resolve_provider(provider, project, client, user_root=None, system_root=ROOT):
    user_root = Path(user_root or Path.home())
    roots = [("project", Path(project) / "skills" / provider["skill"])]
    roots.append(("client", user_root / CLIENTS[client] / provider["skill"]))
    if provider["bundled"]:
        roots.append(("bundled", Path(system_root) / provider["bundled"]))
    for scope, root in roots:
        if (root / "SKILL.md").is_file():
            entry = contained(root, "SKILL.md")
            text = entry.read_text(encoding="utf-8-sig")
            if not re.search(r"(?m)^name:\s*[\"']?" + re.escape(provider["skill"]) + r"[\"']?\s*$", text):
                raise Blocked("provider identity mismatch: " + str(entry))
            return root, scope
    raise Blocked("provider unavailable for client: " + provider["skill"])


def select(caps, task, explicit=None):
    if explicit:
        if explicit not in caps:
            raise Blocked("unknown capability: " + explicit)
        return caps[explicit]
    matches = []
    for cap in caps.values():
        score = sum(1 for term in cap["triggers"] if term.casefold() in task.casefold())
        if score:
            matches.append((score, cap["id"]))
    if not matches:
        raise Blocked("no matching capability; specify --capability after investigation")
    best = max(x[0] for x in matches)
    choices = [key for score, key in matches if score == best]
    if len(choices) != 1:
        raise Blocked("ambiguous capabilities: " + ", ".join(sorted(choices)))
    return caps[choices[0]]


def project_files(project):
    project = Path(project).resolve()
    meta = read_json(project / ".agentos/project.json")
    bindings = [asset(project, "AGENTS.md"), asset(project, ".agentos/project.json")]
    contract = project / ".agentos/contract/contract.json"
    if contract.is_file():
        bindings.append(asset(project, ".agentos/contract/contract.json"))
    ledger = meta.get("evidence_ledger")
    if not isinstance(ledger, str):
        raise Blocked("registered evidence_ledger is required")
    return project, meta, bindings


def route(registry_path, project, client, request, inputs, result, risk,
          capability=None, constraints=(), user_root=None, system_root=ROOT):
    data, caps, providers = registry(registry_path)
    if len(constraints) > data["selection"]["max_constraints"] or len(set(constraints)) != len(constraints):
        raise Blocked("too many or duplicate constraint capabilities")
    primary = select(caps, request, capability)
    chosen = [primary] + [select(caps, request, x) for x in constraints]
    if len({x["id"] for x in chosen}) != len(chosen):
        raise Blocked("primary duplicated as constraint")
    project, meta, bindings = project_files(project)
    if set(inputs) != set(primary["inputs"]):
        raise Blocked("missing or unknown input roles; need task/goals/constraints")
    if risk not in RISKS:
        raise Blocked("unknown risk/evidence class")
    if not request.strip():
        raise Blocked("empty request")
    task_inputs = {role: asset(project, value) for role, value in inputs.items()}
    result_path = contained(project, result, must_exist=False)
    forbidden = {Path(x["path"]).resolve() for x in bindings + list(task_inputs.values())}
    ledger_path = contained(project, meta["evidence_ledger"], must_exist=False)
    if result_path in forbidden or result_path == ledger_path:
        raise Blocked("output cannot overwrite authoritative input or ledger")
    provider_bindings, loads = [], []
    for cap in chosen:
        if cap["availability"] == "candidate":
            raise Blocked("candidate capability has no verified deployment: " + cap["id"])
        root, scope = resolve_provider(providers[cap["provider"]], project, client, user_root, system_root)
        for name in ["SKILL.md"] + cap["resources"]:
            binding = asset(root, name)
            if binding not in provider_bindings:
                provider_bindings.append(binding)
                loads.append({"path": binding["path"], "scope": scope, "capability": cap["id"]})
    policy_bindings = [asset(Path(registry_path).parent, Path(registry_path).name)]
    for relative in ["policies/EVIDENCE-POLICY.json", "policies/APPROVAL-POLICY.json", "policies/INTERACTION-POLICY.json"]:
        policy_bindings.append(asset(system_root, relative))
    protocol_paths = {"VERSION", "runtime/BOOT.md", "protocols/SKILL-MATRIX.md",
                      "protocols/TRUTH-AND-EVIDENCE.md", "protocols/QUALITY-GATE.md"}
    if any(cap["id"].startswith("req-") for cap in chosen):
        protocol_paths.add("protocols/UPFRONT-CONFIRMATION.md")
    if any(cap["id"].startswith("ui-") for cap in chosen):
        protocol_paths.add("protocols/DESIGN-CONSISTENCY.md")
    policy_bindings.extend(asset(system_root, name) for name in sorted(protocol_paths))
    return {"schema": "agentos-skill-route-v1", "route_id": uuid.uuid4().hex,
            "generated_at": stamp(), "project_root": str(project), "client": client,
            "request": request, "primary": primary["id"], "constraints": list(constraints),
            "risk": risk, "minimum_level": RISKS[risk], "status": "ready_for_authorized_unit",
            "inputs": task_inputs, "output": str(result_path),
            "source_bindings": bindings + provider_bindings + policy_bindings,
            "load_only": loads, "ledger": str(ledger_path),
            "acceptance": [x for cap in chosen for x in cap["acceptance"]],
            "upstream": primary["upstream"], "failure_modes": primary["failure_modes"],
            "authority": "Selection is not execution permission, specialist certification or delivery evidence."}


def gate(plan, claim_ids, verifier, project=None):
    if plan.get("schema") != "agentos-skill-route-v1" or plan.get("status") != "ready_for_authorized_unit":
        raise Blocked("not a valid ready route")
    if not claim_ids or len(set(claim_ids)) != len(claim_ids):
        raise Blocked("nonempty distinct current claim IDs required")
    root = Path(plan["project_root"]).resolve()
    if project and root != Path(project).resolve():
        raise Blocked("route belongs to another project")
    check_assets(plan["source_bindings"])
    check_assets(list(plan["inputs"].values()))
    if plan["risk"] not in RISKS or plan["minimum_level"] != RISKS[plan["risk"]]:
        raise Blocked("route evidence level mismatch")
    output = Path(plan["output"])
    if not output.is_file() or root not in output.resolve().parents:
        raise Blocked("declared output missing or outside project")
    output_hash = digest(output)
    review_path = contained(root, verifier)
    if review_path.resolve() == output.resolve() or review_path.stat().st_size == 0:
        raise Blocked("verifier must inspect output in a separate nonempty artifact")
    review = read_json(review_path)
    if set(review) != {"route_id", "output_sha256", "reviewer", "producer", "checks", "reviewed_at"}:
        raise Blocked("incomplete verifier record")
    if review["route_id"] != plan["route_id"] or review["output_sha256"] != output_hash:
        raise Blocked("verifier not bound to this result/Unit")
    if not review["reviewer"] or not review["producer"] or review["reviewer"] == review["producer"]:
        raise Blocked("producer self-assertion is not independent review")
    if not isinstance(review["checks"], list) or not review["checks"] or any(
            set(x) != {"criterion", "result", "evidence"} or x["result"] != "pass" or
            not x["criterion"] or not x["evidence"] for x in review["checks"]):
        raise Blocked("verifier checks incomplete or failed")
    if set(x["criterion"] for x in review["checks"]) != set(plan["acceptance"]):
        raise Blocked("verifier does not cover every routed acceptance criterion")
    inspected = []
    for check in review["checks"]:
        reference = contained(root, check["evidence"])
        if reference.stat().st_size == 0:
            raise Blocked("empty verification artifact")
        inspected.append(asset(root, check["evidence"]))
    now = datetime.now(timezone.utc)
    if not time_value(plan["generated_at"]) <= time_value(review["reviewed_at"]) <= now:
        raise Blocked("review must follow the routed task and cannot be future-dated")
    ledger = Path(plan["ledger"])
    latest, initial = {}, set()
    try:
        for line in ledger.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            key = event["claim_id"]
            if event.get("event_type") == "claim_recorded":
                if key in initial:
                    raise Blocked("duplicate initial claim in ledger")
                initial.add(key)
            latest[key] = event
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise Blocked("malformed/missing evidence ledger") from exc
    matched = False
    for key in claim_ids:
        if key not in latest:
            raise Blocked("claim missing: " + key)
        event = latest[key]
        if event.get("status") != "verified" or event.get("event_type") == "claim_invalidated":
            raise Blocked("claim not currently verified: " + key)
        if event.get("source_type") not in {"file", "command", "test", "device", "url"} or not event.get("source") or not event.get("validation_method"):
            raise Blocked("claim lacks verifiable source/method")
        if event.get("data_class") != "real":
            raise Blocked("synthetic/mixed/unknown evidence cannot close this delivery gate")
        level = event.get("evidence_level")
        if level not in {"E1", "E2", "E3", "E4"} or int(level[1]) < int(plan["minimum_level"][1]):
            raise Blocked("insufficient evidence level")
        valid_app = {"static": {"static"}, "software": {"unit", "compile"},
                     "integration": {"integration"}, "physical": {"real_device", "safety"},
                     "production": {"real_device", "user_acceptance"}}[plan["risk"]]
        if event.get("applicability") not in valid_app:
            raise Blocked("evidence applicability mismatch")
        if plan["risk"] in {"physical", "production"} and not event.get("primary_source"):
            if len(claim_ids) < 2 or not event.get("independent"):
                raise Blocked("high-risk gate needs primary source or independent corroboration")
        if event.get("source_type") in {"command", "test", "device", "url"}:
            if not event.get("expires_at") or not event.get("output_complete"):
                raise Blocked("dynamic evidence needs expiry and complete output")
        if event.get("source_type") in {"command", "test"} and event.get("exit_code") != 0:
            raise Blocked("failed command evidence")
        if event.get("expires_at") and time_value(event["expires_at"]) <= now:
            raise Blocked("stale evidence")
        observed = time_value(event.get("observed_at", ""))
        validated = time_value(event.get("validated_at", ""))
        if not time_value(plan["generated_at"]) <= observed <= validated <= now:
            raise Blocked("claim predates route or is future-dated")
        artifact_path = Path(event.get("artifact_path") or "")
        if not artifact_path.is_file() or digest(artifact_path).lower() != str(event.get("sha256", "")).lower():
            raise Blocked("claim artifact missing/modified")
        if artifact_path.resolve() == output.resolve() and event["sha256"].lower() == output_hash:
            matched = True
    if not matched:
        raise Blocked("no claim verifies the declared output")
    return {"schema": "agentos-skill-gate-v1", "generated_at": stamp(),
            "route_id": plan["route_id"], "status": "verified_for_declared_scope",
            "claim_ids": claim_ids, "output": str(output), "sha256": output_hash,
            "verifier": asset(root, verifier), "minimum_level": plan["minimum_level"],
            "verification_artifacts": inspected,
            "boundary": "Local records checked; producer/reviewer identities are caller supplied, not authenticated."}


def feedback(project, source, summary, capability, registry_path):
    _, caps, _ = registry(registry_path)
    if capability not in caps or not summary.strip():
        raise Blocked("known capability and nonempty lesson required")
    project, _, _ = project_files(project)
    evidence = asset(project, source)
    return {"schema": "agentos-skill-lesson-v1", "lesson_id": uuid.uuid4().hex,
            "created_at": stamp(), "capability": capability, "summary": summary,
            "source": evidence, "state": "proposed_for_review",
            "review_due_at": (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat(),
            "effect": "No automatic rule change; owner authorization and actual validation remain required."}


def persist(path, data):
    """Create once; never overwrite a route, report or raw observation."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "catalog", "route", "gate", "feedback"])
    parser.add_argument("--registry", type=Path, default=ROOT / "policies/SKILL-REGISTRY.json")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--client", choices=CLIENTS, default="codex")
    parser.add_argument("--task", default="")
    parser.add_argument("--capability")
    parser.add_argument("--constraint", action="append", default=[])
    parser.add_argument("--input", action="append", default=[], help="role=project-relative-file")
    parser.add_argument("--result", help="declared project-relative output file")
    parser.add_argument("--risk", choices=RISKS, default="software")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--claim", action="append", default=[])
    parser.add_argument("--verifier")
    parser.add_argument("--source")
    parser.add_argument("--summary", default="")
    parser.add_argument("--save", help="create-only project-relative JSON report")
    args = parser.parse_args(argv)
    try:
        data, caps, providers = registry(args.registry)
        if args.command == "validate":
            result = {"status": "valid_structure", "count": len(caps),
                      "domains": sorted({x["domain"] for x in caps.values()}),
                      "registry_sha256": digest(args.registry), "claim": "Structure only; providers are checked when routed."}
        elif args.command == "catalog":
            result = {"capabilities": [{"id": x["id"], "domain": x["domain"],
                       "availability": x["availability"], "provider": x["provider"], "limits": x["limits"]} for x in caps.values()]}
            if args.project:
                project, _, _ = project_files(args.project)
                for item in result["capabilities"]:
                    if item["availability"] == "candidate":
                        item["provider_status"] = "candidate_unavailable"
                        continue
                    try:
                        cap = caps[item["id"]]
                        root, scope = resolve_provider(providers[cap["provider"]], project, args.client)
                        item["resources"] = [asset(root, name) for name in ["SKILL.md"] + cap["resources"]]
                        item["provider_status"] = "available_files_only"
                        item["provider_scope"] = scope
                    except Blocked as exc:
                        item["provider_status"] = "blocked"
                        item["reason"] = str(exc)
        else:
            if not args.project:
                raise Blocked("--project required")
            if args.command == "route":
                inputs = {}
                for value in args.input:
                    role, sep, path = value.partition("=")
                    if not sep or role in inputs:
                        raise Blocked("duplicate/malformed input role")
                    inputs[role] = path
                if not args.result:
                    raise Blocked("--result required")
                result = route(args.registry, args.project, args.client, args.task, inputs,
                               args.result, args.risk, args.capability, args.constraint)
            elif args.command == "gate":
                if not args.plan or not args.verifier:
                    raise Blocked("--plan and --verifier required")
                result = gate(read_json(args.plan), args.claim, args.verifier, args.project)
            else:
                if not args.source:
                    raise Blocked("--source required")
                result = feedback(args.project, args.source, args.summary, args.capability, args.registry)
        if args.save:
            if not args.project:
                raise Blocked("--save requires --project")
            output = contained(args.project, args.save, must_exist=False)
            state = contained(args.project, ".agentos/skill-runs/placeholder", must_exist=False).parent
            if state not in output.parents:
                raise Blocked("reports must stay in .agentos/skill-runs")
            persist(output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (Blocked, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
