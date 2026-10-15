"""Synthetic fixtures test software gates, not physical or user acceptance."""

import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("agentos_skills", ROOT / "bin/agentos_skills.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SkillMatrixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="AgentOS-skill-matrix-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        self.project.mkdir()
        self.user = Path(self.temp.name) / "user"
        self.reg = ROOT / "policies/SKILL-REGISTRY.json"
        self.write("AGENTS.md", "Synthetic test project governance")
        self.write("task.md", "Synthetic task: inspect a registry and reject known bad inputs")
        self.write("goals.md", "Synthetic goal: verify software gate behavior")
        self.write("constraints.md", "No physical actions; synthetic fixture only")
        self.write(".agentos/project.json", {"evidence_ledger": ".agentos/evidence/claims.jsonl"})
        self.inputs = {"task": "task.md", "goals": "goals.md", "constraints": "constraints.md"}

    def write(self, rel, value):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(value, ensure_ascii=False, indent=2) if isinstance(value, (dict, list)) else value
        path.write_text(text, encoding="utf-8")
        return path

    def make_route(self, **changes):
        args = dict(registry_path=self.reg, project=self.project, client="codex",
                    request="inspect registry", inputs=self.inputs, result="result.md", risk="static",
                    capability="meta-skill-registry", user_root=self.user)
        args.update(changes)
        return m.route(**args)

    def fixture(self, risk="static"):
        plan = self.make_route(risk=risk)
        self.write("result.md", "Actual output of a synthetic fixture operation")
        self.write("tests.log", "Synthetic test runner produced a complete success log")
        now = datetime.now(timezone.utc)
        self.event = {"schema": "agentos-evidence-event-v1", "event_type": "claim_recorded",
                      "claim_id": "fixture-claim", "status": "verified", "source_type": "file",
                      "source": "fixture method", "data_class": "real",
                      "validation_method": "Inspect fixture artifact hash (software test only)",
                      "evidence_level": plan["minimum_level"],
                      "applicability": {"static": "static", "software": "unit", "integration": "integration",
                                        "physical": "real_device", "production": "user_acceptance"}[risk],
                      "observed_at": now.isoformat(), "validated_at": now.isoformat(),
                      "artifact_path": str(self.project / "result.md"), "sha256": m.digest(self.project / "result.md"),
                      "expires_at": (now + timedelta(hours=1)).isoformat(), "output_complete": True, "exit_code": 0,
                      "primary_source": True}
        self.review = {"route_id": plan["route_id"], "output_sha256": self.event["sha256"],
                       "producer": "synthetic-producer", "reviewer": "synthetic-distinct-reviewer",
                       "checks": [{"criterion": c, "result": "pass", "evidence": "tests.log"}
                                  for c in set(plan["acceptance"])], "reviewed_at": now.isoformat()}
        self.save_evidence()
        return plan

    def save_evidence(self, events=None):
        events = events or [self.event]
        self.write(".agentos/evidence/claims.jsonl", "\n".join(json.dumps(x) for x in events) + "\n")
        self.write("review.json", self.review)

    def run_gate(self, plan):
        return m.gate(plan, ["fixture-claim"], "review.json", self.project)

    def mutated_registry(self, change):
        data = m.read_json(self.reg)
        change(data)
        return self.write("registry.json", data)

    def test_structure_and_eight_domains(self):
        _, caps, _ = m.registry(self.reg)
        self.assertEqual(len(caps), 63)
        self.assertEqual({x["domain"] for x in caps.values()}, set("ABCDEFGH"))

    def test_registry_negative_contracts(self):
        edits = [lambda d: d["capabilities"][0].pop("inputs"),
                 lambda d: d["capabilities"][0].update(unknown_key="bad"),
                 lambda d: d["capabilities"].append(copy.deepcopy(d["capabilities"][0])),
                 lambda d: d["capabilities"][1]["triggers"].append(d["capabilities"][0]["triggers"][0]),
                 lambda d: d["capabilities"][0]["upstream"].append("not-known"),
                 lambda d: d["capabilities"][0].update(outputs=[]),
                 lambda d: d["capabilities"][0].update(failure_modes=[]),
                 lambda d: d.update(capabilities=[])]
        for edit in edits:
            with self.subTest(edit=edits.index(edit)), self.assertRaises(m.Blocked):
                m.registry(self.mutated_registry(edit))

    def test_duplicate_json_key(self):
        with self.assertRaises(m.Blocked):
            m.read_json(self.write("bad.json", '{"same": 1, "same": 2}'))

    def test_cycle_rejected(self):
        def change(data):
            first, second = data["capabilities"][:2]
            first["upstream"] = first["downstream"] = [second["id"]]
            second["upstream"] = second["downstream"] = [first["id"]]
        with self.assertRaises(m.Blocked):
            m.registry(self.mutated_registry(change))

    def test_ambiguous_unknown_and_candidate(self):
        _, caps, _ = m.registry(self.reg)
        for request in ["notfound-x", "JTBD Kano"]:
            with self.subTest(request=request), self.assertRaises(m.Blocked):
                m.select(caps, request)
        with self.assertRaisesRegex(m.Blocked, "candidate"):
            self.make_route(capability="hw-drc")

    def test_missing_inputs_and_invalid_outputs(self):
        for inputs in [{}, {"task": "task.md", "goals": "absent.md", "constraints": "constraints.md"},
                       {"task": "../escape", "goals": "goals.md", "constraints": "constraints.md"}]:
            with self.subTest(inputs=inputs), self.assertRaises(m.Blocked):
                self.make_route(inputs=inputs)
        for result in ["../outside.md", "task.md", ".agentos/evidence/claims.jsonl"]:
            with self.subTest(result=result), self.assertRaises(m.Blocked):
                self.make_route(result=result)

    def test_small_context_and_constraint_limits(self):
        plan = self.make_route(constraints=["qa-fmea"])
        self.assertEqual(plan["constraints"], ["qa-fmea"])
        self.assertLessEqual(len(plan["load_only"]), 3)
        for constraints in [["meta-router", "qa-fmea", "qa-vmodel"], ["meta-router", "meta-router"], ["meta-skill-registry"]]:
            with self.subTest(constraints=constraints), self.assertRaises(m.Blocked):
                self.make_route(constraints=constraints)

    def test_missing_external_provider_blocks(self):
        with self.assertRaisesRegex(m.Blocked, "provider unavailable"):
            self.make_route(capability="sw-tdd")

    def test_project_provider_precedes_client_and_is_hashed(self):
        rel = "skills/embedded-software-engineering"
        self.write(rel + "/SKILL.md", "---\nname: embedded-software-engineering\ndescription: fixture\n---\n")
        self.write(rel + "/references/debugging.md", "Fixture custom method")
        plan = self.make_route(capability="sw-tdd")
        self.assertTrue(all(x["scope"] == "project" for x in plan["load_only"]))
        self.write(rel + "/SKILL.md", "---\nname: wrong-identity\n---\n")
        with self.assertRaisesRegex(m.Blocked, "identity mismatch"):
            self.make_route(capability="sw-tdd")

    def test_gate_passes_actual_fixture_artifact_inspection(self):
        self.assertEqual(self.run_gate(self.fixture())["status"], "verified_for_declared_scope")

    def test_gate_needs_output_claim_and_review(self):
        plan = self.fixture()
        with self.assertRaises(m.Blocked):
            m.gate(plan, [], "review.json")
        with self.assertRaises(m.Blocked):
            m.gate(plan, ["absent"], "review.json")
        with self.assertRaises(m.Blocked):
            m.gate(plan, ["fixture-claim"], "../review.json")
        (self.project / "result.md").unlink()
        with self.assertRaises(m.Blocked):
            self.run_gate(plan)

    def test_gate_rejects_bad_evidence_states(self):
        plan = self.fixture(risk="software")
        baseline = copy.deepcopy(self.event)
        edits = [{"status": x} for x in ["observed", "conflicted", "stale", "unknown", "synthetic"]]
        edits += [{"data_class": x} for x in ["synthetic", "mixed", "unknown"]]
        edits += [{"source_type": "model"}, {"evidence_level": "E1"}, {"applicability": "simulation"},
                  {"expires_at": "2001-01-01T00:00:00Z"}, {"sha256": "a" * 64},
                  {"source_type": "command", "exit_code": 1},
                  {"source_type": "test", "output_complete": False},
                  {"source_type": "test", "expires_at": None},
                  {"observed_at": "2099-01-01T00:00:00Z"}]
        for edit in edits:
            with self.subTest(edit=edit), self.assertRaises(m.Blocked):
                self.event = {**baseline, **edit}
                self.save_evidence()
                self.run_gate(plan)

    def test_latest_invalidation_dominates(self):
        plan = self.fixture()
        revoked = {**self.event, "event_type": "claim_invalidated", "status": "unknown"}
        self.save_evidence([self.event, revoked])
        with self.assertRaises(m.Blocked):
            self.run_gate(plan)

    def test_stale_ssot_and_other_project_block(self):
        plan = self.fixture()
        with self.assertRaises(m.Blocked):
            m.gate(plan, ["fixture-claim"], "review.json", self.user)
        self.write("constraints.md", "Changed after route")
        with self.assertRaisesRegex(m.Blocked, "source changed"):
            self.run_gate(plan)

    def test_policy_and_input_and_provider_changes_block(self):
        for category in ["policy", "input", "provider"]:
            with self.subTest(category=category):
                plan = self.fixture()
                if category == "input":
                    plan["inputs"]["task"]["sha256"] = "bad"
                else:
                    target = next(x for x in plan["source_bindings"] if
                                  ("POLICY" in x["path"] if category == "policy" else "SKILL.md" in x["path"]))
                    target["sha256"] = "bad"
                with self.assertRaises(m.Blocked):
                    self.run_gate(plan)

    def test_verifier_cannot_self_assert_or_skip_checks(self):
        plan = self.fixture()
        baseline = copy.deepcopy(self.review)
        edits = [{"reviewer": "synthetic-producer"}, {"checks": []},
                 {"checks": baseline["checks"][:1]}, {"route_id": "other-task"},
                 {"output_sha256": "bad"}, {"reviewed_at": "2000-01-01T00:00:00Z"}]
        for edit in edits:
            with self.subTest(edit=edit), self.assertRaises(m.Blocked):
                self.review = {**baseline, **edit}
                self.save_evidence()
                self.run_gate(plan)

    def test_physical_gate_rejects_simulation(self):
        plan = self.fixture(risk="physical")
        self.event.update(data_class="synthetic", applicability="simulation", evidence_level="E3")
        self.save_evidence()
        with self.assertRaises(m.Blocked):
            self.run_gate(plan)

    def test_create_only_and_feedback_not_auto_promoted(self):
        output = self.project / "saved.json"
        m.persist(output, {"fixture": True})
        with self.assertRaises(FileExistsError):
            m.persist(output, {"fixture": False})
        lesson = m.feedback(self.project, "task.md", "Synthetic known counterexample", "meta-qc-gate", self.reg)
        self.assertEqual(lesson["state"], "proposed_for_review")
        self.assertEqual((m.time_value(lesson["review_due_at"]) - m.time_value(lesson["created_at"])).days, 3)

    def test_cli_real_exit_and_no_phantom_execution(self):
        result = subprocess.run([sys.executable, str(ROOT / "bin/agentos_skills.py"), "route",
                                 "--project", str(self.project), "--capability", "hw-drc",
                                 "--task", "DRC", "--result", "result.md"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "blocked")
        self.assertFalse((self.project / "result.md").exists())


if __name__ == "__main__":
    unittest.main()
