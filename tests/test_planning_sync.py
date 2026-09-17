"""Behavioural checks for durable planner, task database and calendar sync.

The in-memory providers deliberately model versions, outside edits and uncertain
writes. They do not call live accounts or stand in for live integration testing.
"""

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "components" / "planning-sync"))
from planning_sync import (  # noqa: E402
    AmbiguousWrite, Engine, RemoteConflict, RequestConflict, RevisionConflict,
)


TASK_FIELDS = {
    "title", "status", "project_id", "estimated_minutes", "deliverable",
    "depends_on", "week", "due_date", "schedule",
}


def block(day=16, hour=18):
    return {
        "start": f"2026-09-{day:02d}T{hour:02d}:00:00+10:00",
        "end": f"2026-09-{day:02d}T{hour + 1:02d}:00:00+10:00",
        "timezone": "Australia/Brisbane",
    }


class FakeAdapter:
    """A versioned provider whose state survives an Engine restart."""

    def __init__(self, name, fields):
        self.name = name
        self.fields = set(fields)
        self.records = {}
        self.operations = {}
        self.calls = []
        self.commits = []
        self.fail_read = False
        self.fail_before = False
        self.lose_response = False
        self.ambiguous_before = False
        self.ambiguous_after = False
        self.race_patch = None

    def read(self, task_id, remote_id=None):
        if self.fail_read:
            raise RuntimeError("Provider is unavailable")
        record = self.records.get(task_id)
        if record is not None and remote_id is not None:
            if record["id"] != remote_id:
                raise AssertionError("Engine crossed remote task identities")
        return copy.deepcopy(record)

    def write(self, task_id, remote_id, fields, expected_version, operation_id):
        self.calls.append({
            "task_id": task_id, "remote_id": remote_id,
            "fields": copy.deepcopy(fields), "expected_version": expected_version,
            "operation_id": operation_id,
        })
        if operation_id in self.operations:
            return copy.deepcopy(self.operations[operation_id])
        if self.ambiguous_before:
            self.ambiguous_before = False
            raise AmbiguousWrite("Create outcome cannot be established")
        if self.fail_before:
            self.fail_before = False
            raise RuntimeError("Connection failed before provider accepted write")
        if self.race_patch is not None:
            patch, self.race_patch = self.race_patch, None
            self.external_edit(task_id, patch)
        current = self.records.get(task_id)
        if (current or {}).get("version") != expected_version:
            raise RemoteConflict("Remote version changed")
        if current and remote_id and current["id"] != remote_id:
            raise AssertionError("Write targeted the wrong remote identity")
        record = {
            "id": (current or {}).get("id", f"{self.name}-{task_id}"),
            "version": str(int((current or {}).get("version", "0")) + 1),
            "fields": copy.deepcopy(fields),
            "deleted": self.name == "calendar" and fields.get("schedule") is None,
        }
        self.records[task_id] = record
        self.operations[operation_id] = copy.deepcopy(record)
        self.commits.append(copy.deepcopy(self.calls[-1]))
        if self.ambiguous_after:
            self.ambiguous_after = False
            raise AmbiguousWrite("Provider committed but no reliable receipt arrived")
        if self.lose_response:
            self.lose_response = False
            raise RuntimeError("Provider committed but its response was lost")
        return copy.deepcopy(record)

    def external_edit(self, task_id, patch):
        record = self.records[task_id]
        record["fields"].update(copy.deepcopy(patch))
        record["version"] = str(int(record["version"]) + 1)
        if self.name == "calendar" and "schedule" in patch:
            record["deleted"] = patch["schedule"] is None

    def external_delete(self, task_id):
        record = self.records[task_id]
        record["deleted"] = True
        record["version"] = str(int(record["version"]) + 1)
        if self.name == "calendar":
            record["fields"]["schedule"] = None


class PlanningSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "planning.sqlite3"
        self.notion = FakeAdapter("notion", TASK_FIELDS)
        self.calendar = FakeAdapter("calendar", {"title", "schedule"})
        self.engines = []
        self.addCleanup(self.close_engines)
        self.engine = self.new_engine()

    def close_engines(self):
        for engine in self.engines:
            engine.close()
        self.engines.clear()

    def new_engine(self, **kwargs):
        kwargs.setdefault("clock", lambda: datetime(2026, 9, 15, tzinfo=timezone.utc))
        engine = Engine(self.db_path, adapters=(self.notion, self.calendar), **kwargs)
        self.engines.append(engine)
        return engine

    def restart(self):
        self.close_engines()
        self.engine = self.new_engine()
        return self.engine

    def create(self, task_key="record", **fields):
        values = {
            "title": "Record the demonstration", "status": "planned",
            "estimated_minutes": 60, "deliverable": "A complete walkthrough",
            "depends_on": [], "week": 1, "due_date": None, "schedule": None,
        }
        values.update(fields)
        return self.engine.create_task("demo", task_key, values, f"create-{task_key}")

    def edit(self, task, patch, request_id="edit"):
        return self.engine.edit_task(task["id"], patch, task["revision"], request_id)

    def synced_task(self, **fields):
        task = self.create(schedule=block(), **fields)
        report = self.engine.sync()
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["conflicts"], [])
        return self.engine.get_task(task["id"])

    def assert_surfaces(self, task_id, **fields):
        local = self.engine.get_task(task_id)
        for field, value in fields.items():
            self.assertEqual(local[field], value, f"local {field}")
            for adapter in (self.notion, self.calendar):
                if field in adapter.fields:
                    self.assertEqual(adapter.records[task_id]["fields"][field], value,
                                     f"{adapter.name} {field}")

    def test_request_replay_and_task_identity_survive_restart(self):
        first = self.create()
        self.engine.sync()
        self.restart()
        replay = self.create()
        self.assertEqual(replay["id"], first["id"])
        self.assertEqual(len(self.engine.list_tasks()), 1)
        self.engine.sync()
        self.assertEqual(len(self.notion.commits), 1)

    def test_project_ownership_conflict_can_restore_original_owner_without_moving_task(self):
        task = self.create()
        self.engine.sync()
        self.notion.external_edit(task["id"], {"project_id": "other-project"})
        self.assertIn(task["id"], self.engine.sync()["conflicts"])
        current = self.engine.get_task(task["id"])
        with self.assertRaisesRegex(ValueError, "ownership"):
            self.engine.resolve_conflict(task["id"], {"project_id": "other-project"}, current["revision"], "bad-owner")
        self.engine.resolve_conflict(task["id"], {"project_id": "demo"}, current["revision"], "restore-owner")
        self.assertEqual(self.engine.sync()["errors"], [])
        self.assert_surfaces(task["id"], project_id="demo")

    def test_reopening_completed_past_work_does_not_reuse_old_schedule(self):
        past = {"start": "2026-09-10T18:00:00+10:00", "end": "2026-09-10T19:00:00+10:00", "timezone": "Australia/Brisbane"}
        task = self.create(status="completed", schedule=past)
        task = self.edit(task, {"status": "planned"}, "reopen")
        self.assertIsNone(task["schedule"])
        self.assertTrue(any(past["start"] in item["payload"] for item in self.engine.history(task["id"])))
        self.assertEqual(len(self.calendar.commits), 0)

    def test_reused_request_id_cannot_silently_apply_a_different_change(self):
        task = self.create()
        self.edit(task, {"title": "First edit"}, "same-request")
        with self.assertRaises(RequestConflict):
            self.edit(task, {"title": "Different edit"}, "same-request")
        self.assertEqual(self.engine.get_task(task["id"])["title"], "First edit")

    def test_stale_client_revision_cannot_overwrite_a_newer_edit(self):
        task = self.create()
        current = self.edit(task, {"title": "New title"}, "new-title")
        with self.assertRaises(RevisionConflict):
            self.edit(task, {"title": "Old browser title"}, "stale-edit")
        self.assertEqual(self.engine.get_task(task["id"]), current)

    def test_local_schedule_creates_one_linked_event_and_edits_in_place(self):
        task = self.synced_task()
        event_id = self.calendar.records[task["id"]]["id"]
        task = self.edit(task, {"title": "Record final demo", "schedule": block(17)}, "move")
        self.engine.sync()
        self.assert_surfaces(task["id"], title="Record final demo", schedule=block(17))
        self.assertEqual(self.calendar.records[task["id"]]["id"], event_id)
        self.assertEqual(len(self.calendar.records), 1)

    def test_calendar_drag_updates_task_and_notion(self):
        task = self.synced_task()
        self.calendar.external_edit(task["id"], {"schedule": block(18, 9)})
        self.engine.sync()
        self.assert_surfaces(task["id"], schedule=block(18, 9))

    def test_remote_slot_swap_is_validated_as_one_complete_schedule(self):
        first = self.create("first-slot", title="First task", schedule=block(16, 18))
        second = self.create("second-slot", title="Second task", schedule=block(16, 19))
        self.assertEqual(self.engine.sync()["errors"], [])
        identities = {task["id"]: self.calendar.records[task["id"]]["id"] for task in (first, second)}

        self.calendar.external_edit(first["id"], {"schedule": block(16, 19)})
        self.calendar.external_edit(second["id"], {"schedule": block(16, 18)})
        report = self.engine.sync()

        self.assertEqual(report["errors"], [])
        self.assertEqual(report["conflicts"], [])
        self.assert_surfaces(first["id"], schedule=block(16, 19))
        self.assert_surfaces(second["id"], schedule=block(16, 18))
        self.assertEqual(len(self.calendar.records), 2)
        for task_id, event_id in identities.items():
            self.assertEqual(self.calendar.records[task_id]["id"], event_id)
        commits = (len(self.notion.commits), len(self.calendar.commits))
        self.assertEqual(self.engine.sync()["errors"], [])
        self.assertEqual((len(self.notion.commits), len(self.calendar.commits)), commits)

    def test_notion_rename_updates_task_and_calendar(self):
        task = self.synced_task()
        self.notion.external_edit(task["id"], {"title": "Walk through the working agent"})
        self.engine.sync()
        self.assert_surfaces(task["id"], title="Walk through the working agent")

    def test_echo_poll_does_not_write_or_advance_local_revision(self):
        task = self.synced_task()
        commits = (len(self.notion.commits), len(self.calendar.commits))
        for _ in range(3):
            self.engine.sync()
        self.assertEqual((len(self.notion.commits), len(self.calendar.commits)), commits)
        self.assertEqual(self.engine.get_task(task["id"])["revision"], task["revision"])

    def test_disjoint_changes_merge_before_either_surface_is_written(self):
        task = self.synced_task()
        self.notion.external_edit(task["id"], {"title": "Updated in Notion"})
        self.calendar.external_edit(task["id"], {"schedule": block(19)})
        report = self.engine.sync()
        self.assertEqual(report["conflicts"], [])
        self.assert_surfaces(task["id"], title="Updated in Notion", schedule=block(19))

    def test_notion_edit_merges_with_local_estimate_and_due_date_change(self):
        task = self.synced_task()
        self.edit(task, {"estimated_minutes": 90, "due_date": "2026-09-21"})
        self.notion.external_edit(task["id"], {"title": "Notion's clearer task title"})
        report = self.engine.sync()
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["conflicts"], [])
        self.assert_surfaces(task["id"], title="Notion's clearer task title",
                             estimated_minutes=90, due_date="2026-09-21", schedule=block())

    def test_same_field_conflict_is_durable_and_requires_explicit_resolution(self):
        task = self.synced_task()
        self.notion.external_edit(task["id"], {"title": "Notion choice"})
        self.calendar.external_edit(task["id"], {"title": "Calendar choice"})
        commits = (len(self.notion.commits), len(self.calendar.commits))
        report = self.engine.sync()
        self.assertTrue(report["conflicts"])
        self.assertTrue(self.engine.conflicts(task["id"]))
        self.assertEqual((len(self.notion.commits), len(self.calendar.commits)), commits)
        self.restart()
        self.engine.sync()
        self.assertTrue(self.engine.conflicts(task["id"]))
        current = self.engine.get_task(task["id"])
        self.engine.resolve_conflict(task["id"], {"title": "Chosen title"},
                                     current["revision"], "resolve-title")
        self.engine.sync()
        self.assertEqual(self.engine.conflicts(task["id"]), [])
        self.assert_surfaces(task["id"], title="Chosen title")

    def test_concurrent_local_and_remote_title_edits_do_not_lose_either_choice(self):
        task = self.synced_task()
        self.edit(task, {"title": "Dashboard choice"})
        self.notion.external_edit(task["id"], {"title": "Notion choice"})
        report = self.engine.sync()
        self.assertTrue(report["conflicts"])
        self.assertEqual(self.engine.get_task(task["id"])["title"], "Dashboard choice")
        self.assertEqual(self.notion.records[task["id"]]["fields"]["title"], "Notion choice")

    def test_disjoint_remote_edit_survives_resolution_of_a_different_field(self):
        task = self.synced_task()
        self.edit(task, {"title": "Dashboard choice"})
        self.notion.external_edit(task["id"], {
            "title": "Notion choice", "due_date": "2026-09-23",
        })
        report = self.engine.sync()
        self.assertTrue(report["conflicts"])
        self.restart()
        current = self.engine.get_task(task["id"])
        self.assertEqual(current["due_date"], "2026-09-23")
        self.engine.resolve_conflict(task["id"], {"title": "Dashboard choice"},
                                     current["revision"], "choose-dashboard-title")
        report = self.engine.sync()
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["conflicts"], [])
        self.assert_surfaces(task["id"], title="Dashboard choice", due_date="2026-09-23")

    def test_read_failure_blocks_writes_using_unobserved_remote_state(self):
        task = self.synced_task()
        self.edit(task, {"title": "Dashboard choice"})
        self.notion.external_edit(task["id"], {"title": "Offline Notion choice"})
        self.notion.fail_read = True
        commits = (len(self.notion.commits), len(self.calendar.commits))
        report = self.engine.sync()
        self.assertTrue(report["errors"])
        self.assertEqual((len(self.notion.commits), len(self.calendar.commits)), commits)
        self.notion.fail_read = False
        self.assertTrue(self.engine.sync()["conflicts"])

    def test_failed_write_retries_durably_without_duplicating_a_task(self):
        task = self.create()
        self.notion.fail_before = True
        self.assertTrue(self.engine.sync()["errors"])
        operation_id = self.notion.calls[-1]["operation_id"]
        self.restart()
        self.engine.sync()
        self.assertEqual(len(self.notion.records), 1)
        self.assertEqual(len(self.notion.commits), 1)
        self.assertEqual(self.notion.calls[-1]["operation_id"], operation_id)
        self.assertEqual(self.notion.records[task["id"]]["fields"]["title"], task["title"])

    def test_lost_create_response_is_reconciled_after_restart(self):
        task = self.create()
        self.notion.lose_response = True
        self.assertTrue(self.engine.sync()["errors"])
        self.assertEqual(len(self.notion.commits), 1)
        self.restart()
        report = self.engine.sync()
        self.assertEqual(report["errors"], [])
        self.assertEqual(len(self.notion.commits), 1)
        self.assertEqual(len(self.notion.records), 1)
        self.assertEqual(self.engine.get_task(task["id"])["title"], task["title"])

    def test_unresolved_ambiguous_create_does_not_repeat_creation(self):
        task = self.create()
        self.notion.ambiguous_before = True
        self.assertTrue(self.engine.sync()["errors"])
        calls = len(self.notion.calls)
        self.restart()
        report = self.engine.sync()
        self.assertTrue(report["errors"])
        self.assertEqual(len(self.notion.calls), calls)
        self.assertEqual(len(self.engine.list_tasks()), 1)
        self.assertIsNotNone(self.engine.get_task(task["id"]))

    def test_ambiguous_cancellation_recovers_when_calendar_confirms_deletion(self):
        task = self.synced_task()
        self.edit(task, {"schedule": None}, "unschedule")
        self.calendar.ambiguous_after = True
        self.assertTrue(self.engine.sync()["errors"])
        self.assertTrue(self.calendar.records[task["id"]]["deleted"])
        commits = len(self.calendar.commits)
        self.restart()
        report = self.engine.sync()
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["conflicts"], [])
        self.assertEqual(len(self.calendar.commits), commits)
        self.assert_surfaces(task["id"], schedule=None)

    def test_compare_and_swap_does_not_overwrite_edit_between_read_and_write(self):
        task = self.synced_task()
        self.edit(task, {"title": "Dashboard choice"})
        self.notion.race_patch = {"title": "Just edited remotely"}
        report = self.engine.sync()
        self.assertTrue(report["errors"] or report["conflicts"])
        self.assertEqual(self.notion.records[task["id"]]["fields"]["title"], "Just edited remotely")
        self.assertTrue(self.engine.sync()["conflicts"])

    def test_calendar_deletion_unschedules_without_deleting_or_completing_task(self):
        task = self.synced_task()
        self.calendar.external_delete(task["id"])
        self.engine.sync()
        self.assert_surfaces(task["id"], schedule=None)
        self.assertEqual(self.engine.get_task(task["id"])["status"], "planned")
        self.assertFalse(self.notion.records[task["id"]]["deleted"])
        self.assertEqual(len(self.engine.list_tasks()), 1)

    def test_completion_from_notion_removes_active_event_without_losing_task(self):
        task = self.synced_task()
        self.notion.external_edit(task["id"], {"status": "completed"})
        self.engine.sync()
        self.assertEqual(self.engine.get_task(task["id"])["status"], "completed")
        self.assertTrue(self.calendar.records[task["id"]]["deleted"])
        self.assertFalse(self.notion.records[task["id"]]["deleted"])

    def test_cancelling_locally_cancels_linked_calendar_event(self):
        task = self.synced_task()
        self.edit(task, {"status": "cancelled"})
        self.engine.sync()
        self.assertEqual(self.notion.records[task["id"]]["fields"]["status"], "cancelled")
        self.assertTrue(self.calendar.records[task["id"]]["deleted"])

    def test_elapsed_event_does_not_imply_task_completion(self):
        self.close_engines()
        self.engine = self.new_engine(clock=lambda: datetime(2026, 10, 1, tzinfo=timezone.utc))
        task = self.synced_task()
        self.engine.sync()
        self.assertEqual(self.engine.get_task(task["id"])["status"], "planned")

    def test_due_date_and_relative_week_do_not_create_a_calendar_event(self):
        task = self.create(due_date="2026-09-20", week=2)
        self.engine.sync()
        self.assertIsNone(self.engine.get_task(task["id"])["schedule"])
        self.assertEqual(self.calendar.commits, [])
        self.assertEqual(self.notion.records[task["id"]]["fields"]["due_date"], "2026-09-20")

    def test_schedule_requires_explicit_valid_times_and_timezone(self):
        task = self.create()
        invalid = [
            {"start": "2026-09-16", "end": "2026-09-17", "timezone": "Australia/Brisbane"},
            {"start": "2026-09-16T18:00:00", "end": "2026-09-16T19:00:00", "timezone": "Australia/Brisbane"},
            {**block(), "timezone": "Moon/Tranquillity"},
            {**block(), "end": block()["start"]},
            {**block(), "end": "2026-09-16T17:00:00+10:00"},
        ]
        for index, schedule in enumerate(invalid):
            with self.subTest(schedule=schedule):
                with self.assertRaises(ValueError):
                    self.edit(task, {"schedule": schedule}, f"bad-time-{index}")
        self.assertIsNone(self.engine.get_task(task["id"])["schedule"])

    def test_plan_import_maps_dependencies_and_never_invents_calendar_times(self):
        plan = json.loads((ROOT / "skills/project-planner/examples/example-output.json").read_text(encoding="utf-8"))
        self.engine.import_plan("portfolio", plan, "first-plan")
        tasks = self.engine.list_tasks("portfolio")
        self.assertEqual(len(tasks), 6)
        by_title = {task["title"]: task for task in tasks}
        first = by_title["Define the tutoring offer"]
        second = by_title["Write the page copy"]
        self.assertEqual(second["depends_on"], [first["id"]])
        self.assertTrue(all(task["schedule"] is None for task in tasks))
        self.engine.sync()
        self.assertEqual(len(self.notion.records), 6)
        self.assertEqual(self.calendar.commits, [])

    def test_reimport_preserves_edits_completion_and_tasks_omitted_from_next_week(self):
        plan = json.loads((ROOT / "skills/project-planner/examples/example-output.json").read_text(encoding="utf-8"))
        self.engine.import_plan("portfolio", plan, "initial-plan")
        tasks = self.engine.list_tasks("portfolio")
        first = next(task for task in tasks if task["title"] == "Define the tutoring offer")
        changed = self.edit(first, {"title": "Offer already agreed", "status": "completed"})
        self.engine.import_plan("portfolio", plan, "second-import")
        reduced = copy.deepcopy(plan)
        reduced["data"]["tasks"] = reduced["data"]["tasks"][:1]
        self.engine.import_plan("portfolio", reduced, "next-week")
        self.assertEqual(len(self.engine.list_tasks("portfolio")), 6)
        self.assertEqual(self.engine.get_task(first["id"]), changed)

    def test_weekly_review_with_persisted_task_ids_reuses_existing_tasks(self):
        plan = json.loads((ROOT / "skills/project-planner/examples/example-output.json").read_text(encoding="utf-8"))
        self.engine.import_plan("portfolio", plan, "initial-plan")
        existing = {task["title"]: task for task in self.engine.list_tasks("portfolio")}
        ids = {task["id"]: existing[task["title"]]["id"] for task in plan["data"]["tasks"]}
        for task in plan["data"]["tasks"]:
            task["id"] = ids[task["id"]]
            task["depends_on"] = [ids[key] for key in task["depends_on"]]
        self.restart()
        self.engine.import_plan("portfolio", plan, "weekly-review")
        tasks = self.engine.list_tasks("portfolio")
        self.assertEqual(len(tasks), 6)
        self.assertEqual({task["id"] for task in tasks}, set(ids.values()))

    def test_new_review_task_can_depend_on_an_existing_persistent_task_id(self):
        predecessor = self.create("first", status="completed")
        plan = {"data": {"tasks": [
            {"id": predecessor["id"], "title": predecessor["title"], "depends_on": [],
             "estimated_minutes": 60, "week": 1, "deliverable": "Existing task"},
            {"id": "new-followup", "title": "Review demonstration feedback",
             "depends_on": [predecessor["id"]], "estimated_minutes": 30,
             "week": 2, "deliverable": "Feedback recorded"},
        ]}}
        self.engine.import_plan("demo", plan, "next-week-followup")
        tasks = self.engine.list_tasks("demo")
        self.assertEqual(len(tasks), 2)
        followup = next(task for task in tasks if task["id"] != predecessor["id"])
        self.assertEqual(followup["depends_on"], [predecessor["id"]])
        self.assertEqual(self.engine.get_task(predecessor["id"]), predecessor)

    def test_local_multi_task_move_is_atomic_when_the_second_revision_is_stale(self):
        first = self.create("first", schedule=block(16, 9))
        second = self.create("second", schedule=block(16, 10))
        self.edit(second, {"title": "Newer title"}, "newer-title")
        operations = [
            {"action": "schedule", "task_id": first["id"], "expected_revision": first["revision"],
             "patch": {"schedule": block(17, 9)}},
            {"action": "schedule", "task_id": second["id"], "expected_revision": second["revision"],
             "patch": {"schedule": block(17, 10)}},
        ]
        with self.assertRaises(RevisionConflict):
            self.engine.apply_operations(operations, "move-both")
        self.assertEqual(self.engine.get_task(first["id"]), first)
        self.assertEqual(self.engine.get_task(second["id"])["schedule"], second["schedule"])

    def test_invalid_dependency_drag_blocks_propagation_and_explicit_batch_recovers(self):
        first = self.create("first", schedule=block(16, 9))
        second = self.create("second", schedule=block(16, 10), depends_on=[first["id"]])
        self.engine.sync()
        self.calendar.external_edit(first["id"], {"schedule": block(16, 11)})
        report = self.engine.sync()
        self.assertTrue(report["errors"])
        self.assertEqual(self.engine.get_task(first["id"])["schedule"], block(16, 9))
        self.assertEqual(self.notion.records[first["id"]]["fields"]["schedule"], block(16, 9))
        self.engine.apply_operations([
            {"action": "schedule", "task_id": first["id"], "expected_revision": first["revision"],
             "patch": {"schedule": block(16, 11)}},
            {"action": "schedule", "task_id": second["id"], "expected_revision": second["revision"],
             "patch": {"schedule": block(16, 12)}},
        ], "resolve-dependent-times")
        report = self.engine.sync()
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["conflicts"], [])
        self.assert_surfaces(first["id"], schedule=block(16, 11))
        self.assert_surfaces(second["id"], schedule=block(16, 12))


if __name__ == "__main__":
    unittest.main()
