# Project context

Updated: 2026-09-17.

## Current business model

Build a working Hermes-based agent, its dashboard/UI, and useful add-ons, skills, and workflows. Demonstrate the setup and its results on social media. Sell a course that teaches buyers how to create the same setup and add-ons themselves.

The primary paid offer is the course. This replaces the earlier plan to sell the agent itself as a plug-and-play product.

The intended audience is people discovering AI through social media who want to take part and build a setup like the one demonstrated. The advanced visual presentation is intended to attract interest; working demonstrations show what the setup actually does.

## What we are building

- A Hermes agent with a visually distinctive dashboard and UI.
- Useful skills and workflows, including content creation, research, and planning, with further add-ons to develop.
- Text, button and voice interaction with the same tasks and preferences. Users should be able to dictate a request, select or change writing tone/intensity through any of these inputs, and move between them during revisions.
- All selectors for the same draft must reflect one accepted selection. A user's choice through any input remains authoritative until deliberately updated; older transcripts, defaults or model output must not silently replace it.
- A reproducible setup that can become the basis for course lessons and demonstrations.

The partner is building the Hermes agent and dashboard on their computer. This laptop holds the shared skills repository and local prototypes. The partner pulls the repository to integrate and test the skills with Hermes.

The shared [Hermes orchestration component](../components/hermes-orchestration/README.md)
now provides installable profile instructions, a capability catalogue and direct
workflow contracts. Its installer applies all skills and a managed policy block
to the exact active Hermes profile while preserving existing persona/configuration.
The user requested a tested installer for the partner's computer, not a new local
Hermes runtime. Native host/audio acceptance remains on that computer.

The partner has chosen to use the existing shared n8n Cloud instance on their
own computer. The [partner setup guide](../components/hermes-orchestration/partner-setup.md)
provides a copyable prompt, optional MCP configuration installer and read-only
acceptance. It joins the existing workflow owners and Daily Review configuration
without importing workflows, rebinding accounts or selecting a recurring time.

The public content feature is **Content Creation**, implemented by the stable
`idea-to-content` skill. Across every feature, Hermes owns the goal and
conversation; skills guide domain work; connected tools and bounded workflows
execute operations. Direct tools remain suitable for simple tasks. Future
capabilities follow the same model and must be registered in the catalogue;
repository validation checks skill coverage and voice/route consistency.

