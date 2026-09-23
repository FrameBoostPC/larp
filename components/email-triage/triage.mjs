import {buildEmailReviewResult} from '../hermes-orchestration/email-review.mjs';
export const CATEGORIES = ['ACTION', 'MEETING', 'FINANCE', 'NEWSLETTER', 'NOTIFICATION', 'PERSONAL', 'OTHER', 'PROMOTION', 'SOCIAL', 'SALES', 'RECRUITMENT', 'RECEIPT'];
export const LABEL_NAMES = Object.fromEntries(CATEGORIES.map(c => [c, 'Automation/' + c[0] + c.slice(1).toLowerCase()]));

export function categoryPolicy(source, result) {
  if (!CATEGORIES.includes(result.category) || !['DRAFT', 'REVIEW', 'FILE'].includes(result.disposition)) throw new Error('Unexpected AI result');
  let status = result.disposition, reason = String(result.reason ?? '');
  if (source.force_review) { status = 'REVIEW'; reason = source.force_reason; }
  else if (!Number.isFinite(result.confidence) || result.confidence < 0.8 || result.confidence > 1) { status = 'REVIEW'; reason = 'Low or invalid confidence: ' + reason; }
  else if (result.disposition === 'REVIEW') status = 'REVIEW';
  else if (['OTHER', 'RECRUITMENT'].includes(result.category)) { status = 'REVIEW'; reason = 'Owner review required: ' + reason; }
  else if (result.category === 'FINANCE' && result.disposition === 'DRAFT') { status = 'REVIEW'; reason = 'Financial response needs owner review: ' + reason; }
  else if (source.automated || ['NEWSLETTER', 'NOTIFICATION', 'PROMOTION', 'SOCIAL', 'RECEIPT'].includes(result.category)) status = 'FILE';
  return {status, reason, draft: status === 'DRAFT' ? String(result.draft_body ?? '').trim() : ''};
}

export function prepareLabels(source, config) {
  if (!source.message_id || !['REVIEW','FILE','DRAFT_CREATED'].includes(source.status) || (source.status === 'DRAFT_CREATED' && !String(source.draft_id ?? '').trim())) throw new Error('Confirmed email review is required before labelling');
  const base = ['processed', 'draftReady', 'manualReview', 'clash'];
  const all = [...base.map(k => config?.[k]), ...CATEGORIES.map(k => config?.categories?.[k])];
  if (all.some(id => typeof id !== 'string' || !id.trim()) || new Set(all).size !== all.length) throw new Error('Verified distinct email label IDs are required');
  const category = CATEGORIES.includes(source.category) ? source.category : 'OTHER';
  const labels = [[config.processed, 'Automation/Processed'], [config.categories[category], LABEL_NAMES[category]]];
  if (source.status === 'DRAFT_CREATED') labels.push([config.draftReady, 'Automation/Draft Ready']);
  if (source.status === 'REVIEW') labels.push([config.manualReview, 'Automation/Manual Review']);
  if (source.time_clash === true) labels.push([config.clash, 'clash']);
  return {...source, category, time_clash: source.time_clash === true, label_ids: labels.map(x => x[0]), label_names: labels.map(x => x[1])};
}

export function envelope(meta, status, spoken, data = null) {
  return {output: spoken, tool_result: {schema_version: '1.0', request_id: meta?.request_id ?? null, session_id: meta?.session_id ?? null, revision: meta?.revision ?? null, status, spoken_summary: spoken, data}};
}

export function parseReviewRequest(input) {
  let v; try { v = JSON.parse(input.chatInput); } catch {}
  const obj = x => x && typeof x === 'object' && !Array.isArray(x);
  const fail = (status, spoken) => ({origin:'agent', agent:v, agent_result:envelope(v,status,spoken)});
  if (!obj(v) || Object.keys(v).some(k => !['request_id','session_id','revision','action','arguments'].includes(k)) || typeof v.request_id !== 'string' || !/^[a-z0-9][a-z0-9_.-]{1,59}$/.test(v.request_id) || typeof v.session_id !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,119}$/.test(v.session_id) || !Number.isSafeInteger(v.revision) || v.revision < 0 || !obj(v.arguments) || JSON.stringify(v).length > 28000) return fail('invalid_request','The agent request needs valid tracking information and arguments.');
  if (!['list_reviews','get_review'].includes(v.action)) return fail('invalid_request','That action is not supported by this workflow.');
  const a = {...v.arguments};
  const allowed = v.action === 'list_reviews' ? ['limit','category','status','sender','subject_contains'] : ['message_id','limit'];
  if (Object.keys(a).some(k => !allowed.includes(k))) return fail('invalid_request','The request contains unsupported arguments.');
  if (v.action === 'get_review' && (typeof a.message_id !== 'string' || !a.message_id.trim() || a.message_id.length > 160)) return fail('needs_input','Which email review do you mean?');
  if (a.limit !== undefined && (!Number.isInteger(a.limit) || a.limit < 1 || a.limit > 50)) return fail('invalid_request','Review limit must be between one and fifty.');
  if (a.category !== undefined && !CATEGORIES.includes(a.category)) return fail('invalid_request','Choose a supported email category.');
  if (a.status !== undefined && !['REVIEW','FILE','DRAFT_CREATED'].includes(a.status)) return fail('invalid_request','Choose REVIEW, FILE or DRAFT_CREATED.');
  if (a.sender !== undefined) {
    if (typeof a.sender !== 'string' || a.sender.length > 254 || !/^[^<>\s,@]+@[^<>\s,@]+\.[^<>\s,@]+$/.test(a.sender.trim())) return fail('invalid_request','Use the sender’s email address from known correspondence.');
    a.sender = a.sender.trim().toLowerCase();
  }
  if (a.subject_contains !== undefined) {
    if (typeof a.subject_contains !== 'string' || !a.subject_contains.trim() || a.subject_contains.length > 200 || /[\u0000-\u001f]/.test(a.subject_contains)) return fail('invalid_request','Use a short subject phrase.');
    a.subject_contains = a.subject_contains.trim();
  }
  return {origin:'agent', agent:v, operation:v.action, raw:a};
}

export function returnReviews(q, rows, retrievedAt = new Date().toISOString()) {
  return buildEmailReviewResult(q, rows, retrievedAt);
}
