export const LIMITS = { incoming: 40, spam: 20, sent: 30, drafts: 30, work: 100, reviews: 100, organisation: 100 };
const clean = (v, n = 1200) => String(v ?? '').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '').slice(0, n);
const parse = v => { try { return typeof v === 'string' ? JSON.parse(v) : v; } catch { return null; } };
const unique = items => { const seen = new Set(); return items.filter(x => { if (seen.has(x.reference)) return false; seen.add(x.reference); return true; }); };
const dateMs = v => Number.isFinite(Date.parse(v)) ? Date.parse(v) : 0;
export const localDate = (v, timezone = 'Australia/Brisbane') => new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(v));
function midnight(day, timezone) {
  const target = Date.parse(day + 'T00:00:00Z');
  let value = target;
  const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' });
  for (let i = 0; i < 4; i++) {
    const p = Object.fromEntries(formatter.formatToParts(new Date(value)).map(x => [x.type, x.value]));
    const displayed = Date.parse(p.year + '-' + p.month + '-' + p.day + 'T' + p.hour + ':' + p.minute + ':' + p.second + 'Z');
    value += target - displayed;
  }
  return new Date(value).toISOString();
}
const recent = (v, ctx) => dateMs(v) >= dateMs(ctx.since) && dateMs(v) <= dateMs(ctx.snapshot_at);
const envelope = (q, status, spoken, data = null) => ({ output: spoken, tool_result: { schema_version: '1.0', request_id: q?.request_id ?? null, session_id: q?.session_id ?? null, revision: q?.revision ?? null, status, spoken_summary: spoken, data } });

export function parseRequest(input) {
  const q = parse(input.chatInput);
  const object = v => v && typeof v === 'object' && !Array.isArray(v);
  if (!object(q) || Object.keys(q).some(k => !['request_id', 'session_id', 'revision', 'action', 'arguments'].includes(k)) ||
      typeof q.request_id !== 'string' || typeof q.session_id !== 'string' || !/^[a-z0-9][a-z0-9_.-]{1,59}$/.test(q.request_id) || !/^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,119}$/.test(q.session_id) ||
      !Number.isSafeInteger(q.revision) || q.revision < 0 || !object(q.arguments) || JSON.stringify(q).length > 20000 ||
      !['get_priorities', 'get_daily_review', 'get_setup'].includes(q.action) || Object.keys(q.arguments).length !== 0) {
    return { origin: 'agent', agent_result: envelope(q, 'invalid_request', 'The saved review request needs valid tracking information and empty arguments; it does not rescan sources.') };
  }
  return { origin: 'agent', agent: q };
}

export function checkSetup(input) {
  if (input.agent_result) return input;
  const c = input.review_config;
  const fail = message => ({ ...input, agent_result: envelope(input.agent, 'setup_required', message,
    { setup_required: true, live_sources_checked: false }) });
  if (!c || c.schema_version !== 1 || !['setup_required', 'preview', 'active', 'paused'].includes(c.mode)) return fail('Daily Review needs setup in Hermes.');
  if (input.agent?.action === 'get_setup') return { ...input, agent_result: envelope(input.agent, 'completed',
    c.mode === 'setup_required' ? 'Daily Review is ready to set up whenever you choose.' : 'These are the saved Daily Review settings.',
    { configuration: c, live_sources_checked: false }) };
  if (c.mode === 'setup_required') return fail('Set up Daily Review in Hermes by selecting sources, storage and a daily time. You can do this later.');
  if (!/^[a-zA-Z0-9_.-]{1,100}$/.test(c.configuration_id) || !/^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(c.time)) return fail('Daily Review needs valid saved settings.');
  try { new Intl.DateTimeFormat('en', { timeZone: c.timezone }).format(); } catch { return fail('Daily Review needs a valid timezone.'); }
  if (!c.timezone || !c.sources || !['email','workbench','calendar','reviews','organisation'].every(k => typeof c.sources[k] === 'boolean') ||
      !['email','workbench','calendar'].some(k => c.sources[k]) || !c.sources.email && (c.sources.reviews || c.sources.organisation)) return fail('Select the sources to include in Daily Review.');
  if (input.origin !== 'agent' && (c.mode === 'paused' || c.mode !== 'active' && !input.manual)) return {
    ...input, agent_result: envelope(null, 'paused', 'Daily collection is paused.', { live_sources_checked: false }) };
  return { ...input, configuration_id: c.configuration_id, sources: c.sources, source_labels: c.labels ?? {}, timezone: c.timezone };
}

