"""Talk to the generator over serial.

usage: gen_cmd.py "p staircase" ["info" ...]

The port is auto-detected (first /dev/cu.wchusbserial*), or set GEN_PORT.
Other tools import open_gen() and request() from here.
"""
import glob, os, sys, time

import serial

BAUD = 921600  # must match Serial.begin() in src/main.cpp


def port():
    p = os.environ.get("GEN_PORT") or next(iter(sorted(glob.glob("/dev/cu.wchusbserial*"))), None)
    if not p:
        sys.exit("no generator serial port found")
    return p


def open_gen():
    s = serial.Serial(port(), BAUD, timeout=0)
    time.sleep(0.2)
    s.reset_input_buffer()
    return s


def request(s, cmd, until=None, timeout=10.0, quiet=0.3):
    """Send `cmd` and return the reply text.

    Returns as soon as `until` appears in the reply, or, with until=None, once
    the line has been quiet for `quiet` seconds. Reads only what has arrived,
    so it never blocks waiting for a full buffer.
    """
    s.reset_input_buffer()
    s.write((cmd + "\n").encode())
    buf, t0, last = b"", time.time(), time.time()
    while time.time() - t0 < timeout:
        n = s.in_waiting
        if n:
            buf += s.read(n)
            last = time.time()
            if until is not None and until.encode() in buf:
                break
        elif until is None and buf and time.time() - last > quiet:
            break
        else:
            time.sleep(0.002)
    return buf.decode(errors="replace")


class TransferError(RuntimeError):
    pass


DUMP_RETRIES = 0   # dumps re-read because their count or sum didn't match


def dump_line(s, idx, tries=4):
    """DAC codes of ring line `idx` as played (numpy float array).

    The serial link occasionally drops a byte, which would shift every sample
    after it. The firmware sends the sample count and their sum: anything that
    doesn't match is read again, and never used."""
    global DUMP_RETRIES
    import numpy as np
    for attempt in range(tries):
        DUMP_RETRIES += attempt > 0
        lines = request(s, f"dump {idx}", until="sum=", timeout=5).splitlines()
        try:
            i = next(k for k, l in enumerate(lines) if l.startswith(f"line {idx} "))
            n = int(lines[i].split("n=")[1])
            end = next(l for l in lines[i + 1:] if l.startswith("end"))
            want = int(end.split("sum=")[1]) if "sum=" in end else None
            hexs = "".join(l.strip() for l in lines[i + 1:] if l.strip() and not l.startswith("end"))
            if len(hexs) != 2 * n:
                continue
            codes = np.array([int(hexs[j:j + 2], 16) for j in range(0, 2 * n, 2)], float)
        except (StopIteration, ValueError, IndexError):
            continue
        if want is None or int(codes.sum()) == want:
            return codes
    raise TransferError(f"dump {idx}: no intact copy in {tries} tries")


if __name__ == "__main__":
    s = open_gen()
    for c in sys.argv[1:]:
        print(request(s, c).strip())
