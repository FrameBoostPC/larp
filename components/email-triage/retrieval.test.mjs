import test from 'node:test';
import assert from 'node:assert/strict';
import {parseReviewRequest} from './triage.mjs';
import {retrievalOperations} from './retrieval.mjs';
import {buildEmailReviewResult, emailReviewNodeCode} from '../hermes-orchestration/email-review.mjs';

const request = (args, action='list_reviews') => ({chatInput:JSON.stringify({request_id:'search-1',session_id:'test',revision:1,action,arguments:args})});
const baseline = () => ({nodes:[
  {name:'Load push configuration',parameters:{jsCode:'const config={"mailbox":"owner@example.com"};\nreturn [];'}},
  {name:'Read requested email reviews',parameters:{matchType:'allConditions',filters:{conditions:[{keyName:'message_id'},{keyName:'category'},{keyName:'status'}]},limit:20,orderByColumn:'processed_at'}},
]});

test('supplier and subject searches combine with existing filters; names are not guessed as addresses',()=>{
  const q=parseReviewRequest(request({category:'RECEIPT',sender:' Bills@Example.com ',subject_contains:' Invoice ',limit:1}));
  assert.equal(q.raw.sender,'bills@example.com');
  assert.equal(q.raw.subject_contains,'Invoice');
  for(const args of [{sender:'Example Shop'},{sender:[]},{subject_contains:''},{subject_contains:'a\nb'},{subject_contains:'a'.repeat(201)},{sender:'x@y.com',send:true}])
    assert.equal(parseReviewRequest(request(args)).agent_result.tool_result.status,'invalid_request');
  assert.equal(parseReviewRequest(request({message_id:'m1',sender:'x@y.com'},'get_review')).agent_result.tool_result.status,'invalid_request');
});

test('deployed parser treats SQL wildcard punctuation as literal subject text',()=>{
  const [op]=retrievalOperations(baseline());
  const run=new Function('$input',op.parameters.jsCode);
  const parsed=run({first:()=>({json:request({subject_contains:'invoice_50%\\paid'})})})[0].json;
  assert.equal(parsed.subject_pattern,'%invoice\\_50\\%\\\\paid%');
  assert.equal(parsed.raw.subject_contains,'invoice_50%\\paid');
  assert.equal(run({first:()=>({json:{chatInput:'bad'}})})[0].json.agent_result.tool_result.status,'invalid_request');
});

test('migration preserves limits and existing filters and requires a verified mailbox',()=>{
  const b=baseline(), copy=structuredClone(b), ops=retrievalOperations(b);
  assert.deepEqual(b,copy);
  assert.equal(ops.length,3);
  assert.deepEqual(ops[1].parameters.filters.conditions.slice(0,3),b.nodes[1].parameters.filters.conditions);
  assert.equal(ops[1].parameters.limit,20);
  assert.equal(ops[1].parameters.matchType,'allConditions');
  b.nodes[0].parameters.jsCode='const config={};';
  assert.throws(()=>retrievalOperations(b),/mailbox required/);
});

test('Gmail links use the configured account and verified ID shape, with legacy fallback',()=>{
  const q=parseReviewRequest(request({sender:'bills@example.com',subject_contains:'invoice'}));
  const result=buildEmailReviewResult(q,[{message_id:'19a0123456789abc',thread_id:'19b0123456789abc',category:'RECEIPT'}],'2026-09-23T00:00:00Z','owner+receipts@example.com').tool_result;
  assert.equal(result.data.items[0].gmail_url,'https://mail.google.com/mail/?authuser=owner%2Breceipts%40example.com#all/19b0123456789abc');
  assert.equal(result.data.live_inbox_checked,false);
  assert.equal(result.data.filters.subject_contains,'invoice');
  for(const [id,mailbox] of [['bad/id','owner@example.com'],['19a0123456789abc',''],['19a0123456789abc','x\ny@example.com']])
    assert.equal(buildEmailReviewResult(q,[{message_id:id}],'2026-09-23',mailbox).tool_result.data.items[0].gmail_url,null);
});

test('published response wrapper carries mailbox binding and preserves source references',()=>{
  const q=parseReviewRequest(request({category:'RECEIPT'}));
  const rows=[{message_id:'19a0123456789abc',category:'RECEIPT'}];
  const run=new Function('$','$input','$now',emailReviewNodeCode('owner@example.com'));
  assert.deepEqual(run(()=>({first:()=>({json:q})}),{all:()=>rows.map(json=>({json}))},{toISO:()=> '2026-09-23T00:00:00Z'}),[{json:buildEmailReviewResult(q,rows,'2026-09-23T00:00:00Z','owner@example.com')}]);
});
