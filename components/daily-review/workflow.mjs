import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const library = fs.readFileSync(path.join(directory, 'review.mjs'), 'utf8').replace(/^export /gm, '');
const clone = x => JSON.parse(JSON.stringify(x));
const requiredNode = (w, name) => { const n = w.nodes.find(x => x.name === name); if (!n) throw new Error('Missing baseline node: ' + name); return n; };
const code = (name, jsCode) => ({ name, type: 'n8n-nodes-base.code', typeVersion: 2, parameters: { mode: 'runOnceForAllItems', language: 'javaScript', jsCode }, position: [0, 0] });
const edge = (source, target, sourceIndex = 0) => ({ source, target, sourceIndex, targetIndex: 0, connectionType: 'main' });

// Updates Daily Review only. The email push workflow is outside this generator.
export function dailyOperations(daily, { time = null, timezone = daily.settings?.timezone || 'Australia/Brisbane' } = {}) {
  if (time !== null && !/^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(time)) throw new Error('Daily time must be HH:MM');
  new Intl.DateTimeFormat('en', { timeZone: timezone }).format();
  const operations = [], links = [];
  const set = (name, parameters) => operations.push({ type: 'updateNodeParameters', nodeName: name, parameters });
  const connect = (a, b, index = 0) => links.push(edge(a, b, index));
  const workTable = requiredNode(daily, 'Read pending work').parameters.dataTableId;
  const condition = (keyName, keyValue) => ({ keyName, condition: 'eq', keyValue });
  const tableParams = filters => ({ resource: 'row', operation: 'get', dataTableId: workTable, matchType: 'allConditions',
    filters: { conditions: filters }, returnAll: false, limit: 1, orderBy: true, orderByColumn: 'updatedAt', orderByDirection: 'DESC' });
  for (const [source, channels] of Object.entries(daily.connections)) for (const [connectionType, outputs] of Object.entries(channels))
    for (let i = 0; i < outputs.length; i++) for (const c of outputs[i] ?? [])
      operations.push({ type: 'removeConnection', source, target: c.node, sourceIndex: i, targetIndex: c.index, connectionType });
  const renamed = {
    'Weekdays at 8am Brisbane': 'Daily preparation time',
    'Prepare scheduled digest': 'Prepare daily collection',
    'Read previous daily digest': 'Read last complete snapshot',
    'Build daily priorities': 'Collect daily review data',
    'Record daily digest': 'Save daily review snapshot',
    'Return spoken priorities': 'Return saved daily review'
  };
  for (const [oldName, newName] of Object.entries(renamed)) if (daily.nodes.some(n => n.name === oldName))
    operations.push({ type: 'renameNode', oldName, newName });
  for (const name of ['Digest request context', 'Analyse daily briefing', 'Validate and format daily review', 'Route digest output', 'One digest per day', 'Create daily digest draft'])
    if (daily.nodes.some(n => n.name === name)) operations.push({ type: 'removeNode', nodeName: name });
  const previousSchedule = daily.nodes.find(n => n.type === 'n8n-nodes-base.scheduleTrigger');
  const oldTime = previousSchedule.parameters.rule.interval[0];
  const [hour, minute] = time ? time.split(':').map(Number) : [oldTime.triggerAtHour ?? 8, oldTime.triggerAtMinute ?? 0];
  set('Daily preparation time', { rule: { interval: [{ field: 'days', daysInterval: 1, triggerAtHour: hour, triggerAtMinute: minute }] } });
  operations.push({ type: 'setNodeDisabled', nodeName: 'Daily preparation time', disabled: time === null });
  set('Prepare daily collection', code('', 'return [{json:{origin:"scheduled",timezone:$now.zoneName}}];').parameters);
  set('Parse agent request', code('', library + '\nreturn [{json:parseRequest($input.first().json)}];').parameters);
  set('Read last complete snapshot', tableParams([condition('workflow', 'daily_review'), condition('status', 'DONE')]));
  set('Review collection window', code('', library + '\nreturn [{json:reviewWindow($("Prepare daily collection").first().json,$input.first().json,$now.toISO())}];').parameters);
  const work = clone(requiredNode(daily, 'Read pending work').parameters);
  if (!work.filters.conditions.some(c => c.keyValue === 'daily_review')) work.filters.conditions.push({ keyName: 'workflow', condition: 'neq', keyValue: 'daily_review' });
  set('Read pending work', work);
  const sourceNames = { incoming: 'Read incoming email', spam: 'Check recent spam', sent: 'Read recent sent context', drafts: 'Read existing reply drafts', work: 'Read pending work', reviews: 'Read pending email review', organisation: 'Read organisation receipts', calendar: 'Read connected calendar' };
  set('Collect daily review data', code('', library + '\nconst sources={' + Object.entries(sourceNames).map(([k, n]) => JSON.stringify(k) + ':$(' + JSON.stringify(n) + ').all().map(x=>x.json)').join(',') + '};\nreturn [{json:collectSnapshot($("Review collection window").first().json,sources)}];').parameters);
  const ensure = n => daily.nodes.some(x => x.name === n.name) ? set(n.name, n.parameters) : operations.push({ type: 'addNode', node: n });
  ensure(code('Prepare snapshot record', library + '\nreturn [{json:snapshotRecord($input.first().json,String($execution.id),$now.toISO())}];'));
  const fields = ['record_key','workflow','status','title','summary','next_action','due_at','contact_email','raw_input','result_json','draft_id'];
  set('Save daily review snapshot', { resource: 'row', operation: 'upsert', dataTableId: workTable, matchType: 'allConditions', filters: { conditions: [condition('record_key', '={{ $json.record_key }}')] },
    columns: { mappingMode: 'defineBelow', value: Object.fromEntries(fields.map(k => [k, '={{ $json.' + k + ' }}'])) }, options: {} });
  ensure({ name: 'Read latest prepared snapshot', type: 'n8n-nodes-base.dataTable', typeVersion: 1.1, parameters: tableParams([condition('workflow', 'daily_review')]), position: [0,0] });
  ensure(code('Resolve saved daily review', library + '\nreturn [{json:retrieveSnapshot($("Parse agent request").first().json,$input.first().json,$now.toISO())}];'));
  set('Return saved daily review', code('', 'const x=$input.first().json;return [{json:x.agent_result??x}];').parameters);
  const triggerNote = time ? 'Every day at ' + time + ' (' + timezone + '), once published.' : 'Daily time awaits user selection; schedule trigger disabled.';
  set('Sticky Note df7005a8', { content: '## Daily Review — prepare, save, retrieve\n' + triggerNote + '\nScheduled/manual runs collect bounded source data and save a Workbench snapshot. No AI analysis, Gmail digest creation or user delivery.\nHermes get_daily_review/get_priorities reads the latest saved snapshot only and owns priorities, decisions, meeting prep, possible commitments, wording and speech.\nCoverage, partial results and timestamps stay with the snapshot. Each execution has its own save key; partial runs never replace the last complete checkpoint.\nCalendar daily_review_context must be published before daily collection is enabled. Email push workflow is unchanged.', width: 1250, height: 440 });
  connect('Run manually', 'Prepare daily collection'); connect('Daily preparation time', 'Prepare daily collection');
  const chain = ['Prepare daily collection','Read last complete snapshot','Review collection window','Read pending work','Read pending email review','Read incoming email','Check recent spam','Read recent sent context','Read existing reply drafts','Read organisation receipts','Prepare connected calendar read','Read connected calendar','Collect daily review data','Prepare snapshot record','Save daily review snapshot'];
  for (let i = 0; i < chain.length - 1; i++) connect(chain[i], chain[i+1]);
  connect('Agent request','Parse agent request'); connect('Parse agent request','Route priority request');
  connect('Route priority request','Return saved daily review'); connect('Route priority request','Read latest prepared snapshot',1);
  connect('Read latest prepared snapshot','Resolve saved daily review'); connect('Resolve saved daily review','Return saved daily review');
  operations.push({ type: 'setNodeSettings', nodeName: 'Read latest prepared snapshot', settings: { alwaysOutputData: true, executeOnce: true, onError: 'continueRegularOutput' } });
  links.forEach(link => operations.push({ type: 'addConnection', ...link }));
  chain.forEach((name,i)=>operations.push({ type:'setNodePosition',nodeName:name,position:[i*280,300] }));
  const positions = { 'Run manually': [-300,200], 'Daily preparation time': [-300,400], 'Agent request': [-300,-180], 'Parse agent request': [0,-180], 'Route priority request': [280,-180], 'Read latest prepared snapshot': [560,-100], 'Resolve saved daily review': [840,-100], 'Return saved daily review': [1120,-180], 'Sticky Note df7005a8': [-300,650] };
  for (const [nodeName,position] of Object.entries(positions)) operations.push({type:'setNodePosition',nodeName,position});
  operations.push({ type: 'setNodeGroups', nodeGroups: [
    { name:'Prepare daily source snapshot', description:'Read connected sources and save data for later Hermes retrieval.', nodeNames:chain },
    { name:'Retrieve saved review', description:'Validate the request and return the most recently prepared snapshot without rescanning connected sources.', nodeNames:['Parse agent request','Route priority request','Read latest prepared snapshot','Resolve saved daily review','Return saved daily review'] }
  ] });
  operations.push({ type:'setWorkflowSettings',settings:{timezone,executionTimeout:300} },
    { type:'setWorkflowMetadata',description:'Daily source preparation at a user-selected time. Saves email, drafts, organisation receipts, Workbench and connected calendar data. Hermes retrieves a saved snapshot and owns the review output; no scheduled digest or message delivery.' });
  return operations;
}

