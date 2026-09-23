import assert from 'node:assert/strict';
import test from 'node:test';
import { buildEmailReviewResult, emailReviewNodeCode } from './email-review.mjs';

const now = '2026-09-23T03:00:00Z';
const query = { agent: { request_id: 'review-1', session_id: 'session-1', revision: 2 }, operation: 'list_reviews', raw: { limit: 1 } };
const row = { message_id: 'message-1', thread_id: 'thread-1', draft_id: 'draft-1', category: 'MEETING', status: 'DRAFT_CREATED', processed_at: '2026-09-22T03:00:00Z', time_clash: true };
test('preserves source identity, tracking and historical context for follow-ups', () => {
  const { tool_result: result } = buildEmailReviewResult(query, [row], now);
  assert.equal(result.revision, 2);
  assert.equal(result.data.live_inbox_checked, false);
  assert.equal(result.data.may_have_more, true);
  assert.deepEqual(result.data.counts, { categories: { MEETING: 1 }, statuses: { DRAFT_CREATED: 1 } });
  assert.equal(result.data.counts_scope, 'returned_items');
  const item = result.data.items[0];
  assert.deepEqual(item.source_refs, { provider: 'gmail', message_id: 'message-1', thread_id: 'thread-1', draft_id: 'draft-1' });
  assert.equal(item.review_age_seconds, 86400);
  assert.equal(item.source_refresh_required, true);
  assert.equal(item.calendar_refresh_required, true);
  assert.equal(item.historical, true);
  assert.deepEqual(item.tags, ['clash']);
});
test('preserves concurrently added category filters and counts without prototype keys', () => {
  const filtered = { ...query, raw: { category: 'MEETING', status: 'DRAFT_CREATED' } };
  const result = buildEmailReviewResult(filtered, [row], now);
  assert.match(result.output, /saved meeting email review/);
  assert.deepEqual(result.tool_result.data.filters, {...filtered.raw, sender:null, subject_contains:null});
  const weird = buildEmailReviewResult(query, [{ ...row, category: '__proto__' }], now);
  assert.equal(weird.tool_result.data.counts.categories.__proto__, 1);
  assert.equal(Object.getPrototypeOf(weird.tool_result.data.counts.categories), Object.prototype);
});
test('legacy rows do not acquire guessed thread, draft or timestamps', () => {
  const item = buildEmailReviewResult(query, [{ message_id: 'old', processed_at: 'bad' }], now).tool_result.data.items[0];
  assert.equal(item.thread_id, null);
  assert.equal(item.draft_id, null);
  assert.equal(item.review_age_seconds, null);
  assert.equal(item.source_refresh_required, true);
});
test('empty result is distinct from source failure and corrupt rows', () => {
  for (const rows of [[], [{}]]) assert.equal(buildEmailReviewResult(query, rows, now).tool_result.status, 'completed');
  for (const rows of [[{ error: 'unavailable' }], [{ subject: 'missing identity' }], [null]])
    assert.equal(buildEmailReviewResult(query, rows, now).tool_result.status, 'failed');
});
test('duplicate and mismatched identities block ambiguous follow-ups', () => {
  assert.equal(buildEmailReviewResult(query, [row, row], now).tool_result.status, 'conflict');
  const get = { ...query, operation: 'get_review', raw: { message_id: 'other' } };
  assert.equal(buildEmailReviewResult(get, [row], now).tool_result.status, 'conflict');
  assert.equal(buildEmailReviewResult(get, [{}], now).tool_result.status, 'not_found');
});
test('get_review has no misleading pagination; future timestamp is unknown', () => {
  const get = { ...query, operation: 'get_review', raw: { message_id: row.message_id, limit: 1 } };
  const result = buildEmailReviewResult(get, [{ ...row, processed_at: '2099-01-01' }], now).tool_result;
  assert.equal(result.data.may_have_more, false);
  assert.equal(result.data.items[0].review_age_seconds, null);
});
test('validation response passes through and deployed node wrapper matches module', () => {
  const invalid = { tool_result: { status: 'invalid_request' } };
  assert.equal(buildEmailReviewResult({ agent_result: invalid }, null, now), invalid);
  const run = new Function('$', '$input', '$now', emailReviewNodeCode());
  const result = run(() => ({ first: () => ({ json: query }) }), { all: () => [{ json: row }] }, { toISO: () => now });
  assert.deepEqual(result, [{ json: buildEmailReviewResult(query, [row], now) }]);
});
