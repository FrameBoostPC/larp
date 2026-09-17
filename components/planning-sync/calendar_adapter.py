"""Calendar focus-block logic over the host's explicitly selected calendar client.

This is a provider-neutral bridge, not a configured Google/Microsoft connector.
The host supplies OAuth, provider SDK calls, pagination, polling/webhooks and:

* ``calendar_id``: the one writable calendar's ID.
* ``supports_atomic_updates`` and ``supports_idempotent_create``: booleans
  asserted only when the provider implementation really supplies these guarantees.
* ``get_event(id)``: a fresh event, or None for verified deletion/absence. Raise
  on permission failures, network errors or ambiguous 404 responses.
* ``find_task_events(task_id)``: all events with the exact stable marker in the
  selected calendar, including available deletion tombstones. Paginate fully.
* ``busy(start, end)``: all busy entries from all user-selected blocking calendars.
  Each entry is {id, start, end, calendar_id?}; another calendar requires its ID.
  Expand recurrence and normalise all-day events into offset-bearing boundaries.
* ``create_event(event, idempotency_key=...)``
* ``update_event(id, event, expected_version=..., idempotency_key=...)``
* ``delete_event(id, expected_version=..., idempotency_key=...)``

All mutation methods return the resulting event, including a deletion tombstone.
Events contain {id, version, task_id, title, schedule, deleted, recurring,
has_attendees}; calendar_id is optional and checked if present. The two meeting
flags must be explicit booleans. ``schedule`` is None for deletion or contains
start/end ISO timestamps with their correct UTC offset plus an IANA timezone.

Outgoing create/update objects contain only task_id, title and schedule. Store
the marker privately; use provider PATCH semantics and preserve unrelated fields.
Never send invitations. Provider update/delete must use atomic conditional writes
(e.g. real ETag If-Match); raise RemoteConflict on failure. If this cannot be done,
declare the capability false. Create must honour the durable idempotency key;
otherwise declare false. Unknown write outcomes raise AmbiguousWrite. Sanitize
provider diagnostics before raising; the sync engine displays exception messages.

Fresh busy reads cannot atomically reserve a slot in an unrelated calendar.
They detect observed conflicts; a simultaneous external booking can still race.
The host must rerun reconciliation and availability checks after provider changes.

``prepare_batch(moves)`` receives only reconciled, ready pending operations from
the engine: {task_id, remote_id, version, desired: {title, schedule}}. It permits
an approved focus block to occupy a destination temporarily while its own move
vacates that interval. Every exemption requires fresh ownership and version
checks. This supports serial swaps, not an atomic calendar transaction. A partial
failure can leave a temporary overlap; remaining operations stay pending. Never
include unresolved, failed or ambiguous operations in a prepared batch.
"""

from __future__ import annotations

from datetime import datetime

from planning_sync import AmbiguousWrite, RemoteConflict, normalise_schedule


