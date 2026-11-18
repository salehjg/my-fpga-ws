# Build the flash reader: vivado -mode batch -source build.tcl  (run inside this folder)
source bd.tcl
add_files -norecurse top.v
add_files -fileset constrs_1 -norecurse [list pins.xdc ../../constraints/dupcb001003.xdc]
set_property top top [current_fileset]
update_compile_order -fileset sources_1
launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1
puts "IMPL_STATUS [get_property STATUS [get_runs impl_1]]"
open_run impl_1
puts "WNS [get_property SLACK [get_timing_paths]]"
puts "BIT [glob -nocomplain ./frd/frd.runs/impl_1/*.bit] LTX [glob -nocomplain ./frd/frd.runs/impl_1/*.ltx]"
