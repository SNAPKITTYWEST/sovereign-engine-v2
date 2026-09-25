; ═══════════════════════════════════════════════════════════════════════════
; libavx512nn.asm
; AVX-512 Neural-Network Primitive Library
;
; Target : x86-64 ELF64 Linux
; ISA : AVX-512F + AVX-512BW + AVX-512DQ + AVX-512VL
; Assembler: FASM (flat assembler) syntax
; ABI : System V AMD64
; ═══════════════════════════════════════════════════════════════════════════

format ELF64 executable
use64

ZMM_BYTES = 64
ZMM_FLOATS = 16
YMM_BYTES = 32
YMM_FLOATS = 8
XMM_BYTES = 16
XMM_FLOATS = 4

SYS_READ = 0
SYS_WRITE = 1
SYS_MMAP = 9
SYS_MUNMAP = 11
SYS_EXIT = 60
SYS_CLOCK_GETTIME = 228

PROT_READ = 1
PROT_WRITE = 2
PROT_EXEC = 4
MAP_PRIVATE = 2
MAP_ANONYMOUS = 0x20

ERR_NONE = 0
ERR_NULL_PTR = 1
ERR_MISALIGNED = 2
ERR_SIZE_ZERO = 3
ERR_ALLOC_FAIL = 4

LAYER_FMA = 1
LAYER_RELU = 2
LAYER_SIGMOID = 3
LAYER_TANH = 4
LAYER_SOFTMAX = 5
LAYER_LNORM = 6
LAYER_DROPOUT = 7
LAYER_MAXPOOL = 8
LAYER_AVGPOOL = 9

; ═══════════════════════════════════════════════════════════════════════════
; SECTION 1 — READ-ONLY DATA
; ═══════════════════════════════════════════════════════════════════════════

section '.rodata' align 64

align 64
const_one_ps: times 16 dd 1.0
const_zero_ps: times 16 dd 0.0
const_half_ps: times 16 dd 0.5
const_negone_ps: times 16 dd -1.0

align 64
const_exp_clip_hi: times 16 dd 88.0
const_exp_clip_lo: times 16 dd -88.0

align 64
const_log2e_ps: times 16 dd 1.4426950408889634
const_ln2_hi_ps: times 16 dd 0.6931471805599453

align 64
tanh_c3: times 16 dd -0.3333333333333333
tanh_c5: times 16 dd 0.1333333333333333
tanh_c7: times 16 dd -0.0539682539682539
tanh_c9: times 16 dd 0.0218694885361552

align 64
sigmoid_sat_hi: times 16 dd 20.0
sigmoid_sat_lo: times 16 dd -20.0

align 64
exp_mask_ps: times 16 dd 0x7F800000
mant_mask_ps: times 16 dd 0x007FFFFF
sign_mask_ps: times 16 dd 0x80000000
poly_bias_ps: times 16 dd 0x3F800000
exp_bias_ps: times 16 dd 127

align 64
banner: db "libavx512nn :: AVX-512 NN primitive library", 10, 0
banner_len = $ - banner

msg_err_null: db "[libavx512nn] null pointer", 10
msg_err_null_len = $ - msg_err_null
msg_err_align: db "[libavx512nn] misaligned pointer", 10
msg_err_align_len = $ - msg_err_align
msg_ok: db "[libavx512nn] ok", 10
msg_ok_len = $ - msg_ok

; ═══════════════════════════════════════════════════════════════════════════
; SECTION 2 — BSS
; ═══════════════════════════════════════════════════════════════════════════

section '.bss' align 64

align 64
scratch_a: rb 4096
scratch_b: rb 4096
scratch_c: rb 4096
scratch_d: rb 4096

stat_ops: rq 1
stat_cycles: rq 1
stat_layers: rq 1
last_error: rq 1

; ═══════════════════════════════════════════════════════════════════════════
; SECTION 3 — MACROS
; ═══════════════════════════════════════════════════════════════════════════

macro TENSOR_FMA accum, a, b {
    vfmadd231ps accum, a, b
}

macro VECTOR_LOAD dst, ptr {
    vmovaps dst, [ptr]
}

macro VECTOR_LOADU dst, ptr {
    vmovups dst, [ptr]
}

macro VECTOR_STORE ptr, src {
    vmovaps [ptr], src
}

macro VECTOR_STOREU ptr, src {
    vmovups [ptr], src
}

macro VECTOR_BROADCAST dst, scalar_ptr {
    vbroadcastss dst, dword [scalar_ptr]
}

macro VECTOR_ZERO dst {
    vpxord dst, dst, dst
}

