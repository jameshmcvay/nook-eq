"""Fetch/build the maintainer's portable NetBSD makefs locally; no device writes."""
import argparse,hashlib,os,subprocess,tarfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
URL='https://www.daemonology.net/makefs/makefs-20040704.tar.gz'
def main():
 build=ROOT/'build';build.mkdir(exist_ok=True);archive=build/'makefs-20040704.tar.gz'
 if not archive.exists():
  with urllib.request.urlopen(URL,timeout=45) as r:data=r.read(2*1024*1024)
  # Upstream publishes this archive's digest; retain a stronger local digest too.
  if hashlib.sha256(data).hexdigest()!='92f7d602709d578baadf6db4c522383fd5bb52a01cd8c5aed229f217a2f44836':raise ValueError('makefs source digest mismatch')
  archive.write_bytes(data)
 with tarfile.open(archive) as tar:
  for m in tar.getmembers():
   if m.name.startswith('/') or '..' in Path(m.name).parts or m.issym() or m.islnk():raise ValueError('Unsafe archive member')
  tar.extractall(build,filter='data')
 source=build/'makefs-20040704'
 # Compatibility-only host fixes; no filesystem algorithms are changed.
 p=source/'netbsdsrc/tools/compat/configure';p.write_text(p.read_text().replace('sys/mman.h sys/mtio.h sys/param.h','sys/mman.h sys/param.h'))
 p=source/'netbsdsrc/usr.sbin/mtree/spec.c';p.write_text(p.read_text().replace('#include "extern.h"','#include "extern.h"\nextern const char *group_from_gid(gid_t, int);'))
 p=source/'netbsdsrc/usr.sbin/makefs/ffs/ffs_alloc.c';p.write_text(p.read_text().replace('DIP(ip, blocks) += size / DEV_BSIZE;','if (ip->i_fs->fs_magic == FS_UFS1_MAGIC) ip->i_ffs1_blocks += size / DEV_BSIZE; else ip->i_ffs2_blocks += size / DEV_BSIZE;'))
 with (build/'makefs-build.log').open('w') as log:subprocess.run(['sh','build.sh'],cwd=source,env=dict(os.environ,CFLAGS='-O -std=gnu89 -Wno-implicit-function-declaration'),stdout=log,stderr=log,check=True)
 binary=source/'netbsdsrc/tools/makefs/makefs'
 if not binary.exists():raise RuntimeError('makefs build did not produce the tool; inspect build/makefs-build.log')
 print(binary)
if __name__=='__main__':main()
