import test from 'node:test';
import assert from 'node:assert/strict';
import { parseRequest, checkSetup, reviewWindow, collectSnapshot, snapshotRecord, retrieveSnapshot, LIMITS } from './review.mjs';
import { dailyOperations, onboardingOperations, applyOperations } from './workflow.mjs';

const now = '2026-09-17T00:30:00.000Z';
const request = { request_id:'review-test',session_id:'test-session',revision:2,action:'get_daily_review',arguments:{} };
const ctx = () => reviewWindow({origin:'scheduled'}, {}, now);
const sources = () => ({ incoming:[],spam:[],sent:[],drafts:[],work:[],reviews:[],organisation:[],calendar:[{action:'daily_review_context',status:'OK',mutated:false,items:[],tasks:[]}] });
const item = (key,status,updatedAt=now) => ({record_key:'outreach:'+key,workflow:'outreach',title:key,status,updatedAt,summary:'Saved result',next_action:'Review'});
const record = input => snapshotRecord(collectSnapshot(ctx(),input), 'test-execution', now);
const retrieve = row => retrieveSnapshot({agent:request},row,now).tool_result;

test('both retrieval action names preserve identity and reject rescan or write arguments',()=>{
  for(const action of ['get_priorities','get_daily_review']) assert.equal(parseRequest({chatInput:JSON.stringify({...request,action})}).agent.revision,2);
  for(const patch of [{request_id:12},{revision:-1},{arguments:{since:now}},{arguments:{move_emails:true}},{action:'send_email'}])
    assert.equal(parseRequest({chatInput:JSON.stringify({...request,...patch})}).agent_result.tool_result.status,'invalid_request');
});
test('collection day follows configured timezone, including daylight saving',()=>{
  const c=ctx();assert.equal(c.date,'2026-09-17');assert.equal(c.day_start,'2026-09-16T14:00:00.000Z');assert.equal(c.since,'2026-09-16T00:30:00.000Z');
  const dst=reviewWindow({timezone:'America/New_York'}, {}, '2026-03-08T14:00:00Z');
  assert.equal(dst.day_start,'2026-03-08T05:00:00.000Z');assert.equal(dst.day_end,'2026-03-09T04:00:00.000Z');
});
test('only complete preparation receipts advance the checkpoint; lookback caps are explicit',()=>{
  const previous=record(sources());
  const next=reviewWindow({},previous,'2026-09-18T00:30:00Z');assert.equal(next.since,now);assert.equal(next.since_basis,'previous_complete_snapshot');
  previous.status='PARTIAL';assert.equal(reviewWindow({},previous,'2026-09-20T00:30:00Z').since_basis,'last_24_hours');
  previous.status='DONE';assert.equal(reviewWindow({},previous,'2026-10-01T00:30:00Z').window_limited,true);
  assert.throws(()=>reviewWindow({},previous,'2026-09-16T00:30:00Z'));
});
test('preparation saves only source data, and retrieval returns it without a new briefing',()=>{
  const row=record(sources()),snapshot=JSON.parse(row.result_json).snapshot,r=retrieve(row);
  assert.equal(row.workflow,'daily_review');assert.equal(row.draft_id,'');assert.equal(row.status,'DONE');
  assert.equal(snapshot.preparation_only,true);assert.equal(snapshot.presentation_owner,'hermes');
  for(const field of ['agent','origin','full_text','spoken_summary','priorities','analysis_input']) assert.equal(field in snapshot,false);
  assert.equal(r.status,'completed');assert.equal(r.request_id,request.request_id);assert.equal(r.revision,2);
  assert.equal(r.data.live_sources_checked,false);assert.equal(r.data.retrieval_state,'ready');assert.deepEqual(r.data.snapshot,snapshot);
});
test('source failures and collection limits survive persistence and retrieval',()=>{
  const input=sources();input.incoming=[{error:'auth failed'}];input.calendar=[{error:'offline'}];
  const row=record(input),r=retrieve(row);assert.equal(row.status,'PARTIAL');assert.equal(r.status,'partial');
  assert.equal(r.data.snapshot.coverage.incoming.checked,false);assert.equal(r.data.snapshot.coverage.calendar.checked,false);
  input.incoming=Array.from({length:LIMITS.incoming},(_,i)=>({id:'mail'+i,subject:'Mail'}));input.calendar=sources().calendar;
  assert.equal(retrieve(record(input)).data.snapshot.coverage.incoming.may_be_truncated,true);
});
test('empty storage, retrieval failure, corrupted data, future timestamps and stale snapshots are distinct',()=>{
  assert.equal(retrieve({}).status,'not_found');assert.equal(retrieve({error:'offline'}).status,'failed');
  assert.equal(retrieve({record_key:'bad',result_json:'{bad'}).status,'failed');
  const row=record(sources());assert.equal(retrieveSnapshot({agent:request},row,'2026-09-16T00:30:00Z').tool_result.status,'failed');
  const stale=retrieveSnapshot({agent:request},row,'2026-09-17T14:01:00Z').tool_result;
  assert.equal(stale.status,'partial');assert.equal(stale.data.stale,true);assert.equal(stale.data.retrieval_state,'stale');
});
test('completed, recorded ongoing, queued and blocked work remain separate',()=>{
  const input=sources();input.work=[item('new','READY'),item('old','DONE','2026-09-01T00:00:00Z'),item('running','RESEARCHING'),item('queue','QUEUED'),item('bad','FAILED'),{...item('self','DONE'),workflow:'daily_review'},{...item('retired','READY'),workflow:'content'}];
  const r=retrieve(record(input)).data.snapshot;
  assert.deepEqual(r.workbench.completed.map(x=>x.title),['new']);assert.equal(r.workbench.ongoing.length,1);
  assert.equal(r.workbench.queued.length,1);assert.equal(r.workbench.needs_you[0].title,'bad');assert.equal(r.workbench.ongoing[0].recorded_status_only,true);
});
test('organisation reports count confirmed receipts and preserve the actual action',()=>{
  const input=sources();input.organisation=[{record_key:'email-org:1',updatedAt:now,result_json:JSON.stringify({confirmed:true,action:'labels_added',message_id:'1',label_names:['Automation/Processed']})},{record_key:'email-org:2',updatedAt:now,result_json:JSON.stringify({confirmed:false,action:'moved_to_label',message_id:'2'})}];
  const rows=retrieve(record(input)).data.snapshot.organisation;
  assert.equal(rows.length,1);assert.equal(rows[0].count,1);assert.equal(rows[0].action,'labels_added');
});
test('Hermes receives evidence for decisions, commitments, spam, meeting preparation and follow-ups',()=>{
  const input=sources();input.incoming=[{id:'mail1',subject:'Launch decision',text:'Please approve the launch date.',from:'client@example.com'}];
  input.sent=[{id:'sent1',text:'I will send the proposal tomorrow.',to:'client@example.com',threadId:'thread1'}];
  input.spam=[{id:'spam1',text:'Following up on the launch.',from:'client@example.com'}];
  input.drafts=[{id:'draft1',message:{id:'message1',subject:'Re: Launch',text:'Draft reply.'}}];
  input.calendar[0].items=[{page_id:'event1',type:'Event',title:'Launch meeting',notes:'Review the proposal',state_token:'version1',start:'2026-09-17T01:00:00Z',end:'2026-09-17T02:00:00Z'}];
  const s=retrieve(record(input)).data.snapshot;
  assert.equal(s.inbox[0].from,'client@example.com');assert.equal(s.sent[0].thread_id,'thread1');assert.match(s.sent[0].text,/I will/);
  assert.equal(s.spam[0].id,'spam1');assert.equal(s.drafts[0].reference,'draft:draft1');assert.equal(s.schedule[0].notes,'Review the proposal');
  assert.equal(s.references.find(x=>x.reference==='calendar:event1').state_token,'version1');
});
test('partial retries cannot overwrite a complete snapshot identity',()=>{
  const full=record(sources()),input=sources();input.incoming=[{error:'down'}];
  const partial=snapshotRecord(collectSnapshot(ctx(),input),'second-execution',now);
  assert.notEqual(full.record_key,partial.record_key);assert.equal(full.status,'DONE');assert.equal(partial.status,'PARTIAL');
  assert.throws(()=>snapshotRecord(collectSnapshot(ctx(),input),'',now));
});

