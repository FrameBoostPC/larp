# Hermes orchestration setup

This component makes Hermes the common orchestrator for Content Creation,
research, planning, calendar/tasks, outreach and future features. It uses native
Hermes instructions, skill loading and tool discovery; it adds no second agent
runtime. The public name **Content Creation** maps to the stable
`idea-to-content` skill and its existing schema.

## What is installed

- `instructions.md`: shared operating rules, embedded in a managed block in the
  selected profile's `SOUL.md` so they apply across sessions and working directories.
- `capabilities.json`: the known skill/feature mapping and observed workflow
  states. Hermes consults it, then checks live tool access; it is not a connection.
- `workflow-contracts.md`: the direct request, result, retry and action contracts
  for the current n8n instance. Read relevant sections when using those operations.
- `setup-contract.md` and `settings.py`: conversational setup instructions and
  an executable profile settings helper. Users can connect accounts, choose
  linked resources/routes and select or change their daily time after integration.
- Every complete package under `skills/`, copied into the selected profile's
  `skills/` folder, including referenced resources and examples.

The five operational resources live under `<profile>/hermes-agent-skills/`.
The installer adds their absolute locations to the policy block. Existing persona
text outside the block is preserved. Model, speech and credentials are not changed.
Optional `--n8n-url` merges one MCP connection into the existing profile config;
without that flag MCP configuration is untouched. Schema/API identifiers remain compatible.
User choices live separately in `user-settings.json`; installation and updates
preserve that file. The settings helper needs IANA timezone data (`tzdata` on
Windows). Read the [setup contract](setup-contract.md) for tool commands, source
selection, preview acceptance, activation, pause, disconnection and rebinding.
This component supplies no onboarding screen or OAuth server. The host connects
the conversation and provider consent tools; an optional settings screen can use
the same helper.

## Install on the partner's computer

For the current shared instance, start with the [partner setup guide](partner-setup.md).
It includes a copyable agent prompt, connection setup, login and live acceptance.

Use a checkout or the prepared setup bundle containing `scripts/`, `skills/` and
this component directory. Python 3.10+ is required by the installer; it uses only
the standard library for source installation. Optional MCP configuration merging
needs PyYAML from `requirements-dev.txt`. Hermes must already be installed separately.

Select the **exact active profile directory**. Default Hermes normally uses
`~/.hermes`; a named profile or `HERMES_HOME` can use a different directory.
Use the same profile as the dashboard/gateway. Do not install into a guessed
default while the dashboard uses another profile.

From the checkout/bundle root, substitute that actual path:

```sh
python scripts/install_hermes.py --hermes-home "/absolute/active/hermes-profile"
python scripts/install_hermes.py --hermes-home "/absolute/active/hermes-profile" --apply
python scripts/install_hermes.py --hermes-home "/absolute/active/hermes-profile" --check
```

The first command previews. `--apply` installs; `--check` is read-only and returns
0 when current, 1 when an install/update is needed, or 2 for a conflict/error.
Restart or start a new Hermes session afterwards. Avoid `--ignore-rules` for this
setup, because it skips context and personality instructions. A custom dashboard
must invoke the real Hermes runtime with its profile and tools; a direct model
endpoint such as the laptop preview does not load this orchestration setup.

Identical existing files can be adopted. Differing unowned files, edited managed
files or a changed policy block stop the whole preflight without overwriting
them. Reconcile those changes explicitly; there is no force-overwrite option.
Updates preserve existing files in `<profile>/hermes-agent-skills/backups/` and
record owned hashes in `.install-state.json`. The retired `research-brief`
package has an explicit migration: unchanged previously owned files are backed
up and removed on apply. Locally edited or unowned entrypoints block preflight
for manual reconciliation; unrelated notes are retained. Other removed source
files still require an explicit migration. Repeated installs are idempotent. The installer rejects
linked targets and source overlap and serialises installer instances with
`.install.lock`. If an interrupted process leaves that lock, verify no installer
is running, preserve its backups, remove only that stale lock, and rerun preflight.
The installer is not an atomic transaction against a
different process changing the profile concurrently, so update while Hermes is idle.

## Connect the existing n8n instance

The installer can perform the merge below: add
`--n8n-url https://automatedai.app.n8n.cloud/mcp-server/http` to the preview,
apply and check commands. It reuses a matching connection unchanged or creates
`n8n_larp` with OAuth, a 360-second tool timeout and the four discovery/execution
tools. It never logs in or changes remote workflows. Follow the
[partner guide](partner-setup.md) to select local routes and join Daily Review's
existing shared configuration without deploying another copy.

Keep a working connection if one is already configured. Otherwise copy the exact
instance-level MCP URL from n8n's MCP settings for `automatedai.app.n8n.cloud`.
For this instance, the expected endpoint is
`https://automatedai.app.n8n.cloud/mcp-server/http`; verify it in the owner's settings.
Use an authenticated n8n account with access to the shared workflows. In the active Hermes profile's `config.yaml`,
merge this named entry into the existing `mcp_servers` mapping, preserving others:

