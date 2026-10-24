#include "patterns.h"
#include "ntsc_timing.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

using namespace ntsc;

float g_flat_ire = 50.0f;

// RGB (0..1, gamma-corrected) -> luma/chroma in IRE, 7.5 IRE setup.
static Segment rgb(float x0, float x1, float r, float g, float b) {
    float y = 0.299f * r + 0.587f * g + 0.114f * b;
    float u = 0.492f * (b - y);
    float v = 0.877f * (r - y);
    float Y = IRE_SETUP + RGB_SCALE * y;
    return {x0, x1, Y, Y, (float)(RGB_SCALE * u), (float)(RGB_SCALE * v)};
}

// Chroma on the I/Q axes (amplitude in IRE), with setup-level luma.
static Segment iq(float x0, float x1, float i, float q) {
    const float s = sinf(33.0f * (float)M_PI / 180.0f), c = cosf(33.0f * (float)M_PI / 180.0f);
    float v = i * c + q * s;
    float u = -i * s + q * c;
    return {x0, x1, (float)IRE_SETUP, (float)IRE_SETUP, u, v};
}

static Segment luma(float x0, float x1, float ire) { return {x0, x1, ire, ire, 0, 0}; }

static const float BARS75[7][3] = {
    {.75f, .75f, .75f}, {.75f, .75f, 0}, {0, .75f, .75f}, {0, .75f, 0},
    {.75f, 0, .75f},    {.75f, 0, 0},    {0, 0, .75f},
};

// ---- SMPTE EG-1 colour bars -------------------------------------------------
static int smpte_key(int row) {
    if (row < ACTIVE_ROWS * 2 / 3) return 0;
    if (row < ACTIVE_ROWS * 3 / 4) return 1;
    return 2;
}
static int smpte_segs(int key, Segment *o, int) {
    const float w = 1.0f / 7.0f;
    if (key == 0) {
        for (int i = 0; i < 7; i++) o[i] = rgb(i * w, (i + 1) * w, BARS75[i][0], BARS75[i][1], BARS75[i][2]);
        return 7;
    }
    if (key == 1) {  // reverse-order castellations: blue, blk, magenta, blk, cyan, blk, gray
        static const int idx[7] = {6, -1, 4, -1, 2, -1, 0};
        for (int i = 0; i < 7; i++) {
            if (idx[i] < 0) o[i] = rgb(i * w, (i + 1) * w, 0, 0, 0);
            else o[i] = rgb(i * w, (i + 1) * w, BARS75[idx[i]][0], BARS75[idx[i]][1], BARS75[idx[i]][2]);
        }
        return 7;
    }
    // -I, 100% white, +Q, black (each 5/4 bar), PLUGE (3 x 1/3 bar), black
    float x = 0, b = 1.25f * w, p = w / 3.0f;
    int n = 0;
    o[n++] = iq(x, x + b, -20, 0);              x += b;
    o[n++] = luma(x, x + b, 100);               x += b;
    o[n++] = iq(x, x + b, 0, 20);               x += b;
    o[n++] = luma(x, x + b, IRE_SETUP);         x += b;
    o[n++] = luma(x, x + p, IRE_SETUP - 4);     x += p;
    o[n++] = luma(x, x + p, IRE_SETUP);         x += p;
    o[n++] = luma(x, x + p, IRE_SETUP + 4);     x += p;
    o[n++] = luma(x, 1.0f, IRE_SETUP);
    return n;
}

// ---- Full-field 75% EIA bars (with black) -----------------------------------
static int one_key(int) { return 0; }
static int eia_segs(int, Segment *o, int) {
    const float w = 1.0f / 8.0f;
    for (int i = 0; i < 7; i++) o[i] = rgb(i * w, (i + 1) * w, BARS75[i][0], BARS75[i][1], BARS75[i][2]);
    o[7] = rgb(7 * w, 1.0f, 0, 0, 0);
    return 8;
}

// ---- 10-step luma staircase (setup .. 100 IRE) ------------------------------
static int stair_segs(int, Segment *o, int) {
    const int steps = 10;
    for (int i = 0; i < steps; i++) {
        float ire = IRE_SETUP + (IRE_WHITE - IRE_SETUP) * i / (steps - 1);
        o[i] = luma((float)i / steps, (float)(i + 1) / steps, ire);
    }
    return steps;
}

// ---- Flat field at g_flat_ire ------------------------------------------------
static int flat_segs(int, Segment *o, int) { o[0] = luma(0, 1, g_flat_ire); return 1; }

