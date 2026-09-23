# Gmail push setup

The existing **Email | Inbox Organiser & Reply Drafts** workflow owns this
integration draft. Hermes remains responsible for conversation and voice; Google
Pub/Sub is the proposed source of incoming-mail events. This is not a separate
user-facing skill.

## Current observation — 2026-09-23

The live owner had a published 63-node graph, enabled push and daily-renewal
triggers, and message processing enabled. This supersedes the paused September
17 setup state below. Its account and activation boundary were preserved while
adding [category labels and saved-summary filters](../components/email-triage/README.md).
This does not independently re-verify Cloud IAM, billing or token expiry. Do not
repeat historical setup or rebind the account based on the old notes.

## Historical setup state — 2026-09-17

Gmail is the selected provider for the email prototype. The user corrected the
temporary Hotmail selection and requested continuation of Gmail setup, using the
intended Gmail account for Google sign-in and a separate **Hermes Email** Cloud
project. Google sign-in is verified, authorised first-use Google Cloud terms
were accepted with marketing unchecked, and the separate **Hermes Email** project
has been created. Gmail and Pub/Sub APIs are enabled, and the notification topic
has been created. The project's billing page explicitly confirms that no billing
account is linked; no billing or trial was enabled. The topic-only Gmail publisher
permission is prepared but not saved, pending user approval required by browser
policy. The Gmail watch remains unconfigured.

A dedicated keyless push identity has been created with no assigned project roles
or mailbox access. The existing Google-managed Pub/Sub Service Agent role was
verified to include OpenID token creation, so no extra signing grant was made.
An authenticated push subscription now targets the existing n8n webhook with
that exact URL as its audience. It uses wrapped payloads, a 60-second acknowledgement
deadline, 60–600-second retry backoff, one-day message retention, no retention of
acknowledged messages and expiry after 31 inactive days.

The user approved the `gmail.metadata` scope, which is saved in the OAuth app.
A same-project OAuth client has been created using the redirect URI verified in
n8n. The app remains in Testing with only the selected account as a test user.
The generic OAuth2 **Hermes Gmail Watch** credential form is prepared for that
scope, restricted to `gmail.googleapis.com`, with offline consent for token
renewal. Client-secret transfer, credential saving and sign-in have not occurred;
approval for that connection step is pending. Testing refresh tokens expire
after seven days, so this is not yet a permanent unattended connection.

The user requires no additional spending for the prototype. Keep message
processing paused until its cost coverage is verified. Do not link paid billing, upgrade plans
or run paid model processing without a changed spending instruction. Pub/Sub's
free message-throughput allowance is not a guarantee of zero total cost: data
transfer/storage, n8n executions and model usage are separate. Included credits
must be verified before any live test; do not assume they exist or cover overages.
The n8n dashboard currently shows 3 of 2,500 September executions used, providing
execution allowance for a bounded receiver-only test. This does not establish
model credits or authorise paid message processing.

The Gmail push conversion is saved in n8n as an unpublished 60-node draft and is
not live. Its push webhook, daily watch-renewal trigger and former 15-minute
poller are explicitly disabled pending verified setup. Its receiver configuration
rejects work until the Cloud resources,
watch credential and activation boundary are supplied. No Gmail watch has been
created by this setup pass. Preserve the draft
and acceptance evidence while completing setup. The temporary Hotmail detour did
not implement a Microsoft workflow.

Two n8n tables have been created: **Hermes - Gmail Push Mailbox** and
**Hermes - Gmail Push Intake**. The real mailbox row remains `SETUP` / `IDLE`.
Synthetic claim-test rows are separate from the configured real row. Exact
bindings and run evidence stay in ignored `test-results/gmail-push/`.

## Zero-spend configuration

The user explicitly requested a $0 limit on 2026-09-17. The Hermes Email project
remains unlinked from Cloud Billing. Its Budgets & alerts page requires selection
of a billing account, so no $0 budget was created. Do not link a billing account,
start or upgrade a trial, or enable billable usage to make a budget available.
Preserve the existing APIs, topic, subscription and keyless identity.

The subscription already limits message retention to one day, retains no
acknowledged messages, uses 60–600-second retry backoff and expires after 31
inactive days. These are resource-use controls, not financial guarantees. Do not
reduce required API quotas to zero or disable required APIs merely to display a
zero-cost setting; that would prevent the requested notification functionality.

Google's standard budgets only alert. Its spend-cap preview does not currently
cover Pub/Sub and can allow billable overages even for supported services.
The official Pub/Sub setup and Free Tier prerequisites require active billing;
successful resource creation without billing does not prove event delivery will
work. Never promise unrestricted Cloud functionality at guaranteed $0. If live
delivery is blocked by billing, report that limit and preserve the user's $0
constraint. Any future billing or spending change requires a changed instruction.
This guidance records the setup policy; it is not an IAM lock or a provider-side
spending cap. These controls concern this project, not unrelated billing accounts.

