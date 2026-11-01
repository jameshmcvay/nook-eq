"""Inspect encrypted ACP state; optionally enable diagnostic SSH and reboot.
Run locally in a terminal. Password goes through a private stdin pipe, never
argv, environment, a file, or the chat. No firmware upload functionality.
"""
import argparse,getpass,json,subprocess,sys,os,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TARGET=os.environ.get('NOOK_HOST','airport-express.local')

EXPECTED_UNSPECIFIED=object()

def request(mode,password,expected=EXPECTED_UNSPECIFIED):
 payload=dict(mode=mode,host=TARGET,password=password)
 if expected is not EXPECTED_UNSPECIFIED:payload['expected_dbug']=expected
 try:
  result=subprocess.run(['node',str(ROOT/'scripts/connection/manage.js')],input=json.dumps(payload),text=True,capture_output=True,timeout=40)
 except subprocess.TimeoutExpired:raise RuntimeError('Timed out. If enabling SSH, do not retry automatically: the settings/reboot state is uncertain.')
 try:reply=json.loads(result.stdout)
 except ValueError:raise RuntimeError(f'ACP helper exited without a valid result (exit {result.returncode}). No secret output will be displayed.')
 if not reply.get('ok'):
  raise RuntimeError(f"{reply.get('error','Request failed')} State: {reply.get('phase')}; setting write attempted: {reply.get('settings_change_attempted',False)}; settings changed: {reply.get('settings_changed')}; reboot requested: {reply.get('reboot_requested')}. Diagnostic: {json.dumps(reply.get('diagnostic',{}),sort_keys=True)}")
 return reply

def main():
 ap=argparse.ArgumentParser(description=__doc__);mode=ap.add_mutually_exclusive_group();mode.add_argument('--enable',action='store_true',help='enable root diagnostic SSH and request one reboot; requires explicit authorization');mode.add_argument('--finish-enable',action='store_true',help='verify previously saved SSH target flags and request one reboot without rewriting settings');a=ap.parse_args()
 if not sys.stdin.isatty():raise SystemExit('Run this command in your own terminal so the password can be entered privately.')
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,62}',TARGET):raise RuntimeError('Use an AirPort hostname or IPv4 address.')
 print(f'Target: {TARGET} / model 115 / firmware 7.8.1')
 if a.finish_enable:print('This verifies the saved SSH target flags and requests one reboot. It does not rewrite settings.')
 if a.enable:print('This enables diagnostic root SSH on connected networks and reboots Dining Nook. It does not install firmware.')
 password=getpass.getpass('AirPort admin password (not saved): ')
 try:
  plan=request('inspect',password)
  public={k:v for k,v in plan.items() if k!='ok'}
  print(json.dumps(public,indent=2))
  if a.finish_enable:
   backup=ROOT/'private/ssh_debug_flags_before.json'
   if not backup.exists():raise RuntimeError('No prior SSH setup record exists; no reboot requested.')
   saved=json.loads(backup.read_text())
   if saved.get('name')!=plan.get('name') or saved.get('model')!=115 or saved.get('dbug_after')!=plan['dbug_before'] or plan['dbug_before']!=plan['dbug_after']:
    raise RuntimeError('Saved SSH target flags are not present; no write or reboot performed.')
   result=request('finish_enable_ssh',password,saved['dbug_after'])
   print(json.dumps(result,indent=2));print('Reboot requested. Wait for Dining Nook to return before connecting to SSH.');return
  if not a.enable:
   print('Inspection only. No settings changed.');return
  backup=ROOT/'private/ssh_debug_flags_before.json'
  if backup.exists():raise RuntimeError('A prior SSH setup record already exists. Review it before changing the device again.')
  backup.parent.mkdir(mode=0o700,exist_ok=True)
  backup.write_text(json.dumps(public,indent=2)+'\n')
  result=request('enable_ssh',password,plan['dbug_before'])
  print(json.dumps(result,indent=2));print('Wait for the device to restart, then verify SSH before continuing. No firmware was uploaded.')
 finally:password=''
if __name__=='__main__':
 try:main()
 except RuntimeError as e:raise SystemExit(str(e))
