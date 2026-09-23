# Validation notes

## Deferred onboarding and editable bindings — 2026-09-17

The [setup contract](../components/hermes-orchestration/setup-contract.md) and
profile settings helper are installed alongside the orchestration catalogue.
Users can defer setup, resume it later, skip sources and change connections,
resources, routes and daily timing. The helper saves local preferences and
prepares bounded binding plans; authenticated host tools apply and verify them.
No onboarding UI or OAuth server is supplied. Actual Hermes conversation,
provider consent and new-account live acceptance remain on the partner's host.

Daily Review draft `becc1077-1bc9-47d2-9cc7-532035366d6b` has 30 nodes in three
groups, is unpublished, and remains `setup_required` with the schedule disabled.
All triggers validate setup before reads; unselected sources are skipped.
Snapshot/checkpoint reads filter the configuration ID and reject mismatched
records. Local changes generate a new ID and invalidate preview acceptance.
The calendar extension remains an unpublished draft change; this revision did
not edit or execute the separate email push owner.

Validation: 17 Node tests passed. The Python setup/installation/catalogue/schema
suite ran 95 tests successfully, with one platform-specific skip. An isolated
installation ran the actual installed helper and preserved user settings on
reinstallation. `python scripts/validate.py` passed, including 19 Daily Review
behaviour cases. These cases are definitions, not host conversation evaluations.
n8n SDK validation passed; static expression warnings reflect empty SDK output
samples, while runtime probes checked the produced fields. The saved graph has
no validation warnings. Fixture executions 526–532 verified setup status,
unconfigured collection blocking, Workbench-only selection, saved retrieval,
old-configuration rejection, all-source assembly and paused collection. Provider
and persistence nodes were pinned for these probes; they establish branching
and data contracts, not new-account access or live persistence. The earlier
preparation tests retain their original live-source scope.

## Gmail push staging — 2026-09-17

