"""Synthetic counterexamples validate generic rules, not a live incident cause."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("lessons", Path(__file__).resolve().parent.parent / "tools/lesson_checks.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class EvidenceLessonTests(unittest.TestCase):
    def test_access_denied_is_not_empty(self):
        self.assertEqual(m.read_state(error="denied"), {"state": "unreadable", "count": None})
        self.assertEqual(m.read_state([]), {"state": "observed_empty", "count": 0})
        self.assertNotEqual(m.read_state(error="denied"), m.read_state([]))

    def test_uninspected_and_failed_are_not_zero(self):
        self.assertEqual(m.read_state(inspected=False)["state"], "not_inspected")
        self.assertEqual(m.read_state()["count"], None)

    def test_error_signal_does_not_erase_artifact(self):
        self.assertEqual(m.derive_availability({"artifact_exists": True, "write_failed": True}), "captured")
        self.assertEqual(m.derive_availability({"artifact_exists": False, "write_failed": True}), "write_failed")
        self.assertEqual(m.derive_availability({"write_failed": True}), "unknown")

    def test_new_optional_field_does_not_hide_old_records(self):
        old = [{"artifact_exists": True}, {"artifact_exists": True}, {"artifact_exists": False}, {}]
        self.assertEqual(m.aggregate(old), {"total": 4, "captured": 2, "unknown": 1})
        for row in old:
            row["new_derived_field"] = "incorrect-stored-label"
        self.assertEqual(m.aggregate(old), {"total": 4, "captured": 2, "unknown": 1})


if __name__ == "__main__":
    unittest.main()
