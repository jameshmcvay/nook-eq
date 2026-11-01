/* Native syscall shim exercises the exact embedded HTTP parser locally. */
#include <stdint.h>
#include <unistd.h>
#include <errno.h>
#include <signal.h>
#include <fcntl.h>
#include <string.h>
#include <stdio.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <poll.h>
#define main nook_main
#include "../src/http.c"
#undef main
static uint8_t fake_program[332];
static unsigned generation;
static int result(int n){return n<0?-(errno==EAGAIN?35:errno):n;}
static uint32_t read_be(const uint8_t *p){return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];}
int os_call(int nr,uintptr_t a,uintptr_t b,uintptr_t c,uintptr_t d){
 (void)d;
 if(nr==5){if(equal((const char *)a,"/var/run/nook-eq/control"))return 1000;if(strncmp((const char *)a,PROFILE_DIR,sizeof(PROFILE_DIR)-1)!=0)return -2;int flags=b?O_WRONLY|O_CREAT|O_TRUNC:O_RDONLY;return result(open((const char *)a,flags,0600));}
 if(nr==54){
  if(b==EQ_IOC_STATUS){struct eq_status s={EQ_STATUS_MAGIC,1,generation,generation,48000,24,2,0,0};copy((void *)c,&s,sizeof s);return 0;}
  if(b==EQ_IOC_GET){copy((void *)c,fake_program,332);return 0;}
  if(b==EQ_IOC_SET){const uint8_t *p=(const uint8_t *)c;if(read_be(p)>1||read_be(p+4)>8||read_be(p+8)>(1u<<29))return -22;copy(fake_program,p,332);generation++;return 0;}
  return -25;
 }
 if(nr==293){sigset_t mask;sigemptyset(&mask);sigaddset(&mask,SIGPIPE);return result(sigprocmask(SIG_BLOCK,&mask,0));}
 if(nr==23||nr==80||nr==181)return 0;
 if(nr==3)return result((int)read((int)a,(void *)b,c));
 if(nr==4)return result((int)write((int)a,(void *)b,c));
 if(nr==6)return result(close((int)a));
 if(nr==116){struct timeval t;gettimeofday(&t,0);uint32_t *v=(uint32_t *)a;v[0]=t.tv_sec;v[1]=t.tv_usec;return 0;}
 if(nr==209)return result(poll((struct pollfd *)a,b,c));
 if(nr==95)return result(fsync((int)a));
 if(nr==128)return result(rename((const char *)a,(const char *)b));
 if(nr==134)return result(shutdown((int)a,(int)b));
 if(nr==394)return result(socket(AF_INET,SOCK_STREAM,0));
 if(nr==104){const uint8_t *v=(const uint8_t *)b;struct sockaddr_in addr;memset(&addr,0,sizeof addr);addr.sin_family=AF_INET;copy(&addr.sin_port,v+2,2);copy(&addr.sin_addr,v+4,4);return result(bind((int)a,(struct sockaddr *)&addr,sizeof addr));}
 if(nr==106)return result(listen((int)a,(int)b));
 if(nr==30)return result(accept((int)a,0,0));
 if(nr==92)return result(fcntl((int)a,F_SETFL,O_NONBLOCK));
 if(nr==96)return 0;
 return -78;
}
int os_five(int nr,uintptr_t a,uintptr_t b,uintptr_t c,uintptr_t d,uintptr_t e){
 (void)b;(void)c;
 if(nr==105)return result(setsockopt(a,SOL_SOCKET,SO_REUSEADDR,(void *)d,e));
 return -78;
}
int main(int argc,char **argv){fake_program[3]=1;fake_program[8]=0x20;return nook_main(argc,argv);}
