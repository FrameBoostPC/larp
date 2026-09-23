import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

// Exercise the exact Code-node source, including its existing deadline validator.
const execute = new Function('$', '$json', readFileSync(new URL('./n8n-format-result.js', import.meta.url), 'utf8'));
function format({ deadline = null, constraints = '', existing = null, style = 'Broad timeline', replay = null } = {}) {
  const source = {
    record_key: 'test', workflow: 'planner', raw_input: '{}', availability: null,
    brief: { reference: 'test', project_reference: 'test-project', week_start: '2026-09-28', week_end: '2026-10-11', timezone: 'Australia/Brisbane', horizon_weeks: 2, planning_style: style, mode: 'Draft only', goal: 'Prepare a checklist', backlog: 'Write the checklist', constraints, hours_available: null, work_days: ['Monday'] },
    project_context: { items: existing ? [existing] : [], busy: [], checked_at: '2026-09-23T00:00:00Z' },
  };
  const output = { summary: 'Prepare a checklist.', next_action: 'Write the checklist.', assumptions: [], tasks: [{ task_key: 'checklist', existing_reference: existing?.reference ?? null, task: 'Write the checklist', target_week: 1, day: style === 'Broad timeline' ? null : 'Monday', hours: style === 'Broad timeline' ? null : 1, depends_on: [], done_when: 'Checklist is ready', due_date: deadline }] };
  const result = execute(name => { assert.equal(name, 'Combine context with brief'); return { first: () => ({ json: source }) }; }, { output, ...(replay ? { replay_result: replay } : {}) });
  return { ...result.json, result: JSON.parse(result.json.result_json) };
}

test('broad target weeks stay proposals and never become implicit deadlines', () => {
  const row = format();
  assert.equal(row.result.plan.tasks[0].due_date, null);
  assert.equal(row.result.plan.tasks[0].target_week_end, '2026-10-04');
  assert.equal(row.result.plan.tasks[0].hours, null);
  assert.equal(row.should_sync, false);
  assert.doesNotMatch(row.summary, /Explicit deadline:/);
});
test('explicit deadlines remain accepted in both planning styles', () => {
  for (const style of ['Broad timeline', 'Detailed time planning']) {
    assert.equal(format({ style, deadline: '2026-10-02', constraints: 'Finish by 2026-10-02.' }).result.plan.tasks[0].due_date, '2026-10-02');
  }
});
test('dates appearing only in the planning horizon cannot become deadlines', () => {
  assert.throws(() => format({ deadline: '2026-10-11' }), /A due date must be/);
  assert.throws(() => format({ deadline: '2026-09-28' }), /A due date must be/);
});
test('existing task deadlines and replay identity are preserved', () => {
  const existing = { reference: 'planner:test-project:checklist', title: 'Write the checklist', status: 'Planned', due_date: '2026-10-06' };
  assert.equal(format({ existing, deadline: existing.due_date }).result.plan.tasks[0].due_date, existing.due_date);
  const saved = format({ deadline: '2026-10-02', constraints: 'Due 2026-10-02.' }).result;
  assert.equal(format({ deadline: '2026-10-02', replay: saved }).result.plan.tasks[0].due_date, '2026-10-02');
});
test('invalid dates and reopening completed work still fail', () => {
  assert.throws(() => format({ deadline: '2026-02-30', constraints: 'Due 2026-02-30.' }), /A due date must be/);
  assert.throws(() => format({ existing: { reference: 'planner:test-project:checklist', title: 'Write the checklist', status: 'Done' } }), /Completed or cancelled/);
});
