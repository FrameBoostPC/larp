---
name: calendar-planner
description: Review connected calendar capacity for project planning, and schedule or update shared tasks using confirmed availability and current Notion/calendar state.
metadata:
  version: "0.2.1"
---

# Calendar Planner

## Purpose and inputs

Review calendar capacity for detailed project planning, or turn accepted tasks into a feasible schedule and keep edits attached to the same tasks. For changes, use the latest shared task state supplied by the host: stable project ID, persistent task UUIDs, current revisions, progress, dependencies, estimates, due dates and existing schedules. Also use confirmed availability, existing busy periods and the user's timezone. This skill proposes changes and can route authorised execution through available host tools; it does not install a calendar connection, Notion integration or sync service.

Hermes owns the goal, conversation, retrieved context and tool routing. Completed voice requests use the same accepted state as text, without a workflow selector. Use the connected scheduling route's contract for reads and authorised changes; its deterministic result owns execution status. If an n8n planning route already supplies the accepted plan, reuse it rather than invoke a second planning model. This skill guides calendar reasoning; it does not replace the host's task or receipt store.

If the user starts with a goal rather than saved tasks, prepare the project plan first using the host's planning workflow, or `project-planner` when installed. Calendar review can happen before tasks are saved; persist accepted tasks only when their scheduling is requested. Do not fabricate UUIDs, revision numbers or provider IDs. For requested changes, if no identifiable project or task state is available, ask one focused question or request the missing host state; return `needs_input` with null data in JSON mode. If some changes can be prepared accurately, return a `partial` proposal and describe blocked work in `deferred` and `limitations`.

## Review capacity without booking

The project planner's **Detailed time planning** option requests estimates and thoughtful calendar-aware recommendations. It does not authorise creating sessions. A broad timeline uses milestone/week targets without hourly estimates or slot suggestions; do not turn detailed planning on merely because the user asks for an expanded reading view. Existing bookings stay unchanged when the option is turned off.

For a review, read the connected host's current calendar state for the requested horizon. Use confirmed or saved workdays, work-time windows, timezone and breaks. If windows are unknown, show the effort estimate and leave available capacity unknown; an empty calendar never implies 24-hour workdays. Identify exactly which calendars and dates were read. The existing n8n workflow reads the Schedule & Tasks pages shown in Notion Calendar; do not assume unconnected calendars are covered.

Subtract the union of busy intervals from each allowed work window, accounting for all-day items, recurring instances, timezone/DST and the configured buffers. Do not count overlapping meetings twice. Existing sessions for this project's remaining work count as allocated effort once; compare the remaining unscheduled effort with the remaining free time. Fragmented gaps and dependencies may prevent a task fitting even when total minutes seem sufficient. Never infer completion from a past session.

Return an effort/capacity comparison, useful slot suggestions when supported, and any shortage. Suggest reducing scope, extending the timeline or an explicit availability change when necessary. Do not silently add evenings or weekends. Unknown/partial calendar coverage stays visible, and no review-only operation writes to Notion or the calendar. Refresh availability again immediately before an authorised booking.

In structured version 1.1, use `data.intent: "review"`, `operations: []` and a `calendar_review` object. `project_id` may be null before the project is saved. The review fields are defined in the [output schema](templates/output.schema.json): sources and timestamps identify actual coverage; inclusive window dates and same-day ISO-weekday working windows define the period; `buffer_minutes` is the break allowance per window; `available_minutes` is capacity after busy time/buffers; `already_allocated_minutes` is usable existing project time; `unscheduled_effort_minutes` is work still needing space; and `shortfall_minutes` is their nonnegative difference. Unknown values remain null. `checked` is a reviewed source/window result, not a fit guarantee; use `partial`, `unavailable` or `not_requested` and limitations when appropriate. A known shortage or unverified requested availability makes the overall proposal partial. See the fictional [capacity review example](examples/capacity-review-output.json).

## Plan changes

