BITS 64
DEFAULT REL
SECTION .text
GLOBAL raw_kickdown

; RAW KICKDOWN: DeepGEMM SM90 FP8 WGMMA semantic reduction
; System V AMD64 ABI
; RDI=A FP8 E4M3 row-major MxK
; RSI=B FP8 E4M3 row-major KxN
; RDX=C BF16 row-major MxN, accumulated from decoded FP8 products in FP32
; RCX=M, R8=N, R9=K
; Clobbers RAX, R10, R11, R12, R13, R14, R15, XMM0-XMM31
; Preserves RBX,RBP,R12-R15 by stack save/restore.
; Requires AVX2 + FMA. No AVX-512, AMX, CUDA or PTX.

%define M_TILE 4
%define N_TILE 8
%define K_UNROLL 4

raw_kickdown:
    push rbp
    push rbx
    push r12
    push r13
    push r14
    push r15
    mov rbp, rsp
    and rsp, -32
    sub rsp, 128

    test rcx, rcx
    jz .done
    test r8, r8
    jz .done
    test r9, r9
    jz .done

    mov r10, rdi
    mov r11, rsi
    mov r12, rdx
    mov [rsp+112], r10
    mov [rsp+120], r11
    mov r13, rcx
    mov r14, r8
    mov r15, r9

; SOURCE PRIMITIVE: tensormap.replace
; SEMANTIC: descriptor/address metadata
; TARGET: scalar address generation
    mov rax, r13
    imul rax, r15
    mov [rsp+0], rax
    mov rax, r15
    mov [rsp+8], rax
    mov rax, r14
    mov [rsp+16], rax

; SOURCE PRIMITIVE: mbarrier
; SEMANTIC: transaction phase state
; TARGET: ordinary stack-resident control state
    xor eax, eax
    mov [rsp+24], rax
    mov [rsp+32], rax
    mov [rsp+40], rax

; SOURCE PRIMITIVE: ldmatrix
; SEMANTIC: structured fragment load
; TARGET: scalar FP8 byte loads followed by decode
    xor ebx, ebx

.m_loop:
    cmp rbx, r13
    jae .done
    mov rax, r13
    sub rax, rbx
    cmp rax, M_TILE
    jb .m_tail

    xor rax, rax
.n_loop:
    cmp rax, r14
    jae .next_m
    mov rdi, r14
    sub rdi, rax
    cmp rdi, N_TILE
    jb .n_tail

    ; Eight FP32 accumulators per output row, four rows.
    vxorps ymm0, ymm0, ymm0
    vxorps ymm1, ymm1, ymm1
    vxorps ymm2, ymm2, ymm2
    vxorps ymm3, ymm3, ymm3
    vxorps ymm4, ymm4, ymm4
    vxorps ymm5, ymm5, ymm5
    vxorps ymm6, ymm6, ymm6
    vxorps ymm7, ymm7, ymm7
    xor rdi, rdi

.k_loop:
    cmp rdi, r15
    jae .store_tile

    ; A row pointers: four independent address streams.
    mov rcx, rbx
    imul rcx, r15
    add rcx, rdi
    mov r10, [rsp+112]
    lea rcx, [r10+rcx]
    mov rdx, rbx
    add rdx, 1
    imul rdx, r15
    add rdx, rdi
    mov r10, [rsp+112]
    lea rdx, [r10+rdx]
    mov rsi, rbx
    add rsi, 2
    imul rsi, r15
    add rsi, rdi
    mov r10, [rsp+112]
    lea rsi, [r10+rsi]
    mov r9, rbx
    add r9, 3
    imul r9, r15
    add r9, rdi
    mov r10, [rsp+112]
    lea r9, [r10+r9]

    ; SOURCE PRIMITIVE: wgmma
    ; SEMANTIC: matrix multiply accumulate
    ; TARGET: AVX2 broadcast + FMA
    ; Decode four FP8 E4M3 A scalars into XMM registers.
    movzx r8d, byte [rcx]
    call .decode_fp8
    vmovss xmm8, xmm0
    movzx r8d, byte [rdx]
    call .decode_fp8
    vmovss xmm9, xmm0
    movzx r8d, byte [rsi]
    call .decode_fp8
    vmovss xmm10, xmm0
    movzx r8d, byte [r9]
    call .decode_fp8
    vmovss xmm11, xmm0

    ; Load eight B elements, decode into a contiguous FP32 vector.
    mov r8, rdi
    imul r8, r14
    add r8, rax
    mov r11, [rsp+120]
    add r8, r11
    movzx r9d, byte [r8]
    call .decode_fp8_r9
    vmovss [rsp+48], xmm0
    movzx r9d, byte [r8+1]
    call .decode_fp8_r9
    vmovss [rsp+52], xmm0
    movzx r9d, byte [r8+2]
    call .decode_fp8_r9
    vmovss [rsp+56], xmm0
    movzx r9d, byte [r8+3]
    call .decode_fp8_r9
    vmovss [rsp+60], xmm0
    movzx r9d, byte [r8+4]
    call .decode_fp8_r9
    vmovss [rsp+64], xmm0
    movzx r9d, byte [r8+5]
    call .decode_fp8_r9
    vmovss [rsp+68], xmm0
    movzx r9d, byte [r8+6]
    call .decode_fp8_r9
    vmovss [rsp+72], xmm0
    movzx r9d, byte [r8+7]
    call .decode_fp8_r9
    vmovss [rsp+76], xmm0
    vmovups ymm12, [rsp+48]

    ; Four independent output-row accumulators, each covering eight N columns.
    vbroadcastss ymm8, xmm8
    vbroadcastss ymm9, xmm9
    vbroadcastss ymm10, xmm10
    vbroadcastss ymm11, xmm11
    vfmadd231ps ymm0, ymm8, ymm12
    vfmadd231ps ymm1, ymm9, ymm12
    vfmadd231ps ymm2, ymm10, ymm12
    vfmadd231ps ymm3, ymm11, ymm12

    inc rdi
    jmp .k_loop

