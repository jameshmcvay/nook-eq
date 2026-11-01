"""Create a reviewable raw firmware candidate; never writes to a device."""
import hashlib,json,struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
ORIGINAL_SHA256='266d5ec54f5993d780af3befee2d67c9a64deda89b1f5c25a53765f87cb96b19'
BASE=0x80060000;LO=0x803be368;HI=0x803cc640
HOOKS=[(0x801f3370,0x8015f2f0,'eq_uiomove'),(0x801f3d98,0x801f3844,'eq_dma_init'),
 (0x801f3068,0x801f1e98,'eq_clock40_44100'),(0x801f3100,0x801f1e98,'eq_clock40_48000'),
 (0x801f3138,0x801f20c4,'eq_clock25_44100'),(0x801f3160,0x801f20c4,'eq_clock25_48000')]
POINTER_HOOKS=[(0x8030fc40,0x801f3d18,'eq_open'),(0x8030fc44,0x801f3e68,'eq_close'),(0x8030fc50,0x801f2928,'eq_ioctl')]
def sha(b):return hashlib.sha256(b).hexdigest()
def jal(target,pc):
 if target%4 or (target>>28)!=((pc+4)>>28):raise ValueError('JAL target is not reachable')
 return struct.pack('>I',(3<<26)|((target>>2)&0x3ffffff))
def patch(original,elf_path):
 if sha(original)!=ORIGINAL_SHA256:raise ValueError('Input is not the audited A1392 7.8.1 raw image')
 if any(original[LO-BASE:HI-BASE]):raise ValueError('Reserved tail is not zero-filled')
 out=bytearray(original);changes=[];ranges=[]
 with open(elf_path,'rb') as f:
  elf=ELFFile(f)
  if elf.elfclass!=32 or elf.little_endian or elf['e_machine']!='EM_MIPS':raise ValueError('Expected big-endian MIPS32 ELF')
  symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
  for section in elf.iter_sections():
   if not section['sh_flags']&2 or not section['sh_size']:continue
   a,n=section['sh_addr'],section['sh_size']
   if not LO<=a<a+n<=HI:raise ValueError(f'Section {section.name} leaves the reserved tail')
   if any(a<end and a+n>start for start,end in ranges):raise ValueError('ELF section overlap')
   ranges.append((a,a+n));data=bytes(n) if section['sh_type']=='SHT_NOBITS' else section.data()
   if len(data)!=n:raise ValueError('Invalid section length')
   out[a-BASE:a-BASE+n]=data
   changes.append(dict(kind='section',name=section.name,address=hex(a),file_offset=hex(a-BASE),size=n,sha256=sha(data),original='all zero'))
  for address,old,label in HOOKS:
   offset=address-BASE;before=original[offset:offset+4];expected=jal(old,address)
   if before!=expected:raise ValueError(f'Stock instruction mismatch at {address:#x}')
   after=jal(symbols[label],address);out[offset:offset+4]=after
   changes.append(dict(kind='call',name=label,address=hex(address),file_offset=hex(offset),size=4,before=before.hex(),after=after.hex(),original_target=hex(old),patched_target=hex(symbols[label]),delay_slot=original[offset+4:offset+8].hex()))
  for address,old,label in POINTER_HOOKS:
   offset=address-BASE;before=original[offset:offset+4]
   if before!=struct.pack('>I',old):raise ValueError(f'Device dispatch mismatch at {address:#x}')
   after=struct.pack('>I',symbols[label]);out[offset:offset+4]=after
   changes.append(dict(kind='dispatch_pointer',name=label,address=hex(address),file_offset=hex(offset),size=4,before=before.hex(),after=after.hex(),original_target=hex(old),patched_target=hex(symbols[label])))
 # Inverse the entire patch and demand the exact original hash.
 restored=bytearray(out);restored[LO-BASE:HI-BASE]=bytes(HI-LO)
 for item in changes:
  if item['kind'] in ('call','dispatch_pointer'):
   offset=int(item['file_offset'],16);restored[offset:offset+4]=bytes.fromhex(item['before'])
 if bytes(restored)!=original:raise AssertionError('Patch changes bytes outside its manifest')
 manifest=dict(status='OFFLINE CANDIDATE — not approved for device installation',original_sha256=sha(original),patched_sha256=sha(out),raw_size=len(out),arena=[hex(LO),hex(HI)],arena_used_bytes=max(e for a,e in ranges)-LO,patch_elf_sha256=sha(Path(elf_path).read_bytes()),changes=changes,reverse_patch_verified=True,
  unverified=['physical L/R mapping and complete 24-bit hardware behavior','multi-writer concurrency','board timing and cache behavior','full-board boot and firmware acceptance','recovery procedure','on-device runtime control transport verification'])
 return bytes(out),manifest
if __name__=='__main__':
 b,m=patch((ROOT/'firmware/gzimg.bin').read_bytes(),ROOT/'build/eq.elf')
 (ROOT/'build/candidate-gzimg.bin').write_bytes(b);(ROOT/'build/patch_manifest.json').write_text(json.dumps(m,indent=2)+'\n')
 print(f'Candidate: {len(b)} bytes, EQ arena use {m["arena_used_bytes"]} bytes. Exact inverse verified.')