export const EMPTY_CONFIGURATION = { schema_version: 1, configuration_id: 'unconfigured', mode: 'setup_required', time: null, timezone: null,
  sources: { email: false, workbench: false, calendar: false, reviews: false, organisation: false }, labels: {} };

export function onboardingOperations(daily) {
  const operations = [], links = [];
  const set = (nodeName, parameters) => operations.push({type:'updateNodeParameters',nodeName,parameters});
  const ensure = n => daily.nodes.some(x=>x.name===n.name) ? set(n.name,n.parameters) : operations.push({type:'addNode',node:n});
  const connect = (a,b,index=0) => links.push(edge(a,b,index));
  for (const [source,channels] of Object.entries(daily.connections)) for (const [connectionType,outputs] of Object.entries(channels))
    for(let i=0;i<outputs.length;i++) for(const c of outputs[i]??[]) operations.push({type:'removeConnection',source,target:c.node,sourceIndex:i,targetIndex:c.index,connectionType});
  if(daily.nodes.some(n=>n.name==='Prepare daily collection')) operations.push({type:'removeNode',nodeName:'Prepare daily collection'});
  if(!daily.nodes.some(n=>n.name==='Review configuration')) {
    ensure({name:'Review configuration',type:'n8n-nodes-base.set',typeVersion:3.4,position:[0,0],parameters:{mode:'raw',jsonOutput:JSON.stringify({review_config:EMPTY_CONFIGURATION}),includeOtherFields:true,options:{}}});
    operations.push({type:'setNodeDisabled',nodeName:'Daily preparation time',disabled:true});
  }
  set('Parse agent request',code('',library+'\nreturn [{json:$("Agent request").isExecuted?parseRequest($input.first().json):{origin:"scheduled",manual:$execution.mode==="manual"}}];').parameters);
  ensure(code('Check review setup',library+'\nreturn [{json:checkSetup($input.first().json)}];'));
  set('Route priority request',{mode:'expression',numberOutputs:3,output:'={{ $json.agent_result ? 0 : $json.origin === "agent" ? 1 : 2 }}'});
  set('Review collection window',code('',library+'\nreturn [{json:reviewWindow($("Check review setup").first().json,$input.first().json,$now.toISO())}];').parameters);
  const sourceNames={incoming:'Read incoming email',spam:'Check recent spam',sent:'Read recent sent context',drafts:'Read existing reply drafts',work:'Read pending work',reviews:'Read pending email review',organisation:'Read organisation receipts',calendar:'Read connected calendar'};
  set('Collect daily review data',code('',library+'\nconst read=n=>$(n).isExecuted?$(n).all().map(x=>x.json):null;const sources={'+Object.entries(sourceNames).map(([k,n])=>JSON.stringify(k)+':read('+JSON.stringify(n)+')').join(',')+'};return [{json:collectSnapshot($("Review collection window").first().json,sources)}];').parameters);
  set('Prepare snapshot record',code('',library+'\nreturn [{json:snapshotRecord($input.first().json,String($execution.id),$now.toISO())}];').parameters);
  set('Resolve saved daily review',code('',library+'\nreturn [{json:retrieveSnapshot($("Check review setup").first().json,$input.first().json,$now.toISO())}];').parameters);
  for(const nodeName of ['Read last complete snapshot','Read latest prepared snapshot']) {
    const p=clone(requiredNode(daily,nodeName).parameters);
    p.filters.conditions=p.filters.conditions.filter(c=>c.keyName!=='raw_input');
    p.filters.conditions.push({keyName:'raw_input',condition:'eq',keyValue:'={{ $("Check review setup").first().json.configuration_id }}'});
    set(nodeName,p);
  }
  for(const [key,label] of Object.entries({workbench:'work',email:'email',reviews:'saved email reviews',organisation:'organisation receipts',calendar:'calendar'}))
    ensure({name:'Include '+label+'?',type:'n8n-nodes-base.switch',typeVersion:3.4,position:[0,0],parameters:{mode:'expression',numberOutputs:2,output:'={{ $("Check review setup").first().json.sources.'+key+' ? 0 : 1 }}'}});
  for(const trigger of ['Run manually','Daily preparation time','Agent request']) connect(trigger,'Parse agent request');
  connect('Parse agent request','Review configuration');connect('Review configuration','Check review setup');connect('Check review setup','Route priority request');
  connect('Route priority request','Return saved daily review');connect('Route priority request','Read latest prepared snapshot',1);connect('Route priority request','Read last complete snapshot',2);
  connect('Read latest prepared snapshot','Resolve saved daily review');connect('Resolve saved daily review','Return saved daily review');
  connect('Read last complete snapshot','Review collection window');connect('Review collection window','Include work?');
  connect('Include work?','Read pending work');connect('Include work?','Include email?',1);connect('Read pending work','Include email?');
  connect('Include email?','Read incoming email');connect('Include email?','Include saved email reviews?',1);
  connect('Read incoming email','Check recent spam');connect('Check recent spam','Read recent sent context');connect('Read recent sent context','Read existing reply drafts');connect('Read existing reply drafts','Include saved email reviews?');
  connect('Include saved email reviews?','Read pending email review');connect('Include saved email reviews?','Include organisation receipts?',1);connect('Read pending email review','Include organisation receipts?');
  connect('Include organisation receipts?','Read organisation receipts');connect('Include organisation receipts?','Include calendar?',1);connect('Read organisation receipts','Include calendar?');
  connect('Include calendar?','Prepare connected calendar read');connect('Include calendar?','Collect daily review data',1);connect('Prepare connected calendar read','Read connected calendar');connect('Read connected calendar','Collect daily review data');
  connect('Collect daily review data','Prepare snapshot record');connect('Prepare snapshot record','Save daily review snapshot');
  links.forEach(e=>operations.push({type:'addConnection',...e}));
  const setup=['Parse agent request','Review configuration','Check review setup','Route priority request'];
  const collection=['Read last complete snapshot','Review collection window','Include work?','Read pending work','Include email?','Read incoming email','Check recent spam','Read recent sent context','Read existing reply drafts','Include saved email reviews?','Read pending email review','Include organisation receipts?','Read organisation receipts','Include calendar?','Prepare connected calendar read','Read connected calendar','Collect daily review data','Prepare snapshot record','Save daily review snapshot'];
  setup.forEach((nodeName,i)=>operations.push({type:'setNodePosition',nodeName,position:[i*280,0]}));
  collection.forEach((nodeName,i)=>operations.push({type:'setNodePosition',nodeName,position:[1200+i*250,350]}));
  for(const [nodeName,position] of Object.entries({'Run manually':[-350,-100],'Daily preparation time':[-350,100],'Agent request':[-350,300],'Read latest prepared snapshot':[1200,-180],'Resolve saved daily review':[1480,-180],'Return saved daily review':[1760,0],'Sticky Note df7005a8':[-350,700]})) operations.push({type:'setNodePosition',nodeName,position});
  operations.push({type:'setNodeGroups',nodeGroups:[
    {name:'Setup and request',description:'Setup is deferred to Hermes. Validate the selected settings before any provider or storage read.',nodeNames:setup},
    {name:'Collect selected sources',description:'Skip unselected sources and save a snapshot scoped to the current configuration.',nodeNames:collection},
    {name:'Retrieve prepared data',description:'Retrieve only a snapshot belonging to the selected accounts, resources and routing.',nodeNames:['Read latest prepared snapshot','Resolve saved daily review']}
  ]});
  set('Sticky Note df7005a8',{content:'## Daily Review — deferred user setup\nInstall and integrate first; users connect accounts, select linked resources/routes and choose their daily time later through Hermes.\nThe profile settings helper plans account, resource and schedule changes. Review configuration is the applied runtime configuration; no access occurs while setup is required.\nUnselected sources are skipped. Snapshots and checkpoints are isolated by configuration ID, so switching email/calendar does not expose the previous setup’s recap.\nPreview and verify new bindings before activation. No scheduled briefing generation or delivery.\nThe separate email push workflow is unchanged. Changing its mailbox later also requires its own watch/intake setup, not just a new credential.',width:1200,height:440});
  operations.push({type:'setWorkflowMetadata',description:'Daily Review with deferred Hermes onboarding, editable account/resource/routing bindings, optional sources and user-selected scheduling. Collects source data only; Hermes retrieves a configuration-scoped snapshot and presents the recap.'});
  return operations;
}

