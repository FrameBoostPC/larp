import './controls.mjs';
import { buildPreferenceContext, interpretPreferenceText } from './intent.mjs';
import { renderContent, validateGenerationResponse } from './generation-view.mjs';

const controls = document.querySelector('content-preferences');
const topic = document.querySelector('#topic');
const request = document.querySelector('#request');
const info = document.querySelector('#request-info');
const results = document.querySelector('#results');
const cancel = document.querySelector('#cancel');
const retry = document.querySelector('#retry');
const copyStatus = document.querySelector('#copy-status');
const modelInfo = document.querySelector('#model-info');
let active = null;
let sequence = 0;
let lastResult = null;
let retryRequest = null;

// This is a bounded command entry point, not a conversational interpreter.
// Keep simple settings local; send the whole content request to the model.
const commandStart = /^(?:(?:can|could|would) you\s+)?(?:please\s+)?(?:write|create|draft|generate|repurpose|turn|rewrite)\b/i;
const commandPrefix = /^(?:(?:can|could|would) you\s+)?(?:please\s+)?/i;
const asset = '(?:draft|result|content|source|transcript|article|notes|script|post|caption|newsletter|asset|one)s?';
const target = `(?:(?:only|just)\\s+)?(?:(?:the|my|this|that|these|those)\\s+)?(?:(?:current|existing|first|second|third|fourth|last|\\d+(?:st|nd|rd|th)?)\\s+)?(?:short\\s+)?(?:LinkedIn |Instagram |social )?${asset}`;
const targetedEdit = new RegExp(`^make\\s+${target}\\b`, 'i');
const lengthEdit = /^make\s+(?:it|this|that)\s+(?:shorter|longer|more concise)[.!?]?$/i;
controls.interpretText = (text, values) => {
  const intent = interpretPreferenceText(text, values);
  const command = String(text).trim().replace(commandPrefix, '');
  if (intent.action !== 'clarify' || (!commandStart.test(String(text).trim()) && !targetedEdit.test(command) && !lengthEdit.test(command))) return intent;
  return { action: 'generate', patch: {}, contentCommand: true };
};
controls.shadowRoot.querySelector('#instruction').placeholder = 'Repurpose this into a LinkedIn post, or dictate a complete brief';

function refersToCurrent(text) {
  const command = text.trim().replace(commandPrefix, '');
  // Only explicit source markers start a new source here. A colon or newline
  // introducing "Tone: warm" is still part of a follow-up on the current pack.
  const labelledSource = /\b(?:source(?: text| material)?|transcript|article|notes|original(?: text| draft)?)\s*:\s*\S/i;
  const inlineSource = /^(?:repurpose|turn|rewrite)\s+(?:this|the following)\s+(?:transcript|article|source|notes|paragraph|text)\b[^:\n.!?]*:\s*\S/i;
  if (labelledSource.test(command) || inlineSource.test(command) || /^rewrite\s*:\s*\S/i.test(command)) return false;
  // For transformations without a new source, keep available context even when
  // the target is ambiguous. The model resolves/asks about the actual assets.
  return /^(?:repurpose|rewrite)\b/i.test(command)
    || targetedEdit.test(command)
    || lengthEdit.test(command)
    || new RegExp(`^turn\\s+(?:it|this|that|${target})\\b`, 'i').test(command)
    || new RegExp(`\\b(?:from|using|based on)\\s+(?:it|this|that|${target})\\b`, 'i').test(command);
}

