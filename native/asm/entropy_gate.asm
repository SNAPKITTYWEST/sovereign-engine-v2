; =============================================================================
; entropy_gate.asm — Entropy Gate (x86-64 NASM, Linux)
; Validates that agent routing decisions satisfy H <= 0.20 nats.
; H = -Σ p_i * ln(p_i)  (Shannon entropy in nats)
;
; Implementation strategy:
;   - Weights are passed as float64 array (routing probabilities summing to 1)
;   - Entropy is computed using a precomputed ln lookup table (256 entries)
;   - Each weight is quantized to uint8 (0-255 representing 0.0-1.0)
;   - ln_table[i] approximates ln(i/256) using fixed-point integer arithmetic
; =============================================================================

bits 64
default rel

; ─── Entropy threshold ────────────────────────────────────────────────────────
; H <= 0.20 nats
; In IEEE 754 double: 0.20 = 3FC999999999999A (hex)
ENTROPY_THRESHOLD_HEX   equ 0x3FC999999999999A

; ─── Fixed-point log scaling ─────────────────────────────────────────────────
; We store ln(x) * 2^16 as int32 for the table
; For x in [1/256, 1]: ln ranges from ln(1/256) = -ln(256) ≈ -5.545 to 0
; Scaled by 2^16 = 65536: range is -363456 to 0
LN_SCALE        equ 65536

; ─── Invariant bit positions ─────────────────────────────────────────────────
INV_ENTROPY     equ 0           ; bit 0: entropy violation
INV_TRUST       equ 1           ; bit 1: active-not-trusted violation
INV_TOTAL_BITS  equ 2           ; number of invariant checks

; =============================================================================
; .data
; =============================================================================
section .data

msg_entropy_init    db  "Entropy gate initialized.", 0x0A, 0
msg_entropy_ok_msg  db  "ENTROPY GATE: H <= 0.20 (pass)", 0x0A, 0
msg_entropy_reject  db  "ENTROPY GATE: H > 0.20 (REJECT)", 0x0A, 0
msg_trust_ok        db  "TRUST CHECK: all active agents trusted (pass)", 0x0A, 0
msg_trust_fail      db  "TRUST CHECK: untrusted active agent detected (REJECT)", 0x0A, 0
msg_inv_all_ok      db  "INVARIANTS: all checks passed", 0x0A, 0
msg_inv_fail        db  "INVARIANTS: violations detected", 0x0A, 0

; Entropy threshold as float64
align 8
entropy_threshold   dq  0x3FC999999999999A    ; 0.20 (double precision)
entropy_zero        dq  0.0
entropy_one         dq  1.0
entropy_256f        dq  256.0
ln_scale_f          dq  65536.0

; Ln lookup table: 256 entries of float64
; ln_table[i] = ln(i/256) for i = 1..255, ln_table[0] = -Inf (unused)
; We compute these at init time (see entropy_init).
; Placeholder space (will be filled by entropy_init):
align 16
ln_table            times 256 dq 0.0

; Precomputed negative ln values for quantized probabilities
; neg_xlnx_table[i] = -(i/256) * ln(i/256) for i in [1,255]
; Used for: H = Σ neg_xlnx_table[quantize(p_i)]
align 16
neg_xlnx_table      times 256 dq 0.0

; =============================================================================
; .bss
; =============================================================================
section .bss

align 8
entropy_gate_state:
    .initialized    resb 1
    resb 7
    .check_count    resq 1
    .reject_count   resq 1
    .pass_count     resq 1

; =============================================================================
; .text
; =============================================================================
section .text

extern sys_write
extern str_len
extern popcount64

global entropy_init
global entropy_compute
global entropy_check
global entropy_quantize
global entropy_from_mask
global invariant_check_trusted
global invariant_check_entropy
global invariant_check_all
global entropy_gate_init

; =============================================================================
; entropy_gate_init — Initialize the entropy gate subsystem
; Arguments: none
; Returns: rax = 0
; =============================================================================
entropy_gate_init:
    push    rbp
    mov     rbp, rsp
    call    entropy_init
    mov     rdi, 1
    lea     rsi, [rel msg_entropy_init]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_entropy_init]
    call    sys_write
    xor     rax, rax
    pop     rbp
    ret

