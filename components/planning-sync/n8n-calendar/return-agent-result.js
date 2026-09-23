function envelope(meta,status,spoken,data=null,extra={}){
  return {output:spoken,tool_result:{schema_version:'1.0',request_id:meta?.request_id??null,session_id:meta?.session_id??null,revision:meta?.revision??null,status,spoken_summary:spoken,data,...extra}};
}
function scheduleResponse(meta,r,replayed=false){
  const statuses={OK:'completed',AVAILABLE:'completed',CREATED:'completed',UPDATED:'completed',COMPLETED:'completed',ARCHIVED:'completed',UNCHANGED:'completed',ALREADY_EXISTS:'completed',NO_SLOTS:'conflict',UNAVAILABLE:'conflict',CONFLICT:'conflict',STALE_STATE:'conflict',REFERENCE_CONFLICT:'conflict',DATE_REPLACEMENT_REQUIRED:'needs_input',NOT_FOUND:'needs_input',INVALID_ACTION:'needs_input'};
  const title=String(r.item?.title||'the item').replace(/[.!?]+$/,'');
  let spoken=r.status==='CREATED'?'Created '+title+'.':r.status==='UPDATED'?'Updated '+title+'.':r.status==='COMPLETED'?'Marked '+title+' complete.':r.status==='ARCHIVED'?'Removed '+title+'.':r.status==='ALREADY_EXISTS'?'That item is already saved.':r.status==='UNCHANGED'?'That task is already complete.':r.status==='AVAILABLE'?'That time is free in your connected calendar.':r.status==='UNAVAILABLE'?'That time is unavailable in your connected calendar.':r.status==='NO_SLOTS'?'No suitable gaps were found in that window.':r.status==='STALE_STATE'?'That item has changed since we last looked. I have refreshed its details.':r.status==='CONFLICT'?'That overlaps an existing commitment. Choose another time.':r.message;
  if(!spoken&&r.status==='OK'){const count=r.slots?.length??r.items?.length??0;const label=r.slots?'available time slot':r.action==='list_tasks'?'matching task':'matching item';spoken='I found '+count+' '+label+(count===1?'':'s')+'.';}
  if(['CREATED','UPDATED'].includes(r.status)&&r.item?.start){const zone=r.timezone||'Australia/Brisbane';const format=new Intl.DateTimeFormat('en-AU',{timeZone:zone,weekday:'long',day:'numeric',month:'long',hour:'numeric',minute:'2-digit'});spoken=spoken.replace(/\.$/,'')+', '+format.format(new Date(r.item.start))+'.';}
  if(r.status==='UNAVAILABLE'&&r.action==='check_slot'){
    spoken+=' '+(r.alternatives?.length?'I found '+r.alternatives.length+' alternative time'+(r.alternatives.length===1?'':'s')+' on the same day. Nothing has been booked.':r.alternatives_note||'');
  }
  if(replayed)spoken='That request was already handled. I have returned its saved receipt.';
  return envelope(meta,statuses[r.status]||'failed',spoken||'The calendar request needs review.',r,{replayed,historical_receipt:replayed,...(replayed?{refresh_before_edit:true}:{})});
}
const v=$input.first().json;if(v.agent_result)return [{json:v.agent_result}];return [{json:scheduleResponse($("Validate scheduling request").first().json.agent,$("Prepare schedule result").first().json.result)}];
