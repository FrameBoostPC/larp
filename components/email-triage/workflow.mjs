import fs from 'node:fs';
import {CATEGORIES} from './triage.mjs';
const library = fs.readFileSync(new URL('./triage.mjs', import.meta.url), 'utf8').replace(/^export /gm,'');
const clone = value => JSON.parse(JSON.stringify(value));
const requireNode = (w,name) => { const n = w.nodes.find(n => n.name === name); if (!n) throw new Error('Missing baseline node: ' + name); return n; };
function replaceOnce(value, before, after) {
  if (!value.includes(before) || value.indexOf(before) !== value.lastIndexOf(before)) throw new Error('Baseline changed; inspect before applying email patch');
  return value.replace(before,after);
}
export function emailOperations(baseline, labels) {
  const operations = [];
  const set = (name,parameters) => operations.push({type:'updateNodeParameters',nodeName:name,parameters,replace:true});
  const parameters = name => clone(requireNode(baseline,name).parameters);
  const generator = parameters('Generate structured result');
  const schema = JSON.parse(generator.options.textFormat.textOptions.schema);
  schema.properties.category.enum = CATEGORIES;
  generator.options.textFormat.textOptions.schema = JSON.stringify(schema);
  generator.responses.values[0].content = replaceOnce(generator.responses.values[0].content,
    'Classify ACTION, MEETING, FINANCE, NEWSLETTER, NOTIFICATION, PERSONAL or OTHER;',
    'Classify ACTION, MEETING, FINANCE, NEWSLETTER, NOTIFICATION, PERSONAL, OTHER, PROMOTION, SOCIAL, SALES, RECRUITMENT or RECEIPT;');
  generator.responses.values[0].content += '\nCategory boundaries: SALES means a potential/existing customer asking about the owner\'s offering, not someone advertising to the owner (PROMOTION). SOCIAL means routine platform activity notifications; a direct human request needs ACTION or PERSONAL instead. RECEIPT means a completed transaction confirmation; an invoice requiring action or financial question is FINANCE. RECRUITMENT covers applications and hiring correspondence and always needs REVIEW; do not evaluate candidates. NEWSLETTER is recurring editorial content, NOTIFICATION is other routine automated information, MEETING takes precedence for invitations, PERSONAL covers non-business human correspondence, ACTION covers remaining clear tasks, OTHER is a catch-all requiring REVIEW. Sensitive content always requires REVIEW regardless of category. Use FILE for routine promotions, social notifications and receipts; do not auto-mark read, send, forward, archive or delete. Summaries should preserve explicit requests and dates and say whether a response is needed, in at most two short sentences. No invented deadlines. Draft sales replies only using verified facts already supplied; unresolved business questions need the existing cautious draft or REVIEW.';
  set('Generate structured result',generator);
  const decision = parameters('Check draft decision');
  decision.jsCode = replaceOnce(decision.jsCode,"!['ACTION','MEETING','FINANCE','NEWSLETTER','NOTIFICATION','PERSONAL','OTHER'].includes(o.category)",'!CATEGORIES.includes(o.category)');
  const first = decision.jsCode.indexOf('  let status = o.disposition');
  const last = decision.jsCode.indexOf('  const meeting_context =',first);
  if (first < 0 || last < 0) throw new Error('Decision baseline changed');
  decision.jsCode = library + '\n' + decision.jsCode.slice(0,first) + '  let {status, reason, draft} = categoryPolicy(source, o);\n' + decision.jsCode.slice(last);
  set('Check draft decision',decision);
  set('Prepare label request',{mode:'runOnceForAllItems',jsCode:library + '\nreturn [{json:prepareLabels($input.first().json,' + JSON.stringify(labels) + '),pairedItem:{item:0}}];'});
  const labelNode = parameters('Label source email');
  labelNode.labelIds = [0,1,2,3].map(i => '={{ $("Prepare label request").item.json.label_ids[' + i + '] ?? $("Prepare label request").item.json.label_ids[0] }}');
  set('Label source email',labelNode);
  set('Parse agent request',{mode:'runOnceForAllItems',jsCode:library + '\nreturn [{json:parseReviewRequest($input.first().json)}];'});
  const read = parameters('Read requested email reviews');
  // With no optional filter, repeat the existing identity predicate rather than
  // excluding historical rows whose category/status may be empty.
  for (const key of ['category','status']) read.filters.conditions.push({keyName:'={{ $json.raw.' + key + ' ? "' + key + '" : "message_id" }}',condition:'={{ $json.raw.' + key + ' || $json.operation === "get_review" ? "eq" : "isNotEmpty" }}',keyValue:'={{ $json.raw.' + key + ' || $json.raw.message_id || "" }}'});
  read.orderByDirection = 'DESC';
  set('Read requested email reviews',read);
  set('Return email reviews',{mode:'runOnceForAllItems',jsCode:library + '\nreturn [{json:returnReviews($("Parse agent request").first().json,$input.all().map(x=>x.json))}];'});
  operations.push({type:'setWorkflowMetadata',description:'Gmail push triage with category labels, cautious reply drafts and calendar checks. Voice reads filter saved summaries by category/status. Durable duplicate protection; no sending, forwarding, marking read or deleting.'});
  return operations;
}

export function applyOperations(baseline,operations) {
  const w = clone(baseline);
  for (const op of operations) {
    if (op.type === 'updateNodeParameters') requireNode(w,op.nodeName).parameters = clone(op.parameters);
    else if (op.type === 'setWorkflowMetadata') w.description = op.description;
    else throw new Error('Unexpected operation');
  }
  return w;
}

export function workflowSdk(w) {
  const names = new Map(w.nodes.map((n,i)=>[n.name,'n'+i]));
  const encode = x => typeof x === 'string' && x.startsWith('=') && x.includes('{{') ? 'expr(' + JSON.stringify(x.slice(1)) + ')' : Array.isArray(x) ? '[' + x.map(encode).join(',') + ']' : x && typeof x === 'object' ? '{' + Object.entries(x).map(([k,v])=>JSON.stringify(k)+':'+encode(v)).join(',') + '}' : JSON.stringify(x);
  const lines = w.nodes.map(n => {
    const {type,typeVersion,...config} = n;
    const isTrigger = /Trigger$|\.webhook$/.test(type);
    return 'const '+names.get(n.name)+' = '+(isTrigger?'trigger':'node')+'({type:'+JSON.stringify(type)+',version:'+typeVersion+',config:'+encode(config)+',output:[{json:{}}]});';
  });
  let chain = 'export default workflow('+JSON.stringify(w.id)+','+JSON.stringify(w.name)+')';
  for (const n of w.nodes) chain += '.add('+names.get(n.name)+')';
  for (const [source,channels] of Object.entries(w.connections)) for (const [channel,outputs] of Object.entries(channels)) {
    if (channel !== 'main') throw new Error('Review SDK conversion for non-main connections');
    outputs.forEach((edges,index)=>edges.forEach(e=>{chain += '.add('+names.get(source)+'.output('+index+').to('+names.get(e.node)+'.input('+e.index+')))';}));
  }
  for (const g of w.nodeGroups || []) chain += '.group('+JSON.stringify(g.name)+',['+g.nodeNames.map(n=>names.get(n)).join(',')+'],{description:'+JSON.stringify(g.description || g.name)+'})';
  return lines.join('\n')+'\n'+chain+';';
}