; =============================================================================
; entropy_init — Precompute ln table and -x*ln(x) table (256 entries each)
; Uses a simple Taylor-series/Halley's-method approximation for ln in SSE2.
; Arguments: none
; Returns: rax = 0
; =============================================================================
entropy_init:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    ; Set ln_table[0] = -very large (for p=0, treated as 0 contribution)
    lea     rbx, [rel ln_table]
    mov     rax, 0xFFF0000000000000  ; -Inf IEEE 754 double
    mov     [rbx], rax              ; ln_table[0] = -Inf

    ; For i = 1..255: ln_table[i] = ln(i / 256.0)
    ; We compute ln using: ln(x) = 2 * atanh((x-1)/(x+1)) for x near 1
    ; Or simpler: use ln(x) = (x-1) - (x-1)^2/2 + (x-1)^3/3 - ...
    ; For accuracy across [1/256, 1], use: ln(i/256) = ln(i) - ln(256)
    ; And ln(i) for i in [1,255] via the standard SSE2 approximation.
    ;
    ; We'll use: ln(i/256) = (i - 256) * (1/256) - ((i-256)/256)^2 / 2 + ...
    ; This is the Taylor series for ln(1+u) where u = (i-256)/256.
    ; For accuracy we keep 5 terms. Actually for i far from 256, this diverges.
    ;
    ; Better: use ln(i/256) = ln(i) - ln(256)
    ; ln(256) = 8 * ln(2) ≈ 5.545177444...
    ; And compute ln(i) via repeated halving + Taylor near 1.
    ;
    ; For simplicity in assembly, we use the following approximation:
    ; ln(x) ≈ (x-1)*(1 + (x-1)*(-0.5 + (x-1)*(1/3 + (x-1)*(-1/4 + (x-1)*1/5))))
    ; which is accurate for x in [0.5, 2].
    ; For x outside this range, we normalize.
    ;
    ; Here: x = i/256, so for i < 128 we have x < 0.5.
    ; We use: for i in [1,255]: ln(i/256) = ln(i) - 8*ln(2)
    ; and compute ln(i) by: if i >= 128, use Taylor; otherwise recurse via
    ; ln(i) = ln(2i) - ln(2).
    ;
    ; Implementation: just use the built-in `fyl2x` x87 instruction pair.
    ; fyl2x computes y * log2(x). With y = ln(2), we get ln(x).

    ; We'll use FLDLN2 + FYL2X for accurate ln computation.
    mov     rcx, 1              ; i = 1
.ln_loop:
    cmp     rcx, 256
    jge     .ln_done

    ; Compute i/256.0 on x87 stack
    fild    qword [rsp - 16]    ; push i... but rcx is in register
    ; Store rcx temporarily
    mov     [rsp - 8], rcx
    fild    qword [rsp - 8]     ; ST(0) = i
    mov     qword [rsp - 8], 256
    fidiv   qword [rsp - 8]     ; ST(0) = i/256

    ; Compute ln(i/256) = log2(i/256) * ln(2)
    fldln2                      ; ST(0)=ln(2), ST(1)=i/256
    fxch    st1                 ; ST(0)=i/256, ST(1)=ln(2)
    fyl2x                       ; ST(0) = ln(2) * log2(i/256) = ln(i/256)

    ; Store result in ln_table[i]
    lea     rax, [rel ln_table]
    mov     rdx, rcx
    shl     rdx, 3              ; i * 8
    fstp    qword [rax + rdx]   ; store and pop

    inc     rcx
    jmp     .ln_loop

.ln_done:
    ; Compute neg_xlnx_table[i] = -(i/256.0) * ln(i/256.0) for i=1..255
    ; neg_xlnx_table[0] = 0 (0 * ln(0) = 0 by convention)
    lea     rbx, [rel neg_xlnx_table]
    mov     qword [rbx], 0      ; entry 0 = 0.0

    mov     rcx, 1
.xlnx_loop:
    cmp     rcx, 256
    jge     .xlnx_done

    ; Load ln_table[i]
    lea     rax, [rel ln_table]
    mov     rdx, rcx
    shl     rdx, 3
    movsd   xmm0, [rax + rdx]   ; ln(i/256)

    ; Compute p = i/256.0
    mov     [rsp - 8], rcx
    fild    qword [rsp - 8]
    mov     qword [rsp - 8], 256
    fidiv   qword [rsp - 8]
    fstp    qword [rsp - 8]
    movsd   xmm1, [rsp - 8]     ; p = i/256

    ; neg_xlnx = -p * ln(p)
    mulsd   xmm0, xmm1          ; p * ln(p)
    ; negate: xmm0 = -(p * ln(p))
    xorpd   xmm2, xmm2
    subsd   xmm2, xmm0          ; xmm2 = -(p * ln(p))

    ; Store
    lea     rbx, [rel neg_xlnx_table]
    mov     rdx, rcx
    shl     rdx, 3
    movsd   [rbx + rdx], xmm2

    inc     rcx
    jmp     .xlnx_loop

