import ctypes as C,json,math,sys,unittest
from pathlib import Path
import numpy as np
from scipy.signal import lfilter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from configure import make_program,blob,coefficients,Q
ROOT=Path(__file__).resolve().parents[1]
class Coeff(C.Structure):_fields_=[(n,C.c_int32) for n in ['b0','b1','b2','a1','a2']]
class Program(C.Structure):_fields_=[('enabled',C.c_uint32),('stages',C.c_uint32),('preamp',C.c_int32),('coeff',(Coeff*8)*2)]
class Delay(C.Structure):_fields_=[(n,C.c_int32) for n in ['x1','x2','y1','y2','error']]
class State(C.Structure):_fields_=[(n,C.c_uint32) for n in ['rate','bits','channels','output_clips','internal_clips']]+[('delay',(Delay*8)*2)]
lib=C.CDLL(str(ROOT/'build/libeq.dylib'));lib.eq_process.argtypes=[C.POINTER(Program),C.POINTER(State),C.POINTER(C.c_uint8),C.c_uint32,C.c_uint32,C.c_uint32,C.c_uint32];lib.eq_process.restype=C.c_int

def pack(samples,bits):return b''.join(int(x).to_bytes(bits//8,'big',signed=True) for x in np.asarray(samples).flat)
def unpack(data,bits):return np.array([int.from_bytes(data[i:i+bits//8],'big',signed=True) for i in range(0,len(data),bits//8)])
def run(program,samples,bits,rate,state=None,channels=2):
 raw=pack(samples,bits);buf=(C.c_uint8*len(raw)).from_buffer_copy(raw);state=state if state is not None else State()
 p=Program.from_buffer_copy(blob(program,'='));result=lib.eq_process(C.byref(p),C.byref(state),buf,len(raw),bits,channels,rate)
 return unpack(bytes(buf),bits).reshape(-1,channels),state,result

def float_reference(program,samples,bits,rate):
 x=samples.astype(np.float64)*(program['preamp']/Q)
 for c in program['coeff'][rate==48000]:
  c=np.array(c,dtype=float)/Q;x=lfilter(c[:3],[1,*c[3:]],x,axis=0)
 return np.clip(np.floor(x+.5),-(1<<(bits-1)),(1<<(bits-1))-1)
class DSPTests(unittest.TestCase):
 def setUp(self):self.example=make_program(json.loads((ROOT/'tests/example.json').read_text()))
 def test_identity_all_values_16_and_24_edges(self):
  identity=make_program(dict(enabled=True,preamp_db=0,bands=[]))
  for bits in (16,24):
   a=np.arange(-32768,32768) if bits==16 else np.array([-(1<<23),-8388607,-65537,-257,-1,0,1,255,256,65537,8388606,8388607])
   a=np.column_stack([a,a[::-1]]);out,s,r=run(identity,a,bits,44100);np.testing.assert_array_equal(out,a);self.assertEqual(r,0);self.assertEqual(s.output_clips,0)
 def test_against_double_reference(self):
  rng=np.random.default_rng(12345);self.max_errors={}
  for rate in (44100,48000):
   for bits in (16,24):
    scale=1<<(bits-1);n=24000;t=np.arange(n)/rate
    vectors=[np.column_stack([np.r_[scale//2,np.zeros(n-1,dtype=int)],np.zeros(n,dtype=int)]),
      np.round(scale*.7*np.column_stack([np.sin(2*np.pi*100*t),np.sin(2*np.pi*7000*t)])).astype(int),
      rng.integers(-scale,scale,(n,2))]
    for a in vectors:
     out,s,r=run(self.example,a,bits,rate);ref=float_reference(self.example,a,bits,rate);err=np.max(np.abs(out-ref))
     self.max_errors[f'{rate}/{bits}']=max(self.max_errors.get(f'{rate}/{bits}',0),float(err))
     self.assertLessEqual(err,1 if bits==16 else 32);self.assertEqual(s.internal_clips,0);self.assertEqual(s.output_clips,0);self.assertEqual(r,0)
  (ROOT/'build/dsp_accuracy.json').write_text(json.dumps(self.max_errors,indent=2)+'\n')
 def test_channel_isolation_and_chunk_invariance(self):
  rng=np.random.default_rng(9)
  for bits in (16,24):
   a=np.column_stack([rng.integers(-(1<<(bits-2)),1<<(bits-2),10000),np.zeros(10000,dtype=int)])
   full,_,_=run(self.example,a,bits,48000);s=State();parts=[];start=0
   for n in [1,3,588,1,882,777,1024,4000,2724]:
    end=min(start+n,len(a));o,s,_=run(self.example,a[start:end],bits,48000,s);parts.append(o);start=end
   if start<len(a):o,s,_=run(self.example,a[start:],bits,48000,s);parts.append(o)
   np.testing.assert_array_equal(np.concatenate(parts),full);self.assertTrue(np.all(full[:,1]==0))
 def test_bypass_and_rejected_formats_preserve_bytes(self):
  p=Program.from_buffer_copy(blob(self.example,'='));s=State();raw=bytes(range(17));buf=(C.c_uint8*17).from_buffer_copy(raw)
  for bits,ch,rate,size in [(8,2,44100,16),(32,2,44100,16),(16,3,44100,12),(16,2,22050,16),(24,2,44100,17)]:
   s.rate=48000;self.assertEqual(lib.eq_process(C.byref(p),C.byref(s),buf,size,bits,ch,rate),-1);self.assertEqual(bytes(buf),raw);self.assertEqual(s.rate,0)
  p.enabled=0;self.assertEqual(lib.eq_process(C.byref(p),C.byref(s),buf,17,16,2,44100),0);self.assertEqual(bytes(buf),raw)
 def test_rate_change_resets_state(self):
  a=np.full((100,2),10000);_,s,_=run(self.example,a,16,44100);out,s,_=run(self.example,a,16,48000,s);fresh,_,_=run(self.example,a,16,48000);np.testing.assert_array_equal(out,fresh)
 def test_positive_gain_clips_without_wrapping(self):
  p=make_program(dict(enabled=True,preamp_db=0,bands=[dict(type='peaking',frequency_hz=1000,gain_db=12,q=.7)]))
  a=np.round(32767*.9*np.sin(2*np.pi*1000*np.arange(10000)/48000)).astype(int);a=np.column_stack([a,-a]);o,s,_=run(p,a,16,48000)
  self.assertGreater(s.output_clips,0);self.assertEqual(s.internal_clips,0);self.assertTrue(np.all(o<=32767));self.assertTrue(np.all(o>=-32768))
 def test_invalid_designs(self):
  for f,g,q in [(24000,0,1),(0,0,1),(1000,13,1),(1000,1,0),(math.nan,0,1)]:
   with self.assertRaises(ValueError):coefficients(dict(type='peaking',frequency_hz=f,gain_db=g,q=q),48000)
if __name__=='__main__':unittest.main(verbosity=2)