class CalendarAdapter:
    name = "calendar"
    fields = frozenset({"title", "schedule"})

    def __init__(self, client):
        if not isinstance(getattr(client, "calendar_id", None), str) or not client.calendar_id.strip():
            raise ValueError("Select a writable calendar explicitly before connecting the adapter.")
        for method in ("get_event", "find_task_events", "busy", "create_event", "update_event", "delete_event"):
            if not callable(getattr(client, method, None)):
                raise ValueError("Calendar client is missing a required method: " + method)
        self.client = client
        self._batch = {}
        self._batch_tasks = {}

    def prepare_batch(self, moves):
        """Replace the current poll's approved moves; no provider mutation."""
        self._batch = {}
        self._batch_tasks = {}
        if not isinstance(moves, (list, tuple)):
            raise ValueError("Calendar batch must be a list of ready operations.")
        batch, tasks = {}, {}
        for move in moves:
            if not isinstance(move, dict) or set(move) != {"task_id", "remote_id", "version", "desired"}:
                raise ValueError("Calendar batch contains an invalid operation.")
            task_id, remote_id = move["task_id"], move["remote_id"]
            if not isinstance(task_id, str) or not task_id or task_id in tasks:
                raise ValueError("Calendar batch needs unique stable task IDs.")
            if remote_id is not None and (not isinstance(remote_id, str) or not remote_id or remote_id in batch):
                raise ValueError("Calendar batch needs unique linked event IDs.")
            if (remote_id is None) != (move["version"] is None):
                raise ValueError("Calendar batch links need a confirmed remote version.")
            desired = move["desired"]
            if (not isinstance(desired, dict) or set(desired) != self.fields or
                    not isinstance(desired["title"], str) or not desired["title"].strip()):
                raise ValueError("Calendar batch needs complete title/schedule projections.")
            desired = {"title": desired["title"], "schedule": normalise_schedule(desired["schedule"])}
            entry = {**move, "desired": desired}
            tasks[task_id] = entry
            if remote_id is not None:
                batch[remote_id] = entry
        scheduled = [entry["desired"]["schedule"] for entry in tasks.values() if entry["desired"]["schedule"]]
        for index, left in enumerate(scheduled):
            if any(self._overlap(left, right) for right in scheduled[index + 1:]):
                raise ValueError("Prepared calendar destinations must not overlap.")
        self._batch, self._batch_tasks = batch, tasks

    @staticmethod
    def _overlap(left, right):
        return max(datetime.fromisoformat(left["start"]), datetime.fromisoformat(right["start"])) < min(
            datetime.fromisoformat(left["end"]), datetime.fromisoformat(right["end"]))

    def _vacates_requested_slot(self, busy, requested):
        entry = self._batch.get(busy.get("id"))
        if entry is None or busy.get("calendar_id", self.client.calendar_id) != self.client.calendar_id:
            return False
        destination = entry["desired"]["schedule"]
        if destination is not None and self._overlap(requested, destination):
            return False
        event = self.client.get_event(entry["remote_id"])
        if event is None:
            return False  # No ownership proof for a stale busy entry.
        current = self._event(event, entry["task_id"], entry["remote_id"])
        # A fresh scoped lookup also detects a copied marker or a replacement
        # event; neither authorises ignoring this occupied interval.
        unique = self.read(entry["task_id"])
        if unique is None or unique["id"] != current["id"] or unique["version"] != current["version"]:
            raise RemoteConflict("A calendar batch participant changed; reconcile the batch again.")
        if current["version"] != entry["version"] and current["fields"] != entry["desired"]:
            raise RemoteConflict("A calendar batch participant changed; reconcile the batch again.")
        return True

    def _event(self, event, task_id, expected_id=None):
        if not isinstance(event, dict):
            raise ValueError("Calendar returned an invalid event.")
        if not isinstance(event.get("id"), str) or not event["id"]:
            raise ValueError("Calendar event has no stable ID.")
        if expected_id is not None and event["id"] != expected_id:
            raise ValueError("Calendar returned a different event ID.")
        if event.get("task_id") != task_id:
            raise ValueError("Calendar event belongs to another task.")
        if event.get("calendar_id", self.client.calendar_id) != self.client.calendar_id:
            raise ValueError("Calendar event is outside the selected calendar.")
        if any(type(event.get(key)) is not bool for key in ("deleted", "recurring", "has_attendees")):
            raise ValueError("Calendar client must supply deletion, recurrence and attendee flags.")
        if event["recurring"] or event["has_attendees"]:
            raise RemoteConflict("Linked calendar item became a meeting or recurring event; resolve it before syncing.")
        if "version" not in event or (not event["deleted"] and event["version"] is None):
            raise ValueError("Calendar client must supply a conditional-write version.")
        if not isinstance(event.get("title"), str) or (not event["deleted"] and not event["title"].strip()):
            raise ValueError("Calendar event must have a title.")
        schedule = None if event["deleted"] else normalise_schedule(event.get("schedule"))
        if not event["deleted"] and schedule is None:
            raise ValueError("An active calendar event must have a timed schedule.")
        return {"id": event["id"], "version": event["version"], "deleted": event["deleted"],
                "fields": {"title": event["title"], "schedule": schedule}}

    def read(self, task_id, remote_id=None):
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("A stable task ID is required.")
        if remote_id:
            event = self.client.get_event(remote_id)
            return None if event is None else self._event(event, task_id, remote_id)
        events = self.client.find_task_events(task_id)
        if not isinstance(events, (list, tuple)):
            raise ValueError("Calendar lookup must return the complete matching event list.")
        snapshots = [self._event(event, task_id) for event in events]
        active = [snapshot for snapshot in snapshots if not snapshot["deleted"]]
        if len(active) > 1:
            raise RemoteConflict("Multiple calendar events use this task ID; resolve duplicates before syncing.")
        if active:
            return active[0]
        # Old tombstones may remain after a task is deliberately rescheduled.
        # With no active event, any tombstone represents an absent focus block.
        return snapshots[-1] if snapshots else None

    def _check_availability(self, schedule, current_id, allow_batch=False):
        busy = self.client.busy(schedule["start"], schedule["end"])
        if not isinstance(busy, (list, tuple)):
            raise ValueError("Calendar availability must be a complete list of busy intervals.")
        start = datetime.fromisoformat(schedule["start"])
        end = datetime.fromisoformat(schedule["end"])
        for item in busy:
            if not isinstance(item, dict):
                raise ValueError("Calendar returned an invalid busy interval.")
            if (current_id is not None and item.get("id") == current_id and
                    item.get("calendar_id", self.client.calendar_id) == self.client.calendar_id):
                continue
            try:
                other_start = datetime.fromisoformat(item["start"].replace("Z", "+00:00"))
                other_end = datetime.fromisoformat(item["end"].replace("Z", "+00:00"))
                if other_start.utcoffset() is None or other_end.utcoffset() is None or other_end <= other_start:
                    raise ValueError()
            except (KeyError, TypeError, AttributeError, ValueError):
                raise ValueError("Busy intervals need valid start/end timestamps with UTC offsets.") from None
            if max(start, other_start) < min(end, other_end):
                if allow_batch and self._vacates_requested_slot(item, schedule):
                    continue
                raise RemoteConflict("The requested time overlaps an existing calendar commitment.")

    def _mutate(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (AmbiguousWrite, RemoteConflict):
            raise
        except OSError:
            raise AmbiguousWrite("Calendar write outcome is unknown; reconcile before retrying.") from None

    def write(self, task_id, remote_id, fields, expected_version, operation_id):
        try:
            return self._write(task_id, remote_id, fields, expected_version, operation_id)
        except Exception:
            # A failed or uncertain participant cannot promise to vacate a slot
            # for later writes in this poll.
            self._batch, self._batch_tasks = {}, {}
            raise

    def _write(self, task_id, remote_id, fields, expected_version, operation_id):
        if not isinstance(fields, dict) or set(fields) != self.fields:
            raise ValueError("Write the complete calendar title/schedule projection.")
        if not isinstance(fields["title"], str) or not fields["title"].strip():
            raise ValueError("A task title is required.")
        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError("A durable operation ID is required.")
        desired = {"title": fields["title"], "schedule": normalise_schedule(fields["schedule"])}
        current = self.read(task_id, remote_id)
        if current and not current["deleted"] and current["fields"] == desired:
            return current  # Already satisfied, without another write.
        if desired["schedule"] is None and current and current["deleted"]:
            return {**current, "fields": desired}
        active = current is not None and not current["deleted"]
        if active:
            if current["version"] != expected_version:
                raise RemoteConflict("Calendar event changed; reconcile before writing.")
            if getattr(self.client, "supports_atomic_updates", False) is not True:
                raise RuntimeError("Calendar client must support atomic conditional updates and deletes.")
        elif remote_id is not None or expected_version is not None:
            raise RemoteConflict("Calendar event was removed; reconcile before writing.")
        elif desired["schedule"] is None:
            raise RemoteConflict("No calendar event exists to remove; reconcile the missing event.")
        elif getattr(self.client, "supports_idempotent_create", False) is not True:
            raise RuntimeError("Calendar client must support idempotent event creation.")

        if desired["schedule"] is not None:
            approved = self._batch_tasks.get(task_id)
            allow_batch = bool(approved and approved["desired"] == desired and
                               approved["remote_id"] == remote_id and approved["version"] == expected_version)
            self._check_availability(desired["schedule"], current["id"] if active else None, allow_batch)
        # The provider's conditional write still protects edits made after these
        # reads. It must check recurrence/attendee changes as part of its version.
        payload = {"task_id": task_id, **desired}
        if active and desired["schedule"] is None:
            response = self._mutate(self.client.delete_event, current["id"],
                                    expected_version=expected_version, idempotency_key=operation_id)
        elif active:
            response = self._mutate(self.client.update_event, current["id"], payload,
                                    expected_version=expected_version, idempotency_key=operation_id)
        else:
            response = self._mutate(self.client.create_event, payload, idempotency_key=operation_id)
        try:
            snapshot = self._event(response, task_id, current["id"] if active else None)
        except (ValueError, KeyError, TypeError):
            raise AmbiguousWrite("Calendar write receipt could not be verified; reconcile before retrying.") from None
        if desired["schedule"] is None:
            if not snapshot["deleted"]:
                raise AmbiguousWrite("Calendar did not confirm deletion; reconcile before retrying.")
            return {**snapshot, "fields": desired}
        if snapshot["deleted"] or snapshot["fields"] != desired:
            raise RemoteConflict("Calendar changed during the update; read and reconcile again.")
        return snapshot
