"""The conformance matrix: one adversarial decision log per vector, and what each implementation
must do with it.

These vectors are the normative examples that hold three repositories together. Nobody copies code
between the gate, TRACE and ProofPress; they agree because they agree about these documents. Each
vector states an expected outcome for five implementations. Two of them live here and run in this
suite; the other three are external and `tests/conformance/README.md` says how to run them.

Every vector is one mutation of `valid_baseline`, which is the gated fixture's own log, so a
difference in outcome is attributable to the mutation and nothing else.
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VECTORS = REPO_ROOT / "tests/conformance/vectors"
IN_REPO = ("gate_loader", "converter", "profile_verifier")
EXTERNAL = ("trace_mcp_validate", "proofpress_adapter")
OUTCOMES = ("accept", "reject", "n/a")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


import sys  # noqa: E402
sys.path.insert(0, str(REPO_ROOT / "gate"))
DECIDE = _load("conformance_decide", REPO_ROOT / "gate/decide.py")
CONVERTER = _load("conformance_converter", REPO_ROOT / "gate/trace_from_decisions.py")


def run_gate_loader(lines):
    """The gate's own reader: does it accept this log as one it could append to?"""
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "decisions.jsonl"
        path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
        try:
            DECIDE.read_log(path)
        except (Exception, SystemExit):   # the producer's error type subclasses SystemExit
            return "reject"
    return "accept"


def run_converter(lines):
    """The decision log to TRACE converter, which re-checks every contract rule on read."""
    try:
        CONVERTER.build_session(lines, project="conformance", rollout_id="conformance",
                                task="game2048_policy_search", harness="test", model="none",
                                decision_log_sha256="0" * 64)
    except (Exception, SystemExit):
        return "reject"
    return "accept"


PRODUCER = _load("conformance_producer", REPO_ROOT / "profile/build_capsule.py")
VERIFIER = _load("conformance_verifier", REPO_ROOT / "profile/verify_capsule.py")
GATED = REPO_ROOT / "fixtures/gated"


def run_profile_verifier(lines):
    """Build a record over the gated fixture with this log in place of its own, then verify it.

    The vectors are mutations of that fixture's log, so the evidence they name is really there and
    the only thing that changed is the document under test.
    """
    import shutil
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        shutil.copytree(GATED, root, dirs_exist_ok=True)
        job, task = root / "job", root / "task"
        log = job / "artifacts/app/methods/decisions.jsonl"
        log.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
        try:
            capsule = PRODUCER.build_capsule(job, task, "0.1@bc36dadb405b", "conformance",
                                             None, None, [])
        except (Exception, SystemExit):
            return "reject"
        (job / "capsule.json").write_text(
            json.dumps(capsule, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return "accept" if VERIFIER.verify_capsule(job / "capsule.json")["ok"] else "reject"


RUNNERS = {"gate_loader": run_gate_loader, "converter": run_converter,
           "profile_verifier": run_profile_verifier}


class ConformanceMatrixTests(unittest.TestCase):
    def vectors(self):
        for path in sorted(VECTORS.glob("*.json")):
            yield path.stem, json.loads(path.read_text(encoding="utf-8"))

    def test_every_vector_is_well_formed(self):
        names = []
        for name, vector in self.vectors():
            names.append(name)
            for key in ("description", "why", "expect", "lines"):
                self.assertIn(key, vector, name)
            self.assertTrue(vector["lines"], name)
            for implementation, outcome in vector["expect"].items():
                self.assertIn(outcome, OUTCOMES, f"{name}:{implementation}")
            for implementation in IN_REPO + EXTERNAL:
                # Every implementation gets an expectation, including the two that run elsewhere:
                # a vector that says nothing about them is not a conformance vector.
                self.assertIn(implementation, vector["expect"], name)
        self.assertIn("valid_baseline", names)
        self.assertGreaterEqual(len(names), 8)

    def test_each_vector_matches_its_stated_outcome(self):
        for name, vector in self.vectors():
            for implementation in IN_REPO:
                expected = vector["expect"][implementation]
                if expected == "n/a":
                    continue
                with self.subTest(vector=name, implementation=implementation):
                    self.assertEqual(RUNNERS[implementation](vector["lines"]), expected,
                                     f"{name}: {vector['why']}")

    def test_the_baseline_is_accepted_by_everything_in_this_repository(self):
        baseline = json.loads((VECTORS / "valid_baseline.json").read_text(encoding="utf-8"))
        for implementation in IN_REPO:
            self.assertEqual(RUNNERS[implementation](baseline["lines"]), "accept", implementation)


if __name__ == "__main__":
    unittest.main()
