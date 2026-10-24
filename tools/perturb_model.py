"""Reference implementation of the generator's perturbation model ("perturb/1")
and frame marker, for the grader and for verifying the firmware.

Mirrors src/perturb.cpp and src/marker.cpp. Every perturbation is a pure
function of the absolute line number n = frame * 525 + line_index.
"""
import math

SAMPLE_HZ = 4 * 315e6 / 88
SAMPLE_NS = 1e9 / SAMPLE_HZ
SAMPLES_PER_LINE = 910
LINES_PER_FRAME = 525
FH_HZ = SAMPLE_HZ / SAMPLES_PER_LINE
M32 = 0xFFFFFFFF


def hash32(x):
    """lowbias32 (Chris Wellons)."""
    x &= M32
    x ^= x >> 16; x = (x * 0x7FEB352D) & M32
    x ^= x >> 15; x = (x * 0x846CA68B) & M32
    x ^= x >> 16
    return x


def gauss(seed, n):
    """Approx. N(0,1): Irwin-Hall sum of four 16-bit uniforms."""
    s = sum(hash32((seed + 0x9E3779B9 * (4 * n + i)) & M32) & 0xFFFF for i in range(4))
    return (s - 4 * 32767.5) / (65536.0 * 0.57735027)


def phase_inc(test):
    """Integer phase step per line of a periodic test (H2, F3, L3): round(2^32 f / fH)."""
    if "phase_inc" in test:
        return test["phase_inc"]
    tid, p = test["id"], test["params"]
    hz = p["hz"] if tid in ("H2", "H6") else 1.0 / p["period_s"] if tid == "F3" else 60.0 if tid == "L3" else 0.0
    return lround(4294967296.0 * hz / FH_HZ)


def cycle(test, n):
    """Fraction of a cycle of line n: low 32 bits of n * phase_inc, over 2^32."""
    return ((n * phase_inc(test)) & M32) / 4294967296.0


LINE_NS = 1e9 / FH_HZ
FIELD_MS = 262.5 * 1e3 / FH_HZ                                  # 16.683 ms
# An output locked to its input reads 0.0 +- 0.1 ppm against it (Pioneer
# DVR-220, Panasonic DMR-ES10). A free-running clock can sit close to the
# input's: a blind-tested Datavideo-family unit held a steady +1.75 ppm.
LOCKED_PPM = 0.5


HUNT_CYCLE, HUNT_STRESS_START, HUNT_STRESS_END = 90, 30, 60   # X1: clean, stress, clean (frames)
LOSS_PERIOD = 60                                                # S10/S11: fields per loss cycle


HUNT_SETTLE = 3   # frames after a stress burst a TBC may still show its effects (frame-store delay)


def hunt_window(frame, settle=False):
    """X1: 'before', 'stress' or 'after' for an input frame number; with settle=True
    the first HUNT_SETTLE frames after stress are 'settling'."""
    ph = frame % HUNT_CYCLE
    if ph < HUNT_STRESS_START:
        return "before"
    if ph < HUNT_STRESS_END:
        return "stress"
    return "settling" if settle and ph < HUNT_STRESS_END + HUNT_SETTLE else "after"


