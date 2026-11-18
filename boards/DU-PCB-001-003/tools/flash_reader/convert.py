#!/usr/bin/env python3
"""Convert dump.tcl's raw_hex.txt into flash images.

raw_hex.txt: one line per 1 KB AXI burst: "<offset hex> <DATA hex>", where DATA is
Vivado's hw_axi string (256 x 32-bit beats, LAST beat leftmost). Each 32-bit beat is
little-endian over AXI byte addresses, and each 16-bit half is one flash word (DQ[15:0]).

Outputs (same order as Vivado's write_cfgmem/readback_hw_cfgmem for BPI x16:
each flash word written high byte first):
  <out>.bin  - 64 MB flash image
  <out>.mcs  - same data as Intel HEX
and prints a sanity check: the bit-swapped sync word and the IDCODE of the image at 0.
"""
import sys, hashlib

def main(raw, out):
    img = bytearray()
    expect = 0
    for line in open(raw):
        off_s, data = line.split()
        off = int(off_s, 16)
        assert off == expect, f"gap at {off:#x} (expected {expect:#x})"
        beats = [int(data[i:i+8], 16) for i in range(0, len(data), 8)][::-1]  # first beat first
        for w32 in beats:
            for half in (w32 & 0xFFFF, w32 >> 16):         # lower AXI address first
                img += bytes((half >> 8, half & 0xFF))      # flash word, high byte first
        expect = off + 4 * len(beats)
    open(out + ".bin", "wb").write(img)

    # Intel HEX
    with open(out + ".mcs", "w") as f:
        def rec(t, addr, payload):
            b = bytes([len(payload), (addr >> 8) & 0xFF, addr & 0xFF, t]) + payload
            f.write(":" + b.hex().upper() + f"{(-sum(b)) & 0xFF:02X}\n")
        for base in range(0, len(img), 0x10000):
            rec(4, 0, bytes([(base >> 24) & 0xFF, (base >> 16) & 0xFF]))
            for a in range(0, min(0x10000, len(img) - base), 16):
                rec(0, a, bytes(img[base + a: base + a + 16]))
        rec(1, 0, b"")

    rev = bytes(int(f"{b:08b}"[::-1], 2) for b in img[:4096])   # undo the BPI bit swap
    sync = rev.find(bytes.fromhex("AA995566"))
    idc = rev.find(bytes.fromhex("30018001"))
    idcode = rev[idc + 4: idc + 8].hex() if idc >= 0 else None
    used = len(img.rstrip(b"\xff"))
    print(f"size {len(img)} bytes, sha256 {hashlib.sha256(img).hexdigest()}")
    print(f"sync word at {sync:#x}" if sync >= 0 else "NO sync word in the first 4 KB")
    print(f"IDCODE {idcode} (xc7k480t = 03751093)" if idcode else "NO IDCODE packet found")
    print(f"last non-0xFF byte at {used - 1:#x} ({used / 1048576:.1f} MB used)")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "dupcb_flash_backup")
