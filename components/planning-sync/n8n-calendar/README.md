# Practical calendar reads

These four JavaScript files are the Code-node sources for the existing n8n
Calendar & Task Manager. They add no nodes, credentials, database properties,
models or schedules. Each runs once for all items.

| File | Node |
| --- | --- |
| parse-request.js | Parse scheduling agent request |
| validate-request.js | Validate scheduling request |
| plan-action.js | Plan scheduling action |
| return-agent-result.js | Return scheduling agent result |

`list_tasks` combines optional title-word query, exact project, status and page
filters. Default reads remain open tasks only. Returned current IDs/state tokens
support later safe edits; ambiguous names remain separate. `check_slot` includes
up to two same-day alternatives if unavailable, using the requested duration,
buffers and daily/weekend search preferences. Results state that nothing was
booked. Other writes, receipts and schema remain unchanged.

Run `node components/planning-sync/n8n-calendar/read-actions.test.mjs`.
Ten tests execute the exact node sources with synthetic provider records,
covering filters, ambiguity, bad inputs, time/buffer limits, past/weekend and
multi-day cases, untouched conflict/state guards and spoken outcomes.

For deployment, read the current workflow first and preserve concurrent edits.
Set only these nodes' JavaScript parameters, validate, exercise live read-only
requests, then publish and compare with the tested source. These are bounded
node snapshots, not a full workflow installer. Keep actual provider records and
workflow exports outside the public repository. The owning contract is
`components/hermes-orchestration/workflow-contracts.md`.
