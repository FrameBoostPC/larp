function recommendTimeBlocks(tasks, availability, currentTasks) {
  if (availability === null) return null;
  const fail = message => { throw new Error('Time recommendations: ' + message); };
  if (!availability || availability.scope !== 'selected_notion_database' || !Array.isArray(availability.weeks) || !Array.isArray(availability.busy_intervals) || !Array.isArray(tasks) || !Array.isArray(currentTasks)) fail('validated calendar availability and tasks are required');
  const minute = 60000, quarter = 15 * minute, day = 86400000;
  const iso = n => new Date(n).toISOString();
  const horizonStart = Date.parse(availability.horizon_start), horizonEnd = Date.parse(availability.horizon_end), now = Date.parse(availability.evaluated_at);
  if (![horizonStart, horizonEnd, now].every(Number.isFinite) || horizonEnd <= horizonStart) fail('invalid planning horizon');
  const normalId = value => String(value ?? '').replace(/-/g, '').toLowerCase();
  const dateEnd = date => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date ?? '')) fail('invalid due date');
    const ms = Date.parse(date + 'T00:00:00+10:00');
    if (!Number.isFinite(ms) || iso(ms + 10 * 3600000).slice(0, 10) !== date) fail('invalid due date');
    return ms + day;
  };
  const weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const byReference = new Map(), byKey = new Map(), currentByReference = new Map();
  for (const current of currentTasks) {
    if (!current.reference) continue;
    if (currentByReference.has(current.reference)) fail('duplicate current task reference');
    currentByReference.set(current.reference, current);
  }
  for (const task of tasks) {
    if (!task.reference || !task.task_key || byReference.has(task.reference) || byKey.has(task.task_key)) fail('unique task references and keys are required');
    if (!Number.isFinite(task.hours) || task.hours < 0.25 || Math.abs(task.hours * 4 - Math.round(task.hours * 4)) > 0.00001) fail('effort must use positive quarter-hour increments');
    if (!Number.isInteger(task.target_week) || task.target_week < 1 || task.target_week > availability.weeks.length || !Array.isArray(task.dependency_keys)) fail('invalid target week or dependencies');
    if (task.day !== undefined && task.day !== null && !weekdays.includes(task.day)) fail('invalid task weekday');
    byReference.set(task.reference, task); byKey.set(task.task_key, task);
  }
  const slots = availability.weeks.map(week => week.slots.map(slot => ({start: Date.parse(slot.start), end: Date.parse(slot.end)})));
  const weekState = availability.weeks.map(week => ({week: week.week, usable_minutes: week.usable_minutes, budget: week.usable_minutes, existing_minutes: 0, recommended_minutes: 0, required_minutes: 0, unallocated_minutes: 0}));
  const booked = new Map(), results = new Map(), completedAt = new Map(), processing = new Set(), limitations = [...availability.limitations];
  const timingConflicts = [];
  const currentKey = key => currentTasks.find(current => current.reference?.endsWith(':' + key));
  // Recognise every existing reservation before allocating any new time. This
  // makes weekly caps independent of the input task order.
  for (const task of tasks) {
    const current = currentByReference.get(task.reference), blocks = [];
    let credit = 0;
    if (current?.start || current?.end) {
      const rawStart = Date.parse(current.start), rawEnd = Date.parse(current.end);
      const reasons = [];
      const valid = Number.isFinite(rawStart) && Number.isFinite(rawEnd) && rawEnd > rawStart;
      if (!valid) fail('an existing task has invalid saved times');
      if (!current.blocks_time) reasons.push('The saved dates do not reserve time.');
      if (['Done', 'Cancelled'].includes(current.status)) reasons.push('The saved task is ' + current.status.toLowerCase() + '.');
      const matching = availability.busy_intervals.find(interval => normalId(interval.page_id) && normalId(interval.page_id) === normalId(current.page_id ?? current.id) || interval.reference === task.reference && interval.start === current.start && interval.end === current.end);
      const conflicts = availability.busy_intervals.filter(interval => interval !== matching && Date.parse(interval.start) < rawEnd && Date.parse(interval.end) > rawStart);
      if (conflicts.length) reasons.push('The saved reservation overlaps another calendar item and needs review.');
      const start = Math.max(rawStart, horizonStart, now), end = Math.min(rawEnd, horizonEnd, task.due_date ? dateEnd(task.due_date) : Infinity);
      if (end <= start) reasons.push('The saved reservation is outside the future planning horizon or deadline.');
      if (current.blocks_time && !['Done', 'Cancelled'].includes(current.status) && !matching) reasons.push('The saved reservation could not be verified in the current calendar review.');
      if (!reasons.length) credit = Math.min(task.hours * 60, Math.floor((end - start) / quarter) * 15);
      const creditedByWeek = [], reservedByWeek = [];
      if (!reasons.length) {
        for (let index = 0; index < weekState.length; index++) {
          const week = availability.weeks[index], a = Math.max(start, Date.parse(week.window_start)), b = Math.min(end, Date.parse(week.window_end));
          const amount = Math.max(0, (b - a) / minute);
          if (amount) { weekState[index].existing_minutes += amount; reservedByWeek.push({week: index + 1, minutes: amount}); }
        }
      }
      let rest = credit;
      for (let index = 0; index < weekState.length && rest > 0; index++) {
        const week = availability.weeks[index], a = Math.max(start, Date.parse(week.window_start)), b = Math.min(end, Date.parse(week.window_end));
        const amount = Math.min(rest, Math.max(0, Math.floor((b - a) / quarter) * 15));
        if (amount) { creditedByWeek.push({week: index + 1, minutes: amount}); rest -= amount; }
      }
      credit -= rest;
      if (credit && (rawStart < Date.parse(availability.weeks[task.target_week - 1].window_start) || rawEnd > Date.parse(availability.weeks[task.target_week - 1].window_end))) {
        reasons.push('The saved reservation is outside the suggested target week; it was preserved and counted without moving it.');
        timingConflicts.push({reference: task.reference, reason: reasons.at(-1)});
      }
      if (credit && task.day && weekdays[new Date(rawStart + 10 * 3600000).getUTCDay()] !== task.day) {
        reasons.push('The saved reservation is on a different weekday from the suggestion; it was preserved and counted without moving it.');
        timingConflicts.push({reference: task.reference, reason: reasons.at(-1)});
      }
      blocks.push({page_id: current.page_id ?? current.id ?? null, start: current.start, end: current.end, status: current.status, blocks_time: current.blocks_time, minutes: (rawEnd - rawStart) / minute, credited_minutes: credit, credited_by_week: creditedByWeek, reserved_by_week: reservedByWeek, reasons});
    }
    booked.set(task.reference, {blocks, credit});
  }
  for (const week of weekState) {
    if (availability.weekly_cap_hours !== null) {
      const cap = Math.floor(availability.weekly_cap_hours * 60 / 15) * 15;
      week.budget = Math.min(week.budget, Math.max(0, Math.floor((cap - week.existing_minutes) / 15) * 15));
      if (week.existing_minutes > cap) limitations.push('Existing task reservations in week ' + week.week + ' exceed the chosen weekly hours; they were preserved.');
    }
  }
  const planTask = task => {
    if (results.has(task.reference)) return;
    if (processing.has(task.reference)) fail('cyclic dependencies cannot be scheduled');
    processing.add(task.reference);
    const saved = currentByReference.get(task.reference), existing = booked.get(task.reference);
    const reasons = existing.blocks.flatMap(block => block.reasons), proposed = [];
    let remaining = task.hours * 60 - existing.credit, dependencyReadyAt = now;
    let earliest = Math.max(now, Date.parse(availability.weeks[task.target_week - 1].window_start));
    let dependencyBlocked = false;
    for (const key of task.dependency_keys) {
      const dependency = byKey.get(key), current = currentKey(key);
      if (current?.status === 'Done') continue;
      if (dependency) {
        planTask(dependency);
        if (results.get(dependency.reference).remaining_hours > 0 || !completedAt.has(dependency.reference)) {
          reasons.push('Dependency ' + key + ' has no complete feasible time allocation.'); dependencyBlocked = true;
        } else { dependencyReadyAt = Math.max(dependencyReadyAt, completedAt.get(dependency.reference)); earliest = Math.max(earliest, dependencyReadyAt); }
      } else { reasons.push('Dependency ' + key + ' is not confirmed complete and has no proposed time allocation.'); dependencyBlocked = true; }
    }
    const index = task.target_week - 1, state = weekState[index];
    state.required_minutes += ['Done', 'Cancelled'].includes(saved?.status) ? 0 : task.hours * 60;
    const deadline = Math.min(Date.parse(availability.weeks[index].window_end), task.due_date ? dateEnd(task.due_date) : Infinity);
    if (saved?.status === 'Done' || saved?.status === 'Cancelled') {
      reasons.push('This task is ' + saved.status.toLowerCase() + '; no new work blocks were proposed.');
      remaining = 0;
      if (saved.status === 'Done') completedAt.set(task.reference, now);
    } else if (dependencyBlocked || existing.blocks.some(block => block.blocks_time && !block.credited_minutes && block.reasons.length)) {
      // Existing reservations remain visible even if dependencies need review.
      if (!dependencyBlocked) reasons.push('Review the existing reservation before proposing additional work time for this task.');
    } else {
      const existingBeforeDependency = task.dependency_keys.length > 0 && existing.blocks.some(block => block.credited_minutes && Date.parse(block.start) < dependencyReadyAt);
      if (existingBeforeDependency && task.dependency_keys.length) {
        const reason = 'A saved reservation begins before a dependency can finish; review the saved schedule.';
        reasons.push(reason); timingConflicts.push({reference: task.reference, reason});
      }
      slots[index].sort((a, b) => a.start - b.start);
      for (const slot of [...slots[index]]) {
        if (task.day && weekdays[new Date(slot.start + 10 * 3600000).getUTCDay()] !== task.day) continue;
        let cursor = Math.ceil(Math.max(slot.start, earliest) / quarter) * quarter;
        const end = Math.min(slot.end, deadline);
        while (remaining > 0 && state.budget >= 15 && cursor + quarter <= end) {
          const take = Math.min(90, remaining, state.budget, Math.floor((end - cursor) / quarter) * 15);
          if (take < 15) break;
          if (cursor > slot.start) slots[index].push({start: slot.start, end: cursor});
          proposed.push({start: iso(cursor), end: iso(cursor + take * minute), minutes: take});
          remaining -= take; state.budget -= take; state.recommended_minutes += take;
          cursor += take * minute; slot.start = cursor;
        }
        if (!remaining || state.budget < 15) break;
      }
      if (!remaining && !existingBeforeDependency) {
        const ends = [...proposed.map(block => Date.parse(block.end)), ...existing.blocks.filter(block => block.credited_minutes).map(block => Math.min(Date.parse(block.end), horizonEnd))];
        completedAt.set(task.reference, ends.length ? Math.max(...ends) : earliest);
      }
    }
    if (remaining > 0 && !dependencyBlocked) reasons.push('The remaining effort does not fit the requested week, deadline and available-hours budget; no blocks were moved to another week.');
    state.unallocated_minutes += remaining;
    results.set(task.reference, {reference: task.reference, task_key: task.task_key, task: task.task, target_week: task.target_week, hours_required: task.hours, existing_blocks: existing.blocks, suggested_blocks: proposed, remaining_hours: remaining / 60, reasons});
    processing.delete(task.reference);
  };
  for (const task of tasks) planTask(task);
  const recommendations = tasks.map(task => results.get(task.reference));
  const required = tasks.reduce((sum, task) => sum + (['Done', 'Cancelled'].includes(currentByReference.get(task.reference)?.status) ? 0 : task.hours), 0);
  const credited = [...booked.values()].reduce((sum, value) => sum + value.credit, 0) / 60;
  const recommended = weekState.reduce((sum, week) => sum + week.recommended_minutes, 0) / 60;
  const unallocated = recommendations.reduce((sum, task) => sum + task.remaining_hours, 0);
  return {required_hours: required, existing_booked_hours: weekState.reduce((sum, week) => sum + week.existing_minutes, 0) / 60, credited_existing_hours: credited, recommended_hours: recommended, unallocated_hours: unallocated, feasibility: unallocated > 0 || timingConflicts.length ? 'shortfall' : 'fits', timing_conflicts: timingConflicts,
    weeks: weekState.map(week => ({week: week.week, usable_hours: week.usable_minutes / 60, required_hours: week.required_minutes / 60, existing_booked_hours: week.existing_minutes / 60, recommended_hours: week.recommended_minutes / 60, unallocated_hours: week.unallocated_minutes / 60})),
    task_recommendations: recommendations,
    limitations: [...limitations, 'Effort estimates are approximate. Suggested blocks are proposals only and have not been booked.', 'Existing reservations retain their saved dates, time and status; resolve flagged conflicts explicitly.'],
  };
}
function addTimeSummary(row){
  const result=JSON.parse(row.result_json);
  if(result.schema_version!=='3.0'||!result.time_recommendations)return row;
  const t=result.time_recommendations;
  row.summary+='\n\nCalendar review — '+(t.feasibility==='fits'?'estimated work fits the proposed sessions':'time or schedule needs review')+'\n'+
    'Required effort: '+t.required_hours+' h. Already booked: '+t.existing_booked_hours+' h ('+t.credited_existing_hours+' h credited toward remaining work). Suggested new sessions: '+t.recommended_hours+' h. Unallocated work: '+t.unallocated_hours+' h.\nSuggested sessions have not been booked.';
  return row;
}
const formatted=(function(){
const dependencyKey = value => String(value ?? '').trim().toLowerCase();
const dependencySimilarity = (left, right) => {
  const a = new Set(dependencyKey(left).split(/[^a-z0-9]+/).filter(Boolean)), b = new Set(dependencyKey(right).split(/[^a-z0-9]+/).filter(Boolean));
  if (!a.size || !b.size) return 0;
  let shared = 0;
  for (const token of a) if (b.has(token)) shared++;
  return shared / (a.size + b.size - shared);
};
const dependencyCandidates = (seenKeysMap, seenNames) => {
  const candidates = new Map();
  for (const [key, entry] of seenKeysMap) candidates.set(entry.task_key, { entry, texts: [String(key).replace(/[_-]+/g, ' ')] });
  for (const [title, entry] of seenNames) {
    if (!candidates.has(entry.task_key)) candidates.set(entry.task_key, { entry, texts: [] });
    candidates.get(entry.task_key).texts.push(String(title));
  }
  return [...candidates.values()];
};
// A declared dependency is matched to an EARLIER task in this plan by task_key, then by task
// title, then by a conservative token-similarity fallback (>= 0.75 with a >= 0.25 margin).
const matchDependency = (declared, seenKeysMap, seenNames) => {
  const key = dependencyKey(declared);
  if (seenKeysMap.has(key)) return seenKeysMap.get(key);
  if (seenNames.has(key)) return seenNames.get(key);
  const scored = dependencyCandidates(seenKeysMap, seenNames)
    .filter(candidate => candidate.texts.length)
    .map(candidate => ({ entry: candidate.entry, score: Math.max(...candidate.texts.map(text => dependencySimilarity(key, text))) }))
    .sort((a, b) => b.score - a.score);
  if (!scored.length || scored[0].score < 0.75) return null;
  if (scored.length > 1 && scored[0].score - scored[1].score < 0.25) return null;
  return scored[0].entry;
};
// Dependency validation is advisory: an unmatched or unusable dependency is reported in the plan
// assumptions and dropped. It never aborts the run, so the plan is still produced and saved.
const linkDependencies = (value, name, notes, seenKeysMap, seenNames) => {
  const isList = Array.isArray(value), isSingle = !isList && typeof value === 'string' && Boolean(value.trim());
  if (!isList && !isSingle && value !== null && value !== undefined) notes.push('Unusable dependencies were ignored for "' + name + '".');
  const declared = isList ? value : isSingle ? [value] : [];
  const linked = [];
  for (const raw of declared) {
    if (typeof raw !== 'string' || !raw.trim()) { notes.push('Unusable dependency entry ignored for "' + name + '".'); continue; }
    const match = matchDependency(raw, seenKeysMap, seenNames);
    if (!match) { notes.push('Dependency "' + raw.trim() + '" could not be matched to an earlier task in this plan and was ignored.'); continue; }
    if (linked.some(entry => entry.task_key === match.task_key)) continue;
    linked.push(match);
  }
  return linked;
};
const orderNotes = (late, name) => late.length ? '"' + name + '" depends on ' + late.map(entry => '"' + entry.name + '"').join(', ') + ', which this plan proposes later; the proposed order needs review.' : null;
function legacyFormat(){
const src = $('Combine context with brief').first().json;
  const replay = $json.replay_result ?? null;
  if (replay && (replay.reference !== src.brief.reference || replay.project_reference !== src.brief.project_reference || !replay.plan || !Array.isArray(replay.plan.tasks))) throw new Error('Saved plan identity does not match this request.');
  let o = $json.output ?? $json.text ?? $json;
  if (typeof o === 'string') {
    try { o = JSON.parse(o); } catch { throw new Error('No valid structured AI output.'); }
  }
  const keys = (value, allowed, required) => value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).every(x => allowed.includes(x)) && required.every(x => Object.hasOwn(value, x));
  if (!keys(o, ['summary', 'next_action', 'assumptions', 'tasks'], ['summary', 'next_action', 'assumptions', 'tasks']) || typeof o.summary !== 'string' || !o.summary.trim() || typeof o.next_action !== 'string' || !o.next_action.trim() || !Array.isArray(o.assumptions) || o.assumptions.some(x => typeof x !== 'string') || !Array.isArray(o.tasks) || o.tasks.length > 12) throw new Error('Invalid weekly plan structure.');
  const brief = src.brief;
  if (brief.hours_available === 0 && o.tasks.length) throw new Error('A zero-hour week cannot contain planned work.');
  const prefix = 'planner:' + brief.project_reference + ':';
  const current = new Map(src.project_context.items.map(x => [x.reference, x]));
  const normalTitle = value => String(value ?? '').trim().toLowerCase();
  const proposedNames = new Set(o.tasks.map(t => normalTitle(t?.task)));
  const proposedReferences = new Set(o.tasks.map(t => t?.existing_reference ?? (prefix + t?.task_key)));
  const currentByTitle = new Map();
  for (const item of src.project_context.items) {
    const title = normalTitle(item.title);
    const matches = currentByTitle.get(title) ?? [];
    matches.push(item);
    currentByTitle.set(title, matches);
  }
  const satisfiedReferences = new Set();
  o = { ...o, assumptions: [...o.assumptions] };
  const seenKeys = new Set();
  const seenNames = new Map(); const seenKeysMap = new Map();
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const weekFirstDay = new Date(brief.week_start).getUTCDay();
  const suppliedDates = new Set((brief.goal + '\n' + brief.backlog + '\n' + brief.constraints).match(/\b\d{4}-\d{2}-\d{2}\b/g) ?? []);
  const dateOnly = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
  let total = 0;
  const tasks = [];
  for (const t of o.tasks) {
    const allowed = ['task_key', 'existing_reference', 'task', 'day', 'hours', 'depends_on', 'done_when', 'due_date'];
    if (!keys(t, allowed, allowed) || typeof t.task_key !== 'string' || !/^[a-z0-9][a-z0-9_-]{0,19}$/.test(t.task_key) || seenKeys.has(t.task_key)) throw new Error('Every task needs a unique stable task_key of 1–20 lowercase letters, digits, underscores or hyphens.');
    if (typeof t.task !== 'string' || !t.task.trim() || t.task.length > 200 || typeof t.done_when !== 'string' || !t.done_when.trim() || t.done_when.length > 1200 || !Number.isFinite(t.hours) || t.hours < 0.25 || t.hours > 80) throw new Error('Invalid task title, estimate or completion criterion.');
    const name = t.task.trim();
    const canonicalName = name.toLowerCase();
    if (seenNames.has(canonicalName)) throw new Error('Duplicate task name.');
    const dayIndex = days.findIndex(x => x.toLowerCase() === String(t.day).toLowerCase());
    if (dayIndex < 0) throw new Error('Use a complete weekday name for each suggested day.');
    const offset = (dayIndex - weekFirstDay + 7) % 7;
    const dependencies = linkDependencies(t.depends_on, name, o.assumptions, seenKeysMap, seenNames);
    const lateDependencies = orderNotes(dependencies.filter(x => x.offset > offset), name);
    if (lateDependencies) o.assumptions.push(lateDependencies);
    const reference = prefix + t.task_key;
    if (t.existing_reference !== null && (typeof t.existing_reference !== 'string' || t.existing_reference !== reference || (!replay && !current.has(t.existing_reference)))) throw new Error('An existing_reference must match a task actually loaded for this project and its task_key.');
    if (!replay && t.existing_reference === null && current.has(reference)) throw new Error('This task_key already exists. Reuse its existing_reference instead of creating a replacement.');
    const existing = current.get(reference);
    if (!replay && existing && ['Done', 'Cancelled'].includes(existing.status)) throw new Error('Completed or cancelled tasks cannot be reopened by a weekly proposal.');
    const savedTask = replay?.plan.tasks.find(x => x.task_key === t.task_key && x.reference === reference);
    const deadlineWasSupplied = suppliedDates.has(t.due_date) || (existing && existing.due_date === t.due_date) || (savedTask && savedTask.due_date === t.due_date);
    if (t.due_date !== null && (!dateOnly(t.due_date) || !deadlineWasSupplied)) throw new Error('A due date must be a real ISO date supplied in the brief, loaded existing task, or the same saved task on replay. Suggested days do not set deadlines.');
    total += t.hours;
    seenKeys.add(t.task_key);
    seenNames.set(canonicalName, { task_key: t.task_key, name, offset }); seenKeysMap.set(t.task_key, { task_key: t.task_key, name, offset });
    tasks.push({ ...t, depends_on: dependencies.map(x => x.name), task: name, day: days[dayIndex], reference, suggested_date: new Date(Date.parse(brief.week_start) + offset * 86400000).toISOString().slice(0, 10), dependency_keys: dependencies.map(x => x.task_key) });
  }
  if (total > brief.hours_available + 0.000001) throw new Error('Plan exceeds the available hours; revise the brief and rerun.');
  total = Math.round(total * 1000000) / 1000000;
  const save = brief.mode === 'Save tasks to Notion';
  const known_pages = { ...(replay?.sync?.known_pages ?? {}) };
  for (const item of [...(replay?.current_tasks ?? []), ...(replay?.sync?.items ?? []), ...src.project_context.items]) if (typeof item.reference === 'string' && item.page_id && !known_pages[item.reference]) known_pages[item.reference] = item.page_id;
  const sync = { mode: brief.mode, status: !save ? 'DRAFT' : tasks.length ? 'PENDING' : 'NO_TASKS', checked_at: src.project_context.checked_at, items: [], errors: [], known_pages, resume_requires_existing: Boolean(replay?.sync_started) };
  const result = { schema_version: '2.0', reference: brief.reference, project_reference: brief.project_reference, week_start: brief.week_start, week_end: brief.week_end, timezone: brief.timezone, sync_started: save && tasks.length > 0, plan: { summary: o.summary.trim(), next_action: o.next_action.trim(), assumptions: o.assumptions, tasks, total_hours: total, hours_available: brief.hours_available }, current_tasks: src.project_context.items, busy: src.project_context.busy, sync };
  const plannedText = tasks.length ? tasks.map((t, i) => `${i + 1}. ${t.task} — suggested ${t.day} ${t.suggested_date}, ${t.hours}h\nReference: ${t.reference}\nDone when: ${t.done_when}${t.due_date ? '\nProposed deadline: ' + t.due_date : ''}`).join('\n\n') : 'No work allocated this week.';
  const currentText = src.project_context.items.length ? src.project_context.items.map(t => `${t.title} [${t.reference}] — ${t.status}; ${t.blocks_time && t.start ? 'scheduled ' + t.start + ' to ' + t.end : 'unscheduled'}${t.due_date ? '; deadline ' + t.due_date : ''}`).join('\n') : 'No saved tasks in this project.';
  const intro = !save ? 'DRAFT — no Notion changes requested.' : tasks.length ? 'PENDING — Notion task saves have not yet been confirmed.' : 'NO_TASKS — no Notion changes required.';
  const summary = `${intro}\n\n${result.plan.summary}\n\nProposed work for ${brief.week_start} to ${brief.week_end}\n${plannedText}\n\nTotal: ${total}h of ${brief.hours_available}h. Days are suggestions; no time blocks are created.\nAssumptions: ${o.assumptions.join('; ') || 'None'}\n\nCurrent saved state (read ${src.project_context.checked_at})\n${currentText}\n\nExisting task titles, progress, notes and dates are preserved when saving this proposal. For intentional edits, open the task link below and copy its Notion link into Edit or reschedule in the calendar/task workflow.`;
  return { json: { record_key: src.record_key, workflow: src.workflow, status: save && tasks.length ? 'PENDING' : 'READY', title: brief.goal, contact_email: '', raw_input: src.raw_input, result_json: JSON.stringify(result), summary, draft_id: '', next_action: o.next_action.trim(), due_at: '', should_sync: save && tasks.length > 0 } };
}
function modeSummary(result, headline, errorText = '') {
  const detailed = result.planning_style === 'Detailed time planning';
  const plannedText = result.plan.tasks.length ? result.plan.tasks.map((t, i) => `${i + 1}. ${t.task} — target week ${t.target_week} (${t.target_week_start} to ${t.target_week_end})${detailed ? ', suggested ' + t.day + ', estimated ' + t.hours + 'h' : ''}\nReference: ${t.reference}\nDone when: ${t.done_when}${t.due_date ? '\nExplicit deadline: ' + t.due_date : ''}`).join('\n\n') : 'No remaining work proposed.';
  const currentText = result.current_tasks.length ? result.current_tasks.map(t => `${t.title} [${t.reference}] — ${t.status}; ${t.blocks_time && t.start ? 'scheduled ' + t.start + ' to ' + t.end : 'unscheduled'}${t.due_date ? '; deadline ' + t.due_date : ''}`).join('\n') : 'No saved tasks in this project.';
  const effort = detailed ? `\nEstimated effort to complete proposed work: ${result.plan.total_hours}h.${result.plan.hours_available === null ? ' No weekly project-hour limit supplied.' : ' Optional weekly project-hour limit: ' + result.plan.hours_available + 'h.'}\nEstimates are provisional. Calendar suggestions do not book time.` : '\nTarget weeks are a broad sequence and do not book calendar time or set task deadlines.';
  return `${headline}\n\n${result.plan.summary}\n\n${result.planning_style}: ${result.week_start} to ${result.week_end}\n${plannedText}\n${effort}\nAssumptions: ${result.plan.assumptions.join('; ') || 'None'}\n\nCurrent saved state (read ${result.sync.checked_at})\n${currentText}${errorText}\n\nExisting task titles, progress, notes and dates are preserved when saving. Use the calendar/task workflow for intentional edits.`;
}
const src = $('Combine context with brief').first().json;
  const replay = $json.replay_result ?? null;
  if (replay?.schema_version === '2.0') return legacyFormat();
  if (replay && (replay.schema_version !== '3.0' || replay.reference !== src.brief.reference || replay.project_reference !== src.brief.project_reference || !replay.plan || !Array.isArray(replay.plan.tasks))) throw new Error('Saved plan identity does not match this request.');
  let o = $json.output ?? $json.text ?? $json;
  if (typeof o === 'string') { try { o = JSON.parse(o); } catch { throw new Error('No valid structured AI output.'); } }
  const keys = (v, allowed) => v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).every(x => allowed.includes(x)) && allowed.every(x => Object.hasOwn(v, x));
  if (!keys(o, ['summary', 'next_action', 'assumptions', 'tasks']) || typeof o.summary !== 'string' || !o.summary.trim() || typeof o.next_action !== 'string' || !o.next_action.trim() || !Array.isArray(o.assumptions) || o.assumptions.some(x => typeof x !== 'string') || !Array.isArray(o.tasks) || o.tasks.length > 24) throw new Error('Invalid project plan structure.');
  const brief = src.brief;
  const detailed = brief.planning_style === 'Detailed time planning';
  const days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const firstDay = new Date(brief.week_start).getUTCDay();
  const prefix = 'planner:' + brief.project_reference + ':';
  const current = new Map(src.project_context.items.map(x => [x.reference, x]));
  const normalTitle = value => String(value ?? '').trim().toLowerCase();
  const proposedNames = new Set(o.tasks.map(t => normalTitle(t?.task)));
  const proposedReferences = new Set(o.tasks.map(t => t?.existing_reference ?? (prefix + t?.task_key)));
  const currentByTitle = new Map();
  for (const item of src.project_context.items) { const title = normalTitle(item.title); const matches = currentByTitle.get(title) ?? []; matches.push(item); currentByTitle.set(title, matches); }
  const satisfiedReferences = new Set();
  o = { ...o, assumptions: [...o.assumptions] };
  const seenKeys = new Set();
  const seenNames = new Map(); const seenKeysMap = new Map();
  const suppliedDates = new Set((brief.goal + '\n' + brief.backlog + '\n' + brief.constraints).match(/\b\d{4}-\d{2}-\d{2}\b/g) ?? []);
  const dateOnly = v => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v;
  let total = 0;
  const tasks = [];
  for (const t of o.tasks) {
    if (!keys(t, ['task_key', 'existing_reference', 'task', 'target_week', 'day', 'hours', 'depends_on', 'done_when', 'due_date']) || typeof t.task_key !== 'string' || !/^[a-z0-9][a-z0-9_-]{0,29}$/.test(t.task_key) || (!replay && t.existing_reference === null && t.task_key.length > 20) || seenKeys.has(t.task_key)) throw new Error('Every new task needs a unique stable task_key of 1–20 lowercase letters, digits, underscores or hyphens.');
    if (typeof t.task !== 'string' || !t.task.trim() || t.task.length > 200 || typeof t.done_when !== 'string' || !t.done_when.trim() || t.done_when.length > 1200) throw new Error('Invalid task title or completion criterion.');
    if (detailed ? (!Number.isFinite(t.hours) || t.hours < 0.25 || t.hours > 168 || t.hours * 4 !== Math.round(t.hours * 4)) : t.hours !== null) throw new Error(detailed ? 'Detailed tasks need quarter-hour effort estimates between 0.25 and 168 hours.' : 'Broad timeline tasks must not include hour estimates.');
    if (!Number.isInteger(t.target_week) || t.target_week < 1 || t.target_week > brief.horizon_weeks) throw new Error('Each task target week must fall inside the planning horizon.');
    if (detailed ? !brief.work_days.includes(t.day) : t.day !== null) throw new Error(detailed ? 'Choose a full weekday from the allowed work days.' : 'Broad timeline tasks must not select a weekday.');
    const position = (t.target_week - 1) * 7 + (detailed ? (days.indexOf(t.day) - firstDay + 7) % 7 : 0);
    const name = t.task.trim(); const canonicalName = normalTitle(name);
    if (seenNames.has(canonicalName)) throw new Error('Duplicate task name.');
    const dependencies = linkDependencies(t.depends_on, name, o.assumptions, seenKeysMap, seenNames);
    const lateDependencies = orderNotes(dependencies.filter(x => x.position > position), name);
    if (lateDependencies) o.assumptions.push(lateDependencies);
    const reference = prefix + t.task_key;
    if (t.existing_reference !== null && (typeof t.existing_reference !== 'string' || t.existing_reference !== reference || (!replay && !current.has(t.existing_reference)))) throw new Error('An existing_reference must match a task actually loaded for this project and its task_key.');
    if (!replay && t.existing_reference === null && current.has(reference)) throw new Error('This task_key already exists. Reuse its existing_reference instead of creating a replacement.');
    if (!replay && t.existing_reference === null && (currentByTitle.get(canonicalName) ?? []).length) throw new Error('This task title already exists in the project. Reuse its existing reference rather than creating a duplicate.');
    const existing = current.get(reference);
    if (!replay && existing && ['Done', 'Cancelled'].includes(existing.status)) throw new Error('Completed or cancelled tasks cannot be reopened by a proposal.');
    const savedTask = replay?.plan.tasks.find(x => x.task_key === t.task_key && x.reference === reference);
    const deadlineWasSupplied = suppliedDates.has(t.due_date) || (existing && existing.due_date === t.due_date) || (savedTask && savedTask.due_date === t.due_date);
    if (t.due_date !== null && (!dateOnly(t.due_date) || !deadlineWasSupplied)) throw new Error('A due date must be a real ISO date supplied in the brief, loaded existing task, or the same saved task on replay. Target weeks do not set deadlines.');
    total += t.hours ?? 0;
    seenKeys.add(t.task_key); seenNames.set(canonicalName, { task_key: t.task_key, name, target_week: t.target_week, position }); seenKeysMap.set(t.task_key, { task_key: t.task_key, name, target_week: t.target_week, position });
    const target_week_start = new Date(Date.parse(brief.week_start) + (t.target_week - 1) * 7 * 86400000).toISOString().slice(0, 10);
    const target_week_end = new Date(Date.parse(target_week_start) + 6 * 86400000).toISOString().slice(0, 10);
    tasks.push({ ...t, depends_on: dependencies.map(x => x.name), task: name, reference, target_week_start, target_week_end, dependency_keys: dependencies.map(x => x.task_key) });
  }
  total = Math.round(total * 1000000) / 1000000;
  const save = brief.mode === 'Save tasks to Notion';
  const known_pages = { ...(replay?.sync?.known_pages ?? {}) };
  for (const item of [...(replay?.current_tasks ?? []), ...(replay?.sync?.items ?? []), ...src.project_context.items]) if (typeof item.reference === 'string' && item.page_id && !known_pages[item.reference]) known_pages[item.reference] = item.page_id;
  const sync = { mode: brief.mode, status: !save ? 'DRAFT' : tasks.length ? 'PENDING' : 'NO_TASKS', checked_at: src.project_context.checked_at, items: [], errors: [], known_pages, resume_requires_existing: Boolean(replay?.sync_started) };
  const result = { schema_version: '3.0', reference: brief.reference, project_reference: brief.project_reference, planning_style: brief.planning_style, horizon_weeks: brief.horizon_weeks, week_start: brief.week_start, week_end: brief.week_end, timezone: brief.timezone, sync_started: save && tasks.length > 0, plan: { summary: o.summary.trim(), next_action: o.next_action.trim(), assumptions: o.assumptions, tasks, total_hours: detailed ? total : null, hours_available: detailed ? brief.hours_available : null }, current_tasks: src.project_context.items, busy: src.project_context.busy, sync };
  const intro = !save ? 'DRAFT — no Notion changes requested.' : tasks.length ? 'PENDING — Notion task saves have not yet been confirmed.' : 'NO_TASKS — no Notion changes required.';
  return { json: { record_key: src.record_key, workflow: src.workflow, status: save && tasks.length ? 'PENDING' : 'READY', title: brief.goal, contact_email: '', raw_input: src.raw_input, result_json: JSON.stringify(result), summary: modeSummary(result, intro), draft_id: '', next_action: o.next_action.trim(), due_at: '', should_sync: save && tasks.length > 0 } };
})();
const r=JSON.parse(formatted.json.result_json);
if(r.schema_version==="3.0"){const source=$("Combine context with brief").first().json;r.availability=source.availability;r.time_recommendations=r.planning_style==="Detailed time planning"?recommendTimeBlocks(r.plan.tasks,source.availability,source.project_context.items):null;formatted.json.result_json=JSON.stringify(r);addTimeSummary(formatted.json);}
return formatted;
