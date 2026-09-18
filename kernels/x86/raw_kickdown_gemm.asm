; raw_kickdown_gemm.asm
; RAW KICKDOWN: Dense NASM x86-64 super-scalar FP32 GEMM
; ISA: x86-64 + AVX2 + FMA
; ABI: System V AMD64
;
; Signature:
;   void raw_kickdown_gemm(float *A, float *B, float *C,
;                          size_t M, size_t N, size_t K)
; Operation:
;   C[M,N] += A[M,K] * B[K,N]   (row-major FP32)
;
; SASS semantic map:
;   HMMA.16816.F32  → VFMADD231PS / VFMADD231SS
;   LDSM / LDSM.TRANS → VMOVUPS / VMOVAPS
;   LDGSTS.E.128    → PREFETCHT0 + VMOVUPS
;   DEPBAR.LE SB0   → (dependency resolved by sequential execution)
;   BAR.SYNC        → MFENCE
;   FFMA.F32        → VFMADD231PS

BITS 64
DEFAULT REL

SECTION .text

GLOBAL raw_kickdown_gemm
GLOBAL raw_kickdown_atomic_add
GLOBAL raw_kickdown_atomic_or
GLOBAL raw_kickdown_barrier_init
GLOBAL raw_kickdown_barrier_arrive
GLOBAL raw_kickdown_barrier_wait
GLOBAL raw_kickdown_descriptor_replace
GLOBAL raw_kickdown_vector_reduce_add
GLOBAL raw_kickdown_vector_reduce_or
GLOBAL raw_kickdown_fma8
GLOBAL raw_kickdown_pipeline
GLOBAL raw_kickdown_copy_prepare
GLOBAL raw_kickdown_final_accumulate

; ============================================================================
; raw_kickdown_gemm
; RDI=A  RSI=B  RDX=C  RCX=M  R8=N  R9=K
; ============================================================================
raw_kickdown_gemm:
    push rbp
    push rbx
    push r12
    push r13
    push r14
    push r15

    mov rbx, rdi
    mov rbp, rsi
    mov r10, rdx
    mov r12, rcx        ; M
    mov r11, r8         ; N
    mov r13, r9         ; K

    test r12, r12
    jz .gemm_done
    test r11, r11
    jz .gemm_done
    test r13, r13
    jz .gemm_done

    xor r12, r12        ; m = 0

.m_loop:
    cmp r12, rcx
    jae .gemm_done

    mov rax, r12
    imul rax, r9
    lea r14, [rbx + rax*4]      ; A row ptr

    mov rax, r12
    imul rax, r8
    lea r15, [r10 + rax*4]      ; C row ptr

    xor r11, r11                ; n = 0

.n_loop:
    cmp r11, r8
    jae .next_m

    mov rax, r8
    sub rax, r11

    cmp rax, 32
    jb .n_tail_16

    ; 32-wide vector path
    vmovups ymm0, [r15 + r11*4]
    vmovups ymm1, [r15 + r11*4 + 32]
    vmovups ymm2, [r15 + r11*4 + 64]
    vmovups ymm3, [r15 + r11*4 + 96]

    xor r13, r13

.k_loop_32:
    cmp r13, r9
    jae .store_32

    vmovups ymm4, [r14 + r13*4]

    mov rax, r13
    imul rax, r8
    add rax, r11
    shl rax, 2
    vbroadcastss ymm5, [rbp + rax]

    vfmadd231ps ymm0, ymm4, ymm5
    vfmadd231ps ymm1, ymm4, ymm5
    vfmadd231ps ymm2, ymm4, ymm5
    vfmadd231ps ymm3, ymm4, ymm5
    inc r13
    jmp .k_loop_32

.store_32:
    vmovups [r15 + r11*4],      ymm0
    vmovups [r15 + r11*4 + 32], ymm1
    vmovups [r15 + r11*4 + 64], ymm2
    vmovups [r15 + r11*4 + 96], ymm3
    add r11, 32
    jmp .n_loop

.n_tail_16:
    cmp rax, 16
    jb .n_tail_8

    vmovups ymm0, [r15 + r11*4]
    vmovups ymm1, [r15 + r11*4 + 32]
    xor r13, r13

.k_loop_16:
    cmp r13, r9
    jae .store_16

    vmovups ymm4, [r14 + r13*4]
    mov rax, r13
    imul rax, r8
    add rax, r11
    shl rax, 2
    vbroadcastss ymm5, [rbp + rax]
    vfmadd231ps ymm0, ymm4, ymm5
    vfmadd231ps ymm1, ymm4, ymm5
    inc r13
    jmp .k_loop_16

.store_16:
    vmovups [r15 + r11*4],      ymm0
    vmovups [r15 + r11*4 + 32], ymm1
    add r11, 16
    jmp .n_loop

