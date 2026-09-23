import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const node = (file, args) => new Function(...args, readFileSync(new URL(file, import.meta.url), 'utf8'));
const parse = node('./parse-request.js', ['$input', '$execution']);
const validate = node('./validate-request.js', ['$input', '$now']);
const plan = node('./plan-action.js', ['$', '$input']);
const respond = node('./return-agent-result.js', ['$', '$input']);
const now = '2026-09-23T22:00:00Z'; // Thursday 08:00 Brisbane.
const cfg = { timezone: 'Australia/Brisbane', data_source_id: 'a'.repeat(32), max_records: 500,
  properties: { title: 'Name', when: 'When', kind: 'Type', status: 'Status', blocks: 'Blocks time', notes: 'Notes', reference: 'Reference', colour: 'Colour' } };
const input = value => ({ first: () => ({ json: value }) });
function request(action, args = {}) {
  const parsed = parse(input({ chatInput: JSON.stringify({ request_id: 'read-check', session_id: 'test', revision: 1, action, arguments: args }) }), { id: 'test' })[0].json;
  if (parsed.agent_result) return parsed;
  return validate(input({ ...parsed, settings: cfg }), { toMillis: () => Date.parse(now) })[0].json;
}
const rich = text => [{ plain_text: text }];
function record(number, { title = 'Write brochure', status = 'Planned', kind = 'Task', reference = '', start = null, end = null, blocks = false, archived = false } = {}) {
  return { object: 'page', id: String(number).padStart(32, '0'), url: 'https://notion.so/example', parent: { data_source_id: cfg.data_source_id }, last_edited_time: now, archived,
    properties: { Name: { type: 'title', title: rich(title) }, When: { type: 'date', date: start ? { start, end } : null },
      Type: { type: 'select', select: { name: kind } }, Status: { type: 'select', select: { name: status } },
      'Blocks time': { type: 'checkbox', checkbox: blocks }, Notes: { type: 'rich_text', rich_text: rich('') },
      Reference: { type: 'rich_text', rich_text: rich(reference) }, Colour: { type: 'select', select: { name: 'Default' } } } };
}
function run(q, rows = []) {
  assert.ok(!q.agent_result, q.agent_result?.output);
  return plan(name => { assert.equal(name, 'Validate scheduling request'); return input(q); }, { all: () => rows.map(json => ({ json })) })[0].json;
}
const rows = [record(1, { reference: 'planner:launch:brochure' }), record(2, { title: 'Brochure review', status: 'In progress', reference: 'planner:other:review' }),
  record(3, { status: 'Done', reference: 'planner:launch:done' }), record(4, { status: 'Cancelled' }), record(5, { archived: true }), record(6, { kind: 'Event', start: '2026-09-24T09:00:00+10:00', end: '2026-09-24T10:00:00+10:00' })];
test('default list retains open tasks only and current identity', () => {
  const out = run(request('list_tasks'), rows);
  assert.equal(out.route, 0);
  assert.equal(out.result.mutated, false);
  assert.equal(out.result.items.length, 2);
  assert.ok(out.result.items.every(r => r.state_token.startsWith('state-v1:')));
});
test('name, project and status filters combine; completed tasks can be found', () => {
  const result = run(request('list_tasks', { query: 'WRITE  brochure', project_reference: 'launch', status: 'Done' }), rows).result;
  assert.equal(result.match_count, 1);
  assert.equal(result.items[0].status, 'Done');
  assert.equal(result.items[0].reference, 'planner:launch:done');
  assert.equal(result.selection_required, false);
});
test('ambiguous names remain separate and exact page filters never select another task', () => {
  const multiple = run(request('list_tasks', { query: 'brochure' }), rows).result;
  assert.equal(multiple.selection_required, true);
  assert.equal(multiple.items.length, 2);
  assert.equal(run(request('list_tasks', { page_id: rows[1].id }), rows).result.items[0].page_id, rows[1].id);
  assert.equal(run(request('list_tasks', { query: 'missing' }), rows).result.match_count, 0);
  assert.equal(run(request('list_tasks', { query: '.*' }), rows).result.match_count, 0);
});
test('invalid search inputs fail without scheduling or saving', () => {
  for (const args of [{ query: {} }, { query: ' ' }, { query: 'x'.repeat(201) }, { project_reference: '../other' }, { status: 'Urgent' }]) {
    assert.ok(request('list_tasks', args).agent_result);
  }
  assert.equal(request('create', { title: 'Task', kind: 'Task', query: 'x' }).agent_result.tool_result.status, 'invalid_request');
});
const busy = [record(10, { title: 'Meeting', kind: 'Event', start: '2026-09-24T10:00:00+10:00', end: '2026-09-24T11:00:00+10:00', blocks: true }),
  record(11, { title: 'Later meeting', kind: 'Event', start: '2026-09-24T13:00:00+10:00', end: '2026-09-24T14:00:00+10:00', blocks: true })];