// ---- Crosshatch: 16 x 12 white grid on black --------------------------------
static const int XH_COLS = 16, XH_ROWS = 12;
static int xhatch_key(int row) {
    // Horizontal grid lines 2 rows (one per field) thick, incl. top & bottom edge.
    int pitch = ACTIVE_ROWS / XH_ROWS;
    int r = row % pitch;
    return (r < 2 || row >= ACTIVE_ROWS - 2) ? 1 : 0;
}
static int xhatch_segs(int key, Segment *o, int max) {
    if (key == 1) { o[0] = luma(0, 1, IRE_WHITE); return 1; }
    const float lw = 0.004f;  // ~3 samples wide
    int n = 0;
    float x = 0;
    for (int c = 0; c <= XH_COLS && n + 2 <= max; c++) {
        float cx = (float)c / XH_COLS;
        float l0 = cx - lw / 2, l1 = cx + lw / 2;
        if (l0 < 0) { l0 = 0; l1 = lw; }
        if (l1 > 1) { l1 = 1; l0 = 1 - lw; }
        if (l0 > x) o[n++] = luma(x, l0, IRE_SETUP);
        o[n++] = luma(l0, l1, IRE_WHITE);
        x = l1;
    }
    return n;
}

// ---- Black (sync, burst and setup only) --------------------------------------
static int black_segs(int, Segment *o, int) { o[0] = luma(0, 1, IRE_SETUP); return 1; }

// ---- Title card and test cards: not test patterns ---------------------------
// Text on black in a 5x7 block font scaled to square pixels on the 4:3 picture,
// with a slim strip of colour bars. "title" is the TBT title (photos, posts,
// --title); "card" shows host-supplied lines between tests (--cards). Neither
// is ever used by a test: the host restores the test pattern before capturing.
struct Glyph { char c; uint8_t rows[7]; };   // 5 bits per row, MSB = leftmost
static const Glyph FONT[] = {
    {'A', {0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11}}, {'B', {0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E}},
    {'C', {0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E}}, {'D', {0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E}},
    {'E', {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F}}, {'F', {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10}},
    {'G', {0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F}}, {'H', {0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11}},
    {'I', {0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E}}, {'J', {0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C}},
    {'K', {0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11}}, {'L', {0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F}},
    {'M', {0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11}}, {'N', {0x11, 0x11, 0x19, 0x15, 0x13, 0x11, 0x11}},
    {'O', {0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E}}, {'P', {0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10}},
    {'Q', {0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D}}, {'R', {0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11}},
    {'S', {0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E}}, {'T', {0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04}},
    {'U', {0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E}}, {'V', {0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04}},
    {'W', {0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A}}, {'X', {0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11}},
    {'Y', {0x11, 0x11, 0x11, 0x0A, 0x04, 0x04, 0x04}}, {'Z', {0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F}},
    {'0', {0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E}}, {'1', {0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E}},
    {'2', {0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F}}, {'3', {0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E}},
    {'4', {0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02}}, {'5', {0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E}},
    {'6', {0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E}}, {'7', {0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08}},
    {'8', {0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E}}, {'9', {0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C}},
    {'.', {0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C}}, {',', {0x00, 0x00, 0x00, 0x00, 0x0C, 0x04, 0x08}},
    {':', {0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x0C, 0x00}}, {'-', {0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00}},
    {'+', {0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00}}, {'/', {0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x00}},
    {'%', {0x18, 0x19, 0x02, 0x04, 0x08, 0x13, 0x03}}, {'(', {0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02}},
    {')', {0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08}}, {'!', {0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04}},
    {'?', {0x0E, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04}}, {'#', {0x0A, 0x0A, 0x1F, 0x0A, 0x1F, 0x0A, 0x0A}},
    {'=', {0x00, 0x00, 0x1F, 0x00, 0x1F, 0x00, 0x00}}, {'*', {0x00, 0x00, 0x0E, 0x0E, 0x0E, 0x00, 0x00}},
    {'\'', {0x0C, 0x04, 0x08, 0x00, 0x00, 0x00, 0x00}},
};
static uint8_t glyph_row(char c, int r) {
    if (c >= 'a' && c <= 'z') c -= 32;
    for (const Glyph &g : FONT)
        if (g.c == c) return g.rows[r];
    return 0;  // space, or a character the font doesn't have
}

static const int TEXT_MAX = 40, LINES_MAX = 6;
struct TextLine { char text[TEXT_MAX + 1]; int top; int px; float ire; };  // px: picture rows per font pixel
struct TextCard { TextLine line[LINES_MAX]; int n; };
static const int BARS_TOP = 400, BARS_ROWS = 24;    // the slim strip of colour bars

