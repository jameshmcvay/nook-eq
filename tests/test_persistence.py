"""Save/restart/load integration test of the actual embedded service code."""
import http.client,json,os,socket,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));from configure import make_program,blob
class PersistenceTests(unittest.TestCase):
 def test_profile_survives_service_restart(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='profile-') as folder:
   executable=ROOT/'build/http-persistence-host'
   subprocess.run(['/usr/bin/clang','-std=c99','-O2','-Wall','-Wextra','-Werror','-DNOOK_PORT=18088','-DPROFILE_DIR="'+folder+'"','-Isrc','-Ibuild','tests/http_host.c','-o',str(executable)],cwd=ROOT,check=True)
   def start():
    p=subprocess.Popen([str(executable),'127.0.0.1','--persistent'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    for _ in range(40):
     if p.poll() is not None:raise RuntimeError('Persistent test server exited')
     try:
      with socket.create_connection(('127.0.0.1',18088),.1):return p
     except OSError:time.sleep(.025)
    raise RuntimeError('Test server not ready')
   def stop(p):p.terminate();p.wait(timeout=5);p.stderr.close()
   def request(method,path,body=None):
    c=http.client.HTTPConnection('127.0.0.1',18088,timeout=5);c.request(method,path,body,{'Origin':'http://127.0.0.1:18088','Content-Type':'application/octet-stream'});r=c.getresponse();out=(r.status,r.read());c.close();return out
   cfg=dict(enabled=True,preamp_db=-7,bands=[dict(type='peaking',frequency_hz=900,gain_db=-2,q=.8)]);program=blob(make_program(cfg));p=start()
   try:
    self.assertEqual(json.loads(request('GET','/api/mode')[1]),{'persistent':True})
    self.assertEqual(request('POST','/api/program',program+json.dumps(cfg).encode())[0],200)
    self.assertTrue((Path(folder)/'program').read_bytes().startswith(b'NEQ1'+program))
   finally:stop(p)
   p=start()
   try:
    self.assertEqual(request('GET','/api/program'),(200,program));self.assertEqual(json.loads(request('GET','/api/config')[1]),cfg)
   finally:stop(p)
   (Path(folder)/'program').write_bytes(b'invalid profile')
   p=start()
   try:self.assertNotEqual(request('GET','/api/program')[1],program)
   finally:stop(p)
if __name__=='__main__':unittest.main(verbosity=2)
