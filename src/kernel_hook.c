#include "runtime.h"
extern const struct eq_program eq_program;
struct eq_state eq_kernel_state;
volatile uint32_t eq_sample_rate;
int eq_stream_reset(uint32_t flags,int result) {
 if(result==0 && (flags&1)==0){eq_reset(&eq_kernel_state);eq_sample_rate=0;}
 return result;
}
/* Called by entry.S only after a successful original uiomove. */
int eq_filter(void *buffer,uint32_t count) {
 uint32_t cfg=*(volatile uint32_t *)(uintptr_t)0xb80b0000;
 uint32_t bits=8*(((cfg>>12)&3)+1);
 uint32_t channels=(cfg&0x4000)?1:2;
 uint32_t rate=eq_sample_rate;
 eq_process(eq_begin_buffer(),&eq_kernel_state,buffer,count,bits,channels,rate);
 return 0;
}
