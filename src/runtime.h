#ifndef NOOK_RUNTIME_H
#define NOOK_RUNTIME_H
#include "eq.h"
#define EQ_CONTROL_MINOR 128
#define EQ_IOC_SET 0x814c5101u
#define EQ_IOC_GET 0x414c5102u
#define EQ_IOC_STATUS 0x40245103u
#define EQ_STATUS_MAGIC 0x45513130u
struct eq_status {
 uint32_t magic,abi,requested_generation,applied_generation;
 uint32_t rate,bits,channels,output_clips,internal_clips;
};
int eq_control(uint32_t command,void *data,uint32_t flags);
const struct eq_program *eq_begin_buffer(void);
#endif