See [Google budget behavior](https://docs.cloud.google.com/billing/docs/how-to/budgets),
[spend-cap coverage and limitations](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps),
[Pub/Sub prerequisites](https://docs.cloud.google.com/pubsub/docs/publish-receive-messages-client-library)
and [Free Tier requirements](https://docs.cloud.google.com/free/docs/free-cloud-features).

## Processing contract

A notification is a wake-up signal, not the email body or a Gmail message ID.
The receiver verifies Google's rotating signing key, signature, issuer, expiry,
exact audience, service-account identity, subscription and mailbox. It records
sanitised metadata and conditionally claims the mailbox before replying 204.
A busy mailbox receives 503 so Pub/Sub retries. Bearer tokens are not put in the
intake table; restricted n8n execution history can still contain inbound headers.
Retain execution results because Hermes reads the private voice route's terminal
result through the authenticated n8n connection.

The current `receiver_only: true` gate acknowledges authenticated notifications
and releases its mailbox claim without reading Gmail message contents, invoking
a model or creating drafts. It permits receiver acceptance testing once the
remaining connection and allowance checks pass. Watch renewal still verifies
the credential's mailbox identity; a mismatch stops before renewal or recovery.

When message processing is explicitly enabled (`receiver_only: false`), each
accepted wake-up searches eligible unread, unprocessed inbox messages after
a fixed activation timestamp. It retrieves all result pages, checks current
eligibility and processes one message at a time. This deliberately uses an inbox
query rather than a history cursor. Read, archived and pre-activation messages
are outside its scope. It preserves draft-only behaviour and existing review
rules. No messages are sent, archived or deleted.

A durable REVIEW reservation precedes model or draft work. An uncertain draft
creation is never automatically repeated. Saved results can repair failed label
operations without generating another reply. Confirmed organisation receipts
remain available to Daily Review. A process crash can leave an owned mailbox
row: verify that execution has stopped and reconcile its message before releasing
the claim; never steal it solely because a timer expired.

The daily maintenance path is configured for 03:15 Australia/Brisbane
to renew the Gmail watch and recover missed events. Its trigger, the push webhook
and the old 15-minute poller are disabled.
Renewal never moves the activation boundary. A post-acknowledgement crash can wait
for recovery; an unresolved mailbox claim requires reconciliation first.

## Activation requirements

1. Use the created **Hermes Email** project and enabled Gmail/Pub/Sub APIs. Verify the
   prototype can operate within the user's no-additional-spending constraint,
   including the selected Pub/Sub configuration. Do not enable billing
   or assume that a free allowance covers every service.
2. Use the created notification topic and, after the pending approval, save Google's
   `gmail-api-push@system.gserviceaccount.com` publisher access to that topic only.
3. Reuse the created keyless push identity and authenticated subscription.
   Preserve its exact webhook audience, wrapped payload and bounded retention
   settings. The existing Pub/Sub Service Agent role supplies OpenID token
   creation; no additional signing grant is currently required. Recheck those
   bindings before activation without adding mailbox or broad project access.
4. Use the created same-project OAuth client and the prepared separate n8n
   credential for profile/watch calls. Complete the pending connection approval,
   store the client secret only in the credential store, save and authorise the
   intended mailbox with `gmail.metadata`. Preserve the existing managed Gmail
   credential used by other operations. The redirect URI is verified from n8n.
   Confirm the consent configuration supports the intended test duration;
   External/Testing refresh tokens expire after seven days.
5. Bind the real topic, subscription, push identity, audience, credential and
   fixed activation time. Confirm the credential's Gmail profile matches the
   configured mailbox. Keep `receiver_only: true` for initial acceptance. Set its
   singleton state row to READY, enable only the verified push and watch-renewal
   triggers, publish the reviewed workflow and establish the watch. Inspect its
   returned expiration; keep the old poller disabled.
6. Verify an actual Google-signed initial watch notification and repeated delivery
   release the claim without message processing. This proves receiver delivery,
   not new-mail processing. Only after identity and cost coverage are verified,
   explicitly enable message processing and test a controlled new email plus a
   repeated delivery. Confirm one review/draft at most, correct labels,
   organisation receipt, released claim and preserved voice reads.

Google requires the topic's project to match the OAuth developer project used
for `watch`, and recommends daily renewal. See the official
[Gmail push guide](https://developers.google.com/workspace/gmail/api/guides/push),
[watch API](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/watch),
[authenticated Pub/Sub setup](https://docs.cloud.google.com/pubsub/docs/authenticate-push-subscriptions)
and [n8n custom OAuth setup](https://docs.n8n.io/integrations/builtin/credentials/google/oauth-single-service).

## Acceptance evidence

- All 56 local checks were rerun successfully: 42 security/state-decision tests
  and the 14 candidate checks below. The state helpers are isolated
  models, not proof of every workflow path.
- Live n8n executions 500 and 501 attempted their conditional claims two
  milliseconds apart: exactly one succeeded; the other returned no claimed row.
- Execution 502 passed four cryptographic fixture cases in n8n Cloud. Execution
  503 also retrieved Google's current public signing keys successfully.
- 14 candidate-code/graph checks pass for the current 60-node draft. They cover
  explicit activation flags, the receiver-only gate, watch-identity failure,
  acknowledgement order, eligibility, reservations, label repair and preservation
  of the voice and organisation-receipt paths. Canvas grouping was updated without
  logic changes. Current SDK validation is valid, with a pre-existing cosmetic
  advisory about eight top-level boxes when groups are collapsed. These checks
  do not prove the new receiver has received a real notification.
- Main-workflow execution 511 returns the expected spoken `not_found` result for
  a synthetic missing email review. Execution 512 rejects incomplete push setup
  before any Gmail or table operation. These are staging tests, not event delivery.
- The temporary **Internal | Gmail Push Acceptance** workflow is archived.
- An actual Gmail → Pub/Sub → n8n → draft test remains pending Cloud setup.

Use `node --test test-results/gmail-push/pubsub-auth.test.mjs
test-results/gmail-push/decisions.test.mjs test-results/gmail-push/candidate.test.cjs`
for the local checks while those ignored run artifacts are available. Set
`PYTHON_EXECUTABLE` to the environment's Python executable for the candidate
builder checks. Repository validation remains `python scripts/validate.py`.
Prepared code, fixture success and a paused workflow are not a live deployment.