1. Read the current task state and availability. Preserve the user's chosen project and calendar. Reuse existing authorisation for the requested create/edit actions. A request for a suggested schedule alone produces a proposal; an execution request can proceed through the host's permissions.
2. Select unfinished, unblocked work that fits the available time. Respect dependency order, busy events, due dates and realistic breaks. A scheduled predecessor is not a completed predecessor. If a dependency must finish first, explain the condition or defer the dependent task; do not claim it is ready merely because time was booked.
3. Resolve exact dates, start and end instants, and an IANA timezone such as `Australia/Brisbane` before emitting a schedule operation. Include explicit UTC offsets in both timestamps. Verify offsets against the timezone, including daylight-saving transitions. A date-only deadline, relative week or effort estimate is not a calendar slot. Ambiguous local times require a confirmed offset/occurrence. Missing information blocks only the affected scheduling operations.
4. Prepare one operation per affected task, using its persistent UUID and current `expected_revision`. `schedule` sets or moves its one linked focus block with `patch.schedule = {start, end, timezone}`. `unschedule` uses `patch.schedule = null`. `update_task` contains only explicitly edited task fields: title, status, estimated_minutes, deliverable, depends_on, week, due_date or schedule. Omitted fields remain unchanged. Combine requested task-field and schedule edits in one patch so a rename and move are applied atomically against one revision; do not emit a second operation with the same task/revision. Never combine completion/cancellation with a new active schedule.
5. Keep `due_date` separate from `schedule`. Moving a focus block does not move the deadline, and editing a title must not reset progress or schedule. Current support is one focus block per task; explain requests for split sessions or recurring blocks as deferred rather than collapsing them silently.

## Shared execution and sync rules

Route authorised changes through the host's single shared task/sync integration when it is actually available. Do not independently create a Notion page and a calendar event from the same text: the host owns persistent task identities, provider links, revision checks and retry identities. Reuse the same request ID when retrying the same operation batch. A replay must not create duplicate tasks or events. Never change `expected_revision` to bypass a conflict; refresh the task, compare the user's intended fields with newer edits, and prepare a reconciled operation.

The host applies one accepted task change and propagates it to its linked Notion task and calendar focus event. Read its result before reporting success. Keep planning status (`ready`, `partial`, `needs_input`) distinct from task progress and provider sync status. If any provider is disconnected, unavailable, pending or conflicted, name the remaining work rather than describing everything as synced. Provider retries and conflict handling belong to the shared service; stop repeating mutations when their outcome is unknown and use its reconciliation/retry mechanism.

Use these lifecycle meanings consistently:

- Creating a task does not book time until an exact schedule is explicitly set.
- Task edits from the dashboard, Notion or a linked calendar event refer to the same persistent task. Calendar event times update `schedule`; a shared title edit changes its title.
- Deleting a linked calendar event unschedules the task. It does not delete or complete the task. Deleting or archiving a task must be an explicit host-supported action with its own semantics; do not infer it from a missing item in a new weekly plan.
- Explicit completion or cancellation clears the active focus schedule. The passage of the event's end time never marks work completed. Reopening a task leaves it unscheduled until a new time is chosen.
- Unrelated events are availability constraints. Do not edit unrelated events, add invitations or alter recurring series. A provider deletion, recurrence or ownership ambiguity needs host reconciliation rather than a guessed target.

## Output

In chat, state the proposed changes, any conflicts or missing information, and the next action. Use “scheduled”, “updated” or “synced” only after confirmed execution results. Show times in the user's timezone and make the due date versus booked time distinction visible where relevant.

For voice, give a short confirmed result, material limit or essential question using the existing summary; Hermes owns speech. Keep the full details available for display or requested readback, without extra speech fields or raw JSON read aloud.

For dashboard JSON or explicitly requested structured output, load [the output schema](templates/output.schema.json) and return one matching JSON object without Markdown fences or commentary. New outputs use `schema_version: "1.1"` and `skill: "calendar-planner"`; legacy 1.0 outputs remain valid unchanged. Version 1.1 adds `data.intent` (`review` or `changes`) and optional `calendar_review`. For changes, `data.project_id` identifies the existing shared project and operations use the unchanged revision-checked patch contract. `deferred` explains work without operations and `first_action` states the next concrete step. `ready` means a complete proposal is prepared, not that it ran; it may have no operations if the schedule already satisfies the request. `partial` requires a limitation and retains useful known operations. `needs_input` requires questions and null data. The preserved [legacy example](examples/example-output.json) illustrates a move using host-supplied identity and revision; these sample values are not defaults. A legacy mutation consumer must not receive a review-only result as an operation batch.

Before returning, check task identities and revisions against current state, explicit patch fields, unique task operations, chronological start/end, timezone offsets, busy periods, dependencies and capacity. The schema validates shape; the host must still check current revisions, project membership, task progress, availability and sync outcomes at execution time. If availability was not read, disclose that the proposed slot is unverified and return `partial` rather than promising it is free.
