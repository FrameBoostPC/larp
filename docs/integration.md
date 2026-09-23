# Dashboard integration

These schemas are the proposed output contract for the Hermes setup demonstrated and taught in our course, not a built-in Hermes dashboard API. The repository contains skills and validation tooling; connecting them to the dashboard being developed separately is a separate implementation step.

Install the [shared Hermes setup](../components/hermes-orchestration/README.md)
on the partner's active profile. Its [operating instructions](../components/hermes-orchestration/instructions.md)
are the maintained cross-feature policy; its [capability catalogue](../components/hermes-orchestration/capabilities.json)
maps Content Creation to `idea-to-content` and identifies current operation owners.
The portable [workflow contract](../components/hermes-orchestration/workflow-contracts.md)
supplies the runtime transport and action reference. This guide retains detailed
dashboard behaviour, provider background and examples. Follow the same model for
future features; the dashboard must connect to Hermes with its profile and tools,
not directly to a writing model for goals requiring orchestration.

## Invoke and display

Pass the selected skill, user's task, relevant creator/project context, and an explicit request to return dashboard JSON to the agent. Keep the user's content distinct from application instructions. The skill selects no model and does not assume a particular dashboard framework.

Each response has the same envelope:

| Field | Meaning |
| --- | --- |
| `schema_version` | Output contract version, distinct from the skill package version: planning skills support `1.1` and legacy `1.0`; other skills use `1.0` |
| `skill` | One of the installed skill names |
| `status` | `ready`, `partial`, or `needs_input` |
| `title`, `summary` | Title and overview; for planning, `summary` is the condensed reader view |
| `assumptions` | Reasonable choices the agent made where input was missing |
| `questions` | Questions for essential clarification or unresolved work |
| `limitations` | Missing evidence, unavailable execution, or material constraints |
| `data` | Skill-specific content, or null when input is needed |

`ready` means the requested deliverable has been prepared. It never means posts were published or project tasks executed. `partial` means a useful result exists but some requested work or essential evidence remains unavailable. `needs_input` has null data and at least one question. A ready result has no pending questions.

The payloads support these views:

- `idea-to-content`: show `data.assets` as editable content cards; link their hooks using `hook_id`. Make `content` the copyable caption or spoken script. Keep creator guidance, `production_notes`, and internal titles outside the copy area. `call_to_action` identifies text already in the draft; do not append it again. A separate video `caption` is its own copy area. Hide empty hook lists and omit planning displays when the user asks only for drafts. Stable JSON fields need not all be shown in the UI.
- `project-planner`: let the user choose Broad timeline (default) or Detailed time planning. Broad plans show milestones, dependencies and target weeks, without hour estimates or capacity controls. Detailed plans estimate required effort and compare it with a current calendar review and any user-supplied limits. Keep required effort visible when it cannot all fit. Dependencies use task IDs; actual completion belongs to the application's task state.
- `calendar-planner`: support a read-only calendar review for detailed project planning as well as proposed scheduling operations. Show calendar coverage, working windows, buffers, availability and shortages. Scheduling operations use persistent task UUIDs and expected revisions. Planning `ready` does not mean operations have run. The existing n8n integration below uses its own stable page references and execution results.

## Voice-first workflow standard

This is the default for **every new or changed workflow**, including workflows
triggered by events or schedules. An automated run need not speak unprompted; its
status and follow-up actions must be usable through the same conversational tools.

- Let Hermes resolve the user's intent, current project/item, dates and preferences.
  For operations owned by n8n, pass that resolved request to a direct n8n tool
  entry. Content drafting and repurposing use the existing Idea to Content skill.
  Do not require a form,
  dropdown or button to complete an otherwise clear spoken request.
- Keep one accepted state across voice, text and buttons. The host creates request
  IDs, retains the current target and checks revisions before displaying or speaking
  a delayed result. A correction is a new accepted command; a retry reuses the
  original command unchanged. Interim transcripts must not start work.
- Ask one short question only when the missing detail changes the action or its
  safety. Reuse known preferences. Optional fields stay optional. Broad planning
  is the default; detailed planning may ask for working windows, never force a
  weekly hours budget. Do not equate an empty calendar with willingness to work.
- Use deterministic actions for reads, edits, completion and retries. Generate a
  plan once and reuse it. A preference-only change or view toggle does not invoke
  another model or execute a task. Use a bounded model step only when needed.
- Return a short `spoken_summary` and the full structured `data`. Speak confirmed
  outcomes, conflicts and essential limitations. Do not read HTML, identifiers,
  raw JSON or an entire plan unless requested. A voice-only user can ask for the
  next step, readback or a correction without accessing the screen.
- For longer work, acknowledge once after the run starts, retain its execution ID
  and retrieve its actual result. Do not hold a second conversation/model loop in
  n8n or restart work because speech was interrupted. Stopping audio, cancelling
  pending work and undoing a completed write are separate actions.
- Authenticate tool access. Scope targets to the configured account/database,
  preserve stable page identities, recheck current state and availability before
  writes, and record mutation receipts. Serialise related mutations at the host.
  Unknown outcomes require reconciliation before retrying; never announce success
  merely because a workflow started.
- Validate equivalent text/voice actions, essential clarification, corrections,
  duplicate delivery, stale results, failures and a user switching input channels.
  End-to-end audio testing must use the actual Hermes/dashboard deployment.