.store_tile:
    ; SOURCE PRIMITIVE: stmatrix
    ; SEMANTIC: structured fragment store
    ; TARGET: scalar reduction and BF16 conversion stores
    mov rcx, rbx
    imul rcx, r14
    add rcx, rax
    lea rcx, [r12+rcx*2]
    ; Convert the eight FP32 lanes to BF16 with scalar lane stores.
    vmovups [rsp+48], ymm0
    xor r8d, r8d
.store0:
    cmp r8d, 8
    jae .store1
    movss xmm0, [rsp+r8*4+48]
    call .fp32_to_bf16
    mov [rcx+r8*2], ax
    inc r8d
    jmp .store0
.store1:
    mov rcx, rbx
    add rcx, 1
    imul rcx, r14
    add rcx, rax
    lea rcx, [r12+rcx*2]
    vmovups [rsp+48], ymm1
    xor r8d, r8d
.store1_loop:
    cmp r8d, 8
    jae .store2
    movss xmm0, [rsp+r8*4+48]
    call .fp32_to_bf16
    mov [rcx+r8*2], ax
    inc r8d
    jmp .store1_loop
.store2:
    mov rcx, rbx
    add rcx, 2
    imul rcx, r14
    add rcx, rax
    lea rcx, [r12+rcx*2]
    vmovups [rsp+48], ymm2
    xor r8d, r8d
.store2_loop:
    cmp r8d, 8
    jae .store3
    movss xmm0, [rsp+r8*4+48]
    call .fp32_to_bf16
    mov [rcx+r8*2], ax
    inc r8d
    jmp .store2_loop
.store3:
    mov rcx, rbx
    add rcx, 3
    imul rcx, r14
    add rcx, rax
    lea rcx, [r12+rcx*2]
    vmovups [rsp+48], ymm3
    xor r8d, r8d
.store3_loop:
    cmp r8d, 8
    jae .next_n
    movss xmm0, [rsp+r8*4+48]
    call .fp32_to_bf16
    mov [rcx+r8*2], ax
    inc r8d
    jmp .store3_loop

.next_n:
    add rax, N_TILE
    jmp .n_loop

.n_tail:
    ; Scalar tail preserves bounds when N is not a multiple of 8.
    xor rdi, rdi
.tail_n_loop:
    cmp rax, r14
    jae .next_m
    xor rdi, rdi
.tail_k_loop:
    cmp rdi, r15
    jae .tail_store
    mov rcx, rbx
    imul rcx, r15
    add rcx, rdi
    mov r10, [rsp+112]
    movzx r8d, byte [r10+rcx]
    call .decode_fp8
    vmovss xmm1, xmm0
    mov rcx, rdi
    imul rcx, r14
    add rcx, rax
    mov r11, [rsp+120]
    movzx r8d, byte [r11+rcx]
    call .decode_fp8
    vmulss xmm0, xmm1, xmm0
    ; C is BF16; decode C to FP32 before accumulation.
    mov rcx, rbx
    imul rcx, r14
    add rcx, rax
    movzx r8d, word [r12+rcx*2]
    call .bf16_to_fp32
    vaddss xmm0, xmm0, xmm1
    call .fp32_to_bf16
    mov [r12+rcx*2], ax
    inc rdi
    jmp .tail_k_loop
