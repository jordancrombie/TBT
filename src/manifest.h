#pragma once
#include <Print.h>

// Print the current run's manifest (schema "tbc-test/1") as one JSON line.
void print_manifest(Print &out);

#define FIRMWARE_VERSION "ntsc-gen 0.6.0"   // 0.6.0: calibrated levels (5/92); 0.5.0: B3; 0.4.0: B1/B2
