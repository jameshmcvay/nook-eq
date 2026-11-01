#include "runtime.h"
extern const struct eq_program eq_program;
extern struct eq_state eq_kernel_state;
extern volatile uint32_t eq_sample_rate;
static struct eq_program requested,active;
static uint32_t requested_generation,applied_generation,pending,initialized;
/* AR9344 is a uniprocessor. Interrupt exclusion protects short copies of
   settings; it is never held over DSP processing or user-memory access. */
static uint32_t enter(void){
#ifdef __mips__
 uint32_t saved;
 __asm__ volatile("di %0\n\tehb" : "=r"(saved) : : "memory");
 return saved;
#else
 return 0;
#endif
}
static void leave(uint32_t saved){
#ifdef __mips__
 __asm__ volatile("mtc0 %0,$12\n\tehb" : : "r"(saved) : "memory");
#else
 (void)saved;
#endif
}
static void copy_program(struct eq_program *to,const struct eq_program *from){
 /* Avoid a compiler-generated libc call in the freestanding kernel patch. */
 uint32_t i;uint8_t *d=(uint8_t *)to;const uint8_t *s=(const uint8_t *)from;
 for(i=0;i<sizeof(*to);i++)d[i]=s[i];
}
static int valid(const struct eq_program *p){
 const int64_t one=(int64_t)1<<29;
 if(p->enabled>1||p->stages>EQ_MAX_STAGES||p->preamp<0||p->preamp>one)return 0;
 for(uint32_t rate=0;rate<EQ_RATE_COUNT;rate++)for(uint32_t i=0;i<p->stages;i++){
  const struct eq_coeff *c=&p->coeff[rate][i];
  int64_t values[5]={c->b0,c->b1,c->b2,c->a1,c->a2};uint64_t sum=0;
  for(uint32_t j=0;j<5;j++)sum+=(uint64_t)(values[j]<0?-values[j]:values[j]);
  if(sum>=((uint64_t)1<<32))return 0;
  /* Jury's criterion for 1 + a1*z^-1 + a2*z^-2. */
  if(c->a2<=-one||c->a2>=one||one+c->a1+c->a2<=0||one-c->a1+c->a2<=0)return 0;
 }
 return 1;
}
const struct eq_program *eq_begin_buffer(void){
 uint32_t reset=0,saved=enter();
 if(!initialized){copy_program(&active,&eq_program);initialized=1;}
 if(pending){copy_program(&active,&requested);applied_generation=requested_generation;pending=0;reset=1;}
 leave(saved);
 if(reset)eq_reset(&eq_kernel_state);
 return &active;
}
int eq_control(uint32_t command,void *data,uint32_t flags){
 if(command==EQ_IOC_SET){
  if(!(flags&2))return 9; /* EBADF: control fd must be writable. */
  const struct eq_program *p=(const struct eq_program *)data;
  if(!valid(p))return 22;
  uint32_t saved=enter();copy_program(&requested,p);
  requested_generation++;if(!requested_generation)requested_generation=1;
  pending=1;leave(saved);return 0;
 }
 if(command==EQ_IOC_GET){
  uint32_t saved=enter();copy_program((struct eq_program *)data,requested_generation?&requested:&eq_program);leave(saved);return 0;
 }
 if(command==EQ_IOC_STATUS){
  struct eq_status *s=(struct eq_status *)data;uint32_t saved=enter();
  s->magic=EQ_STATUS_MAGIC;s->abi=1;s->requested_generation=requested_generation;s->applied_generation=applied_generation;
  s->rate=eq_sample_rate;s->bits=eq_kernel_state.bits;s->channels=eq_kernel_state.channels;
  s->output_clips=eq_kernel_state.output_clips;s->internal_clips=eq_kernel_state.internal_clips;
  leave(saved);return 0;
 }
 return 25;
}
