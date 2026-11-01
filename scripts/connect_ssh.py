"""Open a private OpenSSH master. Password and host-key decisions stay in Terminal.
This starts an authenticated session only; no uploads or remote commands.
"""
import os,stat,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from transport import SOCKET_DIR,SOCKET,HOST
if not sys.stdin.isatty():raise SystemExit('Run in your local Terminal to handle login and host-key prompts.')
try:SOCKET_DIR.mkdir(mode=0o700)
except FileExistsError:pass
st=SOCKET_DIR.lstat()
if not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.getuid() or st.st_mode&0o077:raise SystemExit('SSH socket directory must be private and owned by you.')
if SOCKET.exists():
 result=subprocess.run(['/usr/bin/ssh','-S',str(SOCKET),'-O','check',HOST])
 if result.returncode==0:print('Existing private SSH session is ready.');raise SystemExit(0)
 raise SystemExit('Existing socket is not usable. Review the old session before starting another.')
args=['/usr/bin/ssh','-M','-N','-f','-S',str(SOCKET),'-o','ControlPersist=30m','-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3','-o','KexAlgorithms=+diffie-hellman-group1-sha1','-o','HostKeyAlgorithms=+ssh-rsa','-o','Ciphers=+aes128-cbc',HOST]
subprocess.run(args,check=True)
subprocess.run(['/usr/bin/ssh','-S',str(SOCKET),'-O','check',HOST],check=True)
print('Private SSH session is ready. No device files or settings were changed.')