function mergeEditedAssets(previous, replacement) {
  if (!previous?.data || !replacement.data) return replacement;
  const oldAssets = new Map(previous.data.assets.map(asset => [asset.id, asset]));
  // A response containing replacements for existing formats is an edit. Keep
  // omitted siblings exactly as received earlier; a new format/ID is a new pack.
  if (!replacement.data.assets.every(asset => {
    const old = oldAssets.get(asset.id);
    return old && old.platform === asset.platform && old.format === asset.format;
  })) return replacement;
  const editedIds = new Set(replacement.data.assets.map(asset => asset.id));
  const untouched = previous.data.assets.filter(asset => !editedIds.has(asset.id));
  const retainedHookIds = new Set(untouched.map(asset => asset.hook_id));
  const hooks = new Map(previous.data.hooks.map(hook => [hook.id, hook]));
  const reservedHookIds = new Set([...hooks.keys(), ...replacement.data.hooks.map(hook => hook.id)]);
  const hookIds = new Map();
  for (const hook of replacement.data.hooks) {
    let id = hook.id;
    if (retainedHookIds.has(id) && hooks.get(id)?.text !== hook.text) {
      let suffix = 1;
      while (reservedHookIds.has(`${id}-edit-${suffix}`)) suffix++;
      id = `${id}-edit-${suffix}`;
      reservedHookIds.add(id);
    }
    hookIds.set(hook.id, id);
    hooks.set(id, id === hook.id ? hook : { ...hook, id });
  }
  const edits = new Map(replacement.data.assets.map(asset => [asset.id, hookIds.has(asset.hook_id)
    ? { ...asset, hook_id: hookIds.get(asset.hook_id) } : asset]));
  const unique = values => [...new Set(values)];
  const reviewNotes = unique([...(untouched.length ? previous.data.review_notes : []), ...replacement.data.review_notes]);
  if (untouched.length && previous.data.brief.tone !== replacement.data.brief.tone) {
    reviewNotes.push(`Writing direction for edited assets (${[...editedIds].join(', ')}): ${replacement.data.brief.tone}. Unchanged assets retain their earlier direction: ${previous.data.brief.tone}.`);
  }
  return { ...replacement,
    status: untouched.length && previous.status === 'partial' ? 'partial' : replacement.status,
    limitations: unique([...(untouched.length ? previous.limitations : []), ...replacement.limitations]),
    assumptions: unique([...(untouched.length ? previous.assumptions : []), ...replacement.assumptions]),
    data: {
      ...replacement.data,
      brief: { ...previous.data.brief, tone: replacement.data.brief.tone },
      hooks: [...hooks.values()], review_notes: reviewNotes,
      assets: previous.data.assets.map(asset => edits.get(asset.id) || asset),
    },
  };
}

function status(message, error = false) {
  request.hidden = false;
  info.textContent = message;
  info.dataset.error = String(error);
}
function busy(value) {
  controls.toggleAttribute('busy', value);
  request.setAttribute('aria-busy', String(value));
  cancel.hidden = !value;
  retry.hidden = value || !retryRequest;
}
function stale() {
  results.dataset.stale = 'true';
  results.querySelectorAll('[data-copy]').forEach(button => { button.disabled = true; });
  copyStatus.textContent = '';
}
function stop(message) {
  sequence++;
  active?.controller.abort();
  active = null;
  busy(false);
  if (message) status(message);
}
function changed(clearDraft = false) {
  retryRequest = null;
  const wasRunning = Boolean(active);
  stop();
  if (clearDraft) lastResult = null;
  stale();
  if (wasRunning || results.childElementCount) status('Choices changed. Generate content to update the result.');
}
controls.addEventListener('preferences-change', event => changed(event.detail.source === 'binding'));
topic.addEventListener('input', () => { controls.invalidateInput(); changed(true); });
new MutationObserver(records => {
  if (records.some(record => record.attributeName === 'scope-label')) changed(true);
}).observe(controls, { attributes: true, attributeFilter: ['scope-label'] });

