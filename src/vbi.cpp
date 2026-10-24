#include "vbi.h"

#include <math.h>
#include "ntsc_timing.h"

namespace vbi {

static const char ROW1[] = "Brought to you by the";
static const char ROW2[] = "Media Archive Project";

float cc_bit_us() { return (float)(1e6 / (32.0 * ntsc::FH_HZ)); }

uint8_t with_parity(uint8_t c) {
    c &= 0x7F;
    uint8_t ones = 0;
    for (int i = 0; i < 7; i++) ones += (c >> i) & 1;
    return (ones & 1) ? c : (uint8_t)(c | 0x80);  // odd parity over all 8 bits
}

// Field-1 byte pairs for one caption cycle, by frame mod CC_CYCLE:
//   0-1 RCL (resume caption loading), 2-3 ENM (erase non-displayed memory),
//   4-5 PAC row 14 indent 4, 6-16 row 1 text, 17-18 PAC row 15 indent 4,
//   19-29 row 2 text, 30-31 EOC (end of caption: show it).
// Control codes are sent twice, in consecutive frames, as 608 expects.
static void f1_bytes(uint32_t i, uint8_t *b) {
    auto text = [&](const char *s, int j) {
        int n = 0;
        while (s[n]) n++;
        b[0] = 2 * j < n ? (uint8_t)s[2 * j] : 0;
        b[1] = 2 * j + 1 < n ? (uint8_t)s[2 * j + 1] : 0;
    };
    if (i < 2)        { b[0] = 0x14; b[1] = 0x20; }
    else if (i < 4)   { b[0] = 0x14; b[1] = 0x2E; }
    else if (i < 6)   { b[0] = 0x14; b[1] = 0x52; }
    else if (i < 17)  text(ROW1, (int)i - 6);
    else if (i < 19)  { b[0] = 0x14; b[1] = 0x72; }
    else if (i < 30)  text(ROW2, (int)i - 19);
    else              { b[0] = 0x14; b[1] = 0x2F; }
}

uint16_t cc_pair(int field, uint32_t frame) {
    uint8_t b[2];
    if (field == 1) {
        f1_bytes(frame % CC_CYCLE, b);
    } else {
        b[0] = (uint8_t)(0x20 + (frame & 0x3F));
        b[1] = (uint8_t)(0x20 + ((frame >> 6) & 0x3F));
    }
    return (uint16_t)(with_parity(b[0]) | (with_parity(b[1]) << 8));
}

// Fraction of the active width at time t (us after the sync edge).
static inline float xat(float t_us) {
    return (float)((t_us * ntsc::US - ntsc::ACTIVE_START) / ntsc::ACTIVE_WIDTH);
}

int cc_segments(uint16_t pair, Segment *out, int max) {
    const float T = cc_bit_us();
    int m = 0;
    auto add = [&](float t0, float t1, float y0, float y1) {
        if (m < max) out[m++] = {xat(t0), xat(t1), y0, y1, 0, 0};
    };
    // Run-in: CC_IRE/2 * (1 - cos), as 8 linear pieces per cycle.
    const int P = 8;
    for (int i = 0; i < CC_RUNIN_CYCLES * P; i++) {
        float a0 = (float)i / P, a1 = (float)(i + 1) / P;
        add(CC_RUNIN_US + a0 * T, CC_RUNIN_US + a1 * T, 0.5f * CC_IRE * (1 - cosf(2 * (float)M_PI * a0)),
            0.5f * CC_IRE * (1 - cosf(2 * (float)M_PI * a1)));
    }
    // Start bit, then 16 data bits LSB first; runs of 1s merge into one segment.
    int bits[17];
    bits[0] = 1;
    for (int i = 0; i < 16; i++) bits[1 + i] = (pair >> i) & 1;
    for (int i = 0; i < 17; i++) {
        if (!bits[i]) continue;
        int j = i;
        while (j + 1 < 17 && bits[j + 1]) j++;
        add(CC_START_US + i * T, CC_START_US + (j + 1) * T, CC_IRE, CC_IRE);
        i = j;
    }
    return m;
}

bool agc_line(int L) { return (L >= AGC_F1_FIRST && L <= AGC_F1_LAST) || (L >= AGC_F2_FIRST && L <= AGC_F2_LAST); }

bool stripe_line(int L) {
    if (L >= STRIPE_F1_FIRST && L <= STRIPE_F1_LAST) return (L - STRIPE_F1_FIRST) % STRIPE_EVERY < STRIPE_LINES;
    if (L >= STRIPE_F2_FIRST && L <= STRIPE_F2_LAST) return (L - STRIPE_F2_FIRST) % STRIPE_EVERY < STRIPE_LINES;
    return false;
}

int agc_segments(float agc_ire, Segment *out, int max) {
    int m = 0;
    for (int k = 0; k < AGC_PAIRS && m + 1 < max; k++) {
        float t = AGC_START_US + k * AGC_PAIR_US;
        out[m++] = {xat(t), xat(t + PSEUDO_US), PSEUDO_IRE, PSEUDO_IRE, 0, 0};
        if (agc_ire != 0.0f) {
            float a = t + PSEUDO_US + AGC_GAP_US;
            out[m++] = {xat(a), xat(a + AGC_US), agc_ire, agc_ire, 0, 0};
        }
    }
    return m;
}

int map_id(int L) {
    if (L >= MAP_F1_FIRST && L <= MAP_F1_LAST) return L - MAP_F1_FIRST + 1;
    if (L >= MAP_F2_FIRST && L <= MAP_F2_LAST) return L - MAP_F2_FIRST + 1;
    return 0;
}

int id_segments(int k, Segment *out, int max) {
    int cells[ID_CELLS] = {1, 0, (k >> 3) & 1, (k >> 2) & 1, (k >> 1) & 1, k & 1, 0, 0, 1};
    cells[6] = ((cells[2] + cells[3] + cells[4] + cells[5]) & 1) ? 0 : 1;  // odd parity over k and this bit
    int m = 0;
    for (int i = 0; i < ID_CELLS; i++) {
        if (!cells[i]) continue;
        int j = i;
        while (j + 1 < ID_CELLS && cells[j + 1]) j++;
        if (m < max) out[m++] = {xat(ID_START_US + i * ID_CELL_US), xat(ID_START_US + (j + 1) * ID_CELL_US), CC_IRE, CC_IRE, 0, 0};
        i = j;
    }
    for (int s = 0; s < 3 && m < max; s++) {
        float ire = 25.0f * (s + 1);
        out[m++] = {xat(STAIR_US[s]), xat(STAIR_US[s + 1]), ire, ire, 0, 0};
    }
    return m;
}

}  // namespace vbi
