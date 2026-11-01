#ifndef AIRPORT_EQ_H
#define AIRPORT_EQ_H
#include <stdint.h>
#define EQ_MAX_STAGES 8
#define EQ_RATE_COUNT 2
struct eq_coeff { int32_t b0,b1,b2,a1,a2; };
struct eq_program {
 uint32_t enabled, stages;
 int32_t preamp; /* Q29, 0..1 */
 struct eq_coeff coeff[EQ_RATE_COUNT][EQ_MAX_STAGES];
};
struct eq_delay { int32_t x1,x2,y1,y2,error; };
struct eq_state {
 uint32_t rate,bits,channels;
 uint32_t output_clips,internal_clips;
 struct eq_delay delay[2][EQ_MAX_STAGES];
};
void eq_reset(struct eq_state *s);
/* Packed signed BE16/BE24, interleaved. Unknown formats pass unchanged. */
int eq_process(const struct eq_program *p,struct eq_state *s,
               uint8_t *data,uint32_t bytes,uint32_t bits,uint32_t channels,uint32_t rate);
#endif