Idea to Content owns both original content creation and repurposing of supplied
source material. Prompts and voice requests select the task without a separate
repurposing app or required form. The standalone n8n **Starter 06 - Content
Repurposing Drafts** workflow was archived on 2026-09-16; its historical Workbench
records remain. Use the [combined content contract](integration.md#idea-to-content-creation-and-repurposing)
for source context, follow-up revisions and concise spoken results. The local
preview exercises prompt/final-transcript routing; production Hermes speech,
conversation state and any persistent draft saving remain the partner's integration.

Keep local mockups minimal in text and easy to redesign. Presentation files should stay separate from the working controls and shared state so the partner can adapt the appearance to their dashboard while retaining the features.

Shared input routing, synchronised preferences and concise spoken responses are specified in the [integration guide](integration.md#text-buttons-and-voice-share-one-request). A [portable content-preferences component](../components/content-preferences/README.md) provides local tone/intensity selectors, a shared preference store, simple typed commands and optional browser speech capture. Its generation prototype calls a configurable model using the Idea to Content instructions and shows actual drafts. The initial local model is OpenAI's open-weight gpt-oss:20b through Ollama; the partner chooses their eventual model/provider independently. The partner still connects the skills and controls to the actual dashboard, full conversational router, speech service and Hermes runtime. The laptop prototype calls a model directly and does not run Hermes itself.

## Direction for future work

**Design every new or changed workflow for voice first.** Hermes should call a
direct tool action, carry the current task and preferences into follow-up requests,
ask only for essential missing details, and return a brief spoken result alongside
the full screen result. Forms are an optional access path. Apply the shared
[voice-first workflow standard](integration.md#voice-first-workflow-standard)
to planning, scheduling and future workflows. Keep speech and conversation in
Hermes; n8n owns the bounded operation and its confirmed result. This is a standing
project requirement, including when the current request does not mention voice.

**Pursue the user's outcome with as much autonomy as the available tools allow.**
Infer and complete ordinary necessary substeps from a clear goal, reuse known
context, and continue independent work when one step is blocked. Do not make the
user name skills, select repurposing modes or request every routine action.
Respect explicit scope limits and ask only for essential missing input or a
consequential decision that the goal does not resolve. Report external actions
from verified results. The host owns the overall goal and may combine skills,
direct tools and n8n operations; see [goal execution](integration.md#goal-execution-and-autonomy).

Prioritise automations that respond to events or schedules and solve repeated
tasks, including automatic email responses and the existing planning/scheduling
integration. On-demand email drafting belongs in Hermes with the required email
tools and optional Markdown instructions for writing preferences. It does not
need a dedicated app or workflow. The separate drafting prototype has been
removed; its Gmail bridge is archived. Client onboarding is obsolete and removed
from the current product/workflow set. Its archived n8n definition and earlier
test records are historical only; exclude it from current workflow inventories
and integration plans.

The existing n8n workflows own the current planning/calendar integration:
**Planning & Calendar | 01 - Project Planner** connects to
**Planning & Calendar | 02 - Calendar & Task Manager**, which already uses
**Notion account 2** and the **Schedule & Tasks**
data source. Notion Calendar displays the same database pages. Task creation,
intentional edits and scheduling use those shared pages; this setup needs no separate
Google Calendar or Outlook provider. The planner offers a broad timeline by default
and optional detailed time planning across 1–12 weeks. Detailed mode estimates
required effort and reviews calendar gaps within editable working windows, with
buffers and an optional weekly limit. Suggested sessions need a deliberate
scheduling action. Both workflows were live-tested and published; the mode update
was published on 2026-09-16. Direct agent routes with concise spoken results,
current-state edit checks and calendar retry receipts were also tested and
published on 2026-09-16. Actual Hermes voice integration remains the partner's
handoff. See the [integration guide](integration.md)
for its contract and the [validation notes](validation.md) for results and publication
status.

The direct agent contract covers six published workflow routes: project planning,
calendar/tasks, prospect research, outreach drafts, saved email reviews and Daily
Review. Their publication and execution access were checked through the owner's
MCP connection on 2026-09-17. The prospect worker remains internal. Workflow names
use shared group prefixes and role numbers. Content Creation uses the skill;
standalone content repurposing and client onboarding remain retired.

Daily Review prepares source snapshots and lets Hermes compose priorities,
decisions, meeting preparation and follow-ups. Its published retrieval route can
read saved snapshots while collection is paused. No recurring time is selected;
the daily trigger is disabled. The calendar's internal read extension is published.
The installed [setup contract and helper](../components/hermes-orchestration/setup-contract.md)
support explicitly joining this existing configuration locally, as well as later
account/resource/time setup through the separate deployment contract. Joining
does not change the shared email push workflow or other owner bindings. Source
freshness and coverage must remain visible. The partner must verify authenticated
access and actual Hermes voice/dashboard operation on their own host.

The portable Python [task/sync component](../components/planning-sync/README.md)
remains an optional separate prototype. It implements persistent task state,
revision checks, Notion reconciliation and a provider-neutral calendar bridge,
but it does not run the existing n8n connection. Its Notion property schema differs
from Schedule & Tasks. Do not run it against that database without an explicit
migration and compatible configuration; its standalone deployment requirements do
not mean the existing Notion/calendar setup is missing.

Keep skills portable and useful across different user ideas. Build examples that are clear to demonstrate and document the setup steps, dependencies, inputs, and outputs needed to recreate them. When drafting marketing for this project, centre the offer on learning to build the demonstrated setup.

The dedicated Research Brief skill was retired on 2026-09-17: token and latency
optimisation reduced its overhead, but testing did not establish a useful research
advantage over a generic assistant. Hermes handles general research natively with
available tools. The separate n8n prospect-research workflow remains unchanged.
The experimental helper, learning state machinery and research schema are no
longer active packages. See the [retirement record](validation.md#research-skill-retired--2026-09-17).

The course price, curriculum, delivery platform, included source files, and support arrangements have not been specified. Current implementation and testing status is recorded in [validation notes](validation.md).
