"""Scoped Notion task adapter, using the 2026-03-11 data-source API.

Pass an existing data source ID and an explicit ``properties`` mapping from each
key below to an existing Notion property name (or ID):

* title: title; status: status (four existing options, configurable names)
* estimated_minutes and week: number (week is a relative positive integer)
* due_date: date; schedule: date range
* sync_id, operation_id, project_id, deliverable, depends_on,
  schedule_timezone: rich_text

``depends_on`` contains a JSON array of stable task IDs, not Notion page IDs.
The schedule timezone is separate because Notion may normalise date offsets.
The adapter never creates a database, modifies schema, searches the workspace,
archives pages, or edits page bodies. Cancellation is a task status. A configured
source must be shared with the connection; a 404 is not proof of deletion.

The host owns credentials (``token_supplier()``), polling and a single sync writer.
``transport(method, url, headers, body)`` may be injected; it returns parsed JSON
or raises NotionAPIError/TimeoutError/OSError. No request/response is logged.

Notion has no documented atomic If-Match update for pages: the fresh-read version
check is best effort and cannot exclude a manual edit between GET and PATCH.
Do not run multiple writers for the same source. Ambiguous writes must be
reconciled before another mutation; the operation and sync markers aid recovery.

API references (verified 2026-09-15):
https://developers.notion.com/reference/query-a-data-source
https://developers.notion.com/reference/parent-object
https://developers.notion.com/reference/post-page
https://developers.notion.com/reference/patch-page
https://developers.notion.com/reference/page-property-values
"""

from __future__ import annotations

from datetime import date, datetime, timezone as utc_timezone
import hashlib
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID
from zoneinfo import ZoneInfo

from planning_sync import AmbiguousWrite, RemoteConflict, normalise_schedule


PROPERTY_TYPES = {
    "sync_id": "rich_text", "operation_id": "rich_text", "title": "title",
    "status": "status", "project_id": "rich_text", "estimated_minutes": "number",
    "deliverable": "rich_text", "depends_on": "rich_text", "week": "number",
    "due_date": "date", "schedule": "date", "schedule_timezone": "rich_text",
}
STATUSES = frozenset({"planned", "in_progress", "completed", "cancelled"})


class NotionAPIError(RuntimeError):
    """Sanitised API diagnostic; never includes credentials or response bodies."""

    def __init__(self, status: int, retry_after: str | None = None):
        self.status = status
        self.retry_after = retry_after
        super().__init__(f"Notion request failed (HTTP {status}); check connection and source access.")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def notion_transport(method, url, headers, body):
    """Send exactly one bounded request without retrying or following redirects."""
    request = Request(url, data=None if body is None else json.dumps(body).encode("utf-8"),
                      headers=headers, method=method)
    try:
        with build_opener(_NoRedirect).open(request, timeout=30) as response:
            raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ValueError("Notion response exceeded the supported size.")
            return json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        retry_after = exc.headers.get("Retry-After")
        if retry_after is not None and not retry_after.isdecimal():
            retry_after = None
        raise NotionAPIError(exc.code, retry_after) from None
    except URLError:
        raise ConnectionError("Notion connection failed; check connection and retry status.") from None
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("Notion returned unreadable JSON.") from None