```yaml
mcp_servers:
  n8n:
    url: "https://automatedai.app.n8n.cloud/mcp-server/http"
    auth: oauth
```

Do not overwrite a different existing `n8n` entry; keep it and use a distinct name
for this instance. Complete the official Hermes MCP login for that same profile,
then restart the session and check discovered tools/workflow execution permissions.
For a named profile the documented form is
`hermes -p <profile> mcp login n8n`; for the default profile use
`hermes mcp login n8n`. Follow the installed Hermes version's help if it differs.
The catalogue `hermes mcp install n8n` recipe may configure a different integration;
it is not a substitute for verifying this exact connection.

All six direct routes were verified published and executable on 2026-09-17:
project planning, calendar/tasks, prospect research, outreach drafts, saved email
reviews and Daily Review. The prospect worker remains internal; repurposing remains
archived. Check live access from the partner's own authenticated connection.

Daily Review retrieves saved source snapshots for Hermes to compose the briefing.
Its collection is paused and the daily trigger remains disabled, with no recurring
time selected. Its published calendar read extension uses the existing Notion
owner. The installer does not enable collection or change Gmail push processing.
Use the [shared setup guide](partner-setup.md) to join its existing configuration.

Other resources use the actual Hermes host's connected file, search, browser,
media and account tools. Discover them per goal and authenticate when needed.
This package does not supply social-account creation or publish posts on install.
Each service operation needs a working supported tool; reuse existing connections.
Use the profile settings helper to select actual instance/workflow bindings for
each customer's environment. Catalogue IDs describe the development instance;
they are not inherited as a new customer's account configuration.

## Voice and dashboard acceptance

Voice and text must reach the same Hermes conversation, tools and accepted state.
The audio layer submits final transcripts only; users need no workflow selector
or follow-up button. The host keeps current source/assets/preferences, targets,
request IDs and revisions. It rejects duplicated delivery, suppresses stale
responses after corrections, and speaks short confirmed results. Full outputs
remain available on screen. Readback uses accepted copy without regeneration.

Exercise these on the real host with its intended model and connected tools:

1. A spoken content goal loads `idea-to-content`, obtains available sources and
   creates the requested platforms' drafts without a repurposing keyword.
2. A broader launch continues through authorised connected actions and retains
   useful drafts/pending steps when one account needs access. Draft-only limits hold.
3. Project planning calls its configured owner once. A later clear scheduling
   request uses current tasks and state tokens without duplicating the plan.
4. Text and voice corrections share the latest state. Interim or repeated speech
   creates no duplicate write; an old result is neither displayed nor spoken.
5. Stop-speaking, stop-work and undo are handled distinctly. Unknown external
   results are reconciled; paused/internal/retired workflows are not dispatched.
6. A new session loads the shared policy and skills. Tool failures or missing
   sources produce an honest partial result and one essential question where needed.

Local validation and staging installation do not establish native Hermes audio,
model quality, dashboard integration or account access. In particular, previous
local gpt-oss:20b repurposing runs failed fidelity checks; evaluate the intended
deployment model before relying on those drafts.

## Future features and maintenance

Add a skill only for reusable expertise that helps the task. Use direct tools
for straightforward operations and a workflow for an operation with useful
repeatability, state, triggers or recovery. Keep Hermes as the sole owner of the
conversation and cross-feature goal. Do not force every task through n8n.

Add the skill/feature to `capabilities.json` and define natural-language examples,
required resource roles, execution ownership and an honest lifecycle state.
New workflows expose bounded direct actions and a concise spoken result; document
identity, current-state checks, receipts, retries and cancellation where relevant.
Keep schemas stable or supply a deliberate migration. Test representative voice
and text requests, useful partial results and recovery before claiming readiness.

`python scripts/validate.py` in the full repository also checks catalogue coverage
and lifecycle/route consistency. `python scripts/validate_orchestration.py` runs
that catalogue check alone. Neither executes prompts or connects providers.
Installer checks are in `tests/test_install_hermes.py` and `tests/test_install_n8n.py`;
shared-instance checks are in `tests/test_shared_n8n_setup.py`; registry checks are in
`tests/test_orchestration.py`; setup checks are in `tests/test_hermes_settings.py`.
Re-run the installer after an accepted source update.

Organiser sequences are in the installed `workflow-contracts.md`: capture a
source email as a task/project, resolve contacts from real tools, and coordinate
booking with reply drafting while retaining separate receipts. Run
`node components/hermes-orchestration/email-review.test.mjs` for the saved-review
transport checks. `email-review.mjs` generates the existing n8n return-node code;
it is deployment source, not another host tool. Exercise `organiser-cases.json`
on the partner's actual Hermes host before claiming conversational acceptance.

## Verified upstream configuration

The profile policy and tool setup follow official
[Hermes context files](https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files/),
[Hermes MCP configuration](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/)
and [n8n instance MCP documentation](https://docs.n8n.io/connect/connect-to-n8n-mcp-server/).
Project `AGENTS.md` alone is scoped to a working directory; the managed profile
policy supplies the broader behaviour requested here without changing Hermes core.