// This fixture represents the existing daily graph, without account data or provider credentials.
function baseline() {
  const names=['Run manually','Weekdays at 8am Brisbane','Prepare scheduled digest','Read previous daily digest','Review collection window','Read pending work','Read pending email review','Read incoming email','Check recent spam','Read recent sent context','Read existing reply drafts','Read organisation receipts','Prepare connected calendar read','Read connected calendar','Build daily priorities','Record daily digest','Agent request','Parse agent request','Route priority request','Return spoken priorities','Sticky Note df7005a8','Digest request context','Analyse daily briefing','Validate and format daily review','Route digest output','One digest per day','Create daily digest draft'];
  return {id:'daily',name:'Daily Review',settings:{timezone:'Australia/Brisbane'},connections:{},nodes:names.map(name=>({id:name,name,type:name==='Weekdays at 8am Brisbane'?'n8n-nodes-base.scheduleTrigger':name==='Create daily digest draft'?'n8n-nodes-base.gmail':'n8n-nodes-base.code',typeVersion:2,parameters:name==='Read pending work'?{dataTableId:{value:'workbench'},filters:{conditions:[]}}:name==='Weekdays at 8am Brisbane'?{rule:{interval:[{triggerAtHour:8,triggerAtMinute:0}]}}:{}}))};
}
function reachable(w,start) {
  const seen=new Set(),todo=[start];while(todo.length){const n=todo.pop();if(seen.has(n))continue;seen.add(n);for(const out of w.connections[n]?.main??[])for(const edge of out)todo.push(edge.node);}return seen;
}
test('Hermes route only reads saved data; scheduled path only collects and persists',()=>{
  const b=baseline(),w=applyOperations(b,dailyOperations(b,{time:'07:15'})),agent=reachable(w,'Agent request'),scheduled=reachable(w,'Daily preparation time');
  assert.ok(agent.has('Read latest prepared snapshot'));assert.ok(agent.has('Return saved daily review'));
  for(const n of ['Read incoming email','Read connected calendar','Save daily review snapshot'])assert.equal(agent.has(n),false);
  assert.ok(scheduled.has('Save daily review snapshot'));assert.equal(scheduled.has('Return saved daily review'),false);
  for(const n of ['Create daily digest draft','Analyse daily briefing','Validate and format daily review'])assert.equal(w.nodes.some(x=>x.name===n),false);
  assert.deepEqual(w.nodes.find(x=>x.name==='Daily preparation time').parameters.rule.interval,[{field:'days',daysInterval:1,triggerAtHour:7,triggerAtMinute:15}]);
});
test('unselected daily time stays disabled and generator can safely reapply to its daily graph',()=>{
  const b=baseline(),first=applyOperations(b,dailyOperations(b));
  assert.equal(first.nodes.find(x=>x.name==='Daily preparation time').disabled,true);
  const second=applyOperations(first,dailyOperations(first,{time:'09:05'}));
  assert.equal(second.nodes.length,first.nodes.length);assert.equal(second.nodes.find(x=>x.name==='Daily preparation time').disabled,false);
  assert.throws(()=>dailyOperations(b,{time:'24:00'}));
});

