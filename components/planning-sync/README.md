# Optional Python planner and calendar sync prototype

This portable Python prototype connects proposed project tasks and calendar edits
to one persistent task record when imported by a separately configured host.
Installing either skill alone does not start a sync service.

## Existing n8n integration

The current integration belongs to **Planning & Calendar | 01 - Project Planner**
and **Planning & Calendar | 02 - Calendar & Task Manager** in n8n. The scheduling workflow
already uses **Notion account 2** and the **Schedule & Tasks** data source.
Notion Calendar displays those same database pages, so task and calendar changes
refer to one saved item. No separate Google Calendar or Outlook provider client
is needed for this setup.

Both connected n8n workflows were live-tested and published on 2026-09-15.
See the [integration guide](../../docs/integration.md) for the workflow
contract and [validation notes](../../docs/validation.md) for results and publication
status.

`n8n-format-result.js` is the deployed planner's `Format result` Code-node
source (JavaScript, run once for each item). It is separate from the Python
prototype below. Broad target weeks remain proposals: without an explicit
deadline, `due_date` stays null. The existing deadline validation, task identity,
replay and detailed time recommendations are preserved. Test the exact source
with `node components/planning-sync/n8n-format-result.test.mjs`. This narrow
node snapshot does not constitute a complete workflow export or installer.

The Python component below is an optional separate implementation. The existing
database uses `Name`, `When`, `Type`, `Status` (select), `Blocks time`, `Notes`,
`Reference` and `Colour`. Its single `When` property holds either a task deadline
or a scheduled interval. The Python adapter expects the different schema documented
below, including separate deadline and scheduled-time properties.
**Do not run this Python adapter against Schedule & Tasks without an explicit
migration and compatible configuration.** The lifecycle, host setup and service
requirements in the remaining sections apply to this Python prototype.

## Implementation and connection status

- `planning_sync.py`: SQLite task state, request replay protection, revision checks,
  three-way field reconciliation, write queue, conflict resolution and history.
- `notion_adapter.py`: HTTP integration for one explicitly configured Notion data
  source. It reads and updates managed task pages and creates missing pages.
- `calendar_adapter.py`: scheduling and event-lifecycle bridge to a host calendar
  client. The client supplies the selected provider's API, authentication,
  conditional writes, idempotency and availability queries.
- `cli.py`: planner import, calendar operation application, status, conflict
  resolution and one sync poll.

This Python prototype has no deployed sync service or live-account configuration
in this repository. A standalone deployment would require compatible Notion
configuration and, if its calendar bridge is used, a provider client supplied by
the host. Its tests use simulated services and do not establish a live deployment.
These requirements are separate from the existing n8n/Notion connection above.

## Shared task lifecycle

1. Validate a Project Planner result, then call
   `engine.import_plan(project_id, result, request_id)`. Keep the project ID stable.
   Planner task IDs are namespaced within that project and mapped to persistent
   UUIDs. Save those UUIDs with the dashboard cards and send them back on revisions.
2. Read `engine.list_tasks()` for both workflows. A weekly review uses real progress,
   blockers and scheduled time from these records, and checks available capacity.
3. Send deliberate changes through `edit_task` or `apply_operations` with the
   current `expected_revision` and a stable `request_id`. The entire operation
   batch is accepted atomically. Do not feed stale model output in as replacement state.
4. Call `engine.sync()` after accepted edits and on each host poll or webhook.
   All connected surfaces are read before a task's pending writes are prepared.
5. Refresh both dashboard views from the same stored result and sync report.
   Only a successful provider receipt confirms an external write. A local save
   alone means the change is pending external sync.

Importing a plan creates missing tasks; it preserves existing task fields,
completion and schedule. Omitted tasks remain present. Reusing a request ID with
different input is rejected. For a new project, use a new project ID even when the
model uses familiar task keys such as `t1`.

| Change | Result |
| --- | --- |
| Create a planner task | Create one managed Notion task; calendar waits for a timed schedule |
| Edit title in either surface | Update the same task and its linked event |
| Move/resize a calendar block | Update the task's scheduled interval and Notion scheduled time |
| Change due date | Update the task deadline; no time block is invented |
| Unschedule/delete a calendar block | Clear scheduled time; keep the task and its progress |
| Mark task completed or cancelled | Remove its active/future focus block; preserve past history |
| Calendar event ends | Leave task completion unchanged |
| Archive the managed Notion page | Mark task cancelled and remove its active/future focus block |
| New unlinked personal calendar event | Use it as busy time; do not import it as a task |
| Different fields edited concurrently | Merge compatible changes |
| Same field edited differently | Block writes for that task and expose both values |

`due_date` is a date-only deadline. `schedule` is a separate nullable object with
`start`, `end` (offset-bearing ISO timestamps) and `timezone` (IANA zone). Times are
validated against that zone, including daylight-saving transitions. Moving a block
does not rewrite its effort estimate or deadline. Scheduling rejects overlaps among
active stored tasks and requires unfinished dependencies to have earlier slots.
The calendar bridge additionally checks current external busy time before writing.
External scheduling cannot be an atomic reservation across multiple calendars;
the host must reconcile subsequent conflicts rather than claim a guarantee.
Moves of several managed focus blocks are coordinated from the same validated
batch, including swaps. Each availability exemption rechecks the other event's
ownership/version and confirms its intended destination vacates the interval.
Provider writes are serial: a partial failure may temporarily leave overlapping
managed blocks while remaining operations wait for reconciliation. A failed
participant invalidates the poll's remaining move exemptions. Genuine external
busy events are never exempted.

