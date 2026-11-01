/* Freestanding NetBSD/MIPS client for the narrow EQ control minor.
   No network stack, no /dev/mem, no code patching or firmware uploads. */
#include "runtime.h"
#include <stdint.h>
extern int os_call(int number,uintptr_t,uintptr_t,uintptr_t,uintptr_t);
static int equal(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static unsigned length(const char *a){unsigned n=0;while(a[n])n++;return n;}
static void message(const char *a){os_call(4,2,(uintptr_t)a,length(a),0);}
static int transfer(int write,int fd,void *buffer,unsigned bytes){
 uint8_t *p=(uint8_t *)buffer;
 while(bytes){int n=os_call(write?4:3,(uintptr_t)fd,(uintptr_t)p,bytes,0);if(n==-4)continue;if(n<=0||(unsigned)n>bytes)return -1;p+=n;bytes-=(unsigned)n;}
 return 0;
}
int main(int argc,char **argv){
 if(argc!=2||(!equal(argv[1],"status")&&!equal(argv[1],"get")&&!equal(argv[1],"set"))){message("usage: eqctl status|get|set\n");return 2;}
 int fd=os_call(5,(uintptr_t)"/var/run/nook-eq/control",2,0,0);
 if(fd<0){message("EQ control node unavailable; the validated patch and device node are required.\n");return 3;}
 struct eq_status status;
 int result=os_call(54,(uintptr_t)fd,EQ_IOC_STATUS,(uintptr_t)&status,0);
 if(result||status.magic!=EQ_STATUS_MAGIC||status.abi!=1){message("EQ driver ABI not found; no settings were written.\n");os_call(6,fd,0,0,0);return 4;}
 struct eq_program p;
 if(equal(argv[1],"set")){
  uint8_t extra;
  if(transfer(0,0,&p,sizeof p)||os_call(3,0,(uintptr_t)&extra,1,0)!=0){message("Expected exactly 332 bytes of EQ settings on stdin.\n");os_call(6,fd,0,0,0);return 5;}
  result=os_call(54,fd,EQ_IOC_SET,(uintptr_t)&p,0);
  if(result){message("EQ settings rejected by driver.\n");os_call(6,fd,0,0,0);return 6;}
  result=os_call(54,fd,EQ_IOC_STATUS,(uintptr_t)&status,0);
 }
 if(equal(argv[1],"get")){
  result=os_call(54,fd,EQ_IOC_GET,(uintptr_t)&p,0);
  if(!result)result=transfer(1,1,&p,sizeof p);
 }else if(!result)result=transfer(1,1,&status,sizeof status);
 os_call(6,fd,0,0,0);
 if(result){message("EQ control I/O failed.\n");return 7;}
 return 0;
}
