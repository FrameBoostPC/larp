import { createPreferenceStore } from './state.mjs';
import { interpretPreferenceText, buildPreferenceContext } from './intent.mjs';
import { controlsTemplate } from './controls-template.mjs';

export class ContentPreferences extends HTMLElement {
  static get observedAttributes() { return ['scope-label', 'action-label', 'busy']; }
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._store = createPreferenceStore();
    this._unsubscribe = null;
    this.interpretText = interpretPreferenceText;
    this._speechAdapter = null;
    this._capture = null;
    this._captureToken = 0;
    this._inputToken = 0;
    this._pendingInput = null;
    this._voiceActive = false;
  }

  connectedCallback() {
    if (!this.shadowRoot.childElementCount) this.render();
    this.watchStore();
    this.sync();
    this.syncMicrophone();
  }

  disconnectedCallback() { this.cancelVoice(); this._inputToken++; this._pendingInput = null; this._unsubscribe?.(); this._unsubscribe = null; }
  attributeChangedCallback(name, previous, next) {
    if (name === 'action-label' || name === 'busy') { this.syncRequestAvailability(); return; }
    if (previous !== next) { this.cancelVoice(); this._inputToken++; this._pendingInput = null; this.sync(); }
  }

  get store() { return this._store; }
  set store(next) {
    if (!next || ['snapshot', 'apply', 'subscribe'].some(method => typeof next[method] !== 'function')) throw new TypeError('Use a preference store with snapshot, apply and subscribe.');
    if (next === this._store) return;
    this.cancelVoice(); this._inputToken++; this._pendingInput = null;
    this._unsubscribe?.(); this._unsubscribe = null;
    this._store = next;
    if (this.isConnected) this.watchStore();
    this.sync();
    this.message(`Current selection: ${this.describe()}.`);
    if (this.isConnected) this.dispatchEvent(new CustomEvent('preferences-change', { detail: { status: 'rebound', state: this.preferences, source: 'binding' }, bubbles: true, composed: true }));
  }

  watchStore() {
    if (this._unsubscribe) return;
    const watchedStore = this.store;
    this._unsubscribe = watchedStore.subscribe(change => {
      if (this.store !== watchedStore || !this.isConnected) return;
      this.sync();
      this.message(`Current selection: ${this.describe()}.`);
      this.dispatchEvent(new CustomEvent('preferences-change', { detail: { ...change, state: this.preferences }, bubbles: true, composed: true }));
    });
  }

  get preferences() { return this.store.snapshot(); }
  set speechAdapter(adapter) { this.cancelVoice(); this._speechAdapter = adapter; if (this.isConnected) this.syncMicrophone(); }
  get speechAdapter() { return this._speechAdapter; }

  setPreferences(patch, options = {}) {
    const result = this.store.apply(patch, options);
    if (result.status === 'conflict') {
      this.message(`A newer choice changed ${result.conflicts.join(', ')}. Repeat your instruction to use it now.`, true);
      return result;
    }
    this.sync();
    return result;
  }

  async submitInstruction(text, options = {}) {
    const source = options.source ?? 'text';
    if (source !== 'voice') this.cancelVoice();
    const original = this.preferences;
    const originalStore = this.store;
    const baseRevision = options.baseRevision ?? original.revision;
    const eventId = options.eventId ?? crypto.randomUUID();
    const token = ++this._inputToken;
    this._pendingInput = { token, source };
    this.syncRequestAvailability();
    this.message('Understanding your instruction…');
    try {
      const intent = await this.interpretText(text, original.values, { source, baseRevision, eventId });
      if (token !== this._inputToken || !this.isConnected || (options.captureToken !== undefined && options.captureToken !== this._captureToken)) return { status: 'superseded' };
      if (!intent || !['settings', 'generate', 'rewrite', 'clarify'].includes(intent.action)) throw new Error('The instruction could not be interpreted.');
      if (intent.action === 'clarify') { this.message(intent.message || 'Please clarify the writing voice.', true); return { status: 'clarify' }; }
      // A content action with no preference changes still belongs to the state
      // at capture time. Do not let delayed speech generate after a newer choice.
      if (intent.action !== 'settings' && Object.keys(intent.patch).length === 0 && this.preferences.revision !== baseRevision) {
        this.message('A newer choice changed this request. Repeat your instruction to use it now.', true);
        return { status: 'conflict' };
      }
      const result = this.setPreferences(intent.patch, { source, baseRevision, eventId });
      if (token !== this._inputToken || this.store !== originalStore || !this.isConnected) return { status: 'superseded' };
      if (['conflict', 'duplicate'].includes(result.status)) return result;
      this.message(Object.keys(intent.patch).length ? `Set to ${this.describe()}.` : (intent.message || `Current selection: ${this.describe()}.`));
      this._pendingInput = null;
      this.syncRequestAvailability();
      if (intent.action !== 'settings') this.requestContent(intent.action, { source, instruction: text, eventId, contentCommand: intent.contentCommand === true });
      return result;
    } catch (error) {
      if (token === this._inputToken) this.message(error.message || 'Could not apply that instruction. Try again.', true);
      return { status: 'error' };
    } finally {
      if (this._pendingInput?.token === token) { this._pendingInput = null; this.syncRequestAvailability(); }
    }
  }

  requestContent(action = 'generate', extra = {}) {
    if (!['generate', 'rewrite'].includes(action)) throw new Error('Unsupported content action.');
    if (this.hasAttribute('busy')) { this.message('Content is being generated. Cancel it or wait for the result.'); return false; }
    if (this._pendingInput || (this._voiceActive && extra.source !== 'voice')) {
      this.message('Finish the current instruction before preparing a request.');
      return false;
    }
    const state = this.preferences;
    if (state.values.tone === 'custom' && !state.values.customVoice.trim()) {
      this.shadowRoot.querySelector('details').open = true;
      this.shadowRoot.querySelector('#custom').focus();
      this.message('Describe your custom voice before preparing the request.', true);
      return false;
    }
    this.dispatchEvent(new CustomEvent('content-request', {
      detail: { ...extra, action, state, preferenceContext: buildPreferenceContext(state), scope: this.getAttribute('scope-label') || 'Current brief' }, bubbles: true, composed: true,
    }));
    this.message('Writing preferences prepared.');
    return true;
  }

  render() {
    this.shadowRoot.innerHTML = controlsTemplate;
    const root = this.shadowRoot;
    root.addEventListener('click', event => {
      const el = event.target;
      // A click on the already selected radio is still a deliberate reaffirmation.
      // Changed radios are handled once by their subsequent change event.
      if (el.type === 'radio' && this.preferences.values[el.name] === el.value) {
        this.setPreferences({ [el.name]: el.value }, { source: 'button' });
        this.message(`Set to ${this.describe()}.`);
      }
    });
    root.addEventListener('change', event => {
      const el = event.target;
      if (['tone', 'intensity', 'wording'].includes(el.name)) {
        this.setPreferences({ [el.name]: el.value }, { source: 'button' });
        this.message(`Set to ${this.describe()}.`);
        if (el.value === 'custom') { root.querySelector('details').open = true; root.querySelector('#custom').focus(); }
      }
    });
    root.querySelector('#custom').addEventListener('input', event => this.setPreferences({ customVoice: event.target.value }, { source: 'text' }));
    root.querySelector('#apply').addEventListener('click', () => this.submitInstruction(root.querySelector('#instruction').value));
    root.querySelector('#instruction').addEventListener('keydown', event => {
      if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); this.submitInstruction(event.target.value); }
    });
    root.querySelector('#prepare').addEventListener('click', () => this.requestContent());
    root.querySelector('.mic').addEventListener('click', () => this._capture ? this.finishVoice() : this.startVoice());
  }

  sync() {
    if (!this.shadowRoot.childElementCount) return;
    const root = this.shadowRoot, values = this.preferences.values;
    root.querySelectorAll('input[type=radio]').forEach(el => { el.checked = values[el.name] === el.value; });
    if (root.querySelector('#custom').value !== values.customVoice) root.querySelector('#custom').value = values.customVoice;
    root.querySelector('#scope').textContent = this.getAttribute('scope-label') || 'Current brief';
    root.querySelector('#current').textContent = this.describe();
    this.syncRequestAvailability();
  }
  syncRequestAvailability() {
    const button = this.shadowRoot.querySelector('#prepare');
    if (!button) return;
    button.disabled = Boolean(this._pendingInput || this._voiceActive || this.hasAttribute('busy'));
    button.textContent = this.getAttribute('action-label') || 'Prepare request';
  }

  // Hosts call this when the source brief changes outside the preference store.
  // Both unfinished transcription and model-backed interpretation lose their scope.
  invalidateInput() {
    this.cancelVoice();
    this._inputToken++;
    this._pendingInput = null;
    this.syncRequestAvailability();
  }
  describe() { const v = this.preferences.values; return [v.tone, v.intensity, v.wording].map(x => x[0].toUpperCase() + x.slice(1)).join(' · '); }
  message(text, error = false) { const el = this.shadowRoot.querySelector('.status'); if (el) { el.textContent = text; el.dataset.error = String(error); } }

  syncMicrophone() {
    const supported = Boolean(this._speechAdapter || window.SpeechRecognition || window.webkitSpeechRecognition);
    this.shadowRoot.querySelector('.mic').disabled = !supported;
    this.shadowRoot.querySelector('#mic-note').textContent = this._speechAdapter ? 'Connected speech service.' : supported ? 'Browser speech may be processed online.' : 'Mic unavailable. Type instead.';
  }

  startVoice() {
    this.cancelVoice();
    const baseRevision = this.preferences.revision, eventId = crypto.randomUUID(), token = ++this._captureToken;
    const adapter = this._speechAdapter || browserSpeechAdapter();
    if (!adapter) { this.syncMicrophone(); return; }
    let delivered = false, finished = false;
    const current = () => token === this._captureToken && this.isConnected && !finished;
    const finish = () => {
      if (!current()) return;
      finished = true;
      this._capture = null;
      this._voiceActive = false;
      this.syncRequestAvailability();
      const button = this.shadowRoot.querySelector('.mic'); button.setAttribute('aria-pressed', 'false'); button.querySelector('span').textContent = 'Use microphone';
    };
    try {
      this._voiceActive = true;
      this.syncRequestAvailability();
      this.message('Starting microphone…');
      const capture = adapter.start({
        onStart: () => { if (current()) { this.message('Listening…'); const b = this.shadowRoot.querySelector('.mic'); b.setAttribute('aria-pressed', 'true'); b.querySelector('span').textContent = 'Finish speaking'; } },
        onInterim: text => { if (current()) this.shadowRoot.querySelector('#instruction').value = text; },
        onFinal: text => { if (!current() || delivered) return; delivered = true; this.shadowRoot.querySelector('#instruction').value = text; this.submitInstruction(text, { source: 'voice', baseRevision, eventId, captureToken: token }); },
        onError: message => { if (current()) { delivered = true; this.message(message, true); finish(); } },
        onEnd: () => { if (current() && !delivered) this.message('No final speech was received. Try again or type your instruction.', true); finish(); },
      });
      if (!capture || typeof capture.stop !== 'function' || typeof capture.abort !== 'function') throw new Error('The speech adapter must provide stop and abort controls.');
      if (!finished) this._capture = capture;
    } catch (error) { this.message(error.message || 'Could not start the microphone.', true); finish(); }
  }
  finishVoice() {
    try { this._capture?.stop?.(); }
    catch { this.cancelVoice(); this.message('Could not finish speech input. Please type the instruction or try again.', true); }
  }
  cancelVoice() {
    this._captureToken++;
    if (this._pendingInput?.source === 'voice') { this._inputToken++; this._pendingInput = null; }
    try { this._capture?.abort?.(); }
    catch { this.message('The speech service reported a cancellation error. Late input will be ignored.', true); }
    finally {
      this._capture = null;
      this._voiceActive = false;
      this.syncRequestAvailability();
      const button = this.shadowRoot.querySelector('.mic');
      if (button) { button.setAttribute('aria-pressed', 'false'); button.querySelector('span').textContent = 'Use microphone'; }
    }
  }
}