.xlnx_done:
    mov     byte [rel entropy_gate_state.initialized], 1
    xor     rax, rax
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; entropy_quantize — Quantize a float64 probability to uint8 (0-255)
; Arguments: xmm0 = weight (0.0 to 1.0)
; Returns: rax = quantized uint8 (0-255)
; Clamps to [0,255], rounds to nearest.
; =============================================================================
entropy_quantize:
    push    rbp
    mov     rbp, rsp

    ; Multiply by 256
    movsd   xmm1, [rel entropy_256f]
    mulsd   xmm0, xmm1          ; xmm0 = w * 256

    ; Round to nearest integer
    cvtsd2si rax, xmm0          ; rax = round(w * 256)

    ; Clamp to [0, 255]
    test    rax, rax
    jns     .qpos
    xor     rax, rax
    jmp     .qdone
.qpos:
    cmp     rax, 255
    jle     .qdone
    mov     rax, 255
.qdone:
    pop     rbp
    ret

; =============================================================================
; entropy_compute — Compute Shannon entropy H = -Σ p_i * ln(p_i) in nats
; Arguments: rdi = weights_ptr (f64 array), rsi = count (number of weights)
; Returns: xmm0 = H (entropy in nats)
; Note: weights should sum to 1.0 (normalized probability distribution)
; =============================================================================
entropy_compute:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    mov     rbx, rdi            ; weights_ptr
    mov     r12, rsi            ; count

    xorpd   xmm4, xmm4          ; H accumulator = 0.0

    xor     r13, r13            ; index
.entropy_loop:
    cmp     r13, r12
    jge     .entropy_done

    ; Load weight
    movsd   xmm0, [rbx + r13 * 8]

    ; Skip if weight is 0 (or very small)
    xorpd   xmm1, xmm1
    ucomisd xmm0, xmm1
    je      .entropy_next

    ; Quantize to index
    call    entropy_quantize    ; rax = q (0-255)

    ; If q == 0, contribution is 0 (treat as 0 * -inf = 0)
    test    rax, rax
    jz      .entropy_next

    ; Lookup -p*ln(p) from table
    lea     rcx, [rel neg_xlnx_table]
    movsd   xmm1, [rcx + rax * 8]  ; neg_xlnx_table[q]

    ; Add to accumulator
    addsd   xmm4, xmm1

.entropy_next:
    inc     r13
    jmp     .entropy_loop

.entropy_done:
    movsd   xmm0, xmm4          ; return H

    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; entropy_check — Check if H <= 0.20 nats
; Arguments: xmm0 = H (entropy value)
; Returns: rax = 1 (ok, H <= 0.20), 0 (reject, H > 0.20)
; =============================================================================
entropy_check:
    push    rbp
    mov     rbp, rsp
    push    rbx

    inc     qword [rel entropy_gate_state.check_count]

    ; Compare H to threshold
    movsd   xmm1, [rel entropy_threshold]   ; 0.20
    ucomisd xmm0, xmm1
    ja      .entropy_reject     ; H > 0.20 -> reject

    ; Pass
    inc     qword [rel entropy_gate_state.pass_count]
    mov     rdi, 1
    lea     rsi, [rel msg_entropy_ok_msg]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_entropy_ok_msg]
    call    sys_write
    mov     rax, 1
    pop     rbx
    pop     rbp
    ret

.entropy_reject:
    inc     qword [rel entropy_gate_state.reject_count]
    mov     rdi, 2
    lea     rsi, [rel msg_entropy_reject]
    call    str_len
    mov     rdx, rax
    mov     rdi, 2
    lea     rsi, [rel msg_entropy_reject]
    call    sys_write
    xor     rax, rax
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; entropy_from_mask — Compute entropy of a 64-bit activation mask
; Treats each set bit as an equal-weight expert: p_i = 1/k for k active experts.
; H = ln(k) (uniform distribution over k outcomes)
; Arguments: rdi = mask (uint64)
; Returns: xmm0 = H
; =============================================================================
entropy_from_mask:
    push    rbp
    mov     rbp, rsp
    push    rbx

    ; Count set bits
    popcnt  rax, rdi            ; k = popcount(mask)

    ; Handle edge cases
    test    rax, rax
    jz      .mask_zero

    cmp     rax, 1
    je      .mask_one           ; H = 0 for deterministic (k=1)

    ; H = ln(k) for uniform distribution over k outcomes
    ; Use x87 FYL2X: ln(k) = log2(k) * ln(2)
    mov     [rsp - 8], rax
    fildq   qword [rsp - 8]     ; ST(0) = k (as float)
    fldln2                      ; ST(0) = ln(2), ST(1) = k
    fxch    st1                 ; ST(0) = k, ST(1) = ln(2)
    fyl2x                       ; ST(0) = ln(2) * log2(k) = ln(k)
    fstp    qword [rsp - 8]     ; store and pop
    movsd   xmm0, [rsp - 8]
    jmp     .mask_done

