// mac_lateral_array.sv
//
// Spatial systolic array for 16×8 Tensor Core tiling (16×8 MAC nodes).
// Each node computes one FP16 multiply and FP32 accumulate per cycle,
// with Q flowing horizontally and K flowing vertically.
//
// Target: 7nm FinFET CMOS bare-metal systolic dataflow for fused GDR.

`timescale 1ps/1ps

// ── Single lateral MAC node ───────────────────────────────────────────────────
module MAC_Lateral_Node (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] q_in,    // Lateral wavefront (horizontal)
    input  wire [15:0] k_in,    // Vertical wavefront (transposed)
    input  wire [31:0] acc_in,  // Stationary accumulator in
    output reg  [15:0] q_out,   // Shift to next lateral cell
    output reg  [15:0] k_out,   // Shift to next vertical cell
    output reg  [31:0] acc_out  // FP32 accumulated result
);
    wire [31:0] mult_res;

    fp16_combinational_mult u_mult (
        .a (q_in),
        .b (k_in),
        .p (mult_res)
    );

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            q_out   <= 16'h0;
            k_out   <= 16'h0;
            acc_out <= 32'h0;
        end else begin
            q_out   <= q_in;
            k_out   <= k_in;
            acc_out <= acc_in + mult_res;
        end
    end
endmodule

// ── 16×8 lateral array ────────────────────────────────────────────────────────
module TensorCore_Lateral_Array #(
    parameter M = 16,  // Q tile rows
    parameter N = 8    // K tile columns
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] q_matrix_in [M-1:0],
    input  wire [15:0] k_matrix_in [N-1:0]
);
    wire [15:0] lateral_q [M-1:0][N:0];
    wire [15:0] lateral_k [M:0][N-1:0];
    wire [31:0] p_accum   [M-1:0][N-1:0];

    genvar i, j;
    generate
        for (i = 0; i < M; i++) begin : ROW
            for (j = 0; j < N; j++) begin : COL
                MAC_Lateral_Node u_mac (
                    .clk    (clk),
                    .rst_n  (rst_n),
                    .q_in   (j == 0 ? q_matrix_in[i] : lateral_q[i][j]),
                    .k_in   (i == 0 ? k_matrix_in[j] : lateral_k[i][j]),
                    .acc_in (p_accum[i][j]),
                    .q_out  (lateral_q[i][j+1]),
                    .k_out  (lateral_k[i+1][j]),
                    .acc_out(p_accum[i][j])
                );
            end
        end
    endgenerate
endmodule
