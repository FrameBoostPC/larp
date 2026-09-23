import fs from 'node:fs';
import assert from 'node:assert/strict';
const [beforePath, afterPath, outputPath] = process.argv.slice(2);
if (!beforePath || !afterPath || !outputPath) throw new Error('Usage: node acceptance.mjs <private before.json> <private candidate.json> <private cloud-code.txt>');
const original=JSON.parse(fs.readFileSync(beforePath));const before=original.workflow || original;
const after=JSON.parse(fs.readFileSync(afterPath));
const changed=new Set(['Generate structured result','Check draft decision','Prepare label request','Label source email','Parse agent request','Read requested email reviews','Return email reviews']);
assert.deepEqual(before.connections,after.connections);
assert.deepEqual(before.settings,after.settings);
assert.deepEqual(before.nodeGroups,after.nodeGroups);
for(const n of before.nodes){const a=after.nodes.find(x=>x.id===n.id);assert.ok(a);assert.deepEqual(n.credentials,a.credentials);if(!changed.has(n.name))assert.deepEqual(n,a);}
const code=name=>after.nodes.find(n=>n.name===name).parameters.jsCode;
const cloud = `function decide($json,$,$now){${code('Check draft decision')}}
function label($input){${code('Prepare label request')}}
function receipt($json,$){${code('Confirm email organisation receipt')}}
function parse($input){${code('Parse agent request')}}
function reviews($input,$,$now){${code('Return email reviews')}}
const now='2026-09-23T00:00:00Z';
const source={message_id:'synthetic-test',thread_id:'synthetic-thread',sender:'sender@example.com',reply_to:'sender@example.com',subject:'An update',body:'Thanks for the update.',received_at:now,processed_at:now,timezone:'Australia/Brisbane',automated:false,force_review:false};
const meeting={requested:false,date_text:'',time_text:'',duration_text:'',timezone_text:'',location_text:'',reply_tone:'neutral'};
const base={category:'PERSONAL',priority:'normal',disposition:'DRAFT',confidence:0.95,summary:'A short update.',reason:'Clear request',draft_body:'Thanks for the update.',meeting};
function run(result,src=source){return decide({status:'completed',output:[{content:[{type:'output_text',text:JSON.stringify(result)}]}]},()=>({item:{json:src}}),{toISO:()=>now}).json;}
let checks=0;function check(ok,message){if(!ok)throw new Error(message);checks++;}
for(const category of ${JSON.stringify(['ACTION','MEETING','FINANCE','NEWSLETTER','NOTIFICATION','PERSONAL','OTHER','PROMOTION','SOCIAL','SALES','RECRUITMENT','RECEIPT'])}) {
 const out=run({...base,category,disposition:'REVIEW'},{...source,automated:true});check(out.status==='REVIEW'&&!out.draft_body,'Automated review preserved '+category);
 const low=run({...base,category,confidence:0.5,disposition:'FILE'});check(low.status==='REVIEW'&&!low.draft_body,'Low confidence review '+category);
 const status=['ACTION','MEETING','PERSONAL','SALES'].includes(category)?'DRAFT':['FINANCE','OTHER','RECRUITMENT'].includes(category)?'REVIEW':'FILE';
 const regular=run({...base,category});check(regular.status===status,'Category policy '+category);
 const src={...regular,status:regular.status==='DRAFT'?'DRAFT_CREATED':regular.status,draft_id:regular.status==='DRAFT'?'synthetic-draft':''};
 const prepared=label({first:()=>({json:src})})[0].json;check(prepared.label_names.some(x=>x==='Automation/'+category[0]+category.slice(1).toLowerCase()),'Category label '+category);
 const record=receipt({id:src.message_id,labelIds:prepared.label_ids},()=>({item:{json:prepared}})).json;check(JSON.parse(record.result_json).confirmed===true,'Receipt '+category);
}
check(run({...base,category:'SALES',draft_body:'Our course includes everything and costs $999.'}).status==='REVIEW','Ungrounded business promise');
const clash=label({first:()=>({json:{...source,category:'MEETING',status:'DRAFT_CREATED',draft_id:'synthetic-draft',time_clash:true}})})[0].json;check(clash.label_ids.length===4&&clash.label_names.includes('clash'),'Four labels preserved');
let rejected=false;try{receipt({id:source.message_id,labelIds:clash.label_ids.slice(0,3)},()=>({item:{json:clash}}));}catch{rejected=true;}check(rejected,'Missing clash receipt rejected');
const input={chatInput:JSON.stringify({request_id:'acceptance-01',session_id:'acceptance',revision:1,action:'list_reviews',arguments:{category:'SOCIAL',status:'FILE',limit:1}})};
const parsed=parse({first:()=>({json:input})})[0].json;check(parsed.raw.category==='SOCIAL','Filter parsed');
const returned=reviews({all:()=>[{json:{...source,category:'SOCIAL',status:'FILE'}}]},()=>({first:()=>({json:parsed})}),{toISO:()=>now})[0].json.tool_result;
check(returned.data.items[0].category==='SOCIAL'&&returned.data.counts_scope==='returned_items'&&returned.data.live_inbox_checked===false,'Saved category summary');
return [{json:{checks,passed:true,model_calls:0,mailbox_writes:0}}];`;
const result=Function(cloud)();assert.equal(result[0].json.passed,true);
fs.writeFileSync(outputPath,cloud);
console.log(JSON.stringify({preserved_graph:true,...result[0].json}));
