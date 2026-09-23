function stateToken(r){
  return 'state-v1:'+JSON.stringify([String(r.page_id||r.id||'').replace(/-/g,'').toLowerCase(),r.title,r.type||r.kind,r.status,r.colour||'Default',r.start||null,r.end||null,r.due_date||null,Boolean(r.blocks_time),r.reference||'',r.notes||'',r.last_edited_time||null]);
}
const q=$("Validate scheduling request").first().json,cfg=q.settings,pn=cfg.properties,raw=$input.all().map(x=>x.json),norm=v=>String(v||"").replace(/-/g,"").toLowerCase();
const isCreate=["create","sync_task"].includes(q.action);
const nonempty=raw.filter(x=>Object.keys(x).length);if(nonempty.length>cfg.max_records)throw new Error("Schedule database exceeds "+cfg.max_records+" entries; refine the database before checking availability");
const rich=v=>(v||[]).map(x=>x.plain_text??x.text?.content??"").join("");
const localDay=v=>new Date(Date.parse(v)+36000000).toISOString().slice(0,10);
const dayMs=d=>Date.parse(d+"T00:00:00+10:00");
const records=nonempty.map(p=>{
if(p.object!=="page"||!p.id||!p.properties||norm(p.parent?.data_source_id)!==norm(cfg.data_source_id))throw new Error("Unexpected Notion schedule record");
const pr=p.properties;
for(const [role,type]of Object.entries({title:"title",when:"date",kind:"select",status:"select",blocks:"checkbox",notes:"rich_text",reference:"rich_text",colour:"select"}))if(pr[pn[role]]?.type!==type)throw new Error("Missing or wrong property on Notion schedule record");
const when=pr[pn.when].date,blocks=pr[pn.blocks].checkbox,status=pr[pn.status].select?.name||"Planned",kind=pr[pn.kind].select?.name||"Task";
if(!["Planned","In progress","Done","Cancelled"].includes(status)||!["Event","Task","Focus"].includes(kind))throw new Error("Unknown task type/status in Notion");
let start=null,end=null,due_date=null;
if(when?.start){const isDay=/^\d{4}-\d{2}-\d{2}$/.test(when.start);let a=isDay?dayMs(when.start):Date.parse(when.start);let b=isDay?dayMs(when.end||when.start)+86400000:Date.parse(when.end||"");
if(!Number.isFinite(a)||!Number.isFinite(b)||b<=a)throw new Error("An item has a missing or invalid end time: "+rich(pr[pn.title].title));
if(isDay&&kind==="Task"&&!blocks&&!when.end){due_date=when.start;}else{start=new Date(a).toISOString();end=new Date(b).toISOString();}}
if(blocks&&!start&&!["Done","Cancelled"].includes(status))throw new Error("A time-blocking item has no scheduled date: "+rich(pr[pn.title].title));
return {id:p.id,page_id:norm(p.id),url:p.url||"",title:rich(pr[pn.title].title),kind,status,colour:pr[pn.colour].select?.name||"Default",blocks_time:blocks,start,end,due_date,notes:rich(pr[pn.notes].rich_text),reference:rich(pr[pn.reference].rich_text),last_edited_time:p.last_edited_time||null,archived:p.archived===true||p.in_trash===true};
}).filter(x=>!x.archived);
const plannerMetadata=r=>{
 const prefix="Planner metadata: ";const candidates=r.notes.split("\n").filter(line=>line.startsWith(prefix));
 for(const line of candidates){try{const m=JSON.parse(line.slice(prefix.length));if("planner:"+m.project_reference+":"+m.task_key!==r.reference)continue;
 return {effort_hours:typeof m.effort_hours==="number"&&Number.isFinite(m.effort_hours)&&m.effort_hours>0&&m.effort_hours<=168?m.effort_hours:null,dependencies:Array.isArray(m.dependencies)&&m.dependencies.length<=30&&m.dependencies.every(x=>typeof x==="string"&&/^[a-z0-9][a-z0-9_-]{0,29}$/.test(x))?m.dependencies:[]};}catch{}}
 return {effort_hours:null,dependencies:[]};
};
const compact=r=>({page_id:r.id,url:r.url,title:r.title,type:r.kind,status:r.status,colour:r.colour||"Default",start:r.start,end:r.end,due_date:r.due_date||null,blocks_time:r.blocks_time,reference:r.reference,last_edited_time:r.last_edited_time,notes:r.notes,state_token:stateToken(r),...plannerMetadata(r)});
const base={api_version:1,action:q.action,timezone:q.timezone,checked_at:q.checked_at,scope:"selected_notion_database",external_calendars_checked:false,mutated:false,...(q.project_reference?{project_reference:q.project_reference}:{}),...(q.action==="sync_task"?{reference:q.request_reference}:{})};
const result=(status,extra={})=>[{json:{request:q,route:0,result:{...base,status,...extra}}}];
const active=records.filter(r=>r.blocks_time&&r.start&&!["Done","Cancelled"].includes(r.status));
const overlap=(a,b,r)=>Date.parse(r.start)<b&&Date.parse(r.end)>a;
if(q.action==="daily_review_context"){
 const a=Date.parse(q.window_start),b=Date.parse(q.window_end);
 const items=records.filter(r=>r.status!=="Cancelled"&&(r.due_date?dayMs(r.due_date)<b&&dayMs(r.due_date)+86400000>a:r.start&&overlap(a,b,r))).sort((a,b)=>(a.due_date||a.start).localeCompare(b.due_date||b.start));
 return result("OK",{window_start:q.window_start,window_end:q.window_end,items:items.map(compact),tasks:records.filter(r=>r.kind==="Task"&&!["Done","Cancelled"].includes(r.status)).map(compact),read_at:new Date().toISOString()});
}
if(q.action==="project_context"){
 const prefix="planner:"+q.project_reference+":";
 const items=records.filter(r=>r.reference.startsWith(prefix)&&/^[a-z0-9][a-z0-9_-]{0,29}$/.test(r.reference.slice(prefix.length)));
 const seen=new Set();for(const r of items){if(seen.has(r.reference))return result("REFERENCE_CONFLICT",{message:"Duplicate project task references need review before planning.",items:items.map(compact),busy:[]});seen.add(r.reference);}
 const a=q.window_start?Date.parse(q.window_start):null,b=q.window_end?Date.parse(q.window_end):null;
 return result("OK",{items:items.map(compact),busy:active.filter(r=>a===null||overlap(a,b,r)).map(compact),read_at:new Date().toISOString()});
}
if(q.action==="sync_task"){
 if(q.unsupported_date_combination)return result("UNSUPPORTED_DATE_COMBINATION",{message:"This Notion database has one When field. Choose a task due date or a scheduled interval; both cannot be saved together."});
 const matches=records.filter(r=>r.reference===q.request_reference);
 if(matches.length>1)return result("REFERENCE_CONFLICT",{message:"Duplicate managed task references need review before creating or changing anything.",items:matches.map(compact)});
 if(matches.length===1){if(matches[0].kind!=="Task"||(q.known_page_id&&norm(matches[0].id)!==q.known_page_id))return result("REFERENCE_CONFLICT",{message:"This project task reference belongs to an unexpected item.",item:compact(matches[0])});return result("ALREADY_EXISTS",{item:compact(matches[0])});}
 if(q.require_existing)return result("NOT_FOUND",{message:"The previously linked project task is no longer available in this Notion database. It was not recreated."});
 if(!q.title)throw new Error("A new project task needs a title");
}
if(q.action==="list_tasks"){
 const words=(q.query||"").normalize("NFKC").toLowerCase().split(/\s+/).filter(Boolean);
 const prefix=q.project_reference?"planner:"+q.project_reference+":":null;
 const items=records.filter(r=>r.kind==="Task"&&(q.status?r.status===q.status:!["Done","Cancelled"].includes(r.status))&&
  (!q.page_id||r.page_id===q.page_id)&&(!prefix||r.reference.startsWith(prefix))&&
  words.every(word=>r.title.normalize("NFKC").toLowerCase().includes(word)))
  .sort((a,b)=>(a.due_date||a.start||"z").localeCompare(b.due_date||b.start||"z")||a.title.localeCompare(b.title));
 return result("OK",{items:items.map(compact),filters:{query:q.query||null,status:q.status||"open",project_reference:q.project_reference||null,page_id:q.page_id||null},match_count:items.length,selection_required:items.length>1});
}
if(q.action==="list_schedule"){const a=Date.parse(q.window_start),b=Date.parse(q.window_end);return result("OK",{window_start:q.window_start,window_end:q.window_end,items:records.filter(r=>r.status!=="Cancelled"&&(r.due_date?dayMs(r.due_date)<b&&dayMs(r.due_date)+86400000>a:r.start&&overlap(a,b,r))).sort((a,b)=>(a.due_date||a.start).localeCompare(b.due_date||b.start)).map(compact)});}
if(["check_slot","find_slots"].includes(q.action)){
 const requestedStart=Date.parse(q.window_start),requestedEnd=Date.parse(q.window_end),now=Date.parse(q.checked_at);
 const buffer=q.buffer_minutes*60000;
 const busy=active.map(r=>({start:Date.parse(r.start)-buffer,end:Date.parse(r.end)+buffer}));
 const findSlots=(searchStart,searchEnd,duration,maxSlots)=>{
  const from=Math.max(searchStart,now),to=searchEnd,slots=[],length=duration*60000,step=15*60000;
  for(let d=dayMs(localDay(new Date(from).toISOString()));d<to&&slots.length<maxSlots;d+=86400000){
   const date=localDay(new Date(d).toISOString()),day=new Date(d+36000000).getUTCDay();
   if(!q.include_weekends&&(day===0||day===6))continue;
   const lo=Math.max(from,Date.parse(date+"T"+q.day_start+":00+10:00")),hi=Math.min(to,Date.parse(date+"T"+q.day_end+":00+10:00"));
   for(let a=Math.ceil(lo/step)*step;a+length<=hi&&slots.length<maxSlots;a+=step){
    if(busy.some(r=>r.start<a+length&&r.end>a))continue;
    slots.push({start:new Date(a).toISOString(),end:new Date(a+length).toISOString()});
    a+=Math.max(0,length-step);
   }
  }
  return slots;
 };
 if(q.action==="check_slot"){
  const available=requestedStart>=now&&!busy.some(r=>r.start<requestedEnd&&r.end>requestedStart);
  const sameDay=localDay(q.window_start)===localDay(new Date(requestedEnd-1).toISOString());
  const dayStart=dayMs(localDay(q.window_start)),duration=(requestedEnd-requestedStart)/60000;
  const alternatives=!available&&sameDay?findSlots(dayStart,dayStart+86400000,duration,2):[];
  return result(available?"AVAILABLE":"UNAVAILABLE",{available,window_start:q.window_start,window_end:q.window_end,
   alternatives,alternatives_scope:{date:localDay(q.window_start),day_start:q.day_start,day_end:q.day_end,
    duration_minutes:duration,buffer_minutes:q.buffer_minutes,include_weekends:q.include_weekends},
   alternatives_note:available?"The requested time is available.":!sameDay?"Automatic alternatives are limited to requests within one day.":
    alternatives.length?"Suggestions only; no time has been booked.":"No alternatives fit the same day and search preferences.",
   refresh_before_booking:true});
 }
 const slots=findSlots(requestedStart,requestedEnd,q.duration_minutes,q.max_slots);
 return result(slots.length?"OK":"NO_SLOTS",{window_start:q.window_start,window_end:q.window_end,duration_minutes:q.duration_minutes,slots});
}
let target=null;
if(!isCreate){target=records.find(r=>r.page_id===q.page_id);if(!target)return result("NOT_FOUND",{message:"That item was not found in the selected schedule database."});}
if(q.origin==="agent"&&target&&q.expected_state!==stateToken(target))return result("STALE_STATE",{message:"This item changed since it was selected. Review its current details before applying the correction.",item:compact(target)});
if(q.origin==="agent"&&target&&q.action==="update"&&!q.replace_date&&((target.due_date&&q.start)||(target.start&&q.due_date)))return result("DATE_REPLACEMENT_REQUIRED",{message:"This task has one date field. Should I replace its current deadline or booking?",item:compact(target)});
if(q.action==="archive")return [{json:{request:q,route:3,target_id:target.id,result:{...base,status:"ARCHIVED",item:compact(target)}}}];
if(q.action==="complete"&&target.kind!=="Task")return result("INVALID_ACTION",{message:"Only tasks can be marked complete."});
if(q.action==="complete"&&target.status==="Done")return result("UNCHANGED",{item:compact(target)});
let desired=isCreate?{title:q.title,kind:q.kind,status:q.status,colour:q.colour||"Default",notes:q.notes,blocks_time:q.blocks_time,start:q.start||null,end:q.end||null,due_date:q.due_date||null}: {...target};
const changed=new Set();
if(isCreate)["title","kind","status","notes","blocks_time","colour"].forEach(k=>changed.add(k));
if(q.action==="update"){for(const k of ["title","kind","status","notes","colour"])if(q["has_"+k]){desired[k]=q[k];changed.add(k);}if(q.blocks_time!==undefined){desired.blocks_time=q.blocks_time;changed.add("blocks_time");}}
if(q.start){desired.start=q.start;desired.end=q.end;desired.due_date=null;changed.add("when");}
if(q.due_date){
if(desired.kind!=="Task")throw new Error("Only tasks can have a due date; choose Type Task to convert this item");
desired.due_date=q.due_date;desired.start=null;desired.end=null;desired.blocks_time=false;changed.add("when");changed.add("blocks_time");
}
if(q.clear_time){desired.start=null;desired.end=null;desired.due_date=null;desired.blocks_time=false;changed.add("when");changed.add("blocks_time");}
if(desired.due_date&&(desired.kind!=="Task"||desired.blocks_time))throw new Error("A task deadline cannot reserve time or become an event without a scheduled start");
if(["Event","Focus"].includes(desired.kind)&&!desired.start)throw new Error("Events and focus blocks need a scheduled start and end");
if(q.action==="complete"){desired.status="Done";changed.add("status");}
if(desired.blocks_time&&!desired.start&&!["Done","Cancelled"].includes(desired.status))throw new Error("A reserved task needs a start and end time");
const signature=r=>JSON.stringify([r.title,r.kind,r.start,r.end,r.notes,r.blocks_time,r.status,...(r.due_date?[r.due_date]:[]),...(r.colour&&r.colour!=="Default"?[r.colour]:[])]);
const canonical=signature(desired);
const hash=text=>{let a=2166136261,b=3335557771;for(const x of text){a=Math.imul(a^x.charCodeAt(0),16777619)>>>0;b=Math.imul(b^x.charCodeAt(0),2246822519)>>>0;}return a.toString(16).padStart(8,"0")+b.toString(16).padStart(8,"0");};
const reference=q.request_reference||"schedule-"+hash(canonical);
if(isCreate){
const existing=records.find(r=>r.reference===reference);
if(existing){const same=signature(existing)===canonical;if(!same)throw new Error("This reference already belongs to a different request");return result("ALREADY_EXISTS",{item:compact(existing)});}
desired.reference=reference;
}
const checkConflict=isCreate||changed.has("when")||changed.has("blocks_time")||changed.has("status");
if(checkConflict&&desired.blocks_time&&desired.start&&!["Done","Cancelled"].includes(desired.status)){
const conflicts=active.filter(r=>r.id!==target?.id&&overlap(Date.parse(desired.start),Date.parse(desired.end),r));if(conflicts.length)return result("CONFLICT",{message:"This would overlap existing reserved time.",conflicts:conflicts.map(compact)});
}
const props=[];
if(changed.has("title")&&!isCreate)props.push({key:pn.title+"|title",title:desired.title});
if(changed.has("kind"))props.push({key:pn.kind+"|select",selectValue:desired.kind});
if(changed.has("colour"))props.push({key:pn.colour+"|select",selectValue:desired.colour});
if(changed.has("status"))props.push({key:pn.status+"|select",selectValue:desired.status});
if(changed.has("notes"))props.push({key:pn.notes+"|rich_text",textContent:desired.notes});
if(changed.has("blocks_time"))props.push({key:pn.blocks+"|checkbox",checkboxValue:desired.blocks_time});
if(changed.has("when"))props.push(desired.due_date?{key:pn.when+"|date",range:false,includeTime:false,date:desired.due_date,timezone:"Australia/Brisbane"}:{key:pn.when+"|date",range:true,includeTime:true,dateStart:desired.start,dateEnd:desired.end,timezone:"Australia/Brisbane"});
if(isCreate)props.push({key:pn.reference+"|rich_text",textContent:desired.reference});
return [{json:{request:q,route:isCreate?((q.start||q.due_date)?1:4):(changed.has("when")?2:5),target_id:target?.id||"",desired,write_properties:props,changed:[...changed],result:{...base,status:isCreate?"CREATED":q.action==="complete"?"COMPLETED":"UPDATED"}}}];
