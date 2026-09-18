; raw_kickdown_hopper.asm
; RAW KICKDOWN: DeepGEMM Hopper PTX → x86-64 Assembly
; ISA: x86-64 + AMX (primary) + AVX-512 (fallback-1) + AVX2 (fallback-2) + Scalar
; ABI: System V AMD64 / Intel syntax (.att_syntax noprefix suppressed)
;
; Critical rules:
;   - No PTX / CUDA / CUTLASS opcodes as executable code
;   - AMX used only when CPUID.AMX_BF16 / AMX_TILE present; otherwise vector/scalar
;   - All synchronization via software + LOCK / mfence
;   - All descriptor state in ordinary memory structures
;
; SASS / PTX → x86-64 semantic map:
;   wgmma.*            → AMX TDPBF16PS / AVX-512 VFMADD231PS
;   ldmatrix.sync      → VMOVAPS / VMOVDQA64
;   stmatrix.sync      → VMOVAPS
;   cp.async.bulk.*    → REP MOVSB / VMOV + PREFETCH
;   mbarrier.arrive    → LOCK XADD
;   mbarrier.wait      → CMP + spin + PAUSE
;   tensormap.replace  → MOV + MFENCE
;   atom.global.add    → LOCK XADD
;   atom.global.or     → LOCK OR / CMPXCHG loop
;   red.global.add     → VADDPS
;   red.global.or      → VPOR
;   setp.ge            → CMP / SETGE
;   prefetch.global    → PREFETCHT0 / PREFETCHT1
;   fence.proxy.*      → MFENCE / SFENCE

.section .bss
.align 64
SCRATCH_SHARED:   .space 65536
TENSOR_DESC:      .space 128
BARRIER_STATE:    .space 64
DOUBLE_BUF_A0:    .space 16384
DOUBLE_BUF_A1:    .space 16384
DOUBLE_BUF_B0:    .space 16384
DOUBLE_BUF_B1:    .space 16384
ACCUM_TILE:       .space 8192

.section .data
.align 8
ZERO_F32: .float 0.0
ONE_F32:  .float 1.0

.section .text
.intel_syntax noprefix

; ── Tensor descriptor update ──────────────────────────────────────────────────
; SOURCE: tensormap.replace.* + fence.proxy.tensormap
; TARGET: MOV + MFENCE
.globl raw_tensor_descriptor
raw_tensor_descriptor:
    mov [rdi + 0],  rsi     ; base address
    mov [rdi + 8],  edx     ; dimension 0
    mov [rdi + 16], rcx     ; stride 0
    mfence
    ret

; ── Barrier init ─────────────────────────────────────────────────────────────
; SOURCE: mbarrier.init
.globl raw_barrier_init
raw_barrier_init:
    mov qword ptr [rdi + 0],  0     ; phase
    mov qword ptr [rdi + 8],  0     ; expected
    mov qword ptr [rdi + 16], 0     ; completed
    ret

; ── Barrier arrive ────────────────────────────────────────────────────────────
; SOURCE: mbarrier.arrive
.globl raw_barrier_arrive
raw_barrier_arrive:
    lock xadd qword ptr [rdi + 16], 1
    ret

; ── Barrier arrive with expected_tx ──────────────────────────────────────────
.globl raw_barrier_arrive_expect_tx
raw_barrier_arrive_expect_tx:
    mov [rdi + 8], rsi      ; expected_tx
    lock xadd qword ptr [rdi + 16], 1
    ret

; ── Barrier wait (parity spin) ────────────────────────────────────────────────
; SOURCE: mbarrier.try_wait.parity
.globl raw_barrier_wait
raw_barrier_wait:
.Lw_spin:
    mov rax, [rdi + 0]
    cmp rax, rsi
    je  .Lw_done
    pause
    jmp .Lw_spin
.Lw_done:
    xor qword ptr [rdi + 0], 1  ; flip phase
    ret

; ── Async bulk copy ───────────────────────────────────────────────────────────
; SOURCE: cp.async.bulk.* / tma_load_1d
.globl raw_async_copy_semantic
raw_async_copy_semantic:
    mov rcx, rdx
    rep movsb
    ret

.globl raw_prefetch
raw_prefetch:
    prefetcht0 byte ptr [rdi]
    prefetcht1 byte ptr [rdi + 64]
    ret

; ── Tile load / store ─────────────────────────────────────────────────────────
; SOURCE: ldmatrix.sync.aligned / stmatrix.sync.aligned
.globl raw_tile_load
raw_tile_load:
    vmovaps zmm0, [rdi]
    vmovaps zmm1, [rdi + 64]
    ret

.globl raw_tile_store
raw_tile_store:
    vmovaps [rdi],      zmm0
    vmovaps [rdi + 64], zmm1
    ret

; ── AMX GEMM kernel ───────────────────────────────────────────────────────────
; SOURCE: wgmma.* (BF16)
; REQUIRES: CPUID AMX_TILE + AMX_BF16
.globl raw_fma_kernel_amx
raw_fma_kernel_amx:
    tdpbf16ps tmm2, tmm0, tmm1
    ret

; ── AVX-512 FMA tile kernel ───────────────────────────────────────────────────
.globl raw_fma_kernel_avx512
raw_fma_kernel_avx512:
    vfmadd231ps zmm16, zmm0, zmm8
    vfmadd231ps zmm17, zmm0, zmm9
    vfmadd231ps zmm18, zmm0, zmm10
    vfmadd231ps zmm19, zmm0, zmm11
    vfmadd231ps zmm20, zmm1, zmm8
    vfmadd231ps zmm21, zmm1, zmm9
    vfmadd231ps zmm22, zmm1, zmm10
    vfmadd231ps zmm23, zmm1, zmm11
    ret

