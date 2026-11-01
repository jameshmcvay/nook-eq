"""Load the exact EQ build in temporary RAM, initially bypassed. No flash writes.
Requires the existing private SSH session. Reboot removes both patch and files.
"""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'control'))
from transport import SshTransport,SOCKET
SSH=['/usr/bin/ssh','-S',str(SOCKET),'-o','ControlMaster=no','-o','ProxyCommand=/usr/bin/false','-o','BatchMode=yes','root@Dining-Nook.local']
def remote(command,data=None):
 r=subprocess.run(SSH+[command],input=data,capture_output=True,timeout=20)
 if r.returncode:raise RuntimeError(f'Temporary RAM operation exited {r.returncode}: '+r.stderr.decode(errors='replace')[:500])
 return r.stdout

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--install-bypass',action='store_true',required=True);ap.parse_args()
 manifest=json.loads((ROOT/'bin/ram_manifest.json').read_text())
 loader=(ROOT/'bin/ram-eq').read_bytes()
 if hashlib.sha256(loader).hexdigest()!=manifest['loader_sha256']:raise RuntimeError('Loader hash mismatch; rebuild with build_ram.py.')
 # Exclusive directory creation refuses a repeat or ambiguous prior attempt.
 remote('umask 077; /bin/mkdir /var/run/nook-eq')
 for name,data in [('ram-eq',loader),('eqctl',(ROOT/'bin/eqctl').read_bytes())]:
  remote(f'/bin/cat > /var/run/nook-eq/{name}',data)
  remote(f'/bin/chmod 700 /var/run/nook-eq/{name}')
  if remote(f'/bin/cat /var/run/nook-eq/{name}')!=data:raise RuntimeError('Executable readback mismatch; no kernel-memory write requested.')
 remote('umask 077; /bin/mknod /var/run/nook-eq/rawmem c 2 13; /bin/chmod 600 /var/run/nook-eq/rawmem')
 try:
  print(remote('/var/run/nook-eq/ram-eq check-write-access').decode(),end='',flush=True)
  print(remote('/var/run/nook-eq/ram-eq install-bypass').decode(),end='',flush=True)
 finally:remote('/bin/rm /var/run/nook-eq/rawmem')
 remote('umask 077; /bin/mknod /var/run/nook-eq/control c 101 128; /bin/chmod 600 /var/run/nook-eq/control')
 t=SshTransport();status=t.status();program=t.command('get')
 if len(program)!=332 or program[:4]!=bytes(4):raise RuntimeError('Initial bypass readback failed; stop and power-cycle to restore stock RAM.')
 print(json.dumps(status,indent=2));print('Temporary driver ready in bypass. Reboot/power-cycle removes it; flash is unchanged.')
if __name__=='__main__':
 try:main()
 except (RuntimeError,OSError,subprocess.TimeoutExpired) as e:raise SystemExit(str(e)+' Do not retry automatically after a partial RAM load; power-cycle restores the stock kernel.')
