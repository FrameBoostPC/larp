"""Persistent task reconciliation shared by the planner, Notion and calendar.

Adapters read/write only records carrying this task's stable identity. No network
credentials, polling daemon or default account is selected by this component.
Run one Engine per user workspace; use a durable private SQLite path.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
import sqlite3
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class RevisionConflict(ValueError):
    pass


class RequestConflict(ValueError):
    pass


class RemoteConflict(RuntimeError):
    pass


class AmbiguousWrite(RuntimeError):
    """The provider may have accepted a non-idempotent write; reconcile first."""


FIELDS = frozenset({"project_id", "title", "status", "estimated_minutes",
                    "deliverable", "depends_on", "week", "due_date", "schedule"})
EDITABLE = FIELDS - {"project_id"}
ACTIVE = {"planned", "in_progress"}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def normalise_schedule(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"start", "end", "timezone"}:
        raise ValueError("schedule needs start, end and an IANA timezone")
    try:
        zone = ZoneInfo(value["timezone"])
        instants = [datetime.fromisoformat(value[k].replace("Z", "+00:00")) for k in ("start", "end")]
    except (TypeError, KeyError, ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("Invalid schedule date/time or timezone; install tzdata on Windows") from exc
    for instant in instants:
        if instant.tzinfo is None or instant.utcoffset() != instant.astimezone(zone).utcoffset():
            raise ValueError("Schedule must include the correct UTC offset for its timezone")
    if instants[1] <= instants[0]:
        raise ValueError("Schedule end must be after start")
    return {"start": instants[0].isoformat(), "end": instants[1].isoformat(), "timezone": value["timezone"]}


class Engine:
    def __init__(self, db_path, adapters=(), clock=None):
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.adapters = {adapter.name: adapter for adapter in adapters}
        if len(self.adapters) != len(adapters):
            raise ValueError("Adapter names must be unique")
        for adapter in adapters:
            if not set(adapter.fields) <= FIELDS:
                raise ValueError("Adapter has unknown fields")
        # Parent directories are deliberately the host's responsibility.
        self.db = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, task_key TEXT NOT NULL,
                revision INTEGER NOT NULL, payload TEXT NOT NULL,
                UNIQUE(project_id, task_key));
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, result TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS links (
                task_id TEXT NOT NULL REFERENCES tasks(id), surface TEXT NOT NULL,
                remote_id TEXT, version TEXT, shadow TEXT NOT NULL, deleted INTEGER NOT NULL,
                PRIMARY KEY(task_id, surface));
            CREATE TABLE IF NOT EXISTS outbox (
                task_id TEXT NOT NULL REFERENCES tasks(id), surface TEXT NOT NULL,
                operation_id TEXT NOT NULL, desired TEXT NOT NULL, state TEXT NOT NULL,
                PRIMARY KEY(task_id, surface));
            CREATE TABLE IF NOT EXISTS conflicts (
                task_id TEXT PRIMARY KEY REFERENCES tasks(id), details TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS history (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                revision INTEGER NOT NULL, source TEXT NOT NULL, changed_at TEXT NOT NULL,
                payload TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    @contextmanager
    def _transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _request(self, request_id, intent, action):
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("A stable request_id is required")
        fingerprint = hashlib.sha256(encode(intent).encode()).hexdigest()
        with self._transaction():
            previous = self.db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
            if previous:
                if previous["fingerprint"] != fingerprint:
                    raise RequestConflict("request_id already belongs to a different change")
                return json.loads(previous["result"])
            result = action()
            self.db.execute("INSERT INTO requests VALUES (?,?,?)", (request_id, fingerprint, encode(result)))
            return result

    def get_task(self, task_id):
        row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        return {"id": row["id"], "revision": row["revision"], **json.loads(row["payload"])}

    def list_tasks(self, project_id=None):
        rows = self.db.execute("SELECT id FROM tasks WHERE (? IS NULL OR project_id=?) ORDER BY rowid", (project_id, project_id))
        return [self.get_task(row["id"]) for row in rows]

    def conflicts(self, task_id):
        row = self.db.execute("SELECT details FROM conflicts WHERE task_id=?", (task_id,)).fetchone()
        return json.loads(row[0]) if row else []

    def history(self, task_id):
        return [dict(row) for row in self.db.execute("SELECT * FROM history WHERE task_id=? ORDER BY sequence", (task_id,))]

    def _payload(self, task):
        return {key: task[key] for key in FIELDS}

    def _validate(self, fields):
        if set(fields) != FIELDS:
            raise ValueError("Unknown or missing task fields")
        for key in ("title", "project_id"):
            if not isinstance(fields[key], str) or not fields[key].strip():
                raise ValueError(f"{key} must be nonempty text")
        if not isinstance(fields["deliverable"], str):
            raise ValueError("deliverable must be text")
        if fields["status"] not in ACTIVE | {"completed", "cancelled"}:
            raise ValueError("Unknown task status")
        for key in ("estimated_minutes", "week"):
            if type(fields[key]) is not int or fields[key] < 1:
                raise ValueError(f"{key} must be a positive integer")
        if fields["due_date"] is not None:
            if not isinstance(fields["due_date"], str) or date.fromisoformat(fields["due_date"]).isoformat() != fields["due_date"]:
                raise ValueError("due_date must be YYYY-MM-DD or null")
        if not isinstance(fields["depends_on"], list) or any(not isinstance(x, str) or not x for x in fields["depends_on"]):
            raise ValueError("depends_on must contain task IDs")
        if len(set(fields["depends_on"])) != len(fields["depends_on"]):
            raise ValueError("Repeated dependency")
        fields["schedule"] = normalise_schedule(fields["schedule"])
        if fields["status"] not in ACTIVE and fields["schedule"]:
            if datetime.fromisoformat(fields["schedule"]["end"]) > self.clock():
                fields["schedule"] = None
        return fields

    def _validate_graph(self):
        tasks = {task["id"]: task for task in self.list_tasks()}
        visiting, done = set(), set()

        def visit(task_id):
            if task_id in visiting:
                raise ValueError("Task dependency cycle")
            if task_id in done:
                return
            visiting.add(task_id)
            task = tasks[task_id]
            for predecessor_id in task["depends_on"]:
                if predecessor_id not in tasks or tasks[predecessor_id]["project_id"] != task["project_id"]:
                    raise ValueError("Unknown dependency or dependency outside project")
                predecessor = tasks[predecessor_id]
                if predecessor["week"] > task["week"]:
                    raise ValueError("Dependency belongs to a later week")
                visit(predecessor_id)
                if task["status"] in ACTIVE and task["schedule"] and predecessor["status"] != "completed":
                    if predecessor["status"] == "cancelled" or not predecessor["schedule"]:
                        raise ValueError("Schedule predecessor first or resolve the blocked dependency")
                    if datetime.fromisoformat(predecessor["schedule"]["end"]) > datetime.fromisoformat(task["schedule"]["start"]):
                        raise ValueError("Scheduled dependency must finish before dependent task")
            visiting.remove(task_id)
            done.add(task_id)

        for task_id in tasks:
            visit(task_id)
        scheduled = [task for task in tasks.values() if task["status"] in ACTIVE and task["schedule"]]
        for index, task in enumerate(scheduled):
            slot = task["schedule"]
            for other in scheduled[index + 1:]:
                other_slot = other["schedule"]
                if max(datetime.fromisoformat(slot["start"]), datetime.fromisoformat(other_slot["start"])) < min(datetime.fromisoformat(slot["end"]), datetime.fromisoformat(other_slot["end"])):
                    raise ValueError("Scheduled tasks overlap")

    def _save(self, task_id, fields, source):
        old = self.get_task(task_id)
        if old["status"] not in ACTIVE and fields["status"] in ACTIVE and fields["schedule"] == old["schedule"]:
            fields["schedule"] = None  # Reopening needs a deliberately chosen new block.
        if self._payload(old) == fields:
            return old
        revision = old["revision"] + 1
        self.db.execute("UPDATE tasks SET revision=?,payload=? WHERE id=?", (revision, encode(fields), task_id))
        self.db.execute("INSERT INTO history(task_id,revision,source,changed_at,payload) VALUES (?,?,?,?,?)", (task_id, revision, source, self.clock().isoformat(), encode(fields)))
        return self.get_task(task_id)

    def _create(self, project_id, task_key, fields):
        if not isinstance(task_key, str) or not task_key.strip():
            raise ValueError("task_key must be stable nonempty text")
        task_id = str(uuid.uuid5(uuid.NAMESPACE_URL, encode([project_id, task_key])))
        existing = self.db.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone()
        if existing:
            return self.get_task(task_id)
        if set(fields) - EDITABLE:
            raise ValueError("Unknown or immutable create field")
        payload = self._validate({"project_id": project_id, "title": "", "status": "planned",
                                  "estimated_minutes": 30, "deliverable": "", "depends_on": [],
                                  "week": 1, "due_date": None, "schedule": None, **fields})
        self.db.execute("INSERT INTO tasks VALUES (?,?,?,?,?)", (task_id, project_id, task_key, 1, encode(payload)))
        self.db.execute("INSERT INTO history(task_id,revision,source,changed_at,payload) VALUES (?,?,?,?,?)", (task_id, 1, "create", self.clock().isoformat(), encode(payload)))
        return self.get_task(task_id)

    def create_task(self, project_id, task_key, fields, request_id):
        def action():
            task = self._create(project_id, task_key, fields)
            self._validate_graph()
            return task
        return self._request(request_id, ["create", project_id, task_key, fields], action)

    def _edit(self, task_id, patch, expected_revision, source="edit"):
        old = self.get_task(task_id)
        if type(expected_revision) is not int or expected_revision != old["revision"]:
            raise RevisionConflict("Task changed; refresh its revision before editing")
        if not isinstance(patch, dict) or not patch or set(patch) - EDITABLE:
            raise ValueError("Patch must name editable task fields explicitly")
        if self.conflicts(task_id) and source != "resolve":
            raise RevisionConflict("Resolve this task's sync conflicts before editing")
        fields = self._validate({**self._payload(old), **patch})
        return self._save(task_id, fields, source)

    def edit_task(self, task_id, patch, expected_revision, request_id):
        def action():
            task = self._edit(task_id, patch, expected_revision)
            self._validate_graph()
            return task
        return self._request(request_id, ["edit", task_id, patch, expected_revision], action)

    def resolve_conflict(self, task_id, patch, expected_revision, request_id):
        def action():
            outstanding = self.conflicts(task_id)
            if not outstanding or any(item["field"] not in patch for item in outstanding):
                raise ValueError("Supply explicit values for every conflicting field")
            old = self.get_task(task_id)
            if type(expected_revision) is not int or expected_revision != old["revision"]:
                raise RevisionConflict("Task changed; refresh its revision before resolving")
            if not isinstance(patch, dict) or set(patch) - FIELDS:
                raise ValueError("Unknown resolution fields")
            if patch.get("project_id", old["project_id"]) != old["project_id"]:
                raise ValueError("Project ownership cannot be changed by sync")
            task = self._save(task_id, self._validate({**self._payload(old), **patch}), "resolve")
            self._validate_graph()
            self.db.execute("DELETE FROM conflicts WHERE task_id=?", (task_id,))
            return task
        return self._request(request_id, ["resolve", task_id, patch, expected_revision], action)

    def apply_operations(self, operations, request_id, project_id=None):
        def action():
            if not isinstance(operations, list):
                raise ValueError("operations must be an array")
            seen = set()
            for operation in operations:
                task_id = operation["task_id"]
                if project_id is not None and self.get_task(task_id)["project_id"] != project_id:
                    raise ValueError("Task belongs to a different project")
                if task_id in seen:
                    raise ValueError("Combine edits into one operation per task")
                seen.add(task_id)
                kind, patch = operation["action"], operation["patch"]
                if kind == "schedule" and (set(patch) != {"schedule"} or patch["schedule"] is None):
                    raise ValueError("schedule action requires one complete schedule")
                if kind == "unschedule" and patch != {"schedule": None}:
                    raise ValueError("unschedule action requires schedule:null")
                if kind not in {"schedule", "unschedule", "update_task"}:
                    raise ValueError("Unknown operation")
                self._edit(task_id, patch, operation["expected_revision"])
            self._validate_graph()
            return [self.get_task(operation["task_id"]) for operation in operations]
        return self._request(request_id, ["operations", operations, project_id], action)

    def import_plan(self, project_id, plan, request_id):
        """Import a validated planner result once; omission never deletes a task.

        Existing task keys preserve live fields. Subsequent intentional changes
        use revision-checked patches, not a replacement model-generated plan.
        """
        data = plan.get("data", plan)
        if not isinstance(data, dict):
            raise ValueError("No actionable plan")

        def action():
            tasks = data["tasks"]
            keys = [task["id"] for task in tasks]
            if len(keys) != len(set(keys)):
                raise ValueError("Duplicate planner task ID")
            ids = {}
            existing_ids = set()
            for key in keys:
                existing = self.db.execute("SELECT project_id FROM tasks WHERE id=?", (key,)).fetchone()
                if existing:
                    if existing["project_id"] != project_id:
                        raise ValueError("Existing task belongs to another project")
                    ids[key] = key
                    existing_ids.add(key)
                else:
                    ids[key] = str(uuid.uuid5(uuid.NAMESPACE_URL, encode([project_id, key])))
            for task in tasks:
                if any(key not in ids for key in task["depends_on"]):
                    raise ValueError("Unknown planner dependency")
                if task["id"] in existing_ids:
                    continue
                self._create(project_id, task["id"], {
                    "title": task["title"], "deliverable": task["deliverable"],
                    "estimated_minutes": task["estimated_minutes"], "week": task["week"],
                    "depends_on": [ids[key] for key in task["depends_on"]],
                })
            self._validate_graph()
            return [self.get_task(ids[key]) for key in keys]
        return self._request(request_id, ["import", project_id, data], action)

    def _link(self, task_id, surface):
        row = self.db.execute("SELECT * FROM links WHERE task_id=? AND surface=?", (task_id, surface)).fetchone()
        if row is None:
            return None
        return {**dict(row), "shadow": json.loads(row["shadow"]), "version": json.loads(row["version"])}

    def _snapshot(self, adapter, snapshot):
        if snapshot is None:
            return None
        if not snapshot.get("id") or "version" not in snapshot or "deleted" not in snapshot:
            raise ValueError("Malformed remote snapshot")
        fields = snapshot["fields"]
        if set(fields) != set(adapter.fields):
            raise ValueError("Remote snapshot does not match adapter field projection")
        if "schedule" in fields:
            fields = {**fields, "schedule": normalise_schedule(fields["schedule"])}
        return {**snapshot, "fields": fields}

    def _remember(self, task_id, surface, snapshot, fields):
        self.db.execute("INSERT OR REPLACE INTO links VALUES (?,?,?,?,?,?)", (task_id, surface, snapshot["id"], encode(snapshot["version"]), encode(fields), int(snapshot["deleted"])))

    def _reconcile(self, task_id, validate_graph=True):
        if self.conflicts(task_id):
            return "conflicts"
        task = self.get_task(task_id)
        local = self._payload(task)
        observations = []
        # Finish every read before accepting any inbound change or queuing writes.
        for name, adapter in self.adapters.items():
            link = self._link(task_id, name)
            snapshot = self._snapshot(adapter, adapter.read(task_id, link["remote_id"] if link else None))
            if snapshot is None and link:
                # Adapters must raise for permission/transport failure, never
                # translate those failures into absence.
                snapshot = {"id": link["remote_id"], "version": None, "deleted": True, "fields": link["shadow"]}
            projection = {key: local[key] for key in adapter.fields}
            remote = snapshot["fields"].copy() if snapshot else projection.copy()
            if snapshot and snapshot["deleted"]:
                remote = (link["shadow"] if link else projection).copy()
                if name == "calendar":
                    remote["schedule"] = None
                elif name == "notion":
                    remote["status"] = "cancelled"
                    remote["schedule"] = None
            pending = self.db.execute("SELECT * FROM outbox WHERE task_id=? AND surface=?", (task_id, name)).fetchone()
            if pending and pending["state"] == "ambiguous":
                pending_fields = json.loads(pending["desired"])
                confirmed_delete = name == "calendar" and snapshot and snapshot["deleted"] and pending_fields.get("schedule") is None
                if confirmed_delete or (snapshot and not snapshot["deleted"] and snapshot["fields"] == pending_fields):
                    self.db.execute("DELETE FROM outbox WHERE task_id=? AND surface=?", (task_id, name))
                else:
                    raise AmbiguousWrite(f"{name}: reconcile the uncertain write before retrying")
            observations.append((name, adapter, link, snapshot, remote))

        changes = {}
        conflicts = []
        for field in FIELDS:
            changed = []
            local_changed = False
            for name, adapter, link, snapshot, remote in observations:
                if field not in adapter.fields or snapshot is None:
                    continue
                baseline = link["shadow"][field] if link else local[field]
                if remote[field] != baseline:
                    changed.append((name, remote[field]))
                    local_changed |= local[field] != baseline
                    if link is None:
                        local_changed = True  # Never adopt an unknown pre-existing record silently.
            choices = {encode(value) for _, value in changed}
            if changed and (len(choices) > 1 or (local_changed and changed[0][1] != local[field]) or field == "project_id"):
                conflicts.append({"field": field, "local": local[field], "remote": dict(changed)})
            elif changed:
                changes[field] = changed[0][1]

        # Store what was actually read. Conflicts remain a barrier until an
        # explicit resolution; these baselines never silently accept a winner.
        for name, adapter, link, snapshot, remote in observations:
            if snapshot:
                self._remember(task_id, name, snapshot, remote)
        # Preserve compatible edits even when another field conflicts. Otherwise
        # acknowledging remote baselines here would lose those independent edits.
        proposed = self._validate({**local, **changes})
        self._save(task_id, proposed, "sync")
        if validate_graph:
            self._validate_graph()
        if conflicts:
            self.db.execute("INSERT OR REPLACE INTO conflicts VALUES (?,?)", (task_id, encode(conflicts)))
            return "conflicts"
        for name, adapter, link, snapshot, remote in observations:
            desired = {key: proposed[key] for key in adapter.fields}
            absent_calendar = name == "calendar" and (snapshot is None or snapshot["deleted"]) and desired["schedule"] is None
            archived_notion = name == "notion" and snapshot and snapshot["deleted"] and proposed["status"] == "cancelled"
            if absent_calendar or archived_notion or (snapshot and not snapshot["deleted"] and desired == snapshot["fields"]):
                self.db.execute("DELETE FROM outbox WHERE task_id=? AND surface=?", (task_id, name))
                continue
            previous = self.db.execute("SELECT * FROM outbox WHERE task_id=? AND surface=?", (task_id, name)).fetchone()
            if not previous or previous["desired"] != encode(desired):
                self.db.execute("INSERT OR REPLACE INTO outbox VALUES (?,?,?,?,?)", (task_id, name, str(uuid.uuid4()), encode(desired), "pending"))
        return "ready"

    def sync(self):
        """One bounded poll. Host repeats it or triggers it after webhooks/edits.

        Queue commits precede writes. The same operation ID survives retry and
        restart. Adapters must perform a last-minute revision check before write.
        """
        report = {"synced": [], "conflicts": [], "errors": []}
        ready = []
        tasks = self.list_tasks()
        try:
            with self._transaction():
                for task in tasks:
                    task_id = task["id"]
                    self.db.execute("SAVEPOINT inbound_task")
                    try:
                        outcome = self._reconcile(task_id, validate_graph=False)
                        if outcome == "conflicts":
                            report["conflicts"].append(task_id)
                        else:
                            ready.append(task_id)
                    except Exception as exc:
                        self.db.execute("ROLLBACK TO inbound_task")
                        report["errors"].append({"task_id": task_id, "error": str(exc)})
                    finally:
                        self.db.execute("RELEASE inbound_task")
                # Read the complete incoming schedule before validating it;
                # otherwise two legitimate remotely swapped blocks deadlock.
                self._validate_graph()
        except Exception as exc:
            report["conflicts"] = [task["id"] for task in tasks if self.conflicts(task["id"])]
            report["errors"].append({"error": f"Incoming batch rejected; no writes sent: {exc}"})
            return report
        blocked_surfaces = set()
        for name, adapter in self.adapters.items():
            if not hasattr(adapter, "prepare_batch"):
                continue
            moves = []
            for task_id in ready:
                queued = self.db.execute("SELECT * FROM outbox WHERE task_id=? AND surface=? AND state='pending'", (task_id, name)).fetchone()
                if not queued:
                    continue
                desired = json.loads(queued["desired"])
                if desired != {key: self.get_task(task_id)[key] for key in adapter.fields}:
                    continue
                link = self._link(task_id, name)
                moves.append({"task_id": task_id, "remote_id": link["remote_id"] if link and not link["deleted"] else None,
                              "version": link["version"] if link and not link["deleted"] else None, "desired": desired})
            try:
                adapter.prepare_batch(moves)
            except Exception as exc:
                blocked_surfaces.add(name)
                report["errors"].append({"surface": name, "error": str(exc)})
        for task_id in ready:
            pending = self.db.execute("SELECT surface FROM outbox WHERE task_id=?", (task_id,)).fetchall()
            for entry in pending:
                name = entry["surface"]
                if name not in self.adapters or name in blocked_surfaces:
                    continue
                try:
                    # Serialise local edits/workers during the final CAS write.
                    # An interrupted transaction leaves the committed queue key.
                    with self._transaction():
                        queued = self.db.execute("SELECT * FROM outbox WHERE task_id=? AND surface=?", (task_id, name)).fetchone()
                        if queued is None or queued["state"] == "ambiguous" or self.conflicts(task_id):
                            continue
                        adapter, link = self.adapters[name], self._link(task_id, name)
                        desired = json.loads(queued["desired"])
                        current = {key: self.get_task(task_id)[key] for key in adapter.fields}
                        if current != desired:
                            raise RevisionConflict("Task changed after reconciliation; poll again before writing")
                        result = self._snapshot(adapter, adapter.write(
                            task_id, link["remote_id"] if link and not link["deleted"] else None,
                            desired, link["version"] if link and not link["deleted"] else None,
                            queued["operation_id"]))
                        if result is None:
                            raise AmbiguousWrite("Provider returned no write receipt")
                        deletion = name == "calendar" and desired["schedule"] is None and result["deleted"]
                        if not deletion and (result["deleted"] or result["fields"] != desired):
                            raise AmbiguousWrite("Provider did not confirm the requested fields")
                        self._remember(task_id, name, result, desired)
                        self.db.execute("DELETE FROM outbox WHERE task_id=? AND surface=?", (task_id, name))
                    report["synced"].append({"task_id": task_id, "surface": name})
                except AmbiguousWrite as exc:
                    self._clear_batches()
                    with self._transaction():
                        self.db.execute("UPDATE outbox SET state='ambiguous' WHERE task_id=? AND surface=?", (task_id, name))
                    report["errors"].append({"task_id": task_id, "surface": name, "error": str(exc)})
                    break
                except Exception as exc:
                    self._clear_batches()
                    report["errors"].append({"task_id": task_id, "surface": name, "error": str(exc)})
                    break
        return report

    def _clear_batches(self):
        # A participant that failed on any surface can no longer promise to
        # vacate a calendar interval in this poll.
        for adapter in self.adapters.values():
            if hasattr(adapter, "prepare_batch"):
                adapter.prepare_batch([])