const configuration = () => ({schema_version:1,configuration_id:'buyer-one',mode:'preview',time:'07:30',timezone:'Australia/Brisbane',sources:{email:false,workbench:true,calendar:false,reviews:false,organisation:false},labels:{}});
test('deferred setup reports readiness without permitting collection or retrieval',()=>{
  const config={...configuration(),mode:'setup_required'};
  assert.equal(checkSetup({origin:'scheduled',review_config:config}).agent_result.tool_result.status,'setup_required');
  assert.equal(checkSetup({origin:'agent',agent:request,review_config:config}).agent_result.tool_result.status,'setup_required');
  const parsed=parseRequest({chatInput:JSON.stringify({...request,action:'get_setup'})});
  const result=checkSetup({...parsed,review_config:config}).agent_result.tool_result;
  assert.equal(result.status,'completed');assert.equal(result.data.live_sources_checked,false);
});
test('only manual preview or active schedules may collect; paused retrieval stays available',()=>{
  const config=configuration();
  assert.equal(checkSetup({origin:'scheduled',review_config:config}).agent_result.tool_result.status,'paused');
  assert.equal(checkSetup({origin:'scheduled',manual:true,review_config:config}).configuration_id,'buyer-one');
  config.mode='active';assert.equal(checkSetup({origin:'scheduled',review_config:config}).configuration_id,'buyer-one');
  config.mode='paused';assert.equal(checkSetup({origin:'scheduled',manual:true,review_config:config}).agent_result.tool_result.status,'paused');
  assert.equal(checkSetup({origin:'agent',agent:request,review_config:config}).configuration_id,'buyer-one');
  config.time='24:00';assert.equal(checkSetup({origin:'scheduled',review_config:config}).agent_result.tool_result.status,'setup_required');
});
test('unselected sources are excluded even if old account data is supplied',()=>{
  const c=reviewWindow(checkSetup({origin:'scheduled',manual:true,review_config:configuration()}),{},now);
  const input=sources();input.work=[item('current','QUEUED')];input.incoming=[{id:'previous-account',subject:'Private old email'}];input.calendar=[{error:'not connected'}];
  const row=snapshotRecord(collectSnapshot(c,input),'work-only',now),saved=JSON.parse(row.result_json).snapshot;
  assert.equal(row.status,'DONE');assert.equal(row.raw_input,'buyer-one');assert.equal(saved.inbox.length,0);
  assert.equal(saved.workbench.queued.length,1);assert.equal(saved.coverage.incoming.skip_reason,'not_selected');
  assert.equal(saved.coverage.calendar.enabled,false);assert.deepEqual(saved.warnings,[]);
});
test('changing a configuration rejects old snapshots and resets collection checkpoint',()=>{
  const c=reviewWindow(checkSetup({origin:'scheduled',manual:true,review_config:configuration()}),{},now);
  const row=snapshotRecord(collectSnapshot(c,{work:[]}),'one',now);
  assert.equal(retrieveSnapshot({agent:request,configuration_id:'buyer-two'},row,now).tool_result.status,'not_found');
  assert.equal(reviewWindow({configuration_id:'buyer-two'},row,'2026-09-19T00:30:00Z').since_basis,'last_24_hours');
  assert.equal(reviewWindow({configuration_id:'buyer-one'},row,'2026-09-19T00:30:00Z').since_basis,'previous_complete_snapshot');
});
test('onboarding graph routes every trigger through setup and scopes both storage reads',()=>{
  const first=applyOperations(baseline(),dailyOperations(baseline()));
  const w=applyOperations(first,onboardingOperations(first));
  for(const trigger of ['Run manually','Agent request','Daily preparation time']) assert.equal(w.connections[trigger].main[0][0].node,'Parse agent request');
  assert.equal(w.connections['Check review setup'].main[0][0].node,'Route priority request');
  assert.equal(w.connections['Route priority request'].main[0][0].node,'Return saved daily review');
  for(const n of ['Read last complete snapshot','Read latest prepared snapshot']) assert.ok(w.nodes.find(x=>x.name===n).parameters.filters.conditions.some(c=>c.keyName==='raw_input'));
  for(const gate of ['Include work?','Include email?','Include saved email reviews?','Include organisation receipts?','Include calendar?']) assert.equal(w.connections[gate].main.length,2);
  assert.equal(w.nodes.find(n=>n.name==='Daily preparation time').disabled,true);
  const repeated=applyOperations(w,onboardingOperations(w));assert.equal(repeated.nodes.length,w.nodes.length);
});
