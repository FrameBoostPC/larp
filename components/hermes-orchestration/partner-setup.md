# Connect your Hermes to the shared n8n instance

This setup installs LARP's three skills and shared orchestration instructions,
then connects your existing Hermes profile to
`https://automatedai.app.n8n.cloud`. The workflows keep running in that instance;
there are no workflow imports or new n8n installation. Operations use the
instance's existing connected accounts and shared records.

The repository is public. **GitHub access does not grant n8n access.** Sign in to
n8n with an account that can access and execute the shared workflows. The instance
owner may need to grant that access. Keep login tokens in Hermes's credential
storage, outside this checkout and chat.

## Give this to your Hermes agent

Copy this prompt into the Hermes instance your dashboard uses. It needs local
terminal/file access to run the installer. If it cannot work with local files,
follow the terminal steps below.

```text
Set up https://github.com/FrameBoostPC/larp on this computer so this Hermes
profile can orchestrate our existing shared n8n workflows at
https://automatedai.app.n8n.cloud. Use the existing connected accounts and
resources. I am joining the shared setup, not creating another deployment.

Read the repository's AGENTS.md, docs/project-context.md, and
components/hermes-orchestration/partner-setup.md before acting. Inspect the
actual files. Identify the exact active Hermes profile used by this session
and dashboard. Preserve my model, persona, existing tools and local edits.
Clone or update the public repository without discarding work, install its
Python requirements, then preview and apply scripts/install_hermes.py for
that profile with --n8n-url
https://automatedai.app.n8n.cloud/mcp-server/http. Use the installer's selected
MCP connection name. Guide me through login in the same profile if required.

After reconnecting, discover the live n8n tools and workflows. Verify the six
direct routes against their published graphs and execution permissions, and
register the discovered instance/routes using the installed settings.py.
Keep the prospect worker internal and retired workflows excluded. For Daily
Review, inspect get_setup and use connect_shared_daily_review with freshly
retrieved published metadata to join its existing configuration locally.
Do not redeploy, change account bindings, or enable scheduled collection.

Run the guide's read-only get_setup check. Preserve its request and execution
IDs, inspect the terminal result, and report installation, authentication,
route access, execution and voice readiness separately. Do not test by sending
email, creating drafts, booking time, running prospect searches or changing
Notion records. Voice and text should use the same Hermes conversation and
tools; verify actual audio on this host before calling voice setup complete.
```

## 1. Install the source and connection configuration

Hermes must already be installed. Use Python 3.10+ in an environment on this
computer; the optional MCP merge needs PyYAML. The repository requirements also
provide schema validation and timezone data. Use `python3` in place of `python`
if that is your environment's command.

```sh
git clone https://github.com/FrameBoostPC/larp.git
cd larp
python -m pip install -r requirements-dev.txt
```

For an existing checkout, pull the current `main` without discarding local work.
Choose the **exact existing active profile directory**, containing `config.yaml`.
It may be `~/.hermes`, a named profile, or a custom location. The dashboard and
gateway must use this same profile. Substitute its absolute path below and run
while Hermes is idle:

```sh
python scripts/install_hermes.py --hermes-home "/absolute/active/hermes-profile" --n8n-url "https://automatedai.app.n8n.cloud/mcp-server/http"
python scripts/install_hermes.py --hermes-home "/absolute/active/hermes-profile" --n8n-url "https://automatedai.app.n8n.cloud/mcp-server/http" --apply
python scripts/install_hermes.py --hermes-home "/absolute/active/hermes-profile" --n8n-url "https://automatedai.app.n8n.cloud/mcp-server/http" --check
```

The first command previews. Apply installs all three skills and five orchestration
resources, adds their managed policy to `SOUL.md`, and merges an OAuth MCP entry
into `config.yaml`. It preserves unrelated configuration and backs up replaced
files locally. Edited managed files stop preflight for reconciliation.
`--check` verifies local files/configuration only; it does not authenticate.

