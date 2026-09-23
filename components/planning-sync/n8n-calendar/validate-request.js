function envelope(meta,status,spoken,data=null,extra={}){
  return {output:spoken,tool_result:{schema_version:'1.0',request_id:meta?.request_id??null,session_id:meta?.session_id??null,revision:meta?.revision??null,status,spoken_summary:spoken,data,...extra}};
}
const transport=$input.first().json;try{const value=(function(){
const input=$input.first().json,cfg=input.settings;
let s=input.raw||{};
const machineAction=s.action;
const isManaged=["project_context","sync_task"].includes(machineAction);
if(isManaged&&input.origin!=="workflow"&&!(input.origin==="agent"&&machineAction==="project_context"))throw new Error("Project integration actions require the workflow entry point");
if(isManaged){
 if(!s||typeof s!=="object"||Array.isArray(s))throw new Error("Invalid project integration request");
 if(typeof s.project_reference!=="string"||!/^[a-z0-9][a-z0-9_-]{0,39}$/.test(s.project_reference))throw new Error("Use a stable project reference of 1–40 lowercase letters, numbers, underscores or hyphens");
 if(machineAction==="sync_task"){
  if(typeof s.task_key!=="string"||!/^[a-z0-9][a-z0-9_-]{0,29}$/.test(s.task_key))throw new Error("Use a stable task key of 1–30 lowercase letters, numbers, underscores or hyphens");
  const managedReference="planner:"+s.project_reference+":"+s.task_key;
  if(s.page||s.page_id||(s.reference&&s.reference!==managedReference))throw new Error("sync_task can only create or read its computed project task reference");
  if(s.require_existing!==undefined&&typeof s.require_existing!=="boolean")throw new Error("require_existing must be true or false");
  if(s.known_page_id!==undefined&&(typeof s.known_page_id!=="string"||!/^(?:[a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$/i.test(s.known_page_id)))throw new Error("known_page_id must be a Notion page ID");
  if((s.kind&&s.kind!=="Task")||(s.status&&s.status!=="Planned"))throw new Error("New project tasks must be Task and Planned; existing progress is preserved");
  if(s.effort_hours!==undefined&&(typeof s.effort_hours!=="number"||!Number.isFinite(s.effort_hours)||s.effort_hours<=0||s.effort_hours>168))throw new Error("effort_hours must be greater than 0 and at most 168");
  if(s.dependencies!==undefined&&(!Array.isArray(s.dependencies)||s.dependencies.length>30||new Set(s.dependencies).size!==s.dependencies.length||s.dependencies.some(x=>typeof x!=="string"||!/^[a-z0-9][a-z0-9_-]{0,29}$/.test(x)||x===s.task_key)))throw new Error("dependencies must be distinct task keys and cannot include this task");
  const metadata={project_reference:s.project_reference,task_key:s.task_key,...(s.effort_hours!==undefined?{effort_hours:s.effort_hours}:{}),dependencies:s.dependencies||[]};
  const notes=String(s.notes??"").trim();
  s={...s,kind:"Task",status:"Planned",reference:managedReference,notes:notes+(notes?"\n\n":"")+"Planner metadata: "+JSON.stringify(metadata)};
 }
}
if(!cfg||cfg.timezone!=="Australia/Brisbane")throw new Error("Scheduling timezone must be Australia/Brisbane");
const names={"View schedule":"list_schedule","View tasks":"list_tasks","Find free time":"find_slots","Create event or task":"create","Edit or reschedule":"update","Mark task complete":"complete","Remove event or task":"archive"};
const action=names[s.action]||s.action;
if(!["list_schedule","list_tasks","find_slots","check_slot","create","update","complete","archive","project_context","sync_task","daily_review_context"].includes(action))throw new Error("Choose a supported scheduling action");
if(input.origin==="workflow"&&!["find_slots","check_slot","project_context","sync_task","daily_review_context"].includes(action))throw new Error("Other workflows may request availability or sync project task identities. Use the owner form to edit existing schedule items.");
if(!["owner","workflow","agent"].includes(input.origin))throw new Error("Invalid request source");
if(JSON.stringify(s).length>18000)throw new Error("Please shorten this request");
const text=(k,max)=>{const v=String(s[k]??"").trim();if(v.length>max)throw new Error(k+" is too long");return v;};
const iso=(v,label)=>{v=String(v??"").trim();const m=v.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d{1,3})?)?(Z|[+-]\d{2}:\d{2})$/);if(!m)throw new Error(label+" needs a valid date, time and timezone");
const [y,mo,d,h,mi,se]=m.slice(1,7).map(v=>Number(v||0));const check=new Date(Date.UTC(y,mo-1,d));
if(y<2000||y>2200||mo<1||mo>12||d<1||check.getUTCMonth()!==mo-1||check.getUTCDate()!==d||h>23||mi>59||se>59)throw new Error(label+" is not a valid date/time");
const ms=Date.parse(v);if(!Number.isFinite(ms))throw new Error(label+" is invalid");return new Date(ms).toISOString();};
const local=(date,time,label)=>iso(String(date)+"T"+String(time||"09:00")+":00+10:00",label);
const number=(v,def,min,max,label)=>{const n=v===""||v==null?def:Number(v);if(!Number.isInteger(n)||n<min||n>max)throw new Error(label+" must be "+min+"–"+max);return n;};
const now=Number($now.toMillis()),q={action,origin:input.origin,record_key:"schedule:"+input.execution_id,raw_input:JSON.stringify(s),timezone:cfg.timezone,settings:cfg,checked_at:new Date(now).toISOString(),request_reference:text("reference",80)};
if(isManaged){q.project_reference=s.project_reference;q.task_key=s.task_key||null;q.effort_hours=s.effort_hours??null;q.dependencies=s.dependencies||[];q.require_existing=s.require_existing===true||Boolean(s.known_page_id);q.known_page_id=String(s.known_page_id||"").replace(/-/g,"").toLowerCase();}
if(action==="daily_review_context"){
 if(input.origin!=="workflow")throw new Error("Daily review context is an internal read operation");
 q.window_start=iso(s.window_start,"Window start");q.window_end=iso(s.window_end,"Window end");
 const span=Date.parse(q.window_end)-Date.parse(q.window_start);
 if(span<=0||span>31*86400000)throw new Error("Review window must span at most 31 days");
 return [{json:q}];
}
if(action==="project_context"){
 if(s.window_start||s.window_end){
  q.window_start=iso(s.window_start,"Window start");q.window_end=iso(s.window_end,"Window end");
  if(Date.parse(q.window_end)<=Date.parse(q.window_start))throw new Error("Window end must follow window start");
 }
 return [{json:q}];
}
if(action==="sync_task"&&s.due_date&&(s.start||s.start_date||s.end||s.end_date||s.start_time||s.end_time)){
 q.unsupported_date_combination=true;return [{json:q}];
}
if(action==="sync_task"&&((s.start&&!s.end)||(!s.start&&s.end)||s.start_date||s.end_date||s.start_time||s.end_time))throw new Error("Project task scheduling requires explicit start and end timestamps");
const page=text("page",2048)||text("page_id",80);
if(page){let id=page;if(/^https?:/i.test(page)){const m=page.match(/^https:\/\/(?:[a-z0-9-]+\.)?notion\.(?:so|site|com)\/([^?#]+)(?:[?#].*)?$/i);if(!m)throw new Error("Paste a Notion page link");id=m[1].match(/([a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$/i)?.[1]||"";}
id=id.replace(/-/g,"").toLowerCase();if(!/^[a-f0-9]{32}$/.test(id))throw new Error("Choose an item by its Notion page link");q.page_id=id;}
q.title=text("title",200);q.notes=text("notes",2000);q.kind=text("kind",20);q.status=text("status",30);
if(q.kind&&!["Event","Task","Focus"].includes(q.kind))throw new Error("Type must be Event, Task or Focus");
if(q.status&&!["Planned","In progress","Done","Cancelled"].includes(q.status))throw new Error("Unsupported task status");
if(s.query!==undefined&&(action!=="list_tasks"||typeof s.query!=="string"||!s.query.trim()||s.query.length>200))throw new Error("Task search needs a name of 1–200 characters and the list_tasks action");
if(action==="list_tasks"){
 q.query=text("query",200);
 if(s.project_reference!==undefined&&(typeof s.project_reference!=="string"||!/^[a-z0-9][a-z0-9_-]{0,39}$/.test(s.project_reference)))throw new Error("Use a stable project reference of 1–40 lowercase letters, numbers, underscores or hyphens");
 q.project_reference=s.project_reference||null;
}
q.has_title=q.title!=="";q.has_notes=Object.prototype.hasOwnProperty.call(s,"notes")&&s.notes!=="";
q.colour=text("colour",20);q.has_colour=q.colour!=="";
if(q.colour&&!["Default","Blue","Green","Yellow","Orange","Red","Purple"].includes(q.colour))throw new Error("Choose one of the supported colours");
q.has_kind=q.kind!=="";q.has_status=q.status!=="";
if(s.blocks_time!==undefined&&s.blocks_time!==""){if(![true,false,"Yes","No"].includes(s.blocks_time))throw new Error("Blocks time must be Yes or No");q.blocks_time=s.blocks_time===true||s.blocks_time==="Yes";}
q.clear_time=s.clear_time===true;
q.due_date=text("due_date",10);
if(q.due_date){
if(!["create","update","sync_task"].includes(action))throw new Error("Due dates apply to creating or editing tasks");
if(!/^\d{4}-\d{2}-\d{2}$/.test(q.due_date))throw new Error("Enter a valid due date");
iso(q.due_date+"T00:00:00+10:00","Due date");
if(q.kind&&q.kind!=="Task")throw new Error("Due dates are for tasks; choose Type Task");
if(s.start||s.start_date||s.end||s.end_date||s.start_time||s.end_time)throw new Error("Use either a due date or a scheduled start time");
if(q.blocks_time===true)throw new Error("A due date does not reserve time; leave Reserve this time blank or choose No");
q.blocks_time=false;
if(action==="create")q.kind="Task";
}
q.duration_minutes=number(s.duration_minutes,30,5,1440,"Duration");
if(s.start||s.start_date){q.start=s.start?iso(s.start,"Start"):local(s.start_date,s.start_time,"Start");
q.end=s.end?iso(s.end,"End"):s.end_date?local(s.end_date,s.end_time,"End"):new Date(Date.parse(q.start)+q.duration_minutes*60000).toISOString();
if(Date.parse(q.end)<=Date.parse(q.start)||Date.parse(q.end)-Date.parse(q.start)>31*86400000)throw new Error("End must follow start and be within 31 days");}
if(["list_schedule","find_slots","check_slot"].includes(action)){
q.window_start=s.window_start?iso(s.window_start,"Window start"):s.from_date?local(s.from_date,"00:00","From date"):q.start;
q.window_end=s.window_end?iso(s.window_end,"Window end"):s.to_date?new Date(Date.parse(local(s.to_date,"00:00","To date"))+86400000).toISOString():q.end;
if(!q.window_start||!q.window_end||Date.parse(q.window_end)<=Date.parse(q.window_start)||Date.parse(q.window_end)-Date.parse(q.window_start)>31*86400000)throw new Error("Choose a search range of up to 31 days");
if(action!=="list_schedule"&&Date.parse(q.window_end)<=now)throw new Error("Availability needs a future time range");
q.day_start=text("day_start",5)||"09:00";q.day_end=text("day_end",5)||"17:00";
if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(q.day_start)||!/^([01]\d|2[0-3]):[0-5]\d$/.test(q.day_end)||q.day_start>=q.day_end)throw new Error("Use a valid daily search window such as 09:00 to 17:00");
if(s.include_weekends!==undefined&&!["Yes","No",true,false,""].includes(s.include_weekends))throw new Error("Include weekends must be Yes or No");
q.include_weekends=s.include_weekends===true||s.include_weekends==="Yes";q.buffer_minutes=number(s.buffer_minutes,0,0,120,"Buffer");q.max_slots=number(s.max_slots,5,1,20,"Number of slots");
}
if(["create","sync_task"].includes(action)){q.colour=q.colour||"Default";q.kind=q.kind||"Event";q.status=q.status||"Planned";if(!q.title&&action!=="sync_task")throw new Error("Enter a title");if(!q.start&&q.kind!=="Task")throw new Error("Events and focus blocks need a start date/time");q.blocks_time=q.blocks_time??Boolean(q.start);if(q.blocks_time&&!q.start)throw new Error("An unscheduled task cannot block time");if(q.start&&Date.parse(q.start)<now)throw new Error("Choose a future start time");}
if(["update","complete","archive"].includes(action)&&!q.page_id)throw new Error("Paste the Notion link for the item to change");
if(action==="update"&&!q.has_title&&!q.has_notes&&!q.has_kind&&!q.has_status&&!q.has_colour&&!q.start&&!q.due_date&&q.blocks_time===undefined&&!q.clear_time)throw new Error("Provide at least one change");
if(action==="update"&&q.start&&Date.parse(q.start)<now)throw new Error("Choose a future start time");
if(!/^[a-f0-9-]{32,36}$/i.test(cfg.data_source_id))throw new Error("SETUP REQUIRED: connect Notion and set the schedule data source in Scheduling settings");
return [{json:q}];
})();
if(transport.origin==="agent")for(const {json:q} of value){q.agent=transport.agent;q.expected_state=transport.raw.expected_state;q.replace_date=transport.raw.replace_date===true;if(transport.mutation){q.record_key=transport.record_key;q.raw_input=transport.input_signature;}}return value;
}catch(error){if(transport.origin!=="agent")throw error;return [{json:{origin:"agent",agent:transport.agent,agent_result:envelope(transport.agent,"needs_input",error.message)}}];}