The existing [shared input and interruption design](#text-buttons-and-voice-share-one-request)
still applies. The planner and scheduler have direct agent routes described below.
Outreach and prospect research now use the same standard, including their internal
research worker. Email review and daily priorities have saved agent routes and
remain paused. Content uses [Idea to Content](#idea-to-content-creation-and-repurposing);
its retired standalone workflow remains archived.

## Goal execution and autonomy

Hermes owns the user's outcome across skills and tools. A workflow supplies a
reusable operation, context retrieval, persistence or recovery; it is not a
required container for every model response. Use Idea to Content for writing and
adaptation, direct tools for suitable actions, and n8n where a maintained workflow
already owns the operation. The same goal and progress apply to text and final
voice transcripts.

For example, “Start a study tips page; make me Facebook, Instagram and X
accounts” implies a coordinated launch. The host should:

1. Reuse available brand, audience, files, preferences and account context. Check
   for existing suitable accounts before creating duplicates. Infer reasonable
   creative defaults, recording assumptions outside the audience-facing copy.
2. Prepare a coherent concept, proposed name, platform-specific bios/descriptions
   and initial content. Create original material where no source exists, then
   adapt it across the named platforms. Retrieve or create suitable visual assets
   through available tools when needed; copy or visual instructions alone do not
   count as rendered images. Requested platforms override default content packs.
3. Check actual authenticated capabilities separately for account/page creation,
   profile editing, media upload and publishing. A generic API connection does
   not establish that all four operations are supported. Execute ordinary
   dependent setup and profile-filling steps already authorised by the goal,
   without asking the user to restate each step. Resolve essential ownership or
   account-type ambiguity before the affected action; do not invent identity
   details, credentials, availability checks or completed actions.
4. Verify resulting profiles and changes, retain account IDs/URLs and operation
   receipts, and report completed versus pending work. Reconcile uncertain
   writes before retrying. Resume from saved progress after a blocker clears.

If authentication, verification, required permissions, unsupported operations or
essential user details block one step, complete independent work and ask only
for what unblocks that step. Do not restart the whole goal. Honour “drafts only”
or other explicit limits. A request to create and fill profiles does not by
itself establish an ongoing posting schedule, paid promotion or direct-message
campaign. Publish initial posts when that is part of the requested outcome;
otherwise retain the prepared posts for the next instruction.

The content skill returns writing assets and honest status; the host retains
broader execution state and confirmed tool results separately. This repository
does not implement social-account provisioning. Its local preview has a bounded
command router and a model drafting endpoint, not a general goal executor. The
partner's Hermes deployment must connect the appropriate capabilities and verify
this contract with both voice and text before claiming a working social launch.

## Workflow names and relationships

Workflow names use a shared group prefix, then a role number where workflows call
one another. The numbers make the connected set easy to find in n8n; users do not
need to start each numbered workflow manually.

| Group | Role | Earlier name |
| --- | --- | --- |
| Prospecting & Outreach | 01 - Find Prospects | Starter 08 |
| Prospecting & Outreach | 02 - Research Prospect (Internal) | Starter 08 Helper |
| Prospecting & Outreach | 03 - Draft Outreach & Follow-ups | Starter 02 |
| Planning & Calendar | 01 - Project Planner | Starter 04 |
| Planning & Calendar | 02 - Calendar & Task Manager | Starter 03 |
| Email | Inbox Organiser & Reply Drafts | Starter 01 |
| Daily Review | Priorities Digest | Starter 07 |

**Prospecting & Outreach:** start Find Prospects. It calls Research Prospect
(Internal), which calls Draft Outreach & Follow-ups for qualifying contacts and
continues through the candidates. Draft Outreach & Follow-ups also accepts a
direct brief when the contact is already known.

**Planning & Calendar:** Project Planner calls Calendar & Task Manager for current
Notion context and accepted task saves. Calendar & Task Manager also supports
direct schedule and task requests.

**Email** independently produces saved email reviews and confirmed label receipts.
**Daily Review** now reads current Gmail sources, those saved records and
Workbench progress, then calls the calendar owner's internal read action for
today's Schedule & Tasks context. It does not generate fresh outreach or research.
Daily Review collection remains paused; joining the shared instance does not change background triggers.

The 2026-09-16 rename preserved stable workflow IDs, form addresses, action names
and execution logic. Historical test notes and older canvas notes may use the
earlier Starter names above. The Hermes registry maps its existing keys to the
same IDs and current display names. Archived workflows are outside these groups.

## Other existing n8n voice routes

Availability verified 2026-09-17. These routes use the same private **Agent request** trigger,
authenticated MCP transport and `output` / `tool_result` response shape as the
[planner/calendar contract](#direct-agent-requests-for-voice). The host supplies
`request_id`, `session_id`, `revision`, `action` and resolved `arguments`. For these
routes, request IDs are 2–60 characters using the planner's lowercase slug alphabet;
session IDs and revisions follow the same rules. Users do not dictate IDs.

| Workflow | Actions and current state |
| --- | --- |
| [Prospecting & Outreach \| 03 - Draft Outreach & Follow-ups](https://automatedai.app.n8n.cloud/workflow/m9qGDkh7s29y4Bef) | Published. `draft_outreach` prepares a Gmail draft; `get_status` reads its saved receipt. |
| [Prospecting & Outreach \| 01 - Find Prospects](https://automatedai.app.n8n.cloud/workflow/xy4pY5ahF6DxwH9P) | Published. `find_prospects`, `get_status`, `cancel_campaign`. Research continues through the published [02 - Research Prospect (Internal)](https://automatedai.app.n8n.cloud/workflow/iA9pVjGGi46EMVs5) helper. |
| [Email \| Inbox Organiser & Reply Drafts](https://automatedai.app.n8n.cloud/workflow/PelmDAUWeW5f0gQU) | Published. `list_reviews` filters recorded reviews by category, status, sender or subject; `get_review` reads one by message ID. Results can link to the original Gmail thread. |
| [Daily Review \| Priorities Digest](https://automatedai.app.n8n.cloud/workflow/Ux9xifTok0pnJRMZ) | Published retrieval; collection paused pending time selection. `get_daily_review` and retained `get_priorities` retrieve the latest prepared source snapshot. |

Outreach needs `contact_name`, `contact_email`, `company`, `context`, `offer` and
`contact_basis`. Reuse details already known to the conversation. `stage` defaults
to `First message`; `Follow-up` needs the actual `conversation`. Optional writing
requirements and guidance retain their existing checks. This workflow creates
drafts only. It does not send messages or provide a conversational editor for an
existing Gmail draft; deliberate edits use the host's email tools and current draft.

For prospect research, Hermes resolves `niche` and `target_location` before calling.
Supply `offer` and `sender_details`; `count` defaults to five and accepts 1–10.
Optional `request`, `search_queries`, writing requirements and exclusions retain
the existing research validation. Direct requests skip the form's intent model.
Search and evidence checks still run; empty candidate lists return an explicit
result. The helper stays internal and keeps its source-verification checks.

Both creation actions accept an optional stable `reference`, defaulting to
`request_id`. `get_status` and `cancel_campaign` require that earlier `reference`.
Use a new request ID for the follow-up command. An exact creation retry returns
the saved receipt or recorded progress, without starting another model/search or
Gmail write. A changed brief under the same reference returns `conflict`; use a
new reference for the correction. A missing record returns `not_found`. An
incomplete outreach write returns `needs_review`: inspect the original execution
and Gmail state before retrying. These get/check/write operations are not atomic;
the host must serialise operations sharing a reference.

Long research returns `running` after starting its worker. Status reads use saved
progress without calling a model; inspect the reported execution when progress
appears stalled. Recorded `RESEARCHING` is not proof an execution is still running.
`cancel_campaign` records a separate stop flag and returns `cancel_requested`.
Workers check before a website fetch and again before reserving/creating a draft.
An in-flight action can finish; completed drafts remain available. Only a worker's
confirmed stop returns `cancelled`. Stopping speech does not cancel the campaign.

For email review, `list_reviews` accepts optional `limit` (1–50, default 20),
`category`, `status`, exact email `sender` and literal `subject_contains`;
filters apply before the limit. Subject matching is case-insensitive and does
not search bodies or attachments. Results include an account-bound `gmail_url`
for the original message/thread when a valid Gmail identity is available.
Category labels and
saved-summary retrieval were added on 2026-09-23; see the
[email triage component](../components/email-triage/README.md). Counts cover only
returned records, not inbox totals.
`get_review` needs `message_id`. Results explicitly identify saved review data and
`live_inbox_checked: false`. They do not poll Gmail or generate more drafts.
Daily Review has separate preparation and retrieval paths. At a user-selected
time every day, preparation collects email/spam, existing drafts, confirmed
organisation actions, completed/pending work and the connected Notion schedule,
then saves a Workbench snapshot. It does not compose or deliver a briefing.
`get_daily_review` and retained `get_priorities` accept empty arguments and read
the latest saved snapshot only. Hermes uses its evidence for priorities,
decisions, meeting preparation, possible commitments and actual user output.
Missing, stale and partial snapshots are explicit; retrieval never silently
rescans. Schema 3.0 replaces the earlier formatted result and optional `since`
argument. See the [daily-review component](../components/daily-review/README.md).
Its daily trigger remains disabled with collection `paused` and no recurring time chosen. The installed
[setup contract](../components/hermes-orchestration/setup-contract.md) and
`settings.py` helper support deferred conversational onboarding and later edits
to connections, resources, routing, time and timezone. The partner exposes the
helper through Hermes and connects provider consent; no onboarding screen is
supplied here. Preferences are separate from remote deployment. Apply bindings,
verify a live preview and publish the checked version before claiming activation.
Unselected sources are skipped. Configuration changes invalidate old snapshots
and selected references. A selected calendar needs its published internal
`daily_review_context` extension and matching account/resource before activation.

All six direct routes are published. Authenticate and verify execution permissions
from the partner's own profile using the [shared instance setup guide](../components/hermes-orchestration/partner-setup.md).
The installer can merge MCP configuration; the local settings helper can reference
the existing Daily Review configuration without changing remote accounts or time.
Use its `get_setup` action for a connection check. Do not publish workflows or
change email push processing as an incidental setup step. Daily Review collection
remains paused. Archived Starter 06 remains retired.

Actual microphone input, conversation state, interruption and speech playback
remain part of the partner's Hermes/dashboard integration.

## Weekly planning, Notion and calendar sync

### Existing n8n integration

The [Planning & Calendar | 01 - Project Planner](https://automatedai.app.n8n.cloud/workflow/tJ6YmJuFsyEoWYXw)
is wired to [Planning & Calendar | 02 - Calendar & Task Manager](https://automatedai.app.n8n.cloud/workflow/rTed7PRf60fF2MjA).
The scheduling workflow already uses **Notion account 2** and the **Schedule & Tasks**
database. Notion Calendar displays those same database pages. A separate calendar
provider and a second copy of each event are unnecessary for this setup.
Both workflows were published on 2026-09-15 after live Notion and model tests passed;
the optional planning-detail update was published on 2026-09-16.
The direct agent routes were live-tested and published on 2026-09-16 as well.
The separately developed Hermes dashboard still
needs to invoke and display the appropriate workflow contract.

The planner form uses these identities and choices:

| Input | Behaviour |
| --- | --- |
| Project reference | Reuse one stable lowercase reference across reviews and planning styles for the same project. |
| Request reference | Identifies one exact brief and its preferences. Reuse it to resume that request; use a new reference when changing the brief, style or planning period. |
| Planning style | **Broad timeline** by default; **Detailed time planning** adds calendar review, effort estimates and proposed work sessions. |
| Plan starts / Number of weeks | Explicit ISO start date and 1–12 weeks, default four, in `Australia/Brisbane`. |
| Working preferences (detailed only) | A second form page shows editable working days/hours, break buffer and reserve. Defaults: Monday–Friday, 09:00–17:00, 15 minutes around commitments, 20% of free time left unallocated. |
| Weekly project hour limit (detailed only) | Optional. Blank uses calendar capacity inside the selected working windows. Zero permits no new allocation; required work remains estimated and is reported as a shortfall. |
| Draft only | Reads current state and prepares a plan without saving tasks to Notion. |
| Save tasks to Notion | Saves new tasks through the scheduling workflow and returns current state for existing tasks. |

Each project task uses `planner:<project_reference>:<task_key>` in the existing
Notion Reference property. Task keys persist across weeks; a changed title does not
create a new identity. The request reference belongs to the planner's Workbench
record and is separate from these task references.

The connected sequence is:

1. Read current project pages and busy periods through the scheduling workflow's
   `project_context` action before every review, including a resumed request.
   If the read fails, stop the dependent plan/save operation.
2. Propose work using actual titles, status, dates and notes. Reuse loaded task
   references; completed or cancelled tasks are not reopened by a new weekly plan.
   Leaving a task out does not delete it.
3. Validate task identities, target weeks and dependency order. Broad plans have
   no hour estimates. Detailed plans estimate the work needed, subtract current
   commitments from selected working windows, and recommend sessions that respect
   dependencies, breaks, reserve and optional limits. Show work that cannot fit;
   do not reduce the estimated work merely to make the plan appear feasible.
   Target weeks and suggested sessions never create bookings. Only an explicitly
   supplied date-only deadline can be carried into a new task's date field.
4. For an accepted save, persist the plan before calling `sync_task` for each
   task. That action creates a missing new page or reloads the existing page
   without replacing its title, progress, notes or dates with model output.
5. Save actual page IDs and receipts in the planner result. Display confirmed
   current task state separately from the proposed work. Unconfirmed writes
   produce `PARTIAL`, not a successful sync message.

Use the scheduler's direct agent route for conversational edits, time changes,
completion or cancellation. The owning scheduling form and a task's Notion page
link provide another access path. Changes made to a page in Notion or its
connected Notion Calendar view are changes to that same page; the next planner
review reloads them. The planner does not send its older proposal back as a patch.
Undated tasks remain in the task list until a date is explicitly chosen. This
database has one date field, so the integration cannot independently store a
deadline and a timed slot on the same page; callers must not silently replace one
with the other.

Detailed review covers the configured **Schedule & Tasks** database. It cannot
see commitments in other calendars that are not represented there. Calendar gaps
are filtered through the user's working preferences; an empty calendar does not
establish willingness to work all day. Suggested sessions are a snapshot and
must be checked again by the scheduling workflow when the user applies them.
Existing bookings remain visible and count toward the corresponding task's effort;
the planner does not automatically move them to match a new suggestion.
Each Notion task has one date interval. When a recommendation spans several
separate sessions, split the task before booking those sessions; applying another
interval to the same page would move its current booking.

Changing the planning style is a new review with the same project/task identities.
Turning detail off hides effort and session recommendations, while preserving saved
progress, deadlines and bookings. It does not cancel existing calendar entries.

### Direct agent requests for voice

Both workflows expose **Agent request**, a private Chat Trigger used as the
structured n8n MCP transport. It is not another chatbot and has no public chat
endpoint. Use the existing authenticated n8n connection; do not send a user to a
chat form or expose account credentials in the dashboard. These are single-owner
workflows, not a tenant-isolated customer service.

Call `execute_workflow` with the workflow ID, `triggerNodeName: "Agent request"`
and `inputs.chatInput` containing a JSON-encoded object:

```json
{
  "request_id": "project-review-001",
  "session_id": "hermes-session-42",
  "revision": 7,
  "action": "plan_project",
  "arguments": {
    "project_reference": "balcony-guide",
    "goal": "Prepare a balcony gardening guide",
    "week_start": "2026-09-21",
    "horizon_weeks": 4
  }
}
```

The host supplies these tracking fields; the user never needs to dictate them.
`request_id` is 2–70 lowercase letters, digits, dots, underscores or hyphens.
`session_id` is 1–120 letters, digits, dots, underscores, colons or hyphens.
`revision` is the non-negative accepted conversation-state revision. The transport
accepts resolved arguments, not a raw speech transcript. It echoes the tracking
fields; revision-based speech suppression remains the host's responsibility.

| Workflow / action | Arguments and behaviour |
| --- | --- |
| Planner `plan_project` | Required goal, stable project reference and resolved ISO start date. Backlog can be omitted; the planner derives tasks from the goal. Defaults to Broad timeline, four weeks and Draft only. Other choices use the planning inputs above. |
| Detailed planning | Supply `planning_style: "Detailed time planning"` and known `work_days`, `work_start`, `work_end`. If windows are unknown, one clarification asks when the user usually works. `hours_available` remains optional; explicit zero remains zero. |
| Calendar `project_context` | Required `project_reference`. Refresh current project tasks, stable page IDs, state tokens and calendar commitments. |
| Calendar `list_tasks`, `list_schedule` | Read current tasks or a schedule window. `list_tasks` accepts optional literal title-word `query`, exact `project_reference`, `status` and `page_id` filters; default status remains open tasks. Multiple matches keep separate IDs and state tokens. For `list_schedule`, supply `window_start`/`window_end` with timezone offsets, or inclusive `from_date`/`to_date`. |
| Calendar `find_slots`, `check_slot` | Supply a resolved window; optional duration, daily start/end, weekends, buffer and maximum slots use the scheduler's existing validation. An unavailable `check_slot` may return up to two same-day alternatives with the requested duration and buffers. Reads never reserve time; refresh availability before booking a selected option. |
| Calendar `create` | Supply title and kind; Task may be undated. A timed item needs explicit `start` and `end` timestamps. A date-only Task uses `due_date`. A stable reference derives from the request ID. |
| Calendar `update`, `complete`, `archive` | Supply the selected `page_id` and its exact latest `state_token` as `expected_state`. Update sends only intentional changed fields. Resolve an ambiguous “it” in Hermes before calling. |

Calendar writes use the same Notion pages as the planner. Missing item identity
returns a short clarification; missing state returns `refresh_required` for an
automatic read. A stale state returns a conflict with the current item. The token
compares content as well as Notion's edit timestamp, so two changes in the same
timestamp interval are still detected. Review the changed details before issuing
a new command. When switching a task between a deadline and a time booking,
`replace_date: true` must reflect the user's deliberate replacement choice.

The terminal node is **Return planning agent result** or **Return scheduling agent
result**. It emits `output` for short speech and `tool_result` containing
`schema_version`, request/session/revision, `status`, `spoken_summary` and full
structured `data`. Statuses include `completed`, `partial`, `needs_input`,
`refresh_required`, `conflict`, `needs_review`, `invalid_request` and `failed`.
`data.plan` remains a proposal; `current_tasks` and sync receipts describe actual
saved state. Do not treat generated plan wording as a write receipt.

MCP execution returns an execution ID first. Keep it, then read the selected
terminal node using `get_workflow_execution`. On a failed execution, report a
failed or unconfirmed result from the actual error; never fabricate the normal
completion envelope. Provider errors are not silently retried by the new route.
For tests use `executionMode: "manual"`; for an intended real command use
`"production"`. The partner must configure and test this connection in Hermes.

Calendar mutation receipts are stored by request ID. An exact completed retry
returns its **historical receipt**, does not repeat the mutation and requests a
fresh read before a subsequent edit. Changed content under the same request ID
is rejected. A started request without a receipt returns `needs_review`; reconcile
the execution and current Notion page before retrying. Reads always load current
state. Planner retries continue to use the persisted plan and fresh calendar
review described below.

These checks are not an atomic lock across n8n and Notion. The Hermes host must
serialise mutations for the same calendar/project, and another actor can still
edit Notion between the read and write. The workflow does not implement microphone
capture, audio playback, interruption handling or stale-transcript reconciliation;
those remain in the separately developed Hermes/dashboard integration.

### n8n retries and current limits

A resumed request reuses its saved plan instead of asking the model to allocate
new task keys. Changed brief content with the same request reference is rejected.
Before task saves start, the Workbench records that the batch may have begun.
Resuming such a batch requires existing pages and checks any saved page IDs; it
does not recreate a page that the owner may have archived.

Missing pages, duplicate references and mismatched page IDs require review. A
failure before any task was created may therefore need manual recovery rather
than a blind replay. Keep planner save runs for the same project/request from
overlapping: Notion page creation and the Workbench lookup are not one atomic
transaction. The scheduler's availability checks also do not reserve time against
simultaneous external edits. Report the returned conflict or partial state and
reload current data before deciding the next operation.

This setup refreshes state when its workflows run. It does not establish continuous
polling, full cross-provider calendar sync, or a validated Hermes dashboard
connection. New Workbench results use their own `schema_version: "3.0"`
plan/current-state/receipt structure with planning style, horizon and optional
availability/recommendations. Saved `2.0` requests retain their original replay
behaviour. Neither structure is the portable skill's `1.1`/`1.0` envelope.

### Optional portable Python integration

The [planning-sync component](../components/planning-sync/README.md) is a separate
prototype for a host that chooses to deploy it. It does not power the n8n workflows
above and its UUID-based state, Notion properties and provider client are an
alternative contract. Do not apply its database schema to the existing Schedule &
Tasks database as an incidental integration step.

For a host choosing this component, use it as the single owner of execution state.
The prototype currently requires positive integer task estimates. Broad `1.1`
plans must remain proposals until that importer supports unknown effort; never
coerce a missing estimate to zero to bypass its contract.

Its guide defines the task lifecycle, Notion property mapping, client contract,
connection requirements, failure recovery and deployment checks. Keep that guide
as the maintained Python sync contract; do not independently implement page/event
writes in each skill handler.

The Python host sequence is:

1. Poll connected surfaces and load current task state before a weekly review.
   Show a stale/disconnected indicator if that read did not succeed.
2. Validate the Project Planner result and import it with a stable project ID and
   request ID. Preserve the returned task UUIDs on cards. Re-importing a draft
   creates missing tasks and preserves existing progress; explicit revisions use patches.
3. Supply these saved tasks, current revisions and availability to Calendar Planner.
   Validate its output and verify every operation belongs to the selected project.
4. Apply the user's authorised operation batch using
   `Engine.apply_operations(operations, request_id, project_id=...)`. The same request
   from a button, typed command or voice input uses the same accepted task identity.
   Reuse its request ID on retry. Refresh after a revision conflict.
5. Poll sync after accepted edits and refresh both views from the stored tasks.
   Use observed receipts/errors for external status. Keep pending and conflicted
   changes visible; do not translate a model's `ready` into a successful save.

The Python host must implement its own calendar provider client, authentication, task/user
isolation, polling or webhook triggers, and UI progress/conflict controls. The
Notion adapter is implemented and contract-tested; no live provider integration or
dashboard wiring has been exercised here. Notion's lack of atomic conditional
updates is a documented concurrency limitation; see the component guide.

## Idea to Content: creation and repurposing

Route new ideas and repurposing requests to the same `idea-to-content` skill.
The user can speak or type the complete request; no mode selector, form, reference
code or second workflow is required. The maintained source rules and default
repurposing pack live in [the repurposing guide](../skills/idea-to-content/references/repurposing.md).
Infer adaptation from the source and desired outcome, without requiring the word
“repurpose”. Specific platforms, formats, lengths and counts override defaults.
Reuse known audience and voice preferences; missing optional settings do not
block drafting. For broader requests, follow [goal execution](#goal-execution-and-autonomy)
and use this skill for the implied writing work.

Example requests through either input channel:

- “Repurpose this transcript into a LinkedIn post and a newsletter.”
- “Turn that script into two Instagram captions. Keep the same facts.”
- “Use yesterday's article for Facebook, Instagram and X.”
- “Make only the second post shorter, and keep the newsletter as it is.”
- “Read the newsletter back to me.”

The Hermes host owns source retrieval, the current source/draft selection and
conversation history. Resolve “this” and “that” to material actually present in
the current conversation or retrieved through an authorised tool. Ask one short
question if the source or target is missing or ambiguous. A URL alone is not
evidence that its contents were read. Voice input provides a final transcript;
this skill does not transcribe audio files or extract video itself.

Retain the original source separately from generated assets. Send the source,
requested formats, current accepted preferences, relevant previous result and
specific target IDs with a follow-up. Do not turn unsupported additions in an
earlier generated draft into source facts. Keep unchanged siblings as the accepted
version, and merge only the deliberately revised asset(s). A format conversion can
add a new asset without deleting the source draft unless replacement was requested.
Readback uses accepted copy and does not call the model again.

The skill keeps output schema `1.0`. Its `summary` is a short spoken completion or
essential clarification; full copy remains in `data.assets`. A newsletter uses
`format: "other"`, `platform: "Newsletter"`, and includes its subject and body in
`content`; the internal `title` is not the email subject. A host may wrap the result
with `spoken_summary`, request/session IDs and its accepted revision. Check that
revision before showing or speaking a delayed result. A `needs_input` result
speaks the essential question; a `partial` result also states the relevant limit.
Never announce that drafts were saved or published without a confirmed action.

The local preview loads this same skill and repurposing guide. Clear content
commands from its completed microphone transcript or text instruction use the
same generation route; simple style-only commands retain their existing controls.
Its API returns `spoken_summary` beside `result`, `model` and `provider`. The preview
does not implement a complete conversational interpreter or spoken playback.
Production Hermes must connect its own conversation state and existing speech
layer and exercise mixed-input, readback and interruption scenarios.

**Retired automation:** `Starter 06 - Content Repurposing Drafts`
(`ROjypSujSwjcyGpG`) was archived on 2026-09-16. Do not route new content or status
requests to it or republish it as part of unrelated workflow updates. Existing
Workbench rows and execution history were not deleted or migrated. New Idea to
Content drafts use the existing host's storage policy; the local preview keeps
them only in its current page. Archiving the old workflow does not add persistent
saving, automatic publishing or media rendering to the skill.

## Idea to Content writing-style controls

The skill accepts voice preferences now. The [portable content-preferences component](../components/content-preferences/README.md) implements selectors and a local generation preview for the separately developed dashboard. It emits preferences and request events. The preview's Python server loads the skill and calls a configurable model directly, initially local gpt-oss:20b through Ollama. The partner can replace that connection with their Hermes backend without changing the skill output schema or shared selector state. The choices below remain the integration contract, not a Hermes configuration API. Keep the first screen simple: the user's topic, their requested deliverables, and a **Writing style** selector. Put the additional controls under an optional **Customise voice** disclosure.

The maintained preset definitions and writing behaviours live in [writing styles](../skills/idea-to-content/references/writing-styles.md). The skill loads that file when drafting or rewriting copy.

| Control | Choices and default | Behaviour |
| --- | --- | --- |
| Writing style | Engaging (default), Educational, Entertaining, Emotional, Professional, Custom | One primary style. Custom accepts the user's description. |
| Secondary style (optional) | Another named style, or none (default) | Adds a lighter influence; do not require multiple selections. |
| Intensity (mapped to Energy in the skill) | Calm, Balanced (default), Bold | Changes pacing and emphasis, not factual certainty. |
| Wording | Plain, Conversational (default), Polished | Changes vocabulary and phrasing; never automatically adds slang or profanity. |
| Writing sample (optional) | Pasted sample or an accessible user-owned profile | A reference for voice; never a source of new product facts or personal history. |

Users can also type or speak a writing-style request in ordinary language. Treat deliberate changes to a setting as overrides of its older value, regardless of input channel. Specific requirements such as no humour remain constraints until the user changes them; a preset must not silently erase those requirements. Do not let an untouched default control override a specific instruction in the user's brief. If the user has not chosen anything, send defaults as fallback preferences. Content purpose (for example, teaching or promoting a product) and audience remain separate from voice.

Pass selected values as request context alongside the topic, audience, factual material, requested assets, and any original copy being rewritten. For example:

```text
Skill: idea-to-content
Topic: how to get good at public speaking
Audience: beginners who hesitate to speak in front of other people
Deliverables: one 45-second vertical video and one companion caption
Writing style: Engaging
Secondary style: Educational
Energy: Bold
Wording: Conversational
Specific instructions: no slang; show one concrete practice exercise
Return dashboard JSON.
```

This is a prompt example, not a new structured request schema. Keep sample/source text labelled as reference content, separate from application instructions. Save the user's actual control selections in application state; the model's existing `data.brief.tone` describes the resolved voice for review. Do not parse that prose field as the source of truth for UI settings. The output schema remains `1.0`, so existing consumers need no new fields.

Applying a new voice to existing copy requires a new generation; this differs from the research/planner reading-view toggle. Offer **Rewrite in this style** on a selected asset. Send that asset's original copy, its factual brief, audience, length constraints, and the new voice, and request only that asset. Keep the previous version available for comparison. After validation, replace only the targeted card; unrelated assets retain their copy and voice. The application owns card identity, version history, loading/error states, and any decision to save a default profile. A rewrite does not imply posting or scheduling.

## Text, buttons and voice share one request

Users must be able to move between typing, clicking and speaking within the same task. Keep one application-owned brief and preference state for that task. All three inputs update it, and the dashboard displays the accepted values. Hermes receives the resolved brief rather than three competing sets of instructions. The portable component implements shared writing-preference state, simple command interpretation and optional speech capture. The broader routing design below still requires the partner's application, speech service and Hermes backend; it is not a new skill output schema.

### Route all inputs to the same actions

- **Text:** interpret the user's request into a topic, deliverables, preferences, target and action.
- **Buttons:** submit explicit settings or actions directly; no model is needed to interpret a dropdown selection.
- **Voice:** reuse the partner's speech layer. With a transcription pipeline, interpret the completed transcript through the same path as text. If a conversational audio model is used, have it send the equivalent intent to the same application actions. It must not keep an independent copy of the current settings or produce a second competing content pack.

The application validates and applies the intended change, updates the visible controls, and invokes the existing skill when generation or rewriting is requested. Preserve natural-language constraints that do not fit a preset, such as “warm, lightly sarcastic, no jargon.” Keep the original request available as context, clearly distinguishing superseded settings from current ones. Do not infer the desired writing style from how emotional, loud or fast the user's microphone audio sounds.

Examples below show mappings in a content-writing context, not universal keyword substitutions:

| User action | Accepted change and behaviour |
| --- | --- |
| Types or says “Write a 45-second public-speaking script. Make it engaging and punchy.” | Set the topic, video length, Engaging style and Bold energy; generate one script and show the resolved choices. |
| Clicks Emotional, then Calm | Set those two preferences for the selected scope. Generate/Rewrite remains a separate action. |
| Says “Make this more emotional, but keep it subtle” with one script selected | Set Emotional and Calm for that script and rewrite it, preserving its facts and requested length. |
| Says “Keep it educational, just dial it down a bit” | Keep the style; reduce energy one step if possible. In a current-draft revision context, rewrite that draft. |
| Says “Use a warmer voice, without sounding sentimental” | Preserve that custom wording instruction; do not discard it merely because there is no exact preset. |
| Says “Use this tone for everything from now on” | Save the resolved preferences to that user's defaults and acknowledge the save after it succeeds. |

Treat Tone/Writing style and Intensity/Energy as label aliases. The UI may show **Tone** and **Intensity** while the skill continues to receive its existing style and energy vocabulary. Content voice and the assistant's speaking voice are separate settings: “make the script calmer” changes copy; “speak more slowly” changes audio delivery where supported. If the intended target is unclear, ask a short question.

### Resolve scope, changes and intent

Use explicit user scope first. “Only the caption” targets that asset; “all three” targets the named set. Otherwise use the clearly selected or currently discussed asset. If several drafts could be “this,” ask which one before rewriting. A fresh content request inherits current task preferences, then saved user defaults, then skill defaults. Editing one asset's tone does not silently alter its siblings or permanent defaults. Keep the UI's scope visible, for example “This script” versus “New drafts.” Save lasting preferences only when the user asks or enables that setting.

Within the same scope and setting, the latest deliberate choice wins across all channels. Changing energy preserves tone and unrelated constraints. A later button selection can supersede an earlier spoken tone choice, and a later spoken choice can supersede an earlier button selection. Distinguish untouched defaults from deliberate selections. Where equally current specific instructions cannot be reconciled, clarify only the disputed part.

All selectors for that scope must remain in agreement with that accepted choice until the user updates it. The portable component supports this by sharing one observable store between views, synchronously refreshing every connected selector after button/text/voice or host updates, and building outgoing requests from the same current snapshot. Bind all views for one draft to that store using the component's `store` property. Do not create a separate voice preference cache, reapply defaults after generation, or let `data.brief.tone` from an agent result reset the user's controls. The partner's full conversation layer must apply newly recognised preferences to this store before requesting content, and continue checking result revisions before showing or speaking completion.

Keep setting changes and execution distinct. “Set the tone to Emotional” changes preferences and receives a short acknowledgement. “Write…”, “Generate”, or “Rewrite this…” executes without a redundant confirmation once topic and target are clear. In an active draft discussion, “Make it funnier” is a rewrite request. Display or speak the resolved change briefly so the user can correct it; do not recite a form or require confirmation of every ordinary choice. Missing optional tone/intensity does not block drafting.

If the user asks what choices are available, offer the same styles and intensity levels through speech and on-screen choices. They can answer by voice, typing or clicking. A follow-up question keeps the original task pending and accepts its answer through any channel; selecting an option must not start a separate conversation or lose the topic.

### Keep voice and the screen in sync

Show Listening, Processing and Generating states only from actual application events. Interim transcription is a draft and must not start multiple generations. Accept one completed utterance as one request, with an event identity that prevents duplicate delivery from causing duplicate work. Keep recognised text visible/editable where a screen is available; direct voice commands should not require an extra click. Clarify a consequential ambiguity such as an uncertain target or a poorly recognised style rather than silently rewriting the wrong asset.

Associate work with the target asset, original copy version and the revision of its input/settings. Pause spoken playback while a new utterance is being resolved. If an accepted newer request changes the target's inputs, cancel obsolete work where supported or keep its eventual result as an older version; never replace the current draft with a stale result or speak it as current. Check delayed transcripts against the state revision they started from: a late transcription must not blindly overwrite a newer conflicting click. Reconcile clear changes and clarify conflicting ones. Provide separate handling for stopping spoken playback, cancelling generation, and ending the voice session; reuse the partner's supported interruption controls.

For voice-originating drafting requests, give a brief spoken acknowledgement and a short completion message while showing the full validated drafts on screen. “Read the script” reads the selected asset's finished copy, excluding internal labels and production notes. Do not speak raw JSON or automatically read an entire content pack. Spoken status must reflect the actual run outcome. A voice-only session can request the same readback and revisions without using the screen.

Hermes documents transcription and spoken-reply flows in [Voice Mode](https://hermes-agent.nousresearch.com/docs/user-guide/features/voice-mode) and editable/direct voice submission in its [practical voice guide](https://hermes-agent.nousresearch.com/docs/guides/use-voice-mode-with-hermes). These capabilities do not establish that the partner's custom dashboard has this shared state or routing implemented. Check the installed Hermes version and the existing audio stack during integration; this design does not require choosing a new speech provider.

### Integration acceptance examples

Verify that equivalent typed, clicked and spoken requests reach the same resolved brief and action, allowing normal model variation in generated wording. Then exercise a mixed sequence: choose Engaging/Bold with buttons, dictate a topic and generate, say “Make only the script emotional but subtle,” and type “keep it under 45 seconds.” Check that controls, current copy and spoken acknowledgement agree, and that sibling captions and saved defaults stay unchanged. Also test an ambiguous target, a corrected transcript, duplicate utterance delivery, a preference update without generation, and a slow older run completing after a newer rewrite. These are handoff scenarios; none has been executed against the custom dashboard here.

## General research

The dedicated `research-brief` package, custom research output schema and
experimental learning layer were retired on 2026-09-17 after evaluation failed
to establish a useful advantage over generic research. Hermes handles ordinary
research directly with its actual search, page-reading and file tools. The
catalogue retains the general research route with no skill binding. Do not load
the retired Markdown, emit its dashboard payload or imply that its private
learning/guard helper is installed.

The separate published n8n prospect-research operation retains its existing
ownership, state and tool contract. It was not removed or changed. Historical
research outputs remain historical records, not active schema support.

The shared installer removes only unchanged files it previously installed from
the retired package, with backups. Edited or unowned copies require manual
reconciliation; they are never silently deleted. Actual removal from an existing
partner profile occurs only when the installer is applied there while Hermes is
idle. No live partner profile was accessed by this source retirement.

## Summary / In depth toggle

Project Planner provides two reading views from one response. Use the existing
`summary` and `data` fields. Default to **Summary**, with **In depth** as the other
choice. Persist one response and switch the displayed fields; changing views
must not rerun generation or execute tasks.

| Display | Project Planner |
| --- | --- |
| Both views | Title, status and material limitations; show any infeasible original goal and essential deferred scope |
| Summary | `summary`, `data.first_action`, and planned effort versus supplied capacity |
| In depth | `summary`, goal, success criteria, assumptions, milestones, tasks by relative week, deliverables, dependencies, estimates, capacity, first action, deferred scope and limitations |

Reading depth (Summary/In depth) is independent of planning style (Broad/Detailed). Hide effort and capacity displays for broad plans in both reading views. For detailed plans, use the estimates, budget fields and calendar review to distinguish required work from work that can fit. Unknown dates and available hours remain unknown in both views. Estimates remain estimates, and `ready` means the plan is prepared. If users edit tasks, refresh the summary from the revised result before showing it again; do not pair a stale summary with changed detail.

For `needs_input`, show the questions with `data: null` and hide the detail toggle. For `partial`, keep limitations visible even in Summary; never make missing evidence or an infeasible deadline disappear through condensation.

In ordinary chat, Project Planner defaults to the condensed view. Requests can explicitly ask for `Summary only`, `In depth only`, or `both views`. JSON mode always supplies the full payload so the application can switch views without a second generation. This repository supplies the skill instructions and output contract; the toggle itself is implemented in the separately developed dashboard.

## Validate at the application boundary

Parse the response as JSON and validate it against that skill's self-contained `templates/output.schema.json` before rendering. Treat dates and source IDs as data, not instructions. The local `scripts/validate.py --output` command is a developer check; use equivalent schema and semantic checks in the actual backend.

The backend must also check cross-references, unique IDs, acyclic task dependencies, and capacity totals where applicable. Validation cannot establish that a source was genuinely read; rely on execution records and review for that. Render all model text as untrusted content and allow only appropriate external link schemes.

If a response is malformed, request a bounded repair with the validation errors (for example, one retry), or surface a clear retry state. Do not silently substitute an empty result and display success.

## Execution state belongs to the application

The backend owns run IDs, timestamps, authentication, user isolation, persistence, actual tool events, retries, and any publishing or scheduling. Derive progress indicators from observed execution events. Keep these fields separate from model-generated summaries.

Do not automatically turn a draft calendar plan into external calendar events. Installing a skill cannot provide web access, and a video script is not an edited video file. Add those capabilities through real integrations and show successful external actions only after the corresponding tool result.

No customer's profile, sources, or output should be written back into the shared skill package. Pass user context per run or store it in that user's application workspace.
