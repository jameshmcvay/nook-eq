"""Verify the freestanding NetBSD tool's entry and syscall ABI without a device."""
import json,struct,sys,unittest
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.mips_const import *
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));from configure import make_program,blob
class EqctlTests(unittest.TestCase):
 def execute(self,command,stdin=b'',bad_abi=False,reject=False):
  u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_BIG_ENDIAN);u.ctl_set_cpu_model(UC_CPU_MIPS32_74KF);u.mem_map(0,0x2000000)
  with (ROOT/'build/eqctl').open('rb') as f:
   elf=ELFFile(f);entry=elf['e_entry']
   for s in elf.iter_segments():
    if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
  stack=0x10ff000;arg0=0x1100100;arg1=0x1100200;u.mem_write(arg0,b'eqctl\0');u.mem_write(arg1,command.encode()+b'\0');u.mem_write(stack,struct.pack('>4I',2,arg0,arg1,0));u.reg_write(UC_MIPS_REG_SP,stack);u.reg_write(UC_MIPS_REG_A0,stack)
  state={'stdout':bytearray(),'stderr':bytearray(),'read':0,'calls':[],'exit':None,'sets':[]};generation=0
  def readstr(p):
   out=bytearray()
   for i in range(256):
    b=bytes(u.mem_read(p+i,1))
    if b==b'\0':return out.decode()
    out.extend(b)
   raise AssertionError('unterminated string')
  def interrupt(uc,n,data):
   nonlocal generation
   self.assertEqual(n,17);number=uc.reg_read(UC_MIPS_REG_V0);a=[uc.reg_read(r) for r in [UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2]];state['calls'].append((number,a));result=0;error=0
   if number==1:state['exit']=a[0];uc.emu_stop();return
   if number==5:self.assertEqual(readstr(a[0]),'/var/run/nook-eq/control');self.assertEqual(a[1],2);result=7
   elif number==6:self.assertEqual(a[0],7)
   elif number==3:
    self.assertEqual(a[0],0);chunk=stdin[state['read']:state['read']+min(17,a[2])];uc.mem_write(a[1],chunk);state['read']+=len(chunk);result=len(chunk)
   elif number==4:
    result=min(13,a[2]);state['stdout' if a[0]==1 else 'stderr'].extend(bytes(uc.mem_read(a[1],result)))
   elif number==54:
    self.assertEqual(a[0],7)
    if a[1]==0x40245103:uc.mem_write(a[2],struct.pack('>9I',0 if bad_abi else 0x45513130,1,generation,0,44100,16,2,0,0))
    elif a[1]==0x814c5101:
     state['sets'].append(bytes(uc.mem_read(a[2],332)))
     if reject:error=22
     else:generation+=1
    elif a[1]==0x414c5102:uc.mem_write(a[2],bytes([0x5a])*332)
    else:raise AssertionError(hex(a[1]))
   else:raise AssertionError(f'unexpected syscall {number}')
   uc.reg_write(UC_MIPS_REG_A3,1 if error else 0);uc.reg_write(UC_MIPS_REG_V0,error if error else result)
  u.hook_add(UC_HOOK_INTR,interrupt);u.emu_start(entry,0,count=1000000);self.assertIsNotNone(state['exit']);return state
 def test_status_and_get_binary_outputs(self):
  s=self.execute('status');self.assertEqual(s['exit'],0);self.assertEqual(len(s['stdout']),36);self.assertEqual(bytes(s['stdout'])[:4],b'EQ10')
  s=self.execute('get');self.assertEqual(s['exit'],0);self.assertEqual(s['stdout'],bytes([0x5a])*332)
 def test_set_consumes_exact_binary_and_queries_status(self):
  p=blob(make_program(dict(enabled=True,preamp_db=-6,bands=[])));s=self.execute('set',p)
  self.assertEqual(s['exit'],0);self.assertEqual(s['sets'],[p]);self.assertEqual(struct.unpack('>9I',s['stdout'])[2],1)
 def test_bad_abi_never_reads_or_writes_settings(self):
  s=self.execute('set',bytes(332),bad_abi=True);self.assertEqual(s['exit'],4);self.assertEqual(s['read'],0);self.assertEqual(s['sets'],[])
 def test_short_and_overlong_input_never_reaches_set(self):
  for data in [bytes(331),bytes(333)]:
   s=self.execute('set',data);self.assertEqual(s['exit'],5);self.assertEqual(s['sets'],[])
 def test_kernel_rejection_propagates_as_failure(self):
  s=self.execute('set',bytes(332),reject=True);self.assertEqual(s['exit'],6);self.assertEqual(s['stdout'],b'')
if __name__=='__main__':unittest.main(verbosity=2)