async function generate({ action = 'generate', instruction, contentCommand = false } = {}) {
  stop();
  retryRequest = null;
  retry.hidden = true;
  if (contentCommand) {
    if (refersToCurrent(instruction)) {
      if (lastResult?.result.data) action = 'rewrite';
      else if (!topic.value.trim()) {
        status('Paste or dictate the source material first, then say what to turn it into.', true);
        return;
      }
    } else {
      // A new complete request owns its brief. Never inherit an unrelated topic
      // or old draft merely because the screen still displays it.
      topic.value = instruction;
      lastResult = null;
      action = 'generate';
    }
  }
  const brief = topic.value.trim();
  if (!brief) { status('Add a brief first.', true); return; }
  if (action === 'rewrite' && !lastResult?.result.data) {
    status('No generated draft to rewrite. Generate content first.', true);
    return;
  }
  const state = controls.preferences;
  const previousResult = action === 'rewrite' ? lastResult.result : null;
  const current = {
    token: ++sequence, controller: new AbortController(), store: controls.store,
    revision: state.revision, brief: topic.value, scope: controls.getAttribute('scope-label'),
  };
  active = current;
  stale();
  busy(true);
  status(action === 'rewrite' ? 'Rewriting… Local generation may take a few minutes.' : 'Generating… Local generation may take a few minutes.');
  const isCurrent = () => active === current && sequence === current.token && controls.isConnected
    && controls.store === current.store && controls.preferences.revision === current.revision
    && topic.value === current.brief && controls.getAttribute('scope-label') === current.scope;
  try {
    const body = { brief, action, preferenceContext: buildPreferenceContext(state) };
    if (instruction) body.instruction = instruction;
    if (previousResult) body.previousResult = previousResult;
    const response = await fetch('/api/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body), signal: current.controller.signal,
    });
    let payload;
    try { payload = await response.json(); }
    catch { throw new Error('Could not read the model response. Check the local server and try again.'); }
    if (!response.ok) throw new Error(typeof payload?.error === 'string' ? payload.error : 'Generation failed. Try again.');
    validateGenerationResponse(payload);
    if (!isCurrent()) return;
    const result = previousResult ? mergeEditedAssets(previousResult, payload.result) : payload.result;
    // A clarification does not erase the successful pack it asks about.
    if (result.data || !previousResult) lastResult = { result };
    renderContent(results, result, async text => {
      try { await navigator.clipboard.writeText(text); copyStatus.textContent = 'Copied.'; }
      catch { copyStatus.textContent = 'Clipboard unavailable. Select and copy the content above.'; }
    });
    results.dataset.stale = 'false';
    modelInfo.textContent = `${payload.model} · ${payload.provider}`;
    const retainedLimitations = result !== payload.result && result.limitations.some(note => !payload.result.limitations.includes(note));
    const completion = typeof payload.spoken_summary === 'string' && payload.spoken_summary.trim() ? payload.spoken_summary
      : result.status === 'needs_input' ? 'A little more detail is needed.'
      : result.status === 'partial' ? 'Draft ready. Check User guidance for limitations.' : 'Ready.';
    status(completion + (retainedLimitations ? ' Existing limitations still apply to unchanged content; check User guidance.' : ''));
  } catch (error) {
    if (!isCurrent()) return;
    retryRequest = { action, instruction };
    status(error.name === 'AbortError' ? 'Stopped waiting for this result.' : error.message || 'Could not connect to the local model server. Try again.', true);
  } finally {
    if (active === current) { active = null; busy(false); }
  }
}
controls.addEventListener('content-request', ({ detail }) => generate(detail));
cancel.addEventListener('click', () => {
  retryRequest = null;
  stop('Stopped waiting. The local model may finish its current run before another can start.');
});
retry.addEventListener('click', () => { if (retryRequest) generate(retryRequest); });
window.addEventListener('pagehide', () => stop());

try {
  const response = await fetch('/api/model');
  const configured = await response.json();
  if (!response.ok || typeof configured.model !== 'string' || typeof configured.provider !== 'string') throw new Error('Missing model settings');
  modelInfo.textContent = `Configured: ${configured.model} · ${configured.provider}`;
} catch {
  modelInfo.textContent = 'Local model server unavailable. Start it to generate content.';
}
