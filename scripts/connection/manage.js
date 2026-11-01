'use strict';
const acp=require('node-acp');
acp.loglevel=acp.LogLevel.NONE;
class Refusal extends Error {}
async function inspect(client,state={}){
 state.phase='connecting';await client.connect(10000);
 state.phase='authenticating';await client.authenticate();
 if(!client.session_encrypted)throw new Refusal('Encrypted administration session was not established.');
 state.phase='reading_identity';
 const properties=await client.getProperties(['syAP','syVs','syNm']);
 const props=Object.fromEntries(properties.map(p=>[p.name,p]));
 if(Number(props.syAP?.format())!==115||!/^7\.8\.1(?:\D|$)/.test(String(props.syVs?.format())))throw new Refusal('Device identity does not match model 115 / firmware 7.8.1.');
 state.phase='reading_debug_flags';
 const debug=await client.getProperties(['dbug'],true);
 const unset=debug.length===1&&debug[0] instanceof Error&&/^Error requesting value for property "dbug": -10 fffffff6$/.test(debug[0].message);
 if(debug[0] instanceof Error&&!unset)throw debug[0];
 const value=debug[0]?.value;
 if(!unset&&(debug.length!==1||debug[0]?.name!=='dbug'||!Buffer.isBuffer(value)||value.length!==4))throw new Refusal('Current debug flags could not be read safely.');
 const before=unset?null:value.readUInt32BE(0),after=unset?0x3000:((before|0x3000)&~0x200)>>>0;
 return {host:client.host,name:String(props.syNm.format()),model:115,firmware:String(props.syVs.format()),dbug_before:before,dbug_was_unset:unset,dbug_after:after,session_encrypted:true};
}
async function execute(client,request,state={}){
 const plan=await inspect(client,state);state.phase='inspected';
 if(request.mode==='inspect')return {...plan,settings_changed:false,reboot_requested:false};
 if(request.mode==='finish_enable_ssh'){
  if(!Number.isInteger(request.expected_dbug)||plan.dbug_before!==request.expected_dbug||plan.dbug_before!==plan.dbug_after)throw new Refusal('Saved SSH target flags are not present; no write or reboot performed.');
  state.phase='requesting_reboot';state.reboot_requested=true;await client.reboot();state.phase='done';
  return {...plan,settings_changed:false,reboot_requested:true};
 }
 if(request.mode!=='enable_ssh')throw new Refusal('Unsupported operation.');
 if(!Object.hasOwn(request,'expected_dbug')||(request.expected_dbug!==null&&!Number.isInteger(request.expected_dbug))||plan.dbug_before!==request.expected_dbug)throw new Refusal('Debug flags changed since inspection; no write performed.');
 if(plan.dbug_before!==plan.dbug_after){
  const value=Buffer.alloc(4);value.writeUInt32BE(plan.dbug_after);
  state.phase='setting_debug_flags';state.settings_change_attempted=true;await client.setProperties([new acp.Property('dbug',value)]);state.settings_changed=true;
  const confirmed=await client.getProperties(['dbug']);
  if(confirmed[0]?.value?.readUInt32BE(0)!==plan.dbug_after)throw new Refusal('Debug flags did not read back correctly; reboot was not requested.');
 }
 state.phase='requesting_reboot';state.reboot_requested=true;await client.reboot();state.phase='done';
 return {...plan,settings_changed:!!state.settings_changed,reboot_requested:true};
}
function diagnostic(error){
 const d={error_type:error?.constructor?.name||'UnknownError'};
 if(typeof error?.code==='number')d.acp_error_code=error.code;
 if(['ECONNREFUSED','ENOTFOUND','EAI_AGAIN','ETIMEDOUT','ENETUNREACH','EHOSTUNREACH','ECONNRESET','EPIPE'].includes(error?.code))d.network_error_code=error.code;
 const property=/^Error requesting value for property "(syAP|syVs|syNm|dbug)": (-?\d+)/.exec(error?.message||'');
 if(property){d.property=property[1];d.property_error_code=Number(property[2]);}
 if(error?.message==='Not connected')d.connection_error='disconnected';
 if(error?.message==='Error verifying response (M2)')d.srp_error='server_proof_rejected';
 const location=/(node-acp\/dist\/[^\s:)]+:\d+:\d+)/.exec(error?.stack||'');
 if(location)d.library_location=location[1];
 return d;
}
function secureClient(host,password,factory=(h,p,pw)=>new acp.default(h,p,pw)){
 const client=factory(host,5009,password),connect=client.connect.bind(client);
 client.connect=(timeout)=>{
  const connected=connect(timeout);
  const failed=new Promise((resolve,reject)=>client.session.socket.once('error',reject));
  // Keep the socket error listener: node-acp 0.7 does not install one itself.
  return Promise.race([connected,failed]);
 };
 return client;
}
module.exports={inspect,execute,Refusal,diagnostic,secureClient};
if(require.main===module){
 let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',chunk=>{input+=chunk;if(input.length>4096)process.exit(2);});
 process.stdin.on('end',async()=>{
  let client,state={phase:'starting',settings_change_attempted:false,settings_changed:false,reboot_requested:false};
  try{
   const request=JSON.parse(input);input='';
   if(typeof request.host!=='string'||! /^[A-Za-z0-9][A-Za-z0-9.-]{0,62}$/.test(request.host))throw new Refusal('Use an AirPort hostname or IPv4 address.');
   if(typeof request.password!=='string'||!request.password)throw new Refusal('An admin password is required.');
   client=secureClient(request.host,request.password);request.password='';
   const result=await execute(client,request,state);console.log(JSON.stringify({ok:true,...result}));
  }catch(e){console.log(JSON.stringify({ok:false,...state,diagnostic:diagnostic(e),error:e instanceof Refusal?e.message:'Authenticated device request failed; do not retry a reboot or setting write automatically.'}));process.exitCode=1;}
  finally{if(client)await client.disconnect()?.catch(()=>{});}
 });
}
