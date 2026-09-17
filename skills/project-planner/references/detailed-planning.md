# Detailed planning and calendar review

Use when the user selects detailed time planning or asks how much work and time to
set aside. This is separate from both the reading-view choice and permission to
book calendar events.

## Estimate the work

Estimate unfinished tasks from their deliverables, dependencies, scope and known
progress. Show task estimates and their sum, label uncertainty, and keep supplied
weekly/total time limits separate from estimates. Unknown capacity stays null; it
does not become zero or a made-up weekly budget. Suggest how much time to set aside
and a feasible sequence even when the user has not supplied an hours allowance.
Avoid false precision: a 90-minute estimate is a working estimate, not a promise.
For version 1.1, keep the full required-work estimate when capacity is smaller or
zero. Return partial with the shortage and a time/scope decision; do not silently
discard tasks, lower estimates or represent required work as zero. Only revise the
estimated scope when the user chooses the smaller goal. A proposed task list is
not an allocation of all that work into the available calendar.

## Review actual availability

Read current commitments through the connected host calendar review/scheduling
workflow, or the calendar-planner skill's review path. Reuse existing connections
and report which calendars and period were checked. The existing n8n setup reads
Schedule & Tasks pages displayed in Notion Calendar; do not assume it also sees
other calendars the user has not connected.

Use the user's current or saved workdays, working-time windows, timezone and break
preferences. An empty calendar is not evidence of 24 free hours per day. If working
windows are unknown, continue estimating but leave capacity unknown and identify
the missing windows. Any suggested work-window assumption must be labelled and
must not support a claim of verified capacity.

Within each confirmed working window, subtract the union of overlapping busy
intervals, account for all-day blocks according to the source's semantics, and
reserve the configured breaks/buffers. Count a busy interval only once. Respect
timezone/DST transitions, recurring-instance coverage and unavailable or truncated
source ranges; disclose incomplete coverage. Do not call a partially checked
period free. For a multiweek plan, review the full horizon or identify the portion
that was checked.

Existing project work sessions already consume calendar capacity. Account for
their usable allocation once, and compare the remaining unscheduled effort with
the remaining free capacity. Do not subtract a booked task's effort from free time
a second time, or count an ended session as completed work. Account for task
dependencies, fragmentation of gaps and realistic breaks when suggesting sessions;
a total number of free hours alone does not prove a task can fit in a suitable gap.

If the work exceeds capacity, show the shortage and offer a smaller scope, later
target, or user-chosen availability change. Never silently stretch the user's
working day. Refresh relevant task/calendar state before actual booking and check
for new conflicts. A review and a detail-toggle change produce no calendar writes.

## Version 1.1 review summary

`data.calendar_review` may be omitted or null when no review is relevant. Otherwise
include one object with the fields defined in the output schema:

- `status`: `checked`, `partial`, `unavailable` or `not_requested`. `checked` means
  the stated sources, period and confirmed windows were reviewed, not that work fits.
- `checked_at`, `timezone`, inclusive `window_start`/`window_end`, and `sources`
  identify actual coverage. The source labels describe the calendars really read.
- `working_windows` uses ISO weekday 1 (Monday) through 7 (Sunday), with same-day
  `HH:MM` start/end (`24:00` is allowed only for an end). Split an overnight window
  at the day boundary before review.
- `buffer_minutes` is the reserved break allowance per working window; additional
  travel or event-specific buffers may reduce availability further.
- `available_minutes` is remaining free capacity after busy time and buffers.
  `already_allocated_minutes` is usable time already assigned to this project's
  remaining work. `unscheduled_effort_minutes` is the remaining effort not covered
  by that allocation. `shortfall_minutes` is
  `max(0, unscheduled_effort_minutes - available_minutes)` when both are known.
- `limitations` names missing calendars, windows, dates, incomplete reads or other
  uncertainty. Unknown values remain null. An unavailable/not-requested review must
  not contain numeric availability or a claimed zero shortage.

A positive shortfall makes the detailed plan partial; retain the required-work
estimate and make the tradeoff visible. If calendar-backed recommendations were
requested but cannot be verified, report partial with estimates and that limitation.
Do not fabricate provider access to turn the review status into `checked`.