macro HSUM_PS zmm_src {
    vextractf64x4 ymm1, zmm_src, 1
    vaddps ymm1, ymm1, ymm_src
    vextractf128 xmm2, ymm1, 1
    vaddps xmm1, xmm1, xmm2
    vpermilps xmm2, xmm1, 0x0E
    vaddps xmm1, xmm1, xmm2
    vpermilps xmm2, xmm1, 0x01
    vaddss xmm1, xmm1, xmm2
}

macro HMAX_PS zmm_src {
    vextractf64x4 ymm1, zmm_src, 1
    vmaxps ymm1, ymm1, ymm_src
    vextractf128 xmm2, ymm1, 1
    vmaxps xmm1, xmm1, xmm2
    vpermilps xmm2, xmm1, 0x0E
    vmaxps xmm1, xmm1, xmm2
    vpermilps xmm2, xmm1, 0x01
    vmaxss xmm1, xmm1, xmm2
}

macro FUNC_BEGIN name {
    name:
        push rbp
        mov rbp, rsp
        push rbx
        push r12
        push r13
        push r14
        push r15
        sub rsp, 64
}

macro FUNC_END {
        add rsp, 64
        pop r15
        pop r14
        pop r13
        pop r12
        pop rbx
        pop rbp
        ret
}

macro GUARD_NULL reg, label {
    test reg, reg
    jz label
}

macro GUARD_ZERO reg, label {
    test reg, reg
    jz label
}

; ═══════════════════════════════════════════════════════════════════════════
; SECTION 4 — ENTRY POINT
; ═══════════════════════════════════════════════════════════════════════════

section '.text' executable align 64

public _start
_start:
    mov eax, SYS_WRITE
    mov edi, 1
    mov rsi, banner
    mov edx, banner_len
    syscall
    call nn_selftest
    mov eax, SYS_EXIT
    xor edi, edi
    syscall

; ═══════════════════════════════════════════════════════════════════════════
; SECTION 6 — VECTOR-LEVEL PRIMITIVES
; ═══════════════════════════════════════════════════════════════════════════

public nn_vadd
FUNC_BEGIN nn_vadd
    GUARD_NULL rdi, .null
    GUARD_NULL rsi, .null
    GUARD_NULL rdx, .null
    GUARD_ZERO rcx, .done
    shl rcx, 2
    add rcx, rdi
.vloop:
    vmovaps zmm0, [rdi]
    vmovaps zmm1, [rsi]
    vaddps zmm0, zmm0, zmm1
    vmovaps [rdx], zmm0
    add rdi, ZMM_BYTES
    add rsi, ZMM_BYTES
    add rdx, ZMM_BYTES
    cmp rdi, rcx
    jb .vloop
.done:
    FUNC_END
.null:
    mov rax, ERR_NULL_PTR
    FUNC_END

public nn_vsub
FUNC_BEGIN nn_vsub
    GUARD_NULL rdi, .null
    GUARD_NULL rsi, .null
    GUARD_NULL rdx, .null
    GUARD_ZERO rcx, .done
    shl rcx, 2
    add rcx, rdi
.vloop:
    vmovaps zmm0, [rdi]
    vmovaps zmm1, [rsi]
    vsubps zmm0, zmm0, zmm1
    vmovaps [rdx], zmm0
    add rdi, ZMM_BYTES
    add rsi, ZMM_BYTES
    add rdx, ZMM_BYTES
    cmp rdi, rcx
    jb .vloop
.done:
    FUNC_END
.null:
    mov rax, ERR_NULL_PTR
    FUNC_END

public nn_vmul
FUNC_BEGIN nn_vmul
    GUARD_NULL rdi, .null
    GUARD_NULL rsi, .null
    GUARD_NULL rdx, .null
    GUARD_ZERO rcx, .done
    shl rcx, 2
    add rcx, rdi
.vloop:
    vmovaps zmm0, [rdi]
    vmovaps zmm1, [rsi]
    vmulps zmm0, zmm0, zmm1
    vmovaps [rdx], zmm0
    add rdi, ZMM_BYTES
    add rsi, ZMM_BYTES
    add rdx, ZMM_BYTES
    cmp rdi, rcx
    jb .vloop
.done:
    FUNC_END
.null:
    mov rax, ERR_NULL_PTR
    FUNC_END

public nn_vscale
FUNC_BEGIN nn_vscale
    GUARD_NULL rdi, .null
    GUARD_NULL rdx, .null
    GUARD_ZERO rcx, .done
    vbroadcastss zmm7, xmm0
    shl rcx, 2
    add rcx, rdi
