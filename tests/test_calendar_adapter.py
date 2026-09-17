"""Calendar bridge contract tests; no provider, credentials or network are used."""

import copy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "components" / "planning-sync"))
from calendar_adapter import CalendarAdapter
from planning_sync import AmbiguousWrite, Engine, RemoteConflict
from notion_adapter import NotionAdapter
from test_notion_adapter import FakeNotion, PROPERTIES, SOURCE_ID


SCHEDULE = {"start": "2026-09-16T18:00:00+10:00", "end": "2026-09-16T19:00:00+10:00",
            "timezone": "Australia/Brisbane"}
FIELDS = {"title": "Record demonstration", "schedule": SCHEDULE}


class FakeCalendarClient:
    calendar_id = "selected-calendar"
    supports_atomic_updates = True
    supports_idempotent_create = True

    def __init__(self):
        self.events = {}
        self.receipts = {}
        self.busy_entries = []
        self.calls = []
        self.failure = None
        self.race = False

    def get_event(self, event_id):
        return copy.deepcopy(self.events.get(event_id))

    def find_task_events(self, task_id):
        return [copy.deepcopy(event) for event in self.events.values() if event["task_id"] == task_id]

    def busy(self, start, end):
        if self.race:
            for event in self.events.values():
                event["version"] += 1
        return copy.deepcopy(self.busy_entries)

    def create_event(self, event, idempotency_key):
        self.calls.append(("create", copy.deepcopy(event), idempotency_key))
        if idempotency_key in self.receipts:
            return copy.deepcopy(self.receipts[idempotency_key])
        created = {"id": "event-" + str(len(self.events) + 1), "version": 1, **copy.deepcopy(event),
                   "deleted": False, "recurring": False, "has_attendees": False, "calendar_id": self.calendar_id,
                   "colour": "blue"}
        self.events[created["id"]] = created
        self.receipts[idempotency_key] = created
        if self.failure:
            raise self.failure
        return copy.deepcopy(created)

    def update_event(self, event_id, event, expected_version, idempotency_key):
        self.calls.append(("update", copy.deepcopy(event), idempotency_key))
        if self.events[event_id]["version"] != expected_version:
            raise RemoteConflict("Provider ETag mismatch")
        self.events[event_id].update(copy.deepcopy(event))
        self.events[event_id]["version"] += 1
        if self.failure:
            raise self.failure
        return copy.deepcopy(self.events[event_id])

    def delete_event(self, event_id, expected_version, idempotency_key):
        self.calls.append(("delete", event_id, idempotency_key))
        if self.events[event_id]["version"] != expected_version:
            raise RemoteConflict("Provider ETag mismatch")
        self.events[event_id].update(deleted=True, schedule=None)
        self.events[event_id]["version"] += 1
        if self.failure:
            raise self.failure
        return copy.deepcopy(self.events[event_id])


class CalendarAdapterTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeCalendarClient()
        self.adapter = CalendarAdapter(self.client)

    def create(self):
        return self.adapter.write("task-1", None, FIELDS, None, "operation-1")

    def test_create_writes_only_managed_fields_and_repeated_request_deduplicates(self):
        first = self.create()
        again = self.create()
        self.assertEqual(first, again)
        self.assertEqual(len(self.client.calls), 1)
        self.assertEqual(self.client.calls[0][1], {"task_id": "task-1", **FIELDS})
        self.assertEqual(first["fields"], FIELDS)

    def test_edit_preserves_id_and_unrelated_provider_fields(self):
        before = self.create()
        changed = {**FIELDS, "title": "Updated demonstration"}
        result = self.adapter.write("task-1", before["id"], changed, before["version"], "operation-2")
        self.assertEqual(result["id"], before["id"])
        self.assertEqual(result["fields"], changed)
        self.assertEqual(self.client.events[before["id"]]["colour"], "blue")

    def test_delete_returns_confirmed_tombstone_and_repeat_is_noop(self):
        before = self.create()
        deleted = self.adapter.write("task-1", before["id"], {"title": FIELDS["title"], "schedule": None},
                                     before["version"], "operation-2")
        self.assertTrue(deleted["deleted"])
        again = self.adapter.write("task-1", before["id"], {"title": FIELDS["title"], "schedule": None},
                                   before["version"], "operation-2")
        self.assertTrue(again["deleted"])
        self.assertEqual([call[0] for call in self.client.calls], ["create", "delete"])

    def test_reschedule_after_deleted_block_creates_new_managed_event(self):
        before = self.create()
        self.client.events[before["id"]].update(deleted=True, schedule=None)
        result = self.adapter.write("task-1", None, FIELDS, None, "operation-2")
        self.assertNotEqual(result["id"], before["id"])
        self.assertEqual(self.adapter.read("task-1")["id"], result["id"])

    def test_manual_calendar_move_is_read_back(self):
        before = self.create()
        moved = {**SCHEDULE, "start": "2026-09-17T18:00:00+10:00", "end": "2026-09-17T19:00:00+10:00"}
        self.client.events[before["id"]].update(schedule=moved, version=2)
        self.assertEqual(self.adapter.read("task-1", before["id"])["fields"]["schedule"], moved)
        with self.assertRaises(RemoteConflict):
            self.adapter.write("task-1", before["id"], FIELDS, before["version"], "operation-2")

    def test_busy_slot_blocks_create(self):
        self.client.busy_entries = [{"id": "meeting", "start": SCHEDULE["start"], "end": SCHEDULE["end"]}]
        with self.assertRaisesRegex(RemoteConflict, "overlaps"):
            self.create()
        self.assertEqual(self.client.calls, [])

    def test_current_event_is_excluded_from_busy_but_same_id_in_other_calendar_is_not(self):
        before = self.create()
        self.client.busy_entries = [{"id": before["id"], "start": SCHEDULE["start"], "end": SCHEDULE["end"],
                                     "calendar_id": self.client.calendar_id}]
        changed = {**FIELDS, "title": "New title"}
        result = self.adapter.write("task-1", before["id"], changed, before["version"], "operation-2")
        self.client.busy_entries[0]["calendar_id"] = "another-calendar"
        with self.assertRaises(RemoteConflict):
            self.adapter.write("task-1", before["id"], FIELDS, result["version"], "operation-3")

    def test_touching_boundaries_are_not_overlap(self):
        self.client.busy_entries = [{"id": "earlier", "start": "2026-09-16T17:00:00+10:00", "end": SCHEDULE["start"]}]
        self.create()
        self.assertEqual(len(self.client.calls), 1)

    def test_recurring_or_attendee_event_never_mutated(self):
        before = self.create()
        for flag in ("recurring", "has_attendees"):
            with self.subTest(flag=flag):
                self.client.events[before["id"]][flag] = True
                with self.assertRaises(RemoteConflict):
                    self.adapter.write("task-1", before["id"], {**FIELDS, "schedule": None}, before["version"], "operation-2")
                self.client.events[before["id"]][flag] = False
        self.assertEqual(len(self.client.calls), 1)

    def test_missing_meeting_flags_or_wrong_scope_stops_sync(self):
        before = self.create()
        del self.client.events[before["id"]]["recurring"]
        with self.assertRaises(ValueError):
            self.adapter.read("task-1", before["id"])
        self.client.events[before["id"]]["recurring"] = False
        self.client.events[before["id"]]["calendar_id"] = "other-calendar"
        with self.assertRaises(ValueError):
            self.adapter.read("task-1", before["id"])

    def test_wrong_marker_and_duplicate_marker_are_refused(self):
        before = self.create()
        with self.assertRaises(ValueError):
            self.adapter.read("other-task", before["id"])
        self.client.events["second"] = {**copy.deepcopy(self.client.events[before["id"]]), "id": "second"}
        with self.assertRaises(RemoteConflict):
            self.adapter.read("task-1")

    def test_provider_conditional_write_rejects_race_after_availability_read(self):
        before = self.create()
        self.client.race = True
        with self.assertRaisesRegex(RemoteConflict, "ETag"):
            self.adapter.write("task-1", before["id"], {**FIELDS, "title": "Changed"}, before["version"], "operation-2")
        self.assertEqual(self.client.events[before["id"]]["title"], FIELDS["title"])

    def test_missing_native_guarantees_prevent_mutation(self):
        self.client.supports_idempotent_create = False
        with self.assertRaisesRegex(RuntimeError, "idempotent"):
            self.create()
        self.client.supports_idempotent_create = True
        before = self.create()
        self.client.supports_atomic_updates = False
        with self.assertRaisesRegex(RuntimeError, "atomic"):
            self.adapter.write("task-1", before["id"], {**FIELDS, "title": "Changed"}, before["version"], "operation-2")
        self.assertEqual(len(self.client.calls), 1)

    def test_unknown_write_outcome_can_be_reconciled_without_duplicate(self):
        self.client.failure = TimeoutError("private details")
        with self.assertRaises(AmbiguousWrite) as error:
            self.create()
        self.assertNotIn("private details", str(error.exception))
        self.client.failure = None
        self.assertEqual(self.create()["fields"], FIELDS)
        self.assertEqual(len(self.client.calls), 1)

    def test_read_failure_is_not_interpreted_as_deletion(self):
        before = self.create()
        def broken(event_id):
            raise RuntimeError("Connection unavailable")
        self.client.get_event = broken
        with self.assertRaisesRegex(RuntimeError, "Connection"):
            self.adapter.read("task-1", before["id"])

    def test_invalid_busy_dates_block_mutation(self):
        self.client.busy_entries = [{"id": "meeting", "start": "2026-09-16", "end": "2026-09-17"}]
        with self.assertRaisesRegex(ValueError, "UTC offsets"):
            self.create()
        self.assertEqual(self.client.calls, [])


