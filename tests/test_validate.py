"""Regression checks for the validation tool; these do not run agent prompts."""

import copy
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("validate", Path(__file__).resolve().parents[1] / "scripts" / "validate.py")
validate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate)


@unittest.skipIf(validate.yaml is None or validate.Draft202012Validator is None, "Install requirements-dev.txt to run validation tests")
class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / "skills" / "sample-skill"
        (self.skill / "templates").mkdir(parents=True)
        (self.skill / "examples").mkdir()
        self.cases_path = self.root / "test-cases" / "sample-skill" / "cases.json"
        self.cases_path.parent.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text(
            "---\nname: sample-skill\ndescription: Create a sample result.\nmetadata:\n  version: '0.1.0'\n---\n"
            "Use the [schema](templates/output.schema.json) and [example](examples/example-output.json).\n",
            encoding="utf-8",
        )
        self.schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": sorted(validate.ENVELOPE_FIELDS),
            "additionalProperties": False,
            "properties": {
                "schema_version": {"const": "1.0"},
                "skill": {"const": "sample-skill"},
                "status": {"enum": ["ready", "partial", "needs_input"]},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "questions": {"type": "array", "items": {"type": "string"}},
                "limitations": {"type": "array", "items": {"type": "string"}},
                "data": {
                    "type": ["object", "null"],
                    "properties": {"date": {"type": "string", "format": "date"}},
                },
            },
            "allOf": [{
                "if": {"properties": {"status": {"const": "needs_input"}}},
                "then": {"properties": {"data": {"type": "null"}, "questions": {"minItems": 1}}},
                "else": {"properties": {"data": {"type": "object"}}},
            }],
        }
        self.output = {
            "schema_version": "1.0", "skill": "sample-skill", "status": "ready",
            "title": "Sample", "summary": "Example", "assumptions": [],
            "questions": [], "limitations": [], "data": {"date": "2026-09-11"},
        }
        self.write_json(self.skill / "templates" / "output.schema.json", self.schema)
        self.write_json(self.skill / "examples" / "example-output.json", self.output)
        self.write_json(self.cases_path, [{"id": "basic", "prompt": "Create a sample.", "expected_behavior": ["Return a sample."]}])

    def write_json(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_complete_package_passes(self):
        errors, passes = validate.validate_repo(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(len(passes), 1)

    def test_traversal_and_missing_links_fail_but_external_and_code_links_do_not(self):
        with (self.skill / "SKILL.md").open("a", encoding="utf-8") as handle:
            handle.write(
                "\n[escape](../../outside.txt)\n[missing](references/missing.md)\n"
                "[external](https://example.com/unknown)\n"
                "```markdown\n[sample](not-a-real-resource.md)\n```\n"
            )
        errors, _ = validate.validate_repo(self.root)
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(any("escapes skill folder" in error for error in errors))
        self.assertTrue(any("missing linked resource" in error for error in errors))

    def test_external_schema_ref_is_rejected_before_validation(self):
        self.schema["properties"]["data"] = {"$ref": "https://example.com/schema.json"}
        self.write_json(self.skill / "templates" / "output.schema.json", self.schema)
        errors, _ = validate.validate_repo(self.root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("must be internal fragments", errors[0])

    def test_wrong_identity_and_invalid_date_are_rejected(self):
        output = copy.deepcopy(self.output)
        output["skill"] = "another-skill"
        output["data"]["date"] = "2026-02-30"
        errors = []
        validate.check_instance(self.schema, output, Path("response.json"), errors)
        self.assertEqual(len(errors), 2, errors)

    def test_needs_input_requires_questions_and_null_data(self):
        output = copy.deepcopy(self.output)
        output["status"] = "needs_input"
        errors = []
        validate.check_instance(self.schema, output, Path("response.json"), errors)
        self.assertEqual(len(errors), 2, errors)
        output.update(data=None, questions=["Which subject?"])
        errors = []
        validate.check_instance(self.schema, output, Path("response.json"), errors)
        self.assertEqual(errors, [])

    def test_duplicate_case_ids_are_rejected(self):
        case = {"id": "repeated", "prompt": "Create a sample.", "expected_behavior": ["Return a sample."]}
        self.write_json(self.cases_path, [case, case])
        errors, _ = validate.validate_repo(self.root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("repeats id", errors[0])

    def test_invalid_schema_property_reports_error_without_crashing(self):
        self.schema["properties"]["skill"] = True
        self.write_json(self.skill / "templates" / "output.schema.json", self.schema)
        errors, _ = validate.validate_repo(self.root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("properties.skill.const", errors[0])

    def test_nonstandard_json_and_duplicate_keys_are_rejected(self):
        for text in ['{"data": NaN}', '{"data": 1, "data": 2}']:
            with self.subTest(text=text):
                response = self.root / "response.json"
                response.write_text(text, encoding="utf-8")
                errors = []
                self.assertIs(validate.read_json(response, errors), validate.MISSING)
                self.assertEqual(len(errors), 1)


@unittest.skipIf(validate.yaml is None or validate.Draft202012Validator is None, "Install requirements-dev.txt to run validation tests")
class SkillRelationshipTests(unittest.TestCase):
    """Mutate published examples to distinguish relationship checks from schema checks."""

    def fixture(self, skill, example="example-output.json"):
        skill_dir = validate.ROOT / "skills" / skill
        errors = []
        schema = validate.load_schema(skill_dir, errors)
        output = validate.read_json(skill_dir / "examples" / example, errors)
        self.assertEqual(errors, [])
        return schema, output

    def rejected(self, skill, mutate, expected):
        schema, output = self.fixture(skill)
        mutate(output["data"])
        shape_errors = list(validate.Draft202012Validator(schema, format_checker=validate.FormatChecker()).iter_errors(output))
        self.assertEqual(shape_errors, [], "Mutation must pass JSON Schema to exercise semantic validation")
        errors = []
        validate.check_instance(schema, output, Path("response.json"), errors)
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_published_examples_and_needs_input_outputs_pass(self):
        for skill in ("idea-to-content", "project-planner", "calendar-planner"):
            with self.subTest(skill=skill):
                schema, output = self.fixture(skill)
                errors = []
                validate.check_instance(schema, output, Path("response.json"), errors)
                self.assertEqual(errors, [])
                output.update(status="needs_input", data=None, questions=["What is your goal?"])
                errors = []
                validate.check_instance(schema, output, Path("response.json"), errors)
                self.assertEqual(errors, [])

    def test_content_ids_and_hook_references(self):
        for field in ("hooks", "assets"):
            with self.subTest(field=field):
                self.rejected("idea-to-content", lambda data: data[field][1].update(id=data[field][0]["id"]), "duplicate ID")
        self.rejected("idea-to-content", lambda data: data["assets"][0].update(hook_id="missing-hook"), "unknown hook")


    def test_planner_ids_and_references(self):
        for field in ("tasks", "milestones"):
            with self.subTest(field=field):
                self.rejected("project-planner", lambda data: data[field][1].update(id=data[field][0]["id"]), "duplicate ID")
        self.rejected("project-planner", lambda data: data["tasks"][0].update(milestone_id="missing"), "unknown milestone")
        self.rejected("project-planner", lambda data: data["tasks"][0].update(depends_on=["missing"]), "unknown task")




    def test_planner_dependency_self_cycle_and_order(self):
        self.rejected("project-planner", lambda data: data["tasks"][0].update(depends_on=["t1"]), "cannot depend on itself")
        self.rejected("project-planner", lambda data: data["tasks"][0].update(depends_on=["t2"]), "dependency cycle")

        def reorder(data):
            data["tasks"][0], data["tasks"][1] = data["tasks"][1], data["tasks"][0]

        self.rejected("project-planner", reorder, "must appear before")

    def test_planner_predecessor_cannot_be_in_later_week(self):
        self.rejected("project-planner", lambda data: data["tasks"][0].update(week=2), "scheduled in a later week")

    def test_planner_weekly_and_total_budgets(self):
        self.rejected("project-planner", lambda data: data.update(time_budget_hours_per_week=2), "exceeding weekly budget")
        self.rejected("project-planner", lambda data: data.update(time_budget_minutes_total=359), "exceeding total budget")
        schema, output = self.fixture("project-planner")
        output["data"].update(time_budget_hours_per_week=None, time_budget_minutes_total=360)
        errors = []
        validate.check_instance(schema, output, Path("response.json"), errors)
        self.assertEqual(errors, [], "An exact total budget with no weekly limit should pass")

    def check_output(self, schema, output):
        errors = []
        validate.check_instance(schema, output, Path("response.json"), errors)
        return errors

    def test_broad_month_has_unknown_estimates_and_no_capacity_requirement(self):
        schema, output = self.fixture("project-planner", "broad-month-output.json")
        self.assertEqual(output["data"]["horizon_weeks"], 4)
        self.assertTrue(all(task["estimated_minutes"] is None for task in output["data"]["tasks"]))
        self.assertEqual(self.check_output(schema, output), [])
        # An explicit limit can be recorded without inventing estimates to prove fit.
        output["data"]["time_budget_hours_per_week"] = 2
        self.assertEqual(self.check_output(schema, output), [])

    def test_planning_modes_do_not_silently_coerce_effort(self):
        schema, output = self.fixture("project-planner", "broad-month-output.json")
        output["data"]["tasks"][0]["estimated_minutes"] = 60
        self.assertTrue(self.check_output(schema, output), "Broad output must not contain hour estimates")
        output["data"]["planning_mode"] = "detailed"
        self.assertTrue(self.check_output(schema, output), "Detailed effort cannot silently treat the other nulls as zero")
        for task in output["data"]["tasks"]:
            task["estimated_minutes"] = 60
        self.assertEqual(self.check_output(schema, output), [], "Detailed estimates do not require a supplied hours budget")
        output["data"]["time_budget_minutes_total"] = 1
        self.assertTrue(any("exceeding total budget" in error for error in self.check_output(schema, output)))

    def test_legacy_plans_remain_strict_and_new_modes_require_new_version(self):
        schema, output = self.fixture("project-planner")
        self.assertEqual(self.check_output(schema, output), [])
        output["data"]["tasks"][0]["estimated_minutes"] = None
        self.assertTrue(self.check_output(schema, output))
        schema, output = self.fixture("project-planner", "broad-month-output.json")
        output["schema_version"] = "1.0"
        self.assertTrue(self.check_output(schema, output), "New fields cannot masquerade as a legacy plan")
        output["schema_version"] = "1.1"
        del output["data"]["planning_mode"]
        self.assertTrue(self.check_output(schema, output), "New consumers need an explicit mode")

    def test_broad_mode_still_checks_dependencies_horizon_and_zero_capacity(self):
        schema, original = self.fixture("project-planner", "broad-month-output.json")
        mutations = [
            (lambda data: data.update(horizon_weeks=3), "outside the planning horizon"),
            (lambda data: data["tasks"][2].update(week=3), "later than its milestone target"),
            (lambda data: data["tasks"][0].update(depends_on=["t6"]), "dependency cycle"),
            (lambda data: data.update(time_budget_hours_per_week=0), "zero capacity"),
            (lambda data: data.update(start_date="2026-09-01", deadline="2026-09-14"), "starts after the deadline"),
        ]
        for mutate, expected in mutations:
            with self.subTest(expected=expected):
                output = copy.deepcopy(original)
                mutate(output["data"])
                self.assertTrue(any(expected in error for error in self.check_output(schema, output)))

    def test_new_detailed_estimates_can_exceed_capacity_when_shortage_is_partial(self):
        schema, original = self.fixture("project-planner", "broad-month-output.json")
        original["data"]["planning_mode"] = "detailed"
        for task in original["data"]["tasks"]:
            task["estimated_minutes"] = 60
        for capacity in (
            {"time_budget_hours_per_week": 1},
            {"time_budget_minutes_total": 60},
            {"time_budget_hours_per_week": 0},
            {"time_budget_minutes_total": 0},
        ):
            with self.subTest(capacity=capacity):
                output = copy.deepcopy(original)
                output["data"].update(capacity)
                self.assertTrue(self.check_output(schema, output), "Ready cannot imply required work fits a known shortage")
                output.update(status="partial", limitations=["Required work is six hours; the supplied allowance is insufficient. Choose more time or smaller scope."])
                output["data"]["first_action"] = "Choose more time or a smaller goal before allocating work."
                self.assertEqual(self.check_output(schema, output), [], "Required-work estimates stay intact even at zero capacity")
                self.assertEqual(sum(task["estimated_minutes"] for task in output["data"]["tasks"]), 360)
                output["limitations"] = []
                self.assertTrue(self.check_output(schema, output), "The partial result must disclose its limitation")

    def test_new_broad_zero_capacity_can_preserve_unallocated_tasks_as_partial(self):
        schema, output = self.fixture("project-planner", "broad-month-output.json")
        output["data"]["time_budget_hours_per_week"] = 0
        self.assertTrue(any("zero capacity" in error for error in self.check_output(schema, output)))
        output.update(status="partial", limitations=["The required tasks remain as targets, but zero available time prevents any allocation."])
        output["data"]["first_action"] = "Choose some available time or defer the project."
        self.assertEqual(self.check_output(schema, output), [])
        self.assertTrue(output["data"]["tasks"])
        self.assertTrue(all(task["estimated_minutes"] is None for task in output["data"]["tasks"]))

    def test_legacy_overcapacity_is_rejected_even_for_partial_output(self):
        schema, output = self.fixture("project-planner")
        output.update(status="partial", limitations=["The available time is insufficient."])
        for capacity in (
            {"time_budget_hours_per_week": 1, "time_budget_minutes_total": None},
            {"time_budget_hours_per_week": None, "time_budget_minutes_total": 1},
            {"time_budget_hours_per_week": 0, "time_budget_minutes_total": None},
        ):
            with self.subTest(capacity=capacity):
                output["data"].update(capacity)
                self.assertTrue(self.check_output(schema, output), "Legacy 1.0 still describes only capped work")

    def test_calendar_review_can_precede_task_persistence_without_mutations(self):
        schema, output = self.fixture("calendar-planner", "capacity-review-output.json")
        self.assertIsNone(output["data"]["project_id"])
        self.assertEqual(self.check_output(schema, output), [])
        _, legacy = self.fixture("calendar-planner")
        output["data"]["operations"] = legacy["data"]["operations"]
        self.assertTrue(self.check_output(schema, output), "A review-only result must not emit task writes")
        output["data"]["intent"] = "changes"
        self.assertTrue(self.check_output(schema, output), "Changes still need a real persisted project identity")
        output["data"]["project_id"] = "agent-demo"
        self.assertEqual(self.check_output(schema, output), [])

    def test_calendar_review_shortage_and_claimed_ready_must_agree(self):
        schema, output = self.fixture("calendar-planner", "capacity-review-output.json")
        output["data"]["calendar_review"]["shortfall_minutes"] = 0
        self.assertTrue(any("must equal" in error for error in self.check_output(schema, output)))
        output["data"]["calendar_review"]["shortfall_minutes"] = 120
        output.update(status="ready", questions=[])
        self.assertTrue(any("shortage requires a partial" in error for error in self.check_output(schema, output)))

    def test_calendar_review_does_not_turn_unknown_capacity_into_zero(self):
        schema, output = self.fixture("calendar-planner", "capacity-review-output.json")
        review = output["data"]["calendar_review"]
        review.update(status="unavailable", checked_at=None, available_minutes=None, shortfall_minutes=None,
                      working_windows=[], sources=[], limitations=["The calendar connection is unavailable."])
        self.assertEqual(self.check_output(schema, output), [])
        review["shortfall_minutes"] = 0
        self.assertTrue(self.check_output(schema, output))
        review.update(shortfall_minutes=None, status="checked")
        self.assertTrue(self.check_output(schema, output), "Checked availability needs actual coverage and working windows")

    def test_calendar_review_cannot_exceed_allowed_windows_or_double_count_allocation(self):
        schema, original = self.fixture("calendar-planner", "capacity-review-output.json")
        for available, allocated in [(600, 0), (400, 200)]:
            with self.subTest(available=available, allocated=allocated):
                output = copy.deepcopy(original)
                review = output["data"]["calendar_review"]
                review.update(available_minutes=available, already_allocated_minutes=allocated,
                              unscheduled_effort_minutes=600, shortfall_minutes=600 - available)
                self.assertTrue(any("exceeds working windows" in error for error in self.check_output(schema, output)))

    def test_calendar_review_rejects_overlapping_windows_and_unknown_timezone(self):
        schema, output = self.fixture("calendar-planner", "capacity-review-output.json")
        review = output["data"]["calendar_review"]
        review["working_windows"].append(copy.deepcopy(review["working_windows"][0]))
        self.assertTrue(any("overlapping windows" in error for error in self.check_output(schema, output)))
        review["working_windows"].pop()
        review["timezone"] = "No/Such_Zone"
        self.assertTrue(any("unknown IANA timezone" in error for error in self.check_output(schema, output)))

    def test_calendar_review_window_capacity_respects_dst_and_midnight_boundary(self):
        schema, output = self.fixture("calendar-planner", "capacity-review-output.json")
        output.update(status="ready", limitations=[])
        review = output["data"]["calendar_review"]
        review.update(timezone="America/New_York", window_start="2026-11-01", window_end="2026-11-01",
                      working_windows=[{"weekday": 7, "start": "00:00", "end": "03:00"}],
                      buffer_minutes=0, available_minutes=240, unscheduled_effort_minutes=240, shortfall_minutes=0)
        self.assertEqual(self.check_output(schema, output), [], "The fall-back window contains four real hours")
        review.update(window_start="2026-03-08", window_end="2026-03-08", available_minutes=180,
                      unscheduled_effort_minutes=180)
        self.assertTrue(any("exceeds working windows" in error for error in self.check_output(schema, output)))
        review.update(window_start="2026-09-20", window_end="2026-09-20",
                      working_windows=[{"weekday": 7, "start": "23:00", "end": "24:00"}],
                      available_minutes=60, unscheduled_effort_minutes=60)
        self.assertEqual(self.check_output(schema, output), [], "A window may end exactly at midnight")

    def test_broad_plan_cannot_smuggle_in_an_hourly_calendar_review(self):
        schema, output = self.fixture("project-planner", "broad-month-output.json")
        _, review_output = self.fixture("calendar-planner", "capacity-review-output.json")
        output["data"]["calendar_review"] = review_output["data"]["calendar_review"]
        self.assertTrue(self.check_output(schema, output))

    def test_planner_supplied_date_bounds(self):
        self.rejected("project-planner", lambda data: data.update(start_date="2026-09-12", deadline="2026-09-11"), "deadline is before")

        def before_start(data):
            data.update(start_date="2026-09-12")
            data["milestones"][0]["target_date"] = "2026-09-11"

        def after_deadline(data):
            data.update(deadline="2026-09-12")
            data["milestones"][0]["target_date"] = "2026-09-13"

        self.rejected("project-planner", before_start, "target date is before")
        self.rejected("project-planner", after_deadline, "target date is after")

    def test_calendar_action_patch_boundaries(self):
        schema, output = self.fixture("calendar-planner")
        operation = output["data"]["operations"][0]
        for action, patch in (
            ("schedule", {"schedule": None}),
            ("unschedule", {"schedule": operation["patch"]["schedule"]}),
            ("update_task", {"project_id": "another-project"}),
            ("update_task", {}),
            ("update_task", {"status": "finished"}),
        ):
            with self.subTest(action=action, patch=patch):
                broken = copy.deepcopy(output)
                broken["data"]["operations"][0].update(action=action, patch=patch)
                errors = []
                validate.check_instance(schema, broken, Path("response.json"), errors)
                self.assertTrue(errors)

    def test_calendar_duplicate_task_operations_and_self_dependency(self):
        self.rejected("calendar-planner", lambda data: data["operations"].append(copy.deepcopy(data["operations"][0])), "duplicate task operation")

        def self_dependency(data):
            operation = data["operations"][0]
            operation.update(action="update_task", patch={"depends_on": [operation["task_id"]]})

        self.rejected("calendar-planner", self_dependency, "cannot depend on itself")

    def test_calendar_timestamp_order_timezone_and_nonexistent_dst_time(self):
        def change_schedule(**values):
            return lambda data: data["operations"][0]["patch"]["schedule"].update(values)

        self.rejected("calendar-planner", change_schedule(end="2026-09-15T18:00:00+10:00"), "end must be after")
        self.rejected("calendar-planner", change_schedule(timezone="No/Such_Zone"), "unknown IANA timezone")
        self.rejected("calendar-planner", change_schedule(start="2026-09-15T18:00:00+09:00"), "does not match timezone")
        self.rejected("calendar-planner", change_schedule(
            start="2026-03-08T02:30:00-05:00", end="2026-03-08T03:30:00-04:00", timezone="America/New_York",
        ), "does not match timezone")

    def test_calendar_fall_back_offsets_define_real_instants(self):
        schema, output = self.fixture("calendar-planner")
        output["data"]["operations"][0]["patch"]["schedule"].update(
            start="2026-11-01T01:30:00-04:00", end="2026-11-01T01:30:00-05:00", timezone="America/New_York",
        )
        errors = []
        validate.check_instance(schema, output, Path("response.json"), errors)
        self.assertEqual(errors, [], "Repeated local clock readings can be one real hour apart")

    def test_calendar_overlapping_and_adjacent_slots(self):
        schema, output = self.fixture("calendar-planner")
        second = copy.deepcopy(output["data"]["operations"][0])
        second["task_id"] = "fa05c1dc-7190-4dba-ae79-39269d7a02ae"
        second["patch"]["schedule"].update(start="2026-09-15T18:30:00+10:00", end="2026-09-15T19:30:00+10:00")
        output["data"]["operations"].append(second)
        errors = []
        validate.check_instance(schema, output, Path("response.json"), errors)
        self.assertTrue(any("overlaps operation" in error for error in errors), errors)
        second["patch"]["schedule"].update(start="2026-09-15T19:00:00+10:00", end="2026-09-15T20:00:00+10:00")
        errors = []
        validate.check_instance(schema, output, Path("response.json"), errors)
        self.assertEqual(errors, [])

    def test_calendar_completion_and_unscheduling_are_distinct_operations(self):
        schema, output = self.fixture("calendar-planner")
        for action, patch in (("update_task", {"status": "completed"}), ("unschedule", {"schedule": None})):
            with self.subTest(action=action):
                output["data"]["operations"][0].update(action=action, patch=patch)
                errors = []
                validate.check_instance(schema, output, Path("response.json"), errors)
                self.assertEqual(errors, [])

    def test_calendar_atomic_rename_and_move(self):
        schema, output = self.fixture("calendar-planner")
        operation = output["data"]["operations"][0]
        operation["action"] = "update_task"
        operation["patch"]["title"] = "Record the final walkthrough"
        errors = []
        validate.check_instance(schema, output, Path("response.json"), errors)
        self.assertEqual(errors, [])
        operation["patch"]["status"] = "completed"
        errors = []
        validate.check_instance(schema, output, Path("response.json"), errors)
        self.assertTrue(any("cannot have an active schedule" in error for error in errors), errors)

    def test_shape_failure_skips_semantic_checks(self):
        schema, output = self.fixture("project-planner")
        output["data"]["tasks"] = None
        errors = []
        validate.check_instance(schema, output, Path("response.json"), errors)
        self.assertTrue(errors)

    def test_output_cli_rejects_semantically_invalid_response(self):
        _, output = self.fixture("idea-to-content")
        output["data"]["assets"][0]["hook_id"] = "missing-hook"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "response.json"
            path.write_text(json.dumps(output), encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = validate.main(["--output", "idea-to-content", str(path)])
            self.assertEqual(result, 1)
            self.assertIn("unknown hook", stderr.getvalue())
            self.assertNotIn("PASS", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
