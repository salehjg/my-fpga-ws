# Flash backup, unit 0265

The full 64 MB of the BPI configuration flash (U4, Micron MT28GU512AAA1EGC), read on **2026-11-18** from unit 0265 as it came, before anything was written to it. It was read over JTAG with [`../tools/flash_reader/`](../tools/flash_reader/). Vivado's own *Readback Configuration Memory Device* does not work on this card ([§3 "Keep-alive pin AC24" and §6 "Configuration flash" of the board README](../README.md#3-keep-alive-pin-ac24)).

| File | What it is |
|---|---|
| `unit0265_flash_2026-11-18.bin` | The whole flash, 67,108,864 bytes |
| `unit0265_flash_2026-11-18.mcs.gz` | The same data as Intel HEX (`.mcs`, 184 MB unpacked), gzip-compressed. Unpack it with `gunzip -k` before use |
| `unit0265_vendor_sector_0x3FC0000.bin` | The last 256 KB block on its own (the vendor record, see below) |
| `SHA256SUMS` | Checksums. Check them with `sha256sum -c SHA256SUMS` (the `.mcs` line refers to the unpacked file) |

**Byte order.** This is the same layout as Vivado's `write_cfgmem` / `readback_hw_cfgmem` for BPI x16. Each 16-bit flash word `DQ[15:0]` is stored high byte first, and the bits are swapped as stored in the flash. Reversing the bits of each byte gives the plain bitstream (sync word `AA995566`).

**Contents.**

| Address range | Contents |
|---|---|
| `0x0000000`–`0x11DDF9B` | The vendor's FPGA design: an **xc7k480t** bitstream (IDCODE `03751093`), sync word at `0x30`, about 17.9 MB, uncompressed. It is what the card boots at power-up. It keeps pin AC24 high, which is why the card does not clear it |
| `0x11DDF9C`–`0x3FBFFFF` | Erased (`0xFF`) |
| `0x3FC0000`–`0x3FC03DF` | **Vendor record** in the last 256 KB block: the ASCII string `CS-H00-100-3026120810-62 5`, plus about 130 bytes of binary data. Probably a Celestica part/serial or board-identity record. Keep it when restoring |
| `0x3FC03E0`–`0x3FFFFFF` | Erased |

Sanity checks passed:
- the image at 0 has a valid sync word and the right IDCODE;
- the two 32 MB halves and the first two 16 MB quarters differ, so the top address lines work (no mirroring);
- all 65,536 reads completed with no errors.

**Restoring.** Write `unit0265_flash_2026-11-18.bin` (or the unpacked `.mcs`) to the whole flash. The writing tool for this card is still TODO, because Vivado's flash programming is cleared by the card ([board README §6.5](../README.md#65-writing-the-flash)). Then verify by re-reading with `tools/flash_reader/dump.tcl` and comparing SHA-256.

**Size.** The `.bin` is 64 MB and the `.mcs.gz` about 23 MB. Consider tracking them with Git LFS (`git lfs track "boards/DU-PCB-001-003/flash_backup/*.bin" "*.mcs.gz"`) before committing.
