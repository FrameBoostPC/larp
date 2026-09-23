/** Saved review transport; provider refresh and mutations belong to their owners. */
export function buildEmailReviewResult(query, inputRows, retrievedAt, mailbox = '') {
  if (query.agent_result) return query.agent_result;
  const meta = query.agent || {};
  const envelope = (status, spoken, data = null) => ({
    output: spoken,
    tool_result: {
      schema_version: '1.0', request_id: meta.request_id ?? null,
      session_id: meta.session_id ?? null, revision: meta.revision ?? null,
      status, spoken_summary: spoken, data,
    },
  });
  const object = value => value && typeof value === 'object' && !Array.isArray(value);
  const identifier = value => typeof value === 'string' && value.trim() ? value : null;
  if (!Array.isArray(inputRows) || inputRows.some(row => !object(row) || row.error ||
      (Object.keys(row).length > 0 && !identifier(row.message_id)))) {
    return envelope('failed', 'The saved email reviews could not be read reliably.');
  }
  const rows = inputRows.filter(row => identifier(row.message_id));
  if (new Set(rows.map(row => row.message_id)).size !== rows.length ||
      (query.operation === 'get_review' && (rows.length > 1 ||
        rows.some(row => row.message_id !== query.raw.message_id)))) {
    return envelope('conflict', 'The saved email review references need attention.');
  }
  const now = Date.parse(retrievedAt);
  const items = rows.map(row => {
    const processed = typeof row.processed_at === 'string' ? Date.parse(row.processed_at) : NaN;
    const validTime = Number.isFinite(processed) && Number.isFinite(now) && processed <= now;
    const age = validTime ? Math.floor((now - processed) / 1000) : null;
    const thread = identifier(row.thread_id);
    const draft = identifier(row.draft_id);
    const gmailId = [thread, row.message_id].find(value => typeof value === 'string' && /^[a-f0-9]{10,32}$/i.test(value));
    const mailboxValid = typeof mailbox === 'string' && /^[^<>\s,@]+@[^<>\s,@]+\.[^<>\s,@]+$/.test(mailbox);
    return {
      message_id: row.message_id, thread_id: thread, category: row.category || 'OTHER',
      subject: row.subject, sender: row.sender, priority: row.priority,
      status: row.status, summary: row.summary, reason: row.reason,
      draft_id: draft, processed_at: row.processed_at,
      gmail_url: gmailId && mailboxValid ? `https://mail.google.com/mail/?authuser=${encodeURIComponent(mailbox)}#all/${gmailId}` : null,
      time_clash: row.time_clash === true, tags: row.time_clash === true ? ['clash'] : [],
      source_refs: { provider: 'gmail', message_id: row.message_id, thread_id: thread, draft_id: draft },
      review_age_seconds: age,
      historical: true,
      source_refresh_required: true,
      calendar_refresh_required: row.category === 'MEETING' || row.time_clash === true,
    };
  });
  const limit = query.raw?.limit || 20;
  const count = items.length;
  const categoryCounts = new Map();
  const statusCounts = new Map();
  for (const item of items) {
    for (const [group, value] of [[categoryCounts, item.category], [statusCounts, item.status]]) {
      const key = String(value ?? 'UNKNOWN');
      group.set(key, (group.get(key) || 0) + 1);
    }
  }
  const counts = { categories: Object.fromEntries(categoryCounts), statuses: Object.fromEntries(statusCounts) };
  const scope = query.raw?.category ? query.raw.category.toLowerCase() + ' ' : '';
  const spoken = count ? `I found ${count} saved ${scope}email review${count === 1 ? '' : 's'}.` : 'No saved email reviews matched.';
  return envelope(count || query.operation === 'list_reviews' ? 'completed' : 'not_found', spoken, {
    items, source: 'saved_email_review', live_inbox_checked: false,
    retrieved_at: retrievedAt, limit,
    may_have_more: query.operation === 'list_reviews' && count === limit,
    references_scope: 'configured_email_owner',
    filters: { category: query.raw?.category ?? null, status: query.raw?.status ?? null,
      sender: query.raw?.sender ?? null, subject_contains: query.raw?.subject_contains ?? null },
    counts, counts_scope: 'returned_items',
  });
}

export function emailReviewNodeCode(mailbox = '') {
  return buildEmailReviewResult.toString() + '\nreturn [{json:buildEmailReviewResult($("Parse agent request").first().json,$input.all().map(item=>item.json),$now.toISO(),' + JSON.stringify(mailbox) + ')}];';
}
