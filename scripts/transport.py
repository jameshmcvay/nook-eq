"""Use an existing, user-authenticated OpenSSH master; never handle a password.
No fallback login, host-key auto-acceptance, shell interpolation or uploads.
"""
import os,stat,struct,subprocess,hashlib
from pathlib import Path
HOST='root@'+os.environ.get('NOOK_HOST','airport-express.local')
TEMP=Path('/private/tmp') if Path('/private/tmp').exists() else Path('/tmp')
SOCKET_DIR=Path(os.environ.get('NOOK_SOCKET_DIR',str(TEMP/f'nook-eq-{os.getuid()}-{hashlib.sha256(HOST.lower().encode()).hexdigest()[:8]}')))
SOCKET=SOCKET_DIR/'ssh.sock'
class DeviceUnavailable(RuntimeError):pass
class SshTransport:
 def command(self,operation,payload=None):
  if operation not in ('status','get','set'):raise ValueError('Invalid control operation')
  try:directory=SOCKET_DIR.lstat();sock=SOCKET.lstat()
  except OSError:raise DeviceUnavailable('Connect the private SSH session in Terminal first.')
  if not stat.S_ISDIR(directory.st_mode) or directory.st_uid!=os.getuid() or directory.st_mode&0o077 or not stat.S_ISSOCK(sock.st_mode) or sock.st_uid!=os.getuid():raise DeviceUnavailable('SSH session path is not private and owned by this user.')
  args=['/usr/bin/ssh','-S',str(SOCKET),'-o','ControlMaster=no','-o','ProxyCommand=/usr/bin/false','-o','BatchMode=yes','-o','PasswordAuthentication=no','-o','KbdInteractiveAuthentication=no','-o','PubkeyAuthentication=no','-o','ConnectTimeout=3',HOST,f'/var/run/nook-eq/eqctl {operation}']
  try:result=subprocess.run(args,input=payload,capture_output=True,timeout=6)
  except (OSError,subprocess.TimeoutExpired):raise DeviceUnavailable('Device request failed or timed out. A write may be pending; check status before retrying.')
  if result.returncode:raise DeviceUnavailable('The EQ control helper is unavailable or rejected the request. The matching validated patch and helper must be installed first.')
  return result.stdout
 def status(self):
  raw=self.command('status')
  if len(raw)!=36:raise DeviceUnavailable('Unexpected EQ driver status length.')
  words=struct.unpack('>9I',raw)
  if words[:2]!=(0x45513130,1):raise DeviceUnavailable('Device EQ driver ABI does not match.')
  keys=['magic','abi','requested_generation','applied_generation','sample_rate','bits','channels','output_clips','internal_clips']
  return dict(zip(keys,words))
 def apply(self,program):
  if len(program)!=332:raise ValueError('Expected 332-byte program.')
  self.status() # refuse to write if the helper/ABI is unavailable
  raw=self.command('set',program)
  if len(raw)!=36:raise DeviceUnavailable('Settings result is uncertain. Check device status before retrying.')
  words=struct.unpack('>9I',raw)
  if words[:2]!=(0x45513130,1):raise DeviceUnavailable('Settings result has an unexpected ABI.')
  if self.command('get')!=program:raise DeviceUnavailable('Requested settings did not read back correctly. Check device status before retrying.')
  return self.status()