export function reviewWindow(input, previous, now) {
  const ms = dateMs(now), timezone = input.timezone || 'Australia/Brisbane';
  if (!ms) throw new Error('Invalid review clock');
  const saved = parse(previous?.result_json)?.snapshot;
  const checkpoint = previous?.status === 'DONE' && saved?.schema_version === '3.0' && saved?.collection_status === 'complete' && saved.configuration_id === input.configuration_id ? saved.snapshot_at : null;
  let since = checkpoint || new Date(ms - 86400000).toISOString();
  if (dateMs(since) > ms || !dateMs(since)) throw new Error('Previous snapshot must be a valid past timestamp');
  const gap = dateMs(since) < ms - 7 * 86400000;
  if (gap) since = new Date(ms - 7 * 86400000).toISOString();
  const day = localDate(now, timezone);
  const nextDay = new Date(Date.parse(day + 'T00:00:00Z') + 86400000).toISOString().slice(0, 10);
  return { ...input, since, snapshot_at: now, date: day, timezone, window_limited: gap, checkpoint_unavailable: Boolean(previous?.error),
    since_basis: checkpoint ? 'previous_complete_snapshot' : 'last_24_hours',
    day_start: midnight(day, timezone), day_end: midnight(nextDay, timezone),
    query_after: Math.floor(dateMs(since) / 1000), query_before: Math.ceil(ms / 1000) };
}

function mail(raw, kind) {
  const m = raw.message && typeof raw.message === 'object' ? { ...raw.message, ...raw } : raw;
  const header = name => { const h = m.headers ?? m.payload?.headers ?? {}; return Array.isArray(h) ? h.find(x => String(x.name).toLowerCase() === name)?.value : h[name]; };
  const id = clean(m.id || m.messageId, 180);
  const text = clean(m.text ?? m.textPlain ?? m.snippet ?? '', 1800);
  const title = clean(m.subject ?? m.Subject ?? header('subject') ?? '(no subject)', 250);
  const labels = (m.labelIds ?? m.labels ?? []).map(x => typeof x === 'string' ? x : x.id);
  return { reference: kind + ':' + id, id, kind, title, text, evidence_text: text,
    from: clean((typeof m.from === 'string' ? m.from : m.from?.text) ?? m.From ?? header('from'), 300), to: clean((typeof m.to === 'string' ? m.to : m.to?.text) ?? m.To ?? header('to'), 300),
    received_at: clean(m.date ?? (m.internalDate ? new Date(Number(m.internalDate)).toISOString() : ''), 40),
    thread_id: clean(m.threadId, 180), label_ids: labels, body_limited: String(m.text ?? m.textPlain ?? m.snippet ?? '').length > 1800,
    url: kind === 'draft' ? 'https://mail.google.com/mail/u/0/#drafts' : 'https://mail.google.com/mail/u/0/#all/' + encodeURIComponent(m.threadId || id) };
}

