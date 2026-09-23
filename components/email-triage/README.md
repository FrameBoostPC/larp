# Email categories and saved summaries

This component updates **Email | Inbox Organiser & Reply Drafts**. Hermes owns
conversation and voice; the existing n8n owner labels incoming mail, saves
summaries and prepares cautious reply drafts.

## Video comparison

Reviewed the auto-generated transcript of Jono Catliff's
[This n8n AI Agent Will Manage Your Email Inbox](https://www.youtube.com/watch?v=l0SiFihbetA)
on 2026-09-23. Retain the existing system and integrate useful parts.

| Video pattern | Decision |
| --- | --- |
| Categories and labels, 05:39–13:24 | Add sales, promotion, social, recruitment and receipt categories, plus labels for every category. |
| Summaries in a sheet, 15:40–22:19 | Reuse saved email reviews and Hermes retrieval; no duplicate storage or extra model call. |
| Threaded personal drafts, 22:22–31:28 | Retain the existing full-message drafts and connected calendar checks. |
| Sending and forwarding, 31:37–37:01 | Keep draft review; no approved forwarding destination or automatic-send policy was supplied. |
| Polling trigger, 01:55–04:41 | Retain authenticated push intake and daily watch renewal. |

The existing system also provides durable message reservations, duplicate
protection, verified label receipts and a fixed activation boundary. A full
replacement would discard those features. The video's cost assertions were not
used as a pricing source. Prospect outreach has a separate verified-contact and
retry contract; the inbox tutorial provides no reason to replace that owner.

## Behaviour

Existing categories remain: ACTION, MEETING, FINANCE, NEWSLETTER, NOTIFICATION,
PERSONAL and OTHER. New categories: PROMOTION, SOCIAL, SALES, RECRUITMENT, RECEIPT.
SALES is an inbound customer enquiry; someone advertising to the owner is
PROMOTION. RECEIPT confirms a completed transaction; financial action or decisions
remain FINANCE. Direct human requests are not routine social notifications.

All categories have custom `Automation/<Title>` Gmail labels. Existing processed,
draft-ready, manual-review and clash labels remain. Labels follow durable review
storage; an organisation receipt requires confirmation of every expected label.
Old mail is not rescanned or relabelled; existing Gmail category tabs are untouched.

Forced review, low/invalid confidence and explicit model REVIEW take precedence
over filing. OTHER and RECRUITMENT require owner review; no candidate screening
is performed. Routine newsletters, notifications, promotions, social updates and
receipts are summarised without reply drafts. FILE means labelled, not archived,
marked read or deleted. No sending, forwarding or extra recurring job is added.

`list_reviews` accepts optional category, status, sender, subject_contains and
limit (1–50, default 20). Sender is an exact email address, normalised to lowercase;
subject_contains is a case-insensitive literal substring (maximum 200 characters).
Status is REVIEW, FILE or DRAFT_CREATED. Storage filters apply before the limit,
newest first. `get_review` retains message identity lookup. Results include
category, thread identity and counts of returned items only, with
`counts_scope: returned_items`, `may_have_more` and `live_inbox_checked: false`.
These are saved summaries, not live inbox totals.

Results include `gmail_url` for opening the original thread in the configured
Gmail account (null when no valid Gmail identity is available). Receipt attachments
stay with the original email. This neither searches attachment contents nor confirms
that an attachment exists, and opening the link does not refresh the saved review.

Examples: “Summarise saved social updates”, “Show sales drafts”, “What emails
need my review?” Actual speech/dashboard acceptance belongs to the partner's host.

## Skool template follow-up

Inspected the [Skool n8n lessons](https://www.skool.com/automatable-free/classroom/6ca29126?md=427b8f8cfce148df88830192ff00a413)
and the downloadable [Outlook email template](https://www.skool.com/automatable-free/classroom/6ca29126?md=85b36844a97b48bdb9018af8474975f1)
on 2026-09-23. The Gmail entry refers to the same video above. The Outlook
template's receipt filing is useful in principle, but its separate storage,
hardcoded forwarding destination and automatic contact creation do not fit this
Gmail owner. No Google Drive credential was connected. Keep receipts in Gmail;
make the saved reviews searchable by sender/subject and link to the originals.
This adds three parameter updates, with no extra nodes, tables or recurring jobs.

`retrieval.mjs` is the subsequent one-time migration from the inspected
category/organiser baseline. `retrievalOperations(baseline)` preserves the three
existing storage filters and adds sender and escaped literal-subject filters,
all before the limit. It reads the verified mailbox from the owner's configuration
to generate account-bound links. Do not commit generated operations or exports:
they contain account configuration. Run `node components/email-triage/retrieval.test.mjs`
and the email-review transport tests when changing it.

## Reproduce and test

`triage.mjs` provides the policy. `workflow.mjs` builds parameter-only operations
from an inspected pre-upgrade owner and preserves its graph, credentials,
triggers, calendar logic, storage and groups. It rejects an unexpected baseline.
This is a one-time migration, not an installer to rerun against an updated owner.

Keep full exports, actual label IDs and results in ignored private storage.
Discover labels with the owner's existing Gmail credential, create only missing
labels, then supply category IDs and processed/draftReady/manualReview/clash IDs.
Never copy development credentials into another customer's configuration.

1. Preserve the current published version and export the owner for rollback.
2. Generate `emailOperations(baseline, verifiedLabels)` and inspect the result of
   `applyOperations`. Run `node components/email-triage/triage.test.mjs`.
3. Run `node components/email-triage/acceptance.mjs private/email-before.json
   private/email-candidate.json private/email-acceptance.js`. It verifies the
   unchanged graph and 65 assertions against the candidate's actual Code nodes.
   The output body can run in an isolated manual n8n Code node without model or
   mailbox calls.
4. Validate changed parameters and the complete graph, save the draft, test
   filtered/unfiltered saved reads and get_review, then publish and verify.

The SDK export uses minimal sample outputs. Whole-graph validation may warn
about missing sample fields; actual fixtures and live routes verify runtime
data paths. Schema validation alone does not establish runtime correctness.

## Acceptance — 2026-09-23

Category version published: `9af78a13-6e14-4966-a4b4-627ad28419d4`.
Eight local policy tests and 65 candidate assertions passed. n8n execution 961
passed the same 65 assertions. Labels were created in execution 940. Draft
saved-data reads 962–964 covered filtered, unfiltered and identity-based reads.
Production execution 966 returned a matching NOTIFICATION review and bounded
category counts. The repository validator and 19 orchestration tests passed.
Eight operations updated the existing 63-node owner with no update-validation
warnings. Temporary setup and acceptance workflows are archived after use.

These tests do not establish model accuracy across all categories or a fresh
end-to-end incoming email run. No emails were sent for testing. Existing model,
account, enabled triggers and activation boundary were preserved. The inspected
September 23 workflow had push processing enabled; September 17 setup notes are
historical and should not be replayed as current configuration instructions.

The concurrent organiser update subsequently published only the saved-response
node as version `f9025a8e-7ad2-401e-a619-609ebfc1b93e`, adding source references and
historical/refresh flags. Inspection confirmed all six other changed email nodes
still exactly matched this migration. Its source belongs to the organiser change;
preserve those response additions in any subsequent email work.

Rollback: restore the preserved prior version, validate and publish it. Added
labels can remain; existing reviews and drafts need not be deleted.

Saved-search version published: `e3c17e62-44aa-49f7-bd5f-dbb8838c5c0c`.
Twenty policy, retrieval and response tests passed, as did the repository validator.
Cloud execution 979 verified combined sender/subject/category filters and limit
against a known saved message; 985 verified literal percent matching without
broadening to every row; 986 verified get_review and the original-email link.
Production execution 987 returned the expected filtered message and link.
Execution 983 also rejected a malformed envelope before reading storage.
Only three existing read-route nodes changed; the other 60 nodes, connections
and workflow settings match the preserved baseline. The published version was
verified equal to the draft. Browser navigation of a Gmail link and actual
Hermes speech remain host acceptance tasks; no email was sent in these tests.