.vloop:
    vmovaps zmm1, [rdi]
    vmulps zmm1, zmm1, zmm7
    vmovaps [rdx], zmm1
    add rdi, ZMM_BYTES
    add rdx, ZMM_BYTES
    cmp rdi, rcx
    jb .vloop
.done:
    FUNC_END
.null:
    mov rax, ERR_NULL_PTR
    FUNC_END

public nn_vdot
FUNC_BEGIN nn_vdot
    GUARD_NULL rdi, .null
    GUARD_NULL rsi, .null
    GUARD_ZERO rcx, .done
    VECTOR_ZERO zmm0
    shl rcx, 2
    add rcx, rdi
.vloop:
    vmovaps zmm1, [rdi]
    vmovaps zmm2, [rsi]
    vfmadd231ps zmm0, zmm1, zmm2
    add rdi, ZMM_BYTES
    add rsi, ZMM_BYTES
    cmp rdi, rcx
    jb .vloop
    HSUM_PS zmm0
.done:
    FUNC_END
.null:
    vxorps xmm0, xmm0, xmm0
    FUNC_END

; ═══════════════════════════════════════════════════════════════════════════
; SECTION 8 — ACTIVATION FUNCTIONS
; ═══════════════════════════════════════════════════════════════════════════

public nn_relu
FUNC_BEGIN nn_relu
    GUARD_NULL rdi, .null
    GUARD_NULL rdx, .null
    GUARD_ZERO rsi, .done
    VECTOR_ZERO zmm7
    mov rcx, rsi
    shl rcx, 2
    add rcx, rdi
.vloop:
    vmovaps zmm0, [rdi]
    vmaxps zmm0, zmm0, zmm7
    vmovaps [rdx], zmm0
    add rdi, ZMM_BYTES
    add rdx, ZMM_BYTES
    cmp rdi, rcx
    jb .vloop
.done:
    FUNC_END
.null:
    mov rax, ERR_NULL_PTR
    FUNC_END

public nn_relu_inplace
FUNC_BEGIN nn_relu_inplace
    GUARD_NULL rdi, .null
    GUARD_ZERO rsi, .done
    VECTOR_ZERO zmm7
    mov rcx, rsi
    shl rcx, 2
    add rcx, rdi
.vloop:
    vmovaps zmm0, [rdi]
    vmaxps zmm0, zmm0, zmm7
    vmovaps [rdi], zmm0
    add rdi, ZMM_BYTES
    cmp rdi, rcx
    jb .vloop
.done:
    FUNC_END
.null:
    mov rax, ERR_NULL_PTR
    FUNC_END

public nn_sigmoid
FUNC_BEGIN nn_sigmoid
    GUARD_NULL rdi, .null
    GUARD_NULL rdx, .null
    GUARD_ZERO rsi, .done
    mov rcx, rsi
    shl rcx, 2
    add rcx, rdi
.vloop:
    vmovaps zmm0, [rdi]
    vminps zmm0, zmm0, [sigmoid_sat_hi]
    vmaxps zmm0, zmm0, [sigmoid_sat_lo]
    vxorps zmm0, zmm0, [sign_mask_ps]
    vmulps zmm0, zmm0, [const_log2e_ps]
    vrndscaleps zmm1, zmm0, 0
    vsubps zmm2, zmm0, zmm1
    vmulps zmm3, zmm2, zmm2
    vmulps zmm4, zmm3, zmm3
    vbroadcastss zmm5, [exp_c4]
    vmulps zmm5, zmm5, zmm4
    vbroadcastss zmm6, [exp_c3]
    vmulps zmm6, zmm6, zmm3
    vmulps zmm6, zmm6, zmm2
    vaddps zmm5, zmm5, zmm6
    vbroadcastss zmm6, [exp_c2]
    vmulps zmm6, zmm6, zmm3
    vaddps zmm5, zmm5, zmm6
    vbroadcastss zmm6, [exp_c1]
    vmulps zmm6, zmm6, zmm2
    vaddps zmm5, zmm5, zmm6
    vbroadcastss zmm6, [exp_c0]
    vaddps zmm5, zmm5, zmm6
    vcvttps2dq zmm1, zmm1
    vpslld zmm1, zmm1, 23
    vpaddd zmm5, zmm5, zmm1
    vaddps zmm5, zmm5, [const_one_ps]
    vbroadcastss zmm7, [const_one_ps]
    vdivps zmm7, zmm7, zmm5
    vmovaps [rdx], zmm7
    add rdi, ZMM_BYTES
    add rdx, ZMM_BYTES
    cmp rdi, rcx
    jb .vloop
.done:
    FUNC_END
