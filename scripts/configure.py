"""Generate deterministic Q29 EQ coefficients for the firmware's two rates.
Peaking EQ uses Robert Bristow-Johnson's Audio EQ Cookbook equations.
"""
import argparse,cmath,json,math,struct
from pathlib import Path
Q=1<<29

def coefficients(band,rate):
 kind=band['type'];f=float(band['frequency_hz']);gain=float(band['gain_db']);q=float(band['q'])
 if kind!='peaking':raise ValueError('Supported band type: peaking')
 if not all(math.isfinite(x) for x in (f,gain,q)) or not (10<=f<rate/2 and -12<=gain<=12 and .1<=q<=20):
  raise ValueError('Band limits: 10 Hz..Nyquist, gain +/-12 dB, Q 0.1..20')
 A=10**(gain/40);w=2*math.pi*f/rate;alpha=math.sin(w)/(2*q);a0=1+alpha/A
 c=[(1+alpha*A)/a0,-2*math.cos(w)/a0,(1-alpha*A)/a0,-2*math.cos(w)/a0,(1-alpha/A)/a0]
 quant=[round(x*Q) for x in c]
 if any(not -(1<<31)<=x<(1<<31) for x in quant):raise ValueError('Coefficient exceeds Q29 range')
 if sum(abs(x) for x in quant)>=(1<<32):raise ValueError('Coefficient sum exceeds accumulator headroom')
 a1,a2=quant[3]/Q,quant[4]/Q;disc=cmath.sqrt(a1*a1-4*a2)
 poles=[(-a1+disc)/2,(-a1-disc)/2]
 if max(abs(x) for x in poles)>=1:raise ValueError('Quantized filter is unstable')
 return quant

def make_program(config):
 enabled=config['enabled']
 if not isinstance(enabled,bool):raise ValueError('enabled must be boolean')
 gain=float(config['preamp_db']);bands=config['bands']
 if not math.isfinite(gain) or not -60<=gain<=0:raise ValueError('Preamp range: -60..0 dB')
 if not isinstance(bands,list) or len(bands)>8:raise ValueError('At most eight bands')
 preamp=round(10**(gain/20)*Q)
 coeff=[[coefficients(b,r) for b in bands] for r in (44100,48000)]
 return dict(enabled=int(enabled),stages=len(bands),preamp=preamp,coeff=coeff)

def blob(program,endian='>'):
 words=[program['enabled'],program['stages'],program['preamp']]
 for rate in program['coeff']:
  for stage in rate:words.extend(stage)
  words.extend([0]*((8-len(rate))*5))
 return struct.pack(endian+'II'+'i'*(len(words)-2),*words)

def response(program,rate_index,freq):
 z=cmath.exp(-2j*math.pi*freq/(44100,48000)[rate_index]);h=program['preamp']/Q
 for c in program['coeff'][rate_index]:
  b0,b1,b2,a1,a2=[x/Q for x in c];h*=(b0+b1*z+b2*z*z)/(1+a1*z+a2*z*z)
 return h

def main():
 ap=argparse.ArgumentParser();ap.add_argument('config');ap.add_argument('--out',default='build/program');a=ap.parse_args()
 cfg=json.loads(Path(a.config).read_text());p=make_program(cfg);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 out.with_suffix('.bin').write_bytes(blob(p));out.with_suffix('.json').write_text(json.dumps(p,indent=2)+'\n')
 lines=['#include "eq.h"','const struct eq_program eq_program = {',f' {p["enabled"]}, {p["stages"]}, {p["preamp"]}, {{']
 for rate in p['coeff']:
  lines.append('  {'+', '.join('{'+','.join(map(str,c))+'}' for c in rate)+'},')
 lines.extend([' }','};']);out.with_suffix('.c').write_text('\n'.join(lines)+'\n')
 peaks={str(rate):20*math.log10(max(abs(response(p,i,rate*k/32768)) for k in range(16385))) for i,rate in enumerate((44100,48000))}
 report=dict(config=cfg,coefficient_fraction_bits=29,peak_frequency_response_db=peaks,
 note='Frequency-response peak is not a worst-case transient bound; clipping counters and stress tests are required.')
 out.with_suffix('.report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
