---
name: project-planner
description: Turn goals into broad project timelines or optional detailed time plans, and review progress using shared tasks and connected calendar availability.
metadata:
  version: "0.3.1"
---

# Project Planner

## When to use

Use for a launch, personal project, learning goal, or content campaign that needs milestones and an achievable sequence of tasks. Produce a plan the user can begin today. Hermes handles research questions with available tools; this skill can list unresolved research as a task without pretending it is complete.

Hermes owns the goal, conversation, retrieved context and tool routing. Accept completed voice requests like text; users need not choose a workflow. If the connected n8n planning route owns generation, send the resolved brief once and use its returned plan; do not also generate a competing local plan. Apply this skill's drafting procedure when the host assigns planning here. Reuse accepted plans for follow-ups; reads, saves, status, edits and retries use the owning integration rather than another planning model.

## Inputs and defaults

Use the user's goal, desired outcome, planning horizon, deadline, existing progress and constraints. Available hours are optional. Reuse relevant context already provided in the conversation. A title alone is enough to start when the outcome is understandable.

If there is no identifiable goal, ask one concise question and return `needs_input` in JSON mode. Otherwise state reasonable assumptions and produce a useful first draft. Missing dates, timezone, or budget do not block a relative plan. Keep unknown dates and available hours null; never silently invent a calendar date or treat an assumption as a user commitment.

### Planning detail is a separate choice

Use **Broad timeline** by default. The user can turn **Detailed time planning** on or off through text, voice or the host's control; preserve that accepted choice across reviews. A request for estimates, hours to set aside, or work sessions selects detailed planning unless the user explicitly keeps it off. Merely supplying a deadline or mentioning a calendar does not select it.

- **Broad timeline (`broad`):** organise deliverables into week-level targets across the requested horizon, including a month or several months. Show what should be finished by each week and the dependencies. Set task `estimated_minutes` to null. Do not generate hours, effort totals, daily work sessions or a capacity calculation. Keep any supplied time limit as context without claiming the unestimated plan fits it. Dates and weekly targets remain proposals.
- **Detailed time planning (`detailed`):** estimate task effort, show the total and the amount of time to set aside, and compare it with calendar capacity where the host provides access. A supplied weekly or total hours budget remains optional. Estimates describe expected work, not an exact guarantee of completion time. Read [detailed planning and calendar review](references/detailed-planning.md) when using this mode.

Changing planning detail does not create, move or remove calendar blocks, reset task progress, or change the user's **Summary / In depth** reading preference. Both reading views work with either planning mode. Turning detail off stops future hourly planning; existing estimates and bookings in persistent task records remain untouched unless the user asks to edit them.

## Procedure

1. Describe the outcome and observable completion criteria. Separate what the user must produce from hoped-for results: publishing a portfolio is a deliverable; getting hired is not a guaranteed result.
2. Identify existing work, dependencies, and constraints. Preserve user-selected tools and scope. Do not expand a simple project into a business strategy, extra platforms, or unrequested purchases.
3. Break the work into milestones with a clear `done_when`. Give each milestone a target week within the requested horizon and tasks with tangible deliverables. In broad mode, a month-long plan can cover week-one research, week-two drafting, week-three testing and week-four completion without daily or hourly detail. For longer projects keep later work coarser; use `deferred` for scope outside the plan, not to discard the requested later weeks.
4. Assign tasks to relative weeks, starting at 1, and set `horizon_weeks` to cover the proposed horizon. Without a start date, a week means a consecutive seven-day planning block, not a named calendar week. If converting a month into four relative weeks, say so; a dated calendar month may span five planning weeks. Respect dependencies and sequence tasks in executable order. Record a supplied repeating weekly allowance in `time_budget_hours_per_week` and a supplied one-time allowance in `time_budget_minutes_total`; leave unknown budgets null. In detailed mode estimate the work needed to achieve the goal, even when it exceeds those budgets or reviewed availability. Compare required effort with capacity and show the shortage; do not lower estimates or silently remove work to make the goal appear to fit. In broad mode preserve explicit limits without inventing estimates to prove feasibility. Explain changing or time-limited allowances and never presume future capacity.
5. For an infeasible deadline, known capacity shortage or conflicting constraints, return `partial` with a clear limitation. In version 1.1, retain the required-work estimate and explain which work can fit, what is contingent and which scope/time decision is needed; proposed weeks are targets, not a feasible booking guarantee. Offer a smaller scope or later target without silently adopting it. If the user chooses a feasible subset, record the omitted scope in `deferred` and estimate that accepted subset. At zero capacity retain useful required tasks and estimates, state that none can be allocated under the current allowance, and make the first action a time/scope decision. A broad plan with a known zero-hour limit is also partial, while its estimates remain null. Legacy version 1.0 retains its original capped-task contract: tasks must fit supplied budgets and a zero budget leaves tasks empty.
6. Finish with one concrete first action. If capacity is zero, make that a decision about time or scope. For a normal plan, tie it to the first unblocked task.

