"""Rebuild the MIPS kernel payload and utilities. No device operations."""
import argparse,hashlib,json,os,struct,subprocess,sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
from configure import make_program,blob
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT)
BUILD=ROOT/'build';BUILD.mkdir(exist_ok=True)
ENV=dict(os.environ,ZIG_LOCAL_CACHE_DIR=str(BUILD/'zig-cache'),ZIG_GLOBAL_CACHE_DIR=str(BUILD/'zig-global-cache'))
def compile(out,inputs,*,kernel=False,includes=()):
 args=[sys.executable,'-m','ziglang','cc','-target','mips-freestanding','-march='+('mips32r2' if kernel else 'mips1'),'-msoft-float','-mno-abicalls','-fno-pic','-G0','-ffreestanding','-fno-builtin','-fno-stack-protector','-O2','-g0','-ffile-prefix-map='+str(ROOT)+'=.','-Isrc','-Ibuild',*includes,'-nostdlib','-Wl,-T,src/'+('eq.ld' if kernel else 'eqctl.ld'),'-Wl,-e,'+('eq_uiomove' if kernel else '__start'),'-Wl,--no-undefined','-Wl,--build-id=none',*inputs,'-o','build/'+out]
 subprocess.run(args,env=ENV,check=True)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--release-binaries',action='store_true');a=ap.parse_args()
 p=make_program(dict(enabled=False,preamp_db=0,bands=[]))
 (BUILD/'factory.c').write_text('#include "eq.h"\nconst struct eq_program eq_program={0,0,536870912,{{{0}}}};\n')
 compile('eq.elf',['src/entry.S','src/eq.c','src/kernel_hook.c','src/runtime.c','build/factory.c'],kernel=True)
 with (BUILD/'eq.elf').open('rb') as f:
  elf=ELFFile(f);syms={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()};sections=[s for s in elf.iter_sections() if s['sh_flags']&2 and s['sh_size']]
  lo,hi=0x803be368,0x803cc640;end=max(s['sh_addr']+s['sh_size'] for s in sections)
  if any(not lo<=s['sh_addr']<s['sh_addr']+s['sh_size']<=hi for s in sections):raise ValueError('Payload leaves arena')
  arena=bytearray(end-lo)
  for s in sections:arena[s['sh_addr']-lo:s['sh_addr']-lo+s['sh_size']]=bytes(s['sh_size']) if s['sh_type']=='SHT_NOBITS' else s.data()
 (BUILD/'ram_image.bin').write_bytes(arena)
 layout=json.loads((ROOT/'src/layout.json').read_text());hooks=[h for h in layout['changes'] if h['kind'] in ('call','dispatch_pointer')]
 lines=['#define ARENA_START 0x803be368u',f'#define ARENA_BYTES {hi-lo}u',f'#define IMAGE_BYTES {len(arena)}u',f'#define HOOK_COUNT {len(hooks)}u','struct hook {uint32_t address,before,after,delay;};','static const struct hook hooks[HOOK_COUNT]={']
 for h in hooks:
  target=syms[h['name']];after=(3<<26)|((target>>2)&0x3ffffff) if h['kind']=='call' else target
  lines.append('{'+','.join([h['address']+'u','0x'+h['before']+'u',hex(after)+'u','0x'+h.get('delay_slot','00000000')+'u'])+'},')
 lines+=['};','static const uint32_t arena_image[IMAGE_BYTES/4]={']
 for i in range(0,len(arena),32):lines.append(','.join(hex(v)+'u' for v in struct.unpack('>'+str(len(arena[i:i+32])//4)+'I',arena[i:i+32]))+',')
 (BUILD/'ram_image.h').write_text('\n'.join(lines+['};'])+'\n')
 compile('ram-eq',['src/syscalls.S','src/ram_io.S','src/ram_eq.c'])
 compile('eqctl',['src/syscalls.S','src/eqctl.c'])
 assets=[('/', 'index.html','text/html; charset=utf-8'),('/style.css','style.css','text/css; charset=utf-8'),('/app.js','app.js','text/javascript; charset=utf-8'),('/coeff.js','coeff.js','text/javascript; charset=utf-8'),('/presets.js','presets.js','text/javascript; charset=utf-8'),('/jhm.svg','jhm.svg','image/svg+xml')]
 lines=['struct asset {const char *path,*type;const unsigned char *data;unsigned size;};'];items=[]
 for i,(url,name,ctype) in enumerate(assets):
  data=(ROOT/'web'/name).read_bytes();lines.append(f'static const unsigned char asset_{i}[]={{'+','.join(map(str,data))+'};');items.append('{'+json.dumps(url)+','+json.dumps(ctype)+f',asset_{i},sizeof asset_{i}'+'}')
 lines.append('static const struct asset assets[]={'+','.join(items)+'};');lines.append(f'#define ASSET_COUNT {len(items)}u');(BUILD/'http_assets.h').write_text('\n'.join(lines)+'\n')
 compile('nook-http',['src/syscalls.S','src/http_io.S','src/http.c'])
 if (ROOT/'firmware/gzimg.bin').exists():
  from patch import patch
  _,details=patch((ROOT/'firmware/gzimg.bin').read_bytes(),BUILD/'eq.elf');(BUILD/'patch_manifest.json').write_text(json.dumps(details,indent=2)+'\n')
 manifest={n:dict(sha256=hashlib.sha256((BUILD/n).read_bytes()).hexdigest(),bytes=(BUILD/n).stat().st_size) for n in ['ram-eq','eqctl','nook-http']}
 (BUILD/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (BUILD/'ram_manifest.json').write_text(json.dumps(dict(loader_sha256=manifest['ram-eq']['sha256'],initial_bypass=True),indent=2)+'\n')
 (BUILD/'http_build.json').write_text(json.dumps(manifest['nook-http'],indent=2)+'\n')
 if a.release_binaries:
  import shutil
  for name in [*manifest,'manifest.json','ram_manifest.json','http_build.json']:shutil.copy2(BUILD/name,ROOT/'bin'/name)
 print('Built guarded RAM payload and device tools. No device writes.')
if __name__=='__main__':main()