export function collectSnapshot(ctx, sources) {
  const coverage = {}, warnings = [];
  const read = (key, identity) => {
    const group = ['incoming', 'spam', 'sent', 'drafts'].includes(key) ? 'email' : key === 'work' ? 'workbench' : key;
    if (ctx.sources && ctx.sources[group] === false) {
      coverage[key] = { enabled: false, checked: false, count: 0, skip_reason: 'not_selected' };
      return [];
    }
    const supplied = sources[key];
    const rows = Array.isArray(supplied) ? supplied : [];
    const failed = !Array.isArray(supplied) || rows.some(x => x?.error);
    const valid = rows.filter(x => x && identity(x));
    const capped = valid.length >= LIMITS[key];
    coverage[key] = { checked: !failed, count: valid.length, limit: LIMITS[key], may_be_truncated: capped };
    if (failed) warnings.push(key + ' could not be checked.');
    if (capped) warnings.push(key + ' reached its collection limit.');
    return valid;
  };
  const emails = read('incoming', x => x.id).map(x => mail(x, 'email'));
  const spam = read('spam', x => x.id).map(x => mail(x, 'spam'));
  const sent = read('sent', x => x.id).map(x => mail(x, 'sent'));
  const drafts = read('drafts', x => x.id).map(x => mail(x, 'draft')).filter(x => !/^\[Agency\] Daily priorities|^\[Daily Review\]/i.test(x.title));
  const reviews = read('reviews', x => x.message_id);
  const byMessage = new Map(reviews.map(x => [x.message_id, x]));
  for (const e of emails) { const r = byMessage.get(e.id); e.priority = r?.priority ?? (e.label_ids.includes('IMPORTANT') ? 'high' : 'normal'); e.review_status = r?.status ?? 'not_reviewed'; e.summary = clean(r?.summary || e.text); }
  const excluded = ['digest', 'scheduling', 'prospecting_control', 'email_organisation', 'daily_review'];
  const work = read('work', x => x.record_key).filter(x => !excluded.includes(x.workflow) && !/^voice:|:demo-|:pilot-|:test-/i.test(x.record_key) && !['content', 'repurposing', 'onboarding'].includes(x.workflow)).map(x => {
    const result = parse(x.result_json), status = String(x.status || '').toUpperCase();
    const state = ['DONE', 'READY', 'COMPLETED', 'PARTIAL', 'NO_MATCHES'].includes(status) ? 'completed' : ['RECEIVED', 'RESEARCHING', 'RUNNING', 'IN_PROGRESS', 'STARTED'].includes(status) ? 'ongoing' : ['ERROR', 'FAILED', 'NEEDS_REVIEW', 'BLOCKED', 'CANCELLED'].includes(status) ? 'needs_you' : 'queued';
    const urls = [result?.url, result?.result_url, result?.document_url].filter(v => typeof v === 'string' && /^https:\/\//.test(v));
    return { reference: 'work:' + x.record_key, record_key: x.record_key, kind: 'work', title: clean(x.title, 250), workflow: x.workflow, status, state, summary: clean(x.summary), evidence_text: clean(x.summary), next_action: clean(x.next_action, 500), updated_at: x.updatedAt, due_date: clean(x.due_at, 40), draft_id: clean(x.draft_id, 180), urls, recorded_status_only: true };
  });
  const receipts = read('organisation', x => x.record_key).filter(x => recent(x.updatedAt, ctx)).map(x => parse(x.result_json)).filter(x => x?.confirmed === true && typeof x.message_id === 'string' && ['labels_added', 'moved_to_label'].includes(x.action));
  const organisation = Object.values(receipts.reduce((out, r) => {
    const key = r.action + ':' + (r.label_names ?? r.label_ids ?? []).join(',');
    out[key] ??= { action: r.action, labels: r.label_names ?? r.label_ids ?? [], message_ids: [] };
    if (!out[key].message_ids.includes(r.message_id)) out[key].message_ids.push(r.message_id);
    return out;
  }, {})).map(x => ({ ...x, count: x.message_ids.length }));
  const cal = Array.isArray(sources.calendar) ? sources.calendar[0] : sources.calendar;
  const calOK = cal?.status === 'OK' && cal?.action === 'daily_review_context' && cal?.mutated === false && Array.isArray(cal.items) && Array.isArray(cal.tasks);
  const calendarEnabled = ctx.sources?.calendar !== false;
  coverage.calendar = { enabled: calendarEnabled, checked: calendarEnabled && calOK, scope: ctx.source_labels?.calendar ?? 'Selected Notion schedule', external_calendars_checked: false, ...(!calendarEnabled ? {skip_reason:'not_selected'} : {}) };
  if (calendarEnabled && !calOK) warnings.push('The connected Notion schedule could not be checked.');
  const notion = r => ({ ...r, reference: 'calendar:' + r.page_id, source_reference: r.reference, kind: 'calendar', evidence_text: clean(r.notes), title: clean(r.title, 250) });
  const schedule = calendarEnabled && calOK ? cal.items.map(notion) : [];
  const tasks = calendarEnabled && calOK ? cal.tasks.map(notion) : [];
  const conflicts = [];
  const busy = schedule.filter(x => x.blocks_time && x.start && x.end && !['Done', 'Cancelled'].includes(x.status));
  for (let i = 0; i < busy.length; i++) for (let j = i + 1; j < busy.length; j++) if (dateMs(busy[i].start) < dateMs(busy[j].end) && dateMs(busy[j].start) < dateMs(busy[i].end)) conflicts.push({ references: [busy[i].reference, busy[j].reference], titles: [busy[i].title, busy[j].title] });
  if (ctx.window_limited) warnings.push('The previous review is more than seven days ago; earlier changes are outside this review.');
  if (ctx.checkpoint_unavailable) warnings.push('The previous scheduled review could not be checked; the default review window was used.');
  const completed = work.filter(x => x.state === 'completed' && recent(x.updated_at, ctx));
  const ongoing = work.filter(x => x.state === 'ongoing');
  const queued = work.filter(x => x.state === 'queued');
  const needs = work.filter(x => x.state === 'needs_you');
  const reviewWork = [...completed, ...ongoing, ...queued, ...needs];
  const references = unique([...emails, ...spam, ...sent, ...drafts, ...reviewWork, ...schedule, ...tasks]);
  if (references.some(x => x.body_limited)) warnings.push('Email bodies are bounded excerpts; retrieve originals for full context.');
  return { ...ctx, coverage, warnings, inbox: emails, spam, sent, drafts, organisation, workbench: { completed, ongoing, queued, needs_you: needs }, schedule, tasks, conflicts,
    references: references.map(({reference, id, page_id, record_key, kind, title, url, urls, state_token}) => ({reference, id, page_id, record_key, kind, title, url, urls, state_token})) };
}

export function snapshotRecord(collected, executionId, completedAt = new Date().toISOString()) {
  if (!/^[a-zA-Z0-9_.-]{1,100}$/.test(String(executionId))) throw new Error('A stable execution ID is required');
  if (!dateMs(completedAt) || dateMs(completedAt) < dateMs(collected.snapshot_at)) throw new Error('Invalid collection completion time');
  const { origin, agent, review_config, manual, ...data } = collected;
  const incomplete = data.window_limited || data.checkpoint_unavailable || Object.values(data.coverage).some(c => c.enabled !== false && (!c.checked || c.may_be_truncated));
  const snapshot = { ...data, schema_version: '3.0', snapshot_id: 'daily-review:' + executionId, collection_completed_at: completedAt,
    collection_status: incomplete ? 'partial' : 'complete', preparation_only: true, presentation_owner: 'hermes' };
  return { record_key: snapshot.snapshot_id, workflow: 'daily_review', status: incomplete ? 'PARTIAL' : 'DONE',
    title: 'Daily review sources — ' + data.date, summary: 'Source snapshot prepared for Hermes (' + snapshot.collection_status + ').',
    result_json: JSON.stringify({ snapshot }), due_at: data.snapshot_at, next_action: '', contact_email: '', raw_input: data.configuration_id ?? '', draft_id: '' };
}

export function retrieveSnapshot(request, row, now = new Date().toISOString()) {
  const q = request.agent;
  if (request.agent_result) return request.agent_result;
  if (row?.error) return envelope(q, 'failed', 'The saved daily review could not be retrieved.', { source_mode: 'saved_snapshot', live_sources_checked: false });
  if (!row?.record_key) return envelope(q, 'not_found', 'No daily review snapshot has been prepared yet.', { source_mode: 'saved_snapshot', live_sources_checked: false });
  const snapshot = parse(row.result_json)?.snapshot;
  if (request.configuration_id && snapshot?.configuration_id !== request.configuration_id) return envelope(q, 'not_found',
    'Prepare a new review for the selected accounts and resources; the old snapshot belongs to different settings.', { source_mode: 'saved_snapshot', live_sources_checked: false });
  if (row.workflow !== 'daily_review' || snapshot?.schema_version !== '3.0' || !dateMs(snapshot.snapshot_at) ||
      !['complete', 'partial'].includes(snapshot.collection_status) || !snapshot.coverage || !Array.isArray(snapshot.warnings) ||
      !Array.isArray(snapshot.inbox) || !snapshot.workbench || !Array.isArray(snapshot.schedule)) {
    return envelope(q, 'failed', 'The saved daily review is invalid; it needs a new preparation run.', { source_mode: 'saved_snapshot', live_sources_checked: false });
  }
  const age = dateMs(now) - dateMs(snapshot.snapshot_at);
  if (!dateMs(now) || age < 0) return envelope(q, 'failed', 'The saved daily review has an invalid timestamp.');
  const stale = localDate(now, snapshot.timezone) !== snapshot.date || age >= 86400000;
  const partial = snapshot.collection_status === 'partial';
  const state = stale ? 'stale' : partial ? 'partial' : 'ready';
  const message = stale ? 'The latest saved daily review is from ' + snapshot.date + '; today’s snapshot is not ready.' :
    partial ? 'The saved daily review is ready with incomplete source coverage.' : 'The saved daily review is ready for Hermes.';
  return envelope(q, stale || partial ? 'partial' : 'completed', message, { source_mode: 'saved_snapshot', live_sources_checked: false, retrieval_state: state,
    retrieved_at: now, age_seconds: Math.floor(age / 1000), stale, snapshot });
}