## Output

Prepare one coherent plan with two reading views: **Summary** and **In depth**. Derive the summary from the complete plan, preserving its goal, scope, constraints, estimates, and status. The views are different levels of explanation, not independent plans.

- **Summary:** normally two to four plain-language sentences covering the outcome, main stages, and any decisive assumption or limitation. Aim for roughly 60–100 words when useful, but use less for a small or blocked request. Include one concrete first action. In detailed mode also include planned effort and the verified or unknown capacity; broad mode gives weekly targets without hourly totals. When the full goal is infeasible, say so and name the feasible subset; do not hide deferred essentials behind the detail view.
- **In depth:** explain the goal, completion criteria, assumptions, milestones, tasks by week, deliverables, dependencies, deferred scope, limitations, and first action. Include effort/capacity totals only in detailed mode. Explain choices or tradeoffs where useful. A longer broad view gives more reasoning and deliverable detail without switching hourly planning on.

In ordinary chat, default to Summary. Respect requests for Summary only, In depth only, or both; label both sections when both are requested. Missing dates or capacity stay unknown in both views. A longer answer must not invent a more detailed calendar or additional available hours.

For voice, Hermes gives a short result or essential question from the accepted plan and confirmed tool outcome, retaining material limits. Keep the full plan available for display or requested readback; do not add speech fields or read raw JSON aloud.

When the user or calling application explicitly requests dashboard JSON, JSON mode, or structured output, load [the output schema](templates/output.schema.json) and return only one JSON object matching it, without Markdown fences or commentary. Always include both reading views in that single result: use the existing top-level `summary` for the condensed explanation and `data` for the complete plan. Do not add parallel answer objects or regenerate the plan when the reader changes views. The dashboard adds `data.first_action`, shows computed capacity totals only in detailed mode, and keeps status and material limitations visible in either view. For `needs_input`, return questions with `data: null` rather than fabricating two views. The [broad monthly example](examples/broad-month-output.json) uses version 1.1 with null estimates. The preserved [legacy detailed example](examples/example-output.json) shows a version 1.0 two-week project with three hours available each week; its names and estimates are examples to adapt, not defaults.

Envelope rules: new outputs use `schema_version: "1.1"`; `skill` is `project-planner`. The schema continues to validate legacy 1.0 outputs unchanged. Version 1.1 requires `data.planning_mode`, `data.horizon_weeks` and each milestone's `target_week`. Broad estimates are null; detailed estimates are positive integer minutes. `calendar_review` is optional and follows the linked detailed-planning contract. `ready` means the requested plan is prepared, not that tasks were executed or capacity was guaranteed. `partial` means useful planning was possible but a material constraint or missing dependency remains; supply at least one limitation. `needs_input` requires a question and null `data`. For `ready`, keep questions empty. Missing hours alone does not make a broad plan partial or require a clarification loop.

