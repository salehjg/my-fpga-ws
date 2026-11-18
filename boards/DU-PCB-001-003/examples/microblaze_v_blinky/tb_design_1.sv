// tb_design_1.sv - full-system RTL testbench for design_1 (MicroBlaze-V + GPIO + MIG DDR3)
//
// - Drives the 50 MHz and 200 MHz (differential) board clocks and resetn.
// - Attaches 9 x Micron DDR3 x8 models (MT41K256M8, 2 Gb) = 72-bit rank,
//   using the model that MIG generated for this exact memory configuration.
// - Watches the 3 LEDs, prints every change, and decodes the firmware's
//   result (PASS / FAIL in test N / stuck), then ends the simulation.
//
// Firmware: associate peripheral_tests_sim.elf (built with -DSIM_BUILD by
// peripheral_tests/build_sim_elf.sh) with microblaze_riscv_0 under
// "Simulation Sources". The normal ELF works too but takes ~1000x longer.

`timescale 1ps / 1ps

module tb_design_1;

  // ------------------------------------------------------------------ clocks
  localparam real CLK50_HALF_PS  = 10000.0;   // 50 MHz
  localparam real CLK200_HALF_PS = 2500.0;    // 200 MHz
  localparam time TIMEOUT        = 64'd3_000_000_000; // 3 ms of simulated time

  reg clk50  = 1'b0;
  reg clk200 = 1'b0;
  reg resetn = 1'b0;

  always #(CLK50_HALF_PS)  clk50  = ~clk50;
  always #(CLK200_HALF_PS) clk200 = ~clk200;

  initial begin
    resetn = 1'b0;
    #(200_000);          // 200 ns
    resetn = 1'b1;
  end

  // -------------------------------------------------------------- DDR3 bus
  wire [14:0] ddr3_addr;
  wire [2:0]  ddr3_ba;
  wire        ddr3_cas_n, ddr3_ras_n, ddr3_we_n, ddr3_reset_n;
  wire [0:0]  ddr3_ck_n, ddr3_ck_p, ddr3_cke, ddr3_cs_n, ddr3_odt;
  wire [71:0] ddr3_dq;
  wire [8:0]  ddr3_dqs_n, ddr3_dqs_p;
  wire [8:0]  ddr3_dm = 9'b0;   // design has no data-mask pins

  wire [2:0]  led;

  // --------------------------------------------------------------- the DUT
  design_1_wrapper dut (
    .ddr3_sdram_ch0_addr    (ddr3_addr),
    .ddr3_sdram_ch0_ba      (ddr3_ba),
    .ddr3_sdram_ch0_cas_n   (ddr3_cas_n),
    .ddr3_sdram_ch0_ck_n    (ddr3_ck_n),
    .ddr3_sdram_ch0_ck_p    (ddr3_ck_p),
    .ddr3_sdram_ch0_cke     (ddr3_cke),
    .ddr3_sdram_ch0_cs_n    (ddr3_cs_n),
    .ddr3_sdram_ch0_dq      (ddr3_dq),
    .ddr3_sdram_ch0_dqs_n   (ddr3_dqs_n),
    .ddr3_sdram_ch0_dqs_p   (ddr3_dqs_p),
    .ddr3_sdram_ch0_odt     (ddr3_odt),
    .ddr3_sdram_ch0_ras_n   (ddr3_ras_n),
    .ddr3_sdram_ch0_reset_n (ddr3_reset_n),
    .ddr3_sdram_ch0_we_n    (ddr3_we_n),
    .default_50mhz_clk0     (clk50),
    .led_3bits_tri_o        (led),
    .resetn                 (resetn),
    .sys_diff_clock_clk_n   (~clk200),
    .sys_diff_clock_clk_p   (clk200)
  );

  // ------------------------------------------------- 9 x8 DDR3 chips (1 rank)
  genvar i;
  generate
    for (i = 0; i < 9; i = i + 1) begin : gen_ddr3
      ddr3_model u_ddr3 (
        .rst_n   (ddr3_reset_n),
        .ck      (ddr3_ck_p[0]),
        .ck_n    (ddr3_ck_n[0]),
        .cke     (ddr3_cke[0]),
        .cs_n    (ddr3_cs_n[0]),
        .ras_n   (ddr3_ras_n),
        .cas_n   (ddr3_cas_n),
        .we_n    (ddr3_we_n),
        .dm_tdqs (ddr3_dm[i]),
        .ba      (ddr3_ba),
        .addr    (ddr3_addr),
        .dq      (ddr3_dq[8*i +: 8]),
        .dqs     (ddr3_dqs_p[i]),
        .dqs_n   (ddr3_dqs_n[i]),
        .tdqs_n  (),
        .odt     (ddr3_odt[0])
      );
    end
  endgenerate

  // ------------------------------------------------ MIG calibration status
  // init_calib_complete is not routed anywhere in the block design, so we
  // peek at it hierarchically. Add it to the waveform window too.
  wire calib_done = dut.design_1_i.mig_7series_0.init_calib_complete;

  initial begin
    wait (calib_done === 1'b1);
    $display("[%0t ns] MIG calibration complete", $time / 1000);
  end

  // ---------------------------------------------- decode the LED sequence
  // Lamp test: 001 010 100 111 000
  // Tests:     001 010 011 (stage = test number)
  // PASS:      running light (100 appears after stage 3)
  // FAIL:      all LEDs flash (111) during the tests
  reg       seen_all_on = 1'b0;
  reg       lamp_done   = 1'b0;
  reg [2:0] stage       = 3'd0;

  always @(led) begin
    $display("[%0t ns] LED = %b", $time / 1000, led);

    if (!lamp_done) begin
      if (led == 3'b111) seen_all_on = 1'b1;
      if (seen_all_on && led == 3'b000) begin
        lamp_done = 1'b1;
        $display("[%0t ns] lamp test done, DDR tests starting", $time / 1000);
      end
    end
    else if (led == 3'b111) begin
      $display("[%0t ns] *** FAIL: DDR test %0d failed ***", $time / 1000, stage);
      #(1_000_000) $finish;       // run 1 us more so the flash shows in the waves
    end
    else if (stage == 3'd3 && led == 3'b100) begin
      $display("[%0t ns] *** PASS: all DDR tests passed, running light started ***",
               $time / 1000);
      #(20_000_000) $finish;      // show 20 us of the running light
    end
    else if (led == stage + 3'd1) begin
      stage = led;
      $display("[%0t ns] DDR test %0d running", $time / 1000, stage);
    end
  end

  initial begin
    #(TIMEOUT);
    if (!calib_done)
      $display("*** TIMEOUT: MIG calibration never completed ***");
    else if (!lamp_done)
      $display("*** TIMEOUT: firmware stuck before/in lamp test (is the ELF associated?) ***");
    else
      $display("*** TIMEOUT: firmware stuck in DDR test %0d ***", stage);
    $finish;
  end

endmodule
