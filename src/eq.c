#include "eq.h"
#define SIGNAL_LIMIT 2147483647 /* Q27: just under 16x full scale */
#define Q29_ONE 536870912
static int32_t round29(int64_t x) { return (int32_t)((x + ((int64_t)1<<28)) >> 29); }
static int32_t clamp_signal(int64_t x,struct eq_state *s) {
 if(x>SIGNAL_LIMIT){s->internal_clips++;return SIGNAL_LIMIT;}
 if(x< -SIGNAL_LIMIT){s->internal_clips++;return -SIGNAL_LIMIT;}
 return (int32_t)x;
}
void eq_reset(struct eq_state *s) {
 uint32_t i; uint8_t *p=(uint8_t *)s;
 for(i=0;i<sizeof(*s);i++)p[i]=0;
}
static int32_t sample(const struct eq_program *p,struct eq_state *s,int32_t x,uint32_t ch,uint32_t r) {
 uint32_t i;
 x=round29((int64_t)x*p->preamp);
 for(i=0;i<p->stages;i++){
  const struct eq_coeff *c=&p->coeff[r][i];
  struct eq_delay *d=&s->delay[ch][i];
  /* configure.py enforces sum(abs(coeff)) < 2^32. Signal/state
     magnitudes are <= 2^31-1, leaving room for rounding and error
     feedback in the signed 64-bit accumulator. */
  int64_t acc=(int64_t)c->b0*x+(int64_t)c->b1*d->x1+(int64_t)c->b2*d->x2
             -(int64_t)c->a1*d->y1-(int64_t)c->a2*d->y2+d->error;
  /* Clamp before narrowing; the rounded accumulator may exceed int32. */
  int32_t y=clamp_signal((acc+((int64_t)1<<28))>>29,s);
  /* Fraction saving avoids a DC limit cycle from repeated rounding. */
  int64_t residual=acc-(int64_t)y*Q29_ONE;
  d->error=(residual>= -((int64_t)1<<28)&&residual<((int64_t)1<<28))?(int32_t)residual:0;
  d->x2=d->x1;d->x1=x;d->y2=d->y1;d->y1=y;x=y;
 }
 return x;
}
int eq_process(const struct eq_program *p,struct eq_state *s,uint8_t *data,
               uint32_t bytes,uint32_t bits,uint32_t channels,uint32_t rate) {
 uint32_t width,frame,pos,ch,r;
 if(!p->enabled){eq_reset(s);return 0;}
 if((bits!=16&&bits!=24)||(channels!=1&&channels!=2)||(rate!=44100&&rate!=48000)
    ||p->stages>EQ_MAX_STAGES||p->preamp<0||p->preamp>Q29_ONE){eq_reset(s);return -1;}
 width=bits/8;frame=width*channels;
 if(bytes%frame){eq_reset(s);return -1;}
 if(s->rate!=rate||s->bits!=bits||s->channels!=channels){eq_reset(s);s->rate=rate;s->bits=bits;s->channels=channels;}
 r=rate==48000;
 for(pos=0;pos<bytes;pos+=frame)for(ch=0;ch<channels;ch++){
  uint8_t *v=data+pos+ch*width;int32_t x,y;uint32_t out;
  uint32_t raw=((uint32_t)v[0]<<16)|((uint32_t)v[1]<<8);
  if(bits==24)raw|=v[2];
  x=((int32_t)(raw^0x800000)-0x800000)*16;
  y=sample(p,s,x,ch,r);
  if(bits==16)y=(int32_t)(((int64_t)y+2048)>>12);
  else y=(int32_t)(((int64_t)y+8)>>4);
  int32_t max=bits==16?32767:8388607, min= -max-1;
  if(y>max){y=max;s->output_clips++;}else if(y<min){y=min;s->output_clips++;}
  out=(uint32_t)y;
  if(bits==16){v[0]=(uint8_t)(out>>8);v[1]=(uint8_t)out;}
  else {v[0]=(uint8_t)(out>>16);v[1]=(uint8_t)(out>>8);v[2]=(uint8_t)out;}
 }
 return 0;
}