.n_tail_8:
    cmp rax, 8
    jb .n_tail_4

    vmovups xmm0, [r15 + r11*4]
    xor r13, r13

.k_loop_8:
    cmp r13, r9
    jae .store_8
    vmovups xmm4, [r14 + r13*4]
    mov rax, r13
    imul rax, r8
    add rax, r11
    shl rax, 2
    vbroadcastss xmm5, [rbp + rax]
    vfmadd231ps xmm0, xmm4, xmm5
    inc r13
    jmp .k_loop_8

.store_8:
    vmovups [r15 + r11*4], xmm0
    add r11, 8
    jmp .n_loop

.n_tail_4:
    cmp rax, 4
    jb .n_tail_1

    movups xmm0, [r15 + r11*4]
    xor r13, r13

.k_loop_4:
    cmp r13, r9
    jae .store_4
    movups xmm4, [r14 + r13*4]
    mov rax, r13
    imul rax, r8
    add rax, r11
    shl rax, 2
    movss xmm5, [rbp + rax]
    shufps xmm5, xmm5, 0
    vfmadd231ps xmm0, xmm4, xmm5
    inc r13
    jmp .k_loop_4

.store_4:
    movups [r15 + r11*4], xmm0
    add r11, 4
    jmp .n_loop

.n_tail_1:
    test rax, rax
    jz .next_m
    xor r13, r13

.tail_scalar:
    cmp r13, r9
    jae .tail_done
    mov rax, r13
    imul rax, r8
    add rax, r11
    shl rax, 2
    movss xmm0, [r14 + r13*4]
    mulss xmm0, [rbp + rax]
    mov rax, r11
    shl rax, 2
    addss xmm0, [r15 + rax]
    movss [r15 + rax], xmm0
    inc r13
    jmp .tail_scalar

.tail_done:
    inc r11
    jmp .n_loop

.next_m:
    inc r12
    jmp .m_loop

.gemm_done:
    vzeroupper
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    pop rbp
    ret

; ============================================================================
; Barrier
; ============================================================================
raw_kickdown_barrier_init:
    mov dword [rdi + 0], esi    ; phase
    mov dword [rdi + 4], edx    ; expected
    mov dword [rdi + 8], 0      ; completed
    mfence
    ret

raw_kickdown_barrier_arrive:
    mov eax, 1
    lock xadd [rdi + 8], eax
    mfence
    ret

raw_kickdown_barrier_wait:
.wait_spin:
    mov eax, [rdi + 8]
    cmp eax, [rdi + 4]
    jae .wait_done
    pause
    jmp .wait_spin
.wait_done:
    mfence
    ret

; ============================================================================
; Atomic operations
; ============================================================================
raw_kickdown_atomic_add:
    mov eax, esi
    lock xadd [rdi], eax
    ret

raw_kickdown_atomic_or:
.retry:
    mov ecx, [rdi]
    mov edx, ecx
    or  edx, esi
    lock cmpxchg [rdi], edx
    jnz .retry
    mov eax, edx
    ret

; ============================================================================
; Descriptor replace (TENSORMAP semantic reduction)
; ============================================================================
raw_kickdown_descriptor_replace:
    ; RDI=desc, RSI=base, RDX=dim_m, RCX=dim_n, R8=stride_m, R9=stride_n
    mov [rdi + 0],  rsi
    mov [rdi + 8],  rdx
    mov [rdi + 16], rcx
    mov [rdi + 24], r8
    mov [rdi + 32], r9
    mfence
    mov rax, rdi
    ret

; ============================================================================
; Vector reductions
; ============================================================================
raw_kickdown_vector_reduce_add:
    ; RDI=ptr  RSI=count(multiple of 8)  RDX=result ptr
    vxorps ymm0, ymm0, ymm0
    xor rax, rax
.ra_loop:
    cmp rax, rsi
    jae .ra_horiz
    vaddps ymm0, ymm0, [rdi + rax*4]
    add rax, 8
    jmp .ra_loop
.ra_horiz:
    vextractf128 xmm1, ymm0, 1
    vaddps xmm0, xmm0, xmm1
    vhaddps xmm0, xmm0, xmm0
    vhaddps xmm0, xmm0, xmm0
    vmovss [rdx], xmm0
    vzeroupper
    ret

raw_kickdown_vector_reduce_or:
    vpxor ymm0, ymm0, ymm0
    xor rax, rax
.ro_loop:
    cmp rax, rsi
    jae .ro_horiz
    vpor ymm0, ymm0, [rdi + rax*4]
    add rax, 8
    jmp .ro_loop
.ro_horiz:
    vextractf128 xmm1, ymm0, 1
    vpor xmm0, xmm0, xmm1
    vmovd eax, xmm0
    mov [rdx], eax
    vzeroupper
    ret

