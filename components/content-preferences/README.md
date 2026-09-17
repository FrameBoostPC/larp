# Content preferences component

A framework-neutral `<content-preferences>` custom element for **Content Creation**, using the stable `idea-to-content` skill, plus a local generation prototype. The element owns selectors and input events; the Python server calls a separately configured model and validates its result. Both remain separate from the installable Hermes skill folders. Your partner can reuse the controls and output schema with a different model or their Hermes backend. Install the [shared Hermes setup](../hermes-orchestration/README.md) on that host to obtain the common skill/tool orchestration policy; this preview remains a direct model client.

## Run the preview

The full preview needs Python 3.10+, the repository's `requirements-dev.txt` dependencies, and a model runtime. The default is OpenAI's open-weight **gpt-oss:20b** served locally by [Ollama](https://ollama.com/library/gpt-oss). The model download is approximately 14 GB and generation speed depends on the machine. ChatGPT itself is a separate hosted product.

With Ollama installed and running, download the model once:

```sh
ollama pull gpt-oss:20b
```

From the repository root, using your activated Python environment:

```sh
python components/content-preferences/server.py
```

Open `http://127.0.0.1:8765/demo.html`. Enter a brief, choose the voice, then select **Generate content**. The server runs the actual Idea to Content instructions with the model; the UI shows copyable drafts, with guidance and production notes kept separate. It does not display the technical prompt or raw JSON. The preview calls the model directly rather than running Hermes itself. An ordinary static file server does not provide generation.

On this Windows laptop, [start-demo.ps1](start-demo.ps1) also starts the project-local Ollama runtime if it is stopped. From the repository root run `./components/content-preferences/start-demo.ps1`. It uses `.venv`, optional `local/content-model.json`, and the downloaded runtime/models under ignored `local/`. It does not install or download anything on startup. Close the preview server with Ctrl+C; the background model service can remain available and releases idle model memory automatically.

Generation uses the accepted preference snapshot and original brief. Changing the brief or preferences makes older results visibly out of date and prevents a late response from replacing the current result. Cancel stops the browser waiting and rejects late results; it does not guarantee an upstream model immediately stops computing. The local server accepts one inference at a time and reports when the model is still busy. Requests that fail or return invalid content produce an error, never a substitute example.

## Choose another model later

Copy [model.example.json](model.example.json) to the ignored `local/content-model.json` and change `provider`, `base_url`, and `model`. Start the server with:

```sh
python components/content-preferences/server.py --config local/content-model.json
```

Supported providers:

| Provider | Example base URL | How it connects |
| --- | --- | --- |
| `ollama` | `http://127.0.0.1:11434` | Appends `/api/chat`; uses the installed model name |
| `openai-compatible` | `http://127.0.0.1:1234/v1` | Appends `/chat/completions`; requires a compatible endpoint and model |

The model name is configuration, not a skill instruction. Restart the server after changing it. Context length, output limit, timeout, temperature and reasoning settings are also configurable; check the chosen model's support and test output quality after switching. An OpenAI-compatible endpoint does not mean every provider or model supports every setting.

With `thinking: null`, the Ollama adapter selects low reasoning for gpt-oss and leaves other models' reasoning settings alone. `temperature: null` omits that setting for models which do not accept it. Compatible endpoints can choose `token_parameter: "max_tokens"` or `"max_completion_tokens"`. `HERMES_MODEL_CONFIG` selects a configuration file; `HERMES_MODEL_PROVIDER`, `HERMES_MODEL_BASE_URL`, `HERMES_MODEL_NAME` and corresponding setting variables override file values in the server and Windows launcher.

If a hosted endpoint needs credentials, set `api_key_env` to the name of a server-side environment variable and put the key in that environment variable. Never put keys in browser files, request bodies, committed configuration, or the shared repository. Hosted inference needs the provider account and can incur charges; the default local Ollama configuration has no hosted API key or per-request API bill. Local model files belong outside source control.

The prototype binds to `127.0.0.1`, serves only its own UI files, checks request origins and validates outputs against the existing skill schema and semantic checks. It is a local development server, not the partner's authenticated multi-user application. It has no web research tools, publishing, saved profiles or permanent draft storage. Content stays in the current page unless copied; model output is a draft to review.

## Create and repurpose through the same request

Idea to Content handles both new ideas and existing source material. Paste notes,
an article or a transcript into the brief, then say or type a clear request such
as “Repurpose this into a LinkedIn post and a newsletter.” You can also supply the
source in the request itself. There is no required mode selector. A generic
repurposing request uses the skill's LinkedIn/short-post/newsletter pack; specific
formats and counts override it. Only available source text can be used: the local
model cannot open links or listen to uploaded media.

The local preview routes clear content commands from the instruction box or a
completed microphone transcript to the same generation call. Its simple command
router is separate from the conservative writing-preference parser. Interim
speech does not generate drafts, duplicate events are ignored, and newer accepted
input makes older results stale. Existing-draft requests pass the real previous
result; original source context stays separate from that generated copy.

The generation response includes `spoken_summary` alongside the unchanged
schema-1.0 `result`, `model` and `provider`. Missing-input speech asks the essential
question; partial results mention their limitation. The preview displays this
completion text; Hermes should speak it through its existing audio layer after
checking the request is still current. Full conversational source/target resolution,
readback without regeneration and actual spoken playback belong to that host.
The separate n8n repurposing workflow is archived; this feature does not call it
or automatically save new drafts into its Workbench.

The default local gpt-oss:20b model failed two source-fidelity acceptance runs:
it presented a fictional exercise as a completed event and missed newsletter
length constraints. Treat its output as drafts requiring source review, not a
validated production repurposing service. See [validation evidence](../../docs/validation.md#unified-content-creation-and-repurposing--2026-09-16)
and run the behavioural cases with the partner's intended model.

The backend expects this repository's `skills/idea-to-content` and `scripts/validate.py` paths. Keep the repository checkout intact when running it. It loads the skill, writing styles and repurposing guide together. Frontend integration can copy only the browser modules/styles; the partner can replace `POST /api/generate` with their Hermes integration. The prototype request contains `brief`, `preferenceContext`, `action`, optional `instruction`, and `previousResult` for rewrites. A successful response contains the validated skill `result` plus `spoken_summary`, `model` and `provider`; failures contain a readable `error`. `GET /api/model` reports configuration and busy status, not proof the model is installed or reachable.

The offline interpreter recognises complete, simple commands such as `Tone: educational`, `Emotional and calm`, `Make this emotional, but keep it subtle`, `Make it a little less intense`, and `Custom: warm, dry humour, no jargon`. Unrecognised, conflicting or compound instructions are reported without partially applying them. For example, `Make it emotional but no slang` requires the Custom voice field or the host interpreter. It is deliberately not a general language model. Existing custom directions survive preset changes; an explicit `Custom:` instruction replaces the previous custom description.

Microphone input uses `SpeechRecognition` or `webkitSpeechRecognition` when available. Recording begins only on a user click; a completed utterance is passed through the same interpreter as typed text. Unsupported or declined microphone access leaves text/buttons usable. Some browser speech services process audio online and may not work offline; see [MDN's speech recognition reference](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition). In-app browser support is not assumed. Inject the partner's existing Hermes speech adapter for its production voice workflow.

## Change the UI

The prototype keeps its layout and styling separate from its behaviour:

| File | Responsibility |
| --- | --- |
| [controls.css](controls.css) | Component colours, spacing, sizes and responsive layout |
| [controls-template.mjs](controls-template.mjs) | Component markup and visible labels |
| [controls.mjs](controls.mjs) | Input handling, shared-store binding and speech callbacks |
| [state.mjs](state.mjs), [intent.mjs](intent.mjs) | Accepted choices, conflict protection and instruction interpretation; no DOM dependency |
| [demo.html](demo.html), [demo.css](demo.css), [demo.mjs](demo.mjs) | Minimal generation preview; not required by the embedded component |
| [generation-view.mjs](generation-view.mjs) | Safe content rendering and per-asset copy buttons |
| [server.py](server.py), [model.example.json](model.example.json) | Local model adapter and replaceable configuration; the partner can use their own backend |

For a quick restyle, set CSS variables on the element in your dashboard stylesheet:

```css
content-preferences {
  --voice-accent: #b6c9ff;
  --voice-accent-ink: #152044;
  --voice-selected: #242e45;
  --voice-radius: 10px;
}
```

Other theme variables are `--voice-ink`, `--voice-muted`, `--voice-border`, `--voice-surface`, `--voice-error` and `--voice-recording`. Match text/background colours when changing themes. The component also exposes `selection`, `option`, `advanced`, `input`, `button`, `primary` and `status` shadow parts for host CSS, for example `content-preferences::part(primary) { width: 100%; }`.

For layout changes, edit the template and CSS. Preserve the IDs, radio `name`/`value` attributes, `.mic`/`.status` classes and native control semantics used by `controls.mjs`; keep the radio immediately before its `.tile` for selected/focus styling. The first `details` element contains the custom voice field, and the microphone button contains a `span` for its changing label. Retain accessible labels and the live status region. Keep user-supplied text in `textContent`/`value`, outside template HTML.

Ship `controls-template.mjs` and `controls.css` alongside the existing modules; the stylesheet URL resolves relative to the component, not the host page. When using a bundler, ensure it copies that CSS asset. There is no build step for direct browser imports. Run the existing browser suite after changing markup or packaging.

To replace the custom element entirely with your partner's UI framework, reuse `state.mjs` and `intent.mjs`, subscribe all views to the same store and route every input through `apply`. The current component is a reference for the speech lifecycle, request snapshots and stale-input handling that the replacement must retain. Reskinning the existing component preserves those behaviours automatically.

## Embed and connect

```html
<script type="module" src="./content-preferences/controls.mjs"></script>
<content-preferences scope-label="This script"></content-preferences>
```

Set `action-label="Generate content"` to rename the action button without changing its request event. The optional boolean `busy` attribute disables new requests while the host is generating; the host clears it when the run ends. The demo owns both attributes. These attributes do not change tone, intensity or wording.

Use one store per editing scope. Every selector view for the same scope must share that store; do not maintain independent button, chat and voice values. `scope-label` is a display label, not an asset identity or a mechanism for loading another asset's saved preferences. The host owns asset IDs, per-user persistence, source facts, run cancellation and results. Changing the label refreshes the display and invalidates pending interpretation; bind the correct store when changing actual scope.

```js
import { createPreferenceStore } from './content-preferences/state.mjs';
const shared = createPreferenceStore();
mainControls.store = shared;
floatingControls.store = shared;
// Direct host updates also refresh every connected view synchronously.
shared.apply({ tone: 'emotional', intensity: 'calm' }, { source: 'voice' });
```

Accepted values stay authoritative until the user deliberately changes those fields. The store never restores fallbacks after generation or takes new preferences from the model's output. Every input updates the same state, the component renders from it, and each request snapshots it. Keep saved defaults as initial/fallback context; do not replay them through `apply` after the user has made a choice. Text in the instruction box is a draft or transcript, not another selected value.

The `store` setter unsubscribes the old store, cancels pending interpretation/capture and immediately displays the new store. A detached view resynchronises on reconnection. `store.subscribe(listener)` returns an unsubscribe function and synchronously delivers detached `{status, state, source}` notifications for accepted nonempty updates, including same-value reaffirmations. Empty, duplicate, invalid or conflicting updates do not notify. Reentrant updates are delivered in acceptance order. One throwing listener does not prevent other views receiving updates; its error is reported in that `apply` result's `notificationErrors` array. Subscribers should render/read state rather than feed it back into the same store.

```js
const controls = document.querySelector('content-preferences');
controls.setPreferences({ tone: 'educational', intensity: 'bold' });

controls.addEventListener('preferences-change', ({ detail }) => {
  // detail.state contains a detached snapshot. Persist only if the user requested it.
});

controls.addEventListener('content-request', ({ detail }) => {
  // Send detail.preferenceContext + the original brief/draft through YOUR Hermes
  // integration. detail.action is generate or rewrite. Use your real asset ID.
  // Capture detail.state.revision and the asset's version before starting work.
  // Validate the result against the skill schema before displaying it. Check the
  // revision/version again so late results cannot replace newer edits.
});
```

`requestContent('generate' | 'rewrite')` emits one request with a detached state snapshot. Changing selectors alone emits no content request. The built-in parser treats `Make this…` as a rewrite request and `Set the tone…` as a settings update. Preparing a request waits for the component's current instruction to resolve; a completed voice instruction can issue its requested action. Caller metadata cannot override the snapshot, action, scope or preference context. The demo sends a rewrite with its actual previous result and reports a missing draft if none exists. Any shared-store change marks older generated content out of date.

`preferences` returns `{revision, values, fieldRevisions}`. UI `tone` maps to the skill's Writing style; `intensity` maps to Energy. `values` contains `tone`, `intensity`, `wording`, `customVoice`, and optional `secondaryTone`. The current UI offers the first four; hosts can set `secondaryTone` programmatically. Tone, intensity and wording all support deliberately reaffirming the currently selected radio. Zero field revision means an untouched fallback, which the generated request explicitly labels. The request also states that accepted choices supersede older preferences in the brief for the same fields. `setPreferences()` represents deliberate accepted choices. Use a new store with no initial values for untouched defaults. `preferences-change` is also emitted with `status: 'rebound'` and `source: 'binding'` when the component switches stores.

## Connect the agent's language understanding

Set `controls.interpretText` to your async interpreter with this signature:

```js
// Values are a detached snapshot; metadata has source, baseRevision and eventId.
controls.interpretText = async (text, values, metadata) => {
  // Ask YOUR backend to interpret the complete instruction in the current scope.
  // Return, for example:
  return { patch: { tone: 'emotional', intensity: 'calm' }, action: 'rewrite' };
};
```

The return above is an interface illustration, not a working backend: do not use a constant response in production. Return only the changed fields in `patch`, preserving custom directions unless the user changes them. Supported actions: `settings`, `generate`, `rewrite`, or `clarify` with a short `message`. Conflicting/unclear input should return `clarify` and an empty patch. Topic changes, length edits, multi-asset targets, saved profiles and agent speech controls belong to the host's full conversational router; this selector handles writing preferences only.

`submitInstruction(text, {source, baseRevision, eventId})` is available for host-delivered text or completed transcripts. Sources are `text` or `voice`; button changes use `setPreferences(patch, options)`. Capture `baseRevision` when the input begins and use a stable event ID. Accepted changes update the visible controls. The store rejects stale conflicting fields atomically, permits unrelated stale changes, and retains the last 256 accepted event IDs to avoid duplicate delivery. Durable/network deduplication belongs to the host. Pending interpretations are discarded after a newer instruction, scope-label change or element removal. Locally captured voice interpretations are also invalidated by microphone cancellation/replacement.

## Connect speech

Assign `controls.speechAdapter` with this interface:

```js
controls.speechAdapter = {
  start({ onStart, onInterim, onFinal, onError, onEnd }) {
    // Start YOUR transcription service only after this user-initiated call.
    // onStart(): recording has actually begun.
    // onInterim(text): display only; do not execute.
    // onFinal(text): one completed utterance; do not paraphrase user intent.
    // onError(message): failed/denied service; onEnd(): capture finished.
    return {
      stop() { /* End recording and request its final transcript. */ },
      abort() { /* Cancel recording and release the microphone. */ },
    };
  },
};
```

The sketch above documents callbacks; replace the empty methods with actual service controls. Component removal and adapter replacement cancel capture. Typed submission retires active capture so the same visible transcript cannot execute twice. Calling `cancelVoice()` discards pending locally captured speech interpretation as well as capture callbacks. Host-delivered transcripts should manage their own cancellation lifetime before calling `submitInstruction`.

Spoken assistant replies, playback speed/voice, reading drafts aloud and full-duplex audio are outside this writing-style component. Keep them in the existing voice layer.

## Tests

Node 20+ is sufficient for the dependency-free checks:

```sh
node --test components/content-preferences/state.test.mjs components/content-preferences/intent.test.mjs
```

The browser suite additionally needs Playwright available to Node and a browser installed for it:

```sh
node --test components/content-preferences/browser.test.mjs
```

Backend tests use a fake model service and do not need a downloaded model:

```sh
python components/content-preferences/server_test.py -v
```

Optionally set `PLAYWRIGHT_MODULE` to an installed Playwright module entry path, `PLAYWRIGHT_CHANNEL` to a locally installed supported channel such as `msedge`, and `CONTROLS_SCREENSHOT` to an output PNG path. The suite starts its own loopback server, uses an isolated headless browser, and injects speech callbacks; it never records microphone audio. Production custom-dashboard integration and actual speech-service transcription still require testing on the partner's machine.
