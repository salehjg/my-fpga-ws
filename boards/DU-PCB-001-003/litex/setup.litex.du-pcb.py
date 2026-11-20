#!/usr/bin/env python3
"""LiteX for the DU-PCB-001-003 card: the whole project in one file.

The project files (board, daily scripts, README) are stored at the end of this file as comment
lines, so the file stays valid Python. Running it unfolds them into a work directory and sets that
up: LiteX release, Python venv, tool paths. Standard library only; runs on Python 3.6+ (LiteX
itself needs 3.8+, see --python). Safe to run again: files you changed are kept unless --force.

    python3 setup.litex.du-pcb.py                  set up in the current directory
    python3 setup.litex.du-pcb.py --workdir DIR    set up in DIR (created if missing)
    python3 setup.litex.du-pcb.py --help           all options

Maintaining this file:
  - Edit the unfolded files as usual, then run this script with --pack in the work directory:
    the files listed in FILES go back into the archive below. Never edit the archive by hand.
  - New project file: add its path to FILES, then --pack.
  - New setup step: write a function for it and call it from main().
  - Archive format: "#@@ FILE <path> <mode>", every line of the file as "#|<line>", "#@@ END".
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

if sys.version_info < (3, 6):
    sys.exit("This script needs Python 3.6 or newer (you have {}).".format(sys.version.split()[0]))

from urllib.request import urlopen

# Settings -----------------------------------------------------------------------------------------

LITEX_TAG      = "2026.08"                    # LiteX release to use.
LITEX_URL      = "https://github.com/enjoy-digital/litex/archive/refs/tags/{}.zip"
LITEX_PYTHON   = (3, 8)                       # Oldest Python the LiteX packages accept.
XILINX_ROOTS   = ["/tools/Xilinx", "/opt/Xilinx", "/opt/xilinx", "~/Xilinx"]   # Searched for Vivado.
ARCHIVE_MARKER = "# ==== ARCHIVE: written by --pack, do not edit by hand ===="

# Files in the bundle, relative to the work directory. Add new project files here, then --pack.
FILES = [
    "README.md",
    ".gitignore",
    "boards/dupcb/dupcb_platform.py",
    "boards/dupcb/target.py",
    "boards/dupcb/wl7ddrphy.py",
    "boards/dupcb/ddr_init.py",
    "scripts/env.sh",
    "scripts/build.sh",
    "scripts/load.sh",
    "scripts/pcie_rescan.sh",
    "scripts/console.sh",
    "scripts/ddr_init.sh",
    "scripts/status.sh",
    "scripts/sim.sh",
    "scripts/clean.sh",
]

SELF        = os.path.abspath(__file__)
SCRIPT_NAME = "setup.litex.du-pcb.py"         # Name of the copy placed in the work directory.

# Helpers ------------------------------------------------------------------------------------------

def _color(code, text):
    return "\033[{}m{}\033[0m".format(code, text) if sys.stdout.isatty() else text

def say(msg):
    print("{} {}".format(_color("1;32", "[setup]"), msg))
    sys.stdout.flush()

def warn(msg):
    sys.stderr.write("{} {}\n".format(_color("1;33", "[setup]"), msg))

def die(msg):
    warn("error: " + msg)
    sys.exit(1)

def run(cmd, **kwargs):
    """Run a command; stop with a clear message if it fails."""
    if subprocess.call(cmd, **kwargs) != 0:
        die("command failed: " + " ".join(cmd))

def read_text(path):
    """File content as text, or None if missing or not UTF-8."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (IOError, OSError, UnicodeDecodeError):
        return None

def write_text(path, text, mode=0o644):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.chmod(path, mode)

# Bundle: read, unfold, pack -----------------------------------------------------------------------

def read_archive():
    """The bundled files: a list of (path, mode, text)."""
    files, cur, inside = [], None, False
    with open(SELF, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not inside:
                inside = line == ARCHIVE_MARKER
            elif line.startswith("#@@ FILE "):
                _, _, path, mode = line.split(" ", 3)
                cur = (path, int(mode, 8), [])
            elif line == "#@@ END" and cur is not None:
                files.append((cur[0], cur[1], "".join(l + "\n" for l in cur[2])))
                cur = None
            elif line.startswith("#|") and cur is not None:
                cur[2].append(line[2:])
    return files

def unfold(workdir, force):
    """Write every bundled file into workdir. Missing files are created; files that differ from the
    bundle are kept unless force, so local edits survive a re-run."""
    files = read_archive()
    if not files:
        die("no files found in the archive of " + SELF)
    new = updated = kept = 0
    for path, mode, text in files:
        dest = os.path.join(workdir, path)
        current = read_text(dest)
        if current is None and not os.path.exists(dest):
            new += 1
        elif current == text:
            os.chmod(dest, mode)
            continue
        elif force:
            updated += 1
            say("updated " + path)
        else:
            kept += 1
            warn("kept your {} (differs from the bundle; --force overwrites)".format(path))
            continue
        write_text(dest, text, mode)
    # A copy of this script in the work directory, so it can be re-run and packed from there.
    me = os.path.join(workdir, SCRIPT_NAME)
    if os.path.abspath(me) != SELF:
        if not os.path.exists(me) or force:
            shutil.copyfile(SELF, me)
            os.chmod(me, 0o755)
        elif read_text(me) != read_text(SELF):
            warn("kept your {} (differs from {}; --force overwrites)".format(SCRIPT_NAME, SELF))
    say("project files in {}: {} new, {} updated, {} kept".format(workdir, new, updated, kept))

def pack(workdir):
    """Rebuild this script's archive from the work directory's FILES."""
    out = []
    with open(SELF, encoding="utf-8") as f:
        for line in f:
            out.append(line)
            if line.rstrip("\n") == ARCHIVE_MARKER:
                break
        else:
            die("archive marker missing in " + SELF)
    for path in FILES:
        src = os.path.join(workdir, path)
        text = read_text(src)
        if text is None:
            die("missing or not a text file: {} (listed in FILES)".format(src))
        mode = 0o755 if os.access(src, os.X_OK) else 0o644
        out.append("#@@ FILE {} {:o}\n".format(path, mode))
        if text.endswith("\n"):
            text = text[:-1]
        if text:
            out.extend("#|" + line + "\n" for line in text.split("\n"))
        out.append("#@@ END\n")
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(SELF))
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(out)
    os.chmod(tmp, 0o755)
    os.replace(tmp, SELF)
    say("packed {} files from {} into {}".format(len(FILES), workdir, SELF))

# Tools --------------------------------------------------------------------------------------------

def find_vivado_settings(xilinx):
    """Vivado's settings64.sh: from --xilinx, from vivado on PATH, else from XILINX_ROOTS."""
    if xilinx:
        x = os.path.expanduser(xilinx)
        for c in [x, os.path.join(x, "settings64.sh"), os.path.join(x, "Vivado", "settings64.sh")]:
            if os.path.isfile(c):
                return os.path.abspath(c)
        die("no Vivado settings64.sh at " + xilinx)
    vivado = shutil.which("vivado")
    if vivado:
        c = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(vivado))), "settings64.sh")
        if os.path.isfile(c):
            return c
    found = []
    for root in map(os.path.expanduser, XILINX_ROOTS):
        for d, dirs, files in os.walk(root):
            if d[len(root):].count(os.sep) >= 3:
                dirs[:] = []                       # At most 4 levels deep.
            if "settings64.sh" in files and "Vivado" in d:
                found.append(os.path.join(d, "settings64.sh"))
    return sorted(found)[-1] if found else ""

def find_riscv_bin(settings):
    """Folder with riscv64-unknown-elf-gcc: from PATH, else the one shipped with Vitis."""
    gcc = shutil.which("riscv64-unknown-elf-gcc")
    if gcc:
        return os.path.dirname(gcc)
    if not settings:
        return ""
    vivado_dir = os.path.dirname(settings)
    up2 = os.path.dirname(vivado_dir)              # <root>/<ver>/Vivado/settings64.sh -> <root>/<ver>
    up3 = os.path.dirname(up2)                     # <root>/Vivado/<ver>/settings64.sh -> <root>
    for c in [os.path.join(up2, "Vitis", "gnu", "riscv", "lin", "bin"),
              os.path.join(up3, "Vitis", os.path.basename(vivado_dir), "gnu", "riscv", "lin", "bin")]:
        if os.access(os.path.join(c, "riscv64-unknown-elf-gcc"), os.X_OK):
            return c
    return ""

def write_config(workdir, force, xilinx):
    """config.sh: this machine's tool paths, read by scripts/env.sh. Kept if present (unless
    --force or --xilinx), so hand edits survive."""
    cfg = os.path.join(workdir, "config.sh")
    if os.path.exists(cfg) and not force and not xilinx:
        say("kept config.sh")
        return
    settings = find_vivado_settings(xilinx)
    riscv = find_riscv_bin(settings)
    write_text(cfg,
        "# config.sh - tool paths on this machine, read by scripts/env.sh.\n"
        "# Written by setup.litex.du-pcb.py (git-ignored). Edit if a tool moves, or re-run it with --xilinx.\n"
        'VIVADO_SETTINGS="{}"\n'
        'RISCV_BIN="{}"\n'.format(settings, riscv))
    say("wrote config.sh (Vivado: {}, RISC-V GCC: {})".format(settings or "not found", riscv or "not found"))

def python_version(python):
    out = subprocess.check_output([python, "-c", "import sys; print('%d %d' % sys.version_info[:2])"],
                                  universal_newlines=True)
    return tuple(int(x) for x in out.split())

def install_litex(workdir, python):
    """LiteX release + Python venv + LiteX ecosystem (migen, litex, litedram, litepcie, CPUs...)."""
    deps = os.path.join(workdir, "deps")
    venv = os.path.join(workdir, ".venv")
    vpy  = os.path.join(venv, "bin", "python3")
    if not shutil.which("git"):
        die("git not found (LiteX repositories are cloned with it)")
    if not os.path.exists(vpy):
        version = python_version(python)
        if version < LITEX_PYTHON:
            die("LiteX needs Python {}.{}+, {} is {}.{}: pass a newer one with --python".format(
                LITEX_PYTHON[0], LITEX_PYTHON[1], python, version[0], version[1]))
    os.makedirs(deps, exist_ok=True)
    os.makedirs(os.path.join(workdir, "build"), exist_ok=True)

    release = os.path.join(deps, "litex-" + LITEX_TAG)
    if not os.path.isdir(release):
        zip_path = os.path.join(deps, LITEX_TAG + ".zip")
        if not os.path.isfile(zip_path):
            say("downloading LiteX {} release".format(LITEX_TAG))
            with urlopen(LITEX_URL.format(LITEX_TAG)) as r, open(zip_path + ".part", "wb") as f:
                shutil.copyfileobj(r, f)
            os.replace(zip_path + ".part", zip_path)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(deps)

    if not os.path.exists(vpy):
        say("creating Python venv in .venv")
        run([python, "-m", "venv", venv])
    run([vpy, "-m", "pip", "install", "-q", "--upgrade", "pip"])
    run([vpy, "-m", "pip", "install", "-q", "meson", "ninja"])

    # litex_setup.py normally updates itself and its repo list from GitHub master first, which would
    # break the release pin. "--dev" skips that update; GITHUB_ACTIONS=true keeps https clone URLs
    # (plain --dev would switch to ssh URLs).
    say("installing LiteX {} ecosystem into deps/ (first run takes a while)".format(LITEX_TAG))
    for name in ["litex_setup.py", "litex_repos.py"]:
        shutil.copyfile(os.path.join(release, name), os.path.join(deps, name))
    env = dict(os.environ, VIRTUAL_ENV=venv, GITHUB_ACTIONS="true",
               PATH=os.path.join(venv, "bin") + os.pathsep + os.environ.get("PATH", ""))
    run([vpy, "litex_setup.py", "--dev", "--init", "--install", "--config=standard",
         "--tag=" + LITEX_TAG], cwd=deps, env=env)