export function applyOperations(base, operations) {
  const w = clone(base);
  for (const op of operations) {
    if (op.type === 'addNode') w.nodes.push(clone(op.node));
    else if (op.type === 'renameNode') requiredNode(w, op.oldName).name = op.newName;
    else if (op.type === 'setNodeDisabled') requiredNode(w, op.nodeName).disabled = op.disabled;
    else if (op.type === 'setNodeCredential') { const n=requiredNode(w,op.nodeName); n.credentials??={}; n.credentials[op.credentialKey]={id:op.credentialId,name:op.credentialName}; }
    else if (op.type === 'removeNode') w.nodes = w.nodes.filter(n => n.name !== op.nodeName);
    else if (op.type === 'updateNodeParameters') requiredNode(w, op.nodeName).parameters = clone(op.parameters);
    else if (op.type === 'setNodeParameter') requiredNode(w, op.nodeName).parameters[op.path] = op.value;
    else if (op.type === 'setNodeSettings') Object.assign(requiredNode(w, op.nodeName), op.settings);
    else if (op.type === 'setNodePosition') requiredNode(w, op.nodeName).position = op.position;
    else if (op.type === 'setWorkflowSettings') Object.assign(w.settings, op.settings);
    else if (op.type === 'setWorkflowMetadata') w.description = op.description;
    else if (op.type === 'setNodeGroups') w.nodeGroups = clone(op.nodeGroups);
    else if (op.type === 'removeConnection') {
      const edges = w.connections[op.source]?.[op.connectionType]?.[op.sourceIndex];
      if (edges) w.connections[op.source][op.connectionType][op.sourceIndex] = edges.filter(c => !(c.node === op.target && c.index === op.targetIndex));
    } else if (op.type === 'addConnection') {
      w.connections[op.source] ??= {}; w.connections[op.source][op.connectionType] ??= [];
      w.connections[op.source][op.connectionType][op.sourceIndex] ??= [];
      w.connections[op.source][op.connectionType][op.sourceIndex].push({ node: op.target, type: op.connectionType, index: op.targetIndex });
    }
  }
  return w;
}