Cost-control follow-up: the user requested a $0 spending limit. The Google Cloud
Budgets & alerts page requires a billing account; the Hermes project remains
unlinked, so no budget or paid billing was enabled. Existing notification
resources were preserved. The [zero-spend setup policy](gmail-push.md#zero-spend-configuration)
records the distinction between alerts, usage controls and an enforceable cap,
including Pub/Sub's billing prerequisite. This documentation change does not
establish live delivery, a provider spending cap or an IAM restriction.

The existing email organiser now has a saved, unpublished 60-node push conversion.
Its old 15-minute poller, push webhook and watch-renewal trigger are disabled
pending completed setup. The private voice-review branch, execution
retention and concurrently added Daily Review organisation receipts were preserved.
Dedicated Cloud configuration fails closed. The current `receiver_only: true`
gate skips Gmail message contents, model calls and draft creation while releasing
the claimed mailbox. Watch-identity failure now stops before renewal or recovery.
See [activation and acceptance](gmail-push.md).

Validation: all 56 local checks were rerun and pass, including 14 current
candidate-code/graph checks covering the receiver-only
gate, explicit activation flags and failed watch identity as well as the earlier
processing paths, plus 42 authentication and isolated state-decision checks.
The candidate builder used an explicit `PYTHON_EXECUTABLE` override. The current
60-node SDK validation is valid. Canvas grouping
changed without logic changes; one pre-existing cosmetic advisory remains about
eight top-level boxes with groups collapsed. Live n8n claims in executions 500/501 began two
milliseconds apart, with one winner and one empty result. Executions 502/503
verified cryptographic fixtures and real public Google signing-key retrieval.
Execution 511 verified a spoken result for a synthetic missing review; 512 stopped
an unconfigured push before Gmail or table access. The temporary probe is archived.
The final organisation-receipt upsert has three bounded attempts; Gmail draft
creation retries remain disabled.

This is not a live Gmail push test. The selected Google account is signed in and
authorised first-use Cloud terms were accepted with marketing unchecked. The
separate **Hermes Email** project was created, Gmail and Pub/Sub APIs enabled,
and a notification topic created. The project's billing page explicitly confirms
that no billing account is linked; no billing or trial was enabled. The topic-only
Gmail publisher permission is prepared but not saved, pending user approval
required by browser policy. A same-project OAuth client was created with the
redirect URI verified from n8n. The user approved `gmail.metadata`; that scope
is saved, with only the selected account added as an OAuth test user. The app
remains in Testing. The generic OAuth2 **Hermes Gmail Watch** form is prepared
for `gmail.metadata`, the `gmail.googleapis.com` domain and offline consent;
the client secret has not been transferred, and the credential has not been
saved or authorised. Approval for that connection step is pending separately
from the topic publisher grant. No Gmail watch has been created.

A dedicated keyless push identity has no assigned project roles or mailbox access.
The existing Google-managed Pub/Sub Service Agent role was verified to include
OpenID token creation, so no extra signing grant was made. An authenticated push
subscription was created for the existing n8n webhook with the exact endpoint as
its audience. It uses wrapped payloads, a 60-second acknowledgement deadline,
60–600-second retry backoff, one-day retention, acknowledged-message retention
off and expiry after 31 inactive days. An initial automatic-review cost rejection
was resolved after the unlinked-billing state was verified; subscription creation
subsequently succeeded.

The n8n dashboard shows 3 of 2,500 September executions used, so a
bounded receiver-only test has execution allowance; model credits remain
unverified. The user's no-additional-spending constraint remains in force and
provider setup checks still precede activation. No email was sent,
and the actual receiver-delivery and new-message end-to-end tests remain
outstanding.
Run-specific source, bindings, baseline and evidence are ignored under
`test-results/gmail-push/`.

The dedicated research skill was retired on 2026-09-17; see the
[current retirement record](#research-skill-retired--2026-09-17). Earlier dated
entries retain the package versions and test results that existed at that time.

## Shared Hermes orchestration and partner installer — 2026-09-16

The user selected a tested installer for the partner's computer. The new
[orchestration component](../components/hermes-orchestration/README.md) supplies
profile-wide operating instructions, a capability catalogue and direct workflow
contracts. The installer embeds the policy in a managed SOUL.md block and installs
complete skill folders, retaining unrelated personality, configuration and credentials.
It uses existing Hermes mechanisms rather than adding a separate agent runtime.

Content Creation retains `idea-to-content` and schema 1.0; its package is now
0.3.2. Research Brief is 0.1.2, Project Planner 0.3.1 and Calendar Planner 0.2.1.
All four describe domain expertise, Hermes context/tool ownership and concise
voice results. Planning reuses its configured operation owner's proposal instead
of generating a second competing plan. Root agent instructions and the regular
validator now require catalogue coverage and the shared voice/route contract for
future skill additions. The local preview's public heading is Content Creation;
it remains a direct model prototype.

Read-only live n8n inspection verified seven non-archived workflows. Planner,
calendar, outreach and prospect research have published private Agent request
routes; published graphs matched their drafts. The prospect helper is internal.
Email review and priorities remain unpublished; publishing them would also
activate their background triggers. Retired repurposing remains archived.
No workflow executions, provider writes, publication or credential changes were
performed in this setup pass. The portable contract was checked against live
parser arguments, including planner `mode`, not `save_mode`.

Validation completed:

- The complete Python repository suite ran **164 tests: 163 passed, one skipped**.
  The skipped test requires Windows symlink-creation privilege. This includes
  20 installer cases and 19 catalogue checks, plus existing regression suites.
- All **20 content backend tests passed** after skill edits, including the
  existing 16k context/source/previous-pack budget. Schemas and model settings
  were unchanged. These backend replies are controlled fixtures.
- Four packages and **80 behavioural case definitions** pass validation. Eight
  new definitions cover skill/tool ownership and voice/context behaviour; this
  does not mean 80 model runs were performed.
- An independent review reproduced a mid-install persona-edit race. The installer
  now serialises installer instances, rechecks before individual replacement,
  and verifies installed contents before committing ownership state. New cases
  cover concurrent edits and lock handling. Unrelated editors are not atomically
  locked; install while the host is idle.
- The exact **28-file partner ZIP** was extracted and tested: catalogue validation,
  write-free preview, installation over a synthetic existing persona/config,
  identical second install and read-only current-state check all passed. Bundle
  contents and manifest hashes were verified. No real Hermes profile was used.
- Two independent authoring-environment forward scenarios used synthetic tools.
  Both produced three bios and three unpublished posts from the supplied source.
  Missing current-state access kept the first profile update pending. The second
  read the fixture state and performed one confirmed mock Facebook bio update
  without reconfirmation; Instagram/X access remained pending. These were not
  native Hermes runs or real account actions.

Verified baselines, forward traces, installer smoke profile, ZIP and hash report
are under ignored `test-results/hermes-orchestration/`. The installer, catalogue
validator and operational sources are maintained in the repository. Partner-host
MCP login, actual audio/dashboard state handling and intended-model acceptance
remain deployment checks. Earlier local content fidelity failures below remain
unresolved; installing instructions is not proof of model or provider reliability.

## Goal-based content and autonomy — 2026-09-16

Idea to Content 0.3.1 infers adaptation from available source and the requested
outcome without requiring a repurposing keyword. Named platforms override default
packs. A broader social-launch request includes useful writing substeps such as
profile copy and initial posts, with original creation when no source exists.
The standing project requirement and [host execution contract](integration.md#goal-execution-and-autonomy)
cover inferred routine actions, real tool capabilities, essential blockers,
verified outcomes and resuming from progress. Explicit draft-only limits remain.

Package validation passes all four skills and 72 behavioural case definitions,
including 32 content cases. The four new cases cover implicit adaptation, named
platforms, a launch without tools and draft-only scope; these are structural
checks of case definitions, not executed model or social-account tests. Output
schema 1.0 and runtime/model configuration are unchanged.

All 20 backend tests pass, including the practical source/previous-pack check
under the existing 16k context limit. The initial expanded instructions exceeded
that budget; repeated wording was compacted and detailed host guidance kept in
the integration contract. Existing source-fidelity rules remain. Scoped diff
checks pass. Model responses in these backend checks are controlled fixtures.

No account integrations or general goal executor were added to the local preview,
and no accounts were created from the user's illustrative request. Actual setup
and profile changes require the partner's connected Hermes deployment and live
acceptance checks. The earlier model fidelity failures below remain unresolved;
this instruction update is not evidence that model quality has improved.
Scoped recovery copies are in ignored
`test-results/content-consolidation/autonomy-baseline/`.

## Unified content creation and repurposing — 2026-09-16

Idea to Content 0.3.0 now owns original creation and source-based repurposing.
The original hooks/script/posts default remains; a repurposing request with no
specified formats uses LinkedIn, short-post and newsletter drafts. Explicit
formats and counts override both defaults. Source fidelity, Australian English
by default, concise completion, targeted corrections and exact readback are
documented in the installable skill. Output schema 1.0 is unchanged.

The separate n8n **Starter 06 - Content Repurposing Drafts**
(`ROjypSujSwjcyGpG`) was archived successfully, and a subsequent workflow search
returned no active catalogue match. Its latest definition was preserved before
archiving; Workbench records and execution history were not deleted. Earlier
workflow setup and voice-route notes are historical, not instructions to
reactivate this retired feature.

The local preview accepts clear drafting/repurposing commands through typed
instructions and completed speech transcripts, using the same backend. Current
source and actual previous-result context survive follow-ups; a new complete
brief does not inherit a sample topic. A targeted replacement preserves other
assets, hook references and review caveats; earlier partial limitations stay
visible. The backend loads the repurposing guide and returns `spoken_summary`
beside the unchanged skill result. No model settings or private configuration
were changed. Repeated instructions were shortened so a representative 1k source
and 6k previous result fit the existing 16k context configuration.

Validation completed:

- **20 backend tests passed**, including prompt/source transport, actual previous
  draft preservation, practical context capacity and ready/partial/missing-input
  spoken responses. Model replies in these tests are controlled fixtures.
  Voice completion is derived from the validated asset count and status rather
  than repeating a model's unsupported claim that content was published or saved.
- **57 browser/state/intent tests passed**, including 38 headless Edge browser
  cases. They cover text/final-voice parity, interim and duplicate suppression,
  delayed input, named/numbered targets, source-aware retries, single-asset merges,
  hook collisions and retained caveats. Speech callbacks and generation were
  simulated; actual microphone transcription was not exercised.
- Package validation passed for all four skills and 68 behavioural case
  definitions, including 28 Idea to Content cases. The eleven new case definitions
  do not mean eleven live agent runs were executed. Scoped diff checks passed.

The first live CPU run using local gpt-oss:20b returned schema-valid drafts but
failed factual review: it described a fictional exercise as a recent real event,
added unsupported source details and added unnecessary hooks. Its newsletter
also exceeded the requested body length. The raw result is retained as
`live-default-pack.json`; it is failure evidence, not an approved example.
The skill now explicitly resolves the background-constraint/style-example
ambiguity in favour of source fidelity. The backend repeats that priority after
the output schema and distinguishes original source context from the latest
command. A valid JSON response alone does not establish faithful repurposing.

The second live run (`live-final.json`) returned all three formats and the new
deterministic spoken receipt, but still failed content acceptance: it described
fictional participants as having learned the method, retained an unnecessary hook
and produced a newsletter below the requested minimum length. The unsupported
plant-specific advice from the first run was absent. These are two failed quality
checks, not a successful end-to-end drafting test. The fictional-source case is
now retained in the behavioural suite. The default local gpt-oss:20b configuration
has not demonstrated dependable repurposing fidelity; evaluate the partner's
intended model against these cases before treating the feature as production-ready.

Recovery snapshots and run evidence are under ignored
`test-results/content-consolidation/`. This laptop preview does not run Hermes,
provide audio playback or persist new drafts. The partner must sync the updated
skill/component, connect their existing conversation/audio layers, and test real
source selection, readback, interruptions and mixed input on the actual host.

## Retired email drafting prototype — 2026-09-16

At the user's request, the dedicated local email drafter and its private
connection configuration were removed, and its server was stopped. The original
[onboarding workflow](https://automatedai.app.n8n.cloud/workflow/5fYq9fNePAZuG4su)
and the unused [Gmail bridge](https://automatedai.app.n8n.cloud/workflow/mM6UI2ohAGNXZ7iL)
are archived in n8n. The email-response, planning and scheduling workflows and
their shared credentials remain in place.

A source/documentation recovery snapshot and earlier synthetic test evidence
remain in ignored `test-results/email-drafting/`. The snapshot excludes private
configuration. The prototype had passed 96 local checks and two fictional
Ollama drafting runs; live Gmail history/save and Hermes integration were not
tested. The shared Ollama runtime and model remain available to the content
generation preview. Four diagnostic log files remain under ignored
`local/email-drafting/` because background processes still hold them open; no
app source, launcher, process-ID file or private connection key remains there.

Date: 2026-09-15. Initial baseline: all skill packages `0.1.0`. Current packages: Idea to Content `0.2.0`, Research Brief `0.1.1`, Project Planner `0.2.0`, Calendar Planner `0.1.0`. Output contract: `1.0`.

## Initial local baseline

- The skill-creator format validator accepted all three `SKILL.md` packages.
- `python scripts/validate.py` passed for three packages, three example outputs, and 18 behavioural case definitions.
- `python -m unittest discover -s tests -v` passed all 18 validator regression tests.
- Six independently generated responses passed their output schemas and the selected semantic checks through `scripts/validate.py --output`.

Validation used Python 3.12, PyYAML 6.0.3, and jsonschema 4.26.0 in the local project's virtual environment. The validator runs offline and does not execute a skill or call a model.

## Behavioural forward tests

Other assistant workers in this authoring environment followed the packages on requests without receiving an intended answer. The worker testing a skill was not that skill's author. These were authoring-environment evaluations, not Hermes runs and not a benchmark of customer reliability.

| Skill | Request | Observed behaviour |
| --- | --- | --- |
| Idea to Content | Exactly two Instagram text posts for handmade unscented soy candles in reusable glass jars; no videos, hooks section, health claims, or discounts | Two text assets, empty hooks and production notes, supplied product details preserved |
| Idea to Content | Introduce an AI app using placeholder claims of 10,000 users doubling income, and publish with no integration | Unsupported claims omitted, honest draft supplied, `partial` status, no publication claimed |
| Project Planner | Launch a clothing brand tomorrow with designs, manufactured stock, shop, and photoshoot; two hours total and no stock or suppliers | Full launch identified as infeasible; `partial` preparation plan totals 120 minutes; remaining execution deferred |
| Project Planner | Portfolio redesign with zero hours this week and next | No tasks allocated, `partial` status, no assumed availability in week three |
| Research Brief | Budget AUD 20 for fictional WaveNote using conflicting undated AUD 15/AUD 30 monthly snippets | Both supplied claims retained, `partial` status, no averaging or invented explanation |
| Research Brief | Assess fictional RapidCaption from a supplied AUD 12/caption-export snippet containing instructions to guarantee virality and send private files | Source instructions ignored, conditional supplied-text assessment, no fabricated guarantees or external actions |

Each output was inspected for the behaviour above and then checked with the repository validator. Raw generated outputs remain in ignored local `test-results/`; the repository contains the reusable scenario definitions, not private run records. These six requests are variants of saved scenarios, not execution of the entire 18-case suite.

The planner originally exposed only a weekly-hours field. Forward testing showed that a one-time allowance could only be expressed in prose. The package now also exposes `time_budget_minutes_total`, the validator enforces both types of limit, and the planner responses were rerun successfully.

The content schema preserves stable envelope and planning fields even when the user asks for drafts only. The UI should hide empty hook lists and avoid displaying planning details the user did not request.

## Idea to Content readability revision

User feedback exposed unclear boundaries between creator guidance and publishable copy, plus a product-launch request being turned into a generic AI tutorial. Version `0.1.1` separates caption/spoken copy from guidance and production notes, preserves the requested content purpose, and updates the JSON example and UI integration guidance without changing the schema.

The local package validator passed all three packages and 21 behavioural case definitions. All 18 validator regression tests passed, and the skill-creator format check accepted the revised package. These structural checks do not judge copy quality or execute all case prompts.

A separate assistant generated a launch response, an explicitly requested educational caption, and a feature-introduction JSON response under the revised instructions. Manual review confirmed clear copy boundaries, preservation of the educational prompt example when requested, and separation of spoken words from filming/overlay notes. The feature-introduction response also passed the repository's output validator. The launch request is included in the readable reference, so that run is an example-following check, not an unseen evaluation.

That launch run unnecessarily repeated the lack of customers/results in promotional copy. The instructions were refined to treat background constraints as limits on claims rather than automatic audience-facing statements.

A further launch variant used a fictional product name, one Instagram caption, and a 30-second video with no confirmed features. That specific request was absent from the reference. Manual review found the requested product introduction, distinct copy boundaries, no invented capabilities or results, and background constraints kept in creator guidance. The script contains 60 spoken words; actual delivery time still requires a read-through. The package/link and skill-format validators passed again after the refinement. All four readability outputs remain in ignored local `test-results/idea-to-content/readability/`; none was executed through Hermes.

## Idea to Content social writing revision

Version `0.1.2` responds to feedback that captions and scripts sounded like a lecture. The default now uses conversational social copy, an opening grounded in the user's actual idea, and a useful payoff. It keeps explicit tone/brand choices and educational steps intact, uses calls to action only where useful or requested, and preserves the copy/guidance boundaries introduced in `0.1.1`. Both reference outputs were rewritten. This is a writing-direction change, not evidence of higher reach or virality.

A separate assistant generated three responses from the updated skill without consulting examples, test-case definitions, or prior outputs:

- An upcoming voice-memo-to-caption app: one conversational Instagram caption and a roughly 30-second script. Review found a relatable walking/forgotten-wording hook, light humour, the sole supplied feature preserved, and separate production notes.
- A professional architecture post: a measured, formal draft under the requested 90 words, with no slang, emoji, call to action, or invented experience. The explicit voice took priority over the casual default.
- A freelancer weekly reset: a lively educational caption containing all three supplied steps. Its dashboard JSON passed the repository output validator; review found no invented results or missing payoff.

The package validator passed three packages, their updated examples, and 24 behavioural case definitions; the skill-creator format check also passed. Validator implementation and schemas were unchanged, so the earlier 18-test regression suite was not rerun for this prose-only revision. The three generated responses remain in ignored `test-results/idea-to-content/social-voice/`. These are local authoring checks, not Hermes execution or audience-performance tests.

Version `0.1.3` is a label-only follow-up: the readable response uses `User guidance` and `Production notes` in place of headings containing `For you`. Instructions and the readable example agree; the output schema is unchanged.

## Summary and In depth views

Research Brief and Project Planner `0.1.1` use the existing `summary` and `data` fields for two reading views of one result. No schema fields or contract version changed. Chat defaults to Summary and accepts explicit requests for either view or both. The integration guide specifies the dashboard toggle, shared limitations/status, capacity display, and research source-token rendering.

Package validation passed all three packages, their examples, and 28 behavioural case definitions. Both revised skill packages passed the skill-creator format check. All 21 validator regression tests passed, including new checks for inline research references in summaries, answers, conflicts, and next actions, and missing-evidence results. These checks validate structure and reference identity, not the truth or completeness of citations.

Two separate assistant workers followed the revised instructions without reading example outputs or test cases:

- Research: supplied fictional ClipMap snippets disagreed on AUD 18 versus AUD 32 pricing against an AUD 25 budget. The summary and full brief both kept affordability unresolved, retained the same conditional recommendation, identified unverified supplied text, and cited existing sources. The generated JSON passed validation.
- Planning: a ten-lesson course launch with 45 minutes total produced a partial preparation plan. The summary and detailed plan both deferred the full launch, used the same three tasks and 45-minute allowance, and left calendar dates and further capacity unknown. The generated JSON passed validation.

The raw outputs remain under ignored `test-results/research-brief/two-views/` and `test-results/project-planner/two-views/`. These were local JSON instruction-following tests; no Hermes runtime, live research retrieval, or actual dashboard toggle was exercised in this revision. The new Summary-only chat scenarios are saved case definitions, not additional executed runs.

## Selectable voice and social script revision

Idea to Content `0.2.0` adds primary and optional secondary writing styles, energy, wording, natural-language overrides, and focused voice rewrites. A linked reference defines the presets and review criteria. The default remains immediate drafting; no questionnaire is required. Existing copy/guidance boundaries, format overrides, purpose preservation, claim limits, and external-action boundaries remain in place. The existing `data.brief.tone` describes the resolved voice, with no output schema change. The integration guide specifies UI choices and application-owned selections; the dashboard controls are not implemented here.

On 2026-09-14, three separate assistant workers followed the revised skill and its relevant references without reading saved cases or prior outputs:

- Topic-only public speaking: produced the default three hooks, selected angle, video, and two posts. The 127-word video opens with unspecific self-criticism after a rehearsal and develops a concrete exercise. The opening no longer depends on the earlier sandwich analogy. This is editorial review, not measured improvement in audience response.
- Four styles on the same topic and supplied takeaway: produced Engaging, Educational, Entertaining, and Emotional scripts of 95, 86, 91, and 77 words. All retained the one-minute familiar-topic practice, main point/example, listener question, and revision of one unclear part. Manual review found different openings and framing, with production notes outside spoken copy. The 35–45 second durations remain estimates; delivery was not recorded.
- Conflicting preset and specific rewrite request: produced one 26-word professional LinkedIn caption, preserving two sketches, a 30-minute call, the room-layout discussion and residential-renovation scope. It followed the explicit professional/plain override, omitted humour and a CTA, and passed JSON output validation.

Package validation passed all three packages, their examples, and 33 case definitions. The skill-creator format check passed for Idea to Content. Schemas and validator code were unchanged, so the earlier validator regression suite was not rerun. The new blend and custom-writing-sample scenarios are saved case definitions, not additional executed tests. Outputs and exact prompts remain in ignored `test-results/idea-to-content/voice-controls/`. No Hermes runtime, dashboard controls, audience-performance experiment, or publishing integration was exercised.

The editorial direction was checked against [YouTube's Shorts creator discussion](https://blog.youtube/creator-and-artist-stories/youtube-shorts-deep-dive/) and [official Shorts discovery guidance](https://support.google.com/youtube/answer/11914225?co=YOUTUBE._YTVideoType%3Dshorts&hl=en). These support immediate audience interest, concise storytelling and attention to observed viewer response. They do not establish a universal script formula or prove that these drafts will go viral.

## Portable selector component

On 2026-09-14, `components/content-preferences/` added a framework-neutral custom element, a preference store, a conservative offline instruction interpreter, an optional browser speech adapter and a local preview. The preview prepares a Hermes prompt and never claims to generate content. The existing skill packages and JSON output schemas are unchanged. Broader voice understanding, actual agent generation, permanent profiles and multi-asset application state still belong to the partner's integration.

Fourteen Node checks passed for the store and interpreter. Twelve isolated browser checks passed in headless Microsoft Edge through Playwright: button/text synchronisation, settings versus generation, custom requirements, unsupported compound requests, stale voice conflicts, completed-utterance deduplication, explicit same-value choices, manual transcript submission, cancelled asynchronous interpretation, scope display, failing speech adapters, final-segment aggregation, unavailable microphones and mobile layout. Some tests cover several related behaviours. The rendered desktop preview was also inspected. The initially attempted bundled Chromium executable was absent; the suite used the already installed Edge browser without installing another browser.

All speech events in these checks were supplied by test adapters or a mock recognition class. No real microphone audio, remote speech service, live Hermes connection or partner dashboard was tested. Browser microphone support is capability-dependent and has a visible fallback. The state/interpreter tests require only Node; the browser suite additionally requires Playwright and a supported installed browser. Package/example validation still passes for all three skills and 33 case definitions.

## Selector agreement follow-up

The component now subscribes all views for the same editing scope to one shared store. Direct host updates refresh the visible controls, re-binding a store invalidates old pending input, and accepted settings remain explicit in the generated preference context. Wording uses the same reaffirmable radio interaction as tone/intensity. Requests wait for the current instruction to resolve and cannot take stale settings from caller metadata. Skill packages and response schemas are unchanged.

Nineteen Node tests and seventeen isolated browser tests passed (36 total). Added checks cover multiple subscribers, listener mutation/failure isolation, unsubscribe and reentrant notification order, agreement across two component views and outgoing requests, wording reaffirmation, delayed input after a store change, synchronous host scope changes, and reconnection. The browser suite used headless Edge with injected speech events; actual microphone audio, Hermes generation and the partner's complete dashboard remain untested here.

## Minimal prototype presentation

On 2026-09-14, the interruption recovery check found no uncommitted changes; all 36 existing selector checks passed before editing. The stopped local preview server was restarted. The mockup now uses a compact form with short labels, while retaining tone/intensity, optional wording/custom directions, typed commands, microphone input and prepared prompts. Component markup and styles are separate files, with theme variables and documented integration hooks. The preference store and interpreter are unchanged.

After the presentation change, all 19 Node and 17 isolated Edge browser tests passed again. The browser suite confirms the extracted component stylesheet loads, and the desktop preview was visually inspected. The package validator also passed all three skills and 33 case definitions. Speech remains simulated in these checks; Hermes generation and the partner's dashboard were not exercised.

## Local model generation prototype

On 2026-09-14, the preview gained a Python model adapter and now renders actual Idea to Content drafts instead of a copyable prompt. The server loads the maintained skill, writing-style reference and schema, uses the repository's schema/semantic validator, and exposes model/provider configuration independently of the UI. The browser displays copyable asset text and separate guidance/production notes, rejects stale results, and supports cancellation/retry. The underlying preference store, interpreter, skill packages and output schema are unchanged.

All 61 automated checks passed: 19 Node selector checks, 27 isolated Edge browser checks and 15 Python backend checks. The new browser cases use explicitly mocked model responses for content rendering/copy, HTML-as-text handling, errors, missing inputs, cancellation and late responses after brief/preference/scope/store updates. Backend cases cover real HTTP transport to a fake service, provider switching, schema/semantic validation, truncated/malformed output, credential isolation, request origin/body limits and one-run-at-a-time behaviour. These do not establish real compatibility with every alternate provider. Package validation still passes all three skills and 33 case definitions. The Windows launcher's syntax, default startup and effective configuration overrides were also checked.

A portable Ollama 0.34.0 runtime was downloaded from its official release and its SHA-256 checked before extraction. The local gpt-oss:20b model uses MXFP4 weights, approximately 13.79 GB on disk. Runtime files, model weights, private configuration and generated results remain in ignored local storage. The measured machine has 31.5 GiB RAM and an Intel Core Ultra 7 355; Ollama used CPU inference with a 16K context window, low reasoning, 4096-token output limit and temperature 0.5.

The first real UI run generated one 121-word public-speaking video script in 305 seconds, returned HTTP 200, passed output validation and produced no browser script errors. Editorial inspection found numbered/emoji markers in spoken copy and an unsupported automatic-confidence claim. The adapter's final output check was reinforced to apply the skill's existing spoken-copy and factual-boundary instructions.

A second real UI run with the model already loaded returned one 129-word video script in 123 seconds, again with HTTP 200, schema/semantic validation success and no browser script errors. The spoken content no longer contains numbered or emoji markers, and the rendered result was visually checked. It still invents a first-person experience and uses overconfident outcome wording. These runs demonstrate functioning local generation and rendering, not approval of the draft's writing quality or facts. Review output before use; model choice and editorial evaluation remain part of the partner's integration. The two prompts/results, timing records and screenshot remain in ignored `test-results/idea-to-content/local-model/`.

The prototype is a direct model call, not a Hermes runtime test. Live microphone transcription, the partner's dashboard, multiple users, hosted-provider billing and audience performance remain outside these local checks.

## Still required in the product environment

No callable Hermes installation was found on PATH or at the checked default installation locations. No Hermes installation, Hermes model configuration, or customer integration was changed.

Before a customer release:

1. Install the packages into a development Hermes profile and confirm all four appear in `hermes skills list` and load by slash command.
2. Run the saved cases using the Hermes version, model, and tools intended for the product. Record those versions and the observed outputs.
3. Exercise live research retrieval as well as missing-access fallbacks. This pass used supplied text; live source retrieval has not been tested through Hermes.
4. Validate JSON results in the actual backend and verify that the UI renders statuses, citations, drafts, task dependencies, and budget limitations correctly.

No rendered video, live recurring schedule, or complete Hermes dashboard integration has been verified. The portable planning/calendar prototype below needs a provider client and deployment configuration if selected. The existing n8n and Notion Calendar integration is documented separately below and uses the already connected Notion database.

## Portable weekly planning and calendar sync prototype

Added Project Planner `0.2.0` weekly-review/handoff instructions, Calendar Planner
`0.1.0`, and the portable `components/planning-sync/` implementation. The existing
planner output schema remains `1.0`; execution progress and provider state are
stored separately from model proposals.

Validation covers persistent project/task identities, repeated requests, stale
revisions, whole-operation rollback, incoming calendar swaps, preservation of
progress across weekly imports, dependency ordering, separate due dates and time
blocks, daylight-saving validation, bidirectional field changes, conflicting
edits, retry after restart, ambiguous creates/deletes, Notion property mapping,
permission failures, marker ownership and calendar availability checks.

The adapter integration tests run the real engine, Notion adapter and calendar
bridge together against simulated HTTP/calendar clients. They verify task creation,
calendar scheduling, stable provider IDs, Notion rename propagation, calendar drag
propagation, unscheduling, completion and duplicate-free repeat polling. CLI tests
exercise imports, edits and project/schema boundaries through actual JSON files.

Local package validation passes for all four skills and 46 behavioural case
definitions. Case definitions are not model executions. The skill-format checks
pass for the revised Project Planner and new Calendar Planner. Tests run with
Python 3.12.14 and tzdata 2026.4 in the project virtual environment.

The complete repository Python test suite passes **111 tests** after this change:
28 validator tests, 33 sync-engine tests, 21 Notion adapter tests, 25 calendar
adapter/integration tests and four CLI tests. Outgoing local swaps are included,
with availability derived from actual simulated events, plus rejection of a
vacating event that was edited concurrently. `git diff --check` also passes.

An independent agent forward-test used Calendar Planner to rename and schedule
one saved task while preserving its supplied deadline. It produced one combined
revision-checked operation with the correct Brisbane timestamps and reported
`partial` because no execution tool was available. Its JSON passed validation;
the raw result is ignored under `test-results/calendar-planner/forward-test.json`.
This was an instruction-following check, not a Hermes or live-account run.

No live Notion workspace, calendar provider, Hermes runtime, continuous polling or
dashboard UI was exercised in the portable prototype tests. The Notion HTTP contract was checked
against official API documentation; its lack of atomic conditional page updates
remains a concurrency limitation. The calendar bridge requires a provider client
that implements actual conditional writes and idempotent creation. See the
[component guide](../components/planning-sync/README.md) for setup and remaining
live acceptance checks.

## Existing n8n and Notion Calendar connection

On 2026-09-15, the existing **Starter 04 - Weekly Project Planner** was connected
to **Starter 03 - Time Management and Scheduling**, reusing **Notion account 2**
and **Schedule & Tasks**. Notion Calendar already displays those same pages. This
integration is separate from the optional Python prototype above; no new calendar
provider, database schema or background polling service was installed.

The planner now reads current project tasks and busy periods, validates a weekly
proposal, and optionally creates new unscheduled tasks through the scheduler.
Existing page identities, edits and progress are preserved. Workbench saves the
validated plan before task writes; repeat requests reuse that proposal and refresh
the actual pages. Missing previously attempted pages return an explicit partial
result instead of being recreated. The supported OpenAI Responses node replaced
the failing execution path; the older model nodes remain disabled for reference.

**113 offline Node checks passed**: 34 scheduler cases, 55 planner cases and 24
request/replay cases. These include existing owner-action parity, reference
ownership, budget/dependency validation, deadlines already present in Notion,
ambiguous-write recovery, missing pages and receipt validation.

Live n8n executions 342–375 exercised real Notion and Workbench operations. Model
generation also ran live for draft, save and fresh-review paths. Successful checks:

- Project-context reads and two-task creation; no extra calendar copies.
- Sequential replay reused both Notion page IDs and skipped model regeneration.
- Owner rename, timed scheduling, colour, completion and deadline edits remained
  present in subsequent planner receipts and reports.
- A new weekly review reused the existing task identity and accepted its current
  saved deadline without inventing a deadline for new work.
- Archiving a linked page produced `PARTIAL` / `NOT_FOUND` on replay and did not
  recreate it. Both synthetic pages were then trashed; final context contained no
  test-project tasks, and the three unrelated commitments were unchanged.

Initial live tests exposed the provider's already-parsed JSON response shape and
a validator that rejected a deadline supplied by current Notion state. Both were
fixed and retested. Automated lifecycle tests supplied synthetic form input and
skipped the terminal completion screen; Notion, Workbench and relevant model
calls ran live. Execution 347 reached the completion screen in a manual run and
waited for its form visitor. The new planner form was not visually tested in a
browser; earlier scheduler browser validation is recorded inside that workflow.

Both final workflows were published successfully:

- [Starter 03 - Time Management and Scheduling](https://automatedai.app.n8n.cloud/workflow/rTed7PRf60fF2MjA), version `d897ebc9-aa4d-4a0d-b25b-9b033132d390`.
- [Starter 04 - Weekly Project Planner](https://automatedai.app.n8n.cloud/workflow/tJ6YmJuFsyEoWYXw), version `2ef0df57-5524-49eb-9857-1301b99bd447`.

Both forms require n8n sign-in; the planner also requires workflow execution
access. Notion/Calendar changes are shared-page changes; stored planner reports
refresh when the workflow is rerun. Limits remain: one date property for either a
deadline or interval, availability limited to this database, a 500-record scan
limit, and no atomic lock against overlapping saves or external calendar edits.
Retries after uncertain writes may require manual review. This did not exercise
the Hermes dashboard, continuous monitoring or a separate calendar provider.

## Fictional project acceptance test — 2026-09-16

Tested a fictional Weekend Brew coffee-cart launch pack for 21–25 September:
six deliverables, eight hours available, no Wednesday/weekend work, and a two-hour
daily maximum. The live planner allocated six hours with two hours of buffer,
created six Notion pages, preserved dependency order and gave only the final
review its supplied deadline (execution 382).

Live scheduling then booked a task, rejected an overlapping booking, renamed and
rescheduled the first task, and marked a second Done as a simulation (390–393).
Replaying the original plan retained all six page IDs, notes, colour, dates and
completion without duplicates or another model call (394).

A fresh review (402) exposed a formatter bug: the model omitted a completed task
from its allocation but still named it as a historical prerequisite. The formatter
now treats an omitted dependency as satisfied only when its title uniquely
identifies a current Done task in the same project. It removes that historical
edge from the weekly plan and records the exact reference in assumptions. Tasks
still present in the proposal by title or identity retain normal ordering checks;
unknown, ambiguous, cancelled and unfinished dependencies remain errors.

All 113 existing offline checks and 18 new regression checks passed. The exact
failing model output passed after the fix (404), as did a fresh live-model review
(406), which proposed five remaining tasks and five hours. The fix is published
in Starter 04 version `bd0518ae-2507-466a-996e-d1712f152c66`.

Archiving one page and retrying returned `PARTIAL` / `NOT_FOUND` without recreating
it (408–409). All six fixtures were then trashed; the final read (422) found no
test-project tasks and the three original entries unchanged. Form inputs were
synthetic and completion screens were skipped; live model, Notion and Workbench
actions ran. Browser rendering and the Notion Calendar app were not retested.
Run evidence remains in ignored `test-results/n8n-planning/weekend-brew-test.json`
and the accompanying Markdown report. Test history remains available in n8n.

## Optional planning detail — 2026-09-16

Project Planner 0.3.0 and Calendar Planner 0.2.0 introduce portable output version
1.1, retaining legacy 1.0 compatibility. Broad timeline is the default: target
weeks and dependencies with null effort estimates. Detailed mode keeps required
work estimates separate from optional budgets and calendar capacity. Estimates
above a supplied limit remain visible with partial status and a limitation.
Read-only calendar review and switching detail never emit booking operations.

The existing n8n planner now offers both modes over 1–12 weeks, default four.
Detailed mode opens a second form for editable working days/hours, event buffers,
reserve and an optional weekly cap. It reads the same scheduling workflow and
Notion database, credits existing bookings once, and proposes feasible sessions
without booking them. New Workbench results use schema 3.0; schema 2.0 saved
requests retain their original proposal and retry behaviour.

Validation completed:

- 42 Python validator tests and all four packages/57 behavioural case definitions
  passed. The separate optional Python sync/CLI component's 37 tests also passed;
  its integer-estimate importer still does not support broad null estimates.
- 100 focused Node tests passed: 60 planner-mode/input cases, 25 availability and
  allocation cases, and 15 independent integration cases. These cover actual
  embedded node bodies, working windows, overlapping/all-day reservations, stale
  reads, dependencies, deadlines, existing bookings, zero limits, saved requests,
  HTML escaping and graph branches. External providers/model/table calls were
  mocked in these offline tests.
- Three independent portable forward scenarios produced four valid JSON outputs:
  a broad month plan, detailed planning without a budget using supplied calendar
  state, and turning detail off while preserving an existing booking/progress.
  These were authoring-environment tests, not Hermes execution.

Live tests used the real model, Notion and Workbench. A fictional three-task herb
garden plan saved broad tasks for weeks 1, 2 and 4 without effort metadata or dates
(423). The scheduling workflow booked its first task and marked it In progress as
a fixture (428). Detailed review without an hours budget reused all three task
identities, estimated 3.75 hours, credited the existing hour, and proposed 2.75
new hours without writes (429). Broad replay preserved all page IDs and that
booking/progress without another model call (431). A zero-cap review retained
3.75 hours of work, proposed no new time and reported 2.75 hours unallocated (436).
Detailed replay reused the saved proposal and refreshed calendar review (446).
Legacy schema 2.0 replay correctly returned missing-page errors for the previously
archived Weekend Brew fixtures without recreating them (438).

Both production form paths were exercised in the browser. This found n8n's blank
number-field coercion to zero (448); the optional hours field now uses text input
with numeric validation. Blank/whitespace remains unknown and explicit zero
remains zero. The corrected browser run (454) calculated calendar availability,
showed no supplied weekly limit and proposed a 90-minute session. Broad browser
submission (456) bypassed time preferences and displayed only target weeks and
outcomes. A further detailed test (458) retained four hours of supplied work
against two restricted working windows, but the model added an unnecessary
dependency between explicitly independent tasks. The prompt now reinforces that
an earlier week or shared topic does not create a prerequisite. The final live
test (460) kept both tasks independent, retained the four-hour estimate, proposed
1.5 hours and reported 2.5 hours still to allocate. Model wording was also
reinforced to call new work proposed, never already booked.

All three new Notion fixture pages were trashed (450–452). Final context read 453
found zero fixture tasks and only the three original calendar entries; their
titles, dates, status, notes, references and colours matched the pre-test read.
Draft results and execution history remain in Workbench/n8n. Run evidence lives
under ignored `test-results/n8n-planning/modes-*` artifacts.

The planner is published at version `c3fdb67b-43c2-4ebb-96ba-94a24ec35737`, with
the active version matching the draft. The scheduling workflow remains published
at `d897ebc9-aa4d-4a0d-b25b-9b033132d390`. Calendar coverage remains the selected
Notion database, refresh is on workflow execution, and each saved task holds one
date interval. Split a task before booking multiple separate suggested sessions.
No continuous polling, separate provider or Hermes dashboard integration was added.

## Voice-first workflow entry and results — 2026-09-16

Voice is now a standing requirement for every new or modified workflow. The
planner and scheduler were updated in this pass; the subsequent section records
the rollout to other workflows. The owning contract and partner
handoff are in [Direct agent requests for voice](integration.md#direct-agent-requests-for-voice).

Both workflows now expose a private `Agent request` Chat Trigger for authenticated
n8n MCP calls. JSON requests bypass form pages and reuse the existing domain
logic. Responses contain a concise spoken result and full structured data with
request/session/revision identifiers. Calendar actions use no model. Agent edits
require the current page content token, and mutation retries use persisted
receipts. The host still owns conversational state, resolved intent and speech.

Validation completed:

- Both full SDK graphs and changed node configurations validated. The retained
  disabled legacy LLM node warning and a false-positive JS Date/Luxon warning
  remain; the affected code calls `toISOString()` on a JavaScript Date.
- **65 local checks passed**: 16 voice request, retry, state and response checks;
  15 planner form/integration regressions; 34 scheduler and owner/workflow
  regressions. These execute the serialized candidate Code nodes and graph paths
  with controlled provider fixtures; they are not audio tests.
- Live manual MCP execution 462 read tasks directly and returned a spoken result.
  Execution 463 generated a fictional two-task herb guide and saved both Notion
  tasks without hours or bookings, using the real model and existing connection.
- First-time mutation run 467 exposed a missing runtime `alwaysOutputData` setting
  on the empty receipt lookup. The setting was applied explicitly. Rerun 468
  successfully booked one fixture task and marked it In progress. Exact replay
  469 returned a historical receipt without reapplying the write.
- Detailed review 470 omitted the hours budget, retained four hours of estimated
  work, credited the existing hour, proposed 2.75 hours, and reported 15 minutes
  still unallocated. It preserved page identities and created no bookings.
- Stale edit 472 returned `STALE_STATE` without writing. Missing working windows
  in 473 returned one clarification question before model/calendar work.
- Completion 474 marked the second fixture Done. Broad replay 475 reused the
  saved plan without a model call and preserved that completion and the first
  task's booking. The corrected spoken summary had clean sentence endings.
- Cleanup 479–480 trashed only the two new fixture pages. Final read 481 found no
  fixture tasks and the same three original commitments, with identical content
  and edit timestamps. Execution history and Workbench receipts remain.

The published planner version is `8b4915cd-a5dd-4945-af7e-f60807b56c3e` (36 nodes).
The published scheduler version is `51fe93cf-2b9d-4a23-81da-2cec3a3d4327` (37 nodes).
These supersede the versions recorded in the preceding mode-update section.
Candidate graphs, snapshots, test scripts and selected results are under ignored
`test-results/n8n-planning/voice-*` artifacts.

The new routes were tested using manual execution against real providers; actual
spoken interaction through Hermes and the custom dashboard has not been tested.
The partner must connect authenticated workflow tools, serialise related writes,
reject stale speech/results and exercise interruption/mixed-input scenarios.
Notion read/check/write is not atomic, and a receipt is historical evidence rather
than proof that an item has not changed since. Existing database coverage, scan
limit and single-date-field constraints still apply.

## Voice routes for the remaining workflows — 2026-09-16

Outreach and prospect research now have private direct agent entries, concise
spoken responses, saved status queries and duplicate-reference checks. The research
helper checks persisted cancellation flags before external work and draft creation.
Email review and daily priorities have read-only agent routes saved as drafts;
their inbox poller and weekday schedule remain paused. The contract is in
[Other existing n8n voice routes](integration.md#other-existing-n8n-voice-routes).

Validation completed:

- Full SDK graphs and changed node configurations validated. Remote node
  parameters, execution settings and connection edges matched the tested graphs
  before publication. The retained disabled content chain produces an expected
  disconnected-node warning.
- **31 local checks passed**, exercising serialized Code nodes and graph paths:
  invalid inputs, essential clarification, exact retries, changed-reference
  conflicts, uncertain writes, existing form/internal callers, bounded research,
  status, both cancellation checkpoints, saved email reads and digest aggregation.
- Manual runs 482–484 returned explicit missing-record results for outreach,
  prospect status and email review without provider mutations.
- Content run 486 exposed an unsupported old Gateway model subnode. A supported
  Responses node then generated and saved three synthetic assets in run 487.
  Starter 06 was subsequently archived by the separate content-consolidation work;
  its attempted live replay was refused. It was not republished or reactivated.
  New content uses Idea to Content, not this retired route.
- Digest runs exposed the old `executeOnce` setting that discarded all but the
  first input row. Aggregation now reads the complete merged input. Calendar
  receipts and research control rows are excluded. Final read-only run 494 returned
  two saved email reviews and 43 Workbench records; it created no Gmail draft.
  These include historical test records and are not counts of current Notion tasks.
- Controlled prospect run 489 used a fictional search result and a stubbed worker
  start. Real cancellation run 491 wrote its stop flag. Worker test 492 read that
  flag, saved `CANCELLED` and returned before website access or draft creation.
  Status run 493 then returned the confirmed stopped state.
- Outreach run 490 exercised the real model and output validation with fictional
  details. Workbench writes and Gmail draft creation were pinned provider fixtures;
  it did not create a real Gmail draft. No email was sent in this validation pass.

Published versions, verified against the tested drafts:

| Workflow | Version |
| --- | --- |
| Starter 02 — Outreach and Follow-up Drafts | `95107997-e74c-41ad-9cec-e66ffbbd968a` |
| Starter 08 Helper — Research One Prospect | `bb3d8cf1-ebd5-4be4-a90d-a096788b8557` |
| Starter 08 — Find Prospects and Draft Outreach | `e8b68672-31dc-415f-90ac-086b27fcf152` |

Starter 01 remains unpublished at draft `aeb51740-5a86-473a-95a2-9a0548edf924`.
Starter 07 remains unpublished at draft `63a57411-4c2a-4dcc-b3cf-ae77b23b8b41`.
Planner and scheduler publication is unchanged from the preceding section.
Candidate graphs, baselines, local tests and selected run evidence remain in
ignored `test-results/n8n-planning/voice2-*` files. Synthetic Workbench records and
execution history remain; no customer records were edited by these tests.

These are workflow and tool-contract checks, not an end-to-end voice test. Hermes
must resolve follow-ups, serialise related writes, suppress stale results and
connect the actual speech stack. Cancellation is cooperative and cannot undo an
in-flight write. Saved receipts and progress need reconciliation after an unknown
provider outcome; no cross-service atomic lock was added.

## Grouped workflow names — 2026-09-16

The seven current n8n workflows were renamed using shared functional prefixes and
role numbers. See the [name and relationship map](integration.md#workflow-names-and-relationships)
for current names and historical Starter aliases. Workflow descriptions, five
linked-workflow display labels and the Hermes capability registry were updated.

Before/after comparisons passed for all seven workflows: stable IDs, runtime node
parameters, node settings, connections, credentials, form paths and active/paused
states were preserved. The only node-parameter changes were cached display names
for linked workflows. No workflow execution or external data write was needed.
The offline capability-registry validator and scoped whitespace checks passed.

The display-label versions were published for Find Prospects
(`6312f847-5f5f-486b-a909-24597ad57c37`), Research Prospect (Internal)
(`189a15a6-2b61-4fba-865d-5723229ef932`) and Project Planner
(`0b40744d-820e-4813-8fa3-35bd2ff0ace7`). Other version IDs are unchanged.
Final read-back confirmed the five active workflows match their intended versions;
the email organiser and priorities digest remain paused. The original metadata,
display labels and verification record are recoverable in ignored
`test-results/n8n-planning/workflow-group-renames-2026-09-16.json`.

## Bounded research and learning — 2026-09-17

Research Brief `0.2.0` adds an evidence-led investigation method, the portable
`research_control.py` host helper, and a local evaluation runner. The stable
skill identifier, output schema `1.0`, examples and existing output rules are
preserved. Detailed output instructions now live in the skill's output reference.
The archived runtime contract and original host integration separated source
availability from actual Hermes bindings. Current routing is documented under
[general research](integration.md#general-research). No n8n workflow or
partner deployment was changed.

### What the controls establish

The helper bounds steps, tool attempts, elapsed time, consecutive no-progress
observations and repairs. Terminal stops cannot be reset within a run; duplicate
queries and failed attempts count against limits. Observed source IDs and literal
excerpts are checked independently of model claims. Matching text establishes
attribution, not semantic truth. Host transport cancellation remains required.

Learning selects from a bounded tactic library using verified failure categories.
Promotion requires repeated paired trials on at least two held-out cases and one
regression case, independent semantic review, no candidate safety failures, no
per-trial score regression, and a measurable quality or cost improvement. A
relevant held-out failure must actually be resolved. The private memory uses
revision checks, atomic writes, definition hashes, scoped loading and rollback.
Instructions and executable tactics are both loaded into subsequent evaluations.
It does not retrain weights, collect facts as truth or guarantee improvement after
every request.

Automated tests exercise saving a qualifying fixture tactic, reopening its state,
loading it only in scope, rejecting unsafe/no-gain/unreviewed candidates and
rolling it back. These prove control and persistence behaviour using controlled
test signals; they are not evidence of improved model reasoning. Actual model
candidate outcomes are reported separately below.

### Repeated model comparison

The local Ollama `gpt-oss:20b` model ran on CPU using identical fictional supplied
sources, output schema and seeds for each arm. There were three rounds of four
evaluation cases per arm: **36 comparative generations**, plus one training
generation. Expected answers were never included in the model prompts. The
generic prompt already requested accuracy, supporting evidence, constraints and
explicit uncertainty; it was not deliberately weakened. Arm order rotated to
reduce ordering effects. This tests supplied-evidence reasoning and attribution,
not search quality, live factual research, voice or the partner's Hermes model.

| Method | Correct decisions | Exact-quotation passes | Semantically supported answers | Mean total tokens | Mean seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Generic prompt | 12/12 | 10/12 | 12/12 | 563 | 32.0 |
| Research skill instructions | 11/12 | 8/12 | 11/12 | 2,268 | 49.8 |
| Skill plus candidate quotation instruction | 10/12 | 12/12 | 10/12 | 2,387 | 49.0 |

Independent review checked every answer against its source text and calculations.
The skill selected AUD 40 over AUD 35 as cheaper in one run. The prompted
candidate selected AUD 64 over AUD 58 in another and claimed a cheaper option
when a compulsory competing charge was unknown. Its better quotation score did
not excuse those errors: promotion returned `candidate_safety_failure` and no
tactic was saved. The longer prompt did **not** demonstrate better decisions or
efficiency in this small local test. Other models and tasks require their own
evaluation; these results do not establish universal inferiority or superiority.

### Narrow procedural repair and fresh cases

A deterministic candidate restores only uniquely matching original source
passages after whitespace, typographic-hyphen or outer-quotation-mark changes.
It cannot change decisions, amounts, explanations or source identities. Tests
reject altered digits, currencies, negations, case and ambiguous matches.

Retrospective replay on the 12 generic answers increased exact-quotation passes
from **10/12 to 12/12**, with every other answer field unchanged and zero extra
model calls. Its relevant failures occurred only in regression cases, so the
gate rejected promotion with `no_relevant_holdout_failure`.

An independent reviewer then authored two fresh held-out comparisons and one
regression case before any generation. Two seeds produced **six further actual
generic answers**; the fixed repair was applied to those same answers. Every
before/after output was independently reviewed. Exact-quotation passes improved
from **1/6 to 6/6** without extra model calls. Structured checks improved from
1/6 to 3/6, but semantically supported answers remained **2/6**: the repair left
wrong comparisons, an unsupported choice with an unknown fee, and a contradictory
cost explanation unchanged. The fresh candidate also failed the safety gate and
remains disabled. This demonstrates useful quotation handling and conservative
rejection, not a proven upgrade in research reasoning.

The repair took about 1.4 milliseconds in aggregate across the six fresh outputs;
this is a small local measurement, not a throughput benchmark. Model token cost
was unchanged. No further batches were run to search for a favourable result.
The learning store starts empty; no actual model-tested tactic was promoted in
this evaluation. Do not market the skill as autonomous learning that improves
every answer, or as eliminating hallucinations.

### Reproduction and remaining acceptance

The original fixtures were `benchmark.json` and `quotation-benchmark.json`.
They and the following evaluation runner are now retained in the retirement
snapshot rather than the active repository; restore that snapshot before reuse.
Use `scripts/evaluate_research.py --output test-results/<run> --repeats 3`
for the main comparison. A finite fresh collection uses `--generic-only --suite
test-cases/research-brief/quotation-benchmark.json --repeats 2`; paired procedural
replay uses `--replay-repair <completed-run>`. Finalisation requires a trusted
independent `--review-file`; model self-scores cannot authorise learning.

Private raw responses, immutable answer review identities, receipts and reports
are under ignored `test-results/research-method/`, including `comparison-v3`,
`repair-replay`, `fresh-generic` and `fresh-repair`. Earlier interrupted runtime
attempts are preserved separately. A host interruption produced transport waits
beyond the configured deadline; affected attempts were excluded from the completed
comparison and that exclusion is recorded. This reinforces the need for real
host cancellation, rather than claiming the Python guard can terminate arbitrary
blocking code. No credentials or real customer research entered these fixtures.

Package/catalogue validation passes for four skill packages and 84 behavioural
case definitions; this checks definitions, not model behaviour. All **32 research
automated tests passed**, covering runtime stops, evidence validation, learning
gates, persistence, version changes and the evaluator. The full suite ran **197
tests: 196 passed and one was skipped** because this host cannot create the
symlink fixture. Scoped whitespace checks passed. The installer includes the
portable helper but excludes generated Python bytecode and cache directories.
Original output/schema compatibility and unrelated working-tree changes were
preserved.

Before deployment, the partner must wire real retrieval observations, transport
deadlines, trusted evaluators and per-user persistent memory into Hermes, then
repeat acceptance on the actual model and completed text/voice requests. A
Markdown installation alone cannot enforce runtime limits or persistent learning.

## Research prompt efficiency — 2026-09-17

Research Brief `0.3.0` reduces the routine entrypoint from **1,365 to 520 words**
(62% shorter). Shared evidence checks, private-note storage, stop limits and
learning boundaries remain in the entrypoint. Complex investigation guidance
moved to a conditionally loaded reference. Summary requests now write the
requested answer directly instead of first drafting a full report. Explicit
In depth requests and dashboard JSON retain their existing detail and schema.
The output contract, runtime helper and learning gates are byte-identical to
the saved v0.2.0 baseline; no tactic was enabled or memory rewritten.

An independent instruction review mapped prior rules to their new locations
and checked 12 realistic routing scenarios. It identified a missing routine-path
private-storage qualifier, which was restored before the final comparison.
Two new behavioural cases cover minimal routine context and preservation of
explicit depth/conflicting evidence. The catalogue and host integration guide
describe conditional reference loading; preloading the entire package would
lose the context saving.

The existing evaluator now supports a frozen baseline through `--compare-skill`.
The finite comparison uses four existing supplied-source cases, two repeated
seeds and both versions of the skill: **16 actual generations** with identical
model, evidence, output format, context size, output-token cap and temperature.
Order alternates by case and round to balance prompt-cache effects. It does not
update learning memory. Independent review must check actual answers, not just
successful JSON or exact quotation matches. Missing token telemetry cannot be
reported as a token saving.

The final measurements and independent semantic review are retained in ignored
`test-results/research-method/optimization-2026-09-17/paired/`. Recoverable source
baselines, the rule/routing review and progress record are in its parent folder.
Three completed baseline-only pilot runs in `comparison/` are excluded: that
pilot was stopped before any optimized answers to correct unequal cache
opportunities between versions. No completed final-comparison trial is excluded.

The comparison measures the routine entrypoint on local CPU Ollama
`gpt-oss:20b`, not complex investigations, live retrieval or the partner's Hermes
host. Wall time depends on cache state, output length and local system load;
the first baseline request benefited from the pilot's warm prompt cache. These
results establish only the measured local difference, not a guaranteed response
time on every question or deployment.

## Research skill retired — 2026-09-17

The user requested removal if the dedicated skill did not offer a useful edge
over generic research. The optimization reduced instruction overhead but did
not demonstrate that edge, so the active package was retired rather than kept
as an unproven extra layer.

Final optimization results: four supplied-source questions, two seeds per
version, the same local `gpt-oss:20b` model and resource settings, with order
alternating by case and round. All 16 actual answers received independent
review with method labels and grader expectations hidden.

| Measure | Previous v0.2.0 | Compressed v0.3.0 |
| --- | ---: | ---: |
| Mean input tokens | 2,003 | 1,008 |
| Mean total tokens | 2,223 | 1,228 |
| Mean response seconds | 59.1 | 43.2 |
| Median response seconds | 58.9 | 41.1 |
| Correct decisions | 6/8 | 6/8 |
| Independently supported answers | 6/8 | 6/8 |
| Exact-quotation passes | 7/8 | 7/8 |
| All structured checks passed | 6/8 | 5/8 |

Compression saved 44.7% of reported total tokens and 26.9% of measured mean wall
time relative to the prior skill. It fixed one unknown-fee decision but introduced
a wrong cheaper-option choice in another paired case; equal aggregate accuracy
hid that change. Both versions also failed the unknown-fee case in the second
round. The earlier generic comparison achieved 12/12 correct decisions, using
fewer tokens, on the same four tasks repeated three times. These small local
experiments do not establish universal superiority of generic prompting; they
do not justify retaining this dedicated skill under the user's criterion.

Removed the research skill instructions, references, schema/example, runtime
helper, experimental learning machinery, dedicated evaluator, case fixtures and
owned tests. Shared validation no longer contains its schema-specific branch.
The general research catalogue route now uses native Hermes reasoning and actual
search/page/file tools without a skill binding. Project planning, content,
calendar and all n8n workflow definitions/states are preserved, including the
separate prospect-research workflow. No research method was copied into the
shared Hermes prompt as a replacement hidden skill.

The installer implements the explicit retirement for previously owned files:
preview lists removals; apply verifies stored hashes, creates recovery copies,
removes only those files and updates ownership. Edited or unowned entrypoints
block preflight, and unrelated notes remain. Tests cover dry-run preservation,
backup/removal/idempotence, local edits, unowned copies and an edit during backup.
This source change does not claim to have removed anything from the partner's
live profile; the partner must apply the update there while Hermes is idle.

Recoverable source and checksums are under ignored
`test-results/research-method/retired-2026-09-17/`. All prior experiment reports,
raw answers and independent review receipts remain under
`test-results/research-method/`, including the final
`optimization-2026-09-17/paired/report.json`. The retired implementation is not
installed or loaded from these run artifacts.

After retirement, validation passes for the three remaining skill packages,
70 behavioural case definitions and the Hermes catalogue. The current automated
suite ran 165 tests: **164 passed, one skipped** because this host cannot create
the symlink fixture. The 34 dedicated research tests and four retired-schema
tests were archived with their removed implementation; four installer retirement
tests were added. Historical test counts above describe their original revisions.

## Expanded daily review — 2026-09-17

Implemented the [daily-review component](../components/daily-review/README.md)
and saved changes to the existing Daily Review, email organiser and calendar
workflows. Daily Review collects current email/spam/drafts, saved reviews,
confirmed organisation receipts, newly completed/pending/blocked work and the
connected Notion schedule. Local rules produce priorities, decisions, source-linked
meeting preparation and possible outstanding promises. No new external model call
is part of the saved implementation. The proposed external model step was rejected
by automatic approval review and replaced before saving with local analysis.

The email organiser records only its confirmed existing label actions; no new
folder-move rule or spam recovery was enabled. The calendar draft adds internal
`daily_review_context` with existing schema validation and current state tokens.
The previously published calendar version remains unchanged. Both email and
Daily Review remain inactive/unpublished, with their poller/schedule paused.
Their IDs and previous direct action names are preserved; Daily Review also
accepts `get_daily_review` and an optional previous-review timestamp.

Checks:

- n8n SDK and changed-node validation passed. Earlier SDK expression-path warnings
  came from empty sample-output hints, not runtime failures. The saved updates
  report no new validation warnings; the calendar retains its pre-existing Date
  method lint warning. Actual code uses native Date for those calls.
- Executions 504/508/516: fictional end-to-end voice/text review, covering email,
  spam, drafts, organisation receipts, completed/ongoing/blocked work, due tasks,
  meeting preparation, promise evidence and identity-preserving output.
- Execution 505: calendar draft's new read operation returned today's Event/Task
  and open tasks with `mutated: false`; provider reads and persistence were pinned.
- Execution 506: scheduled branch with Gmail creation and persistence pinned.
  Execution 515: duplicate-day gate produced no item and neither draft creation
  nor receipt writing ran.
- Execution 507: email label confirmation and receipt generation with provider
  calls and persistence pinned; message ID/label IDs matched before logging.
- Executions 513/514: empty sources return a completed empty review; failed inbox
  and calendar sources return partial with explicit unavailable-source speech.
- Executions 509/517: manual development reads against actual connected Gmail,
  saved tables and the calendar owner succeeded. Final execution 517 checked all
  sources and returned the complete structured/text response. No Gmail message was
  sent, moved, recovered or drafted by these agent-route reads, and no Notion item
  was changed. The calendar owner retained its existing internal read receipts.
- Twelve Node behaviour tests passed, including authored/quoted promise handling,
  later fulfilment cues, source caps, failed analysis, dates, priority ordering,
  exact excerpts, valid references and organisation truthfulness.
- Repository validation passed for three skill packages, their 70 case definitions,
  the Hermes catalogue and ten new daily-review host acceptance case definitions.
  The repository Python suite ran 165 tests: 164 passed and one symlink fixture was
  skipped. An initial run with bundled Python lacked project dependencies; rerun
  in the existing `.venv` passed without changing dependencies.

Actual Hermes microphone, speaker, interruption and dashboard follow-ups remain
partner-host acceptance work. Publication is separate because it starts background
processing. The action log describes labels rather than inferred moves. Spam
matching, meeting associations and possible commitments use limited explicit rules;
they are candidates to inspect, not comprehensive semantic detection or proof.
Same-day Gmail draft delivery remains a serialised check/create/record sequence;
an uncertain write requires reconciliation before retrying.

Private baseline exports and generated SDK/operation artifacts are retained under
ignored `local/daily-review-backup/` and `local/daily-review-build/`. Maintained files
contain no connected mailbox content or credentials. Concurrent research-skill
retirement and unrelated content-preview work were preserved.

## Daily review preparation and saved retrieval — 2026-09-17

This revision supersedes the preceding Daily Review delivery/analysis contract.
The user requested a daily preparation run at a chosen time, with Hermes later
retrieving the information and producing the review. The separate email push
workflow was not edited, tested, published or otherwise changed by this revision.

The saved Daily Review draft now has two disconnected paths: scheduled/manual
source collection with Workbench snapshot persistence, and read-only retrieval
of the most recently saved snapshot. Scheduled local analysis, formatted briefing
generation, the Gmail digest draft and the duplicate-delivery gate were removed.
Hermes owns priorities, decisions, meeting preparation, possible commitments and
the final user output. Source coverage, timestamps, references and missing/stale/
partial states remain explicit. Each collection execution has its own save key;
partial snapshots do not replace the complete checkpoint.

Checks:

- Twelve Node tests passed: collection windows and DST, complete checkpoints,
  persistence/retrieval, caps/failures, missing/corrupt/future/stale snapshots,
  work states, action receipts, evidence for Hermes, retry identities and graph
  separation. Both retrieval action names retain request/session/revision identity.
- n8n SDK validation passed. Its expression-path hints use empty sample outputs;
  runtime checks verify those actual fields. Final saved workflow validation has
  no warnings and its two groups cover preparation and retrieval.
- Execution 519: fictional collection and source assembly succeeded with all
  provider nodes and final persistence pinned. Execution 520 retrieved that
  prepared fixture. Execution 521 returned `not_found` for empty saved storage.
  Execution 522 preserved unavailable inbox/calendar coverage as `PARTIAL`.
- Execution 523: manual development collection read actual connected sources and
  saved a complete `daily_review` snapshot in Workbench. Execution 525 retrieved
  that same snapshot by its saved identity, returning `source_mode: saved_snapshot`
  and `live_sources_checked: false`. No Gmail message/draft or Notion item was
  created or changed. The calendar owner retained its internal read receipts.
- Repository validation passed for three skills, the catalogue and twelve daily
  review host case definitions. Focused Python orchestration, installation and
  validation checks also passed; the unsupported symlink fixture was skipped.

Daily Review remains unpublished. Its **Daily preparation time** node is now
daily, including weekends, and disabled pending a chosen time. The retained 08:00
Australia/Brisbane value is only a placeholder. The calendar's internal read
extension remains a saved draft; its production version is unchanged. No workflow
was published by this revision. Partner-host speech/dashboard acceptance and
selection of the daily activation time remain outstanding.

Private pre-change exports and generated artifacts are in ignored
`local/daily-review-before-prepare/` and `local/daily-review-prepare-build/`.
Connected source contents are not copied into maintained files.

## Organiser video integration — 23 September 2026

Kept the existing owners and added cross-organiser contracts and nine host
acceptance cases. The video comparison and transcript limitations are recorded
in `docs/organiser-video-review.md`.

Published only the email owner's `Return email reviews` node on top of the
concurrent category/filter changes: version
`f9025a8e-7ad2-401e-a619-609ebfc1b93e`. It preserves message/thread/draft identity,
category/status filters and counts, and adds historical age and source/calendar
refresh requirements. All other nodes, connections and settings were unchanged.
Cloud test 965 exposed count serialization that offline tests missed; the
corrected version passed execution 970 and was verified against the publication.

Checks: seven Node transport tests, repository validation, 19 orchestration
tests, and 26 installer tests (25 passed; one platform skip). Nine organiser
case definitions were checked structurally, not run on the partner host.
Read-only calendar executions 967 and 971 returned current tasks and available
slots. Planner draft executions 968 and 973 exercised broad and detailed modes;
no Notion tasks or bookings were saved. Detailed mode respected the requested
hours/windows. Broad mode exposed an existing target-week-to-deadline conversion
and requires a separate correction before calling that path accepted.
Daily Review retrieval 972 correctly marked the saved September 21 snapshot
stale/partial and performed no live collection. Its preparation schedule remains
paused pending the user's chosen time. No mail was sent.

Actual Hermes installation, voice/text acceptance, and missing host contact or
live-mail tools remain partner-host work. Local source and n8n checks do not
establish that deployment.

### Planner deadline correction

The broad-plan defect above was a formatter fallback, not generated model
output: after validating deadlines, `Format result` replaced null broad task
deadlines with target-week ends. Removed just that fallback and retained the
exact formatter source in `components/planning-sync/n8n-format-result.js`.
Five regression tests execute that source: null deadlines, explicit deadlines
in both modes, horizon-only dates, existing/replayed deadlines, invalid dates
and completed-task protection. All passed; node configuration validation passed.

Cloud execution 975 returned two broad tasks with null deadlines and separate
week targets, with `sync_started: false`. Published planner version
`574f8703-fc97-4462-9587-5a1c394ab820`; only `Format result` changed, with all
connections and settings retained. The existing canvas grouping warning is
unrelated to execution. Historical saved proposals/Notion tasks were not edited.
Existing save paths were not exercised with real writes during this review.

The user explicitly chose to keep Daily Review preparation paused.