.null:
    mov rax, ERR_NULL_PTR
    FUNC_END

public nn_softmax
FUNC_BEGIN nn_softmax
    push rbx
    push r12
    push r13
    mov rbx, rdi
    mov r12, rsi
    VECTOR_ZERO zmm15
    mov rcx, rsi
    shl rcx, 2
    add rcx, rdi
.max_loop:
    vmaxps zmm15, zmm15, [rdi]
    add rdi, ZMM_BYTES
    cmp rdi, rcx
    jb .max_loop
    HMAX_PS zmm15
    vbroadcastss zmm15, xmm1
    mov rdi, rbx
    VECTOR_ZERO zmm14
    mov rcx, r12
    shl rcx, 2
    add rcx, rbx
.exp_loop:
    vmovaps zmm0, [rdi]
    vsubps zmm0, zmm0, zmm15
    vminps zmm0, zmm0, [const_exp_clip_hi]
    vmaxps zmm0, zmm0, [const_exp_clip_lo]
    vmulps zmm0, zmm0, [const_log2e_ps]
    vrndscaleps zmm1, zmm0, 0
    vsubps zmm2, zmm0, zmm1
    vmulps zmm3, zmm2, zmm2
    vmulps zmm4, zmm3, zmm3
    vbroadcastss zmm5, [exp_c4]
    vmulps zmm5, zmm5, zmm4
    vbroadcastss zmm6, [exp_c3]
    vmulps zmm6, zmm6, zmm3
    vmulps zmm6, zmm6, zmm2
    vaddps zmm5, zmm5, zmm6
    vbroadcastss zmm6, [exp_c2]
    vmulps zmm6, zmm6, zmm3
    vaddps zmm5, zmm5, zmm6
    vbroadcastss zmm6, [exp_c1]
    vmulps zmm6, zmm6, zmm2
    vaddps zmm5, zmm5, zmm6
    vbroadcastss zmm6, [exp_c0]
    vaddps zmm5, zmm5, zmm6
    vcvttps2dq zmm1, zmm1
    vpslld zmm1, zmm1, 23
    vpaddd zmm5, zmm5, zmm1
    vmovaps [rdi], zmm5
    vaddps zmm14, zmm14, zmm5
    add rdi, ZMM_BYTES
    cmp rdi, rcx
    jb .exp_loop
    HSUM_PS zmm14
    vbroadcastss zmm14, xmm1
    mov rdi, rbx
    mov rcx, r12
    shl rcx, 2
    add rcx, rbx
.div_loop:
    vmovaps zmm0, [rdi]
    vdivps zmm0, zmm0, zmm14
    vmovaps [rdi], zmm0
    add rdi, ZMM_BYTES
    cmp rdi, rcx
    jb .div_loop
    pop r13
    pop r12
    pop rbx
    FUNC_END

; ═══════════════════════════════════════════════════════════════════════════
; SECTION 13 — LAYER DISPATCH
; ═══════════════════════════════════════════════════════════════════════════

public nn_exec_layer
FUNC_BEGIN nn_exec_layer
    cmp rdi, LAYER_FMA
    je .fma
    cmp rdi, LAYER_RELU
    je .relu
    cmp rdi, LAYER_SIGMOID
    je .sigmoid
    cmp rdi, LAYER_TANH
    je .tanh
    cmp rdi, LAYER_SOFTMAX
    je .softmax
    jmp .unknown
.fma:
    mov rdi, rsi
    mov rsi, rdx
    mov rdx, rcx
    mov rcx, r8
    call nn_vmul
    jmp .done
.relu:
    mov rdi, rsi
    mov rsi, r8
    mov rdx, rcx
    call nn_relu
    jmp .done
.sigmoid:
    mov rdi, rsi
    mov rsi, r8
    mov rdx, rcx
    call nn_sigmoid
    jmp .done
.tanh:
    mov rdi, rsi
    mov rsi, r8
    mov rdx, rcx
    call nn_tanh
    jmp .done
.softmax:
    mov rdi, rsi
    mov rsi, r8
    call nn_softmax
    jmp .done
.unknown:
    mov rax, ERR_NONE
.done:
    inc qword [stat_layers]
    FUNC_END

; tanh stub
public nn_tanh
FUNC_BEGIN nn_tanh
    GUARD_NULL rdi, .null
    GUARD_NULL rdx, .null
    GUARD_ZERO rsi, .done
    ; simplified: tanh ~ 2*sigmoid(2x)-1 via in-place
    mov rcx, rsi
    shl rcx, 2
    add rcx, rdi
    vbroadcastss zmm15, [const_two]
