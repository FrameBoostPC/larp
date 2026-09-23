function canonical(value){
  if(Array.isArray(value))return value.map(canonical);
  if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])]));
  return value;
}
function envelope(meta,status,spoken,data=null,extra={}){
  return {output:spoken,tool_result:{schema_version:'1.0',request_id:meta?.request_id??null,session_id:meta?.session_id??null,revision:meta?.revision??null,status,spoken_summary:spoken,data,...extra}};
}
const clone=v=>JSON.parse(JSON.stringify(v));
function parseAgent(input,domain){
  const object=x=>x&&typeof x==='object'&&!Array.isArray(x);
  let v;
  try {v=typeof input.chatInput==='string'?JSON.parse(input.chatInput):null;}catch{}
  const fail=(status,message,extra={})=>({agent:v,agent_result:envelope(v,status,message,null,extra)});
  if(!object(v)||JSON.stringify(v).length>20000)return fail('invalid_request','The request could not be read. Please try again.');
  if(Object.keys(v).some(k=>!['request_id','session_id','revision','action','arguments'].includes(k))||
     typeof v.request_id!=='string'||!/^[a-z0-9][a-z0-9_.-]{1,69}$/.test(v.request_id)||
     typeof v.session_id!=='string'||!/^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,119}$/.test(v.session_id)||
     !Number.isSafeInteger(v.revision)||v.revision<0||!object(v.arguments))
    return fail('invalid_request','The agent request is missing valid tracking information.');
  const a=clone(v.arguments);
  const missing=[];
  if(domain==='planner'){
    if(v.action!=='plan_project')return fail('invalid_request','That planning action is not supported.');
    const allowed=['project_reference','week_start','goal','backlog','constraints','planning_style','horizon_weeks','mode','hours_available','work_days','work_start','work_end','buffer_minutes','reserve_percent'];
    if(Object.keys(a).some(k=>!allowed.includes(k)))return fail('invalid_request','The planning request contains unsupported fields.');
    if(!a.project_reference)missing.push('project_reference');
    if(!a.goal)missing.push('goal');
    if(!a.week_start)missing.push('week_start');
    if(missing.length)return fail('needs_input',!a.goal?'What would you like to achieve?':!a.week_start?'When should the plan start?':'Which project is this for?',{missing_fields:missing});
    if(a.planning_style==='Detailed time planning'){
      for(const key of ['work_days','work_start','work_end'])if(!a[key]||Array.isArray(a[key])&&!a[key].length)missing.push(key);
      if(missing.length)return fail('needs_input','Which days and times can you usually work on this?',{missing_fields:missing});
    }
    a.reference=v.request_id;
    a.backlog=a.backlog||'Derive the necessary tasks from the goal. State any assumptions.';
    a.planning_style=a.planning_style||'Broad timeline';
    a.horizon_weeks=a.horizon_weeks??4;
    a.mode=a.mode||'Draft only';
    return {origin:'agent',agent:v,submitted_form:a,detail_preferences:a};
  }
  const supported=['list_schedule','list_tasks','find_slots','check_slot','project_context','create','update','complete','archive'];
  if(!supported.includes(v.action))return fail('invalid_request','That calendar action is not supported.');
  const allowed=['project_reference','page_id','title','notes','kind','status','colour','blocks_time','due_date','start','end','window_start','window_end','from_date','to_date','duration_minutes','day_start','day_end','include_weekends','buffer_minutes','max_slots','expected_state','replace_date','clear_time','query'];
  if(Object.keys(a).some(k=>!allowed.includes(k)))return fail('invalid_request','The calendar request contains unsupported fields.');
  if(a.query!==undefined&&(v.action!=='list_tasks'||typeof a.query!=='string'||!a.query.trim()||a.query.length>200))return fail('invalid_request','Task search needs a name of 1–200 characters and the list_tasks action.');
  if(['update','complete','archive'].includes(v.action)&&!a.page_id)return fail('needs_input','Which task or event do you mean?',{missing_fields:['page_id']});
  if(['update','complete','archive'].includes(v.action)&&(typeof a.expected_state!=='string'||!a.expected_state.startsWith('state-v1:')||a.expected_state.length>12000))return fail('refresh_required','I need to refresh that item before changing it.',{missing_fields:['expected_state']});
  if(a.replace_date!==undefined&&typeof a.replace_date!=='boolean')return fail('invalid_request','The date replacement choice must be true or false.');
  if(a.start&&!a.end||a.end&&!a.start)return fail('needs_input','When should that time block start and finish?',{missing_fields:[a.start?'end':'start']});
  if(v.action==='create'&&!a.title)return fail('needs_input','What should I call it?',{missing_fields:['title']});
  const mutation=['create','update','complete','archive'].includes(v.action);
  const raw={...a,action:v.action,...(v.action==='create'?{reference:'voice-'+v.request_id}:{})};
  return {origin:'agent',agent:v,raw,mutation,record_key:'voice:schedule:'+v.request_id,input_signature:JSON.stringify(canonical(v))};
}
const v=parseAgent($input.first().json,"schedule");v.execution_id=String($execution.id);return [{json:v}];