def check_tools(workdir):
    """What the daily scripts will find (through scripts/env.sh)."""
    if not shutil.which("bash"):
        die("bash not found (the daily scripts need it)")
    run(["bash", "-c", """
        . "$1/scripts/env.sh"
        python3 -c "import migen, litex, litedram, litepcie" && echo "[setup] Python packages OK"
        for t in vivado riscv64-unknown-elf-gcc verilator; do
            command -v "$t" > /dev/null && echo "[setup] found $t" || echo "[setup] missing $t"
        done
        command -v verilator > /dev/null || echo "[setup]   (verilator is only needed for scripts/sim.sh)"
        true
    """, "_", workdir], cwd=workdir)   # From workdir, so no stray .py in the caller's folder interferes.

# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Unfold the DU-PCB-001-003 LiteX project into a work directory and set it up: "
                    "project files, LiteX {} (deps/), Python venv (.venv/), tool paths (config.sh).".format(LITEX_TAG),
        epilog="Needs: git, bash, internet access for the first run; Vivado for builds. "
               "After setup: cd <workdir> && scripts/build.sh --no-compile-gateware (see README.md).")
    parser.add_argument("-w", "--workdir", default=os.getcwd(),
        help="work directory (default: the current directory); created if missing")
    parser.add_argument("-f", "--force", action="store_true",
        help="overwrite project files you changed (default: keep them and say so), rewrite config.sh")
    parser.add_argument("--files-only", action="store_true",
        help="only unfold the project files and config.sh; skip LiteX and the venv")
    parser.add_argument("--xilinx", metavar="PATH",
        help="Vivado install: its settings64.sh, its Vivado folder or the folder above "
             "(default: from vivado on PATH, else " + ", ".join(XILINX_ROOTS) + ")")
    parser.add_argument("--python", default=sys.executable, metavar="PATH",
        help="Python for the venv, {}.{}+ (default: the one running this script)".format(*LITEX_PYTHON))
    parser.add_argument("--list", action="store_true", help="list the files in the bundle and exit")
    parser.add_argument("--pack", action="store_true",
        help="put the work directory's files (FILES) back into this script and exit")
    args = parser.parse_args()

    workdir = os.path.abspath(os.path.expanduser(args.workdir))
    if args.list:
        for path, _, _ in read_archive():
            print(path)
        return
    if args.pack:
        pack(workdir)
        return
    os.makedirs(workdir, exist_ok=True)
    say("work directory: " + workdir)
    unfold(workdir, args.force)
    write_config(workdir, args.force, args.xilinx)
    if not args.files_only:
        install_litex(workdir, args.python)
        check_tools(workdir)
    say('done. Next: cd "{}" && scripts/build.sh --no-compile-gateware'.format(workdir))

if __name__ == "__main__":
    main()