export function browserSpeechAdapter() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) return null;
  return {
    start(callbacks) {
      const recognition = new Recognition();
      const finalParts = new Map();
      let failed = false;
      recognition.lang = document.documentElement.lang || 'en-AU';
      recognition.continuous = false; recognition.interimResults = true;
      recognition.onstart = callbacks.onStart;
      recognition.onresult = event => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const text = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalParts.set(i, text); else interim += text;
        }
        callbacks.onInterim([...finalParts.values(), interim].filter(Boolean).join(' '));
      };
      recognition.onerror = event => { failed = true; callbacks.onError(({ 'not-allowed': 'Microphone access was declined. You can continue by typing.', 'service-not-allowed': 'This browser’s speech service is unavailable. You can type instead.', 'network': 'Speech transcription could not connect. Try again or type instead.', 'no-speech': 'No speech was detected. Try again or type instead.', 'aborted': 'Voice input cancelled.' })[event.error] || 'Speech input failed. Try again or type instead.'); };
      recognition.onend = () => {
        if (!failed && finalParts.size) callbacks.onFinal([...finalParts.values()].join(' '));
        callbacks.onEnd();
      };
      recognition.start();
      return { stop: () => recognition.stop(), abort: () => recognition.abort() };
    },
  };
}

if (!customElements.get('content-preferences')) customElements.define('content-preferences', ContentPreferences);
