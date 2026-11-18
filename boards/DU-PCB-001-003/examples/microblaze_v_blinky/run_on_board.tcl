# run_on_board.tcl - load the blinker over JTAG and watch the LEDs through the debug module.
# Usage:  xsdb run_on_board.tcl <design_1_wrapper.bit> <blinky.elf> [seconds]
#   The bitstream is in the .xsa / Vitis platform (platform/export/platform/hw/sdt/*.bit).
#   Prints every change of the LED GPIO register (0x4000_0000), so the result is visible
#   without looking at the card. A pass ends in the running light 001 010 100 010 ...
#   A failure flashes 111/000 N times (N = failed test). See the board README section 4.3, "What the LEDs mean".
lassign $argv bit elf secs
if {$elf eq ""} { puts "usage: xsdb run_on_board.tcl <bit> <elf> \[seconds\]"; exit 1 }
if {$secs eq ""} { set secs 60 }
connect
targets -set -filter {name =~ "xc7k480t*"}
fpga -file $bit
for {set i 0} {$i < 30} {incr i} {
  after 500
  if {[llength [targets -filter {name =~ "*Hart*"}]]} break
}
targets -set -filter {name =~ "*Hart*"}
rst -processor
dow $elf
con
set prev ""; set t0 [clock milliseconds]
while {[clock milliseconds] - $t0 < $secs * 1000} {
  set v [expr {[lindex [mrd -value 0x40000000] 0] & 7}]
  if {$v ne $prev} { puts [format "LED t=%6dms %03b" [expr {[clock milliseconds]-$t0}] $v]; set prev $v }
  after 50
}
puts "keep-alive GPIO (0x4001_0000) = [format %x [mrd -value 0x40010000]]  (must be 1)"
