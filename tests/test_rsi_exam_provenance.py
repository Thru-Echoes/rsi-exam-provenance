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


if __name__ == "__main__":
    unittest.main()
