#pragma once
// Data in the vertical blanking interval (the B tests).
//
// Captions (EIA/CTA-608) on line 21 of both fields (lines 21 and 284): a
// 7-cycle clock run-in at 32 x fH (503 kHz) from 10.5 us after the sync
// edge, then low until the start bit at 27.382 us, then two bytes NRZ, LSB
// first, each 7 data bits plus odd parity. 0 = blanking, 1 = 50 IRE.
//
// Field 1 (CC1) carries a pop-on caption that repeats every CC_CYCLE frames:
//   "Brought to you by the" / "Media Archive Project"
// Field 2 carries the frame counter (6 bits per byte, plus 0x20), a distinct
// data stream that lets the analysis tell repeated or lost fields apart.
//
// Line map (B2): lines 10-20 of field 1 and 273-282 of field 2 each carry an
// ID for their line of the field (k = 1..11), and a 25/50/75 IRE staircase.
// The ID is 9 cells of 1.5 us from 12 us: start "10", k in 4 bits MSB first,
// odd parity, stop "01". 0 = blanking, 1 = 50 IRE.

#include <stdint.h>
#include "patterns.h"

namespace vbi {

constexpr int CC_LINE_F1 = 21, CC_LINE_F2 = 284;
constexpr float CC_IRE = 50.0f;
constexpr float CC_RUNIN_US = 10.5f, CC_START_US = 27.382f;
constexpr int CC_RUNIN_CYCLES = 7;
constexpr int CC_CYCLE = 32;  // frames per field-1 caption cycle

constexpr int MAP_F1_FIRST = 10, MAP_F1_LAST = 20, MAP_F2_FIRST = 273, MAP_F2_LAST = 282;
constexpr float ID_START_US = 12.0f, ID_CELL_US = 1.5f;
constexpr int ID_CELLS = 9;
constexpr float STAIR_US[4] = {30.0f, 38.0f, 46.0f, 54.0f};  // 25, 50, 75 IRE steps

// Bit period, us (32 x fH).
float cc_bit_us();
uint8_t with_parity(uint8_t c7);
// The two bytes (parity included) line 21 of `field` (1 or 2) carries in `frame`.
uint16_t cc_pair(int field, uint32_t frame);
// Segments for a caption line carrying `pair` (low byte first).
int cc_segments(uint16_t pair, Segment *out, int max);
// Line-map ID k for NTSC line L (0 if L carries none).
int map_id(int line);
int id_segments(int k, Segment *out, int max);

}  // namespace vbi