Every proposed task has a unique ID, a valid milestone ID, and only existing predecessor IDs. No circular or self dependencies. A predecessor's week must not be later than its dependent task's week. Every task in this proposal starts with `status: planned`; this is not a command to reset an existing task's progress. A ready plan contains at least one actionable task. Use ISO `YYYY-MM-DD` dates only when supported by the user's context. A timezone is only needed when resolving actual calendar times; this skill does not schedule times.

## Weekly review and calendar handoff

When reviewing an existing project, read the latest shared task state through the host's available integration before proposing changes. Reuse its stable project identity and task identities. Account for actual progress, blocked tasks, due dates, dependencies and existing calendar commitments when choosing work that fits this week. Reconsider unfinished work; do not automatically carry it forward or reopen completed work. If shared state is unavailable, use the supplied progress and state that the review has not been checked against Notion or the calendar.

Keep the proposed planning result separate from persistent task state. IDs such as `t1` identify proposed tasks within a stable project; the host owns the mapping to persistent task UUIDs and provider record IDs. Preserve known planner IDs across reviews and allocate new ones only for new tasks. Never match tasks by title alone, invent provider IDs, or reuse an ID for a different task. Importing the same accepted plan again must reuse its project/task mapping and run identity. Leaving a task out of a new plan does not delete or cancel it.

Check the host's supported contract before import. A legacy 1.0 importer that requires integer estimates cannot import a broad 1.1 plan. Do not coerce null to zero, fabricate estimates or silently switch modes to satisfy it. Use a host that supports broad tasks or report that the save needs that capability. The repository's optional Python planning-sync prototype still requires integer estimates; it is not the owner of the existing n8n/Notion integration.

When the user authorises saving or scheduling, route the accepted plan through the host's shared planning-sync integration, if available. The host imports new tasks, preserves existing task state and returns persistent task IDs and current revisions. Changes to existing tasks must be explicit field patches against those revisions; a regenerated plan must not overwrite newer edits, status or times. Use the current user request to identify changed fields. If the integration is unavailable, deliver the plan and explain which requested saves remain pending; a portable skill does not install the sync service or connect accounts.

Detailed planning first reads calendar availability through the host's calendar review/scheduling workflow (or `calendar-planner` in review mode when installed); it does not require persisting tasks to review free time. For an authorised booking, pass persisted tasks, current revisions, dependencies, existing commitments and confirmed availability to the same workflow. A deadline or due date is not a booked appointment. Relative weeks, estimates and the detail toggle never create calendar events. Require an exact date, start/end times and timezone before scheduling, and preserve other task fields when moving a time block. The calendar workflow writes through the same shared task integration so Notion and the calendar refer to the same task.

Sync state and execution results are separate from the proposed plan. Report created, updated, pending or conflicted records only from actual host results. A task becomes completed only through explicit progress input, never because its calendar event ended. Removing a linked calendar event unschedules its task; completing or cancelling a task removes its active focus event. Unrelated calendar events, invitations and recurring series remain outside this workflow.

## Tools and limits

No external tools are needed to draft a plan. Read user-supplied files only when available and relevant. If a choice depends on current prices, availability, or platform rules, verify it with an available research tool or mark it as a research dependency. Do not claim current facts from memory. Use only actual tools exposed by the host; no tool is provided by this skill itself.

The output proposes work. Drafting alone does not authorise calendar events, purchases, contacting people or marking tasks complete. Execution explicitly requested in the accepted goal may proceed through connected tools under the host's permissions without a separate follow-up command. Do not claim actions happened without a successful tool result.

## Verification

Before returning, check that tasks advance the goal, preserve explicit constraints, have actionable deliverables and fit the selected horizon. Check IDs, dependency order, target weeks and any supplied deadline. In detailed mode check effort totals against supplied budgets and reviewed calendar capacity; in broad mode check that estimates remain null and no capacity guarantee is implied. Compare the summary against the full plan: mode, scope, dates, feasibility and first action must agree. Confirm that deferred work is visible and the first action can actually be taken. Validate JSON against the schema when a validator is available; otherwise do not claim automated validation ran.
