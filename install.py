#!/usr/bin/env python3
"""Install/update the reboot-removable Nook EQ and on-device UI. Never flashes firmware."""
import argparse,hashlib,json,os,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--host',default='airport-express.local',help='AirPort Bonjour hostname or IPv4');ap.add_argument('--check',action='store_true',help='verify release files without connecting');a=ap.parse_args()
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,62}',a.host):raise SystemExit('Use a hostname or IPv4 address.')
 manifest=json.loads((ROOT/'bin/manifest.json').read_text())
 for name,record in manifest.items():
  data=(ROOT/'bin'/name).read_bytes()
  if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:raise SystemExit('Release binary check failed: '+name)
 print('Nook EQ · jhm\nAirPort Express A1392 / 7.8.1 only\nRAM install: no flash writes; reboot removes it.',flush=True)
 if a.check:print('All release binaries verified. No device connection made.');return
 env=dict(os.environ,NOOK_HOST=a.host)
 subprocess.run([sys.executable,str(ROOT/'scripts/connect_ssh.py')],env=env,check=True)
 sys.path.insert(0,str(ROOT/'scripts'));os.environ['NOOK_HOST']=a.host
 from transport import SshTransport,DeviceUnavailable
 try:SshTransport().status();print('Matching RAM driver already available.',flush=True)
 except DeviceUnavailable:subprocess.run([sys.executable,str(ROOT/'scripts/load_ram.py'),'--install-bypass'],env=env,check=True)
 subprocess.run([sys.executable,str(ROOT/'scripts/deploy_http.py'),'--replace'],env=env,check=True)
if __name__=='__main__':
 try:main()
 except (OSError,subprocess.CalledProcessError) as e:raise SystemExit(str(e)+' No automatic retry. If RAM loading was partial, power-cycle to restore stock.')