.mask_zero:
    xorpd   xmm0, xmm0          ; H = 0 for empty mask
    jmp     .mask_done

.mask_one:
    xorpd   xmm0, xmm0          ; H = 0 for single active expert

.mask_done:
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; invariant_check_trusted — Check: active(I) => trusted(I)
; For all bits set in active_flags, the corresponding bit must be set in trusted_flags.
; Arguments: rdi = active_flags (uint64), rsi = trusted_flags (uint64)
; Returns: rax = 1 (all active are trusted), 0 (violation found)
; =============================================================================
invariant_check_trusted:
    push    rbp
    mov     rbp, rsp
    push    rbx

    ; Check: (active AND NOT(trusted)) == 0
    ; If any bit is active but not trusted, this is a violation.
    mov     rbx, rsi            ; trusted_flags
    not     rbx                 ; ~trusted_flags
    and     rbx, rdi            ; active & ~trusted

    test    rbx, rbx
    jnz     .trust_fail

    ; All active agents are trusted
    mov     rdi, 1
    lea     rsi, [rel msg_trust_ok]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_trust_ok]
    call    sys_write
    mov     rax, 1
    pop     rbx
    pop     rbp
    ret

.trust_fail:
    mov     rdi, 2
    lea     rsi, [rel msg_trust_fail]
    call    str_len
    mov     rdx, rax
    mov     rdi, 2
    lea     rsi, [rel msg_trust_fail]
    call    sys_write
    xor     rax, rax
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; invariant_check_entropy — Check entropy(I) <= 0.20 for all active agents
; Computes entropy from the active mask and validates threshold.
; Arguments: rdi = active_flags (uint64)
; Returns: rax = 1 (ok), 0 (violation)
; =============================================================================
invariant_check_entropy:
    push    rbp
    mov     rbp, rsp
    push    rbx

    mov     rbx, rdi

    ; Compute entropy from mask
    call    entropy_from_mask   ; xmm0 = H = ln(k)

    ; Check H <= 0.20
    call    entropy_check       ; rax = 1 (ok) or 0 (reject)

    pop     rbx
    pop     rbp
    ret

; =============================================================================
; invariant_check_all — Run all invariant checks, return bitmask of violations
; Checks:
;   Bit 0 (INV_ENTROPY): entropy(active_flags) <= 0.20
;   Bit 1 (INV_TRUST):   active(I) => trusted(I)
; Arguments:
;   rdi = active_flags (uint64)
;   rsi = trusted_flags (uint64)
; Returns: rax = bitmask of violations (0 = all ok)
; =============================================================================
invariant_check_all:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    mov     rbx, rdi            ; active_flags
    mov     r12, rsi            ; trusted_flags
    xor     r13, r13            ; violations bitmask

    ; Check INV_ENTROPY
    mov     rdi, rbx
    call    invariant_check_entropy
    test    rax, rax
    jnz     .entropy_inv_ok
    or      r13, (1 << INV_ENTROPY)
.entropy_inv_ok:

    ; Check INV_TRUST
    mov     rdi, rbx
    mov     rsi, r12
    call    invariant_check_trusted
    test    rax, rax
    jnz     .trust_inv_ok
    or      r13, (1 << INV_TRUST)
.trust_inv_ok:

    ; Report overall result
    test    r13, r13
    jnz     .inv_failed

    mov     rdi, 1
    lea     rsi, [rel msg_inv_all_ok]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_inv_all_ok]
    call    sys_write
    jmp     .inv_done

.inv_failed:
    mov     rdi, 2
    lea     rsi, [rel msg_inv_fail]
    call    str_len
    mov     rdx, rax
    mov     rdi, 2
    lea     rsi, [rel msg_inv_fail]
    call    sys_write

.inv_done:
    mov     rax, r13            ; return violation bitmask

    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret
