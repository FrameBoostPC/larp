import {CATEGORIES, envelope, parseReviewRequest} from './triage.mjs';
import {emailReviewNodeCode} from '../hermes-orchestration/email-review.mjs';

export function retrievalOperations(baseline) {
  const find = name => {
    const node = baseline.nodes.find(n => n.name === name);
    if (!node) throw new Error('Missing email node: ' + name);
    return node;
  };
  const configText = find('Load push configuration').parameters.jsCode;
  const match = configText.match(/const config=(\{[^\n]+\});/);
  const mailbox = match ? JSON.parse(match[1]).mailbox : null;
  if (typeof mailbox !== 'string' || !/^[^<>\s,@]+@[^<>\s,@]+\.[^<>\s,@]+$/.test(mailbox)) throw new Error('Verified configured mailbox required');
  const read = structuredClone(find('Read requested email reviews').parameters);
  if (read.matchType !== 'allConditions' || read.filters.conditions.length !== 3) throw new Error('Inspect changed saved-review filters before applying');
  read.filters.conditions.push(
    {keyName:'={{ $json.raw.sender ? "sender" : "message_id" }}', condition:'={{ $json.raw.sender ? "eq" : "isNotEmpty" }}', keyValue:'={{ $json.raw.sender || "" }}'},
    {keyName:'={{ $json.raw.subject_contains ? "subject" : "message_id" }}', condition:'={{ $json.raw.subject_contains ? "ilike" : "isNotEmpty" }}', keyValue:'={{ $json.subject_pattern || "" }}'}
  );
  const parser = 'const CATEGORIES=' + JSON.stringify(CATEGORIES) + ';\n' + envelope.toString() + '\n' + parseReviewRequest.toString() + '\nconst parsed=parseReviewRequest($input.first().json);\nif(parsed.raw?.subject_contains) parsed.subject_pattern="%"+parsed.raw.subject_contains.replace(/[\\\\%_]/g, char=>"\\\\"+char)+"%";\nreturn [{json:parsed}];';
  return [
    {type:'updateNodeParameters',nodeName:'Parse agent request',parameters:{mode:'runOnceForAllItems',jsCode:parser},replace:true},
    {type:'updateNodeParameters',nodeName:'Read requested email reviews',parameters:read,replace:true},
    {type:'updateNodeParameters',nodeName:'Return email reviews',parameters:{mode:'runOnceForAllItems',jsCode:emailReviewNodeCode(mailbox)},replace:true},
  ];
}