static TextCard s_title = {{{"TBT", 56, 24, 100.0f}, {"TIME BASE TORTURE", 256, 5, 80.0f},
                            {"MEDIA ARCHIVE PROJECT", 322, 4, 60.0f}}, 3};
static TextCard s_card = {{{"TBT", 180, 12, 100.0f}}, 1};

static float px_width(int px) { return px * 0.75f / ACTIVE_ROWS; }  // a square font pixel, as a fraction of the width

bool set_card_text(const char *spec) {
    // "px:text|px:text|..." (up to 6 lines); a line too wide for its size is
    // shrunk to fit; the block is centred above the bar strip.
    static const float IRE[LINES_MAX] = {100, 90, 80, 75, 70, 65};
    TextCard c = {};
    const char *p = spec;
    while (*p && c.n < LINES_MAX) {
        TextLine &L = c.line[c.n];
        char *end;
        long px = strtol(p, &end, 10);
        if (end == p || *end != ':') return false;
        p = end + 1;
        int k = 0;
        while (*p && *p != '|' && k < TEXT_MAX) L.text[k++] = *p++;
        L.text[k] = 0;
        while (*p && *p != '|') p++;
        if (*p == '|') p++;
        int cols = 6 * k - 1;
        L.px = (int)px < 2 ? 2 : (int)px > 24 ? 24 : (int)px;
        while (L.px > 2 && cols > 0 && cols * px_width(L.px) > 0.92f) L.px--;
        L.ire = IRE[c.n];
        c.n++;
    }
    if (!c.n) return false;
    int gap = 20, h = 0;
    for (int i = 0; i < c.n; i++) h += 7 * c.line[i].px + (i ? gap : 0);
    int top = (BARS_TOP - 16 - h) / 2;
    if (top < 8) top = 8;
    for (int i = 0; i < c.n; i++) {
        c.line[i].top = top;
        top += 7 * c.line[i].px + gap;
    }
    s_card = c;
    return true;
}

// Keys: 0 black, 1 the bar strip, 2 + 8 * line + font row for text.
static int text_key(const TextCard &c, int row) {
    for (int i = 0; i < c.n; i++) {
        int r = row - c.line[i].top;
        if (r >= 0 && r < 7 * c.line[i].px) return 2 + 8 * i + r / c.line[i].px;
    }
    if (row >= BARS_TOP && row < BARS_TOP + BARS_ROWS) return 1;
    return 0;
}
static int text_segs(const TextCard &c, int key, Segment *o, int max) {
    if (key == 1) {
        const float x0 = 0.15f, w = 0.7f / 7.0f;
        int n = 0;
        o[n++] = luma(0, x0, IRE_SETUP);
        for (int i = 0; i < 7; i++) o[n++] = rgb(x0 + i * w, x0 + (i + 1) * w, BARS75[i][0], BARS75[i][1], BARS75[i][2]);
        o[n++] = luma(x0 + 7 * w, 1, IRE_SETUP);
        return n;
    }
    o[0] = luma(0, 1, IRE_SETUP);  // black background; text runs add to it
    if (key < 2 || (key - 2) / 8 >= c.n) return 1;
    const TextLine &L = c.line[(key - 2) / 8];
    const int r = (key - 2) % 8;
    const float pw = px_width(L.px);
    const int len = (int)strlen(L.text), cols = 6 * len - 1;
    const float left = 0.5f - 0.5f * cols * pw;
    int n = 1, run = -1;
    for (int col = 0; col <= cols && n < max; col++) {  // one segment per run of lit pixels
        bool lit = col < cols && (col % 6) < 5 && (glyph_row(L.text[col / 6], r) >> (4 - col % 6) & 1);
        if (lit && run < 0) run = col;
        if (!lit && run >= 0) {
            o[n++] = luma(left + run * pw, left + col * pw, L.ire - (float)IRE_SETUP);
            run = -1;
        }
    }
    return n;
}
static int title_key(int row) { return text_key(s_title, row); }
static int title_segs(int key, Segment *o, int max) { return text_segs(s_title, key, o, max); }
static int card_key(int row) { return text_key(s_card, row); }
static int card_segs(int key, Segment *o, int max) { return text_segs(s_card, key, o, max); }

const Pattern PATTERNS[] = {
    {"smpte_bars", smpte_key, smpte_segs},
    {"eia_bars_75", one_key, eia_segs},
    {"staircase", one_key, stair_segs},
    {"flat", one_key, flat_segs},
    {"crosshatch", xhatch_key, xhatch_segs},
    {"black", one_key, black_segs},
    {"title", title_key, title_segs},
    {"card", card_key, card_segs},
};
const int NUM_PATTERNS = sizeof(PATTERNS) / sizeof(PATTERNS[0]);