# ==== ARCHIVE: written by --pack, do not edit by hand ====
#@@ FILE README.md 644
#|# LiteX on the DU-PCB-001-003
#|
#|LiteX SoC for the DU-PCB-001-003 Kintex-7 480T card (`xc7k480tiffg1156-2L`), used as a PCIe accelerator.
#|The board itself is documented in `my-fpga-ws/boards/DU-PCB-001-003/README.md`; section numbers (§) below refer to it.
#|
#|## What is in the SoC
#|
#|| Block | Details |
#||---|---|
#|| PCIe | Gen2 x8, BAR0 = CSRs, 1 DMA channel, LitePCIe Linux driver generated into `build/dupcb/driver/` |
#|| CPU | VexRiscv + BIOS. Console over PCIe (`scripts/console.sh`); no UART pins on the card |
#|| DDR3 CH0 | CPU main RAM at `0x4000_0000` (CPU sees 1 GB of the 2 GB). BIST for testing |
#|| DDR3 CH1 | Second controller (2 GB) for your accelerator logic. BIST for testing |
#|| DDR3 PHY | `WL7DDRPHY`: one MMCM per channel, CK phase moved by the host. Both channels calibrated by the host: `scripts/ddr_init.sh` |
#|| Clocks | 200 MHz #0 → `sys` 125 MHz → one DDR MMCM per channel. 200 MHz #1 → `accel` domain 200 MHz. 50 MHz → `clk50` domain. Freq meters on `clk50` and `accel` |
#|| LEDs | Red/green/yellow bracket LEDs run a chaser = SoC alive. Host can take over via `leds_out` |
#|| Keep-alive | AC24 driven high **and** all unused pins pulled up (§3). Never remove this |
#|
#|## Layout
#|
#|```
#|setup.litex.du-pcb.py  the whole project in one file: unfolds everything below, installs LiteX
#|boards/dupcb/
#|  dupcb_platform.py    pins and bitstream settings
#|  target.py            the SoC
#|  wl7ddrphy.py         DDR3 PHY with host-adjustable CK phase (from openTPU)
#|  ddr_init.py          host-side DDR3 calibration (CK phase scan) + tests, both channels
#|scripts/               daily scripts
#|config.sh              tool paths on this machine (written by the setup script, git-ignored)
#|deps/  .venv/          LiteX and Python env (git-ignored, recreated by the setup script)
#|build/                 all build output (git-ignored)
#|```
#|
#|## Setup (once)
#|
#|```
#|python3 setup.litex.du-pcb.py                     # in the current directory
#|python3 setup.litex.du-pcb.py --workdir ~/dupcb   # or anywhere else
#|python3 setup.litex.du-pcb.py --help              # all options
#|```
#|Needs Python 3.6+ to run (LiteX itself needs 3.8+: `--python /path/to/python3.x` picks the one for the venv),
#|git, bash, and Vivado (found on PATH or in /tools/Xilinx, /opt/Xilinx, ~/Xilinx; else `--xilinx PATH`).
#|Standard library only. It pins everything to LiteX `2026.08` (`LITEX_TAG` at the top of the script). The RISC-V
#|GCC that comes with Vitis builds the BIOS. Safe to run again; files you changed are kept unless `--force`.
#|
#|**Changing the project:** edit the files as usual, then `python3 setup.litex.du-pcb.py --pack` copies them back
#|into the script, so the single file stays complete. A new file: add its path to `FILES` at the top of the
#|script, then `--pack`.
#|
#|## Daily use
#|
#|```
#|scripts/build.sh --no-compile-gateware   # fast check (~1 min): Verilog, XDC, BIOS, driver
#|scripts/build.sh                         # full bitstream (Vivado, ~30-60 min)
#|scripts/load.sh                          # load over JTAG (volatile)
#|scripts/pcie_rescan.sh                   # card in this PC: let Linux find it again
#|scripts/status.sh                        # ident, measured clocks, LEDs
#|scripts/ddr_init.sh                      # calibrate + test both DDR3 channels (after every load)
#|scripts/console.sh                       # BIOS console (Ctrl-C to quit)
#|scripts/sim.sh                           # SoC + firmware in Verilator (needs verilator)
#|scripts/clean.sh
#|```
#|Extra target options pass through `build.sh`, e.g. `--sys-clk-freq 100e6`, `--no-ch1`, `--no-pcie`,
#|`--uart-name jtag_uart`. See `python3 boards/dupcb/target.py --help`.
#|
#|Adding accelerator logic: in `target.py`, take a DDR CH1 port with
#|`self.sdram1.crossbar.get_port(clock_domain="accel")` and connect it to your core.
#|
#|## Things to know
#|
#|- **AC24 keep-alive (§3).** If DONE drops and the red SMD LED blinks ~250 ms after loading, something removed it.
#|- **Reloading in a running PC** drops the PCIe link. Run `scripts/pcie_rescan.sh`; if the card is still missing,
#|  warm-reboot (the FPGA keeps its design). A bench supply avoids this.
#|- **Flash boot is not supported yet:** §6.5 says there is no working way to write the flash. Load over JTAG.
#|- **DDR3 calibration.** The DDR banks are HR (no ODELAY, so no write leveling), and the chips sit on a fly-by
#|  bus, so the far chips see CK later. The stock `A7DDRPHY` can only move DQS, and on this card that leaves no
#|  write timing that works for every lane under traffic (CH0: lanes 4-7 fail; CH1: BIST ~21% bad even though
#|  every single-burst check passed). `wl7ddrphy.py` is openTPU's fix (`my-fpga-ws/submodules/openTPU`,
#|  `docs/litedram.md` sections 7-8, measured on the YPCB-00338): CK moves against DQ/DQS through the channel's
#|  MMCM, and `ddr_init.py` picks the CK phase with a BIST at every step. The BIOS still tries CH0 at boot
#|  without that scan and usually prints a memtest failure: ignore it, run `scripts/ddr_init.sh`.
#|- **ECC chips** (byte lane 8) are not used: 64-bit data per channel.
#|- **Verified on this card (2026-11-20):** keep-alive, PCIe (Gen2, x4 in this PC's slot), both 200 MHz clocks and
#|  the 50 MHz, both DDR3 channels (CH0 893 ps / CH1 1429 ps write window, 1 GB BIST clean, 7.2 GB/s).
#|  DDR3 VDDQ (1.35 or 1.5 V) is unmeasured; I/O is SSTL15 like the MIG design that calibrated on this card.
#@@ END
#@@ FILE .gitignore 644
#|# Created by setup.litex.du-pcb.py
#|.venv/
#|deps/
#|config.sh
#|# Build output
#|build/
#|*.jou
#|*.log
#|*.str
#|.Xil/
#|__pycache__/
#|*.pyc
#@@ END
#@@ FILE boards/dupcb/dupcb_platform.py 644
#|#
#|# LiteX platform for the DU-PCB-001-003 (SCH-001-003) Kintex-7 480T PCIe card.
#|#
#|# Pins come from the board README (my-fpga-ws/boards/DU-PCB-001-003, sections 12.x) and its master
#|# XDC (constraints/dupcb001003.xdc). Verified on unit 0265: LEDs, clk50, clk200 #0, DDR3 CH0.
#|# Inherited from the YPCB-00338-1P1 and not yet verified on this card: DDR3 CH1, clk200 #1, PCIe.
#|#
#|# THE ONE RULE: pin AC24 ("keepalive") must stay high after configuration, or the card clears the
#|# FPGA ~250 ms later. The target drives it to 1 and this file pulls every unused pin up as well.
#|
#|from litex.build.generic_platform import Pins, Subsignal, IOStandard, Misc
#|from litex.build.xilinx import Xilinx7SeriesPlatform, VivadoProgrammer
#|
#|
#|# DDR3 channel helper ------------------------------------------------------------------------------
#|# Both channels: 64 data bits (8 x8 chips) used; the 9th (ECC) chip is not connected here.
#|# I/O like the MIG preset that calibrated on this card: SSTL15, 50 ohm split termination, LVCMOS15 reset.
#|
#|def _ddram(n, a, ba, ras_n, cas_n, we_n, cs_n, cke, odt, reset_n, clk_p, clk_n, dq, dqs_p, dqs_n):
#|    term = Misc("IN_TERM=UNTUNED_SPLIT_50")
#|    return ("ddram", n,
#|        Subsignal("a",       Pins(a),       IOStandard("SSTL15")),
#|        Subsignal("ba",      Pins(ba),      IOStandard("SSTL15")),
#|        Subsignal("ras_n",   Pins(ras_n),   IOStandard("SSTL15")),
#|        Subsignal("cas_n",   Pins(cas_n),   IOStandard("SSTL15")),
#|        Subsignal("we_n",    Pins(we_n),    IOStandard("SSTL15")),
#|        Subsignal("cs_n",    Pins(cs_n),    IOStandard("SSTL15")),
#|        Subsignal("cke",     Pins(cke),     IOStandard("SSTL15")),
#|        Subsignal("odt",     Pins(odt),     IOStandard("SSTL15")),
#|        Subsignal("reset_n", Pins(reset_n), IOStandard("LVCMOS15")),
#|        Subsignal("clk_p",   Pins(clk_p),   IOStandard("DIFF_SSTL15")),
#|        Subsignal("clk_n",   Pins(clk_n),   IOStandard("DIFF_SSTL15")),
#|        Subsignal("dq",      Pins(dq),      IOStandard("SSTL15"),      term),
#|        Subsignal("dqs_p",   Pins(dqs_p),   IOStandard("DIFF_SSTL15"), term),
#|        Subsignal("dqs_n",   Pins(dqs_n),   IOStandard("DIFF_SSTL15"), term),
#|        Misc("SLEW=FAST"),
#|    )
#|
#|# IOs ----------------------------------------------------------------------------------------------
#|
#|_io = [
#|    # Clocks / reset.
#|    ("clk50",  0, Pins("AA28"), IOStandard("LVCMOS18")),                     # Y2, bank 14.
#|    ("clk200", 0,                                                             # Bank 12 (DDR CH0 side).
#|        Subsignal("p", Pins("AH27")),
#|        Subsignal("n", Pins("AH28")),
#|        IOStandard("DIFF_SSTL15"), Misc("DQS_BIAS=TRUE"),
#|    ),
#|    ("clk200", 1,                                                             # Bank 17 (DDR CH1 side).
#|        Subsignal("p", Pins("G25")),
#|        Subsignal("n", Pins("G26")),
#|        IOStandard("DIFF_SSTL15"), Misc("DQS_BIAS=TRUE"),
#|    ),
#|    ("cpu_reset_n", 0, Pins("R28"), IOStandard("LVCMOS18")),                  # SW2, active low.
#|
#|    # Keep-alive: must be high after configuration (see top of file).
#|    ("keepalive", 0, Pins("AC24"), IOStandard("LVCMOS18")),
#|
#|    # Bracket LEDs, active high: red, green, yellow.
#|    ("user_led", 0, Pins("P30"), IOStandard("LVCMOS18"), Misc("DRIVE=8"), Misc("SLEW=SLOW")),
#|    ("user_led", 1, Pins("M30"), IOStandard("LVCMOS18"), Misc("DRIVE=8"), Misc("SLEW=SLOW")),
#|    ("user_led", 2, Pins("N30"), IOStandard("LVCMOS18"), Misc("DRIVE=8"), Misc("SLEW=SLOW")),
#|
#|    # LM73 temperature sensor (I2C address 0x4A) and PCIe SMBus. Defined, not used by the target.
#|    ("lm73", 0,
#|        Subsignal("scl",   Pins("N24")),
#|        Subsignal("sda",   Pins("N25")),
#|        Subsignal("alert", Pins("P25")),
#|        IOStandard("LVCMOS18"),
#|    ),
#|    ("pcie_smbus", 0,
#|        Subsignal("scl", Pins("R26")),
#|        Subsignal("sda", Pins("R27")),
#|        IOStandard("LVCMOS18"),
#|    ),
#|
#|    # PCIe Gen2 x8 (GTX quads 115/116, lane 0 on GTXE2_CHANNEL_X0Y23).
#|    ("pcie_x8", 0,
#|        Subsignal("rst_n", Pins("Y26"), IOStandard("LVCMOS18"), Misc("PULLUP=TRUE")),
#|        Subsignal("clk_p", Pins("J8")),
#|        Subsignal("clk_n", Pins("J7")),
#|        Subsignal("rx_p",  Pins("H6 J4 K6 L4 M6 P6 R4 T6")),
#|        Subsignal("rx_n",  Pins("H5 J3 K5 L3 M5 P5 R3 T5")),
#|        Subsignal("tx_p",  Pins("F2 H2 K2 M2 N4 P2 T2 U4")),
#|        Subsignal("tx_n",  Pins("F1 H1 K1 M1 N3 P1 T1 U3")),
#|    ),
#|
#|    # DDR3 channel 0: chips U5-U12 (+ECC U13), banks 11/12/13.
#|    _ddram(0,
#|        a       = "AK27 AN23 AL24 AK26 AH24 AH25 AL26 AJ24 AJ25 AM23 AL28 AL25 AM25 AK24 AM27",
#|        ba      = "AM26 AP24 AN28",
#|        ras_n   = "AJ29", cas_n = "AP26", we_n = "AN27", cs_n = "AK28",
#|        cke     = "AP27", odt   = "AK29", reset_n = "AD31",
#|        clk_p   = "AN25", clk_n = "AP25",
#|        dq      = " ".join([
#|            "AG17 AG16 AH17 AJ19 AH18 AH19 AJ16 AJ17",  # Byte 0, U5.
#|            "AL20 AN17 AL19 AM16 AL18 AL16 AM20 AN18",  # Byte 1, U6.
#|            "AL23 AN20 AK23 AP19 AN22 AN19 AM22 AP20",  # Byte 2, U7.
#|            "AJ21 AH22 AK21 AG21 AG22 AG20 AH23 AG23",  # Byte 3, U8.
#|            "AJ32 AK32 AK31 AL30 AL34 AL31 AK34 AL29",  # Byte 4, U9.
#|            "AJ34 AH32 AJ30 AH34 AF31 AG30 AG31 AF30",  # Byte 5, U10.
#|            "AE32 AC33 AF33 AC32 AD34 AC34 AE33 AE31",  # Byte 6, U11.
#|            "AE26 AF29 AE24 AF28 AF24 AG25 AF26 AF25",  # Byte 7, U12.
#|        ]),
#|        dqs_p   = "AK16 AM17 AP21 AH20 AK33 AG33 AE34 AE27",
#|        dqs_n   = "AK17 AM18 AP22 AJ20 AL33 AH33 AF34 AE28",
#|    ),
#|
#|    # DDR3 channel 1: chips U1, U14-U20 (+ECC U21), banks 16/17/18.
#|    _ddram(1,
#|        a       = "E27 C27 B28 D27 C24 D24 C25 A24 A25 J24 F26 D26 H25 D25 B26",
#|        ba      = "F24 J25 E24",
#|        ras_n   = "E28", cas_n = "E26", we_n = "F25", cs_n = "F28",
#|        cke     = "A28", odt   = "B27", reset_n = "F18",
#|        clk_p   = "B25", clk_n = "A26",
#|        dq      = " ".join([
#|            "A29 B33 A31 C33 C32 A30 B30 A33",          # Byte 0, U1.
#|            "D31 F33 D30 D29 E33 E34 E31 F34",          # Byte 1, U14.
#|            "B23 A21 C23 B20 B22 A23 C20 B21",          # Byte 2, U15.
#|            "G31 G32 F29 F31 E29 G33 H33 H32",          # Byte 3, U16.
#|            "B18 C17 C19 B16 A18 A16 C18 B17",          # Byte 4, U17.
#|            "K27 L24 K24 L28 K26 M27 L25 M26",          # Byte 5, U18.
#|            "F16 E18 E16 H19 H17 H20 E17 H18",          # Byte 6, U19.
#|            "D20 F21 E23 G21 G20 D21 F20 F23",          # Byte 7, U20.
#|        ]),
#|        dqs_p   = "B31 D34 A19 H29 D16 K28 G17 G22",
#|        dqs_n   = "B32 C34 A20 H30 D17 K29 G18 G23",
#|    ),
#|]
#|
#|# Platform -----------------------------------------------------------------------------------------
#|
#|class Platform(Xilinx7SeriesPlatform):
#|    default_clk_name   = "clk200"
#|    default_clk_period = 1e9/200e6
#|
#|    def __init__(self, toolchain="vivado"):
#|        Xilinx7SeriesPlatform.__init__(self, "xc7k480tiffg1156-2L", _io, name="dupcb", toolchain=toolchain)
#|
#|        # Master XDC section 1: required on this card.
#|        self.add_platform_command("set_property BITSTREAM.CONFIG.UNUSEDPIN Pullup [current_design]")  # Keeps AC24 high too.
#|        self.add_platform_command("set_property CFGBVS GND [current_design]")
#|        self.add_platform_command("set_property CONFIG_VOLTAGE 1.8 [current_design]")
#|        # Master XDC section 2: BPI x16 flash boot settings (harmless for JTAG loading).
#|        self.add_platform_command("set_property CONFIG_MODE BPI16 [current_design]")
#|        self.add_platform_command("set_property BITSTREAM.CONFIG.BPI_SYNC_MODE Disable [current_design]")
#|        self.add_platform_command("set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]")
#|
#|    def create_programmer(self):
#|        return VivadoProgrammer()
#|
#|    def do_finalize(self, fragment):
#|        Xilinx7SeriesPlatform.do_finalize(self, fragment)
#|        self.add_period_constraint(self.lookup_request("clk50",     loose=True), 1e9/50e6)
#|        self.add_period_constraint(self.lookup_request("clk200", 0, loose=True), 1e9/200e6)
#|        self.add_period_constraint(self.lookup_request("clk200", 1, loose=True), 1e9/200e6)
#@@ END
#@@ FILE boards/dupcb/target.py 644
#|#!/usr/bin/env python3
#|#
#|# LiteX SoC for the DU-PCB-001-003 card, used as a PCIe accelerator.
#|#
#|#   PCIe Gen2 x8 -> BAR0: CSRs (LEDs, DDR, freq meters, BIOS console) + 1 DMA channel.
#|#   VexRiscv CPU + BIOS: CH0 is its main RAM (CPU sees the first 1 GB).
#|#   DDR3 CH0 + CH1: WL7DDRPHY (host-adjustable CK phase), both calibrated by the host after every
#|#             load (scripts/ddr_init.sh). CH1 is for your accelerator logic.
#|#   Clocks:   clk200 #0 -> sys (125 MHz) -> per-channel DDR MMCMs, clk200 #1 -> "accel" (200 MHz),
#|#             clk50 -> "clk50" domain. Freq meters on both let the host check every crystal.
#|#   AC24 keep-alive driven high. 3 LEDs run a chaser (host can take them over).
#|#
#|# Normally run through scripts/build.sh and scripts/load.sh.
#|
#|import os
#|import sys
#|
#|from migen import *
#|from litex.gen import *
#|from litex.build.io import DifferentialInput
#|
#|from litex.build.parser import LiteXArgumentParser
#|from litex.soc.cores.clock import S7MMCM, S7PLL, S7IDELAYCTRL
#|from litex.soc.cores.led import LedChaser
#|from litex.soc.cores.freqmeter import FreqMeter
#|from litex.soc.integration.soc_core import SoCCore
#|from litex.soc.integration.builder import Builder
#|
#|from litedram.modules import MT41K256M8          # Same geometry/timings as the SK hynix H5TC2G83 on the card.
#|from litedram.core import LiteDRAMCore
#|from litedram.frontend.bist import LiteDRAMBISTGenerator, LiteDRAMBISTChecker
#|from litedram.init import get_sdram_phy_py_header
#|
#|from litepcie.phy.s7pciephy import S7PCIEPHY
#|from litepcie.software import generate_litepcie_software
#|
#|sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
#|import dupcb_platform  # noqa: E402  (boards/dupcb/dupcb_platform.py)
#|from wl7ddrphy import DDRClocks, WL7DDRPHY  # noqa: E402
#|
#|# CRG ----------------------------------------------------------------------------------------------
#|
#|class _CRG(LiteXModule):
#|    def __init__(self, platform, sys_clk_freq, accel_clk_freq):
#|        self.rst          = Signal()
#|        self.cd_sys       = ClockDomain()
#|        self.cd_idelay    = ClockDomain()
#|        self.cd_accel     = ClockDomain()
#|        self.cd_clk50     = ClockDomain(reset_less=True)
#|
#|        rst_n = platform.request("cpu_reset_n")
#|
#|        # 200 MHz inputs go through a BUFG first: LiteX clocks the MMCM/PLL reset logic from clkin,
#|        # and on local routing that logic fails hold timing.
#|        def clk200(n):
#|            se, buffered = Signal(), Signal()
#|            pads = platform.request("clk200", n)
#|            self.specials += DifferentialInput(pads.p, pads.n, se)
#|            self.specials += Instance("BUFG", i_I=se, o_O=buffered)
#|            return buffered
#|
#|        # Main MMCM on 200 MHz #0: sys + IDELAY reference. Each DDR3 channel's PHY clocks come from
#|        # its own MMCM, cascaded from sys (wl7ddrphy.DDRClocks).
#|        self.mmcm = mmcm = S7MMCM(speedgrade=-2)
#|        self.comb += mmcm.reset.eq(~rst_n | self.rst)
#|        mmcm.register_clkin(clk200(0), 200e6)
#|        mmcm.create_clkout(self.cd_sys,    sys_clk_freq)
#|        mmcm.create_clkout(self.cd_idelay, 200e6)
#|        platform.add_false_path_constraints(self.cd_sys.clk, mmcm.clkin)
#|        self.idelayctrl = S7IDELAYCTRL(self.cd_idelay)
#|
#|        # PLL on 200 MHz #1: clock for accelerator logic.
#|        self.pll = pll = S7PLL(speedgrade=-2)
#|        self.comb += pll.reset.eq(~rst_n | self.rst)
#|        pll.register_clkin(clk200(1), 200e6)
#|        pll.create_clkout(self.cd_accel, accel_clk_freq)
#|        platform.add_false_path_constraints(self.cd_sys.clk, pll.clkin)
#|
#|        # 50 MHz crystal, used as is.
#|        self.comb += self.cd_clk50.clk.eq(platform.request("clk50"))
#|
#|        platform.add_false_path_constraints(self.cd_sys.clk, self.cd_accel.clk, self.cd_clk50.clk)
#|
#|# SoC ----------------------------------------------------------------------------------------------
#|
#|class BaseSoC(SoCCore):
#|    def __init__(self, sys_clk_freq=125e6, accel_clk_freq=200e6, with_ch1=True, with_pcie=True, **kwargs):
#|        platform = dupcb_platform.Platform()
#|        sys_clk_freq = int(sys_clk_freq)
#|
#|        # The card has no UART pins: the BIOS console goes over PCIe (crossover) by default.
#|        if kwargs.get("uart_name", "serial") == "serial":
#|            kwargs["uart_name"] = "crossover"
#|
#|        self.crg = _CRG(platform, sys_clk_freq, accel_clk_freq)
#|        SoCCore.__init__(self, platform, sys_clk_freq, ident="LiteX SoC on DU-PCB-001-003", **kwargs)
#|
#|        # Keep-alive: AC24 high, always (otherwise the card clears the FPGA). -----------------------
#|        self.comb += platform.request("keepalive").eq(1)
#|
#|        # LEDs -------------------------------------------------------------------------------------
#|        self.leds = LedChaser(platform.request_all("user_led"), sys_clk_freq)
#|
#|        # Clock checks: read clk50_freq / accel_freq over PCIe, value is in Hz. --------------------
#|        self.clk50_freq = FreqMeter(period=sys_clk_freq, clk=ClockSignal("clk50"))
#|        self.accel_freq = FreqMeter(period=sys_clk_freq, clk=ClockSignal("accel"))
#|
#|        # DDR3 -------------------------------------------------------------------------------------
#|        # Both channels: WL7DDRPHY (boards/dupcb/wl7ddrphy.py), A7DDRPHY with a host-adjustable CK
#|        # phase. The stock PHY has no write timing that works for all lanes on these HR banks.
#|        # The host calibrates both channels after every load (scripts/ddr_init.sh): CK phase scan
#|        # with BIST, write latency and read leveling per lane. The BIOS still tries CH0 at boot,
#|        # without the phase scan, and will usually report a memtest failure; ignore it.
#|        self.ddr_module = module = MT41K256M8(sys_clk_freq, "1:4")
#|        if not self.integrated_main_ram_size:
#|            self.ddrphy = self.add_ddr_phy(platform, 0, sys_clk_freq)
#|            self.add_sdram("sdram",
#|                phy           = self.ddrphy,
#|                module        = module,
#|                size          = 0x4000_0000,      # CPU window: 1 GB of the 2 GB channel.
#|                l2_cache_size = 8192,
#|                with_bist     = True)             # sdram_generator/checker: traffic test.
#|
#|        # DDR3 CH1: second controller for accelerator logic. ---------------------------------------
#|        if with_ch1:
#|            self.ddrphy1 = self.add_ddr_phy(platform, 1, sys_clk_freq)
#|            self.sdram1 = LiteDRAMCore(
#|                phy             = self.ddrphy1,
#|                geom_settings   = module.geom_settings,
#|                timing_settings = module.timing_settings,
#|                clk_freq        = sys_clk_freq)
#|            # BIST (pattern generator + checker), used by ddr_init.py to test the whole channel.
#|            self.sdram1_generator = LiteDRAMBISTGenerator(self.sdram1.crossbar.get_port())
#|            self.sdram1_checker   = LiteDRAMBISTChecker(self.sdram1.crossbar.get_port())
#|            # Your accelerator: take a native port (2 GB, 512-bit at sys_clk) like this:
#|            #   self.my_accel = MyAccel(self.sdram1.crossbar.get_port(clock_domain="accel"))
#|
#|        # PCIe Gen2 x8 -----------------------------------------------------------------------------
#|        if with_pcie:
#|            self.pcie_phy = S7PCIEPHY(platform, platform.request("pcie_x8"),
#|                data_width = 128,
#|                bar0_size  = 0x20000)
#|            self.pcie_phy.update_config({"PCIe_Blk_Locn": "X0Y0"})
#|            self.add_pcie(phy=self.pcie_phy, ndmas=1)
#|            # Lane 0 is on X0Y23 and lane 7 on X0Y16 (README 12.4): pin the GTs explicitly.
#|            self.pcie_phy.add_gt_loc_constraints(
#|                locs    = [f"GTXE2_CHANNEL_X0Y{n}" for n in range(23, 15, -1)],
#|                gt_type = "gtx")
#|
#|    # Channel n's PHY clocks (own MMCM, in the channel's banks' clock regions as in openTPU) + PHY.
#|    MMCM_LOCS = {0: "MMCME2_ADV_X0Y2", 1: "MMCME2_ADV_X0Y6"}   # CH0 banks 11-13, CH1 banks 16-18.
#|
#|    def add_ddr_phy(self, platform, n, sys_clk_freq):
#|        esc = lambda c: c.replace("{", "{{").replace("}", "}}")   # LiteX runs .format() on these.
#|        clocks = DDRClocks(n, sys_clk_freq)
#|        setattr(self, "ddrclk" if n == 0 else f"ddrclk{n}", clocks)
#|        phy = ClockDomainsRenamer(clocks.domains)(
#|            WL7DDRPHY(platform.request("ddram", n), sys_clk_freq=sys_clk_freq))
#|        platform.toolchain.pre_placement_commands += [esc(c) for c in clocks.constraints()]
#|        platform.add_platform_command(f"set_property LOC {self.MMCM_LOCS[n]} [get_cells {clocks.name_of}]")
#|        if not getattr(self, "_wl7_constraints", False):
#|            for c in WL7DDRPHY.constraints():
#|                platform.add_platform_command(esc(c))
#|            self._wl7_constraints = True
#|        return phy
#|
#|# Build --------------------------------------------------------------------------------------------
#|
#|def main():
#|    parser = LiteXArgumentParser(platform=dupcb_platform.Platform, description="LiteX SoC on DU-PCB-001-003.")
#|    parser.add_target_argument("--sys-clk-freq",   default=125e6, type=float, help="System clock frequency.")
#|    parser.add_target_argument("--accel-clk-freq", default=200e6, type=float, help="Accelerator clock frequency.")
#|    parser.add_target_argument("--no-ch1",         action="store_true",       help="Leave DDR3 channel 1 out.")
#|    parser.add_target_argument("--no-pcie",        action="store_true",       help="Leave PCIe out.")
#|    parser.add_target_argument("--driver",         action="store_true",       help="Generate the LitePCIe Linux driver.")
#|    args = parser.parse_args()
#|
#|    soc = BaseSoC(
#|        sys_clk_freq   = args.sys_clk_freq,
#|        accel_clk_freq = args.accel_clk_freq,
#|        with_ch1       = not args.no_ch1,
#|        with_pcie      = not args.no_pcie,
#|        **parser.soc_argdict)
#|
#|    builder_args = parser.builder_argdict
#|    builder = Builder(soc, **builder_args)
#|    if builder_args.get("csr_csv") is None:
#|        builder.csr_csv = os.path.join(builder.output_dir, "csr.csv")  # Host tools read register addresses here.
#|
#|    if args.build:
#|        builder.build(**parser.toolchain_argdict)
#|
#|        # Init data for ddr_init.py (host-side calibration). Both channels use the same PHY settings.
#|        phy = getattr(soc, "ddrphy1", None) or getattr(soc, "ddrphy", None)
#|        if phy is not None:
#|            with open(os.path.join(builder.output_dir, "sdram_init.py"), "w") as f:
#|                f.write(get_sdram_phy_py_header(phy.settings, soc.ddr_module.timing_settings))
#|
#|    if args.driver and not args.no_pcie:
#|        generate_litepcie_software(soc, os.path.join(builder.output_dir, "driver"))
#|
#|    if args.load:
#|        soc.platform.create_programmer().load_bitstream(builder.get_bitstream_filename(mode="sram"))
#|
#|if __name__ == "__main__":
#|    main()
#@@ END
#@@ FILE boards/dupcb/wl7ddrphy.py 644
#|#
#|# wl7ddrphy.py - DDR3 PHY with host-adjustable CK phase, for the HR banks of the DU-PCB-001-003.
#|#
#|# Adapted from openTPU's tools/litedram/wl7ddrphy.py (Apache-2.0; my-fpga-ws/submodules/openTPU,
#|# docs/litedram.md sections 7-8), itself derived from LiteDRAM's A7DDRPHY (BSD-2-Clause:
#|# Copyright (c) 2015-2020 Florent Kermarrec, (c) 2015 Sebastien Bourdeauducq, (c) 2021 Antmicro).
#|# Changes here: one write clock group per channel (openTPU dropped its second group after it failed
#|# on the card), no rd_reg option, write_latency_calibration off in the settings (the host does it).
#|#
#|# Why: HR banks have no ODELAY, so there is no write leveling. The stock A7DDRPHY can only move DQS,
#|# which shifts it against CK *and* against its own DQ. On these cards that leaves no write timing
#|# that works for every byte lane under traffic (measured by openTPU, and by us: CH1 BIST ~21% bad).
#|#
#|# What this PHY does instead: each channel gets its own MMCM (DDRClocks). CK and the commands run on
#|# two outputs with fine phase shift (1/56 VCO period per step, 17.9 ps at 125 MHz sys), which the
#|# host moves. DQ, DQS (DQ + 90 deg) and the read capture stay on static outputs. So the host moves
#|# CK against the DQ/DQS pair, which is what write leveling does, and each lane still picks its own
#|# write latency (bitslip). scripts/ddr_init.sh scans the phase with a BIST at every step and picks
#|# the centre of the range where every lane passes.
#|#
#|# Clock domains (renamed per channel with ClockDomainsRenamer(DDRClocks.domains)):
#|#   sys_ck, sys4x_ck      CLKDIV / CLK of CK and the commands   (fine phase shift, host-controlled)
#|#   sys_w                 CLKDIV of every DQ/DQS OSERDES and ISERDES (static, in phase with sys)
#|#   sys4x_w, sys4x_w_dqs  CLK of DQ (and the read ISERDES) / of DQS at +90 deg (static)
#|# The PHY logic itself runs in sys. Commands cross sys -> sys_ck through registers on sys's falling
#|# edge; the host keeps sys_ck within half a tCK of sys (ddr_init.py wraps the phase), so they keep
#|# about 3 ns of setup and hold.
#|
#|from functools import reduce
#|from operator import or_
#|import math
#|
#|from migen import *
#|
#|from litex.gen import LiteXModule
#|from litex.soc.interconnect.csr import CSR, CSRStatus, CSRStorage, AutoCSR
#|
#|from litedram.common import *
#|from litedram.phy.dfi import *
#|
#|# Per-channel clocks -------------------------------------------------------------------------------
#|
#|class DDRClocks(LiteXModule):
#|    """One channel's PHY clocks from one MMCM, cascaded from sys (DIVCLK 1, x8 VCO, feedback through
#|    a BUFG) so its outputs keep a fixed phase to sys. CSRs: reset/locked, and the CK phase:
#|    each write to ck_shift moves CK one fine step later (1) or earlier (0) once ck_busy is 0;
#|    ck_steps counts the steps since the MMCM came out of reset."""
#|    def __init__(self, n, sys_clk_freq):
#|        self.name_of = f"ddr{n}_mmcm"
#|        self.domains = {
#|            "sys_ck":      f"ddr{n}_ck",
#|            "sys4x_ck":    f"ddr{n}_ck4x",
#|            "sys_w":       f"ddr{n}_w",
#|            "sys4x_w":     f"ddr{n}_w4x",
#|            "sys4x_w_dqs": f"ddr{n}_w4x_dqs",
#|        }
#|        # (output, divide, static phase, fine phase shift) per PHY clock.
#|        outs = {
#|            "sys_ck":      (0, 8,  0.0, True),
#|            "sys4x_ck":    (1, 2,  0.0, True),
#|            "sys_w":       (2, 8,  0.0, False),
#|            "sys4x_w":     (3, 2,  0.0, False),
#|            "sys4x_w_dqs": (4, 2, 90.0, False),
#|        }
#|        self.vco_freq = 8*sys_clk_freq
#|        self.steps_per_tck = round(56*self.vco_freq/(4*sys_clk_freq))   # 112
#|
#|        self.reset    = CSRStorage(1, description="1: hold this channel's MMCM in reset.")
#|        self.locked   = CSRStatus(1)
#|        self.ck_shift = CSRStorage(1, description="Write: move CK one step; 1 = later, 0 = earlier.")
#|        self.ck_busy  = CSRStatus(1)
#|        self.ck_steps = CSRStatus(32, description="CK phase in fine steps since reset (signed).")
#|
#|        # # #
#|
#|        params = {}
#|        for name, (i, div, phase, fine) in outs.items():
#|            cd = ClockDomain(self.domains[name], reset_less=True)
#|            setattr(self, "cd_" + cd.name, cd)
#|            o = Signal()
#|            params[f"p_CLKOUT{i}_DIVIDE" + ("_F" if i == 0 else "")] = float(div) if i == 0 else div
#|            params[f"p_CLKOUT{i}_PHASE"]       = phase
#|            params[f"p_CLKOUT{i}_DUTY_CYCLE"]  = 0.5
#|            params[f"p_CLKOUT{i}_USE_FINE_PS"] = "TRUE" if fine else "FALSE"
#|            params[f"o_CLKOUT{i}"]             = o
#|            self.specials += Instance("BUFG", i_I=o, o_O=cd.clk)
#|
#|        locked, rst = Signal(), Signal()
#|        psen, psincdec, psdone = Signal(), Signal(), Signal()
#|        fb, fb_buf = Signal(), Signal()
#|        self.comb += rst.eq(ResetSignal("sys") | self.reset.storage)
#|        self.specials += Instance("MMCME2_ADV", name=self.name_of,
#|            p_BANDWIDTH="OPTIMIZED", p_COMPENSATION="ZHOLD", p_STARTUP_WAIT="FALSE",
#|            p_CLKIN1_PERIOD=1e9/sys_clk_freq, p_REF_JITTER1=0.01, p_DIVCLK_DIVIDE=1,
#|            p_CLKFBOUT_MULT_F=8.0, p_CLKFBOUT_PHASE=0.0, p_CLKFBOUT_USE_FINE_PS="FALSE",
#|            i_CLKIN1=ClockSignal("sys"), i_CLKIN2=0, i_CLKINSEL=1,
#|            i_CLKFBIN=fb_buf, o_CLKFBOUT=fb, i_RST=rst, i_PWRDWN=0, o_LOCKED=locked,
#|            i_PSCLK=ClockSignal("sys"), i_PSEN=psen, i_PSINCDEC=psincdec, o_PSDONE=psdone,
#|            i_DCLK=0, i_DEN=0, i_DWE=0, i_DADDR=0, i_DI=0,
#|            **params)
#|        self.specials += Instance("BUFG", i_I=fb, o_O=fb_buf)
#|
#|        # Phase-shift control: one step per ck_shift write, counted while the MMCM is running.
#|        busy  = Signal()
#|        steps = Signal((32, True))
#|        self.sync += [
#|            psen.eq(0),
#|            If(self.ck_shift.re & ~busy,
#|                psen.eq(1), psincdec.eq(self.ck_shift.storage[0]), busy.eq(1),
#|                If(self.ck_shift.storage[0], steps.eq(steps + 1)).Else(steps.eq(steps - 1)),
#|            ).Elif(psdone, busy.eq(0)),
#|            If(~locked | self.reset.storage, busy.eq(0), steps.eq(0)),
#|        ]
#|        self.comb += [
#|            self.locked.status.eq(locked),
#|            self.ck_busy.status.eq(busy),
#|            self.ck_steps.status.eq(steps),
#|        ]
#|
#|    def constraints(self, ns=1.0):
#|        """Tcl (before placement): commands cross between sys (falling edge) and the shifted
#|        sys_ck, which the host keeps within half a tCK of sys: `ns` of uncertainty both ways."""
#|        pin = lambda p: f"[get_pins {self.name_of}/{p}]"
#|        sys_, ck = (f"[get_clocks -of_objects {pin(p)}]" for p in ("CLKIN1", "CLKOUT0"))
#|        return [f"set_clock_uncertainty -{k} {ns:.3f} -from {a} -to {b}"
#|                for a, b in ((sys_, ck), (ck, sys_)) for k in ("setup", "hold")]
#|
#|# PHY ----------------------------------------------------------------------------------------------
#|
#|class WL7DDRPHY(Module, AutoCSR):
#|    """A7DDRPHY (DDR3, 1:4, no ODELAY) on the DDRClocks domains. CSRs and settings are A7DDRPHY's
#|    (phytype A7DDRPHY), plus dly_sel_bits: which DQ bits of the lanes in dly_sel the read/write
#|    bitslip strobes act on (reset 0xFF). Some bits' ISERDES frame the word one CLK off the rest
#|    of their lane (openTPU: always a few on CH1, different pins per build); the host gives those
#|    bits their own read bitslip."""
#|    def __init__(self, pads, sys_clk_freq, iodelay_clk_freq=200e6, cl=None, cwl=None):
#|        memtype, nphases = "DDR3", 4
#|        pads        = PHYPadsCombiner(pads)
#|        tck         = 2/(2*nphases*sys_clk_freq)
#|        addressbits = len(pads.a)
#|        bankbits    = len(pads.ba)
#|        nranks      = 1 if not hasattr(pads, "cs_n") else len(pads.cs_n)
#|        databits    = len(pads.dq)
#|        strobes     = len(pads.dqs_p)
#|        assert databits == 8*strobes
#|
#|        # Parameters (A7DDRPHY's) ------------------------------------------------------------------
#|        half_sys8x_taps = math.floor(tck/(4*{200e6: 78e-12, 300e6: 52e-12}[iodelay_clk_freq]))
#|        cl  = get_default_cl(memtype, tck)  if cl  is None else cl
#|        cwl = get_default_cwl(memtype, tck) if cwl is None else cwl
#|        cl_sys_latency  = get_sys_latency(nphases, cl)
#|        cwl_sys_latency = get_sys_latency(nphases, cwl)
#|        rdphase = get_sys_phase(nphases, cl_sys_latency, cl)
#|        wrphase = get_sys_phase(nphases, cwl_sys_latency, cwl)
#|        # No ODELAY: read data one memory-clock phase into the ISERDESE2 word (as A7DDRPHY).
#|        phase_cycles, rdphase = divmod(rdphase + 1, nphases)
#|        cl_sys_latency -= phase_cycles
#|
#|        # Registers (A7DDRPHY's + dly_sel_bits) ----------------------------------------------------
#|        self._rst                 = CSRStorage()
#|        self._dly_sel             = CSRStorage(strobes)
#|        self._dly_sel_bits        = CSRStorage(8, reset=0xFF)
#|        self._half_sys8x_taps     = CSRStorage(5, reset=half_sys8x_taps)
#|        self._wlevel_en           = CSRStorage()
#|        self._wlevel_strobe       = CSR()
#|        self._rdly_dq_rst         = CSR()
#|        self._rdly_dq_inc         = CSR()
#|        self._rdly_dq_bitslip_rst = CSR()
#|        self._rdly_dq_bitslip     = CSR()
#|        self._wdly_dq_bitslip_rst = CSR()
#|        self._wdly_dq_bitslip     = CSR()
#|        self._rdphase             = CSRStorage(int(math.log2(nphases)), reset=rdphase)
#|        self._wrphase             = CSRStorage(int(math.log2(nphases)), reset=wrphase)
#|
#|        rdly_dq_rst         = self._rdly_dq_rst.wr_stb
#|        rdly_dq_inc         = self._rdly_dq_inc.wr_stb
#|        rdly_dq_bitslip_rst = self._rdly_dq_bitslip_rst.wr_stb
#|        rdly_dq_bitslip     = self._rdly_dq_bitslip.wr_stb
#|        wdly_dq_bitslip_rst = self._wdly_dq_bitslip_rst.wr_stb
#|        wdly_dq_bitslip     = self._wdly_dq_bitslip.wr_stb
#|        bit_sel  = self._dly_sel_bits.storage
#|        lane_all = Signal()
#|        self.comb += lane_all.eq(bit_sel == 0xFF)
#|
#|        self.settings = PhySettings(
#|            phytype                   = "A7DDRPHY",
#|            memtype                   = memtype,
#|            databits                  = databits,
#|            strobes                   = strobes,
#|            dfi_databits              = 2*databits,
#|            nranks                    = nranks,
#|            nphases                   = nphases,
#|            rdphase                   = self._rdphase.storage,
#|            wrphase                   = self._wrphase.storage,
#|            cl                        = cl,
#|            cwl                       = cwl,
#|            read_latency              = cl_sys_latency + 6,
#|            write_latency             = cwl_sys_latency - 1,
#|            cmd_latency               = 0,
#|            cmd_delay                 = None,
#|            write_leveling            = False,
#|            write_dq_dqs_training     = False,
#|            write_latency_calibration = False,  # Host does it (the 2026.08 BIOS can't compile it here).
#|            read_leveling             = True,
#|            delays                    = 32,
#|            bitslips                  = 8,
#|            with_dm                   = hasattr(pads, "dm"),
#|        )
#|
#|        self.dfi = dfi = Interface(addressbits, bankbits, nranks, 2*databits, nphases)
#|
#|        # # #
#|
#|        def oserdes(d, clk, clkdiv, rst, o, t1=None, tq=None):
#|            kw = dict(i_TCE=1, i_T1=t1, o_TQ=tq) if t1 is not None else {}
#|            return Instance("OSERDESE2",
#|                p_SERDES_MODE="MASTER", p_DATA_WIDTH=2*nphases, p_TRISTATE_WIDTH=1,
#|                p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
#|                i_RST=rst, i_CLK=clk, i_CLKDIV=clkdiv,
#|                **{f"i_D{n + 1}": d[n] for n in range(8)},
#|                i_OCE=1, o_OQ=o, **kw)
#|
#|        def nreg(x):
#|            """x through FDREs on sys's falling edge (clock inverted in the slice, no LUT in the
#|            clock path), on its way to the shifted sys_ck."""
#|            r = Signal(len(x))
#|            for i in range(len(x)):
#|                self.specials += Instance("FDRE", p_INIT=0, p_IS_C_INVERTED=1,
#|                    i_C=ClockSignal("sys"), i_CE=1, i_R=0, i_D=x[i], o_Q=r[i])
#|            return r
#|
#|        def serdes_rst(x, clk):
#|            """x registered again in the serializers' CLKDIV domain, close to its SERDES, so all
#|            SERDES of a word leave reset on the same edge (constraints() bounds the route)."""
#|            r = Signal()
#|            self.specials += Instance("FDRE", name="wlrst", p_INIT=1, i_C=ClockSignal(clk),
#|                i_CE=1, i_R=0, i_D=x, o_Q=r, attr={("DONT_TOUCH", "TRUE")})
#|            return r
#|
#|        sys_rst = Signal(reset=1, reset_less=True)
#|        self.sync += sys_rst.eq(ResetSignal("sys") | self._rst.storage)
#|        ck_rst_n = nreg(sys_rst)
#|        ck_rsts  = []
#|
#|        def ck_rst():  # One reset register per 8 command/clock pads.
#|            if len(ck_rsts) % 8 == 0:
#|                ck_rsts.append(serdes_rst(ck_rst_n, "sys_ck"))
#|            else:
#|                ck_rsts.append(ck_rsts[-1])
#|            return ck_rsts[-1]
#|
#|        # Clock ------------------------------------------------------------------------------------
#|        for i in range(len(pads.clk_p)):
#|            clk_o = Signal()
#|            self.specials += oserdes([(0b10101010 >> n) & 1 for n in range(8)],
#|                ClockSignal("sys4x_ck"), ClockSignal("sys_ck"), ck_rst(), clk_o)
#|            self.specials += Instance("OBUFDS", i_I=clk_o, o_O=pads.clk_p[i], o_OB=pads.clk_n[i])
#|
#|        # Commands ---------------------------------------------------------------------------------
#|        pads_ba  = Signal(bankbits)
#|        commands = {"reset_n": "reset_n", "cs_n": "cs_n", "a": "address", pads_ba: "bank",
#|                    "ras_n": "ras_n", "cas_n": "cas_n", "we_n": "we_n", "cke": "cke", "odt": "odt"}
#|        for pad_name, dfi_name in commands.items():
#|            pad = pad_name if isinstance(pad_name, Signal) else getattr(pads, pad_name, None)
#|            if pad is None:
#|                assert pad_name in ("reset_n", "cs_n", "cke", "odt"), pad_name
#|                continue
#|            for i in range(len(pad)):
#|                # reset_n sits in another bank: its own reset register.
#|                own = dfi_name == "reset_n"
#|                self.specials += oserdes(
#|                    nreg(Cat(*[getattr(dfi.phases[n//2], dfi_name)[i] for n in range(8)])),
#|                    ClockSignal("sys4x_ck"), ClockSignal("sys_ck"),
#|                    serdes_rst(ck_rst_n, "sys_ck") if own else ck_rst(), pad[i])
#|        self.comb += pads.ba.eq(pads_ba)
#|
#|        # DQS --------------------------------------------------------------------------------------
#|        dqs_oe        = Signal()
#|        dqs_preamble  = Signal()
#|        dqs_postamble = Signal()
#|        dqs_oe_delay  = TappedDelayLine(ntaps=2)
#|        dqs_pattern   = DQSPattern(wlevel_en=self._wlevel_en.storage,
#|            wlevel_strobe=self._wlevel_strobe.wr_stb, register=True)
#|        self.submodules += dqs_oe_delay, dqs_pattern
#|        self.comb += dqs_oe_delay.input.eq(dqs_preamble | dqs_oe | dqs_postamble)
#|        for i in range(strobes):
#|            dqs_o = Signal()
#|            dqs_t = Signal()
#|            dqs_bitslip = BitSlip(8, i=dqs_pattern.o,
#|                rst = (self._dly_sel.storage[i] & lane_all & wdly_dq_bitslip_rst) | self._rst.storage,
#|                slp = self._dly_sel.storage[i] & lane_all & wdly_dq_bitslip, cycles=1)
#|            self.submodules += dqs_bitslip
#|            self.specials += oserdes(dqs_bitslip.o, ClockSignal("sys4x_w_dqs"),
#|                ClockSignal("sys_w"), serdes_rst(sys_rst, "sys_w"), dqs_o,
#|                t1=~dqs_oe_delay.output, tq=dqs_t)
#|            self.specials += Instance("IOBUFDS", i_T=dqs_t, i_I=dqs_o,
#|                io_IO=pads.dqs_p[i], io_IOB=pads.dqs_n[i])
#|
#|        # DM ---------------------------------------------------------------------------------------
#|        if hasattr(pads, "dm"):
#|            for i in range(databits//8):
#|                dm_i = Cat(*[dfi.phases[n//2].wrdata_mask[n%2*databits//8 + i] for n in range(8)])
#|                dm_o_bitslip = BitSlip(8, i=dm_i,
#|                    rst = (self._dly_sel.storage[i] & lane_all & wdly_dq_bitslip_rst) | self._rst.storage,
#|                    slp = self._dly_sel.storage[i] & lane_all & wdly_dq_bitslip, cycles=1)
#|                self.submodules += dm_o_bitslip
#|                self.specials += oserdes(dm_o_bitslip.o, ClockSignal("sys4x_w"),
#|                    ClockSignal("sys_w"), serdes_rst(sys_rst, "sys_w"), pads.dm[i])
#|
#|        # DQ ---------------------------------------------------------------------------------------
#|        dq_oe       = Signal()
#|        dq_oe_delay = TappedDelayLine(ntaps=2)
#|        self.submodules += dq_oe_delay
#|        self.comb += dq_oe_delay.input.eq(dqs_preamble | dq_oe | dqs_postamble)
#|        for i in range(databits):
#|            lane = i//8
#|            dq_o         = Signal()
#|            dq_i         = Signal()
#|            dq_i_delayed = Signal()
#|            dq_t         = Signal()
#|            dq_o_bitslip = BitSlip(8,
#|                i   = Cat(*[dfi.phases[n//2].wrdata[n%2*databits + i] for n in range(8)]),
#|                rst = (self._dly_sel.storage[lane] & bit_sel[i%8] & wdly_dq_bitslip_rst) | self._rst.storage,
#|                slp = self._dly_sel.storage[lane] & bit_sel[i%8] & wdly_dq_bitslip, cycles=1)
#|            self.submodules += dq_o_bitslip
#|            dq_rst = serdes_rst(sys_rst, "sys_w")  # The pad's OSERDES and ISERDES.
#|            self.specials += oserdes(dq_o_bitslip.o, ClockSignal("sys4x_w"),
#|                ClockSignal("sys_w"), dq_rst, dq_o, t1=~dq_oe_delay.output, tq=dq_t)
#|            dq_q = Signal(8)
#|            dq_i_bitslip = BitSlip(8, i=dq_q,
#|                rst = (self._dly_sel.storage[lane] & bit_sel[i%8] & rdly_dq_bitslip_rst) | self._rst.storage,
#|                slp = self._dly_sel.storage[lane] & bit_sel[i%8] & rdly_dq_bitslip, cycles=1)
#|            self.submodules += dq_i_bitslip
#|            self.specials += Instance("ISERDESE2",
#|                p_SERDES_MODE="MASTER", p_INTERFACE_TYPE="NETWORKING", p_DATA_WIDTH=2*nphases,
#|                p_DATA_RATE="DDR", p_NUM_CE=1, p_IOBDELAY="IFD",
#|                i_RST=dq_rst, i_CLK=ClockSignal("sys4x_w"), i_CLKB=~ClockSignal("sys4x_w"),
#|                i_CLKDIV=ClockSignal("sys_w"), i_BITSLIP=0, i_CE1=1, i_DDLY=dq_i_delayed,
#|                **{f"o_Q{n + 1}": dq_q[8 - 1 - n] for n in range(8)})
#|            for n in range(8):
#|                self.comb += dfi.phases[n//2].rddata[n%2*databits + i].eq(dq_i_bitslip.o[n])
#|            self.specials += Instance("IDELAYE2",
#|                p_SIGNAL_PATTERN="DATA", p_DELAY_SRC="IDATAIN", p_CINVCTRL_SEL="FALSE",
#|                p_HIGH_PERFORMANCE_MODE="TRUE", p_REFCLK_FREQUENCY=iodelay_clk_freq/1e6,
#|                p_PIPE_SEL="FALSE", p_IDELAY_TYPE="VARIABLE", p_IDELAY_VALUE=0,
#|                i_C=ClockSignal("sys"),
#|                i_LD=(self._dly_sel.storage[lane] & rdly_dq_rst) | self._rst.storage,
#|                i_LDPIPEEN=0, i_CE=self._dly_sel.storage[lane] & rdly_dq_inc, i_INC=1,
#|                i_IDATAIN=dq_i, o_DATAOUT=dq_i_delayed)
#|            self.specials += Instance("IOBUF", i_I=dq_o, o_O=dq_i, i_T=dq_t, io_IO=pads.dq[i])
#|
#|        # Read control path (A7DDRPHY's) -----------------------------------------------------------
#|        rddata_en = TappedDelayLine(
#|            signal = reduce(or_, [dfi.phases[i].rddata_en for i in range(nphases)]),
#|            ntaps  = self.settings.read_latency)
#|        self.submodules += rddata_en
#|        self.comb += [phase.rddata_valid.eq(rddata_en.output | self._wlevel_en.storage)
#|            for phase in dfi.phases]
#|
#|        # Write control path (A7DDRPHY's) ----------------------------------------------------------
#|        wrtap = cwl_sys_latency - 1
#|        wrdata_en = TappedDelayLine(
#|            signal = reduce(or_, [dfi.phases[i].wrdata_en for i in range(nphases)]),
#|            ntaps  = wrtap + 2)
#|        self.submodules += wrdata_en
#|        self.comb += dq_oe.eq(wrdata_en.taps[wrtap])
#|        self.comb += If(self._wlevel_en.storage, dqs_oe.eq(1)).Else(dqs_oe.eq(dq_oe))
#|        self.comb += dqs_preamble.eq(wrdata_en.taps[wrtap - 1] & ~wrdata_en.taps[wrtap + 0])
#|        self.comb += dqs_postamble.eq(wrdata_en.taps[wrtap + 1] & ~wrdata_en.taps[wrtap + 0])
#|
#|    @staticmethod
#|    def constraints(ns=3.0):
#|        """XDC: every SERDES reset register (serdes_rst) reaches its SERDES' RST within `ns`."""
#|        src = "[get_cells -hierarchical -filter {NAME =~ *wlrst*}]"
#|        dst = ("[get_pins -of_objects [get_cells -hierarchical -filter "
#|               "{REF_NAME == OSERDESE2 || REF_NAME == ISERDESE2}] -filter {REF_PIN_NAME == RST}]")
#|        return [f"set_max_delay {ns:.3f} -from {src} -to {dst}"]
#@@ END
#@@ FILE boards/dupcb/ddr_init.py 644
#|#!/usr/bin/env python3
#|#
#|# ddr_init.py - calibrate the DDR3 channels from the host over PCIe, then test them.
#|#
#|# Run after every bitstream load (scripts/ddr_init.sh). Talks to BAR0 directly (mmap), no server.
#|# Per channel (WL7DDRPHY, boards/dupcb/wl7ddrphy.py):
#|#   1. CK phase scan: the channel's MMCM moves CK against DQ/DQS in 1/56-VCO steps (17.9 ps).
#|#      At every --stride step over one tCK: DRAM init, calibration (below), then a 64 MB BIST.
#|#      A step passes if every lane calibrates and the BIST has no errors.
#|#   2. CK goes to the centre of the longest run of passing steps; calibrate again there.
#|#   3. Check 200 random addresses (errors per lane), then BIST: write once, read back twice.
#|# Calibration at one phase: for write bitslip 0/2/4/6 (whole tCK) x read bitslip x read delay,
#|# write/read random bursts at random addresses, all lanes at once, errors counted per DQ bit.
#|# Per lane keep the widest read window; a DQ bit may read 2 bitslips off its lane (its ISERDES
#|# frames the word one clock off) and then gets its own read bitslip.
#|# The single-burst check alone is not enough (it passes where streaming traffic fails), which is
#|# why every phase step is checked with the BIST. Method and card data: openTPU docs/litedram.md.
#|
#|import argparse
#|import os
#|import random
#|import sys
#|import time
#|
#|from litex.tools.remote.comm_pcie import CommPCIe
#|
#|MODULES   = 8               # Byte lanes (x8 chips) used per channel.
#|DATABITS  = 64
#|NPHASES   = 4
#|DELAYS    = 32              # IDELAYE2 taps (78 ps each with a 200 MHz reference).
#|BITSLIPS  = 8
#|WBITSLIPS = (0, 2, 4, 6)    # Write latency in whole tCK; CK phase covers the rest.
#|STEPS     = 112             # CK fine-phase steps per tCK (56 per VCO period, VCO = 2 x DDR clock).
#|BANKS, ROWS, COLS = 8, 1 << 15, 1 << 10   # MT41K256M8 / H5TC2G83 geometry.
#|
#|# BAR0 access --------------------------------------------------------------------------------------
#|
#|class Bar(CommPCIe):
#|    """BAR0 mapped into this process. csr.csv addresses start at the CSR base; on the bus at 0."""
#|    def __init__(self, bar, csr_csv):
#|        CommPCIe.__init__(self, bar, csr_csv=csr_csv)
#|        self.offset = self.mems.csr.base
#|
#|    def read(self, addr, length=None, burst="incr"):
#|        return CommPCIe.read(self, addr - self.offset, length, burst)
#|
#|    def write(self, addr, data):
#|        CommPCIe.write(self, addr - self.offset, data)
#|
#|# One channel --------------------------------------------------------------------------------------
#|
#|class Channel:
#|    def __init__(self, bus, n, init_file):
#|        self.n     = n
#|        self.r     = bus.regs
#|        self.sys_clk_freq = bus.constants.config_clock_frequency
#|        sfx        = "" if n == 0 else str(n)
#|        self.dfii  = f"sdram{sfx}_dfii_"
#|        self.phyn  = f"ddrphy{sfx}_"
#|        self.clkn  = f"ddrclk{sfx}_"
#|        self.bistn = f"sdram{sfx}_"
#|        ns = {}
#|        with open(init_file) as f:
#|            src = f.read()
#|        exec(src, ns)
#|        self.c = ns  # dfii_* constants + init_sequence.
#|        # Entries that set the DFII control register (reset/CKE) instead of issuing a command.
#|        lines = [l for l in src.splitlines() if l.strip().startswith('("')]
#|        self.is_control = ["dfii_control" in l for l in lines]
#|        self.rdphase = self.reg_phy("rdphase").read()
#|        self.wrphase = self.reg_phy("wrphase").read()
#|        self.seed    = 1
#|
#|    def reg(self, name):     return getattr(self.r, self.dfii + name)
#|    def reg_phy(self, name): return getattr(self.r, self.phyn + name)
#|    def reg_clk(self, name): return getattr(self.r, self.clkn + name)
#|
#|    # DFII ---------------------------------------------------------------------------------------
#|    def command(self, phase, cmd, address=0, baddress=0):
#|        self.reg(f"pi{phase}_address").write(address)
#|        self.reg(f"pi{phase}_baddress").write(baddress)
#|        self.reg(f"pi{phase}_command").write(cmd)
#|        self.reg(f"pi{phase}_command_issue").write(1)
#|
#|    def hardware_control(self):
#|        self.reg("control").write(self.c["dfii_control_sel"])
#|
#|    def init_dram(self):
#|        """PHY reset (clears all delays/bitslips), then the JEDEC init sequence."""
#|        c = self.c
#|        self.reg("control").write(c["dfii_control_cke"] | c["dfii_control_odt"] | c["dfii_control_reset_n"])
#|        self.reg_phy("dly_sel_bits").write(0xFF)
#|        self.reg_phy("rst").write(1); time.sleep(0.001)
#|        self.reg_phy("rst").write(0); time.sleep(0.001)
#|        for (comment, a, ba, cmd, delay), control in zip(c["init_sequence"], self.is_control):
#|            if control:
#|                self.reg("control").write(cmd)
#|            else:
#|                self.command(0, cmd, a, ba)
#|            time.sleep(0.001 if delay else 0)
#|
#|    def test_bits(self, count=1):
#|        """Write random bursts to random addresses and read them back; wrong reads per DQ bit."""
#|        c   = self.c
#|        err = [0]*DATABITS
#|        for _ in range(count):
#|            rng  = random.Random(self.seed); self.seed += 1
#|            bank = rng.randrange(BANKS)
#|            row  = rng.randrange(ROWS)
#|            col  = rng.randrange(COLS) & ~7          # Burst of 8 starts on an 8-column boundary.
#|            data = [rng.getrandbits(2*DATABITS) for _ in range(NPHASES)]
#|            self.command(0, c["dfii_command_ras"] | c["dfii_command_cs"], row, bank)        # Activate.
#|            for p in range(NPHASES):
#|                self.reg(f"pi{p}_wrdata").write(data[p])
#|            self.command(self.wrphase, c["dfii_command_cas"] | c["dfii_command_we"] |
#|                         c["dfii_command_cs"] | c["dfii_command_wrdata"], col, bank)        # Write.
#|            self.command(self.rdphase, c["dfii_command_cas"] | c["dfii_command_cs"] |
#|                         c["dfii_command_rddata"], col, bank)                               # Read.
#|            self.command(0, c["dfii_command_ras"] | c["dfii_command_we"] | c["dfii_command_cs"],
#|                         1 << 10)                                                           # Precharge all.
#|            for p in range(NPHASES):
#|                x = data[p] ^ self.reg(f"pi{p}_rddata").read()
#|                while x:
#|                    low = x & -x
#|                    err[(low.bit_length() - 1) % DATABITS] += 1
#|                    x ^= low
#|        return err
#|
#|    def lane_errors(self, count):
#|        e = self.test_bits(count)
#|        return [sum(e[8*m:8*m + 8]) for m in range(MODULES)]
#|
#|    # PHY delay/bitslip controls; `lanes` is a bit mask of byte lanes. -----------------------------
#|    def strobe(self, lanes, action, count=1):
#|        self.reg_phy("dly_sel").write(lanes)
#|        for _ in range(count):
#|            self.reg_phy(action).write(1)
#|        self.reg_phy("dly_sel").write(0)
#|
#|    def set_lane(self, m, wbitslip, rbitslip, delay, bit_offsets):
#|        self.strobe(1 << m, "wdly_dq_bitslip_rst"); self.strobe(1 << m, "wdly_dq_bitslip", wbitslip)
#|        self.strobe(1 << m, "rdly_dq_bitslip_rst"); self.strobe(1 << m, "rdly_dq_bitslip", rbitslip)
#|        self.strobe(1 << m, "rdly_dq_rst");         self.strobe(1 << m, "rdly_dq_inc",     delay)
#|        for i, o in enumerate(bit_offsets):         # Bits framed one clock off their lane.
#|            if o:
#|                self.reg_phy("dly_sel_bits").write(1 << i)
#|                self.strobe(1 << m, "rdly_dq_bitslip_rst")
#|                self.strobe(1 << m, "rdly_dq_bitslip", rbitslip + o)
#|                self.reg_phy("dly_sel_bits").write(0xFF)
#|
#|    # CK phase -------------------------------------------------------------------------------------
#|    def ck_steps(self):
#|        v = self.reg_clk("ck_steps").read()
#|        return v - (1 << 32) if v & (1 << 31) else v
#|
#|    def ck_move(self, target):
#|        """Move CK to `target` steps. Kept within half a tCK of sys (the PHY's command crossing
#|        needs that); a target a whole tCK away is the same phase against the DRAM."""
#|        if not self.reg_clk("locked").read():
#|            raise RuntimeError(f"CH{self.n}: DDR clock MMCM not locked")
#|        target = (target + STEPS//2) % STEPS - STEPS//2
#|        t0 = time.time()
#|        while (s := self.ck_steps()) != target:
#|            while self.reg_clk("ck_busy").read():
#|                if time.time() - t0 > 5:
#|                    raise TimeoutError(f"CH{self.n}: CK phase stuck at {s}")
#|            self.reg_clk("ck_shift").write(1 if target > s else 0)
#|
#|    # BIST -----------------------------------------------------------------------------------------
#|    def bist_run(self, unit, size):
#|        """BIST generator (write) or checker (read) over [0, size): (bad 64-byte words, seconds)."""
#|        u = lambda name: getattr(self.r, f"{self.bistn}{unit}_{name}")
#|        u("reset").write(1)
#|        u("base").write(0)
#|        u("end").write(size)
#|        u("length").write(size)
#|        u("random").write(1)  # Random data (same sequence in generator and checker), linear addresses.
#|        u("start").write(1)
#|        t0 = time.time()
#|        while not u("done").read():
#|            if time.time() - t0 > 30:
#|                raise TimeoutError(f"CH{self.n}: BIST {unit} did not finish")
#|        seconds = u("ticks").read()/self.sys_clk_freq
#|        return (u("errors").read() if unit == "checker" else 0), seconds
#|
#|    def bist(self, size):
#|        self.bist_run("generator", size)
#|        return self.bist_run("checker", size)[0]
#|
#|# Calibration at the current CK phase --------------------------------------------------------------
#|
#|def windows(ok):
#|    """Longest run of True: (start, length)."""
#|    best, start = (0, 0), None
#|    for i, good in enumerate(list(ok) + [False]):
#|        if good and start is None:
#|            start = i
#|        if not good and start is not None:
#|            if i - start > best[1]:
#|                best = (start, i - start)
#|            start = None
#|    return best
#|
#|def lane_best(scan, m):
#|    """Best read setting for lane m in scan[rbitslip][tap][bit] = errors.
#|    Returns (window, rbitslip, start, per-bit offsets). Every bit of a lane uses the lane's tap;
#|    a bit may read at the lane's bitslip +-2 (one clock off). Widest window wins; between equals,
#|    the one with the fewest bits off."""
#|    best = (0, 0, 0, [0]*8)
#|    for b in range(BITSLIPS):
#|        ok = {(i, o): [0 <= b + o < BITSLIPS and scan[b + o][t][8*m + i] == 0 for t in range(DELAYS)]
#|              for i in range(8) for o in (0, 2, -2)}
#|        start, n = windows([all(any(ok[i, o][t] for o in (0, 2, -2)) for i in range(8))
#|                            for t in range(DELAYS)])
#|        if n < best[0]:
#|            continue
#|        offs = [max((0, 2, -2), key=lambda o: sum(ok[i, o][start:start + n])) for i in range(8)]
#|        start, n = windows([all(ok[i, offs[i]][t] for i in range(8)) for t in range(DELAYS)])
#|        if (n, -sum(map(bool, offs))) > (best[0], -sum(map(bool, best[3]))):
#|            best = (n, b, start, offs)
#|    return best
#|
#|def calibrate(ch, verbose=False):
#|    """Init the DRAM, find and set each lane's write bitslip, read bitslip, read delay (and per-bit
#|    offsets). Returns the read window per lane (0 = lane failed)."""
#|    ch.init_dram()
#|    all_lanes = (1 << MODULES) - 1
#|    best = [(0, None)]*MODULES   # Per lane: (window, (wbitslip, rbitslip, delay, offsets)).
#|    for wbs in WBITSLIPS:
#|        ch.strobe(all_lanes, "wdly_dq_bitslip_rst"); ch.strobe(all_lanes, "wdly_dq_bitslip", wbs)
#|        ch.strobe(all_lanes, "rdly_dq_bitslip_rst")
#|        scan = []
#|        for rbs in range(BITSLIPS):
#|            ch.strobe(all_lanes, "rdly_dq_rst")
#|            row = []
#|            for t in range(DELAYS):
#|                row.append(ch.test_bits())
#|                ch.strobe(all_lanes, "rdly_dq_inc")
#|            scan.append(row)
#|            ch.strobe(all_lanes, "rdly_dq_bitslip")
#|        for m in range(MODULES):
#|            n, b, start, offs = lane_best(scan, m)
#|            if n > best[m][0]:
#|                best[m] = (n, (wbs, b, start + n//2, offs))
#|    for m, (n, setting) in enumerate(best):
#|        if setting is not None:
#|            ch.set_lane(m, *setting)
#|        if verbose:
#|            if setting is None:
#|                print(f"  lane {m}: NO working setting")
#|            else:
#|                wbs, b, d, offs = setting
#|                print(f"  lane {m}: write bitslip {wbs}, read bitslip {b}, delay {d:2d} "
#|                      f"(window {n}/{DELAYS} taps)" + (f", bit offsets {offs}" if any(offs) else ""))
#|    return [n for n, _ in best]
#|
#|# Per channel --------------------------------------------------------------------------------------
#|
#|def ck_scan(ch, stride, mib):
#|    """Pass/fail per CK phase step over one tCK. Returns {step: passed}."""
#|    start, table = ch.ck_steps(), {}
#|    size = mib << 20
#|    line = ""
#|    for k in range(0, STEPS, stride):
#|        ch.ck_move(start + k)
#|        win = calibrate(ch)
#|        ok  = min(win) >= 3 and not any(ch.lane_errors(4))
#|        if ok:
#|            ch.hardware_control()
#|            ok = ch.bist(size) == 0
#|        table[k] = ok
#|        line += "#" if ok else "."
#|    print(f"  CK phase scan, {stride*1e12/(8*ch.sys_clk_freq)/56:.0f} ps per char, # = all lanes pass:")
#|    print(f"  |{line}|")
#|    ch.ck_move(start)
#|    return table
#|
#|def pick(table):
#|    """Centre of the longest run of passing steps, around the circle (the scan covers one tCK)."""
#|    ks  = sorted(table)
#|    seq = ks + ks
#|    best, cur = [], []
#|    for k in seq:
#|        if table[k]:
#|            cur.append(k)
#|            if len(best) < len(cur) <= len(ks):
#|                best = list(cur)
#|        else:
#|            cur = []
#|    return (best[len(best)//2], len(best)) if best else (None, 0)
#|
#|def run_channel(ch, args):
#|    name = f"DDR3 CH{ch.n}"
#|    print(f"{name}: CK phase scan (stride {args.stride})")
#|    t0    = time.time()
#|    table = ck_scan(ch, args.stride, args.scan_mib)
#|    k, n  = pick(table)
#|    step_ps = 1e12/(8*ch.sys_clk_freq)/56
#|    if k is None:
#|        print(f"{name}: no CK phase where every lane passes. FAIL")
#|        return False
#|    print(f"  window {n*args.stride} steps ({n*args.stride*step_ps:.0f} ps), CK at +{k} "
#|          f"({time.time() - t0:.0f} s)")
#|    ch.ck_move(ch.ck_steps() + k)
#|    print(f"{name}: calibration at CK step {ch.ck_steps()}")
#|    ok = min(calibrate(ch, verbose=True)) > 0
#|    bits  = [0]*MODULES
#|    fails = [0]*MODULES
#|    for _ in range(args.check):
#|        for m, e in enumerate(ch.lane_errors(1)):
#|            bits[m] += e; fails[m] += e > 0
#|    print(f"{name}: check, {args.check} random addresses, per lane:")
#|    print("    failed tests: " + " ".join(f"{f:5d}" for f in fails))
#|    print("    bit errors:   " + " ".join(f"{b:5d}" for b in bits))
#|    ok &= sum(bits) == 0
#|    ch.hardware_control()
#|    size  = args.bist_size
#|    words = size//64
#|    _, tw  = ch.bist_run("generator", size)
#|    e1, t1 = ch.bist_run("checker",   size)
#|    e2, _  = ch.bist_run("checker",   size)
#|    print(f"{name}: BIST {size >> 20} MB, bad 64-byte words: read 1 {e1}, read 2 {e2} of {words}"
#|          f" (write {size/tw/1e9:.2f} GB/s, read {size/t1/1e9:.2f} GB/s)")
#|    ok &= e1 == 0 and e2 == 0
#|    print(f"{name}: {'PASS' if ok else 'FAIL'}")
#|    return ok
#|
#|# Main ---------------------------------------------------------------------------------------------
#|
#|def main():
#|    parser = argparse.ArgumentParser(description="Calibrate and test the DDR3 channels over PCIe.")
#|    parser.add_argument("--bar",       required=True, help="BAR0 file: /sys/bus/pci/devices/<bdf>/resource0.")
#|    parser.add_argument("--channel",   default="all", choices=["all", "0", "1"], help="Channel(s) (default all).")
#|    parser.add_argument("--build-dir", default="build/dupcb", help="Build directory (csr.csv, sdram_init.py).")
#|    parser.add_argument("--stride",    default=2, type=int, help="CK phase scan step, fine steps (default 2).")
#|    parser.add_argument("--scan-mib",  default=64, type=int, help="BIST size per scan step, MB (default 64).")
#|    parser.add_argument("--check",     default=200, type=int, help="Random addresses for the final check.")
#|    parser.add_argument("--bist-size", default=0x4000_0000, type=lambda x: int(x, 0), help="Final BIST size, bytes (default 1 GB).")
#|    args = parser.parse_args()
#|
#|    bus = Bar(args.bar, os.path.join(args.build_dir, "csr.csv"))
#|    bus.open()
#|    try:
#|        chans = [0, 1] if args.channel == "all" else [int(args.channel)]
#|        chans = [n for n in chans if hasattr(bus.regs, ("ddrphy_" if n == 0 else f"ddrphy{n}_") + "rst")]
#|        init  = os.path.join(args.build_dir, "sdram_init.py")
#|        results = {n: run_channel(Channel(bus, n, init), args) for n in chans}
#|    finally:
#|        bus.close()
#|    print("Result: " + ", ".join(f"CH{n} {'PASS' if ok else 'FAIL'}" for n, ok in results.items()))
#|    sys.exit(0 if all(results.values()) else 1)
#|
#|if __name__ == "__main__":
#|    main()
#@@ END
#@@ FILE scripts/env.sh 755
#|# env.sh - sourced by the other scripts: Python venv, Vivado, RISC-V GCC, paths and helpers.
#|# Tool locations come from config.sh (written by setup.litex.du-pcb.py; edit it if a tool moves).
#|if [ -n "${ZSH_VERSION:-}" ]; then _env_self="$(eval 'echo "${(%):-%x}"')"; else _env_self="${BASH_SOURCE[0]}"; fi
#|ROOT="$(cd "$(dirname "$_env_self")/.." && pwd)"
#|[ -f "$ROOT/config.sh" ] && . "$ROOT/config.sh"
#|. "$ROOT/.venv/bin/activate"
#|if ! command -v vivado > /dev/null 2>&1 && [ -f "${VIVADO_SETTINGS:-}" ]; then
#|    _flags=$-; set +u                     # Xilinx settings scripts use unset variables.
#|    . "$VIVADO_SETTINGS"
#|    case $_flags in *u*) set -u ;; esac
#|fi
#|if ! command -v riscv64-unknown-elf-gcc > /dev/null 2>&1 && [ -d "${RISCV_BIN:-}" ]; then
#|    export PATH="$RISCV_BIN:$PATH"        # Any riscv64-unknown-elf-gcc builds the LiteX BIOS.
#|fi
#|TARGET="$ROOT/boards/dupcb/target.py"
#|BUILD="$ROOT/build/dupcb"
#|# PCI address of the card (empty if not enumerated). LitePCIe uses Xilinx vendor ID 10ee.
#|pcie_bdf() { lspci -D -d 10ee: | head -n1 | cut -d' ' -f1; }
#|# Path of the card's BAR0 file, after making sure Linux has the device enabled (needs sudo).
#|pcie_bar() {
#|    local bdf dev
#|    bdf="$(pcie_bdf)"
#|    [[ -n "$bdf" ]] || { echo "Card not on the PCIe bus (try scripts/pcie_rescan.sh)." >&2; return 1; }
#|    dev="/sys/bus/pci/devices/$bdf"
#|    sudo -v   # The LiteX tools run "sudo chmod" on the BAR file.
#|    # Linux leaves a driverless device disabled; only root may enable it.
#|    [[ "$(cat "$dev/enable")" != 0 ]] || echo 1 | sudo tee "$dev/enable" > /dev/null
#|    echo "$dev/resource0"
#|}
#|# Start litex_server on BAR0 in the background (stopped when the script exits).
#|# litex_term and litex_cli then talk to it on localhost:1234.
#|start_server() {
#|    local bar pid
#|    bar="$(pcie_bar)" || exit 1
#|    mkdir -p "$BUILD"
#|    litex_server --pcie --pcie-bar "$bar" > "$BUILD/litex_server.log" 2>&1 &
#|    pid=$!
#|    trap "kill $pid 2> /dev/null" EXIT
#|    # Wait until it listens on port 1234; if it dies, show why.
#|    for _ in $(seq 50); do
#|        kill -0 $pid 2> /dev/null || { echo "litex_server failed:"; cat "$BUILD/litex_server.log"; exit 1; }
#|        ss -ltn "sport = :1234" | grep -q LISTEN && return
#|        sleep 0.1
#|    done
#|    echo "litex_server did not start, see $BUILD/litex_server.log"; exit 1
#|}
#@@ END
#@@ FILE scripts/build.sh 755
#|#!/usr/bin/env bash
#|# build.sh - generate the SoC, BIOS, kernel driver and bitstream into build/dupcb/.
#|#   scripts/build.sh                         full build (Vivado, ~30-60 min)
#|#   scripts/build.sh --no-compile-gateware   fast check: Verilog + XDC + BIOS only
#|set -euo pipefail
#|source "$(dirname "$0")/env.sh"
#|python3 "$TARGET" --output-dir "$BUILD" --build --driver "$@"
#@@ END
#@@ FILE scripts/load.sh 755
#|#!/usr/bin/env bash
#|# load.sh - load build/dupcb/gateware/dupcb.bit over JTAG (volatile, lost at power-off).
#|# If the card sits in a running PC, run scripts/pcie_rescan.sh afterwards.
#|set -euo pipefail
#|source "$(dirname "$0")/env.sh"
#|cd "$BUILD"   # Vivado writes its .jou/.log files here, not where you called this from.
#|python3 "$TARGET" --output-dir "$BUILD" --load "$@"
#|echo "Loaded. If the card is in this PC: scripts/pcie_rescan.sh"
#@@ END
#@@ FILE scripts/pcie_rescan.sh 755
#|#!/usr/bin/env bash
#|# pcie_rescan.sh - make Linux see the card again after a JTAG reload (needs sudo).
#|# If the card still does not show up, reboot the PC (warm reboot keeps the FPGA loaded).
#|set -euo pipefail
#|source "$(dirname "$0")/env.sh"
#|bdf="$(pcie_bdf)"
#|[[ -n "$bdf" ]] && echo 1 | sudo tee "/sys/bus/pci/devices/$bdf/remove" > /dev/null
#|echo 1 | sudo tee /sys/bus/pci/rescan > /dev/null
#|sleep 1
#|sudo lspci -vv -d 10ee: | grep -E "^[0-9a-f]|Region 0|LnkCap:|LnkSta:" || echo "Card not found on the PCIe bus."
#|# LiteX design: Region 0 size=128K. LnkSta shows the link we got (Gen2 = 5GT/s, width x8 or less).
#@@ END
#@@ FILE scripts/console.sh 755
#|#!/usr/bin/env bash
#|# console.sh - BIOS console over PCIe (no kernel driver needed). Ctrl-C to quit.
#|set -euo pipefail
#|source "$(dirname "$0")/env.sh"
#|start_server
#|litex_term crossover --csr-csv "$BUILD/csr.csv"
#@@ END
#@@ FILE scripts/ddr_init.sh 755
#|#!/usr/bin/env bash
#|# ddr_init.sh - calibrate both DDR3 channels from the host and test them (~1-2 min).
#|# Run after every bitstream load. Options: --channel 0|1, --stride N, --bist-size BYTES (see -h).
#|set -euo pipefail
#|source "$(dirname "$0")/env.sh"
#|bar="$(pcie_bar)"
#|python3 "$ROOT/boards/dupcb/ddr_init.py" --bar "$bar" --build-dir "$BUILD" "$@"
#@@ END
#@@ FILE scripts/status.sh 755
#|#!/usr/bin/env bash
#|# status.sh - quick health check over PCIe: SoC ident, measured clocks (Hz), LED register.
#|set -euo pipefail
#|source "$(dirname "$0")/env.sh"
#|start_server
#|cd "$BUILD"
#|litex_cli --ident
#|litex_cli --regs --filter freq    # Expect ~50000000 (clk50) and ~200000000 (accel, from clk200 #1).
#|litex_cli --regs --filter leds
#@@ END
#@@ FILE scripts/sim.sh 755
#|#!/usr/bin/env bash
#|# sim.sh - simulate a LiteX SoC (VexRiscv + BIOS + DDR3 model) in Verilator.
#|# Use it to test firmware and your own SoC logic. The board PHYs (DDR, PCIe) are Xilinx
#|# primitives and cannot run in Verilator; for those, test on the card.
#|# Needs: verilator, json-c and libevent from your distribution (Arch: sudo pacman -S verilator json-c libevent).
#|set -euo pipefail
#|source "$(dirname "$0")/env.sh"
#|command -v verilator > /dev/null || { echo "verilator not found: install verilator, json-c and libevent"; exit 1; }
#|litex_sim --output-dir "$ROOT/build/sim" --cpu-type vexriscv \
#|    --with-sdram --sdram-module MT41K256M8 --sdram-data-width 64 "$@"
#@@ END
#@@ FILE scripts/clean.sh 755
#|#!/usr/bin/env bash
#|# clean.sh - delete all build output.
#|rm -rf "$(dirname "$0")/../build"
#@@ END
