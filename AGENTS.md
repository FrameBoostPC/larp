# Project working instructions

Read [project context](docs/project-context.md) before changing this repository.
It owns the product direction and records which integrations actually exist.
Preserve unrelated work in a dirty checkout.

All existing and future features follow the shared
[Hermes operating model](components/hermes-orchestration/instructions.md):
Hermes orchestrates goals, conversation and voice; skills provide expertise;
connected tools/workflows own bounded operations. Voice and ordinary prompts
are primary. Do not require users to name workflows or use forms for clear tasks.

When adding or changing a capability, update its entry in
[the catalogue](components/hermes-orchestration/capabilities.json), its owning
skill or tool contract, and relevant behavioural cases. Preserve published,
paused, internal and retired distinctions. Discover actual connected tools;
do not represent catalogue entries or draft outputs as executed capabilities.

Keep skills independently installable and retain stable identifiers unless a
migration is explicitly part of the task. Follow the
[orchestration component guide](components/hermes-orchestration/README.md) for
installation and future-feature acceptance. Run `python scripts/validate.py`
and relevant tests before delivery. This check includes catalogue coverage, so
new skill packages also need a registered conversational route.

The partner owns the actual Hermes/dashboard host. The local content preview
calls a model directly. Do not describe source changes or staging tests as a
live deployment. Credentials and private results stay outside maintained files.
