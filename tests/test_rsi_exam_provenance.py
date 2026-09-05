"""Fault-injection tests for the RSI-Exam rollout provenance verifier and producer.

Every test copies the committed fixture (a harbor-shaped job directory plus
the task directory it ran against) into a temporary location, injects exactly
one fault, and asserts the specific error code or downgrade. The valid
fixture must pass with complete coverage, and the producer must regenerate
the committed golden capsule byte for byte.
"""

import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STUDY = REPO_ROOT / "profile"
FIXTURE_ROOT = REPO_ROOT / "fixtures/valid"
GATED_ROOT = REPO_ROOT / "fixtures/gated"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFIER = _load("rsi_exam_verifier", STUDY / "verify_capsule.py")
PRODUCER = _load("rsi_exam_producer", STUDY / "build_capsule.py")

METHODS = "artifacts/app/methods"


class FixtureCase(unittest.TestCase):
    """Copy the fixture, mutate one thing, verify."""

    def materialize(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        shutil.copytree(FIXTURE_ROOT, root, dirs_exist_ok=True)
        return root / "job", root / "task"

    @staticmethod
    def load(job):
        return json.loads((job / "capsule.json").read_text(encoding="utf-8"))

    @staticmethod
    def save(job, data):
        (job / "capsule.json").write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def rebind(job, data, capsule_key, relpath):
        """Refresh one bound-file digest after editing the file it names."""
        digest = VERIFIER.file_digest(job / relpath)
        node = data
        *parents, leaf = capsule_key.split(".")
        for key in parents:
            node = node[key]
        node[leaf] = digest

    def verify(self, job, **kwargs):
        return VERIFIER.verify_capsule(job / "capsule.json", **kwargs)


class ValidFixtureTests(FixtureCase):
    def test_valid_fixture_passes_with_complete_coverage(self):
        job, _ = self.materialize()
        result = self.verify(job, require_complete=True)
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["ok"])
        self.assertEqual(result["integrity"], "pass")
        self.assertEqual(result["coverage"], "complete")

    def test_producer_regenerates_the_committed_golden_capsule(self):
        job, task = self.materialize()
        golden = (FIXTURE_ROOT / "job/capsule.json").read_text(encoding="utf-8")
        capsule = PRODUCER.build_capsule(
            job, task, "0.1@bc36dadb405b", "fixture-rollout-001", None, None, [])
        regenerated = json.dumps(capsule, indent=2, sort_keys=True) + "\n"
        self.assertEqual(regenerated, golden)

    def test_tree_digest_implementations_agree(self):
        job, _ = self.materialize()
        target = job / METHODS / "versions/v2"
        self.assertEqual(VERIFIER.tree_digest(target), PRODUCER.tree_digest(target))
        log = job / METHODS / "experiment_log.md"
        self.assertEqual(VERIFIER.file_digest(log), PRODUCER.file_digest(log))

    def test_capsule_unreadable(self):
        job, _ = self.materialize()
        (job / "capsule.json").write_text("not json", encoding="utf-8")
        result = self.verify(job)
        self.assertEqual(result["errors"], ["capsule_unreadable"])

    def test_fixture_validates_against_schema_when_jsonschema_available(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed; structural rules are "
                          "enforced by the verifier itself")
        schema = json.loads((STUDY / "schema.json").read_text(encoding="utf-8"))
        data = json.loads((FIXTURE_ROOT / "job/capsule.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(data)


class StructuralTests(FixtureCase):
    def test_unknown_top_level_key_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["notes"] = "hello"
        self.save(job, data)
        self.assertIn("schema:$.notes:unknown_key", self.verify(job)["errors"])

    def test_unknown_nested_key_carrying_raw_payload_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["hidden_evaluation"]["prompt_text"] = "the full prompt..."
        self.save(job, data)
        self.assertIn("schema:$.hidden_evaluation.prompt_text:unknown_key",
                      self.verify(job)["errors"])

    def test_oversized_string_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["versions"][0]["stage"] = "x" * 3000
        self.save(job, data)
        self.assertIn("schema:$.versions[0].stage:string_too_long",
                      self.verify(job)["errors"])

    def test_status_outside_enum_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["versions"][0]["status"] = "retained-ish"
        self.save(job, data)
        self.assertIn("schema:$.versions[0].status:invalid",
                      self.verify(job)["errors"])

    def test_boolean_budget_hours_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["rollout"]["budget_hours"] = True
        self.save(job, data)
        self.assertIn("schema:$.rollout.budget_hours:invalid",
                      self.verify(job)["errors"])

    def test_string_reward_is_rejected_even_when_file_matches(self):
        job, _ = self.materialize()
        reward_path = job / "verifier/reward.json"
        payload = json.loads(reward_path.read_text(encoding="utf-8"))
        payload["reward"] = "0.41273418"
        reward_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        data = self.load(job)
        data["hidden_evaluation"]["reward"] = "0.41273418"
        self.rebind(job, data, "hidden_evaluation.reward_sha256", "verifier/reward.json")
        self.save(job, data)
        self.assertIn("schema:$.hidden_evaluation.reward:invalid",
                      self.verify(job)["errors"])

    def test_missing_log_reference_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        del data["versions"][0]["log"]
        self.save(job, data)
        self.assertIn("schema:$.versions[0].log:missing",
                      self.verify(job)["errors"])


class SemanticTests(FixtureCase):
    def test_two_submitted_versions_are_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["versions"][0]["status"] = "submitted"
        self.save(job, data)
        self.assertIn("semantic:versions:submitted_count", self.verify(job)["errors"])

    def test_final_bound_to_a_reverted_version_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        reverted = next(v for v in data["versions"] if v["status"] == "reverted")
        data["final_submission"]["version_id"] = reverted["version_id"]
        data["final_submission"]["tree_sha256"] = reverted["artifact"]["tree_sha256"]
        self.save(job, data)
        self.assertIn("semantic:final:submitted_mismatch", self.verify(job)["errors"])

    def test_missing_parent_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["versions"][2]["parent_ids"] = ["v9"]
        self.save(job, data)
        self.assertIn("semantic:version:v3:missing_parent", self.verify(job)["errors"])

    def test_parent_order_violation_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["versions"][0]["parent_ids"] = ["v3"]
        self.save(job, data)
        self.assertIn("semantic:version:v1:parent_order", self.verify(job)["errors"])

    def test_duplicate_ordinal_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["versions"][1]["ordinal"] = data["versions"][0]["ordinal"]
        self.save(job, data)
        self.assertIn("semantic:versions:v2:duplicate_ordinal",
                      self.verify(job)["errors"])

    def test_second_root_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["versions"][2]["parent_ids"] = []
        self.save(job, data)
        self.assertIn("semantic:versions:root_count", self.verify(job)["errors"])

    def test_duplicate_trace_event_across_versions_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["versions"][0]["trace_event_ids"] = ["evt_1"]
        data["versions"][1]["trace_event_ids"] = ["evt_1"]
        self.save(job, data)
        self.assertIn("semantic:versions:v2:duplicate_trace_event",
                      self.verify(job)["errors"])

    def test_snapshot_locator_convention_is_enforced(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["versions"][1]["artifact"]["locator"] = "elsewhere/v2"
        self.save(job, data)
        self.assertIn("semantic:version:v2:locator_convention",
                      self.verify(job)["errors"])


class FileTests(FixtureCase):
    def test_artifact_directory_tamper_is_rejected(self):
        job, _ = self.materialize()
        target = job / METHODS / "versions/v3/policy.py"
        target.write_text(target.read_text(encoding="utf-8") + "\n# tampered\n",
                          encoding="utf-8")
        self.assertIn("file:artifact:v3:digest_mismatch", self.verify(job)["errors"])

    def test_symlink_inside_a_version_directory_is_rejected(self):
        job, _ = self.materialize()
        outside = job.parent / "outside.py"
        outside.write_text("stolen = True\n", encoding="utf-8")
        (job / METHODS / "versions/v2/linked.py").symlink_to(outside)
        self.assertIn("file:artifact:v2:symlink", self.verify(job)["errors"])

    def test_experiment_log_tamper_is_rejected(self):
        job, _ = self.materialize()
        log = job / METHODS / "experiment_log.md"
        log.write_text(log.read_text(encoding="utf-8") + "\n- edited later\n",
                       encoding="utf-8")
        self.assertIn("file:experiment_log:digest_mismatch",
                      self.verify(job)["errors"])

    def test_log_line_not_naming_the_version_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        v3 = next(v for v in data["versions"] if v["version_id"] == "v3")
        v3["log"]["line"] = 3
        self.save(job, data)
        self.assertIn("file:log:v3:line_mismatch", self.verify(job)["errors"])

    def test_log_line_out_of_range_is_rejected(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["versions"][0]["log"]["line"] = 99
        self.save(job, data)
        self.assertIn("file:log:v1:line_out_of_range", self.verify(job)["errors"])

    def test_reward_file_tamper_is_rejected(self):
        job, _ = self.materialize()
        reward_path = job / "verifier/reward.json"
        payload = json.loads(reward_path.read_text(encoding="utf-8"))
        payload["reward"] = 0.99
        reward_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        self.assertIn("file:reward:digest_mismatch", self.verify(job)["errors"])

    def test_reward_mismatch_between_file_and_capsule_is_rejected(self):
        job, _ = self.materialize()
        reward_path = job / "verifier/reward.json"
        payload = json.loads(reward_path.read_text(encoding="utf-8"))
        payload["reward"] = 0.99
        reward_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        data = self.load(job)
        self.rebind(job, data, "hidden_evaluation.reward_sha256", "verifier/reward.json")
        self.save(job, data)
        self.assertIn("file:reward:reward_mismatch", self.verify(job)["errors"])

    def test_reward_error_field_must_match_capsule(self):
        job, _ = self.materialize()
        reward_path = job / "verifier/reward.json"
        payload = json.loads(reward_path.read_text(encoding="utf-8"))
        payload["error"] = "grader failed: boom"
        reward_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        data = self.load(job)
        self.rebind(job, data, "hidden_evaluation.reward_sha256", "verifier/reward.json")
        self.save(job, data)
        self.assertIn("file:reward:error_mismatch", self.verify(job)["errors"])

    def test_trace_export_binding_is_checked(self):
        job, _ = self.materialize()
        export = job / "trace-export.json"
        export.write_text('{"id": "trace_fixture", "events": []}\n', encoding="utf-8")
        data = self.load(job)
        data["source"]["trace_exports"] = [{
            "session_id": "trace_fixture",
            "locator": "trace-export.json",
            "sha256": "0" * 64,
        }]
        self.save(job, data)
        self.assertIn("file:trace_export:0:digest_mismatch",
                      self.verify(job)["errors"])


class CoverageTests(FixtureCase):
    def test_missing_snapshot_directory_fails_integrity_and_downgrades(self):
        job, _ = self.materialize()
        shutil.rmtree(job / METHODS / "versions/v2")
        result = self.verify(job)
        self.assertIn("file:artifact:v2:missing_file", result["errors"])
        self.assertEqual(result["coverage"], "partial")

    def test_unrecorded_snapshot_directory_downgrades_coverage_only(self):
        job, _ = self.materialize()
        extra = job / METHODS / "versions/v4"
        extra.mkdir()
        (extra / "policy.py").write_text("def choose_move(board):\n    return 'UP'\n",
                                         encoding="utf-8")
        result = self.verify(job)
        self.assertEqual(result["integrity"], "pass")
        self.assertEqual(result["coverage"], "partial")
        self.assertTrue(result["ok"])

    def test_require_complete_fails_on_partial_coverage(self):
        job, _ = self.materialize()
        extra = job / METHODS / "versions/v4"
        extra.mkdir()
        (extra / "policy.py").write_text("def choose_move(board):\n    return 'UP'\n",
                                         encoding="utf-8")
        result = self.verify(job, require_complete=True)
        self.assertEqual(result["integrity"], "pass")
        self.assertFalse(result["ok"])

    def test_missing_versions_root_is_unverifiable(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["source"]["versions_root"]["locator"] = "artifacts/app/methods/nowhere"
        self.save(job, data)
        result = self.verify(job)
        self.assertEqual(result["coverage"], "unverifiable")


class ProducerTests(FixtureCase):
    def build(self, job, task, **overrides):
        kwargs = dict(release="0.1@bc36dadb405b", capsule_id="fixture-rollout-001",
                      model=None, harness=None, trace_exports=[])
        kwargs.update(overrides)
        return PRODUCER.build_capsule(job, task, kwargs["release"],
                                      kwargs["capsule_id"], kwargs["model"],
                                      kwargs["harness"], kwargs["trace_exports"])

    def assert_producer_error(self, code, job, task):
        with self.assertRaises(SystemExit) as caught:
            self.build(job, task)
        self.assertEqual(str(caught.exception), f"producer_error: {code}")

    def test_submitted_tree_not_snapshotted_is_an_error(self):
        job, task = self.materialize()
        main = job / METHODS / "main/policy.py"
        main.write_text(main.read_text(encoding="utf-8") + "\n# drifted\n",
                        encoding="utf-8")
        self.assert_producer_error("submitted_not_snapshotted", job, task)

    def test_unclassifiable_log_line_is_an_error(self):
        job, task = self.materialize()
        log = job / METHODS / "experiment_log.md"
        text = log.read_text(encoding="utf-8").replace(
            "exceeded the per-move budget. score: 940. reverted",
            "exceeded the per-move budget. score: 940.")
        log.write_text(text, encoding="utf-8")
        self.assert_producer_error("log_unclassifiable:v2", job, task)

    def test_version_missing_from_log_is_an_error(self):
        job, task = self.materialize()
        log = job / METHODS / "experiment_log.md"
        lines = [line for line in log.read_text(encoding="utf-8").splitlines()
                 if " v2 " not in line and "v2 (" not in line]
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assert_producer_error("log_missing_version:v2", job, task)

    def test_missing_reward_is_an_error(self):
        job, task = self.materialize()
        (job / "verifier/reward.json").unlink()
        self.assert_producer_error("missing_reward", job, task)

    def test_producer_output_verifies_end_to_end(self):
        job, task = self.materialize()
        capsule = self.build(job, task)
        (job / "capsule.json").write_text(
            json.dumps(capsule, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = self.verify(job, require_complete=True)
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["ok"])


class MethodTreeIdentityTests(FixtureCase):
    """Identity is the grader's view of the tree, and indistinguishable snapshots stay a class."""

    def build(self, job, task, **overrides):
        kwargs = dict(release="0.1@bc36dadb405b", capsule_id="fixture-rollout-001",
                      model=None, harness=None, trace_exports=[])
        kwargs.update(overrides)
        return PRODUCER.build_capsule(job, task, kwargs["release"],
                                      kwargs["capsule_id"], kwargs["model"],
                                      kwargs["harness"], kwargs["trace_exports"])

    def assert_producer_error(self, code, job, task):
        with self.assertRaises(SystemExit) as caught:
            self.build(job, task)
        self.assertEqual(str(caught.exception), f"producer_error: {code}")

    def build_and_verify(self, job, task, **kwargs):
        capsule = self.build(job, task)
        (job / "capsule.json").write_text(
            json.dumps(capsule, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return capsule, self.verify(job, **kwargs)

    def alias_v2_to_v3(self, job):
        """Give v2 the method tree v3 and main already share, so two snapshots are the same tree."""
        source = (job / METHODS / "versions/v3/policy.py").read_text(encoding="utf-8")
        (job / METHODS / "versions/v2/policy.py").write_text(source, encoding="utf-8")

    @staticmethod
    def add_cache(target):
        cache = target / "__pycache__"
        cache.mkdir(exist_ok=True)
        (cache / "policy.cpython-312.pyc").write_bytes(b"\x00bytecode")

    def test_the_three_method_tree_implementations_agree(self):
        job, _ = self.materialize()
        gate = _load("rsi_exam_treedigest", REPO_ROOT / "gate/treedigest.py")
        for relative in ("versions/v1", "versions/v2", "versions/v3", "main"):
            target = job / METHODS / relative
            expected = gate.method_tree_sha256(target)
            self.assertEqual(PRODUCER.method_tree_digest(target), expected, relative)
            self.assertEqual(VERIFIER.method_tree_digest(target), expected, relative)

    def test_bytecode_caches_move_the_full_digest_but_not_the_method_digest(self):
        job, _ = self.materialize()
        target = job / METHODS / "versions/v2"
        before_full = PRODUCER.tree_digest(target)
        before_method = PRODUCER.method_tree_digest(target)
        self.add_cache(target)
        self.assertNotEqual(PRODUCER.tree_digest(target), before_full)
        self.assertEqual(PRODUCER.method_tree_digest(target), before_method)
        self.assertEqual(VERIFIER.method_tree_digest(target), before_method)

    def test_an_imported_submission_still_produces_a_record_that_verifies(self):
        """The case the change exists for: importing main/ leaves a cache there and not in the
        snapshot it was copied from, so the two full trees differ and only the method trees match."""
        job, task = self.materialize()
        self.add_cache(job / METHODS / "main")
        capsule, result = self.build_and_verify(job, task, require_complete=True)
        self.assertEqual(capsule["final_submission"]["version_ids"], ["v3"])
        self.assertNotEqual(capsule["final_submission"]["tree_sha256"],
                            capsule["versions"][2]["artifact"]["tree_sha256"])
        self.assertEqual(capsule["final_submission"]["method_tree_sha256"],
                         capsule["versions"][2]["artifact"]["method_tree_sha256"])
        self.assertEqual(result["errors"], [])

    def test_a_note_left_in_a_snapshot_is_recorded_rather_than_fatal(self):
        """A snapshot the grader would refuse is still a fact about the rollout. Only the tree that
        was actually submitted has to be stageable."""
        job, task = self.materialize()
        (job / METHODS / "versions/v1/notes.txt").write_text("scratch", encoding="utf-8")
        capsule, result = self.build_and_verify(job, task, require_complete=True)
        v1 = next(v for v in capsule["versions"] if v["version_id"] == "v1")
        self.assertNotEqual(v1["artifact"]["tree_sha256"], v1["artifact"]["method_tree_sha256"])
        self.assertEqual(result["errors"], [])

    def test_a_non_python_file_in_the_submitted_tree_is_refused(self):
        job, task = self.materialize()
        (job / METHODS / "main/visible_result.json").write_text("{}", encoding="utf-8")
        self.assert_producer_error("non_python_in_submission:visible_result.json", job, task)

    def test_a_submission_with_no_python_is_refused(self):
        job, task = self.materialize()
        (job / METHODS / "main/policy.py").unlink()
        self.assert_producer_error("empty_submission", job, task)

    def test_python_source_under_a_cache_directory_is_refused(self):
        """Bytecode there is ignored, but source there may or may not be staged, and a digest must
        not silently drop a file that might be."""
        job, task = self.materialize()
        cache = job / METHODS / "versions/v2/__pycache__"
        cache.mkdir()
        (cache / "shim.py").write_text("x = 1\n", encoding="utf-8")
        self.assert_producer_error("source_in_cache_dir:v2/__pycache__/shim.py", job, task)

    def test_a_file_that_is_not_a_regular_file_is_refused(self):
        job, task = self.materialize()
        os.mkfifo(job / METHODS / "versions/v2/pipe.py")
        self.assert_producer_error("not_a_regular_file:v2/pipe.py", job, task)

    def test_indistinguishable_snapshots_are_recorded_as_a_class(self):
        job, task = self.materialize()
        self.alias_v2_to_v3(job)
        capsule, result = self.build_and_verify(job, task, require_complete=True)
        final = capsule["final_submission"]
        self.assertEqual(final["version_ids"], ["v2", "v3"])
        self.assertEqual(final["version_id"], "v2")
        submitted = [v["version_id"] for v in capsule["versions"] if v["status"] == "submitted"]
        self.assertEqual(submitted, ["v2"])
        self.assertEqual(result["errors"], [])

    def test_the_verifier_recomputes_the_submitted_tree(self):
        job, _ = self.materialize()
        main = job / METHODS / "main/policy.py"
        main.write_text(main.read_text(encoding="utf-8") + "\n# drifted\n", encoding="utf-8")
        errors = self.verify(job)["errors"]
        self.assertIn("file:final_submission:digest_mismatch", errors)
        self.assertIn("file:final_submission:method_tree_mismatch", errors)

    def test_the_submitted_locator_cannot_point_away_from_main(self):
        """Otherwise the record chooses what the verifier recomputes and main/ is never read."""
        job, _ = self.materialize()
        data = self.load(job)
        data["final_submission"]["locator"] = "artifacts/app/methods/versions/v3"
        self.save(job, data)
        self.assertIn("semantic:final:locator_convention", self.verify(job)["errors"])

    def test_a_class_that_omits_a_member_is_flagged(self):
        job, _ = self.materialize()
        data = self.load(job)
        shared = data["final_submission"]["method_tree_sha256"]
        for version in data["versions"]:
            if version["version_id"] == "v2":
                version["artifact"]["method_tree_sha256"] = shared
        self.save(job, data)
        self.assertIn("semantic:final:class_mismatch", self.verify(job)["errors"])

    def test_a_representative_that_is_not_the_lowest_ordinal_is_flagged(self):
        job, _ = self.materialize()
        data = self.load(job)
        shared = data["final_submission"]["method_tree_sha256"]
        for version in data["versions"]:
            if version["version_id"] == "v2":
                version["artifact"]["method_tree_sha256"] = shared
        data["final_submission"]["version_ids"] = ["v2", "v3"]
        self.save(job, data)
        self.assertIn("semantic:final:not_canonical", self.verify(job)["errors"])

    def test_a_matching_snapshot_left_out_of_the_record_is_flagged(self):
        job, _ = self.materialize()
        extra = job / METHODS / "versions/v9"
        extra.mkdir()
        (extra / "policy.py").write_text(
            (job / METHODS / "main/policy.py").read_text(encoding="utf-8"), encoding="utf-8")
        self.assertIn("identity:unrecorded_match:v9", self.verify(job)["errors"])

    def test_a_tampered_snapshot_is_caught_by_recomputation(self):
        job, _ = self.materialize()
        target = job / METHODS / "versions/v2/policy.py"
        target.write_text("# swapped\n", encoding="utf-8")
        errors = self.verify(job)["errors"]
        self.assertIn("file:artifact:v2:digest_mismatch", errors)
        self.assertIn("file:artifact:v2:method_tree_mismatch", errors)

    def test_a_final_digest_matching_no_snapshot_is_flagged(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["final_submission"]["method_tree_sha256"] = "0" * 64
        self.save(job, data)
        errors = self.verify(job)["errors"]
        self.assertIn("semantic:final:method_tree_mismatch", errors)
        self.assertIn("semantic:final:class_mismatch", errors)
        self.assertIn("file:final_submission:method_tree_mismatch", errors)

    def test_the_verifier_refuses_a_submitted_tree_the_grader_would_reject(self):
        """The producer will not build such a record; the verifier must not accept one either,
        or the rule holds only for records this producer wrote."""
        job, _ = self.materialize()
        (job / METHODS / "main/visible_result.json").write_text("{}", encoding="utf-8")
        self.assertIn("protocol:submission_not_stageable:visible_result.json",
                      self.verify(job)["errors"])

    def test_an_unscannable_snapshot_is_reported_rather_than_skipped(self):
        """Skipping it would let an unreadable directory hide a member of the class."""
        job, _ = self.materialize()
        extra = job / METHODS / "versions/v9"
        extra.mkdir()
        (extra / "policy.py").symlink_to(job / METHODS / "main/policy.py")
        errors = self.verify(job)["errors"]
        self.assertTrue(any(e.startswith("identity:unscannable_snapshot:v9") for e in errors), errors)

    def test_the_submitted_locator_is_derived_for_any_versions_root(self):
        """A record with a flatter layout than the fixture's must still resolve to its own main."""
        for versions_root, expected in (
            ("artifacts/app/methods/versions", "artifacts/app/methods/main"),
            ("artifacts/app/methods/versions/", "artifacts/app/methods/main"),
            ("methods/versions", "methods/main"),
            ("versions", "main"),
        ):
            self.assertEqual(VERIFIER.expected_main_locator(versions_root), expected, versions_root)

    def test_a_record_declaring_other_exclusions_is_flagged(self):
        job, _ = self.materialize()
        data = self.load(job)
        data["source"]["exclusions"] = ["*.pyc"]
        self.save(job, data)
        self.assertIn("semantic:source:exclusions_mismatch", self.verify(job)["errors"])


class DecisionRecordTests(FixtureCase):
    """The record carries the gate's decision log, and the log outranks the experiment-log prose."""

    def materialize_gated(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        shutil.copytree(GATED_ROOT, root, dirs_exist_ok=True)
        return root / "job", root / "task"

    def build(self, job, task):
        return PRODUCER.build_capsule(job, task, "0.1@bc36dadb405b", "fixture-gated-001",
                                      None, None, [])

    def assert_producer_error(self, code, job, task):
        with self.assertRaises(SystemExit) as caught:
            self.build(job, task)
        self.assertEqual(str(caught.exception), f"producer_error: {code}")

    @staticmethod
    def log_path(job):
        return job / METHODS / "decisions.jsonl"

    def rewrite_log(self, job, lines):
        self.log_path(job).write_text(
            "".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")

    def log_lines(self, job):
        return [json.loads(text) for text in
                self.log_path(job).read_text(encoding="utf-8").splitlines()]

    def test_the_gated_fixture_verifies_with_complete_coverage(self):
        job, _ = self.materialize_gated()
        result = self.verify(job, require_complete=True)
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["ok"])
        self.assertEqual(result["coverage"], "complete")

    def test_the_producer_regenerates_the_committed_gated_capsule(self):
        job, task = self.materialize_gated()
        golden = (GATED_ROOT / "job/capsule.json").read_text(encoding="utf-8")
        regenerated = json.dumps(self.build(job, task), indent=2, sort_keys=True) + "\n"
        self.assertEqual(regenerated, golden)

    def test_the_decision_log_decides_the_status_not_the_experiment_log(self):
        """The experiment log calls v3 kept in prose. The record's status comes from the gate's own
        line, and a provisional resolved by a confirmation carries the confirmation's outcome."""
        job, task = self.materialize_gated()
        capsule = self.build(job, task)
        by_id = {v["version_id"]: v for v in capsule["versions"]}
        self.assertEqual(by_id["v2"]["status"], "reverted")
        self.assertEqual([(d["log_line"], d["kind"], d["disposition"])
                          for d in by_id["v3"]["decisions"]],
                         [(2, "screening", "provisional"), (3, "confirmation", "keep")])
        self.assertEqual(by_id["v3"]["decisions"][1]["resolves_log_line"], 2)
        self.assertNotIn("decisions", by_id["v1"])
        self.assertEqual(by_id["v1"]["status"], "kept")

    def test_an_unresolved_provisional_is_a_status(self):
        job, task = self.materialize_gated()
        lines = self.log_lines(job)
        self.rewrite_log(job, lines[:2])                     # drop the confirmation
        (job / METHODS / "main/policy.py").write_text(
            (job / METHODS / "versions/v2/policy.py").read_text(encoding="utf-8"), encoding="utf-8")
        capsule = self.build(job, task)
        by_id = {v["version_id"]: v for v in capsule["versions"]}
        self.assertEqual(by_id["v3"]["status"], "provisional")

    def test_the_measurement_is_hoisted_and_the_log_is_bound(self):
        job, task = self.materialize_gated()
        capsule = self.build(job, task)
        self.assertEqual(capsule["benchmark"]["statistic"], "mean_paired_delta")
        self.assertEqual(capsule["benchmark"]["unit"], "game_score")
        bound = capsule["source"]["decision_log"]
        self.assertEqual(bound["locator"], "artifacts/app/methods/decisions.jsonl")
        self.assertEqual(bound["sha256"], VERIFIER.file_digest(self.log_path(job)))
        for decision in capsule["versions"][1]["decisions"]:
            self.assertNotIn("statistic", decision)
            self.assertNotIn("unit", decision)

    def test_a_rollout_without_a_gate_still_produces_a_record(self):
        job, task = self.materialize_gated()
        self.log_path(job).unlink()
        capsule = self.build(job, task)
        self.assertNotIn("decision_log", capsule["source"])
        self.assertNotIn("statistic", capsule["benchmark"])
        self.assertTrue(all("decisions" not in v for v in capsule["versions"]))

    def test_a_malformed_decision_log_is_refused(self):
        cases = {
            "decision_log_blank_line:2": lambda lines, job: self.log_path(job).write_text(
                json.dumps(lines[0]) + "\n\n" + json.dumps(lines[1]) + "\n", encoding="utf-8"),
            "decision_log_malformed:2": lambda lines, job: self.log_path(job).write_text(
                json.dumps(lines[0]) + "\nnot json\n", encoding="utf-8"),
            "decision_log_foreign_schema:1": lambda lines, job: self.rewrite_log(
                job, [{**lines[0], "schema": "other/v1"}] + lines[1:]),
            "decision_log_line_number:1": lambda lines, job: self.rewrite_log(
                job, [{**lines[0], "line": 7}] + lines[1:]),
            "decision_log_missing_field:1:verdict": lambda lines, job: self.rewrite_log(
                job, [{k: v for k, v in lines[0].items() if k != "verdict"}] + lines[1:]),
            "decision_log_mixed_measurement": lambda lines, job: self.rewrite_log(
                job, [{**lines[0], "unit": "seconds"}] + lines[1:]),
            "decision_log_confirmation_without_provisional:2": lambda lines, job: self.rewrite_log(
                job, [lines[0], {**lines[2], "line": 2}]),
            "decision_log_unknown_version:v9": lambda lines, job: self.rewrite_log(
                job, [{**lines[0], "version_id": "v9"}] + lines[1:]),
        }
        for code, mutate in cases.items():
            with self.subTest(code=code):
                job, task = self.materialize_gated()
                mutate(self.log_lines(job), job)
                self.assert_producer_error(code, job, task)

    def test_a_record_carrying_decisions_must_bind_the_log(self):
        job, _ = self.materialize_gated()
        data = self.load(job)
        del data["source"]["decision_log"]
        self.save(job, data)
        self.assertIn("semantic:source:decision_log_missing", self.verify(job)["errors"])

    def test_a_decision_filed_under_the_wrong_version_is_flagged(self):
        job, _ = self.materialize_gated()
        data = self.load(job)
        version = next(v for v in data["versions"] if v["version_id"] == "v2")
        version["decisions"][0]["version_id"] = "v1"
        self.save(job, data)
        self.assertIn("semantic:decision:version_mismatch:v2:1", self.verify(job)["errors"])

    def test_a_confirmation_resolving_nothing_is_flagged(self):
        job, _ = self.materialize_gated()
        data = self.load(job)
        version = next(v for v in data["versions"] if v["version_id"] == "v3")
        version["decisions"][1]["resolves_log_line"] = 99
        self.save(job, data)
        self.assertIn("semantic:decision:resolves_unknown:v3:3", self.verify(job)["errors"])

    def test_a_kind_that_disagrees_with_replicates_is_flagged(self):
        job, _ = self.materialize_gated()
        data = self.load(job)
        version = next(v for v in data["versions"] if v["version_id"] == "v2")
        version["decisions"][0]["kind"] = "confirmation"
        self.save(job, data)
        errors = self.verify(job)["errors"]
        self.assertIn("semantic:decision:kind_mismatch:v2:1", errors)

    def test_a_status_the_decisions_do_not_imply_is_flagged(self):
        job, _ = self.materialize_gated()
        data = self.load(job)
        version = next(v for v in data["versions"] if v["version_id"] == "v2")
        version["status"] = "kept"
        self.save(job, data)
        self.assertIn("semantic:version:status_not_decided:v2", self.verify(job)["errors"])

    def test_a_projected_decision_must_say_what_the_bound_log_says(self):
        """Binding the log by digest proves the file is unchanged; it proves nothing about whether
        the record's own decisions[] report it faithfully."""
        for field, value in (("verdict", "clears"),
                             ("estimate", -318.0),
                             ("interval", {"lower": 500.0, "upper": 900.0, "level": 0.9}),
                             ("evidence_digests", {"parent": "sha256:" + "9" * 64,
                                                   "candidate": "sha256:" + "8" * 64}),
                             ("disposition", "keep")):
            with self.subTest(field=field):
                job, _ = self.materialize_gated()
                data = self.load(job)
                version = next(v for v in data["versions"] if v["version_id"] == "v2")
                version["decisions"][0][field] = value
                self.save(job, data)
                self.assertIn(f"decision:log_line_mismatch:v2:1:{field}",
                              self.verify(job)["errors"])

    def test_a_log_line_the_record_does_not_carry_is_flagged(self):
        job, _ = self.materialize_gated()
        data = self.load(job)
        version = next(v for v in data["versions"] if v["version_id"] == "v3")
        version["decisions"] = version["decisions"][:1]
        version["status"] = "provisional"
        self.save(job, data)
        self.assertIn("decision:log_line_missing:3", self.verify(job)["errors"])

    def test_a_decision_for_a_line_the_log_does_not_have_is_flagged(self):
        job, _ = self.materialize_gated()
        data = self.load(job)
        source = next(v for v in data["versions"] if v["version_id"] == "v2")["decisions"][0]
        version = next(v for v in data["versions"] if v["version_id"] == "v1")
        version["decisions"] = [dict(source, log_line=9, version_id="v1")]
        version["status"] = "reverted"
        self.save(job, data)
        self.assertIn("decision:log_line_absent:v1:9", self.verify(job)["errors"])

    def rebind_log(self, job, data):
        data["source"]["decision_log"]["sha256"] = VERIFIER.file_digest(self.log_path(job))

    def test_a_bound_log_that_cannot_be_read_is_a_finding_not_a_crash(self):
        job, _ = self.materialize_gated()
        self.log_path(job).write_bytes(b"\xff\n")
        data = self.load(job)
        self.rebind_log(job, data)
        self.save(job, data)
        self.assertIn("file:decision_log:unreadable:UnicodeDecodeError", self.verify(job)["errors"])

    def test_an_empty_bound_log_is_refused_by_the_verifier_too(self):
        """The producer calls an empty log invalid; a verifier that accepted one would disagree
        with the contract the producer enforces."""
        job, _ = self.materialize_gated()
        self.log_path(job).write_text("", encoding="utf-8")
        data = self.load(job)
        for version in data["versions"]:
            version.pop("decisions", None)
        self.rebind_log(job, data)
        self.save(job, data)
        self.assertIn("decision:log_empty", self.verify(job)["errors"])

    def test_a_field_the_log_never_stated_cannot_be_carried_as_null(self):
        job, _ = self.materialize_gated()
        self.rewrite_log(job, [{k: v for k, v in line.items() if k != "profile_sha256"}
                               for line in self.log_lines(job)])
        data = self.load(job)
        self.rebind_log(job, data)
        self.save(job, data)
        self.assertIn("decision:log_line_absent_field:v2:1:profile_sha256",
                      self.verify(job)["errors"])

    def test_a_log_that_renumbers_itself_is_flagged(self):
        job, _ = self.materialize_gated()
        self.rewrite_log(job, [{**line, "line": 9} for line in self.log_lines(job)])
        data = self.load(job)
        self.rebind_log(job, data)
        self.save(job, data)
        self.assertIn("decision:log_line_number:1", self.verify(job)["errors"])

    def test_a_foreign_schema_in_the_bound_log_is_flagged(self):
        job, _ = self.materialize_gated()
        self.rewrite_log(job, [{**line, "schema": "other/v1"} for line in self.log_lines(job)])
        data = self.load(job)
        self.rebind_log(job, data)
        self.save(job, data)
        self.assertIn("decision:log_foreign_schema:1", self.verify(job)["errors"])

    def test_the_hoisted_measurement_is_checked_against_the_log(self):
        """Hoisting statistic and unit to the benchmark block is only safe if the hoist is checked."""
        for field in ("statistic", "unit"):
            with self.subTest(field=field):
                job, _ = self.materialize_gated()
                data = self.load(job)
                data["benchmark"][field] = "something else"
                self.save(job, data)
                self.assertIn(f"decision:log_{field}_mismatch", self.verify(job)["errors"])

    def test_an_unresolved_provisional_cannot_be_the_submission(self):
        job, _ = self.materialize_gated()
        self.rewrite_log(job, self.log_lines(job)[:2])
        data = self.load(job)
        version = next(v for v in data["versions"] if v["version_id"] == "v3")
        version["decisions"] = version["decisions"][:1]
        self.rebind_log(job, data)
        self.save(job, data)
        self.assertIn("protocol:unresolved_provisional_submitted:v3", self.verify(job)["errors"])

    def test_a_measurement_that_is_not_a_string_is_a_finding_not_a_crash(self):
        """statistic and unit are collected into sets to prove the log states one of each; an
        unhashable or missing value must be reported before it reaches that set."""
        for mutation, code in (({"statistic": []}, "decision_log_bad_measurement:1:statistic"),
                               ({"unit": None}, "decision_log_bad_measurement:1:unit")):
            with self.subTest(mutation=mutation):
                job, task = self.materialize_gated()
                self.rewrite_log(job, [{**line, **mutation} for line in self.log_lines(job)])
                self.assert_producer_error(code, job, task)

        job, _ = self.materialize_gated()
        self.rewrite_log(job, [{**line, "statistic": []} for line in self.log_lines(job)])
        data = self.load(job)
        self.rebind_log(job, data)
        self.save(job, data)
        self.assertIn("decision:log_bad_statistic", self.verify(job)["errors"])

    def test_a_non_finite_number_in_the_log_is_refused(self):
        """json.loads accepts Infinity and NaN; the contract requires every number finite."""
        job, task = self.materialize_gated()
        self.log_path(job).write_text(
            '{"schema": "rsi-exam-decision-log/v1", "line": 1, "estimate": Infinity}\n',
            encoding="utf-8")
        self.assert_producer_error("decision_log_malformed:1", job, task)
        data = self.load(job)
        self.rebind_log(job, data)
        self.save(job, data)
        self.assertIn("decision:log_unparsable:1", self.verify(job)["errors"])

    def test_the_standalone_verifier_matches_the_schema_on_decision_shape(self):
        """Where the two disagree the record is only as strict as whichever a reader runs."""
        cases = (
            (lambda d: d["interval"].__setitem__("level", 1), "interval.level"),
            (lambda d: d.__setitem__("evidence_digests", {}), "evidence_digests"),
            (lambda d: d["method"].pop("seed"), "method.seed"),
        )
        for mutate, field in cases:
            with self.subTest(field=field):
                job, _ = self.materialize_gated()
                data = self.load(job)
                mutate(next(v for v in data["versions"]
                            if v["version_id"] == "v2")["decisions"][0])
                self.save(job, data)
                errors = self.verify(job)["errors"]
                self.assertTrue(any(field in error for error in errors), errors)

    def test_a_tampered_decision_log_breaks_its_binding(self):
        job, _ = self.materialize_gated()
        with self.log_path(job).open("a", encoding="utf-8") as stream:
            stream.write("\n")
        self.assertIn("file:decision_log:digest_mismatch", self.verify(job)["errors"])


class RecomputedMeasurementTests(FixtureCase):
    """The verifier redoes each decision's interval from the files the decision rests on."""

    def materialize_gated(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        shutil.copytree(GATED_ROOT, root, dirs_exist_ok=True)
        return root / "job", root / "task"

    @staticmethod
    def decision(data, version_id, index=0):
        return next(v for v in data["versions"]
                    if v["version_id"] == version_id)["decisions"][index]

    def test_the_gate_and_the_verifier_agree_on_the_interval_algorithm(self):
        """Two implementations of rsi-exam-gate/percentile-bootstrap/1 that disagree would make the
        record unverifiable exactly when it mattered."""
        import random as _random
        gate = _load("rsi_exam_decide", REPO_ROOT / "gate/decide.py")
        rng = _random.Random(20260905)
        for _ in range(25):
            deltas = [rng.uniform(-500, 500) for _ in range(rng.randint(2, 12))]
            level = rng.choice([0.8, 0.9, 0.95])
            resamples = rng.choice([50, 500, 2000])
            seed = rng.randint(0, 10 ** 6)
            self.assertEqual(
                VERIFIER.bootstrap_interval(deltas, level=level, resamples=resamples, seed=seed),
                gate.bootstrap_interval(deltas, level=level, resamples=resamples, seed=seed))

    def test_the_percentile_index_is_computed_exactly(self):
        """Through binary floats (1.0 - 0.9) / 2.0 is a shade under 0.05, so the float index at
        5000 resamples is 249 where the contract says 250. On the eight-seed fixtures the two order
        statistics coincide, which is why this needs its own test: on realistic suites they do not,
        and an implementation that indexes in floats reports a different interval every time."""
        import random as _random
        from fractions import Fraction
        self.assertEqual(int(((1.0 - 0.9) / 2.0) * 5000), 249)
        self.assertEqual(int(((Fraction(1) - Fraction("0.9")) / 2) * 5000), 250)

        def float_indexed(deltas, level, resamples, seed):
            rng = _random.Random(seed)
            n = len(deltas)
            means = sorted(sum(rng.choice(deltas) for _ in range(n)) / n for _ in range(resamples))
            alpha = (1.0 - level) / 2.0
            return means[int(alpha * resamples)], means[int((1.0 - alpha) * resamples) - 1]

        rng = _random.Random(1)
        differed = 0
        for _ in range(20):
            deltas = [rng.uniform(-100, 100) for _ in range(rng.randint(20, 40))]
            seed = rng.randint(1, 10 ** 6)
            exact = VERIFIER.bootstrap_interval(deltas, level=0.9, resamples=5000, seed=seed)
            if exact != float_indexed(deltas, 0.9, 5000, seed):
                differed += 1
        self.assertEqual(differed, 20)

    def test_a_declared_holdout_that_cannot_be_recomputed_is_reported(self):
        job, _ = self.materialize_gated()
        data = self.load(job)
        self.decision(data, "v2")["holdout"] = {"estimate": 1.0}
        self.save(job, data)
        self.assertIn("decision:holdout_malformed:v2:1", self.verify(job)["errors"])

    def test_a_repeated_evidence_role_is_refused(self):
        job, _ = self.materialize_gated()
        data = self.load(job)
        decision = self.decision(data, "v2")
        decision["evidence"].append(dict(decision["evidence"][0]))
        self.save(job, data)
        self.assertIn("decision:evidence_duplicate_role:v2:1", self.verify(job)["errors"])

    def test_a_consistently_retold_result_still_fails_to_reproduce(self):
        """The case the check exists for: a score is changed and every digest, the log and the
        record are updated to agree with it. Nothing contradicts anything, and the interval the gate
        recorded no longer follows from the numbers."""
        job, _ = self.materialize_gated()
        result = job / METHODS / "results/v2/visible_result.json"
        payload = json.loads(result.read_text(encoding="utf-8"))
        payload["instances"][0]["score"] += 1000
        result.write_text(json.dumps(payload), encoding="utf-8")
        digest = VERIFIER.file_digest(result)

        log = job / METHODS / "decisions.jsonl"
        lines = [json.loads(text) for text in log.read_text(encoding="utf-8").splitlines()]
        for line in lines:
            for reference in line["evidence"]:
                if reference["locator"] == "results/v2/visible_result.json":
                    reference["sha256"] = digest
                    line["evidence_digests"][reference["role"]] = "sha256:" + digest
        log.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")

        data = self.load(job)
        data["source"]["decision_log"]["sha256"] = VERIFIER.file_digest(log)
        for version in data["versions"]:
            for entry in version.get("decisions", []):
                source = next(l for l in lines if l["line"] == entry["log_line"])
                entry["evidence"] = source["evidence"]
                entry["evidence_digests"] = source["evidence_digests"]
        self.save(job, data)

        errors = self.verify(job)["errors"]
        self.assertIn("decision:interval_not_reproducible:v2:1", errors)
        self.assertIn("decision:estimate_not_reproducible:v2:1", errors)

    def test_an_interval_the_evidence_does_not_give_is_flagged(self):
        job, _ = self.materialize_gated()
        data = self.load(job)
        self.decision(data, "v2")["interval"]["lower"] = -382.0
        self.save(job, data)
        self.assertIn("decision:interval_not_reproducible:v2:1", self.verify(job)["errors"])

    def test_an_algorithm_this_verifier_cannot_redo_is_reported(self):
        """Reporting it beats recording the decision as verified when the interval was never redone."""
        job, _ = self.materialize_gated()
        data = self.load(job)
        self.decision(data, "v2")["method"]["algorithm"] = "someone-elses/bootstrap/2"
        self.save(job, data)
        self.assertIn("decision:interval_algorithm_unsupported:v2:1", self.verify(job)["errors"])

    def test_evidence_that_does_not_match_its_digest_is_flagged(self):
        job, _ = self.materialize_gated()
        result = job / METHODS / "results/v2/visible_result.json"
        result.write_text(result.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        errors = self.verify(job)["errors"]
        self.assertIn("decision:evidence_digest_mismatch:v2:1:candidate", errors)

    def test_a_missing_evidence_file_is_flagged(self):
        job, _ = self.materialize_gated()
        (job / METHODS / "results/v2/visible_result.json").unlink()
        self.assertIn("decision:evidence_missing:v2:1:candidate", self.verify(job)["errors"])

    def test_a_digest_map_that_disagrees_with_the_evidence_list_is_flagged(self):
        job, _ = self.materialize_gated()
        data = self.load(job)
        self.decision(data, "v2")["evidence_digests"]["parent"] = "sha256:" + "0" * 64
        self.save(job, data)
        self.assertIn("decision:evidence_digest_mismatch:v2:1:parent", self.verify(job)["errors"])

    def test_a_logged_score_its_evidence_does_not_support_is_flagged(self):
        job, _ = self.materialize_gated()
        log = job / METHODS / "experiment_log.md"
        log.write_text(log.read_text(encoding="utf-8").replace("score: 3801.25", "score: 940"),
                       encoding="utf-8")
        data = self.load(job)
        self.rebind(job, data, "source.experiment_log.sha256", f"{METHODS}/experiment_log.md")
        self.save(job, data)
        self.assertIn("log:score_mismatch:v2", self.verify(job)["errors"])

    def test_a_rounded_logged_score_is_not_a_contradiction(self):
        """3801.25 printed as 3801 is a rounding, not a different number."""
        job, _ = self.materialize_gated()
        log = job / METHODS / "experiment_log.md"
        log.write_text(log.read_text(encoding="utf-8").replace("score: 3801.25", "score: 3801"),
                       encoding="utf-8")
        data = self.load(job)
        self.rebind(job, data, "source.experiment_log.sha256", f"{METHODS}/experiment_log.md")
        self.save(job, data)
        self.assertNotIn("log:score_mismatch:v2", self.verify(job)["errors"])

    def test_evidence_inside_the_policy_tree_is_refused(self):
        """The grader scores a submission carrying any non-Python file 0.0, so a result file under
        versions/ zeroes the run the moment that snapshot is restored."""
        job, _ = self.materialize_gated()
        data = self.load(job)
        self.decision(data, "v2")["evidence"][1]["locator"] = "versions/v2/visible_result.json"
        self.save(job, data)
        self.assertIn("decision:evidence_in_policy_tree:v2:1:candidate", self.verify(job)["errors"])

    def test_unusable_interval_parameters_give_a_stable_error(self):
        job, _ = self.materialize_gated()
        data = self.load(job)
        self.decision(data, "v2")["method"]["resamples"] = None
        self.save(job, data)
        self.assertIn("decision:interval_not_reproducible:v2:1:parameters",
                      self.verify(job)["errors"])

    def test_a_result_file_the_verifier_cannot_read_is_reported(self):
        for mutation, fragment in (
            ({"instances": []}, "empty"),
            ({"instances": [{"seed": 1, "score": 1}, {"seed": 1, "score": 2}]}, "duplicate_seed"),
            ({"instances": [{"seed": "x", "score": 1}]}, "seed"),
        ):
            with self.subTest(fragment=fragment):
                job, _ = self.materialize_gated()
                result = job / METHODS / "results/v2/visible_result.json"
                result.write_text(json.dumps(mutation), encoding="utf-8")
                data = self.load(job)
                digest = VERIFIER.file_digest(result)
                log = job / METHODS / "decisions.jsonl"
                lines = [json.loads(t) for t in log.read_text(encoding="utf-8").splitlines()]
                for line in lines:
                    for reference in line["evidence"]:
                        if reference["locator"] == "results/v2/visible_result.json":
                            reference["sha256"] = digest
                            line["evidence_digests"][reference["role"]] = "sha256:" + digest
                log.write_text("".join(json.dumps(l) + "\n" for l in lines), encoding="utf-8")
                data["source"]["decision_log"]["sha256"] = VERIFIER.file_digest(log)
                for version in data["versions"]:
                    for entry in version.get("decisions", []):
                        source = next(l for l in lines if l["line"] == entry["log_line"])
                        entry["evidence"] = source["evidence"]
                        entry["evidence_digests"] = source["evidence_digests"]
                self.save(job, data)
                errors = self.verify(job)["errors"]
                self.assertTrue(
                    any(e.startswith("decision:evidence_unparsable:v2:1:candidate") for e in errors),
                    errors)


if __name__ == "__main__":
    unittest.main()
