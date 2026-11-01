"""Hardware release gate: reboot, prove RAM removal, install the release ZIP,
verify web control/readback and unchanged primary flash, then check playback.
Run locally in Terminal; passwords stay in OpenSSH prompts. No firmware writes.
"""
import argparse,hashlib,json,os,socket,struct,subprocess,sys,tempfile,time,urllib.error,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--host',required=True);mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--reboot',action='store_true');mode.add_argument('--resume',action='store_true');a=ap.parse_args()
 if not sys.stdin.isatty():raise SystemExit('Run this test in your local Terminal for private SSH prompts.')
 import re
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,62}',a.host):raise SystemExit('Use an AirPort hostname or IPv4.')
 os.environ['NOOK_HOST']=a.host;env=dict(os.environ)
 archive=ROOT/'dist/nook-eq-0.1.0.zip'
 if not archive.exists():raise SystemExit('Run python3 scripts/package.py first.')
 sys.path.insert(0,str(ROOT/'scripts'));from transport import SshTransport,SOCKET,HOST
 ssh=['/usr/bin/ssh','-S',str(SOCKET),'-o','ControlMaster=no','-o','ProxyCommand=/usr/bin/false','-o','BatchMode=yes',HOST]
 def remote(command,timeout=20):
  r=subprocess.run(ssh+[command],capture_output=True,timeout=timeout)
  if r.returncode:raise RuntimeError('Remote test operation failed; do not automatically retry a write/reboot.')
  return r.stdout
 def http(path,*,body=None,url=None):
  origin=url or 'http://'+a.host+':8080';headers={'Content-Type':'application/octet-stream','Origin':origin}
  req=urllib.request.Request(origin+path,data=body,headers=headers,method='POST' if body is not None else 'GET')
  with urllib.request.urlopen(req,timeout=8) as r:return r.read()
 private=ROOT/'private';private.mkdir(mode=0o700,exist_ok=True);log=private/'clean-install.json';saved_program=private/'clean-install-program.bin'
 digest=hashlib.sha256(archive.read_bytes()).hexdigest();transport=SshTransport()
 if a.resume:
  if not log.exists():raise RuntimeError('No saved clean-install checkpoint exists.')
  record=json.loads(log.read_text())
  if record.get('host')!=a.host or not record.get('reboot_requested'):raise RuntimeError('Checkpoint target/reboot state does not match.')
  if record.get('passed'):raise RuntimeError('This test already passed; use --reboot for a new release candidate.')
  if digest!=record['archive_sha256']:
   if record['checks'].get('fresh_packaged_install'):raise RuntimeError('Archive changed after installation; a new clean test is required.')
   record['previous_candidate_sha256']=record['archive_sha256'];record['archive_sha256']=digest
  before=record['primary_before'];program=saved_program.read_bytes() if saved_program.exists() else None
  if program is not None and (len(program)!=332 or hashlib.sha256(program).hexdigest()!=record.get('previous_program_sha256')):program=None
  config=record.get('previous_config')
  print('Resuming the saved checkpoint. No reboot will be requested.',flush=True)
 else:
  subprocess.run([sys.executable,str(ROOT/'scripts/connect_ssh.py')],env=env,check=True)
  program=transport.command('get');config=None
  try:config=json.loads(http('/api/config'))
  except (OSError,ValueError):pass
  saved_program.write_bytes(program);saved_program.chmod(0o600)
  record={'host':a.host,'archive_sha256':digest,'previous_config':config,'previous_program_sha256':hashlib.sha256(program).hexdigest(),'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'checks':{}}
 def save():log.write_text(json.dumps(record,indent=2)+'\n');log.chmod(0o600)
 if not a.resume:
  print('Reading primary-bank hash before the RAM-only test...',flush=True)
  before=hashlib.sha256(remote('/bin/cat /dev/rflash0.raw',90)).hexdigest();record['primary_before']=before
  record['reboot_requested']=True;save();print('Rebooting the AirPort to remove the RAM install. Audio will stop.',flush=True)
  try:subprocess.run(ssh+['/sbin/reboot'],capture_output=True,timeout=20)
  except subprocess.TimeoutExpired:record['reboot_channel_timed_out']=True;save();print('SSH reboot channel timed out; checking the device without retrying reboot.',flush=True)
 deadline=time.monotonic()+180
 while time.monotonic()<deadline:
  try:
   with socket.create_connection((a.host,22),timeout=2):break
  except OSError:time.sleep(1)
 else:raise RuntimeError('SSH has not returned. Inspect the device; do not reboot again automatically.')
 print('Connecting to the restarted AirPort. Enter its password in the local SSH prompt.',flush=True)
 subprocess.run([sys.executable,str(ROOT/'scripts/connect_ssh.py')],env=env,check=True)
 if not record['checks'].get('fresh_packaged_install'):
  remote('/bin/test ! -e /var/run/nook-eq');record['checks']['ram_files_removed']=True
  layout=json.loads((ROOT/'src/layout.json').read_text())
  for item in layout['changes']:
   if item['kind'] in ('call','dispatch_pointer'):
    address=int(item['address'],16);data=remote(f'/bin/dd if=/dev/kmem bs=4 skip={address//4} count=1')
    if data!=bytes.fromhex(item['before']):raise RuntimeError('Stock hook did not return after reboot; stopped before install.')
  record['checks']['stock_hooks_restored_after_reboot']=True;save()
 if not record['checks'].get('fresh_packaged_install'):
  with tempfile.TemporaryDirectory(prefix='nook-release-test-') as folder:
   with zipfile.ZipFile(archive) as z:z.extractall(folder)
   release=Path(folder)/'nook-eq-0.1.0'
   for line in (release/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1)
    if hashlib.sha256((release/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Archive member hash mismatch.')
   subprocess.run([sys.executable,str(release/'install.py'),'--host',a.host],env=env,check=True)
 record['checks']['fresh_packaged_install']=True;save()
 current=transport.command('get')
 if not record['checks'].get('initial_bypass') and current[:4]!=bytes(4):raise RuntimeError('Fresh installer did not start bypassed.')
 record['checks']['initial_bypass']=True;save()
 mode=json.loads(http('/api/mode'))
 if mode!={'persistent':False}:raise RuntimeError('Unexpected persistent mode during RAM test.')
 for asset in ['/','/app.js','/coeff.js','/style.css','/jhm.svg']:
  if not http(asset):raise RuntimeError('Empty web asset')
 record['checks']['device_web_assets_and_ram_mode']=True
 if program is None:
  from configure import make_program,blob
  config=dict(enabled=True,preamp_db=0,bands=[]);program=blob(make_program(config));record['prior_program_not_checkpointed']=True
  print('The earlier checkpoint had no saved EQ. Using Flat/unity for this test; choose your preset again in the UI.',flush=True)
 status=http('/api/program',body=program+json.dumps(config).encode())
 if len(status)!=36 or http('/api/program')!=program:raise RuntimeError('HTTP Apply/readback failed.')
 record['checks']['http_apply_and_readback']=True
 print('HTTP Apply/readback passed.',flush=True)
 print('Reading primary-bank hash after installation...',flush=True)
 after=hashlib.sha256(remote('/bin/cat /dev/rflash0.raw',90)).hexdigest();record['primary_after']=after
 if after!=before:raise RuntimeError('Primary flash changed unexpectedly; stop and inspect.')
 record['checks']['primary_flash_unchanged']=True;save()
 input('Start/restart AirPlay. In the web UI, choose Flat (or your preset), leave EQ on, click Apply, confirm the sound, then press Return: ')
 words=struct.unpack('>9I',http('/api/status'));record['audio_status']=dict(zip(['magic','abi','requested','applied','rate','bits','channels','output_clips','internal_clips'],words))
 if words[2]!=words[3] or words[4] not in (44100,48000) or words[5] not in (16,24) or words[6] not in (1,2):raise RuntimeError('Audio processing was not observed; start a fresh stream and inspect status.')
 record['checks']['live_audio_and_applied_generation']=True;record['checks']['audible_confirmation']=True;record['passed']=True;record['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());save()
 print('PASS: clean packaged RAM install, real audio, HTTP controls and unchanged flash. Evidence saved privately.')
if __name__=='__main__':
 try:main()
 except (OSError,RuntimeError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as e:raise SystemExit(str(e)+' Test stopped; no automatic reboot or write retry.')
