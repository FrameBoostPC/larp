"""Notion wire-contract checks with an in-memory HTTP transport; no account calls."""

import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "components" / "planning-sync"))
from notion_adapter import NotionAdapter, NotionAPIError, PROPERTY_TYPES
from planning_sync import AmbiguousWrite, RemoteConflict


SOURCE_ID = "d9824bdc-8445-4327-be8b-5b47500af6ce"
PAGE_ID = "b55c9c91-384d-452b-81db-d1ef79372b75"
OTHER_ID = "e9824bdc-8445-4327-be8b-5b47500af6ce"
PROPERTIES = {key: key.replace("_", " ").title() for key in PROPERTY_TYPES}
FIELDS = {"title": "Record walkthrough", "status": "planned", "project_id": "demo-project",
          "estimated_minutes": 60, "deliverable": "A recorded demonstration", "depends_on": [],
          "week": 1, "due_date": "2026-09-18", "schedule": {"start": "2026-09-16T18:00:00+10:00",
          "end": "2026-09-16T19:00:00+10:00", "timezone": "Australia/Brisbane"}}


class FakeNotion:
    def __init__(self):
        self.calls = []
        self.pages = {}
        self.queries = []
        self.fail_mutation = None
        self.fail_read = None
        self.schema = {"object": "data_source", "id": SOURCE_ID, "properties": {
            PROPERTIES[key]: {"id": key, "type": kind, kind: ({"options": [
                {"name": status} for status in ("planned", "in_progress", "completed", "cancelled")]
            } if kind == "status" else {})} for key, kind in PROPERTY_TYPES.items()}}

    def __call__(self, method, url, headers, body):
        # Tokens are intentionally not recorded in request traces.
        self.calls.append((method, url, copy.deepcopy(body), headers["Notion-Version"]))
        path = url.removeprefix("https://api.notion.com/v1/")
        if method == "GET":
            if self.fail_read:
                raise self.fail_read
            if path == "data_sources/" + SOURCE_ID:
                return copy.deepcopy(self.schema)
            page = self.pages.get(path.removeprefix("pages/"))
            if page is None:
                raise NotionAPIError(404)
            return copy.deepcopy(page)
        if path == "data_sources/" + SOURCE_ID + "/query":
            if self.queries:
                return copy.deepcopy(self.queries.pop(0))
            task_id = body["filter"]["rich_text"]["equals"]
            matches = [page for page in self.pages.values() if
                       page["properties"][PROPERTIES["sync_id"]]["rich_text"][0]["text"]["content"] == task_id
                       and bool(page.get("in_trash")) == body["in_trash"]]
            return {"results": copy.deepcopy(matches), "has_more": False, "next_cursor": None}
        if self.fail_mutation:
            raise self.fail_mutation
        if method == "POST" and path == "pages":
            page = {"object": "page", "id": PAGE_ID, "parent": body["parent"], "in_trash": False,
                    "last_edited_time": "2026-09-15T00:00:00.000Z", "properties": {}}
        elif method == "PATCH" and path.startswith("pages/"):
            page = copy.deepcopy(self.pages[path.removeprefix("pages/")])
            page["last_edited_time"] = "2026-09-15T00:01:00.000Z"
        else:
            raise AssertionError("Unexpected transport operation")
        for name, value in body["properties"].items():
            kind = next(iter(value))
            page["properties"][name] = {"id": name, "type": kind, **copy.deepcopy(value)}
        self.pages[page["id"]] = page
        return copy.deepcopy(page)

    def mutations(self):
        return [(method, url, body) for method, url, body, _ in self.calls
                if method == "PATCH" or (method == "POST" and url.endswith("/pages"))]


class NotionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeNotion()
        self.adapter = NotionAdapter(SOURCE_ID, PROPERTIES, lambda: "test-only-token", self.transport)

    def create(self):
        return self.adapter.write("project:task-1", None, copy.deepcopy(FIELDS), None, "operation-1")

    def test_create_uses_data_source_parent_stable_marker_and_separate_dates(self):
        snapshot = self.create()
        self.assertEqual(snapshot["fields"], FIELDS)
        self.assertFalse(snapshot["deleted"])
        body = self.transport.mutations()[0][2]
        self.assertEqual(body["parent"], {"type": "data_source_id", "data_source_id": SOURCE_ID})
        self.assertEqual(body["properties"]["Due Date"], {"date": {"start": "2026-09-18"}})
        self.assertEqual(body["properties"]["Schedule"]["date"]["end"], FIELDS["schedule"]["end"])
        self.assertEqual(body["properties"]["Sync Id"]["rich_text"][0]["text"]["content"], "project:task-1")
        self.assertTrue(all(version == "2026-03-11" for _, _, _, version in self.transport.calls))

    def test_repeated_create_operation_finds_same_page_without_duplicate(self):
        self.create()
        snapshot = self.create()
        self.assertEqual(snapshot["id"], PAGE_ID)
        self.assertEqual(len(self.transport.mutations()), 1)

    def test_reschedule_updates_linked_page_and_preserves_deadline(self):
        before = self.create()
        values = copy.deepcopy(FIELDS)
        values["schedule"].update(start="2026-09-17T18:00:00+10:00", end="2026-09-17T19:00:00+10:00")
        result = self.adapter.write("project:task-1", PAGE_ID, values, before["version"], "operation-2")
        self.assertEqual(result["fields"]["due_date"], FIELDS["due_date"])
        self.assertEqual(result["fields"]["schedule"], values["schedule"])
        self.assertEqual(self.transport.mutations()[-1][0], "PATCH")

    def test_cleared_schedule_is_explicit_and_cancellation_does_not_archive(self):
        before = self.create()
        values = {**FIELDS, "schedule": None, "status": "cancelled"}
        result = self.adapter.write("project:task-1", PAGE_ID, values, before["version"], "operation-2")
        self.assertIsNone(result["fields"]["schedule"])
        self.assertFalse(result["deleted"])
        body = self.transport.mutations()[-1][2]
        self.assertEqual(body["properties"]["Schedule"], {"date": None})
        self.assertEqual(body["properties"]["Schedule Timezone"], {"rich_text": []})
        self.assertNotIn("archived", body)
        self.assertNotIn("in_trash", body)

    def test_manual_edits_are_read_back_and_stale_updates_refused(self):
        before = self.create()
        self.transport.pages[PAGE_ID]["properties"]["Title"]["title"][0]["text"]["content"] = "Edited in Notion"
        # Even same-timestamp changes affect the projection hash.
        current = self.adapter.read("project:task-1", PAGE_ID)
        self.assertEqual(current["fields"]["title"], "Edited in Notion")
        with self.assertRaises(RemoteConflict):
            self.adapter.write("project:task-1", PAGE_ID, FIELDS, before["version"], "operation-2")
        self.assertEqual(len(self.transport.mutations()), 1)

    def test_existing_page_cannot_be_overwritten_without_expected_version(self):
        self.create()
        with self.assertRaises(RemoteConflict):
            self.adapter.write("project:task-1", None, {**FIELDS, "title": "New title"}, None, "new-operation")
        self.assertEqual(len(self.transport.mutations()), 1)

    def test_page_outside_source_or_wrong_marker_is_never_edited(self):
        before = self.create()
        self.transport.pages[PAGE_ID]["parent"]["data_source_id"] = OTHER_ID
        with self.assertRaises(ValueError):
            self.adapter.write("project:task-1", PAGE_ID, FIELDS, before["version"], "operation-2")
        self.transport.pages[PAGE_ID]["parent"]["data_source_id"] = SOURCE_ID
        with self.assertRaises(ValueError):
            self.adapter.read("another-task", PAGE_ID)
        self.assertEqual(len(self.transport.mutations()), 1)

    def test_trashed_unknown_page_is_found_and_not_recreated(self):
        self.create()
        self.transport.pages[PAGE_ID]["in_trash"] = True
        self.assertTrue(self.adapter.read("project:task-1")["deleted"])
        with self.assertRaises(RemoteConflict):
            self.create()
        self.assertEqual(len(self.transport.mutations()), 1)

    def test_404_does_not_mean_deleted_or_trigger_create(self):
        with self.assertRaises(NotionAPIError) as error:
            self.adapter.read("project:task-1", PAGE_ID)
        self.assertEqual(error.exception.status, 404)
        self.assertEqual(self.transport.mutations(), [])

    def test_pagination_finds_marker_on_second_page_and_queries_trash(self):
        self.create()
        self.transport.queries = [
            {"results": [], "has_more": True, "next_cursor": "next"},
            {"results": [self.transport.pages[PAGE_ID]], "has_more": False},
            {"results": [], "has_more": False}]
        self.assertEqual(self.adapter.read("project:task-1")["id"], PAGE_ID)
        self.assertEqual(self.transport.calls[-2][2]["start_cursor"], "next")
        self.assertTrue(self.transport.calls[-1][2]["in_trash"])

    def test_duplicate_marker_stops_sync(self):
        self.create()
        duplicate = copy.deepcopy(self.transport.pages[PAGE_ID])
        duplicate["id"] = OTHER_ID
        self.transport.pages[OTHER_ID] = duplicate
        with self.assertRaises(RemoteConflict):
            self.adapter.read("project:task-1")

    def test_timeout_or_server_failure_is_ambiguous_and_never_retried(self):
        for failure in (TimeoutError("private details"), NotionAPIError(503)):
            with self.subTest(failure=type(failure).__name__):
                self.transport.fail_mutation = failure
                before = len(self.transport.mutations())
                with self.assertRaises(AmbiguousWrite) as error:
                    self.create()
                self.assertEqual(len(self.transport.mutations()), before + 1)
                self.assertNotIn("private details", str(error.exception))

    def test_conflict_and_rate_limit_keep_distinct_retry_semantics(self):
        self.transport.fail_mutation = NotionAPIError(409)
        with self.assertRaises(RemoteConflict):
            self.create()
        self.transport.fail_mutation = NotionAPIError(429, "10")
        with self.assertRaises(NotionAPIError) as error:
            self.create()
        self.assertEqual(error.exception.retry_after, "10")

    def test_missing_schema_option_is_reported_without_schema_mutation(self):
        self.transport.schema["properties"]["Status"]["status"]["options"] = []
        with self.assertRaisesRegex(ValueError, "status options"):
            self.create()
        self.assertEqual(self.transport.mutations(), [])

    def test_custom_status_option_names_round_trip(self):
        names = {"planned": "To do", "in_progress": "Doing", "completed": "Done", "cancelled": "Cancelled"}
        self.transport.schema["properties"]["Status"]["status"]["options"] = [{"name": value} for value in names.values()]
        self.adapter = NotionAdapter(SOURCE_ID, PROPERTIES, lambda: "test-only-token", self.transport, names)
        self.assertEqual(self.create()["fields"]["status"], "planned")
        self.assertEqual(self.transport.pages[PAGE_ID]["properties"]["Status"]["status"]["name"], "To do")

    def test_invalid_dependencies_are_not_silently_lost(self):
        self.create()
        self.transport.pages[PAGE_ID]["properties"]["Depends On"]["rich_text"] = [{"text": {"content": "not json"}}]
        with self.assertRaisesRegex(ValueError, "JSON array"):
            self.adapter.read("project:task-1", PAGE_ID)

    def test_date_only_schedule_is_not_confused_with_a_timed_event(self):
        self.create()
        self.transport.pages[PAGE_ID]["properties"]["Schedule"]["date"]["start"] = "2026-09-16"
        with self.assertRaisesRegex(ValueError, "time and UTC offset"):
            self.adapter.read("project:task-1", PAGE_ID)

    def test_full_projection_required_before_network(self):
        with self.assertRaisesRegex(ValueError, "complete Notion"):
            self.adapter.write("task", None, {"title": "Partial"}, None, "operation")
        self.assertEqual(self.transport.calls, [])

    def test_empty_deliverable_round_trips_without_becoming_null(self):
        values = {**FIELDS, "deliverable": ""}
        snapshot = self.adapter.write("project:task-1", None, values, None, "operation")
        self.assertEqual(snapshot["fields"]["deliverable"], "")

    def test_notion_utc_normalisation_preserves_named_schedule_timezone(self):
        self.create()
        self.transport.pages[PAGE_ID]["properties"]["Schedule"]["date"].update(
            start="2026-09-16T08:00:00.000Z", end="2026-09-16T09:00:00.000Z")
        self.assertEqual(self.adapter.read("project:task-1", PAGE_ID)["fields"]["schedule"], FIELDS["schedule"])

    def test_notion_explicit_timezone_with_local_timestamp_is_read(self):
        self.create()
        self.transport.pages[PAGE_ID]["properties"]["Schedule"]["date"].update(
            start="2026-09-16T18:00:00", end="2026-09-16T19:00:00", time_zone="Australia/Brisbane")
        self.assertEqual(self.adapter.read("project:task-1", PAGE_ID)["fields"]["schedule"], FIELDS["schedule"])


if __name__ == "__main__":
    unittest.main()
