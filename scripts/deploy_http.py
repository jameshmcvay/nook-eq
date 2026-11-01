"""Deploy the on-device EQ UI into RAM. No flash/autostart writes.
Requires a running RAM EQ driver and the private SSH master. Run scripts/build.py
first. The service drops root/groups before accepting LAN HTTP requests.
"""
import argparse,hashlib,ipaddress,json,os,re,subprocess,time,urllib.request
from pathlib import Path
from transport import SshTransport,SOCKET,HOST
ROOT=Path(__file__).resolve().parents[1]
SSH=['/usr/bin/ssh','-S',str(SOCKET),'-o','ControlMaster=no','-o','ProxyCommand=/usr/bin/false','-o','BatchMode=yes','root@Dining-Nook.local']
def remote(command,data=None,check=True):
 r=subprocess.run(SSH+[command],input=data,capture_output=True,timeout=20)
 if check and r.returncode:raise RuntimeError('Remote deployment operation failed: '+r.stderr.decode(errors='replace')[:250])
 return r

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--replace',action='store_true',help='replace a verified existing service process');args=ap.parse_args()
 transport=SshTransport();transport.status() # validates private socket and driver ABI
 binary=(ROOT/'bin/nook-http').read_bytes();manifest=json.loads((ROOT/'bin/http_build.json').read_text())
 if hashlib.sha256(binary).hexdigest()!=manifest['sha256']:raise RuntimeError('HTTP build hash mismatch.')
 text=remote('/sbin/ifconfig bridge0').stdout.decode()
 addresses=[a for a in re.findall(r'\binet (\d+\.\d+\.\d+\.\d+)',text) if ipaddress.ip_address(a).is_private and not ipaddress.ip_address(a).is_link_local]
 if not addresses:raise RuntimeError('No private bridge IPv4 address found.')
 address=addresses[0]
 before=transport.command('get');seed=None
 try:
  from configure import make_program,blob
  with urllib.request.urlopen(f'http://{address}:8080/api/config',timeout=2) as response:config=json.load(response)
  if isinstance(config,dict) and blob(make_program(config))==before:seed=b'NEQ1'+before+json.dumps(config).encode()
 except (OSError,ValueError,TypeError,KeyError):pass
 prior=remote('/bin/cat /var/run/nook-eq/http.pid',check=False).stdout.decode().strip()
 if prior:
  if not prior.isdecimal():raise RuntimeError('Invalid prior PID record; not stopping anything.')
  process=remote(f'/bin/ps -o comm= -p {prior}',check=False).stdout.decode().strip()
  if process:
   if not args.replace:raise RuntimeError('Service already running; use --replace to update it.')
   if process!='/var/run/nook-eq/nook-http':raise RuntimeError('Prior PID belongs to another process; not stopping it.')
   remote(f'/bin/kill {prior}')
   for _ in range(20):
    if not remote(f'/bin/ps -o comm= -p {prior}',check=False).stdout.strip():break
    time.sleep(.1)
   else:raise RuntimeError('Prior service did not stop; not overwriting its executable.')
 remote('umask 077; /bin/cat > /var/run/nook-eq/nook-http',binary);remote('/bin/chmod 700 /var/run/nook-eq/nook-http')
 if remote('/bin/cat /var/run/nook-eq/nook-http').stdout!=binary:raise RuntimeError('Server executable readback mismatch.')
 if seed is not None:remote('umask 077; /bin/cat > /var/run/nook-eq/http.seed',seed)
 remote(f'/usr/bin/nohup /var/run/nook-eq/nook-http {address} > /var/run/nook-eq/http.log 2>&1 < /dev/null & echo $! > /var/run/nook-eq/http.pid')
 url=f'http://{address}:8080';headers={}
 for _ in range(15):
  try:
   with urllib.request.urlopen(urllib.request.Request(url+'/api/program',headers=headers),timeout=2) as r:after=r.read()
   break
  except OSError:time.sleep(.2)
 else:raise RuntimeError('Service did not become ready; inspect its temporary log.')
 if after!=before:raise RuntimeError('EQ changed during deployment; inspect current settings. No automatic restore was attempted.')
 print('On-device EQ: http://'+HOST.split('@',1)[1]+':8080')
 print('IPv4 fallback: '+url)
 print('No firmware or EQ changes. Server and driver clear on reboot.')
if __name__=='__main__':
 try:main()
 except (RuntimeError,OSError,subprocess.TimeoutExpired) as e:raise SystemExit(str(e))
