# Organiser integration review — 23 September 2026

Follow-up: the signed-in Skool classroom subsequently provided the actual
manager, calendar, task and receptionist scheduler JSON files. See the
[direct blueprint comparison](skool-planner-comparison.md) for the stronger
source evidence, concrete defects and recommended additions. The earlier video
transcript limitation below remains accurate, but no longer limits the workflow
comparison to descriptions and summaries.

## Decision

Keep the current email, planner and calendar owners; integrate the useful
coordination patterns into Hermes. Replacement is not justified by the available
evidence. The existing inbox has authenticated push intake, durable processing
claims, draft reconciliation, meeting-time resolution and calendar checks. The
planner already shares Notion task identities with the calendar owner. Replacing
these with a tutorial assistant would require reimplementing those protections.

## Source and limits

Reference: Jono Catliff,
[This n8n AI Assistant Will Manage Your Life (Automate Everything)](https://www.youtube.com/watch?v=iEzr0GdFitU),
published 17 February 2025. The creator's YouTube description and chapter list
were read directly. Relevant chapters: calendar/email demonstration at 3:54,
tasks at 5:17, main assistant at 8:56, calendar build at 23:56, Gmail at 27:09,
and Airtable at 28:04.

YouTube transcript export returned unavailable and the transcript panel did not
load text. The [indexed summary](https://videohighlight.com/v/iEzr0GdFitU)
was used as secondary evidence, not as a verified transcript or blueprint.
It describes a central assistant, shared input handling, remembered record IDs,
contact lookup and coordination across email/calendar/task tools. These are
design patterns to adapt, not evidence of production reliability. The exact
tutorial implementation was not imported or executed.

## Comparison and integration

| Area | Existing evidence | Decision |
| --- | --- | --- |
| Conversation and voice | Hermes already owns conversation, final transcripts and tool dispatch | Keep; add explicit organiser sequences in its installed contract |
| Incoming email | Published push pipeline, claims, draft-only replies and calendar checks | Keep; improve saved review references used for follow-up work |
| Planning | Broad/detailed plans and shared task saves already exist | Keep one planner; route email-derived projects through it |
| Calendar and tasks | One Notion database, current-state edit tokens and retry receipts | Keep; no Airtable/Google Calendar migration |
| Follow-up context | Initial saved output omitted thread/category; the concurrent Email automation task now adds them and category/status filters | Preserved those additions; published source references, age and refresh requirements |
| People by name | No contact-search operation exposed by these workflow routes | Specify grounded lookup when a host tool is connected; do not claim a new connection |
| Booking plus reply | Operations have different owners and can finish partially | Record booking receipt first; resume only failed draft work |
| Invitations/calls | Notion entries do not send attendee invites; no calling integration verified | Leave as explicit capability gaps, not implicit new features |
| Documents and social publishing | Adjacent to the user's organiser/email request | Preserve existing owners; no new publishing, upload or calling service |

## Delivered scope

The source changes update the Hermes operating policy, capability catalogue,
workflow contract and nine behavioural acceptance cases. They describe email-to-task
and email-to-project capture, contact disambiguation, current source checks,
booking/reply ordering and recovery after a partial result. These instructions
use existing tools and still require installation and acceptance on the partner's
Hermes host.

`components/hermes-orchestration/email-review.mjs` supplies the improved return
node for the existing saved-review route. Its seven offline tests cover source
identity, legacy rows, empty versus failed reads, duplicate/mismatched records,
unknown timestamps, category-filter compatibility and the exact deployable wrapper. It does not add a model call,
send mail, create tasks, alter watch settings or change stored reviews.

Deployment status and test results are recorded in `docs/validation.md`. Keep the
existing workflow version history for rollback; revert just the return node if
later unrelated changes have been made. No historical email records need migration.

Integration checks also found and corrected an existing planner formatter
fallback that converted broad weekly targets into implicit deadlines. The
published correction preserves null deadlines while retaining target weeks,
explicit deadline validation, existing task identities and detailed scheduling.
Daily Review remains paused at the user's explicit choice.
