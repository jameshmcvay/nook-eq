'use strict';
const NookEQ=(()=>{
 const Q=2**29;
 function rounded(v){const lo=Math.floor(v),f=v-lo;return f<.5?lo:f>.5?lo+1:lo%2===0?lo:lo+1;}
 function program(config){
  if(!config||typeof config.enabled!=='boolean'||!Number.isFinite(config.preamp_db)||config.preamp_db< -60||config.preamp_db>0||!Array.isArray(config.bands)||config.bands.length>8)throw Error('Use up to eight bands and a preamp between −60 and 0 dB.');
  const buffer=new ArrayBuffer(332),data=new DataView(buffer);let index=0;
  const word=v=>{data.setInt32(index,v,false);index+=4;};
  word(Number(config.enabled));word(config.bands.length);word(rounded(10**(config.preamp_db/20)*Q));
  for(const rate of [44100,48000]){
   for(const b of config.bands){
    const f=b.frequency_hz,g=b.gain_db,q=b.q;
    if(b.type!=='peaking'||![f,g,q].every(Number.isFinite)||f<10||f>=22050||g< -12||g>12||q<.1||q>20)throw Error('Bands: 10–22049 Hz, ±12 dB, Q 0.1–20.');
    const A=10**(g/40),w=2*Math.PI*f/rate,alpha=Math.sin(w)/(2*q),a0=1+alpha/A;
    const c=[(1+alpha*A)/a0,-2*Math.cos(w)/a0,(1-alpha*A)/a0,-2*Math.cos(w)/a0,(1-alpha/A)/a0].map(x=>rounded(x*Q));
    if(c.some(x=>x< -(2**31)||x>=2**31)||c.reduce((sum,x)=>sum+Math.abs(x),0)>=2**32||c[4]<=-Q||c[4]>=Q||Q+c[3]+c[4]<=0||Q-c[3]+c[4]<=0)throw Error('This band is outside the stable fixed-point range. Reduce its gain or Q.');
    c.forEach(word);
   }
   for(let i=config.bands.length;i<8;i++)for(let j=0;j<5;j++)word(0);
  }
  return new Uint8Array(buffer);
 }
 function equal(a,b){return a&&b&&a.length===b.length&&a.every((v,i)=>v===b[i]);}
 function decode(bytes){
  if(bytes.length!==332)throw Error('Unexpected EQ program.');const d=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  const enabled=d.getUint32(0),stages=d.getUint32(4),preamp=d.getInt32(8);
  if(enabled>1||stages>8||preamp<0||preamp>Q)throw Error('Unexpected EQ program.');
  const coeff=[0,1].map(r=>Array.from({length:stages},(_,i)=>Array.from({length:5},(_,j)=>d.getInt32(12+(r*40+i*5+j)*4)/Q)));
  return {enabled:!!enabled,stages,preamp:preamp/Q,coeff};
 }
 function curve(bytes,rate){const p=decode(bytes),r=rate===48000?1:0;
  return Array.from({length:241},(_,i)=>{const f=20*1100**(i/240),w=2*Math.PI*f/rate,c=Math.cos(w),s=-Math.sin(w),c2=Math.cos(2*w),s2=-Math.sin(2*w);let h=p.enabled?p.preamp:1;
   if(p.enabled)for(const [b0,b1,b2,a1,a2] of p.coeff[r])h*=Math.hypot(b0+b1*c+b2*c2,b1*s+b2*s2)/Math.hypot(1+a1*c+a2*c2,a1*s+a2*s2);
   return [f,20*Math.log10(Math.max(h,1e-12))];});
 }
 return {program,equal,decode,curve};
})();
if(typeof module!=='undefined')module.exports=NookEQ;