## Notion database properties

For a standalone Python deployment, use a dedicated data source or explicitly map
these keys to compatible properties after approving any required migration.
The existing Schedule & Tasks schema is not directly compatible. This component
does not silently change a database schema. Share the selected compatible data
source with the host's Notion integration.

| Example property | Type | Purpose |
| --- | --- | --- |
| Name | Title | Task title |
| Sync ID | Rich text | Stable task UUID; do not manually edit |
| Project ID | Rich text | Stable project ownership |
| Status | Status | `planned`, `in_progress`, `completed`, `cancelled` |
| Estimated minutes | Number | Positive effort estimate |
| Deliverable | Rich text | Observable completion result |
| Depends on IDs | Rich text | JSON array of persistent task UUIDs |
| Week | Number | Relative planning week, starting at 1 |
| Due date | Date | Date-only deadline |
| Scheduled time | Date range | Start and end of the current focus block |
| Timezone | Rich text | IANA zone for the scheduled block |
| Sync operation | Rich text | Last write operation marker; do not manually edit |

The adapter accepts an explicit `status_names` mapping when existing Notion status
labels differ. Page properties outside the mapping are preserved. Duplicate Sync IDs,
missing required values and access errors block the affected task instead of being
treated as deletion. New tasks should enter through the planner or host create action;
arbitrary manually created unlinked Notion pages are not imported automatically.
The CLI accepts the same optional `notion.status_names` mapping in private config.

## Host setup

Requires Python 3.10+ and the component's `requirements.txt`. The CLI also uses the
repository's `requirements-dev.txt` for planner JSON validation. Keep configuration,
tokens and SQLite state under ignored/private user storage, never in a skill package.
Use a separate state database and service credentials for each user workspace.

For the optional Python deployment, copy `config.example.json` to ignored
`local/planning-sync.json`, set the explicitly selected compatible Notion data
source ID and property mapping, and set `NOTION_TOKEN` through the host's secret
manager or environment. The token is read at request time and is never saved in
SQLite. A `null` calendar means no external calendar client is configured for
this Python host.

For calendar integration set:

```json
{
  "calendar": {
    "client_factory": "your_host.calendar:create_client",
    "options": {"calendar_id": "the-selected-calendar-id"}
  }
}
```

This factory is trusted deployment configuration. Its client must implement the
protocol in `calendar_adapter.py`; use the selected provider's authenticated API
and cover every calendar that should contribute busy time. Store refresh tokens
in the host's secret store. Do not send credentials or factory names to the model.

Example commands from the repository root:

```powershell
.\.venv\Scripts\python.exe components/planning-sync/cli.py --config local/planning-sync.json import-plan --project-id demo-project --request-id import-001 --input test-results/project-plan.json
.\.venv\Scripts\python.exe components/planning-sync/cli.py --config local/planning-sync.json apply --request-id calendar-edit-001 --input test-results/calendar-edit.json
.\.venv\Scripts\python.exe components/planning-sync/cli.py --config local/planning-sync.json sync
.\.venv\Scripts\python.exe components/planning-sync/cli.py --config local/planning-sync.json status
```

The example input files must be real validated outputs from the relevant workflow.
These commands do not install dependencies, create an account or start a daemon.
The host should perform bounded periodic polls (for example every 60 seconds),
request a fresh poll before weekly planning, and trigger one after accepted edits.
Webhook notifications can shorten the delay; keep polling as recovery for missed
notifications. Honour provider rate limits/backoff in the host. Display last
successful poll time, pending/error state and conflicts; do not label stale views
as live. No poll or recurring automation has been activated by adding this code.

## Failures and conflict resolution

SQLite commits a write's operation ID before contacting a provider. Retries keep
that ID. A subsequent successful read can acknowledge a write whose reply was lost.
Adapters must preserve provider IDs, check remote versions before writing and use
provider idempotency where supported. A failed read blocks writes for that task.

Notion does not provide an atomic conditional page update or a documented create
idempotency key. The adapter rechecks the page version and uses Sync ID/operation
markers, but a concurrent edit between read and update remains a live API limitation.
An uncertain non-idempotent write raises `AmbiguousWrite` and stops automatic
resubmission until a read confirms the intended result. If no result can be found,
an operator must investigate the provider before any manual retry; do not clear
the queue just to make its warning disappear.

Inspect `engine.conflicts(task_id)`, present the alternatives, and call
`resolve_conflict(task_id, explicit_patch, current_revision, request_id)` with the
selected values. It requires all conflicting fields. Then poll again. Never pick
the latest wall-clock timestamp as a silent winner or resolve by deleting a task.
The task history retains accepted changes. Partial failures across services are
reported and retried; this is eventual synchronisation, not a distributed transaction.

## Verify before deployment

Run the repository validator and unit suite. In a dedicated test Notion data source
and calendar, then exercise create, rename, drag/resize, unschedule, complete,
cancel, stale edits, conflicting edits, rate limits, credential expiry and restart
after an uncertain response. Verify external IDs and that unrelated meetings and
Notion properties are preserved. Connect the dashboard only after these live checks.
