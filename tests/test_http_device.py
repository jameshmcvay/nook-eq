"""Exercise the actual embedded HTTP parser with a native syscall shim."""
import http.client,json,socket,subprocess,time,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));from configure import make_program,blob
PORT=18087
class HttpTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  subprocess.run(['/usr/bin/clang','-std=c99','-O2','-Wall','-Wextra','-Werror','-DNOOK_PORT=18087','-Isrc','-Ibuild','tests/http_host.c','-o','build/http-host'],cwd=ROOT,check=True)
  with socket.socket() as check:check.bind(('127.0.0.1',PORT))
  cls.process=subprocess.Popen([str(ROOT/'build/http-host'),'127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  for _ in range(40):
   if cls.process.poll() is not None:raise RuntimeError('Host test server exited')
   try:
    with socket.create_connection(('127.0.0.1',PORT),.1):break
   except OSError:time.sleep(.025)
 @classmethod
 def tearDownClass(cls):cls.process.terminate();cls.process.wait(timeout=5);cls.process.stderr.close()
 def request(self,method,path,body=None,headers=None):
  c=http.client.HTTPConnection('127.0.0.1',PORT,timeout=7);c.request(method,path,body,headers or {});r=c.getresponse();out=(r.status,r.read());c.close();return out
 def test_embedded_assets_and_binary_status(self):
  for path in ['/','/app.js','/coeff.js','/presets.js','/style.css']:
   code,data=self.request('GET',path);self.assertEqual(code,200);self.assertGreater(len(data),500)
  self.assertEqual(self.request('GET','/api/name'),(200,b'AirPort Express'))
  code,data=self.request('GET','/api/status');self.assertEqual(code,200);self.assertEqual(len(data),36);self.assertEqual(data[:4],b'EQ10')
 def test_program_set_readback_and_metadata(self):
  cfg=dict(enabled=True,preamp_db=-5,bands=[]);p=blob(make_program(cfg));body=p+json.dumps(cfg).encode();headers={'Origin':f'http://127.0.0.1:{PORT}','Content-Type':'application/octet-stream'}
  self.assertEqual(self.request('POST','/api/program',body,headers)[0],200)
  self.assertEqual(self.request('GET','/api/program'),(200,p));self.assertEqual(json.loads(self.request('GET','/api/config')[1]),cfg)
 def test_origin_host_size_and_invalid_program_never_change_settings(self):
  before=self.request('GET','/api/program')[1];body=before+b'{}'
  for headers,code in [({'Content-Type':'application/octet-stream'},403),({'Origin':'https://elsewhere.invalid','Content-Type':'application/octet-stream'},403),({'Host':'elsewhere.invalid'},403),({'Origin':f'http://127.0.0.1:{PORT}','Content-Type':'text/plain'},415)]:
   self.assertEqual(self.request('POST','/api/program',body,headers)[0],code)
  h={'Origin':f'http://127.0.0.1:{PORT}','Content-Type':'application/octet-stream'}
  self.assertEqual(self.request('POST','/api/program',bytes(4097),h)[0],400)
  bad=bytearray(body);bad[:4]=b'\xff'*4;self.assertEqual(self.request('POST','/api/program',bad,h)[0],422)
  self.assertEqual(self.request('GET','/api/program')[1],before)
 def test_no_access_code_required_on_lan(self):
  for path in ['/api/status','/api/program','/api/config']:
   self.assertEqual(self.request('GET',path)[0],200)
 def test_unknown_paths_and_transfer_encoding_rejected(self):
  self.assertEqual(self.request('GET','/../../etc/passwd')[0],404)
  self.assertEqual(self.request('GET','/',headers={'Transfer-Encoding':'chunked'})[0],400)
 def test_duplicate_headers_are_rejected(self):
  with socket.create_connection(('127.0.0.1',PORT),timeout=3) as s:
   s.sendall(f'GET / HTTP/1.1\r\nHost: 127.0.0.1:{PORT}\r\nHost: 127.0.0.1:{PORT}\r\n\r\n'.encode());self.assertIn(b'400 Bad Request',s.recv(1024))
if __name__=='__main__':unittest.main(verbosity=2)
