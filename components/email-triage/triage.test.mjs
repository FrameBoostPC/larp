import test from 'node:test';
import assert from 'node:assert/strict';
import {CATEGORIES, categoryPolicy, prepareLabels, parseReviewRequest, returnReviews} from './triage.mjs';
const result = overrides => ({category:'PERSONAL',disposition:'DRAFT',confidence:0.95,draft_body:'Thanks for the update.',reason:'Clear request',...overrides});
const request = (action='list_reviews',args={}) => ({chatInput:JSON.stringify({request_id:'test-01',session_id:'test',revision:1,action,arguments:args})});
const config = {processed:'processed',draftReady:'draft',manualReview:'review',clash:'clash',categories:Object.fromEntries(CATEGORIES.map(c=>[c,'category-'+c]))};

test('automated messages never override explicit or forced review',()=>{
  for(const category of CATEGORIES) {
    assert.equal(categoryPolicy({automated:true},result({category,disposition:'REVIEW'})).status,'REVIEW');
    assert.equal(categoryPolicy({automated:true,force_review:true,force_reason:'Sensitive'},result({category,disposition:'FILE'})).status,'REVIEW');
  }
});
test('low confidence routes every category to review before filing',()=>{
  for(const category of CATEGORIES) for(const confidence of [0.79,NaN,1.1,'0.95']) {
    assert.equal(categoryPolicy({automated:true},result({category,confidence,disposition:'FILE'})).status,'REVIEW');
  }
});
test('passive categories produce summaries with no reply',()=>{
  for(const category of ['NEWSLETTER','NOTIFICATION','PROMOTION','SOCIAL','RECEIPT']) assert.deepEqual(categoryPolicy({},result({category})),{status:'FILE',reason:'Clear request',draft:''});
});
test('human sales and personal drafts survive; unknown and recruitment require review',()=>{
  for(const category of ['SALES','PERSONAL','ACTION','MEETING']) assert.equal(categoryPolicy({},result({category})).status,'DRAFT');
  for(const category of ['OTHER','RECRUITMENT','FINANCE']) assert.equal(categoryPolicy({},result({category})).status,'REVIEW');
  assert.throws(()=>categoryPolicy({},result({category:'invented'})));
});
test('category and all status/clash labels are retained',()=>{
  const p=prepareLabels({message_id:'m1',category:'MEETING',status:'DRAFT_CREATED',draft_id:'d1',time_clash:true},config);
  assert.deepEqual(p.label_ids,['processed','category-MEETING','draft','clash']);
  assert.equal(prepareLabels({message_id:'m1',status:'REVIEW'},config).category,'OTHER');
  assert.throws(()=>prepareLabels({message_id:'m1',status:'DRAFT_CREATED'},config));
  assert.throws(()=>prepareLabels({message_id:'m1',status:'REVIEW'},{...config,categories:{...config.categories,ACTION:'processed'}}));
});
test('read requests support categories and status without accepting writes',()=>{
  const q=parseReviewRequest(request('list_reviews',{category:'SALES',status:'DRAFT_CREATED',limit:5}));
  assert.equal(q.raw.category,'SALES');
  for(const args of [{category:'made-up'},{status:'SENT'},{limit:51},{send:true}]) assert.equal(parseReviewRequest(request('list_reviews',args)).agent_result.tool_result.status,'invalid_request');
  assert.equal(parseReviewRequest(request('send')).agent_result.tool_result.status,'invalid_request');
  assert.equal(parseReviewRequest(request('get_review')).agent_result.tool_result.status,'needs_input');
  assert.equal(parseReviewRequest(request('get_review',{message_id:'m1'})).operation,'get_review');
});
test('summaries identify bounded saved data and preserve voice identity',()=>{
  const q=parseReviewRequest(request('list_reviews',{category:'SOCIAL',limit:1}));
  const out=returnReviews(q,[{message_id:'m1',category:'SOCIAL',status:'FILE',summary:'A new post is available.'}]).tool_result;
  assert.equal(out.data.live_inbox_checked,false);
  assert.equal(out.data.counts_scope,'returned_items');
  assert.equal(out.data.counts.categories.SOCIAL,1);
  assert.equal(out.data.may_have_more,true);
  assert.equal(out.request_id,'test-01');
  assert.equal(out.revision,1);
  assert.match(out.spoken_summary,/saved social/);
});
test('empty, historical, duplicate and invalid request results remain explicit',()=>{
  assert.equal(returnReviews(parseReviewRequest(request()),[{}]).tool_result.status,'completed');
  const q=parseReviewRequest(request('get_review',{message_id:'m1'}));
  assert.equal(returnReviews(q,[]).tool_result.status,'not_found');
  assert.equal(returnReviews(q,[{message_id:'m1'},{message_id:'m1'}]).tool_result.status,'conflict');
  assert.equal(returnReviews(q,[{message_id:'m1'}]).tool_result.data.items[0].category,'OTHER');
  const bad=parseReviewRequest({chatInput:'bad'});assert.equal(returnReviews(bad,[]).tool_result.status,'invalid_request');
});
