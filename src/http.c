/* Small LAN-bound HTTP service. Only embedded assets and narrow EQ ioctls.
   No request-controlled file access, process execution, memory/flash access. */
#include <stdint.h>
#include "runtime.h"
#include "http_assets.h"
extern int os_call(int,uintptr_t,uintptr_t,uintptr_t,uintptr_t);
extern int os_five(int,uintptr_t,uintptr_t,uintptr_t,uintptr_t,uintptr_t);
#ifndef NOOK_PORT
#define NOOK_PORT 8080
#endif
#ifndef PROFILE_DIR
#define PROFILE_DIR "/mnt/Flash/nook-eq"
#endif
static int persistent;
static int control;
static char device_name[256]="AirPort Express";
static char input[8193],metadata[3765],host_ip[40];
static uint8_t remembered[332];
static unsigned metadata_size;
static unsigned length(const char *s){unsigned n=0;while(s[n])n++;return n;}
static int equal(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static char lower(char c){return c>='A'&&c<='Z'?c+32:c;}
static int insensitive(const char *a,const char *b){while(*a&&lower(*a)==lower(*b)){a++;b++;}return *a==*b;}
static int same(const void *a,const void *b,unsigned n){const uint8_t *x=a,*y=b;while(n--)if(*x++!=*y++)return 0;return 1;}
static void copy(void *to,const void *from,unsigned n){uint8_t *d=to;const uint8_t *s=from;while(n--)*d++=*s++;}
static char *append(char *p,const char *s){while(*s)*p++=*s++;return p;}
static char *decimal(char *p,unsigned n){char t[10];unsigned i=0;do{t[i++]='0'+n%10;n/=10;}while(n);while(i)*p++=t[--i];return p;}
static uint32_t seconds(void){uint32_t t[2]={0,0};os_call(116,(uintptr_t)t,0,0,0);return t[0];}
struct nook_pollfd {int fd;int16_t events,revents;};
static int waitfd(int fd,int events){struct nook_pollfd p={fd,(int16_t)events,0};int n=os_call(209,(uintptr_t)&p,1,1500,0);return n>0&&(p.revents&events);}
static int write_all(int fd,const void *buffer,unsigned size){
 const uint8_t *p=buffer;uint32_t start=seconds();
 while(size){if(seconds()-start>5||!waitfd(fd,4))return -1;int n=os_call(4,fd,(uintptr_t)p,size,0);if(n==-4||n==-35)continue;if(n<=0||(unsigned)n>size)return -1;p+=n;size-=n;}return 0;
}
static void reply(int fd,const char *status,const char *type,const void *body,unsigned n){
 char header[640],*p=header;p=append(p,"HTTP/1.1 ");p=append(p,status);p=append(p,"\r\nContent-Type: ");p=append(p,type);p=append(p,"\r\nContent-Length: ");p=decimal(p,n);
 p=append(p,"\r\nConnection: close\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\nContent-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'\r\n\r\n");
 if(!write_all(fd,header,(unsigned)(p-header)))write_all(fd,body,n);
}
static void fail(int fd,const char *status,const char *message){reply(fd,status,"text/plain; charset=utf-8",message,length(message));}
static int get_program(void *p){return os_call(54,control,EQ_IOC_GET,(uintptr_t)p,0);}
static int get_status(struct eq_status *s){int n=os_call(54,control,EQ_IOC_STATUS,(uintptr_t)s,0);return n||s->magic!=EQ_STATUS_MAGIC||s->abi!=1?-1:0;}
static void status_reply(int fd){
 struct eq_status s;if(get_status(&s)){fail(fd,"503 Unavailable","EQ driver unavailable.");return;}
 uint8_t out[36];uint32_t words[9]={s.magic,s.abi,s.requested_generation,s.applied_generation,s.rate,s.bits,s.channels,s.output_clips,s.internal_clips};
 for(unsigned i=0;i<9;i++)for(unsigned j=0;j<4;j++)out[i*4+j]=(uint8_t)(words[i]>>(24-j*8));reply(fd,"200 OK","application/octet-stream",out,sizeof out);
}
static int save_profile(const void *program,const char *meta,unsigned size){
 int fd=os_call(5,(uintptr_t)(PROFILE_DIR "/program.new"),0x701,0600,0);
 if(fd<0)return -1;
 int result=write_all(fd,"NEQ1",4)||write_all(fd,program,332)||write_all(fd,meta,size)||os_call(95,fd,0,0,0);
 os_call(6,fd,0,0,0);if(result)return -1;
 if(os_call(128,(uintptr_t)(PROFILE_DIR "/program.new"),(uintptr_t)(PROFILE_DIR "/program"),0,0))return -1;
 fd=os_call(5,(uintptr_t)PROFILE_DIR,0,0,0);if(fd<0)return -1;result=os_call(95,fd,0,0,0);os_call(6,fd,0,0,0);return result;
}
static void load_profile(const char *path,int restore){
 int fd=os_call(5,(uintptr_t)path,0,0,0);if(fd<0)return;
 unsigned used=0;while(used<sizeof input){int n=os_call(3,fd,(uintptr_t)(input+used),sizeof input-used,0);if(n==-4)continue;if(n<=0)break;used+=(unsigned)n;}os_call(6,fd,0,0,0);
 if(used<=336||used>4100||!same(input,"NEQ1",4))return;
 uint32_t p[83],confirmed[83];copy(p,input+4,332);
 if(restore&&os_call(54,control,EQ_IOC_SET,(uintptr_t)p,0))return;
 if(get_program(confirmed)||!same(p,confirmed,332))return;
 copy(remembered,p,332);metadata_size=used-336;copy(metadata,input+336,metadata_size);
}
static int allowed_host(const char *host){
 if(!host||length(host)>52)return 0;
 if(insensitive(host,host_ip))return 1;
 unsigned n=length(host);const char *suffix=".local:8080";
 if(n<=11||!insensitive(host+n-11,suffix))return 0;
 for(unsigned i=0;i<n-11;i++)if(!((lower(host[i])>='a'&&lower(host[i])<='z')||(host[i]>='0'&&host[i]<='9')||host[i]=='-'||host[i]=='.'))return 0;
 return 1;
}
static char *find_end(char *buffer,unsigned n){for(unsigned i=0;i+3<n;i++)if(buffer[i]=='\r'&&buffer[i+1]=='\n'&&buffer[i+2]=='\r'&&buffer[i+3]=='\n')return buffer+i+4;return 0;}
static int parse_number(const char *s,unsigned *out){unsigned n=0;if(!*s)return -1;while(*s){if(*s<'0'||*s>'9'||n>8192)return -1;n=n*10+*s++-'0';}*out=n;return 0;}
static void serve(int fd){
 unsigned total=0;char *body=0;uint32_t start=seconds();
 while(!body){
  if(total>=4096||seconds()-start>5||!waitfd(fd,1))return;
  int n=os_call(3,fd,(uintptr_t)(input+total),sizeof(input)-1-total,0);if(n==-4||n==-35)continue;if(n<=0)return;total+=n;input[total]=0;body=find_end(input,total);
 }
 unsigned header_size=(unsigned)(body-input);
 if(header_size>4096){fail(fd,"431 Headers Too Large","Headers too large.");return;}
 char *method=input,*path=0,*protocol=0,*headers=0;
 for(char *p=input;p<body-2;p++){
  if(*p==' '&&!path){*p=0;path=p+1;}
  else if(*p==' '&&path&&!protocol){*p=0;protocol=p+1;}
  else if(*p=='\r'&&p[1]=='\n'){*p=0;headers=p+2;break;}
 }
 if(!path||!protocol||!headers||(!equal(protocol,"HTTP/1.1")&&!equal(protocol,"HTTP/1.0"))){fail(fd,"400 Bad Request","Malformed request.");return;}
 char *host=0,*origin=0,*type=0;unsigned content_size=0;int has_length=0;
 for(char *line=headers;line<body-2;){
  char *end=line;while(end<body-2&&!(end[0]=='\r'&&end[1]=='\n'))end++;
  if(end>=body-2){fail(fd,"400 Bad Request","Malformed headers.");return;}*end=0;
  char *colon=line;while(*colon&&*colon!=':')colon++;if(!*colon){fail(fd,"400 Bad Request","Malformed header.");return;}*colon++=0;while(*colon==' '||*colon=='\t')colon++;
  char *tail=colon+length(colon);while(tail>colon&&(tail[-1]==' '||tail[-1]=='\t'))*--tail=0;
  if(insensitive(line,"Host")){if(host){fail(fd,"400 Bad Request","Duplicate Host.");return;}host=colon;}
  else if(insensitive(line,"Origin")){if(origin){fail(fd,"400 Bad Request","Duplicate Origin.");return;}origin=colon;}
  else if(insensitive(line,"Content-Type")){if(type){fail(fd,"400 Bad Request","Duplicate Content-Type.");return;}type=colon;}
  else if(insensitive(line,"Content-Length")){if(has_length||parse_number(colon,&content_size)){fail(fd,"400 Bad Request","Invalid Content-Length.");return;}has_length=1;}
  else if(insensitive(line,"Transfer-Encoding")){fail(fd,"400 Bad Request","Transfer-Encoding unsupported.");return;}
  line=end+2;
 }
 if(!allowed_host(host)){fail(fd,"403 Forbidden","Use airport-express.local:8080.");return;}
 if(equal(method,"GET")){
  if(content_size||total!=header_size){fail(fd,"400 Bad Request","Unexpected request body.");return;}
  for(unsigned i=0;i<ASSET_COUNT;i++)if(equal(path,assets[i].path)){reply(fd,"200 OK",assets[i].type,assets[i].data,assets[i].size);return;}
  if(equal(path,"/api/name")){reply(fd,"200 OK","text/plain; charset=utf-8",device_name,length(device_name));return;}
  if(equal(path,"/api/mode")){const char *mode=persistent?"{\"persistent\":true}":"{\"persistent\":false}";reply(fd,"200 OK","application/json",mode,length(mode));return;}
  if(equal(path,"/api/status")){status_reply(fd);return;}
  if(equal(path,"/api/program")||equal(path,"/api/config")){
   uint32_t program[83];if(get_program(program)){fail(fd,"503 Unavailable","EQ driver unavailable.");return;}
   if(equal(path,"/api/program"))reply(fd,"200 OK","application/octet-stream",program,sizeof program);
   else if(metadata_size&&same(program,remembered,332))reply(fd,"200 OK","application/json",metadata,metadata_size);
   else reply(fd,"200 OK","application/json","null",4);
   return;
  }
  fail(fd,"404 Not Found","Not found.");return;
 }
 if(!equal(method,"POST")||!equal(path,"/api/program")){fail(fd,"404 Not Found","Not found.");return;}
 char expected_origin[64];char *end=append(expected_origin,"http://");end=append(end,host);*end=0;
 if(!origin||!insensitive(origin,expected_origin)){fail(fd,"403 Forbidden","Same-origin request required.");return;}
 if(!type||!equal(type,"application/octet-stream")){fail(fd,"415 Unsupported Media Type","Send application/octet-stream.");return;}
 if(!has_length||content_size<=332||content_size>4096||total-header_size>content_size){fail(fd,"400 Bad Request","Invalid program length.");return;}
 while(total-header_size<content_size){
  if(seconds()-start>5||!waitfd(fd,1)){fail(fd,"408 Request Timeout","Request timed out.");return;}
  unsigned remaining=content_size-(total-header_size);int n=os_call(3,fd,(uintptr_t)(input+total),remaining,0);if(n==-4||n==-35)continue;if(n<=0)return;total+=n;
 }
 /* Align the ioctl buffer regardless of HTTP header length. Kernel validates it. */
 uint32_t program[83],confirmed[83];copy(program,body,332);
 if(os_call(54,control,EQ_IOC_SET,(uintptr_t)program,0)){fail(fd,"422 Unprocessable Content","EQ program rejected; settings unchanged.");return;}
 if(get_program(confirmed)||!same(program,confirmed,332)){fail(fd,"409 Conflict","Settings result uncertain. Read the current EQ before retrying.");return;}
 copy(remembered,confirmed,332);metadata_size=content_size-332;copy(metadata,body+332,metadata_size);
 if(persistent&&save_profile(confirmed,metadata,metadata_size)){fail(fd,"500 Save Failed","EQ applied in RAM, but saving failed. Check current settings before retrying.");return;}
 status_reply(fd);
}
static int startup_error(unsigned code){char message[64],*p=append(message,"nook-http startup error ");p=decimal(p,code);*p++='\n';os_call(4,2,(uintptr_t)message,(unsigned)(p-message),0);return (int)code;}
int main(int argc,char **argv){
 if(argc!=2&&argc!=3)return startup_error(2);
 if(argc==3){if(!equal(argv[2],"--persistent"))return startup_error(2);persistent=1;}
 uint8_t address[16]={16,2,(NOOK_PORT>>8)&255,NOOK_PORT&255};const char *p=argv[1];
 for(unsigned i=0;i<4;i++){unsigned n=0,digits=0;while(*p>='0'&&*p<='9'){n=n*10+*p++-'0';digits++;if(n>255)return startup_error(2);}if(!digits||((i<3)?*p++!='.':*p!=0))return startup_error(2);address[4+i]=(uint8_t)n;}
 if(!address[4])return startup_error(2);
 char *h=append(host_ip,argv[1]);h=append(h,":");h=decimal(h,NOOK_PORT);*h=0;
 control=os_call(5,(uintptr_t)"/var/run/nook-eq/control",2,0,0);struct eq_status state;if(control<0||get_status(&state))return startup_error(3);
 int name_fd=os_call(5,(uintptr_t)"/var/run/nook-eq/name",0,0,0);
 if(name_fd>=0){char name[256];int n=os_call(3,name_fd,(uintptr_t)name,sizeof name-1,0);os_call(6,name_fd,0,0,0);if(n>0){while(n>0&&(name[n-1]=='\n'||name[n-1]=='\r'))n--;int valid=n>0;for(int i=0;i<n;i++)if((unsigned char)name[i]<32)valid=0;if(valid){copy(device_name,name,(unsigned)n);device_name[n]=0;}}}
 if(persistent)load_profile(PROFILE_DIR "/program",1);
 else load_profile("/var/run/nook-eq/http.seed",0);
 /* The open descriptor exposes only validated EQ ioctls. Drop all groups and
    root identity before accepting any HTTP request. */
 if(os_call(80,0,0,0,0)||os_call(181,65534,0,0,0)||os_call(23,65534,0,0,0))return startup_error(9);
 /* Block SIGPIPE: failed socket writes return EPIPE without a handler. */
 uint32_t mask[4]={1u<<12,0,0,0};if(os_call(293,1,(uintptr_t)mask,0,0))return startup_error(4);
 os_call(96,0,0,10,0);
 int socket=os_call(394,2,1,0,0);if(socket<0)return startup_error(5);
 int yes=1;os_five(105,socket,0xffff,4,(uintptr_t)&yes,4);
 if(os_call(104,socket,(uintptr_t)address,16,0)||os_call(106,socket,8,0,0))return startup_error(6);
 for(;;){int fd=os_call(30,socket,0,0,0);if(fd==-4)continue;if(fd<0)return startup_error(7);if(!os_call(92,fd,4,4,0))serve(fd);
  /* Send FIN before closing; drain a bounded rejected body to avoid RST
     discarding the error response when request bytes remain unread. */
  os_call(134,fd,1,0,0);
  for(unsigned drained=0;drained<8192;){struct nook_pollfd p={fd,1,0};if(os_call(209,(uintptr_t)&p,1,20,0)<=0)break;int n=os_call(3,fd,(uintptr_t)input,sizeof input,0);if(n<=0)break;drained+=(unsigned)n;}
  os_call(6,fd,0,0,0);}
}
