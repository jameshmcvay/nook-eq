/* Exact-build, temporary RAM-only experiment. No flash devices or reboot code. */
#include <stdint.h>
#include "ram_image.h"
extern int os_call(int,uintptr_t,uintptr_t,uintptr_t,uintptr_t);
extern int os_at(int,int,void *,unsigned,uint32_t);
static uint32_t scratch[(ARENA_BYTES+3)/4];
static int equal(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int report(const char *s,int result){unsigned n=0;while(s[n])n++;os_call(4,result?2:1,(uintptr_t)s,n,0);return result;}
static int read_exact(int fd,uint32_t address,void *buffer,unsigned size){
 return os_at(173,fd,buffer,size,address)==(int)size?0:-1;
}
static int word_is(int fd,uint32_t address,uint32_t expected){
 uint32_t value=0;int result=os_at(173,fd,&value,4,address);
 if(result!=4||value!=expected){
  char line[]="Guard address=00000000 read_result=00000000 value=00000000\n";
  const char hex[]="0123456789abcdef";
  uint32_t fields[3]={address,(uint32_t)result,value};unsigned positions[3]={14,35,50};
  for(unsigned f=0;f<3;f++)for(unsigned i=0;i<8;i++)line[positions[f]+i]=hex[(fields[f]>>(28-4*i))&15];
  report(line,4);return 0;
 }
 return 1;
}
static int flush(void){uint32_t args[3]={0,0,3};return os_call(165,0,(uintptr_t)args,0,0);}
int main(int argc,char **argv){
 if(argc!=2||(!equal(argv[1],"check")&&!equal(argv[1],"install-bypass")&&!equal(argv[1],"check-write-access")))return report("usage: ram-eq check|check-write-access|install-bypass\n",2);
 int install=equal(argv[1],"install-bypass");
 int writable=install||equal(argv[1],"check-write-access");
 int fd=os_call(5,(uintptr_t)"/var/run/nook-eq/rawmem",writable?2:0,0,0);
 if(fd<0)return report("Cannot open kernel memory.\n",3);
 if(!word_is(fd,0x803cc640,0x5acd8)||!word_is(fd,0x81007384,1)||!word_is(fd,0x810073b0,0x801e8528)||!word_is(fd,0x810073bc,0x801e8bc4))return report("Kernel symbol/cache guards mismatch; no writes.\n",4);
 if(read_exact(fd,ARENA_START,scratch,ARENA_BYTES))return report("Cannot read complete arena; no writes.\n",4);
 for(unsigned i=0;i<ARENA_BYTES/4;i++)if(scratch[i])return report("Arena is occupied; no writes.\n",4);
 for(unsigned i=0;i<HOOK_COUNT;i++){
  if(!word_is(fd,hooks[i].address,hooks[i].before))return report("Stock hook mismatch; no writes.\n",4);
  if(hooks[i].delay&&!word_is(fd,hooks[i].address+4,hooks[i].delay))return report("Stock delay slot mismatch; no writes.\n",4);
 }
 if(!install){os_call(6,fd,0,0,0);return report("RAM preflight passed; no writes.\n",0);}
 /* Check the existing cacheflush syscall before any kernel write. */
 if(flush())return report("Cache synchronization unavailable; no writes.\n",5);
 if(os_at(174,fd,(void *)arena_image,IMAGE_BYTES,ARENA_START)!=(int)IMAGE_BYTES)return report("Arena write incomplete. Stop and power-cycle to restore stock RAM.\n",6);
 if(read_exact(fd,ARENA_START,scratch,IMAGE_BYTES))return report("Arena verification failed. Stop and power-cycle.\n",6);
 for(unsigned i=0;i<IMAGE_BYTES/4;i++)if(scratch[i]!=arena_image[i])return report("Arena verification mismatch. Stop and power-cycle.\n",6);
 if(flush())return report("Cache synchronization failed. Stop and power-cycle.\n",6);
 for(unsigned i=0;i<HOOK_COUNT;i++){
  if(!word_is(fd,hooks[i].address,hooks[i].before))return report("Hook changed. Stop and power-cycle.\n",6);
  /* Aligned source and exactly four bytes: stock copyin/memcpy uses one SW. */
  if(os_at(174,fd,(void *)&hooks[i].after,4,hooks[i].address)!=4||flush()||!word_is(fd,hooks[i].address,hooks[i].after))return report("Hook install failed. Stop and power-cycle.\n",6);
 }
 os_call(6,fd,0,0,0);
 return report("Temporary EQ installed in bypass. Flash unchanged; power-cycle removes it.\n",0);
}
