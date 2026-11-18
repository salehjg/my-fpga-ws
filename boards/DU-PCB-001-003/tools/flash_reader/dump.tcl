# Dump 64 MB of BPI flash through jtag_axi -> axi_emc (base 0x60000000), 1 KB per AXI burst.
open_hw_manager
connect_hw_server -url localhost:3121
open_hw_target
set d [lindex [get_hw_devices xc7k*] 0]
current_hw_device $d
set_property PROBES.FILE ./frd/frd.runs/impl_1/top.ltx $d
refresh_hw_device $d
if {[get_property REGISTER.CONFIG_STATUS.BIT14_DONE_PIN $d] != 1} {
  set_property PROGRAM.FILE ./frd/frd.runs/impl_1/top.bit $d
  program_hw_devices $d; after 1000; refresh_hw_device $d
}
set axi [lindex [get_hw_axis] 0]
reset_hw_axi $axi
set total [expr {64*1024*1024}]
set chunk 1024
set batch 64
set f [open raw_hex.txt w]
set t0 [clock milliseconds]
for {set off 0} {$off < $total} {incr off [expr {$chunk*$batch}]} {
  set txns {}
  for {set k 0} {$k < $batch} {incr k} {
    set a [expr {0x60000000 + $off + $k*$chunk}]
    lappend txns [create_hw_axi_txn -force r$k $axi -type read -address [format %08x $a] -len 256 -size 32]
  }
  run_hw_axi -quiet $txns
  for {set k 0} {$k < $batch} {incr k} {
    puts $f "[format %08x [expr {$off + $k*$chunk}]] [get_property DATA [lindex $txns $k]]"
  }
  if {($off % (1024*1024)) == 0} {
    set el [expr {([clock milliseconds]-$t0)/1000.0}]
    puts "PROGRESS [expr {$off/1048576}] MB  elapsed ${el}s"; flush stdout
  }
}
close $f
puts "DUMP_COMPLETE [expr {([clock milliseconds]-$t0)/1000.0}]s"
boot_hw_device $d
close_hw_manager
