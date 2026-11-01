/* User-space DSP test runner: stdin PCM -> EQ -> stdout PCM. No audio device,
   kernel-memory access, networking, flash operations or settings changes. */
#include "eq.h"
#include <stdint.h>
extern int os_call(int,uintptr_t,uintptr_t,uintptr_t,uintptr_t);
static struct eq_program program;
static struct eq_state state;
static uint8_t buffer[3072];
static int equal(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int transfer(int writing,void *data,unsigned size){
 uint8_t *p=data;
 while(size){int n=os_call(writing?4:3,writing?1:0,(uintptr_t)p,size,0);if(n==-4)continue;if(n<=0||(unsigned)n>size)return -1;p+=n;size-=n;}
 return 0;
}
static int clock_us(uint32_t *result){uint32_t t[2];if(os_call(116,(uintptr_t)t,0,0,0))return -1;*result=t[0]*1000000u+t[1];return 0;}
static void text(const char *s){unsigned n=0;while(s[n])n++;os_call(4,2,(uintptr_t)s,n,0);}
static void number(uint32_t n){char out[10];unsigned p=10;do{out[--p]='0'+n%10;n/=10;}while(n);os_call(4,2,(uintptr_t)(out+p),10-p,0);}
int main(int argc,char **argv){
 if(argc!=3)return 2;
 unsigned bits=equal(argv[1],"16")?16:equal(argv[1],"24")?24:0;
 unsigned rate=equal(argv[2],"44100")?44100:equal(argv[2],"48000")?48000:0;
 if(!bits||!rate||transfer(0,&program,sizeof program))return 2;
 uint32_t frames=0,elapsed=0;unsigned used=0;
 for(;;){
  int n=os_call(3,0,(uintptr_t)(buffer+used),sizeof buffer-used,0);
  if(n==-4)continue;
  if(n<0||(unsigned)n>sizeof buffer-used)return 3;
  used+=n;
  if(n&&used<sizeof buffer)continue;
  if(used){
   if(used%(bits/8*2))return 4;
   uint32_t before,after;
   if(clock_us(&before)||eq_process(&program,&state,buffer,used,bits,2,rate)||clock_us(&after))return 5;
   elapsed+=after-before;frames+=used/(bits/8*2);
   if(transfer(1,buffer,used))return 6;
   used=0;
  }
  if(!n)break;
 }
 text("{\"frames\":");number(frames);text(",\"processing_us\":");number(elapsed);text(",\"output_clips\":");number(state.output_clips);text(",\"internal_clips\":");number(state.internal_clips);text("}\n");
 return 0;
}