def _uuid(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("A valid Notion data source or page ID is required.") from None


def _text(value):
    if value is None:
        return []
    if not isinstance(value, str) or len(value) > 40_000:
        raise ValueError("Notion text must be a string of at most 40,000 characters.")
    return [{"type": "text", "text": {"content": value[i:i + 2000]}}
            for i in range(0, len(value), 2000)]


def _read_text(items):
    if not isinstance(items, list):
        raise ValueError("Notion returned an invalid text property.")
    # Explicit plain text avoids interpreting page references as stable IDs.
    if any(item.get("type", "text") != "text" for item in items):
        raise ValueError("Synced Notion text properties must contain plain text.")
    return "".join(item.get("plain_text", item.get("text", {}).get("content", "")) for item in items)


def _timestamp(value, timezone=None):
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("Scheduled dates must include a time and UTC offset.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timezone:
        zone = ZoneInfo(timezone)
        if parsed.utcoffset() is None:
            candidate = parsed.replace(tzinfo=zone)
            if (candidate.utcoffset() != candidate.replace(fold=1).utcoffset() or
                    candidate.astimezone(utc_timezone.utc).astimezone(zone).replace(tzinfo=None) != parsed):
                raise ValueError("Ambiguous or nonexistent Notion time; provide an explicit UTC offset.")
            parsed = candidate
        parsed = parsed.astimezone(zone)
    elif parsed.utcoffset() is None:
        raise ValueError("Scheduled dates must include a UTC offset.")
    return parsed.isoformat()


class NotionAdapter:
    name = "notion"
    fields = frozenset({"title", "status", "project_id", "estimated_minutes", "deliverable",
                        "depends_on", "week", "due_date", "schedule"})

    def __init__(self, data_source_id, properties, token_supplier, transport=None, status_names=None):
        self.data_source_id = _uuid(data_source_id)
        if not isinstance(properties, dict) or set(properties) != set(PROPERTY_TYPES):
            raise ValueError("Configure every required Notion property mapping exactly once.")
        if any(not isinstance(value, str) or not value.strip() for value in properties.values()):
            raise ValueError("Notion property names or IDs must be nonempty strings.")
        if len(set(properties.values())) != len(properties):
            raise ValueError("Each synced Notion field needs its own property.")
        self.properties = dict(properties)
        self.status_names = dict(status_names if status_names is not None else {key: key for key in STATUSES})
        if (set(self.status_names) != STATUSES or
                any(not isinstance(value, str) or not value.strip() for value in self.status_names.values()) or
                len(set(self.status_names.values())) != len(STATUSES)):
            raise ValueError("Map the four canonical statuses to distinct existing Notion status options.")
        if not callable(token_supplier):
            raise ValueError("Provide a callable token supplier.")
        self._token_supplier = token_supplier
        self._transport = transport or notion_transport

    def _request(self, method, path, body=None, *, mutation=False):
        token = self._token_supplier()
        if not isinstance(token, str) or not token.strip() or "\n" in token or "\r" in token:
            raise ValueError("A valid Notion connection token is required.")
        try:
            result = self._transport(method, "https://api.notion.com/v1/" + path,
                                     {"Authorization": "Bearer " + token,
                                      "Content-Type": "application/json", "Notion-Version": "2026-03-11"}, body)
            if not isinstance(result, dict):
                raise ValueError("Notion returned an invalid response.")
            return result
        except NotionAPIError as exc:
            if mutation and exc.status == 409:
                raise RemoteConflict("Notion changed during the update; read and reconcile again.") from None
            if mutation and exc.status >= 500:
                raise AmbiguousWrite("Notion write outcome is unknown; reconcile before retrying.") from None
            raise
        except (OSError, ValueError):
            if mutation:
                raise AmbiguousWrite("Notion write outcome is unknown; reconcile before retrying.") from None
            raise RuntimeError("Notion could not be read; check access and connection.") from None

    def _property(self, page, key):
        props = page.get("properties", {})
        name = self.properties[key]
        prop = props.get(name)
        if prop is None:
            prop = next((value for value in props.values() if value.get("id") == name), None)
        kind = PROPERTY_TYPES[key]
        if not isinstance(prop, dict) or prop.get("type", kind) != kind or kind not in prop:
            raise ValueError("A mapped Notion property is missing or has the wrong type: " + key)
        return prop[kind]

    def validate_schema(self):
        """Read-only preflight: existing properties/options must already match."""
        source = self._request("GET", "data_sources/" + self.data_source_id)
        if _uuid(source.get("id")) != self.data_source_id:
            raise ValueError("Notion returned the wrong data source.")
        props = source.get("properties", {})
        seen_ids = set()
        for key, kind in PROPERTY_TYPES.items():
            name = self.properties[key]
            prop = props.get(name)
            if prop is None:
                prop = next((value for value in props.values() if value.get("id") == name), None)
            if not isinstance(prop, dict) or prop.get("type") != kind:
                raise ValueError("A mapped Notion schema property is missing or has the wrong type: " + key)
            prop_id = prop.get("id", name)
            if prop_id in seen_ids:
                raise ValueError("Two mappings resolve to the same Notion property.")
            seen_ids.add(prop_id)
            if key == "status":
                names = {item.get("name") for item in prop["status"].get("options", [])}
                if not set(self.status_names.values()).issubset(names):
                    raise ValueError("Create the configured Notion status options before connecting sync.")

    def _snapshot(self, page, task_id):
        parent = page.get("parent", {})
        if (page.get("object") != "page" or parent.get("type") != "data_source_id" or
                _uuid(parent.get("data_source_id")) != self.data_source_id):
            raise ValueError("Linked Notion page is outside the configured data source.")
        if _read_text(self._property(page, "sync_id")) != task_id:
            raise ValueError("Linked Notion page has a different stable task ID.")
        status_name = (self._property(page, "status") or {}).get("name")
        inverse_status = {value: key for key, value in self.status_names.items()}
        if status_name not in inverse_status:
            raise ValueError("Notion task status does not match the configured status mapping.")
        dependencies = _read_text(self._property(page, "depends_on"))
        try:
            dependencies = json.loads(dependencies) if dependencies else []
        except ValueError:
            raise ValueError("Notion dependency IDs must be a JSON array.") from None
        due = self._property(page, "due_date")
        if due and (due.get("end") is not None or "T" in due["start"]):
            raise ValueError("Notion due_date must be a single date without a time.")
        scheduled = self._property(page, "schedule")
        timezone = _read_text(self._property(page, "schedule_timezone"))
        schedule = None
        if scheduled:
            if not timezone:
                raise ValueError("A scheduled Notion task requires its schedule timezone.")
            timezone = scheduled.get("time_zone") or timezone
            schedule = {"start": _timestamp(scheduled["start"], timezone),
                        "end": _timestamp(scheduled.get("end"), timezone), "timezone": timezone}
        values = {"title": _read_text(self._property(page, "title")), "status": inverse_status[status_name],
                  "project_id": _read_text(self._property(page, "project_id")),
                  "estimated_minutes": self._property(page, "estimated_minutes"),
                  "deliverable": _read_text(self._property(page, "deliverable")),
                  "depends_on": dependencies, "week": self._property(page, "week"),
                  "due_date": due["start"] if due else None, "schedule": schedule}
        values = self._normalise(values)
        deleted = bool(page.get("in_trash") or page.get("archived") or page.get("is_archived"))
        edited = page.get("last_edited_time")
        if not isinstance(edited, str) or not edited:
            raise ValueError("Notion returned no version timestamp.")
        signature = json.dumps({"fields": values, "deleted": deleted}, sort_keys=True, separators=(",", ":"))
        return {"id": _uuid(page["id"]), "version": edited + ":" + hashlib.sha256(signature.encode()).hexdigest(),
                "fields": values, "deleted": deleted,
                "last_operation_id": _read_text(self._property(page, "operation_id")) or None}

    def _normalise(self, values):
        if set(values) != self.fields:
            raise ValueError("Write the complete Notion task projection.")
        result = dict(values)
        if not isinstance(result["title"], str) or not result["title"].strip():
            raise ValueError("A task title is required.")
        if result["status"] not in STATUSES:
            raise ValueError("A supported task status is required.")
        if not isinstance(result["project_id"], str) or not result["project_id"].strip():
            raise ValueError("A task project ID is required.")
        if not isinstance(result["deliverable"], str):
            raise ValueError("The task deliverable must be text.")
        for key in ("estimated_minutes", "week"):
            value = result[key]
            # Notion's number properties may decode as integral floats.
            if isinstance(value, float) and value.is_integer():
                result[key] = value = int(value)
            if type(value) is not int or value <= 0:
                raise ValueError("Task effort and week must be positive integers.")
        if (not isinstance(result["depends_on"], list) or
                any(not isinstance(item, str) or not item for item in result["depends_on"])):
            raise ValueError("Dependencies must be a list of stable task IDs.")
        if len(result["depends_on"]) != len(set(result["depends_on"])):
            raise ValueError("A dependency may only be included once.")
        if result["due_date"] is not None:
            if not isinstance(result["due_date"], str) or len(result["due_date"]) != 10:
                raise ValueError("due_date must be an ISO date or null.")
            result["due_date"] = date.fromisoformat(result["due_date"]).isoformat()
        result["schedule"] = normalise_schedule(result["schedule"])
        return result

    def read(self, task_id, remote_id=None):
        if not isinstance(task_id, str) or not task_id or len(task_id) > 2000:
            raise ValueError("A nonempty stable task ID of at most 2,000 characters is required.")
        if remote_id:
            return self._snapshot(self._request("GET", "pages/" + _uuid(remote_id)), task_id)
        matches = {}
        # Include trash when recovering an unknown create outcome: never recreate
        # a task simply because its existing page was moved to trash.
        for in_trash in (False, True):
            cursor = None
            cursors = set()
            while True:
                body = {"filter": {"property": self.properties["sync_id"], "rich_text": {"equals": task_id}},
                        "page_size": 100, "in_trash": in_trash, "result_type": "page"}
                if cursor:
                    body["start_cursor"] = cursor
                response = self._request("POST", "data_sources/" + self.data_source_id + "/query", body)
                if not isinstance(response.get("results"), list):
                    raise ValueError("Notion returned an invalid page query.")
                for page in response["results"]:
                    snapshot = self._snapshot(page, task_id)
                    matches[snapshot["id"]] = snapshot
                    if len(matches) > 1:
                        raise RemoteConflict("Multiple Notion pages use this task ID; resolve duplicates before syncing.")
                if not response.get("has_more"):
                    break
                cursor = response.get("next_cursor")
                if not isinstance(cursor, str) or not cursor or cursor in cursors:
                    raise ValueError("Notion returned invalid pagination; sync was stopped.")
                cursors.add(cursor)
        return next(iter(matches.values()), None)

    def _encode(self, task_id, values, operation_id):
        raw = {"sync_id": _text(task_id), "operation_id": _text(operation_id),
               "title": _text(values["title"]), "status": {"name": self.status_names[values["status"]]},
               "project_id": _text(values["project_id"]), "estimated_minutes": values["estimated_minutes"],
               "deliverable": _text(values["deliverable"]), "depends_on": _text(json.dumps(values["depends_on"])),
               "week": values["week"], "due_date": {"start": values["due_date"]} if values["due_date"] else None,
               "schedule": None, "schedule_timezone": []}
        if values["schedule"]:
            schedule = values["schedule"]
            raw["schedule"] = {"start": schedule["start"], "end": schedule["end"]}
            raw["schedule_timezone"] = _text(schedule["timezone"])
        return {self.properties[key]: {PROPERTY_TYPES[key]: value} for key, value in raw.items()}

    def write(self, task_id, remote_id, fields, expected_version, operation_id):
        values = self._normalise(fields)
        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError("A stable operation ID is required.")
        body = {"properties": self._encode(task_id, values, operation_id)}
        self.validate_schema()
        current = self.read(task_id, remote_id)
        if current is not None:
            if current["deleted"]:
                raise RemoteConflict("Notion task is archived or in trash; reconcile before writing.")
            if current["last_operation_id"] == operation_id and current["fields"] == values:
                return current
            if current["version"] != expected_version:
                raise RemoteConflict("Notion task changed; read and reconcile before writing.")
        elif remote_id is not None or expected_version is not None:
            raise RemoteConflict("Notion task is unavailable; reconcile before writing.")
        if current is None:
            body["parent"] = {"type": "data_source_id", "data_source_id": self.data_source_id}
            response = self._request("POST", "pages", body, mutation=True)
        else:
            response = self._request("PATCH", "pages/" + quote(current["id"], safe=""), body, mutation=True)
        try:
            snapshot = self._snapshot(response, task_id)
        except (KeyError, TypeError, ValueError):
            raise AmbiguousWrite("Notion write response could not be verified; reconcile before retrying.") from None
        if snapshot["fields"] != values or snapshot["last_operation_id"] != operation_id or snapshot["deleted"]:
            raise RemoteConflict("Notion changed during the update; read and reconcile again.")
        return snapshot