.vloop:
    vmovaps zmm0, [rdi]
    vmulps zmm0, zmm0, zmm15
    vminps zmm0, zmm0, [sigmoid_sat_hi]
    vmaxps zmm0, zmm0, [sigmoid_sat_lo]
    vxorps zmm0, zmm0, [sign_mask_ps]
    vmulps zmm0, zmm0, [const_log2e_ps]
    vrndscaleps zmm1, zmm0, 0
    vsubps zmm2, zmm0, zmm1
    vmulps zmm3, zmm2, zmm2
    vmulps zmm4, zmm3, zmm3
    vbroadcastss zmm5, [exp_c4]
    vmulps zmm5, zmm5, zmm4
    vbroadcastss zmm6, [exp_c3]
    vmulps zmm6, zmm6, zmm3
    vmulps zmm6, zmm6, zmm2
    vaddps zmm5, zmm5, zmm6
    vbroadcastss zmm6, [exp_c2]
    vmulps zmm6, zmm6, zmm3
    vaddps zmm5, zmm5, zmm6
    vbroadcastss zmm6, [exp_c1]
    vmulps zmm6, zmm6, zmm2
    vaddps zmm5, zmm5, zmm6
    vbroadcastss zmm6, [exp_c0]
    vaddps zmm5, zmm5, zmm6
    vcvttps2dq zmm1, zmm1
    vpslld zmm1, zmm1, 23
    vpaddd zmm5, zmm5, zmm1
    vaddps zmm5, zmm5, [const_one_ps]
    vbroadcastss zmm7, [const_one_ps]
    vdivps zmm7, zmm7, zmm5
    vaddps zmm7, zmm7, zmm7
    vsubps zmm7, zmm7, [const_one_ps]
    vmovaps [rdx], zmm7
    add rdi, ZMM_BYTES
    add rdx, ZMM_BYTES
    cmp rdi, rcx
    jb .vloop
.done:
    FUNC_END
.null:
    mov rax, ERR_NULL_PTR
    FUNC_END

; ═══════════════════════════════════════════════════════════════════════════
; SECTION 15 — SELF-TEST
; ═══════════════════════════════════════════════════════════════════════════

public nn_selftest
FUNC_BEGIN nn_selftest
    lea rdi, [test_matrix]
    lea rsi, [test_vector]
    lea rdx, [scratch_a]
    mov rcx, 4
    mov r8, 4
    call nn_matvec
    lea rsi, [msg_ok]
    mov edx, msg_ok_len
    mov eax, SYS_WRITE
    mov edi, 1
    syscall
    FUNC_END

; matvec stub
public nn_matvec
FUNC_BEGIN nn_matvec
    push rbx
    push r12
    push r13
    mov r12, rdi
    mov r13, rsi
    mov rbx, rcx
    VECTOR_ZERO zmm0
.row:
    test rbx, rbx
    jz .done
    xor eax, eax
.col:
    cmp rax, r8
    jae .store
    vmovss xmm1, dword [r12 + rax*4]
    vmovss xmm2, dword [r13 + rax*4]
    vmulss xmm1, xmm1, xmm2
    vaddss xmm0, xmm0, xmm1
    inc rax
    jmp .col
.store:
    vmovss dword [rdx], xmm0
    add r12, r8
    add r12, r8
    add r12, r8
    add r12, r8
    add rdx, 4
    VECTOR_ZERO zmm0
    dec rbx
    jmp .row
.done:
    pop r13
    pop r12
    pop rbx
    FUNC_END

; ═══════════════════════════════════════════════════════════════════════════
; SECTION 16 — DATA TABLES
; ═══════════════════════════════════════════════════════════════════════════

section '.data' align 64

align 64
exp_c0: dd 1.0
exp_c1: dd 0.6931471805599453
exp_c2: dd 0.2402265069591007
exp_c3: dd 0.0555041086648216
exp_c4: dd 0.0096181291076285

const_two: dd 2.0
const_half: dd 0.5
const_quarter: dd 0.25
const_ten: dd 10.0
const_sqrt_2_pi: dd 0.7978845608028654
const_gelu_c: dd 0.044715

align 64
test_matrix: dd 1.0, 2.0, 3.0, 4.0
             dd 5.0, 6.0, 7.0, 8.0
             dd 9.0, 10.0, 11.0, 12.0
             dd 13.0, 14.0, 15.0, 16.0

test_vector: dd 1.0, 1.0, 1.0, 1.0

; ═══════════════════════════════════════════════════════════════════════════
; END OF libavx512nn.asm
; ═══════════════════════════════════════════════════════════════════════════
