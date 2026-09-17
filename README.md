# LARP

Shared skill packages for the Hermes-based agent and dashboard we are building and demonstrating. The paid offer is a course teaching buyers how to recreate the setup and its add-ons. See [project context](docs/project-context.md) for the current business model and division of work.

## Partner quick start

The shared source is in the public [larp repository](https://github.com/FrameBoostPC/larp).
Anyone can read or clone it without a repository invitation or GitHub sign-in:

```sh
git clone https://github.com/FrameBoostPC/larp.git
cd larp
```

Track work on the linked [larp project board](https://github.com/users/FrameBoostPC/projects/2).
The board is private and requires separate access. Pushing changes to the repository
also requires collaborator access.

Read [project context](docs/project-context.md), then follow the
[partner setup for our existing n8n instance](components/hermes-orchestration/partner-setup.md).
It includes a copyable Hermes prompt, optional MCP connection installer, sign-in
steps and a read-only workflow check. Your partner runs it on their computer.
The repository contains source, contracts and setup guides; access to the running
n8n instance and the partner's Hermes/dashboard host is configured separately.

## Skills

Each skill is a portable folder with instructions, a dashboard output schema, and an example. Package versions are declared in each `SKILL.md`; these are development candidates to test in the target Hermes environment before including them in course materials.

| Skill | Result | Example request |
| --- | --- | --- |
| [Content Creation](skills/idea-to-content/SKILL.md) | Create or adapt content, profile copy, scripts, posts and newsletters | “Use this transcript for two posts and a newsletter.” |
| [Project Planner](skills/project-planner/SKILL.md) | Broad milestones and target weeks, with optional effort estimates and calendar-aware detail | `/project-planner Give me a four-week portfolio launch timeline without hourly planning.` |
| [Calendar Planner](skills/calendar-planner/SKILL.md) | Review availability or schedule and edit accepted tasks using current shared state | `/calendar-planner Review my free project time next week without booking anything.` |

The skills return readable answers by default. Add `Return dashboard JSON` to request the structured result defined in that skill's `templates/output.schema.json`. See [dashboard integration](docs/integration.md) for status meanings and application responsibilities.

Idea to Content is the single content creation and repurposing feature. Say or type what you want, supply source material or refer to an available current draft, and request the formats you need. A plain repurposing request defaults to a LinkedIn post, a short social post and a newsletter with a subject; a new idea retains the hooks/script/posts default. Follow-up requests can change just one draft. The separate **Starter 06 - Content Repurposing Drafts** n8n workflow was archived on 2026-09-16; its existing Workbench records remain available. See the [combined content and voice contract](docs/integration.md#idea-to-content-creation-and-repurposing).

All new and updated workflows must prioritise voice: direct agent actions, shared
conversation state, optional inputs and concise spoken results. See the
[voice-first workflow standard](docs/integration.md#voice-first-workflow-standard).

Hermes should infer the necessary steps from the user's goal, including creating
and adapting content for named platforms without a repurposing command. Broader
goals can combine writing, connected tools and existing workflows. Complete
authorised routine steps autonomously and ask only for essential blockers;
see the [goal execution contract](docs/integration.md#goal-execution-and-autonomy).
Social-account creation still requires capabilities in the actual Hermes host.

The existing [n8n project planner](https://automatedai.app.n8n.cloud/workflow/tJ6YmJuFsyEoWYXw) is wired to the [n8n scheduling workflow](https://automatedai.app.n8n.cloud/workflow/rTed7PRf60fF2MjA) and its configured **Notion account 2 / Schedule & Tasks** database. Notion Calendar displays the same pages. The planner defaults to a broad four-week timeline; optional detailed planning estimates required effort and proposes sessions using calendar availability, working preferences and optional limits. Both modes retain shared task identities, edits and progress. Saving tasks does not automatically book suggested sessions. The mode update was live-tested and published on 2026-09-16. See the [n8n integration and recovery guide](docs/integration.md#weekly-planning-notion-and-calendar-sync).

The [portable Python planning-sync component](components/planning-sync/README.md) is an optional alternative for a separately deployed Hermes host. It has its own Notion schema, persistent state and calendar client contract; it is not the implementation running these n8n workflows.

Idea to Content supports **Engaging, Educational, Entertaining, Emotional, Professional, and Custom** writing styles. You can combine a primary style with one secondary influence and choose energy and wording, or describe the voice naturally. For example: `/idea-to-content Write a 45-second script about public speaking. Style: Engaging + Educational. Energy: Bold. Wording: Conversational. No slang.` It drafts immediately when no style is supplied. A [portable selector component and local preview](components/content-preferences/README.md) implement tone/intensity controls, simple typed instructions and optional microphone input. The partner connects it to the custom dashboard and agent using the [integration guide](docs/integration.md#idea-to-content-writing-style-controls).

Project Planner supports **Summary** and **In depth** reading views. Chat defaults to Summary; ask for `In depth only` or `both views` when needed. Dashboard JSON contains a condensed `summary` and complete `data` in the same response, ready for the dashboard's view toggle. Both views retain important limitations and describe the same result.

The dedicated Research Brief skill was retired after evaluation on 2026-09-17.
Hermes handles ordinary research with its native reasoning and connected search,
page and file tools. No separate research skill or self-learning layer is
installed. The existing prospect-research n8n workflow remains available. See
[the evaluation and retirement record](docs/validation.md#research-skill-retired--2026-09-17).

The [local generation preview](components/content-preferences/README.md#run-the-preview) produces finished Idea to Content drafts using a configurable model. Its initial model is OpenAI's open-weight gpt-oss:20b through Ollama. Model files and private configuration stay in ignored local storage; your partner can select a different model or connect the same UI to Hermes.

## Structure

```text
skills/
  idea-to-content/
    SKILL.md
    templates/output.schema.json
    examples/example-output.json
    references/readable-output.md
    references/writing-styles.md
    references/repurposing.md
  project-planner/
    SKILL.md
    templates/output.schema.json
    examples/example-output.json
  calendar-planner/
    SKILL.md
    templates/output.schema.json
    examples/example-output.json
test-cases/<skill-name>/cases.json
scripts/validate.py
components/content-preferences/
  controls.mjs
  controls-template.mjs
  controls.css
  state.mjs
  intent.mjs
  demo.html
  demo.css
  demo.mjs
  generation-view.mjs
  server.py
  model.example.json
  start-demo.ps1
components/planning-sync/
  planning_sync.py
  notion_adapter.py
  calendar_adapter.py
  cli.py
  config.example.json
  requirements.txt
  README.md
```

Each package is independent. Keep links to its resources in `SKILL.md`; Hermes's installer only includes referenced support files. Test cases and developer tooling stay outside installable skill folders. Example outputs are illustrative, not completed work for a customer.

## Shared Hermes setup

Use the [orchestration installer and partner guide](components/hermes-orchestration/README.md)
to install all three skills and the shared operating policy into the active Hermes
profile. Hermes owns goals, conversation, context and voice; skills supply
expertise, while actual connected tools and workflows perform operations. The
policy applies across current and future features. Content Creation keeps the
`idea-to-content` identifier for existing integrations.

The installer previews by default, preserves existing personality and unrelated configuration,
and protects locally edited files. It includes the capability catalogue and
verified direct-workflow contracts. Optional `--n8n-url` adds the existing instance's
MCP connection configuration; the partner completes authentication and host speech
acceptance. The existing published n8n routes already fit
this architecture. Paused workflows and the archived repurposing workflow retain
their states. See [project working instructions](AGENTS.md) for future changes.

## Install into a development Hermes agent

The shared installer above is the recommended complete setup. To install only
individual skills, register this public repository and install the packages:

```sh
hermes skills tap add FrameBoostPC/larp
hermes skills install FrameBoostPC/larp/idea-to-content
hermes skills install FrameBoostPC/larp/project-planner
hermes skills install FrameBoostPC/larp/calendar-planner
hermes skills list
```

Start a new Hermes session and invoke a skill using a request from the table. For a manual transfer, copy the complete skill folders into the active Hermes profile's skills directory (the default is `~/.hermes/skills/`), then start a new session. Use a development profile so testing does not change a customer installation.

Content drafting and relative project planning need no connected external services. Current web research needs working search/page-reading tools; without them Hermes must report its limits and can use supplied text. Calendar planning uses current task state and availability. Skills do not install dependencies or connect accounts. The existing n8n setup uses its configured Notion connection; a Hermes host can call those workflows after integration and validation, or separately deploy the optional Python component with its required accounts and provider client. These packages do not include a publisher, video renderer, or complete dashboard application. The separate selector and sync components are not installed with the skills.

## Validate and test

Developer tooling requires Python 3.10+ and the packages in `requirements-dev.txt`; they are not required merely to load a skill in Hermes. In an activated virtual environment:

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate.py
python -m unittest discover -s tests -v
```

Validate a response saved from an agent run:

```sh
python scripts/validate.py --output idea-to-content test-results/my-content-result.json
```

The checks cover package structure, referenced resources, schemas, example outputs, and selected data invariants. They do not prove writing quality, citation truth, or successful execution inside Hermes. `test-cases/` contains realistic prompts and criteria for behavioural review; the validator does not run those prompts through a model automatically.

For each skill, run its cases in Hermes with the intended model and tools. Check discovery, source access, requested formats/counts, useful output, JSON validity, and missing-input behaviour. Record the Hermes version, model, tools, input, output, and result outside the distributable packages. Generated local outputs go under ignored `test-results/`.

## Working together

1. Make a focused change to one skill on a `codex/` branch.
2. Add or update cases for the behaviour being changed; avoid rules that overfit one example.
3. Run local validation and relevant Hermes cases.
4. Review the change together before including it in a course release.
5. Update the skill version and tag a tested release when its target-environment checks pass.

Keep credentials, personal configuration, customer data, and private outputs outside this repository. Document required capabilities without secret values. See [validation notes](docs/validation.md) for what has actually been checked so far.

## References

- [Hermes skills system and repository installation](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)
- [Working with Hermes skills](https://hermes-agent.nousresearch.com/docs/guides/work-with-skills)
- [Agent Skills format](https://agentskills.io/specification)
