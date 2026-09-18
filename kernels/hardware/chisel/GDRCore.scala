// GDRCore.scala — Chisel3 description of the dual-core GDR processor.
//
// GDRCore: simplified microcode executor that interfaces with Verilog-A MAC cells
//          via a BlackBox boundary.
// DualCoreGDR: wires two cores with a shared memory bus and barrier register.

import chisel3._
import chisel3.util._

class GDRCore(id: Int) extends Module {
  val io = IO(new Bundle {
    val start   = Input(Bool())
    val dataIn  = Input(UInt(128.W))
    val dataOut = Output(UInt(128.W))
    val sync    = Flipped(Bool())
  })

  val reg_pc  = RegInit(0.U(10.W))
  val acc_reg = RegInit(0.U(128.W))

  when(io.start) {
    reg_pc := reg_pc + 1.U
  }

  // In a real flow this maps to a BlackBox connecting to the Verilog-A MAC cells
  io.dataOut     := acc_reg + io.dataIn
  io.sync.write(true.B)
}

class DualCoreGDR extends Module {
  val io = IO(new Bundle {
    val global_start = Input(Bool())
    val mem_bus      = Input(UInt(128.W))
    val result_bus   = Output(UInt(256.W))
  })

  val core0 = Module(new GDRCore(0))
  val core1 = Module(new GDRCore(1))

  core0.io.dataIn := io.mem_bus
  core1.io.dataIn := io.mem_bus
  core0.io.start  := io.global_start
  core1.io.start  := io.global_start

  val barrier = RegInit(false.B)
  when(core0.io.sync && core1.io.sync) {
    barrier := true.B
  } .otherwise {
    barrier := false.B
  }

  io.result_bus := Cat(core0.io.dataOut, core1.io.dataOut)
}
