"""Executable counterexamples for generalized evidence-quality lessons."""


def read_state(values=None, error=None, inspected=True):
    if not inspected:
        return {"state": "not_inspected", "count": None}
    if error:
        return {"state": "unreadable", "count": None}
    if values is None:
        return {"state": "failed", "count": None}
    return {"state": "observed_nonempty" if values else "observed_empty", "count": len(values)}


def derive_availability(record):
    """Old rows without a new derived field retain their original evidence."""
    if record.get("artifact_exists") is True:
        return "captured"
    if record.get("artifact_exists") is None:
        return "unknown"
    if record.get("write_failed") is True:
        return "write_failed"
    return "not_observed"


def aggregate(rows):
    states = [derive_availability(row) for row in rows]
    return {"total": len(rows), "captured": states.count("captured"), "unknown": states.count("unknown")}