export function sdkCode(w) {
  const vars = new Map(w.nodes.map((n, i) => [n.name, 'step' + i]));
  const encode = v => typeof v === 'string' && v.startsWith('=') && v.includes('{{') ? 'expr(' + JSON.stringify(v.slice(1)) + ')' : Array.isArray(v) ? '[' + v.map(encode).join(',') + ']' : v && typeof v === 'object' ? '{' + Object.entries(v).map(([k, value]) => JSON.stringify(k) + ':' + encode(value)).join(',') + '}' : JSON.stringify(v);
  let s = "import {workflow,node,trigger,expr} from '@n8n/workflow-sdk';\n";
  for (const n of w.nodes) {
    const config = Object.fromEntries(['name', 'parameters', 'position', 'credentials', 'disabled', 'alwaysOutputData', 'executeOnce', 'onError', 'retryOnFail', 'maxTries', 'waitBetweenTries'].filter(k => n[k] !== undefined).map(k => [k, n[k]]));
    s += 'const ' + vars.get(n.name) + '=' + (/Trigger$|\.chatTrigger$/.test(n.type) ? 'trigger' : 'node') + '(' + encode({ type: n.type, version: n.typeVersion, config, output: [{ json: {} }] }) + ');\n';
  }
  s += 'export default workflow(' + JSON.stringify(w.id) + ',' + JSON.stringify(w.name) + ')';
  for (const n of w.nodes) s += '\n.add(' + vars.get(n.name) + ')';
  for (const [source, channels] of Object.entries(w.connections)) for (const [channel, outputs] of Object.entries(channels)) {
    if (channel !== 'main') throw new Error('Unexpected subnode connection; preserve through the SDK before updating');
    for (let i = 0; i < outputs.length; i++) for (const c of outputs[i] ?? []) s += '\n.add(' + vars.get(source) + '.output(' + i + ').to(' + vars.get(c.node) + '.input(' + c.index + ')))';
  }
  for (const group of w.nodeGroups ?? []) s += '\n.group(' + JSON.stringify(group.name) + ',[' + group.nodeNames.map(n => vars.get(n)).join(',') + '],{description:' + JSON.stringify(group.description || '') + '})';
  return s + ';\n';
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [baselineDir, outputDir, time, timezone] = process.argv.slice(2);
  if (!baselineDir || !outputDir) throw new Error('Usage: node workflow.mjs <private-baseline-directory> <ignored-output-directory>');
  const baseline = JSON.parse(fs.readFileSync(path.join(baselineDir, 'daily.json'), 'utf8'));
  const operations = baseline.nodes.some(n=>n.name==='Prepare snapshot record') ? [] : dailyOperations(baseline);
  const prepared = applyOperations(baseline, operations);
  operations.push(...onboardingOperations(prepared));
  if(time || timezone) throw new Error('Choose accounts, resources and time later with the installed Hermes settings helper.');
  const updated = applyOperations(baseline, operations);
  fs.mkdirSync(outputDir, {recursive:true});
  fs.writeFileSync(path.join(outputDir,'daily-operations.json'),JSON.stringify(operations,null,2));
  fs.writeFileSync(path.join(outputDir,'daily-workflow.json'),JSON.stringify(updated,null,2));
  fs.writeFileSync(path.join(outputDir,'daily-sdk.js'),sdkCode(updated));
}