The new server name defaults to `n8n_larp`. An existing connection to this endpoint
is reused unchanged, including its auth and tool filters. Read the selected name
printed by the installer. Use `--n8n-server-name NAME` to resolve a name collision
or choose among duplicate endpoint entries. Unusual YAML is left for a local
manual merge using the [connection configuration](README.md#connect-the-existing-n8n-instance).

## 2. Complete n8n login in that same profile

In a terminal, use the selected connection name. For the default active profile:

```sh
hermes mcp login n8n_larp
```

For a named profile, select it explicitly:

```sh
hermes -p PROFILE mcp login n8n_larp
```

Complete the browser sign-in/consent. A working existing non-OAuth connection
can keep its current authentication. Match the actual profile rather than relying
only on `HERMES_HOME`: an active named profile may select another location.
Restart the dashboard/gateway's Hermes session after configuration and login.

Use the installed Hermes version's help if its CLI differs. Configuration and
login follow the official [Hermes MCP guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/).
Instance access and workflow visibility follow
[n8n's instance MCP guide](https://docs.n8n.io/connect/connect-to-n8n-mcp-server/).

## 3. Discover and register the shared routes

The new entry exposes these n8n tools: `search_workflows`,
`get_workflow_details`, `execute_workflow`, `get_workflow_execution`.
Hermes may prefix their names with `mcp_n8n_larp_`. Existing connections retain
their filters; ensure these four tools are actually visible. Workflow editing is
separate administrative work and is not needed to join this setup.

Have Hermes search the authenticated instance and inspect each direct workflow's
full published graph. Confirm its ID, `active`, `activeVersionId`, `canExecute`,
private enabled `Agent request` trigger and terminal nodes. The table is a lookup
aid, not permission or proof of current availability.

| Route key | Workflow | ID |
| --- | --- | --- |
| `project-planner` | Planning & Calendar · 01 Project Planner | `tJ6YmJuFsyEoWYXw` |
| `calendar` | Planning & Calendar · 02 Calendar & Task Manager | `rTed7PRf60fF2MjA` |
| `prospects` | Prospecting & Outreach · 01 Find Prospects | `xy4pY5ahF6DxwH9P` |
| `outreach` | Prospecting & Outreach · 03 Draft Outreach & Follow-ups | `m9qGDkh7s29y4Bef` |
| `email-review` | Email · Inbox Organiser & Reply Drafts | `PelmDAUWeW5f0gQU` |
| `priorities` | Daily Review · Priorities Digest | `Ux9xifTok0pnJRMZ` |

The research worker `iA9pVjGGi46EMVs5` is an internal dependency. Hermes calls
Find Prospects; that workflow invokes its worker. The existing planner similarly
uses the existing calendar owner. Joining requires no rewiring. Client onboarding
and standalone content repurposing are retired.

Use `<profile>/hermes-agent-skills/settings.py --hermes-home <profile>` with JSON
on stdin, through Hermes's local process tool. Read `{"action":"get_settings"}`.
Then send `update_settings` with a fresh `request_id`, the returned
`expected_revision`, and `changes` containing only the selected `instance_url`
and six verified `routes`. Each route has `workflow_id`, `trigger` and
`terminal_nodes`; use the catalogue values only after comparing live metadata.
See [settings commands](setup-contract.md#read-and-edit-settings) for the schema.

Do not copy development account credentials into this profile or run binding
plans to join an existing instance. The current workflow owners retain their
Notion, Gmail and storage connections. Saving local route preferences returns
`remote_changed: false`.

### Join the existing Daily Review configuration

Daily Review's saved retrieval route can run while its collection is paused.
An unconfigured profile may inspect it by calling `resolve_route` with
`route_key: "priorities"`, `workflow_action: "get_setup"`, and fresh full
authenticated `workflow` metadata. This grants only the setup inspection action.
Run the read-only check below and explain the returned shared setup.

For this explicitly chosen shared instance, send the local helper:

```json
{
  "action": "connect_shared_daily_review",
  "request_id": "join-shared-review-001",
  "expected_revision": 1,
  "workflow": {"...": "replace with the fresh full authenticated workflow object"}
}
```

Use the actual latest revision and a fresh request ID; the workflow placeholder
is not executable data. The helper records a local reference and hash of the
published configuration. It leaves remote accounts, storage and schedule alone.
`shared_configured` means the selection is saved locally. Call `resolve_route`
against fresh metadata before retrieving snapshots. A changed configuration or
local settings change requires reconciliation and reselection. This does not
activate collection or create a new snapshot.

## 4. Verify a real call without altering user records

Through the authenticated n8n `execute_workflow` tool, invoke the selected
priorities route with `executionMode: "production"`,
`triggerNodeName: "Agent request"`, and `inputs.chatInput` containing JSON text:

```json
{
  "request_id": "partner-check-replace-with-a-fresh-id",
  "session_id": "partner-setup",
  "revision": 0,
  "action": "get_setup",
  "arguments": {}
}
```

Generate a lowercase request ID of at most 60 characters. Retain the execution
ID and inspect `Return saved daily review` with `get_workflow_execution`; poll
that execution if still running, without submitting another copy. Verify success,
matching request/session/revision and `tool_result.data.live_sources_checked:
false`. Interpret the actual returned setup status. A configuration-only response
does not prove that a fresh review snapshot exists.

This call reads setup only. Do not exercise Gmail writes, bookings, planning
saves, prospect searches or scheduled collection as a connection test. An access
error needs n8n account/workflow permission repair; an execution error needs its
actual error investigated, not an assertion that setup succeeded.

## 5. Check the actual voice path

Ask by voice: “Check whether our daily review is configured.” Verify that the
final transcript reaches the same Hermes conversation and MCP route and that the
confirmed setup result is spoken briefly. Repeated/interim transcripts must not
dispatch duplicate calls. A text correction must use the same accepted state.

Later planning defaults to broad milestones; hours and calendar-based detailed
planning stay optional. Follow the [host acceptance cases](README.md#voice-and-dashboard-acceptance)
for planning, scheduling, corrections and interrupted speech. This package does
not install a microphone service or dashboard audio adapter.

## Verification record and remaining work

On 2026-09-17, all six direct routes were published and executable through the
owner's existing MCP connection. The internal worker was separately identified.
Production setup inspection execution **567** succeeded, reported no live source
reads, and reported Daily Review collection paused with no recurring time selected.
Private account labels and execution payloads are intentionally omitted here.

That verifies the shared service from the owner's connection. Your partner still
needs to run installation, complete their n8n authentication, check route access
and test their actual Hermes voice path. Keep those results distinct from local
installer/configuration tests.