.tail_store:
    inc rax
    jmp .tail_n_loop

.next_m:
    add rbx, M_TILE
    jmp .m_loop

.m_tail:
    ; General scalar M tail.
    mov rax, rbx
.tail_m_loop:
    cmp rax, r13
    jae .done
    xor rcx, rcx
.tail_m_n:
    cmp rcx, r14
    jae .tail_m_next
    xor rdi, rdi
.tail_m_k:
    cmp rdi, r15
    jae .tail_m_store
    mov r8, rax
    imul r8, r15
    add r8, rdi
    mov r10, [rsp+112]
    movzx r9d, byte [r10+r8]
    call .decode_fp8
    vmovss xmm1, xmm0
    mov r8, rdi
    imul r8, r14
    add r8, rcx
    mov r11, [rsp+120]
    movzx r9d, byte [r11+r8]
    call .decode_fp8
    vmulss xmm0, xmm1, xmm0
    mov r8, rax
    imul r8, r14
    add r8, rcx
    movzx r9d, word [r12+r8*2]
    call .bf16_to_fp32
    vaddss xmm0, xmm0, xmm1
    call .fp32_to_bf16
    mov [r12+r8*2], ax
    inc rdi
    jmp .tail_m_k
.tail_m_store:
    inc rcx
    jmp .tail_m_n
.tail_m_next:
    inc rax
    jmp .tail_m_loop

; SOURCE PRIMITIVE: atom.global.add
; SEMANTIC: atomic read-modify-write
; TARGET: LOCK XADD primitive
raw_kickdown_atomic_add:
    mov eax, esi
    lock xadd [rdi], eax
    ret

; SOURCE PRIMITIVE: atom.global.or
; SEMANTIC: atomic bitwise OR
; TARGET: LOCK CMPXCHG retry loop
raw_kickdown_atomic_or:
    mov eax, [rdi]
.or_retry:
    mov ecx, eax
    or ecx, esi
    lock cmpxchg [rdi], ecx
    jne .or_retry
    mov eax, ecx
    ret

; SOURCE PRIMITIVE: mbarrier
; SEMANTIC: arrival count transition
; TARGET: LOCK XADD
raw_kickdown_barrier_arrive:
    mov eax, 1
    lock xadd [rdi], eax
    ret

; SOURCE PRIMITIVE: mbarrier
; SEMANTIC: phase/count wait
; TARGET: cache-coherent polling with PAUSE
raw_kickdown_barrier_wait:
.wait:
    mov eax, [rdi]
    cmp eax, esi
    jb .pause
    ret
.pause:
    pause
    jmp .wait

; SOURCE PRIMITIVE: cp.async.bulk
; SEMANTIC: asynchronous bulk transfer
; TARGET: software-prefetch assisted ordinary copy
raw_kickdown_copy64:
    prefetcht0 [rsi]
    prefetcht0 [rsi+32]
    vmovdqu ymm0, [rsi]
    vmovdqu ymm1, [rsi+32]
    vmovdqu [rdi], ymm0
    vmovdqu [rdi+32], ymm1
    ret

; SOURCE PRIMITIVE: prefetch.global
; SEMANTIC: cache preparation
; TARGET: PREFETCHT0
raw_kickdown_prefetch:
    prefetcht0 [rdi]
    prefetcht0 [rdi+64]
    ret

; SOURCE PRIMITIVE: tensormap.replace
; SEMANTIC: descriptor field update
; TARGET: LEA/ADD/IMUL address metadata
raw_kickdown_desc_stride:
    mov rax, rdi
    imul rsi, rdx
    add rax, rsi
    ret

; FP8 E4M3FN decode to scalar FP32.
; Input: R8D or R9D low byte. Output: XMM0.
.decode_fp8:
    mov eax, r8d
    and eax, 0xff
    mov r10d, eax
    and r10d, 0x80
    shr r10d, 7
    mov r11d, eax
    and r11d, 0x7f
    mov ecx, r11d
    and ecx, 0x78
    shr ecx, 3
    mov edx, r11d
    and edx, 7
    test ecx, ecx
    jne .fp8_normal
    test edx, edx
    jz .fp8_zero
    cvtsi2ss xmm0, edx
    mov eax, 0x3a000000
    movd xmm1, eax
    mulss xmm0, xmm1
    jmp .fp8_sign