class ConnectedWorkflowTests(unittest.TestCase):
    """Real reconciliation and both real adapters over fake provider I/O."""

    def setUp(self):
        self.http = FakeNotion()
        self.notion = NotionAdapter(SOURCE_ID, PROPERTIES, lambda: "test-only-token", self.http)
        self.calendar_client = FakeCalendarClient()
        self.calendar = CalendarAdapter(self.calendar_client)
        self.engine = Engine(":memory:", [self.notion, self.calendar],
                             clock=lambda: datetime(2026, 9, 15, tzinfo=timezone.utc))
        self.addCleanup(self.engine.close)
        self.task = self.engine.create_task("project-1", "task-1", {
            "title": FIELDS["title"], "estimated_minutes": 60, "deliverable": "", "week": 1,
            "due_date": "2026-09-18"}, "create-task")

    def sync_ok(self):
        result = self.engine.sync()
        self.assertEqual(result["errors"], [], result)
        self.assertEqual(result["conflicts"], [], result)
        return result

    def schedule(self):
        task = self.engine.get_task(self.task["id"])
        self.engine.edit_task(task["id"], {"schedule": SCHEDULE}, task["revision"], "schedule-task")
        self.sync_ok()
        return self.calendar.read(task["id"])

    def test_plan_notion_calendar_round_trip_and_stable_ids(self):
        self.sync_ok()
        self.assertEqual(len(self.http.mutations()), 1)
        self.assertEqual(self.calendar_client.calls, [])  # An unscheduled task is not a calendar event.
        event = self.schedule()
        page = self.notion.read(self.task["id"])
        self.assertEqual(page["fields"]["schedule"], SCHEDULE)
        self.assertEqual(self.sync_ok()["synced"], [])
        self.assertEqual(len([call for call in self.calendar_client.calls if call[0] == "create"]), 1)

        # A title edited in Notion updates the existing calendar block.
        self.http.pages[page["id"]]["properties"]["Title"]["title"][0]["text"]["content"] = "Final walkthrough"
        self.sync_ok()
        self.assertEqual(self.engine.get_task(self.task["id"])["title"], "Final walkthrough")
        self.assertEqual(self.calendar_client.events[event["id"]]["title"], "Final walkthrough")

        # A calendar drag updates the same task and Notion range, leaving due date intact.
        moved = {**SCHEDULE, "start": "2026-09-17T18:00:00+10:00", "end": "2026-09-17T19:00:00+10:00"}
        self.calendar_client.events[event["id"]].update(schedule=moved, version=3)
        self.sync_ok()
        self.assertEqual(self.engine.get_task(self.task["id"])["schedule"], moved)
        self.assertEqual(self.notion.read(self.task["id"], page["id"])["fields"]["schedule"], moved)
        self.assertEqual(self.notion.read(self.task["id"], page["id"])["fields"]["due_date"], "2026-09-18")
        self.assertEqual(self.sync_ok()["synced"], [])
        self.assertEqual(len([call for call in self.calendar_client.calls if call[0] == "create"]), 1)

    def test_manual_calendar_deletion_clears_notion_schedule_and_keeps_task(self):
        event = self.schedule()
        self.calendar_client.events[event["id"]].update(deleted=True, schedule=None, version=2)
        self.sync_ok()
        task = self.engine.get_task(self.task["id"])
        self.assertIsNone(task["schedule"])
        self.assertEqual(task["status"], "planned")
        page = self.notion.read(task["id"])
        self.assertIsNone(page["fields"]["schedule"])
        self.assertEqual(page["fields"]["due_date"], "2026-09-18")
        self.assertEqual(self.sync_ok()["synced"], [])

    def test_notion_completion_removes_future_block_and_syncs_all_statuses(self):
        event = self.schedule()
        page = self.notion.read(self.task["id"])
        self.http.pages[page["id"]]["properties"]["Status"]["status"]["name"] = "completed"
        self.sync_ok()
        task = self.engine.get_task(self.task["id"])
        self.assertEqual(task["status"], "completed")
        self.assertIsNone(task["schedule"])
        self.assertTrue(self.calendar_client.events[event["id"]]["deleted"])
        self.assertIsNone(self.notion.read(task["id"])["fields"]["schedule"])
        self.assertEqual([call[0] for call in self.calendar_client.calls], ["create", "delete"])
        self.assertEqual(self.sync_ok()["synced"], [])


class LiveBusyCalendarClient(FakeCalendarClient):
    """Availability derives from events, including intermediate writes in swaps."""

    def __init__(self):
        super().__init__()
        self.edit_during_busy = None
        self.overlap_seen = False

    def busy(self, start, end):
        if self.edit_during_busy:
            event = self.events[self.edit_during_busy]
            event["title"] = "Manual edit after batch approval"
            event["version"] += 1
            self.edit_during_busy = None
        items = copy.deepcopy(self.busy_entries)
        active = [event for event in self.events.values() if not event["deleted"]]
        for event in active:
            items.append({"id": event["id"], "calendar_id": event["calendar_id"],
                          "start": event["schedule"]["start"], "end": event["schedule"]["end"]})
        for index, left in enumerate(active):
            if any(CalendarAdapter._overlap(left["schedule"], right["schedule"]) for right in active[index + 1:]):
                self.overlap_seen = True
        return items


class CalendarBatchTests(unittest.TestCase):
    def setUp(self):
        self.client = LiveBusyCalendarClient()
        self.calendar = CalendarAdapter(self.client)
        self.engine = Engine(":memory:", [self.calendar], clock=lambda: datetime(2026, 9, 15, tzinfo=timezone.utc))
        self.addCleanup(self.engine.close)
        self.first_slot = copy.deepcopy(SCHEDULE)
        self.second_slot = {**SCHEDULE, "start": "2026-09-16T19:00:00+10:00", "end": "2026-09-16T20:00:00+10:00"}
        self.first = self.engine.create_task("project", "first", {"title": "First", "schedule": self.first_slot}, "create-first")
        self.second = self.engine.create_task("project", "second", {"title": "Second", "schedule": self.second_slot}, "create-second")
        initial = self.engine.sync()
        self.assertEqual(initial["errors"], [], initial)
        self.first_event = self.calendar.read(self.first["id"])
        self.second_event = self.calendar.read(self.second["id"])

    def approve_swap(self):
        first = self.engine.get_task(self.first["id"])
        second = self.engine.get_task(self.second["id"])
        self.engine.apply_operations([
            {"task_id": first["id"], "expected_revision": first["revision"], "action": "schedule", "patch": {"schedule": self.second_slot}},
            {"task_id": second["id"], "expected_revision": second["revision"], "action": "schedule", "patch": {"schedule": self.first_slot}},
        ], "swap")

    def moves(self):
        return [
            {"task_id": self.first["id"], "remote_id": self.first_event["id"], "version": self.first_event["version"],
             "desired": {"title": "First", "schedule": self.second_slot}},
            {"task_id": self.second["id"], "remote_id": self.second_event["id"], "version": self.second_event["version"],
             "desired": {"title": "Second", "schedule": self.first_slot}},
        ]

    def test_engine_outgoing_swap_finishes_with_real_busy_intervals(self):
        self.approve_swap()
        result = self.engine.sync()
        self.assertEqual(result["errors"], [], result)
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(self.client.events[self.first_event["id"]]["schedule"], self.second_slot)
        self.assertEqual(self.client.events[self.second_event["id"]]["schedule"], self.first_slot)
        self.assertTrue(self.client.overlap_seen)  # Serial provider writes are explicitly eventual.
        self.assertEqual([call[0] for call in self.client.calls], ["create", "create", "update", "update"])
        self.assertEqual(self.engine.sync()["synced"], [])

    def test_manual_edit_on_vacating_participant_blocks_swap(self):
        self.approve_swap()
        self.client.edit_during_busy = self.second_event["id"]
        result = self.engine.sync()
        self.assertTrue(result["errors"], result)
        self.assertEqual([call[0] for call in self.client.calls], ["create", "create"])
        self.assertEqual(self.client.events[self.first_event["id"]]["schedule"], self.first_slot)
        self.assertEqual(self.client.events[self.second_event["id"]]["schedule"], self.second_slot)

    def test_clearing_batch_prevents_stale_slot_exemption(self):
        self.calendar.prepare_batch(self.moves())
        self.calendar.prepare_batch([])
        with self.assertRaisesRegex(RemoteConflict, "overlaps"):
            self.calendar.write(self.first["id"], self.first_event["id"], self.moves()[0]["desired"], self.first_event["version"], "move-first")

    def test_foreign_marker_or_duplicate_event_never_exempts_busy_slot(self):
        for kind in ("marker", "duplicate"):
            with self.subTest(kind=kind):
                self.calendar.prepare_batch(self.moves())
                second = self.client.events[self.second_event["id"]]
                if kind == "marker":
                    second["task_id"] = "unrelated-task"
                else:
                    self.client.events["duplicate"] = {**copy.deepcopy(second), "id": "duplicate"}
                with self.assertRaises((RemoteConflict, ValueError)):
                    self.calendar.write(self.first["id"], self.first_event["id"], self.moves()[0]["desired"], self.first_event["version"], "move-first")
                second["task_id"] = self.second["id"]
                self.client.events.pop("duplicate", None)
        self.assertEqual([call[0] for call in self.client.calls], ["create", "create"])

    def test_unapproved_third_write_cannot_use_prepared_swap(self):
        self.calendar.prepare_batch(self.moves())
        with self.assertRaisesRegex(RemoteConflict, "overlaps"):
            self.calendar.write("third-task", None, {"title": "Third", "schedule": self.second_slot}, None, "third-op")

    def test_duplicate_or_overlapping_batch_replaces_previous_context(self):
        self.calendar.prepare_batch(self.moves())
        invalid = self.moves()
        invalid[1]["desired"]["schedule"] = self.second_slot
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.calendar.prepare_batch(invalid)
        with self.assertRaisesRegex(RemoteConflict, "overlaps"):
            self.calendar.write(self.first["id"], self.first_event["id"], self.moves()[0]["desired"], self.first_event["version"], "move-first")


if __name__ == "__main__":
    unittest.main()
