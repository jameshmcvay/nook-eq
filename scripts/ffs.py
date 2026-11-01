"""Bounded reader for the audited big-endian UFS1 root image."""
import struct
class FFS:
 def __init__(self,data):
  self.data=data;self.sb=8192
  if self.u32(self.sb+1372)!=0x11954:raise ValueError('Expected big-endian UFS1')
  self.iblk,self.cgoff,self.cgmask=[self.u32(self.sb+x) for x in (16,24,28)]
  self.bs,self.fs,self.ipg,self.fpg=[self.u32(self.sb+x) for x in (48,52,184,188)]
  if (self.bs,self.fs)!=(4096,512):raise ValueError('Unexpected filesystem block sizes')
 def u32(self,p):return struct.unpack_from('>I',self.data,p)[0]
 def inode(self,n):
  cg=n//self.ipg;p=(cg*self.fpg+self.cgoff*(cg&~self.cgmask)+self.iblk)*self.fs+(n%self.ipg)*128
  if p<0 or p+128>len(self.data):raise ValueError('Invalid inode location')
  return p
 def content(self,n):
  p=self.inode(n);mode=struct.unpack_from('>H',self.data,p)[0];size=struct.unpack_from('>Q',self.data,p+8)[0]
  if size>len(self.data):raise ValueError('File exceeds image')
  if mode&0xf000==0xa000 and size<60:return self.data[p+40:p+40+size]
  ptr=list(struct.unpack_from('>15I',self.data,p+40));blocks=ptr[:12]
  def indirect(a,depth):
   if not a:return [0]*((self.bs//4)**depth)
   if a*self.fs+self.bs>len(self.data):raise ValueError('Invalid indirect extent')
   words=struct.unpack_from('>1024I',self.data,a*self.fs)
   if depth==1:return words
   out=[]
   for word in words:
    out.extend(indirect(word,depth-1))
    if len(out)*self.bs>=size:break
   return out
  for depth,a in enumerate(ptr[12:],1):
   if len(blocks)*self.bs>=size:break
   blocks.extend(indirect(a,depth))
  out=bytearray()
  for a in blocks:
   take=min(self.bs,size-len(out))
   if take<=0:break
   if a*self.fs+take>len(self.data):raise ValueError('Invalid file extent')
   out.extend(self.data[a*self.fs:a*self.fs+take] if a else bytes(take))
  if len(out)!=size:raise ValueError('Truncated file')
  return bytes(out)
 def entries(self):
  out=[]
  def visit(n,path,ancestors=()):
   if n in ancestors:raise ValueError('Directory cycle')
   p=self.inode(n);mode=struct.unpack_from('>H',self.data,p)[0];typ=mode&0xf000
   entry=dict(path=path,inode=n,mode=mode,uid=self.u32(p+112),gid=self.u32(p+116),rdev=self.u32(p+40))
   if typ in (0x4000,0x8000,0xa000):entry['data']=self.content(n)
   out.append(entry)
   if typ==0x4000:
    data=entry['data'];pos=0
    while pos<len(data):
     ino,reclen,ft,nlen=struct.unpack_from('>IHBB',data,pos)
     if reclen<8 or reclen%4 or pos+reclen>len(data) or nlen>reclen-8:raise ValueError('Invalid directory')
     name=data[pos+8:pos+8+nlen].decode('ascii');pos+=reclen
     if not ino or name in ('.','..'):continue
     if not name or '/' in name or '\0' in name:raise ValueError('Unsafe path')
     visit(ino,name if path=='.' else path+'/'+name,ancestors+(n,))
  visit(2,'.');return out