; ============================================================================
; FMA-8 unrolled kernel
; ============================================================================
raw_kickdown_fma8:
    ; RDI=A_row RSI=B_col RDX=C_out RCX=K
    vxorps ymm0, ymm0, ymm0
    xor rax, rax
.fma8_loop:
    cmp rax, rcx
    jae .fma8_store
    vmovups ymm4, [rdi + rax*4]
    vbroadcastss ymm5, [rsi + rax*4]
    vfmadd231ps ymm0, ymm4, ymm5
    inc rax
    jmp .fma8_loop
.fma8_store:
    vmovups [rdx], ymm0
    vzeroupper
    ret

; ============================================================================
; Independent accumulator pipeline (8-wide)
; ============================================================================
raw_kickdown_pipeline:
    vxorps ymm0, ymm0, ymm0
    vxorps ymm1, ymm1, ymm1
    vxorps ymm2, ymm2, ymm2
    vxorps ymm3, ymm3, ymm3
    vxorps ymm4, ymm4, ymm4
    vxorps ymm5, ymm5, ymm5
    vxorps ymm6, ymm6, ymm6
    vxorps ymm7, ymm7, ymm7
    xor r14, r14
.pipe_loop:
    cmp r14, rcx
    jae .pipe_done
    prefetcht0 [rdi + r14*4 + 256]
    prefetcht0 [rsi + r14*4 + 256]
    vmovups ymm8,  [rdi + r14*4]
    vmovups ymm9,  [rdi + r14*4 + 32]
    vbroadcastss ymm10, [rsi + r14*4]
    vbroadcastss ymm11, [rsi + r14*4 + 4]
    vfmadd231ps ymm0, ymm8,  ymm10
    vfmadd231ps ymm1, ymm9,  ymm10
    vfmadd231ps ymm2, ymm8,  ymm11
    vfmadd231ps ymm3, ymm9,  ymm11
    vmovups ymm12, [rdi + r14*4 + 64]
    vmovups ymm13, [rdi + r14*4 + 96]
    vbroadcastss ymm14, [rsi + r14*4 + 8]
    vbroadcastss ymm15, [rsi + r14*4 + 12]
    vfmadd231ps ymm4, ymm12, ymm14
    vfmadd231ps ymm5, ymm13, ymm14
    vfmadd231ps ymm6, ymm12, ymm15
    vfmadd231ps ymm7, ymm13, ymm15
    add r14, 4
    jmp .pipe_loop
.pipe_done:
    vmovups [rdx],       ymm0
    vmovups [rdx + 32],  ymm1
    vmovups [rdx + 64],  ymm2
    vmovups [rdx + 96],  ymm3
    vmovups [rdx + 128], ymm4
    vmovups [rdx + 160], ymm5
    vmovups [rdx + 192], ymm6
    vmovups [rdx + 224], ymm7
    vzeroupper
    ret

; ============================================================================
; Async-copy semantic (cp.async reduction: PREFETCH + REP MOVSB)
; ============================================================================
raw_kickdown_copy_prepare:
    push rbx
    push rbp
    mov rbx, rdi        ; src
    mov rbp, rsi        ; dst
    mov rcx, rdx        ; count (FP32 elements)
    prefetcht0 [rbx]
    prefetcht0 [rbx + 64]
    prefetcht0 [rbx + 128]
    prefetcht0 [rbx + 192]
.cp_loop:
    cmp rcx, 32
    jb .cp_tail
    vmovups ymm0, [rbx]
    vmovups ymm1, [rbx + 32]
    vmovups ymm2, [rbx + 64]
    vmovups ymm3, [rbx + 96]
    vmovups [rbp],       ymm0
    vmovups [rbp + 32],  ymm1
    vmovups [rbp + 64],  ymm2
    vmovups [rbp + 96],  ymm3
    add rbx, 128
    add rbp, 128
    sub rcx, 32
    prefetcht0 [rbx + 256]
    jmp .cp_loop
.cp_tail:
    test rcx, rcx
    jz .cp_done
.cp_scalar:
    mov eax, [rbx]
    mov [rbp], eax
    add rbx, 4
    add rbp, 4
    dec rcx
    jnz .cp_scalar
.cp_done:
    sfence
    pop rbp
    pop rbx
    ret

; ============================================================================
; Final accumulate (reduction across output tiles)
; ============================================================================
raw_kickdown_final_accumulate:
    ; RDI=dst  RSI=src  RDX=count(multiple of 8)
    xor rax, rax
.fa_loop:
    cmp rax, rdx
    jae .fa_done
    vmovups ymm0, [rdi + rax*4]
    vaddps  ymm0, ymm0, [rsi + rax*4]
    vmovups [rdi + rax*4], ymm0
    add rax, 8
    jmp .fa_loop
.fa_done:
    vzeroupper
    ret
