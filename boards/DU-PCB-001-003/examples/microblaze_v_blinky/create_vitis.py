# create_vitis.py - create the Vitis 2026.1 platform and application for the MicroBlaze-V
# blinker (board README section 4, "Example: MicroBlaze-V blinker"), from the .xsa that
# create_project.tcl -build writes.
#
# Usage:
#   vitis -s create_vitis.py <path/to/design_1_wrapper.xsa> [workspace_dir]
#
#   workspace_dir defaults to ./blinky_vitis. It is created and must not already contain
#   components named "platform" or "blinky". The result:
#     <ws>/platform/export/platform/platform.xpfm      standalone, microblaze_riscv_0
#     <ws>/blinky/build/blinky.elf                     the firmware (runs from local BRAM)
#   Then open <ws> in the Vitis IDE and press Run, or load the bitstream and the ELF with xsdb.
#
# The calls are the ones the Vitis IDE itself recorded in its workspace journal when the
# original project was created, plus importing blinky.c and the BRAM-only linker script.

import os
import sys
import vitis

here = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if not a.endswith(".py")]
if not args:
    sys.exit("usage: vitis -s create_vitis.py <design_1_wrapper.xsa> [workspace_dir]")
xsa = os.path.abspath(args[0])
ws = os.path.abspath(args[1] if len(args) > 1 else "blinky_vitis")
if not os.path.isfile(xsa):
    sys.exit(f"no such .xsa: {xsa}")
os.makedirs(ws, exist_ok=True)

domain = "standalone_microblaze_riscv_0"

client = vitis.create_client()
client.set_workspace(path=ws)

# ---- platform: standalone BSP on the MicroBlaze-V ---------------------------------------
platform = client.create_platform_component(
    name="platform", hw_design=xsa, os="standalone",
    cpu="microblaze_riscv_0", domain_name=domain, compiler="gcc")
# The card has no UART: keep stdin/stdout unset (the default for this hardware, set here so
# it stays that way if the hardware gains a UART later).
dom = platform.get_domain(name=domain)
dom.set_config(option="os", param="standalone_stdin", value="None")
dom.set_config(option="os", param="standalone_stdout", value="None")
platform.build()

xpfm = os.path.join(ws, "platform", "export", "platform", "platform.xpfm")

# ---- application: empty template + blinky.c + BRAM-only linker script --------------------
app = client.create_app_component(name="blinky", platform=xpfm, domain=domain,
                                  template="empty_application")
app.import_files(from_loc=here, files=["blinky.c", "lscript.ld"], dest_dir_in_cmp="src")
app.build()

elf = os.path.join(ws, "blinky", "build", "blinky.elf")
print(f"VITIS_PLATFORM {xpfm}")
print(f"VITIS_ELF {elf} exists={os.path.isfile(elf)}")
vitis.dispose()
