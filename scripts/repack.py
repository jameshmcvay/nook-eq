"""Repack an offline candidate using the stock gzip stub and both envelopes.
No network/device writes. Image acceptance and recovery remain separate gates.
"""
import gzip,hashlib,json,struct,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import bb
from Crypto.Cipher import AES

def compose(template,plaintext):
 header=template[:bb.HDR.size];magic,b0f,model,version,b18,b19,b1a,flags,unk=bb.HDR.unpack(header)
 if magic!=bb.MAGIC:raise ValueError('Bad envelope template')
 checksum=struct.pack('>I',zlib.adler32(header+plaintext)&0xffffffff)
 if flags&2:
  key=bb.derive_key(model);iv=bb.MAGIC+bytes([b0f]);out=[]
  for pos in range(0,len(plaintext),0x8000):
   block=plaintext[pos:pos+0x8000];n=len(block)&~15
   out.append(AES.new(key,AES.MODE_CBC,iv).encrypt(block[:n])+block[n:])
  encrypted=b''.join(out)
 else:encrypted=plaintext
 return header+encrypted+checksum

def repack(stock,candidate):
 inner=bb.parse(stock,False);payload=bb.parse(inner,False)
 # Prove inverse composition against the entire untouched original first.
 if compose(inner,payload)!=inner or compose(stock,inner)!=stock:raise AssertionError('Stock envelope round-trip failed')
 off=0x57a0
 if payload[off:off+3]!=b'\x1f\x8b\x08':raise ValueError('Unexpected stock gzip header')
 flags=payload[off+3];header_end=off+10
 if flags&0xe0:raise ValueError('Invalid gzip flags')
 if flags&4:
  extra=struct.unpack_from('<H',payload,header_end)[0];header_end+=2+extra
 for flag in (8,16):
  if flags&flag:header_end=payload.index(b'\0',header_end)+1
 if flags&2:header_end+=2
 if header_end>=len(payload):raise ValueError('Truncated gzip header')
 old=zlib.decompressobj(31);original=old.decompress(payload[off:])+old.flush()
 if not old.eof or any(old.unused_data):raise ValueError('Invalid stock gzip boundary')
 if len(candidate)!=len(original) or len(candidate)>0x1400000:raise ValueError('Candidate violates stock raw image size/buffer bound')
 compressor=zlib.compressobj(9,zlib.DEFLATED,-15)
 gz=payload[off:header_end]+compressor.compress(candidate)+compressor.flush()+struct.pack('<II',zlib.crc32(candidate)&0xffffffff,len(candidate)&0xffffffff)
 new_payload=payload[:off]+gz
 new_payload+=bytes((-len(new_payload))%4)
 # Stock BootDecompress uses a 10 MiB default compressed-input window.
 if len(new_payload)-off>0xa00000:raise ValueError('Compressed payload exceeds boot input window')
 output=compose(stock,compose(inner,new_payload))
 decoded=bb.parse(bb.parse(output,False),False)
 if decoded[:off]!=payload[:off]:raise AssertionError('Boot stub changed')
 if gzip.decompress(decoded[off:])!=candidate:raise AssertionError('Independent gzip decode mismatch')
 return output,dict(status='OFFLINE CANDIDATE — firmware acceptance and recovery unverified',
  original_envelope_roundtrip_exact=True,nested_adler32_verified=True,gzip_crc_and_size_verified=True,
  boot_stub_unchanged=True,raw_size=len(candidate),gzip_offset=hex(off),gzip_size=len(gz),image_size=len(output),
  stock_image_size=len(stock),size_change=len(output)-len(stock),zlib_version=zlib.ZLIB_VERSION,
  sha256=hashlib.sha256(output).hexdigest(),raw_sha256=hashlib.sha256(candidate).hexdigest(),
  not_proven=['flash partition capacity','bootloader or updater acceptance','complete board boot','device recovery'])

if __name__=='__main__':
 stock=(ROOT/'firmware/7.8.1.basebinary').read_bytes();raw=(ROOT/'build/candidate-gzimg.bin').read_bytes()
 output,report=repack(stock,raw)
 (ROOT/'build/candidate-7.8.1.basebinary').write_bytes(output);(ROOT/'build/repack_report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
