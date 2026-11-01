"""Prepare a persistent boot candidate locally. Never uploads/flashes a device."""
import argparse,hashlib,json,os,shutil,struct,subprocess,sys
from pathlib import Path
from ffs import FFS
from prepare_stock import prepare
from patch import patch
from repack import repack
ROOT=Path(__file__).resolve().parents[1]
OFFSET=0x36f394;SIZE=0xc03000

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--makefs',default=shutil.which('makefs'));args=ap.parse_args()
 if not args.makefs:raise SystemExit('Install NetBSD makefs or provide --makefs /path/to/makefs.')
 original=prepare();root=ROOT/'build/persistent-root'
 if root.exists():shutil.rmtree(root)
 root.mkdir(parents=True);entries=FFS(original[OFFSET:OFFSET+SIZE]).entries();inodes={};spec=[];expected={}
 kinds={0x4000:'dir',0x8000:'file',0xa000:'link',0x2000:'char',0x6000:'block',0x1000:'fifo',0xc000:'socket'}
 def line(path,typ,mode,uid,gid,extra=''):return ('.' if path=='.' else './'+path)+f' type={typ} mode={mode&0o7777:04o} uid={uid} gid={gid} time=1558752213.0'+extra
 for e in entries:
  path=e['path'];p=root/path;typ=kinds[e['mode']&0xf000];extra=''
  if typ=='dir':p.mkdir(parents=True,exist_ok=True)
  elif typ=='file':
   p.parent.mkdir(parents=True,exist_ok=True)
   if e['inode'] in inodes:os.link(inodes[e['inode']],p)
   else:p.write_bytes(e['data']);inodes[e['inode']]=p
   expected[path]=hashlib.sha256(e['data']).hexdigest()
  elif typ=='link':
   target=e['data'].decode();p.symlink_to(target);extra=' link='+target
  elif typ in ('char','block'):
   dev=e['rdev'];major=(dev>>8)&0xfff;minor=(dev&255)|((dev>>12)&0xfff00);extra=f' device=netbsd,{major},{minor}'
  spec.append(line(path,typ,e['mode'],e['uid'],e['gid'],extra))
 for path in ['usr/local','usr/local/sbin']:
  (root/path).mkdir(exist_ok=True);spec.append(line(path,'dir',0o755,0,0))
 additions={'usr/local/sbin/nook-http':ROOT/'bin/nook-http','usr/local/sbin/eqctl':ROOT/'bin/eqctl','etc/rc.d/nook':ROOT/'src/nook.rc'}
 for path,source in additions.items():
  data=source.read_bytes();(root/path).write_bytes(data);spec.append(line(path,'file',0o755,0,0));expected[path]=hashlib.sha256(data).hexdigest()
 spec_path=ROOT/'build/persistent.mtree';spec_path.write_text('\n'.join(spec)+'\n')
 ffs=ROOT/'build/persistent.ffs'
 subprocess.run([args.makefs,'-B','be','-s',str(SIZE),'-o','bsize=4096,fsize=512,version=1','-F',str(spec_path),str(ffs),str(root)],check=True)
 filesystem=ffs.read_bytes()
 if len(filesystem)!=SIZE:raise ValueError('Root filesystem size changed')
 actual=FFS(filesystem).entries();files={e['path']:hashlib.sha256(e['data']).hexdigest() for e in actual if e['mode']&0xf000==0x8000}
 if files!=expected:raise ValueError('Rebuilt filesystem does not reproduce every original/new regular file')
 old={e['path']:e for e in entries};new={e['path']:e for e in actual}
 for path,e in old.items():
  for key in ['mode','uid','gid']:
   if e[key]!=new[path][key]:raise ValueError(f'Metadata changed: {path} {key}')
  if e['mode']&0xf000 in (0x2000,0x6000) and e['rdev']!=new[path]['rdev']:raise ValueError('Device number changed')
  if e['mode']&0xf000==0xa000 and e['data']!=new[path]['data']:raise ValueError('Symlink changed')
 groups={}
 for e in entries:
  if e['mode']&0xf000==0x8000:groups.setdefault(e['inode'],[]).append(e['path'])
 if any(len({new[path]['inode'] for path in paths})!=1 for paths in groups.values()):raise ValueError('Original hardlink group split')
 raw,manifest=patch(original,ROOT/'build/eq.elf');raw=bytearray(raw);raw[OFFSET:OFFSET+SIZE]=filesystem
 stock=(ROOT/'firmware/7.8.1.basebinary').read_bytes();image,report=repack(stock,raw)
 if len(image)-72>0x6fffe0:raise ValueError('Candidate exceeds bank capacity')
 (ROOT/'build/nook-persistent-7.8.1.basebinary').write_bytes(image)
 report.update(stage='UNBOOTED PERSISTENT CANDIDATE — not a tested firmware release',original_entries=len(entries),new_entries=len(actual),all_original_file_bytes_preserved=True,original_modes_owners_symlinks_devices_preserved=True,firmware_uploaded=False,settings_after_reboot='Restores the last valid profile saved by the device web UI; first boot starts in bypass.',new_files=list(additions))
 (ROOT/'build/persistent_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
