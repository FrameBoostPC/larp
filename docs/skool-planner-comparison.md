# Skool planner and scheduler comparison

Reviewed 23 September 2026 using the signed-in classroom, downloaded JSON
blueprints, and the current published n8n planner/calendar definitions.

**Recommendation: keep the current planner and scheduler. Adapt selected
features; do not import these templates as replacements.** This conclusion now
uses the actual workflow files, extending the earlier video-description review.
The tutorial workflows were inspected, not executed against connected accounts.

## What corresponds to our system

The expanded n8n lesson list did not show a lesson titled Project Planner.
The closest relevant resources were:

- [This n8n AI Assistant Will Manage Your Life](https://www.skool.com/automatable-free/classroom/6ca29126?md=bad8b11cac0445e4bc9465ec0da496fa):
  Manager Agent, Google Calendar Agent and Airtable Agent. This is the same
  video supplied earlier. The manager routes requests; the other two perform
  individual event/task operations. They do not implement our multi-week
  project-planning and capacity-allocation process.
- [AI Voice Agent Answers Calls](https://www.skool.com/automatable-free/classroom/6ca29126?md=9daac68aaeb44a68a2ad1ab066170064):
  the user's linked lesson, containing Vapi Calendar. This is a receptionist
  appointment scheduler, corresponding more closely to Calendar & Task Manager
  than to Project Planner.

| Area | Downloaded blueprints | Current published system | Assessment |
| --- | --- | --- | --- |
| Project planning | No dedicated goal-to-multi-week planning stage in these files | Broad/detailed plans across 1–12 weeks, task keys, dependencies and completion criteria | Keep current planner |
| Effort and capacity | Appointment durations; no project effort/capacity allocator | Detailed estimates, working windows, buffers, reserve and optional weekly cap; proposed sessions and shortfalls | Current system is more capable for this purpose |
| Task storage | Separate Airtable tasks and Google Calendar events | Shared Notion task/calendar records and stable references | Avoid a second competing task store |
| Scheduling checks | AI prompts request event lookup before changes; Vapi prompt requests availability checks | Code validates overlaps, computes slots and checks selected record state | Keep current deterministic checks; they are not a guarantee against every concurrent provider write |
| Retry recovery | Conversational memory and prompt rules; no durable per-command receipt checks visible in these files | Saved request signatures, receipts and replay/conflict handling | Keep current recovery approach |
| Contacts and attendees | Google Contacts search and an event-with-attendee tool | Notion records; no verified contact search or invitation action in the two owners | Useful additional capability, with its own provider connection |
| Priority and ownership | Low/Medium/High priority; assignee fixed to the author's name | Current live schema/route has no dedicated priority or assignee input | Consider priority next; assignee only if shared work needs it |
| Conversation | Telegram text/voice transcription, manager and specialist model calls | Hermes owns conversation and voice; bounded workflow actions | Keep Hermes; a Telegram adapter is optional, not a replacement orchestrator |

## Concrete concerns in the supplied files

1. `Vapi_Calendar.json` connects Calendar Agent to Respond to Webhook, whose
   result is a fixed invoice-success message. It does not report the calendar
   agent's actual availability, booking or cancellation result.
2. Its Helper Agent prompt requests Europe/Berlin with a fixed `-04:00` offset,
   while its example uses `Z`. These instructions conflict and do not fit the
   current Brisbane setup.
3. Its action restrictions and single-hour availability rules are in prompts;
   all calendar tools are attached to the same agent. There is no separate
   deterministic operation gate or overlap validator in this exported graph.
4. The earlier Google Calendar Agent uses
   `emailAddresses.undefined[0]` for contact email context. That mapping needs
   verification/correction. Contact results pass onward without an explicit
   zero-match/multiple-match resolution branch; direct reuse is unsuitable.
5. Airtable update maps title, notes, status, priority, assignee and ID together
   from model inputs. It has no visible stale-record token or field-preservation
   check comparable to our current scheduler. Its assignee and resource bindings
   are author-specific.

These are static findings about the downloaded versions, not claims about every
version of the creator's system or a live failure rate. Model choice and node
count alone do not establish which system works better.

## Parts worth adapting

**First: contact lookup and explicit attendee operations.** Resolve people from
a connected address book; return ambiguous matches for selection, retain the
chosen contact identity and confirmed email, and distinguish a personal Notion
reservation from an actual attendee invitation. If Google Calendar is introduced,
define which system owns meetings and how external event IDs map to Notion before
adding writes. The tutorial's capability is useful; its exact mapping is not
ready to reuse. Do not migrate existing tasks to enable this.

**Second: task priority.** If priorities are needed, add an optional priority
field consistently to the existing Notion schema, planner, scheduler and display.
Keep the user's explicit priority separate from the agent's recommendation.
Priority is currently a proposal for a schema change, not an implemented field.
Hardcoded assignees should not be copied.

**Already covered:** read before edit, retain task IDs, complete booking before
drafting its confirmation, and keep text/voice context together. The earlier
organiser update documents these patterns. Installing/testing those instructions
on the partner's Hermes host remains necessary.

No tutorial workflow was imported, executed or published during this comparison.
The existing planner/calendar versions were read only. Daily Review remains
paused at the user's request. The downloaded third-party files remain local;
they were not copied into the public repository.

## Evidence versions

Subsequent implementation selected two low-complexity features from these
patterns: task lookup by name/project/status and up to two verified same-day
alternatives for an unavailable slot. Both extend the existing calendar owner
and are documented in `components/planning-sync/n8n-calendar/README.md`.
Contact lookup has no configured Google Contacts credential in this instance;
adding invitations would require a separate meeting provider/ownership decision.
Priority and assignee properties would require a schema change. Those larger
additions were deferred to keep this implementation practical and simple.
The comparison's versions below are the pre-change evidence, not a deployment
instruction. See `docs/validation.md` for the subsequent publication.

Published planner: `574f8703-fc97-4462-9587-5a1c394ab820`.
Published calendar: `14e83f7e-3404-475a-b8f3-cf9048d284c6`.
Both matched their current drafts when inspected.

Downloaded source fingerprints (SHA-256):

- Google Calendar Agent.json: `C9BDDB23A17FE52E54D6C9172E3FF636A94DC708B52C854CDABCE35BEBB6EC4D`
- Airtable Agent.json: `AF5202B6F2765420537E4A56CCD1FB62327E69A02C59A23231E58F5D54BBAC56`
- Manager Agent.json: `C973F4F41FD2802963D5BF4C4C5A4D5F7B419B28D112E308F4CE321B54466F43`
- Vapi_Calendar.json: `C61BAA8B117B8ADF85D40ED30591CC4C67B3B67BB9460270298B2FE26E5B7B36`