.fp8_normal:
    mov eax, ecx
    sub eax, 7
    add eax, 127
    shl eax, 23
    shl edx, 20
    or eax, edx
    movd xmm0, eax
.fp8_sign:
    test r10d, r10d
    jz .fp8_ret
    xor eax, eax
    movd xmm1, eax
    subss xmm1, xmm0
    movaps xmm0, xmm1
.fp8_ret:
    ret
.fp8_zero:
    vxorps xmm0, xmm0, xmm0
    ret
.decode_fp8_r9:
    mov r8d, r9d
    jmp .decode_fp8


.bf16_to_fp32:
    shl r8d, 16
    movd xmm0, r8d
    ret

.fp32_to_bf16:
    movd eax, xmm0
    add eax, 0x7fff
    adc eax, 0
    shr eax, 16
    ret

.done:
    vzeroupper
    mov rsp, rbp
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    pop rbp
    ret

SECTION .data
ALIGN 32
fp8_zero:
    times 8 dd 0
SECTION .note.GNU-stack noalloc noexec nowrite progbits

SECTION .text
GLOBAL raw_kickdown_vec_accumulate
raw_kickdown_vec_accumulate:
    ; RDI=A FP32, RSI=B FP32, RDX=out FP32, RCX=count vectors of 8 floats
    vxorps ymm0, ymm0, ymm0
    vxorps ymm1, ymm1, ymm1
    vxorps ymm2, ymm2, ymm2
    vxorps ymm3, ymm3, ymm3
    xor r8d, r8d
.vloop:
    cmp r8, rcx
    jae .vstore
    vmovups ymm4, [rdi+r8*32]
    vmovups ymm5, [rsi+r8*32]
    vmovups ymm6, [rdi+r8*32+32]
    vmovups ymm7, [rsi+r8*32+32]
    vfmadd231ps ymm0, ymm4, ymm5
    vfmadd231ps ymm1, ymm6, ymm7
    vmovups ymm8, [rdi+r8*32+64]
    vmovups ymm9, [rsi+r8*32+64]
    vmovups ymm10, [rdi+r8*32+96]
    vmovups ymm11, [rsi+r8*32+96]
    vfmadd231ps ymm2, ymm8, ymm9
    vfmadd231ps ymm3, ymm10, ymm11
    inc r8
    jmp .vloop
.vstore:
    vmovups [rdx], ymm0
    vmovups [rdx+32], ymm1
    vmovups [rdx+64], ymm2
    vmovups [rdx+96], ymm3
    vzeroupper
    ret

GLOBAL raw_kickdown_reduce_ps
raw_kickdown_reduce_ps:
    ; RDI=input, RSI=output scalar, RDX=count vectors
    vxorps ymm0, ymm0, ymm0
    xor rcx, rcx
.rloop:
    cmp rcx, rdx
    jae .rdone
    vaddps ymm0, ymm0, [rdi+rcx*32]
    inc rcx
    jmp .rloop
.rdone:
    vextractf128 xmm1, ymm0, 1
    vaddps xmm0, xmm0, xmm1
    movhlps xmm1, xmm0
    addps xmm0, xmm1
    pshufd xmm1, xmm0, 1
    addss xmm0, xmm1
    vmovss [rsi], xmm0
    vzeroupper
    ret

GLOBAL raw_kickdown_reduce_pd
raw_kickdown_reduce_pd:
    vxorpd ymm0, ymm0, ymm0
    xor rcx, rcx
.prloop:
    cmp rcx, rdx
    jae .prdone
    vaddpd ymm0, ymm0, [rdi+rcx*32]
    inc rcx
    jmp .prloop
.prdone:
    vextractf128 xmm1, ymm0, 1
    vaddpd xmm0, xmm0, xmm1
    vhaddpd xmm0, xmm0, xmm0
    vmovsd [rsi], xmm0
    vzeroupper
    ret

GLOBAL raw_kickdown_or_u32x8
raw_kickdown_or_u32x8:
    vmovdqu ymm0, [rdi]
    vmovdqu ymm1, [rsi]
    vpor ymm0, ymm0, ymm1
    vmovdqu [rdx], ymm0
    vzeroupper
    ret

GLOBAL raw_kickdown_add_u32x8
raw_kickdown_add_u32x8:
    vmovdqu ymm0, [rdi]
    vpaddd ymm0, ymm0, [rsi]
    vmovdqu [rdx], ymm0
    vzeroupper
    ret