const slot = { window_start: '2026-09-24T10:00:00+10:00', window_end: '2026-09-24T11:00:00+10:00', day_start: '09:00', day_end: '16:00', buffer_minutes: 15 };
test('busy slot returns two nonoverlapping same-day alternatives with original duration and buffers', () => {
  const out = run(request('check_slot', slot), busy);
  assert.equal(out.route, 0);
  assert.equal(out.result.status, 'UNAVAILABLE');
  assert.equal(out.result.mutated, false);
  assert.equal(out.result.alternatives.length, 2);
  assert.deepEqual(out.result.alternatives.map(s => s.start), ['2026-09-24T01:15:00.000Z', '2026-09-24T04:15:00.000Z']);
  assert.ok(out.result.alternatives.every(s => Date.parse(s.end) - Date.parse(s.start) === 3600000));
  assert.equal(out.result.refresh_before_booking, true);
});
test('free slot needs no alternative; all-day busy and excluded weekends produce no invented options', () => {
  assert.deepEqual(run(request('check_slot', { ...slot, window_start: '2026-09-24T15:00:00+10:00', window_end: '2026-09-24T16:00:00+10:00' }), busy).result.alternatives, []);
  const allDay = [record(12, { kind: 'Event', start: '2026-09-24T00:00:00+10:00', end: '2026-09-25T00:00:00+10:00', blocks: true })];
  assert.equal(run(request('check_slot', slot), allDay).result.alternatives.length, 0);
  const saturday = { ...slot, window_start: '2026-09-26T10:00:00+10:00', window_end: '2026-09-26T11:00:00+10:00' };
  const satBusy = [record(13, { kind: 'Event', start: saturday.window_start, end: saturday.window_end, blocks: true })];
  assert.equal(run(request('check_slot', saturday), satBusy).result.alternatives.length, 0);
  assert.equal(run(request('check_slot', { ...saturday, include_weekends: true }), satBusy).result.alternatives.length, 2);
});
test('cross-day requests do not invent a shorter alternative; find_slots retains requested count/duration', () => {
  const crossDay = run(request('check_slot', { ...slot, window_end: '2026-09-25T11:00:00+10:00' }), busy).result;
  assert.equal(crossDay.alternatives.length, 0);
  assert.match(crossDay.alternatives_note, /within one day/);
  const found = run(request('find_slots', { ...slot, window_end: '2026-09-24T16:00:00+10:00', duration_minutes: 30, max_slots: 3 }), busy).result;
  assert.equal(found.slots.length, 3);
  assert.ok(found.slots.every(s => Date.parse(s.end) - Date.parse(s.start) === 1800000));
});
test('create conflict remains a read-only conflict and stale edits still fail', () => {
  const conflict = run(request('create', { title: 'Conflicting meeting', kind: 'Event', start: slot.window_start, end: slot.window_end }), busy);
  assert.equal(conflict.route, 0);
  assert.equal(conflict.result.status, 'CONFLICT');
  const stale = run(request('update', { page_id: rows[0].id, title: 'New title', expected_state: 'state-v1:old' }), rows);
  assert.equal(stale.result.status, 'STALE_STATE');
  assert.equal(stale.route, 0);
});
test('alternatives never start before the current check time', () => {
  const q = request('check_slot', slot);
  q.checked_at = '2026-09-24T04:20:00Z';
  const result = run(q, busy).result;
  assert.equal(result.alternatives.length, 1);
  assert.equal(result.alternatives[0].start, '2026-09-24T04:30:00.000Z');
});
test('spoken result distinguishes available alternatives from a booking', () => {
  const q = request('check_slot', slot), result = run(q, busy).result;
  const out = respond(name => input(name === 'Validate scheduling request' ? q : { result }), input({}))[0].json;
  assert.equal(out.tool_result.status, 'conflict');
  assert.match(out.output, /2 alternative times/);
  assert.match(out.output, /Nothing has been booked/);
});