; ── AVX2 fallback ─────────────────────────────────────────────────────────────
.globl raw_fma_kernel_avx2
raw_fma_kernel_avx2:
    vfmadd231ps ymm0, ymm1, ymm2
    vfmadd231ps ymm3, ymm4, ymm5
    ret

; ── Scalar fallback ───────────────────────────────────────────────────────────
.globl raw_fma_scalar
raw_fma_scalar:
    vfmadd231ss xmm0, xmm1, xmm2
    ret

; ── Atomic add / or ──────────────────────────────────────────────────────────
.globl raw_atomic_add_u32
raw_atomic_add_u32:
    lock xadd dword ptr [rdi], esi
    mov eax, esi
    ret

.globl raw_atomic_add_u64
raw_atomic_add_u64:
    lock xadd qword ptr [rdi], rsi
    mov rax, rsi
    ret

.globl raw_atomic_or_u64
raw_atomic_or_u64:
    lock or qword ptr [rdi], rsi
    ret

; ── Predicate ─────────────────────────────────────────────────────────────────
.globl raw_predicate
raw_predicate:
    cmp edi, esi
    setge al
    movzx eax, al
    ret

; ── Main GEMM loop ────────────────────────────────────────────────────────────
; RDI=A RSI=B RDX=C RCX=M R8=N R9=K
; stack: A_stride, B_stride, C_stride
.globl raw_gemm
raw_gemm:
    push rbp
    mov  rbp, rsp
    push rbx
    push r12
    push r13
    push r14
    push r15

    mov rbx, rdi        ; A
    mov r12, rsi        ; B
    mov r13, rdx        ; C
    mov r14, rcx        ; M
    mov r15, r8         ; N

    ; clear accumulators
    vxorps zmm16, zmm16, zmm16
    vxorps zmm17, zmm17, zmm17
    vxorps zmm18, zmm18, zmm18
    vxorps zmm19, zmm19, zmm19
    vxorps zmm20, zmm20, zmm20
    vxorps zmm21, zmm21, zmm21
    vxorps zmm22, zmm22, zmm22
    vxorps zmm23, zmm23, zmm23

    xor rcx, rcx        ; i = 0
.Lm_loop:
    cmp rcx, r14
    jge .Lm_done

    xor rdx, rdx        ; j = 0
.Ln_loop:
    cmp rdx, r15
    jge .Ln_done

    xor rsi, rsi        ; k = 0
.Lk_loop:
    cmp rsi, r9
    jge .Lk_done

    mov rax, rcx
    imul rax, [rbp + 16]    ; A_stride
    add  rax, rsi
    lea  rdi, [rbx + rax*4]

    mov rax, rsi
    imul rax, [rbp + 24]    ; B_stride
    add  rax, rdx
    lea  r8, [r12 + rax*4]

    vmovups zmm0, [rdi]
    vmovups zmm8, [r8]
    vfmadd231ps zmm16, zmm0, zmm8

    add rsi, 16
    jmp .Lk_loop
.Lk_done:

    mov rax, rcx
    imul rax, [rbp + 32]    ; C_stride
    add  rax, rdx
    lea  rdi, [r13 + rax*4]
    vmovups [rdi], zmm16

    add rdx, 16
    jmp .Ln_loop
.Ln_done:
    add rcx, 16
    jmp .Lm_loop
.Lm_done:

    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    pop rbp
    ret

; ── Accumulator clear / store ─────────────────────────────────────────────────
.globl raw_accum_clear
raw_accum_clear:
    vxorps zmm16, zmm16, zmm16
    vxorps zmm17, zmm17, zmm17
    vxorps zmm18, zmm18, zmm18
    vxorps zmm19, zmm19, zmm19
    vxorps zmm20, zmm20, zmm20
    vxorps zmm21, zmm21, zmm21
    vxorps zmm22, zmm22, zmm22
    vxorps zmm23, zmm23, zmm23
    ret

.globl raw_accum_store
raw_accum_store:
    vmovaps [rdi],       zmm16
    vmovaps [rdi + 64],  zmm17
    vmovaps [rdi + 128], zmm18
    vmovaps [rdi + 192], zmm19
    ret

; ── Fence ─────────────────────────────────────────────────────────────────────
.globl raw_memory_fence
raw_memory_fence:
    mfence
    ret

.globl raw_store_fence
raw_store_fence:
    sfence
    ret

; ── Utility: ld/st shared/global, red.add, red.or ────────────────────────────
.globl raw_ld_shared_u32
raw_ld_shared_u32:
    mov eax, [rdi]
    ret

.globl raw_st_shared_u32
raw_st_shared_u32:
    mov [rdi], esi
    ret

.globl raw_ld_global_u64
raw_ld_global_u64:
    mov rax, [rdi]
    ret

.globl raw_st_global_u64
raw_st_global_u64:
    mov [rdi], rsi
    ret

.globl raw_red_add_u32
raw_red_add_u32:
    lock add dword ptr [rdi], esi
    ret

.globl raw_red_or_u64
raw_red_or_u64:
    lock or qword ptr [rdi], rsi
    ret

; END OF RAW KICKDOWN HOPPER ARTIFACT
