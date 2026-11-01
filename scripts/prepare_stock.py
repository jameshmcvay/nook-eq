"""Fetch the exact Apple input locally. Never redistributes firmware or writes devices."""
import gzip,hashlib,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import bb
URL='https://apsu.apple.com/data/115/041-48470-20190619-3ce2e81d-ac38-447e-8ca3-fdb3a4a09b91/7.8.1.basebinary'
SHA='56707780d126396ec5c217cafcb40f61850c94087f12693085fdf81ee9ac4eb6'
RAW_SHA='266d5ec54f5993d780af3befee2d67c9a64deda89b1f5c25a53765f87cb96b19'
def prepare():
 folder=ROOT/'firmware';folder.mkdir(exist_ok=True);path=folder/'7.8.1.basebinary'
 if not path.exists():
  print('Downloading stock Apple A1392 firmware (local build input only).',flush=True)
  with urllib.request.urlopen(URL,timeout=45) as r:data=r.read(6098301)
  if hashlib.sha256(data).hexdigest()!=SHA:raise ValueError('Stock download checksum mismatch')
  path.write_bytes(data)
 data=path.read_bytes()
 if hashlib.sha256(data).hexdigest()!=SHA:raise ValueError('Not the audited stock 7.8.1 image')
 payload=bb.parse(bb.parse(data,False),False);raw=gzip.decompress(payload[0x57a0:])
 if hashlib.sha256(raw).hexdigest()!=RAW_SHA:raise ValueError('Unexpected stock kernel hash')
 (folder/'gzimg.bin').write_bytes(raw);return raw
if __name__=='__main__':prepare();print('Verified stock input ready under firmware/.')
