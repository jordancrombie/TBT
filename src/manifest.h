#pragma once
#include <Print.h>

// Print the current run's manifest (schema "tbc-test/1") as one JSON line.
void print_manifest(Print &out);

#define FIRMWARE_VERSION "ntsc-gen 0.4.0"   // 0.4.0: B tests (captions, VBI line map)