GLOBAL raw_kickdown_copy128
raw_kickdown_copy128:
    prefetcht0 [rsi]
    prefetcht0 [rsi+64]
    vmovdqu ymm0, [rsi]
    vmovdqu ymm1, [rsi+32]
    vmovdqu ymm2, [rsi+64]
    vmovdqu ymm3, [rsi+96]
    vmovdqu [rdi], ymm0
    vmovdqu [rdi+32], ymm1
    vmovdqu [rdi+64], ymm2
    vmovdqu [rdi+96], ymm3
    ret
GLOBAL raw_kickdown_block_0
raw_kickdown_block_0:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_1
raw_kickdown_block_1:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_2
raw_kickdown_block_2:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_3
raw_kickdown_block_3:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_4
raw_kickdown_block_4:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_5
raw_kickdown_block_5:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_6
raw_kickdown_block_6:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_7
raw_kickdown_block_7:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_8
raw_kickdown_block_8:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_9
raw_kickdown_block_9:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_10
raw_kickdown_block_10:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_11
raw_kickdown_block_11:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_12
raw_kickdown_block_12:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_13
raw_kickdown_block_13:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_14
raw_kickdown_block_14:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_15
raw_kickdown_block_15:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_16
raw_kickdown_block_16:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_17
raw_kickdown_block_17:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_18
raw_kickdown_block_18:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_19
raw_kickdown_block_19:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_20
raw_kickdown_block_20:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_21
raw_kickdown_block_21:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_22
raw_kickdown_block_22:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_23
raw_kickdown_block_23:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_24
raw_kickdown_block_24:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_25
raw_kickdown_block_25:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_26
raw_kickdown_block_26:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_27
raw_kickdown_block_27:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_28
raw_kickdown_block_28:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_29
raw_kickdown_block_29:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_30
raw_kickdown_block_30:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_31
raw_kickdown_block_31:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_32
raw_kickdown_block_32:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_33
raw_kickdown_block_33:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_34
raw_kickdown_block_34:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_35
raw_kickdown_block_35:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_36
raw_kickdown_block_36:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_37
raw_kickdown_block_37:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_38
raw_kickdown_block_38:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_39
raw_kickdown_block_39:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_40
raw_kickdown_block_40:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_41
raw_kickdown_block_41:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_42
raw_kickdown_block_42:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_43
raw_kickdown_block_43:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_44
raw_kickdown_block_44:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_45
raw_kickdown_block_45:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_46
raw_kickdown_block_46:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_47
raw_kickdown_block_47:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_48
raw_kickdown_block_48:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_49
raw_kickdown_block_49:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_50
raw_kickdown_block_50:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_51
raw_kickdown_block_51:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_52
raw_kickdown_block_52:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_53
raw_kickdown_block_53:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_54
raw_kickdown_block_54:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_55
raw_kickdown_block_55:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_56
raw_kickdown_block_56:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_57
raw_kickdown_block_57:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_58
raw_kickdown_block_58:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_59
raw_kickdown_block_59:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_60
raw_kickdown_block_60:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_61
raw_kickdown_block_61:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_62
raw_kickdown_block_62:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_63
raw_kickdown_block_63:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_64
raw_kickdown_block_64:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_65
raw_kickdown_block_65:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_66
raw_kickdown_block_66:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_67
raw_kickdown_block_67:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_68
raw_kickdown_block_68:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_69
raw_kickdown_block_69:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_70
raw_kickdown_block_70:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_71
raw_kickdown_block_71:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_72
raw_kickdown_block_72:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_73
raw_kickdown_block_73:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_74
raw_kickdown_block_74:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_75
raw_kickdown_block_75:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_76
raw_kickdown_block_76:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_77
raw_kickdown_block_77:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_78
raw_kickdown_block_78:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
GLOBAL raw_kickdown_block_79
raw_kickdown_block_79:
    vmovups ymm0, [rdi]
    vmovups ymm1, [rsi]
    vmovups ymm2, [rdi+32]
    vmovups ymm3, [rsi+32]
    vmovups ymm4, [rdi+64]
    vmovups ymm5, [rsi+64]
    vmovups ymm6, [rdi+96]
    vmovups ymm7, [rsi+96]
    vfmadd231ps ymm8, ymm0, ymm1
    vfmadd231ps ymm9, ymm2, ymm3
    vfmadd231ps ymm10, ymm4, ymm5
    vfmadd231ps ymm11, ymm6, ymm7
    vaddps ymm12, ymm8, ymm9
    vaddps ymm13, ymm10, ymm11
    vmovups [rdx], ymm12
    vmovups [rdx+32], ymm13
    add rdi, 128
    add rsi, 128
    add rdx, 64
    ret
