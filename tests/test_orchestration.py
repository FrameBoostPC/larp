"""Offline capability registration checks; these never execute external actions."""

from contextlib import redirect_stderr, redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "validate_orchestration", Path(__file__).resolve().parents[1] / "scripts" / "validate_orchestration.py",
)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / validator.REGISTRY_PATH
        self.path.parent.mkdir(parents=True)
        self.add_skill("writing")
        self.registry = {
            "schema_version": "1.0",
            "orchestrator": "hermes",
            "observed_at": "2026-09-16",
            "n8n_instance": "https://automation.example.com",
            "interaction": {
                "primary": ["voice", "text"], "final_transcripts_only": True,
                "shared_state": True, "concise_spoken_results": True,
            },
            "skills": [{"id": "writing", "label": "Writing"}],
            "features": [{
                "id": "content", "label": "Content creation", "skill_id": "writing",
                "workflow_key": None, "tool_roles": ["source retrieval"],
                "intent_examples": ["Turn these notes into an Instagram post."],
                "notes": "Use writing expertise and available connected tools.",
            }],
            "workflows": [{
                "key": "tasks", "id": "workflow123", "name": "Task tools",
                "lifecycle": "published", "exposure": "direct", "actions": ["list_tasks"],
                "trigger": "Agent request", "terminal_nodes": ["Return task result"],
                "production_callable": True,
            }],
        }

    def add_skill(self, name):
        directory = self.root / "skills" / name
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text("Skill fixture; body is not read by this validator.", encoding="utf-8")

    def errors(self):
        self.path.write_text(json.dumps(self.registry), encoding="utf-8")
        return validator.validate_registry(self.root)

    def assert_invalid(self, fragment):
        errors = self.errors()
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_complete_registry_and_standalone_cli_pass(self):
        self.assertEqual(self.errors(), [])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(validator.main([str(self.root)]), 0)

    def test_new_local_skill_requires_registry_entry(self):
        self.add_skill("research")
        self.assert_invalid("'research' is missing from the registry")
        self.registry["skills"].append({"id": "research", "label": "Research"})
        self.assertEqual(self.errors(), [])

    def test_nonexistent_skill_and_missing_skill_directory_are_errors(self):
        self.registry["skills"].append({"id": "missing", "label": "Missing"})
        self.assert_invalid("'missing' has no local SKILL.md")
        (self.root / "skills" / "writing" / "SKILL.md").unlink()
        self.assert_invalid("'writing' has no local SKILL.md")

    def test_dead_skill_and_workflow_feature_references_are_rejected(self):
        feature = self.registry["features"][0]
        feature["skill_id"] = "unregistered"
        feature["workflow_key"] = "missing"
        errors = self.errors()
        self.assertTrue(any(".skill_id" in error for error in errors), errors)
        self.assertTrue(any(".workflow_key" in error for error in errors), errors)

    def test_unpublished_and_internal_workflows_cannot_claim_production_callability(self):
        workflow = self.registry["workflows"][0]
        for lifecycle, exposure in (("draft", "direct"), ("published", "internal"), ("archived", "retired")):
            with self.subTest(lifecycle=lifecycle, exposure=exposure):
                workflow.update(lifecycle=lifecycle, exposure=exposure)
                workflow["trigger"] = "Agent request" if exposure == "direct" else None
                self.assert_invalid("must be true exactly for published direct workflows")

    def test_published_direct_route_must_claim_callability(self):
        self.registry["workflows"][0]["production_callable"] = False
        self.assert_invalid("must be true exactly for published direct workflows")

    def test_draft_feature_is_allowed_with_non_callable_status_and_notes(self):
        self.registry["workflows"][0].update(lifecycle="draft", production_callable=False)
        self.registry["features"][0].update(workflow_key="tasks", notes="Saved draft; unavailable in production.")
        self.assertEqual(self.errors(), [])

    def test_features_cannot_route_to_internal_or_retired_workflows(self):
        self.registry["features"][0]["workflow_key"] = "tasks"
        for lifecycle, exposure in (("published", "internal"), ("archived", "retired")):
            with self.subTest(exposure=exposure):
                self.registry["workflows"][0].update(
                    lifecycle=lifecycle, exposure=exposure, trigger=None, production_callable=False,
                )
                self.assert_invalid("must not directly route to internal or retired")

    def test_direct_routes_require_action_entry_and_terminal_result(self):
        workflow = self.registry["workflows"][0]
        workflow.update(actions=[], trigger="Submit form", terminal_nodes=[])
        errors = self.errors()
        for fragment in (".actions", ".trigger", ".terminal_nodes"):
            self.assertTrue(any(fragment in error for error in errors), errors)

    def test_internal_and_retired_routes_do_not_have_direct_trigger(self):
        self.registry["workflows"][0].update(exposure="internal", production_callable=False)
        self.assert_invalid("must not expose a direct trigger")

    def test_archive_and_retired_exposure_agree(self):
        self.registry["workflows"][0].update(lifecycle="archived", production_callable=False)
        self.assert_invalid("archived workflows must have retired exposure")
        self.registry["workflows"][0].update(lifecycle="draft", exposure="retired", trigger=None)
        self.assert_invalid("retired exposure requires an archived workflow")

    def test_voice_contract_cannot_be_removed_or_disabled(self):
        baseline = copy.deepcopy(self.registry)
        changes = {"primary": ["buttons"], "final_transcripts_only": False, "shared_state": 1, "concise_spoken_results": None}
        for field, value in changes.items():
            with self.subTest(field=field):
                self.registry = copy.deepcopy(baseline)
                self.registry["interaction"][field] = value
                self.assert_invalid(f"interaction.{field}")

    def test_bad_instance_urls_are_rejected(self):
        for url in (
            "http://automation.example.com", "file:///private/config.json", "https://",
            "https://user:secret@automation.example.com", "https://automation.example.com?token=secret",
            "https://automation.example.com#fragment", "https://automation.example.com:99999",
            "https://automation..example.com", "https://automation.example.com\n", [], None,
        ):
            with self.subTest(url=url):
                self.registry["n8n_instance"] = url
                self.assert_invalid("n8n_instance")

    def test_duplicate_identifiers_and_actions_are_rejected(self):
        for field in ("skills", "features", "workflows"):
            with self.subTest(field=field):
                self.registry[field].append(copy.deepcopy(self.registry[field][0]))
                self.assert_invalid("duplicate identifier")
                self.registry[field].pop()
        self.registry["workflows"][0]["actions"].append("list_tasks")
        self.assert_invalid("duplicate value")

    def test_feature_needs_an_execution_path_and_voice_examples(self):
        feature = self.registry["features"][0]
        feature.update(skill_id=None, workflow_key=None, tool_roles=[], intent_examples=[])
        errors = self.errors()
        self.assertTrue(any("must select a skill" in error for error in errors), errors)
        self.assertTrue(any("intent_examples" in error for error in errors), errors)
        feature.update(tool_roles=["image generation"], intent_examples=["Make a profile image for this page."])
        self.assertEqual(self.errors(), [])

    def test_malformed_nested_values_and_missing_fields_return_errors(self):
        baseline = copy.deepcopy(self.registry)
        mutations = [
            {"skills": {}}, {"features": [None]}, {"workflows": ["bad"]}, {"interaction": []},
            {"features": [{}]}, {"workflows": [{}]}, {"skills": [{"id": [], "label": None}]},
            {"features": [{**baseline["features"][0], "skill_id": [], "workflow_key": {}}]},
            {"workflows": [{**baseline["workflows"][0], "lifecycle": [], "exposure": {}, "actions": [False]}]},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.registry = {**baseline, **mutation}
                self.assertTrue(self.errors())
        self.registry = {}
        self.assert_invalid("missing required field")

    def test_invalid_json_and_duplicate_keys_return_errors_and_failure_exit(self):
        for text in ('{"schema_version":"1.0","schema_version":"2.0"}', '{"nested":{"key":1,"key":2}}', '{"x":NaN}', "{"):
            with self.subTest(text=text):
                self.path.write_text(text, encoding="utf-8")
                errors = validator.validate_registry(self.root)
                self.assertTrue(any("cannot read valid JSON" in error for error in errors), errors)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(validator.main([str(self.root)]), 1)

    def test_invalid_root_types_dates_and_missing_registry_return_errors(self):
        for value in ([], None, 42):
            self.registry = value
            self.assert_invalid("must be an object")
        self.path.unlink()
        self.assertTrue(validator.validate_registry(self.root))

    def test_invalid_date_or_orchestrator_does_not_pass(self):
        self.registry.update(observed_at="2026-02-30", orchestrator="n8n", schema_version=1)
        errors = self.errors()
        for fragment in ("observed_at", "orchestrator", "schema_version"):
            self.assertTrue(any(fragment in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
