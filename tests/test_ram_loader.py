"""Model exact RAM loader syscalls, guards and cache/write ordering."""
import json,struct,unittest
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.mips_const import *
ROOT=Path(__file__).resolve().parents[1]
class RamLoaderTests(unittest.TestCase):
 def run_loader(self,mode,corrupt=None,flush_error=False,partial=False):
  u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_BIG_ENDIAN);u.ctl_set_cpu_model(UC_CPU_MIPS32_74KF);u.mem_map(0,0x2000000)
  with (ROOT/'build/ram-eq').open('rb') as f:
   elf=ELFFile(f);entry=elf['e_entry']
   for s in elf.iter_segments():
    if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
  stack=0x10ff000;u.mem_write(0x1100100,b'ram-eq\0');u.mem_write(0x1100200,mode.encode()+b'\0');u.mem_write(stack,struct.pack('>4I',2,0x1100100,0x1100200,0));u.reg_write(UC_MIPS_REG_SP,stack);u.reg_write(UC_MIPS_REG_A0,stack)
  mem=bytearray(0x1100000);stock=(ROOT/'firmware/gzimg.bin').read_bytes();mem[0x60000:0x60000+len(stock)]=stock
  def setword(a,v):struct.pack_into('>I',mem,a-0x80000000,v)
  setword(0x81007384,1);setword(0x810073b0,0x801e8528);setword(0x810073bc,0x801e8bc4)
  if corrupt=='arena':setword(0x803be368,1)
  if corrupt=='hook':setword(0x801f3370,0)
  if corrupt=='delay':setword(0x801f3374,0)
  if corrupt=='cache':setword(0x810073b0,0)
  if corrupt=='symbols':setword(0x803cc640,0)
  before=bytes(mem);events=[];exitcode=[]
  def interrupt(uc,n,data):
   self.assertEqual(n,17);nr=uc.reg_read(UC_MIPS_REG_V0);a=[uc.reg_read(r) for r in [UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2,UC_MIPS_REG_A3]];result=0;error=0
   if nr==1:exitcode.append(a[0]);uc.emu_stop();return
   if nr==5:
    self.assertEqual(bytes(uc.mem_read(a[0],24)),b'/var/run/nook-eq/rawmem\0');self.assertEqual(a[1],2 if mode in ['install-bypass','check-write-access'] else 0);result=7
   elif nr==6:self.assertEqual(a[0],7)
   elif nr==4:self.assertIn(a[0],[1,2]);result=a[2]
   elif nr==198:
    self.assertEqual(a[0],0);nr,fd,buffer=a[1:];self.assertIn(nr,[173,174]);self.assertEqual(fd,7)
    size,padding,hi,offset=struct.unpack('>4I',bytes(uc.mem_read(uc.reg_read(UC_MIPS_REG_SP)+16,16)));self.assertEqual(hi,0);self.assertEqual(padding,0)
    a=[fd,buffer,size,0]
    self.assertTrue(0x80000000<=offset<0x81100000);p=offset-0x80000000
    if nr==173:uc.mem_write(a[1],bytes(mem[p:p+a[2]]));result=a[2]
    else:
     self.assertEqual(a[1]%4,0);self.assertEqual(offset%4,0)
     result=a[2]-4 if partial and not any(x[0]=='write' for x in events) else a[2]
     mem[p:p+result]=bytes(uc.mem_read(a[1],result));events.append(('write',offset,result))
   elif nr==165:
    self.assertEqual(a[0],0);self.assertEqual(bytes(uc.mem_read(a[1],12)),struct.pack('>3I',0,0,3));events.append(('flush',));error=22 if flush_error else 0
   else:raise AssertionError(nr)
   uc.reg_write(UC_MIPS_REG_A3,bool(error));uc.reg_write(UC_MIPS_REG_V0,error or result)
  u.hook_add(UC_HOOK_INTR,interrupt);u.emu_start(entry,0,count=3000000);self.assertTrue(exitcode)
  return exitcode[0],events,mem,before
 def test_stock_memcpy_uses_one_aligned_store_for_hook_word(self):
  stock=(ROOT/'firmware/gzimg.bin').read_bytes()
  for src,dst in [(0x401000,0x803be368),(0x410000,0x801f3370)]:
   u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_BIG_ENDIAN);u.ctl_set_cpu_model(UC_CPU_MIPS32_74KF);u.mem_map(0,0x2000000)
   u.mem_write(0x2fe770,stock[0x29e770:0x29eb90]);u.mem_write(src,b'ABCD');writes=[]
   u.reg_write(UC_MIPS_REG_A0,dst);u.reg_write(UC_MIPS_REG_A1,src);u.reg_write(UC_MIPS_REG_A2,4);u.reg_write(UC_MIPS_REG_RA,0x1000)
   u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,access,address,size,value,data:writes.append((address,size)))
   u.emu_start(0x802fe770,0x1000,count=1000)
   self.assertEqual(writes,[(dst&0x1fffffff,4)]);self.assertEqual(bytes(u.mem_read(dst&0x1fffffff,4)),b'ABCD')
 def test_elf_layout_matches_legacy_loader_limits(self):
  for name in ['ram-eq','eqctl']:
   with (ROOT/'build'/name).open('rb') as f:
    e=ELFFile(f);loads=[s for s in e.iter_segments() if s['p_type']=='PT_LOAD']
    self.assertLessEqual(len(loads),2);self.assertEqual(loads[0]['p_offset'],0)
    self.assertEqual(loads[0]['p_vaddr'],0x400000)
    self.assertEqual(loads[1]['p_vaddr']%4096,0)
 def test_write_access_preflight_never_writes_or_flushes(self):
  code,events,mem,before=self.run_loader('check-write-access');self.assertEqual(code,0);self.assertEqual(events,[]);self.assertEqual(bytes(mem),before)
 def test_check_never_writes_or_flushes(self):
  code,events,mem,before=self.run_loader('check');self.assertEqual(code,0);self.assertEqual(events,[]);self.assertEqual(bytes(mem),before)
 def test_guards_reject_all_before_any_write(self):
  for bad in ['arena','hook','delay','cache','symbols']:
   with self.subTest(bad=bad):
    code,events,mem,before=self.run_loader('install-bypass',corrupt=bad);self.assertEqual(code,4);self.assertEqual(events,[]);self.assertEqual(bytes(mem),before)
 def test_flush_failure_prevents_writes(self):
  code,events,mem,before=self.run_loader('install-bypass',flush_error=True);self.assertEqual(code,5);self.assertEqual(events,[('flush',)]);self.assertEqual(bytes(mem),before)
 def test_install_writes_arena_then_atomic_hooks_with_cache_sync(self):
  code,events,mem,before=self.run_loader('install-bypass');self.assertEqual(code,0)
  image=(ROOT/'build/ram_image.bin').read_bytes();self.assertEqual(mem[0x3be368:0x3be368+len(image)],image)
  self.assertEqual(events[:3],[('flush',),('write',0x803be368,len(image)),('flush',)])
  manifest=json.loads((ROOT/'build/patch_manifest.json').read_text());hooks=[x for x in manifest['changes'] if x['kind'] in ('call','dispatch_pointer')]
  expected=bytearray(before);expected[0x3be368:0x3be368+len(image)]=image
  for i,h in enumerate(hooks):
   a=int(h['address'],16);self.assertEqual(events[3+i*2:5+i*2],[('write',a,4),('flush',)]);expected[a-0x80000000:a-0x80000000+4]=bytes.fromhex(h['after'])
  self.assertEqual(bytes(mem),bytes(expected));self.assertEqual(struct.unpack_from('>I',image,next(s['st_value'] for s in ELFFile((ROOT/'build/eq.elf').open('rb')).get_section_by_name('.symtab').iter_symbols() if s.name=='eq_program')-0x803be368)[0],0)
 def test_partial_arena_write_never_installs_hooks(self):
  code,events,mem,before=self.run_loader('install-bypass',partial=True);self.assertEqual(code,6);self.assertEqual(len(events),2)
 def test_bad_mode_never_opens_memory(self):
  code,events,mem,before=self.run_loader('nope');self.assertEqual(code,2);self.assertEqual(events,[]);self.assertEqual(bytes(mem),before)
if __name__=='__main__':unittest.main(verbosity=2)