def shift_ns(test, n):
    """Target sync shift of absolute line n, ns. `test` is the manifest's test dict."""
    tid, p = test["id"], test["params"]
    if tid == "X1":  # stress types 1, 4, 5 jitter; 5 adds a 5 us head-switch skew
        if hunt_window(n // LINES_PER_FRAME) != "stress":
            return 0.0
        s, L = int(p["stress"]), n % LINES_PER_FRAME + 1
        ns = 200.0 * gauss(test["seed"], n) if s == 1 else 100.0 * gauss(test["seed"], n) if s in (4, 5) else 0.0
        if s == 5 and not (257 <= L < 520):
            ns += 5000.0
        return ns
    if tid == "H1":
        return p["rms_ns"] * gauss(test["seed"], n)
    if tid in ("H2", "H6"):
        return p["peak_ns"] * math.sin(2 * math.pi * cycle(test, n))
    if tid == "F2":  # H runs p ppm fast against a fixed subcarrier
        return -n * LINE_NS * p["ppm"] * 1e-6
    if tid == "F3":  # rate offset peak_ppm sin(2 pi t / period), integrated; 1 - cos x = 2 sin^2(x/2)
        amp = p["peak_ppm"] * 1e-6 * p["period_s"] / (2 * math.pi) * 1e9
        return -amp * 2 * math.sin(math.pi * cycle(test, n)) ** 2
    if tid == "H3":
        return p["step_us"] * 1000.0 if (n // 7867) & 1 else 0.0
    if tid == "H4":
        L = n % LINES_PER_FRAME + 1
        return 0.0 if 257 <= L < 520 else p["skew_us"] * 1000.0
    if tid == "H5":
        L = n % LINES_PER_FRAME + 1
        return p["samples"] * SAMPLE_NS if L in (100, 362) else 0.0
    return 0.0


HALF_SAMPLES = 456  # a lone half-line, rounded to the DAC's sample pairs
SLOT_HALF, SLOT_ALT, SLOT_NOISE, SLOT_DROPOUT, SLOT_DEAD = 1, 2, 4, 8, 64
NOISE_VARIANTS = 4
DROPOUT_VARIANTS = 4
DROPOUT_POS = (0.15, 0.35, 0.55, 0.75)        # dropout start, fraction of the active width
ACTIVE_START_US, ACTIVE_WIDTH_US = 9.4, 52.6  # picture window after the sync point
FRAME_HZ = FH_HZ / LINES_PER_FRAME

# Render modifiers for SLOT_ALT lines (src/line_render.h)
MOD_NO_HSYNC, MOD_EQ_AS_HSYNC, MOD_VS_UNSERRATED, MOD_VS_AS_EQ = 1, 2, 4, 8
MOD_AGC_OFF, MOD_BURST_INV = 32, 64                              # B3


def line_halves(L):
    """(first half, second half) of NTSC line L: 'EQ', 'VS', 'BLANK' or 'ACTIVE'."""
    if L <= 3: return "EQ", "EQ"
    if L <= 6: return "VS", "VS"
    if L <= 9: return "EQ", "EQ"
    if L <= 20: return "BLANK", "BLANK"
    if L <= 262: return "ACTIVE", "ACTIVE"
    if L == 263: return "ACTIVE", "EQ"
    if L <= 265: return "EQ", "EQ"
    if L == 266: return "EQ", "VS"
    if L <= 268: return "VS", "VS"
    if L == 269: return "VS", "EQ"
    if L <= 271: return "EQ", "EQ"
    if L == 272: return "EQ", "BLANK"
    if L <= 282: return "BLANK", "BLANK"
    if L == 283: return "BLANK", "ACTIVE"
    return "ACTIVE", "ACTIVE"


def alt_mods(test, L):
    """Render modifiers of line L's SLOT_ALT copy (0 = never altered)."""
    tid, p = test["id"], test["params"]
    if tid == "S3":
        return MOD_NO_HSYNC if 100 <= L < 100 + int(p["lines"]) else 0
    if tid == "B3":
        if agc_line(L):
            return MOD_AGC_OFF if int(p["mode"]) >= 2 else 0
        return MOD_BURST_INV if int(p["mode"]) == 3 and stripe_line(L) else 0
    if tid != "S4":
        return 0
    h = line_halves(L)
    eq, vs = "EQ" in h, "VS" in h
    v = int(p["variant"])
    if v == 1: return MOD_EQ_AS_HSYNC if eq else 0
    if v == 2: return MOD_VS_UNSERRATED if vs else 0
    if v == 3: return (MOD_EQ_AS_HSYNC if eq else 0) | (MOD_VS_UNSERRATED if vs else 0)
    if v in (4, 5): return MOD_VS_AS_EQ if vs and L <= 9 else 0
    if v == 6: return MOD_VS_AS_EQ if vs else 0
    return 0


def lround(x):
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def wow_lines(test, frame):
    """S8: lines added (>0) or removed (<0) per field in this frame."""
    p = test["params"]
    return lround(p["peak_lines"] * math.sin(2 * math.pi * p["hz"] * frame / FRAME_HZ))


def noise_variant(frame, slot):
    return (frame * 7 + slot) % NOISE_VARIANTS


def mix32(x):
    return hash32(x)


def snow_ire(seed, k):
    """Snow sample k of rendering `seed`: uniform -15..100 IRE (src/line_render.cpp snow_ire)."""
    x = hash32((seed * 0x9E3779B9 + k * 0x85EBCA6B) & M32)
    return -15.0 + 115.0 * (x & 0xFFFF) / 65535.0


def noise_sample(seed, k):
    """Approx. N(0,1) noise sample k (src/line_render.cpp noise_sample)."""
    s = sum(hash32((seed * 0x9E3779B9 + 4 * k + i) & M32) & 0xFFFF for i in range(4))
    return (s - 4 * 32767.5) / (65536.0 * 0.57735027)


# ---- Rendering style and per-line variants (C, L and S1/S2 tests) ----------
def base_style(test):
    """Static rendering changes for the whole test (src/perturb.cpp base_style)."""
    tid, p = test["id"], test["params"]
    st = {"sync_ire": -40.0, "sync_edge_samples": 3.4, "burst_amp_ire": 20.0, "chroma_rot_deg": 0.0,
          "video_gain": 1.0, "noise_rms_ire": 0.0}
    if tid == "S1": st["sync_ire"] = -p["sync_ire"]
    if tid == "S2": st["sync_edge_samples"] = p["rise_ns"] / 0.59 / SAMPLE_NS
    if tid == "C1": st["burst_amp_ire"] = p["burst_pp_ire"] / 2
    if tid == "C2": st["burst_amp_ire"] = 0.0
    if tid == "C4": st["chroma_rot_deg"] = p["deg"]
    if tid == "L2": st["noise_rms_ire"] = 100.0 / 10 ** (p["snr_db"] / 20)
    if tid == "L4": st["video_gain"] = p["white_pct"] / 100.0
    return st


def variant_mode(test):
    return {"C3": "carrier", "L2": "noise", "L3": "dc"}.get(test["id"], "timing")


def line_variant(test, n, nsub):
    """Which pre-rendered copy line n uses in the carrier/noise/dc modes."""
    if nsub <= 1:
        return 0
    mode, p = variant_mode(test), test["params"]
    clamp = lambda v: max(0, min(nsub - 1, v))
    if mode == "carrier":
        step = 2 * 3.47 * p["rms_deg"] / (nsub - 1)
        return clamp(lround(p["rms_deg"] * gauss(test["seed"], n) / step + (nsub - 1) / 2))
    if mode == "noise":
        return hash32((test["seed"] * 0x9E3779B9 + n) & M32) % nsub
    if mode == "dc":
        h = 0.5 * math.sin(2 * math.pi * cycle(test, n))
        return clamp(lround((h + 0.5) * (nsub - 1)))
    return 0


def variant_value(test, v, nsub):
    """What copy v carries: carrier phase (deg), DC level (IRE) or noise seed."""
    mode, p = variant_mode(test), test["params"]
    mid = (nsub - 1) / 2
    if mode == "carrier":
        return (v - mid) * 2 * 3.47 * p["rms_deg"] / (nsub - 1) if nsub > 1 else 0.0
    if mode == "dc":
        return -0.5 * p["pp_ire"] + v * p["pp_ire"] / (nsub - 1) if nsub > 1 else 0.0
    if mode == "noise":
        return v + 1
    return 0.0


def dropout_lines(test, frame):
    """L1: {line: variant} of the lines carrying a dropout in this frame."""
    out = {}
    for j in range(int(test["params"]["per_field"])):
        L = 30 + hash32((test["seed"] * 2654435761 + frame * 64 + j) & M32) % 141
        out[L] = out[L + 262] = j % DROPOUT_VARIANTS
    return out


def dropout_span_us(test, var):
    """L1: (start, end) of dropout variant `var`, us after the sync point (always inside the picture)."""
    length = test["params"]["length_us"]
    t0 = ACTIVE_START_US + DROPOUT_POS[var] * max(0.0, ACTIVE_WIDTH_US - length)
    return t0, t0 + length


def noise_ire(variant, k):
    """IRE of sample k of snow rendering `variant` (src/line_render.cpp render_noise)."""
    x = ((variant + 1) * 0x9E3779B9 + k * 0x85EBCA6B) & M32
    x ^= x >> 16; x = (x * 0x7FEB352D) & M32
    x ^= x >> 15; x = (x * 0x846CA68B) & M32
    x ^= x >> 16
    return -15.0 + 115.0 * (x & 0xFFFF) / 65535.0


def frame_slots(test, frame):
    """Lines played for `frame`: list of (ntsc_line 1..525, flags)."""
    tid, p = test["id"], test["params"]
    if tid == "S5":  # 240p: two 262-line fields with field-1 timing
        return [(L, 0) for _ in range(2) for L in range(1, 263)]
    if tid == "B1" and int(p["disruption"]) == 2:  # as S10: CC_LOST fields of no signal per LOSS_PERIOD
        return [(L, SLOT_DEAD if (2 * frame + (L >= 264)) % LOSS_PERIOD < CC_LOST else 0)
                for L in range(1, LINES_PER_FRAME + 1)]
    if tid == "S7" or (tid == "B1" and int(p["disruption"]) == 1):
        every = int(p["every_frames"]) if tid == "S7" else CC_DROP_EVERY
        if frame % every == every - 1:  # field 1 only, ending half-way along line 263
            return [(L, 0) for L in range(1, 263)] + [(263, SLOT_HALF)]
    if tid in ("S6", "S8"):
        d = int(p["delta_lines"]) if tid == "S6" else wow_lines(test, frame)
        out = []
        for L in range(1, LINES_PER_FRAME + 1):
            if d < 0 and (200 <= L < 200 - d or 462 <= L < 462 - d):
                continue
            out.append((L, 0))
            if d > 0 and L in (200, 462):
                out += [(L, 0)] * d
        return out
    if tid == "S9":  # a band of snow moving down 23 lines a frame through lines 30..229 (+263)
        top, h = 30 + (frame * 23) % 200, int(p["lines"])
        return [(L, SLOT_NOISE if top <= L < top + h or top + 263 <= L < top + 263 + h else 0)
                for L in range(1, LINES_PER_FRAME + 1)]
    if tid == "S4":
        v = int(p["variant"])
        active = frame % 30 == 0 if v == 4 else frame % 6 == 0 if v == 5 else True
        return [(L, SLOT_ALT if active and alt_mods(test, L) else 0) for L in range(1, LINES_PER_FRAME + 1)]
    if tid == "S3":
        return [(L, SLOT_ALT if alt_mods(test, L) else 0) for L in range(1, LINES_PER_FRAME + 1)]
    if tid == "B3":  # AGC lines take their off rendering in the cycle's off half; stripes always
        off = not agc_on(test, frame)
        return [(L, SLOT_ALT if alt_mods(test, L) and (off if agc_line(L) else True) else 0)
                for L in range(1, LINES_PER_FRAME + 1)]
    if tid in ("S10", "S11", "V1"):  # lost fields: field 1 = lines 1..263, field 2 = 264..525
        lost = SLOT_NOISE if tid == "S11" else SLOT_DEAD
        n = 10 ** 9 if tid == "V1" else int(p["fields"])
        return [(L, lost if (2 * frame + (L >= 264)) % LOSS_PERIOD < n else 0) for L in range(1, LINES_PER_FRAME + 1)]
    if tid == "X1":
        s, stress = int(p["stress"]), hunt_window(frame) == "stress"
        if s == 2 and stress and frame & 1:  # field 1 only, ending half-way along line 263
            return [(L, 0) for L in range(1, 263)] + [(263, SLOT_HALF)]
        top, h, out = 30 + (frame * 23) % 200, 40 if s == 4 else 20, []
        for L in range(1, LINES_PER_FRAME + 1):
            f, field = 0, 2 * frame + (L >= 264)
            if stress and s == 3 and field % 20 < 3: f = SLOT_DEAD
            if stress and s == 5 and field % 30 < 2: f = SLOT_DEAD
            if stress and s in (4, 5) and not f and (top <= L < top + h or top + 263 <= L < top + 263 + h):
                f = SLOT_NOISE
            out.append((L, f))
        return out
    if tid == "L1":
        d = dropout_lines(test, frame)
        return [(L, SLOT_DROPOUT | (d[L] << 4) if L in d else 0) for L in range(1, LINES_PER_FRAME + 1)]
    return [(L, 0) for L in range(1, LINES_PER_FRAME + 1)]


def nominal_samples(flags):
    return HALF_SAMPLES if flags & SLOT_HALF else SAMPLES_PER_LINE


def frame_start_mod4(test, frame):
    """Nominal samples played before `frame`, mod 4 (sets the subcarrier phase)."""
    return sum(nominal_samples(f) for fr in range(frame) for _, f in frame_slots(test, fr)) % 4


def plan(test, n, nsub):
    """(e, v) of absolute line n as played: timing tests quantize the shift;
    C3/L2/L3 pick a copy and leave timing alone."""
    if variant_mode(test) != "timing":
        return 0, line_variant(test, n, nsub)
    if test["id"] == "F2":  # exact integer quantization (shifts land on half-steps)
        q = -((n * 910 * lround(test["params"]["ppm"]) * nsub + 1000000) // 2000000)
        e2 = q // nsub
        return 2 * e2, q - e2 * nsub
    return quantize(shift_ns(test, n), nsub)


def quantize(shift, nsub):
    """(e, v): whole-sample even offset and sub-sample step index, as played."""
    q = int(math.floor(shift / SAMPLE_NS / (2.0 / nsub) + 0.5)) if shift >= 0 else \
        -int(math.floor(-shift / SAMPLE_NS / (2.0 / nsub) + 0.5))
    e2 = q // nsub
    return 2 * e2, q - e2 * nsub


def played_ns(e, v, nsub):
    return (e + v * 2.0 / nsub) * SAMPLE_NS


def crc4(d28):
    crc = 0
    for i in range(27, -1, -1):
        bit = ((d28 >> i) & 1) ^ ((crc >> 3) & 1)
        crc = (crc << 1) & 0xF
        if bit:
            crc ^= 0x3
    return crc


def marker_word(code, rung, frame):
    d = (code << 20) | ((rung & 0xF) << 16) | (frame & 0xFFFF)
    return (d << 4) | crc4(d)


def decode_marker(bits36):
    """bits36: 36 cell values (0/1). Returns (code, rung, frame) or None if invalid."""
    if list(bits36[:2]) != [1, 0] or list(bits36[-2:]) != [0, 1]:
        return None
    w = 0
    for b in bits36[2:34]:
        w = (w << 1) | int(b)
    d = w >> 4
    if crc4(d) != (w & 0xF):
        return None
    return d >> 20, (d >> 16) & 0xF, d & 0xFFFF


# ---- Vertical blanking data (B tests; src/vbi.h) ------------------------------
CC_LINES = (21, 284)                 # line 21 of each field
CC_IRE = 50.0
CC_RUNIN_US, CC_START_US, CC_RUNIN_CYCLES = 10.5, 27.382, 7
CC_BIT_US = 1e6 / (32 * FH_HZ)       # 1.986 us
CC_CYCLE = 32                        # frames per field-1 caption cycle
CC_DROP_EVERY, CC_LOST = 30, 2       # B1 rungs 2 and 3
CC_ROWS = ("Brought to you by the", "Media Archive Project")
MAP_F1, MAP_F2 = (10, 20), (273, 282)
ID_START_US, ID_CELL_US, ID_CELLS = 12.0, 1.5, 9
STAIR_US, STAIR_IRE = (30.0, 38.0, 46.0, 54.0), (25.0, 50.0, 75.0)


def with_parity(c):
    c &= 0x7F
    return c if bin(c).count("1") % 2 else c | 0x80


def _f1_bytes(i):
    def text(row, j):
        s = CC_ROWS[row]
        return [ord(s[k]) if k < len(s) else 0 for k in (2 * j, 2 * j + 1)]
    if i < 2: return [0x14, 0x20]            # RCL: resume caption loading
    if i < 4: return [0x14, 0x2E]            # ENM: erase non-displayed memory
    if i < 6: return [0x14, 0x52]            # PAC: row 14, indent 4
    if i < 17: return text(0, i - 6)
    if i < 19: return [0x14, 0x72]           # PAC: row 15, indent 4
    if i < 30: return text(1, i - 19)
    return [0x14, 0x2F]                      # EOC: end of caption (display it)


def cc_pair(field, frame):
    """The two bytes (parity included) line 21 of `field` (1 or 2) carries in `frame`."""
    b = _f1_bytes(frame % CC_CYCLE) if field == 1 else [0x20 + (frame & 0x3F), 0x20 + ((frame >> 6) & 0x3F)]
    return with_parity(b[0]), with_parity(b[1])


def cc_frame_of_f2(b0, b1):
    """Field 2's frame counter (12 bits) from its bytes, or None if they aren't one."""
    c0, c1 = b0 & 0x7F, b1 & 0x7F
    if not (0x20 <= c0 < 0x60 and 0x20 <= c1 < 0x60):
        return None
    return (c0 - 0x20) | ((c1 - 0x20) << 6)


def map_id(L):
    """B2 line-map ID (1..11) NTSC line L carries, or 0."""
    for a, b in (MAP_F1, MAP_F2):
        if a <= L <= b:
            return L - a + 1
    return 0


def id_cells(k):
    bits = [(k >> 3) & 1, (k >> 2) & 1, (k >> 1) & 1, k & 1]
    return [1, 0] + bits + [0 if sum(bits) % 2 else 1, 0, 1]


def decode_id(cells):
    """9 cells (0/1) -> k, or None if the framing or parity is wrong."""
    c = [int(v) for v in cells]
    if c[:2] != [1, 0] or c[7:] != [0, 1] or sum(c[2:7]) % 2 != 1:
        return None
    return (c[2] << 3) | (c[3] << 2) | (c[4] << 1) | c[5]


# ---- AGC pulses (B3; src/vbi.h) ----------------------------------------------
# Macrovision-like, from the Ryan patents (US4631603, US4819098): the licensed
# production spec isn't public.
AGC_F1, AGC_F2 = (12, 19), (275, 282)
AGC_PAIRS, AGC_START_US, AGC_PAIR_US = 6, 12.0, 8.0
PSEUDO_US, AGC_GAP_US, AGC_US = 2.0, 1.0, 3.0
PSEUDO_IRE, AGC_IRE = -40.0, 110.0
AGC_CYCLE = 30                                   # frames on, then frames off
STRIPE_F1, STRIPE_F2, STRIPE_EVERY, STRIPE_LINES = (30, 250), (293, 513), 20, 4


def agc_line(L):
    return AGC_F1[0] <= L <= AGC_F1[1] or AGC_F2[0] <= L <= AGC_F2[1]


def stripe_line(L):
    for a, b in (STRIPE_F1, STRIPE_F2):
        if a <= L <= b:
            return (L - a) % STRIPE_EVERY < STRIPE_LINES
    return False


def agc_on(test, frame):
    """B3: whether the AGC pulses are up in `frame` (always, on rung 1)."""
    return test["id"] != "B3" or int(test["params"]["mode"]) < 2 or frame % (2 * AGC_CYCLE) < AGC_CYCLE


def agc_windows():
    """[(kind, t0_us, t1_us)] of one AGC line: 'pseudo' and 'agc' pulses."""
    out = []
    for k in range(AGC_PAIRS):
        t = AGC_START_US + k * AGC_PAIR_US
        a = t + PSEUDO_US + AGC_GAP_US
        out += [("pseudo", t, t + PSEUDO_US), ("agc", a, a + AGC_US)]
    return out
