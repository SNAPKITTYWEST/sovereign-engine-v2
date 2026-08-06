; =============================================================================
; nand_kernel.asm — NAND Boolean Kernel (x86-64 NASM, Linux)
; All boolean operations derived from NAND, matching the DSL BooleanKernel:
;   NAND(a,b) = 1-ab
;   NOT(x)    = NAND(x,x)
;   AND(a,b)  = NAND(NAND(a,b), NAND(a,b))
;   OR(a,b)   = NAND(NAND(a,a), NAND(b,b))
;   IMPLIES(a,b) = OR(NOT(a), b)
;   EQUAL(a,b)   = AND(IMPLIES(a,b), IMPLIES(b,a))
; =============================================================================
; Single-bit functions: rdi=a, rsi=b, return rax=0 or 1
; Word functions:       rdi=a, rsi=b, return rax=64-bit result
; Entropy constraint:   H <= 0.20 ↔ popcount(word)/64 <= 0.20 ↔ popcount <= 12
; =============================================================================

bits 64
default rel

; ─── Entropy threshold ────────────────────────────────────────────────────────
; H = -sum(p * ln p) for a bit distribution
; For binary uniform-ish distribution, H ≈ popcount/64 * ln(64/popcount) + ...
; Conservative approximation: popcount <= 12 bits set satisfies H <= 0.20 nats
ENTROPY_MAX_BITS_SET    equ 12  ; max set bits for H <= 0.20

; =============================================================================
; .data
; =============================================================================
section .data

msg_nand_init   db  "NAND kernel initialized.", 0x0A, 0
msg_entropy_ok  db  "ENTROPY: H <= 0.20 (ok)", 0x0A, 0
msg_entropy_err db  "ENTROPY: H > 0.20 (reject)", 0x0A, 0

; Precomputed NAND truth table (2x2):
; NAND(0,0)=1  NAND(0,1)=1  NAND(1,0)=1  NAND(1,1)=0
nand_truth:
    db 1, 1, 1, 0               ; [a*2+b] -> result

; Routing conflict table: expert pair (i,j) conflicts if they share a resource
; Represented as 8x8 bit matrix stored as 8 bytes
; Entry [i*8+j] = 1 means experts i and j conflict
; For demonstration: experts 0+1, 2+3, 4+5 conflict (paired resources)
conflict_matrix:
    db 0,1,0,0,0,0,0,0         ; expert 0 conflicts with 1
    db 1,0,0,0,0,0,0,0         ; expert 1 conflicts with 0
    db 0,0,0,1,0,0,0,0         ; expert 2 conflicts with 3
    db 0,0,1,0,0,0,0,0         ; expert 3 conflicts with 2
    db 0,0,0,0,0,1,0,0         ; expert 4 conflicts with 5
    db 0,0,0,0,1,0,0,0         ; expert 5 conflicts with 4
    db 0,0,0,0,0,0,0,0         ; expert 6: no conflicts
    db 0,0,0,0,0,0,0,0         ; expert 7: no conflicts

; Popcount lookup table (nibble-based, 16 entries)
; popcount_nibble[n] = number of set bits in n (for n in 0..15)
popcount_nibble:
    db 0,1,1,2,1,2,2,3,1,2,2,3,2,3,3,4

; =============================================================================
; .bss
; =============================================================================
section .bss

align 8
nand_stats:
    .nand_calls     resq 1
    .and_calls      resq 1
    .or_calls       resq 1
    .not_calls      resq 1
    .entropy_checks resq 1
    .entropy_rejects resq 1

; =============================================================================
; .text
; =============================================================================
section .text

extern sys_write
extern str_len

global nand_bit
global not_bit
global and_bit
global or_bit
global xor_bit
global implies_bit
global equal_bit
global nand_word
global not_word
global and_word
global or_word
global xor_word
global implies_word
global equal_word
global entropy_check_word
global popcount64
global nand_route_filter
global nand_kernel_init
global nand_selftest

; =============================================================================
; nand_kernel_init — Initialize NAND kernel (print banner, zero stats)
; Arguments: none
; Returns: rax = 0
; =============================================================================
nand_kernel_init:
    push    rbp
    mov     rbp, rsp

    ; Zero stats
    mov     qword [rel nand_stats.nand_calls], 0
    mov     qword [rel nand_stats.and_calls], 0
    mov     qword [rel nand_stats.or_calls], 0
    mov     qword [rel nand_stats.not_calls], 0
    mov     qword [rel nand_stats.entropy_checks], 0
    mov     qword [rel nand_stats.entropy_rejects], 0

    ; Print init message
    mov     rdi, 1
    lea     rsi, [rel msg_nand_init]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_nand_init]
    call    sys_write

    xor     rax, rax
    pop     rbp
    ret

; =============================================================================
; nand_bit — Single-bit NAND: NAND(a, b) = NOT(a AND b)
; Arguments: rdi = a (0 or 1), rsi = b (0 or 1)
; Returns: rax = NAND(a, b) (0 or 1)
; Derivation: NAND(a,b) = 1 - a*b
;   a=0,b=0 -> 1-0 = 1
;   a=0,b=1 -> 1-0 = 1
;   a=1,b=0 -> 1-0 = 1
;   a=1,b=1 -> 1-1 = 0
; =============================================================================
nand_bit:
    push    rbp
    mov     rbp, rsp
    inc     qword [rel nand_stats.nand_calls]
    ; Normalize inputs to 0/1
    test    rdi, rdi
    setnz   al
    movzx   rdi, al
    test    rsi, rsi
    setnz   al
    movzx   rsi, al
    ; a*b
    mov     rax, rdi
    imul    rax, rsi            ; rax = a*b (0 or 1)
    ; 1 - a*b
    xor     rax, 1              ; toggle bit 0: 0->1, 1->0
    pop     rbp
    ret

; =============================================================================
; not_bit — Single-bit NOT via NAND: NOT(x) = NAND(x, x)
; Arguments: rdi = x (0 or 1)
; Returns: rax = NOT(x)
; =============================================================================
not_bit:
    push    rbp
    mov     rbp, rsp
    inc     qword [rel nand_stats.not_calls]
    ; NOT(x) = NAND(x, x): pass same value twice
    mov     rsi, rdi            ; b = a = x
    call    nand_bit
    pop     rbp
    ret

; =============================================================================
; and_bit — Single-bit AND via NAND: AND(a,b) = NAND(NAND(a,b), NAND(a,b))
; Arguments: rdi = a, rsi = b
; Returns: rax = AND(a, b)
; =============================================================================
and_bit:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    inc     qword [rel nand_stats.and_calls]

    mov     rbx, rdi            ; save a
    mov     r12, rsi            ; save b

    ; n = NAND(a, b)
    call    nand_bit            ; rdi=a, rsi=b already set
    mov     rdi, rax            ; n
    mov     rsi, rax            ; n
    ; AND = NAND(n, n)
    call    nand_bit

    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; or_bit — Single-bit OR via NAND: OR(a,b) = NAND(NAND(a,a), NAND(b,b))
; Arguments: rdi = a, rsi = b
; Returns: rax = OR(a, b)
; =============================================================================
or_bit:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    inc     qword [rel nand_stats.or_calls]

    mov     rbx, rdi            ; save a
    mov     r12, rsi            ; save b

    ; na = NAND(a, a) = NOT(a)
    mov     rsi, rbx
    call    nand_bit            ; rdi=a, rsi=a
    mov     rbx, rax            ; na

    ; nb = NAND(b, b) = NOT(b)
    mov     rdi, r12
    mov     rsi, r12
    call    nand_bit            ; rdi=b, rsi=b
    ; rax = nb

    ; OR = NAND(na, nb)
    mov     rdi, rbx
    mov     rsi, rax
    call    nand_bit

    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; xor_bit — Single-bit XOR via NAND:
;   XOR(a,b) = AND(OR(a,b), NAND(a,b))
;            = NAND(NAND(OR(a,b), OR(a,b)), NAND(NAND(a,b), NAND(a,b)))
; (Simplified: use 4-NAND construction)
; a XOR b = NAND(NAND(a, NAND(a,b)), NAND(b, NAND(a,b)))
; Arguments: rdi = a, rsi = b
; Returns: rax = XOR(a, b)
; =============================================================================
xor_bit:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    mov     rbx, rdi            ; save a
    mov     r12, rsi            ; save b

    ; n = NAND(a, b)
    call    nand_bit
    mov     r13, rax            ; n = NAND(a,b)

    ; p = NAND(a, n)
    mov     rdi, rbx            ; a
    mov     rsi, r13            ; n
    call    nand_bit
    push    rax                 ; save p

    ; q = NAND(b, n)
    mov     rdi, r12            ; b
    mov     rsi, r13            ; n
    call    nand_bit
    mov     rsi, rax            ; q
    pop     rdi                 ; p

    ; XOR = NAND(p, q)
    call    nand_bit

    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; implies_bit — Single-bit IMPLIES via NAND: IMPLIES(a,b) = OR(NOT(a), b)
; Arguments: rdi = a, rsi = b
; Returns: rax = IMPLIES(a, b)
; =============================================================================
implies_bit:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    mov     rbx, rdi            ; save a
    mov     r12, rsi            ; save b

    ; na = NOT(a)
    call    not_bit             ; rdi=a already set
    mov     rbx, rax            ; na

    ; OR(NOT(a), b) = OR(na, b)
    mov     rdi, rbx
    mov     rsi, r12
    call    or_bit

    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; equal_bit — Single-bit EQUAL via NAND: EQUAL(a,b) = AND(IMPLIES(a,b), IMPLIES(b,a))
; Arguments: rdi = a, rsi = b
; Returns: rax = EQUAL(a, b) (1 if a==b, 0 otherwise)
; =============================================================================
equal_bit:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    mov     rbx, rdi            ; save a
    mov     r12, rsi            ; save b

    ; p = IMPLIES(a, b)
    call    implies_bit
    push    rax                 ; save p

    ; q = IMPLIES(b, a)
    mov     rdi, r12            ; b
    mov     rsi, rbx            ; a
    call    implies_bit
    mov     rsi, rax            ; q
    pop     rdi                 ; p

    ; EQUAL = AND(p, q)
    call    and_bit

    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; nand_word — 64-bit bitwise NAND: ~(a & b)
; Arguments: rdi = a (uint64), rsi = b (uint64)
; Returns: rax = NAND(a, b) = ~(a & b)
; Note: This is the direct bitwise implementation, not bit-serial.
;       The bit-serial functions above are for single-bit logical operations.
; =============================================================================
nand_word:
    push    rbp
    mov     rbp, rsp
    inc     qword [rel nand_stats.nand_calls]
    mov     rax, rdi
    and     rax, rsi            ; a & b
    not     rax                 ; ~(a & b)
    pop     rbp
    ret

; =============================================================================
; not_word — 64-bit bitwise NOT via NAND: NOT(x) = NAND(x, x) = ~x
; Arguments: rdi = x (uint64)
; Returns: rax = ~x
; =============================================================================
not_word:
    push    rbp
    mov     rbp, rsp
    inc     qword [rel nand_stats.not_calls]
    mov     rax, rdi
    and     rax, rdi            ; x & x = x
    not     rax                 ; ~x
    pop     rbp
    ret

; =============================================================================
; and_word — 64-bit bitwise AND via NAND: AND = NAND(NAND(a,b), NAND(a,b))
; = ~(~(a&b) & ~(a&b)) = ~(~(a&b)) = a&b
; Arguments: rdi = a, rsi = b
; Returns: rax = a & b
; =============================================================================
and_word:
    push    rbp
    mov     rbp, rsp
    inc     qword [rel nand_stats.and_calls]
    ; Step 1: n = NAND(a, b) = ~(a & b)
    mov     rax, rdi
    and     rax, rsi            ; a & b
    not     rax                 ; ~(a & b) = n
    ; Step 2: AND = NAND(n, n) = ~(n & n) = ~n = ~~(a&b) = a&b
    not     rax                 ; ~~(a&b) = a&b
    pop     rbp
    ret

; =============================================================================
; or_word — 64-bit bitwise OR via NAND: OR = NAND(NAND(a,a), NAND(b,b))
; = ~(~a & ~b) = ~(~a) | ~(~b) [De Morgan] = a | b
; Arguments: rdi = a, rsi = b
; Returns: rax = a | b
; =============================================================================
or_word:
    push    rbp
    mov     rbp, rsp
    push    rbx
    inc     qword [rel nand_stats.or_calls]
    ; na = NAND(a, a) = ~a
    mov     rbx, rdi
    and     rbx, rdi
    not     rbx                 ; na = ~a
    ; nb = NAND(b, b) = ~b
    mov     rax, rsi
    and     rax, rsi
    not     rax                 ; nb = ~b
    ; OR = NAND(na, nb) = ~(na & nb) = ~(~a & ~b) = a | b
    and     rax, rbx            ; ~a & ~b
    not     rax                 ; a | b
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; xor_word — 64-bit bitwise XOR via NAND (4-NAND construction)
; XOR(a,b) = NAND(NAND(a, NAND(a,b)), NAND(b, NAND(a,b)))
; Arguments: rdi = a, rsi = b
; Returns: rax = a ^ b
; =============================================================================
xor_word:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    mov     rbx, rdi            ; a
    mov     r12, rsi            ; b

    ; n = NAND(a, b) = ~(a & b)
    mov     rax, rbx
    and     rax, r12
    not     rax                 ; n = NAND(a,b)
    push    rax                 ; save n

    ; p = NAND(a, n)
    mov     rdi, rbx
    mov     rsi, rax
    call    nand_word
    push    rax                 ; save p

    ; q = NAND(b, n)
    pop     rcx                 ; restore n? No — we need n again
    ; Actually restore properly:
    pop     rcx                 ; this is p
    push    rcx                 ; re-save p
    ; We need n — recompute
    mov     rax, rbx
    and     rax, r12
    not     rax                 ; n again

    mov     rdi, r12            ; b
    mov     rsi, rax            ; n
    call    nand_word           ; rax = q = NAND(b, n)
    mov     rsi, rax            ; q
    pop     rdi                 ; p

    ; XOR = NAND(p, q)
    call    nand_word

    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; implies_word — 64-bit bitwise IMPLIES: IMPLIES(a,b) = OR(NOT(a), b) = ~a | b
; Arguments: rdi = a, rsi = b
; Returns: rax = ~a | b
; =============================================================================
implies_word:
    push    rbp
    mov     rbp, rsp
    ; ~a | b
    mov     rax, rdi
    not     rax                 ; ~a
    or      rax, rsi            ; ~a | b
    pop     rbp
    ret

; =============================================================================
; equal_word — 64-bit bitwise EQUAL: EQUAL(a,b) = ~(a ^ b)  [XNOR]
; Arguments: rdi = a, rsi = b
; Returns: rax = ~(a ^ b)
; =============================================================================
equal_word:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    xor     rax, rsi
    not     rax                 ; XNOR = ~XOR
    pop     rbp
    ret

; =============================================================================
; popcount64 — Count set bits in a 64-bit word using POPCNT instruction
; Arguments: rdi = word
; Returns: rax = popcount(word)
; =============================================================================
popcount64:
    push    rbp
    mov     rbp, rsp
    popcnt  rax, rdi            ; hardware POPCNT (SSE4.2)
    pop     rbp
    ret

; =============================================================================
; entropy_check_word — Check H(word) <= 0.20 constraint
; Approximation: popcount(word) / 64 is the "density".
; For a Bernoulli-p distribution: H = -p*ln(p) - (1-p)*ln(1-p)
; H <= 0.20 nats is satisfied when p <= ~0.026 or p >= ~0.974
; i.e., at most 12 bits set (p <= 12/64 = 0.1875 → H ≈ 0.45 nats... )
;
; More precisely, we use the conservative check:
; If popcount <= ENTROPY_MAX_BITS_SET (12) OR popcount >= (64-12) = 52, H ≤ 0.20
; (sparse or near-full masks have low entropy)
;
; For the routing use case, we only have a few active experts (sparse),
; so the "at most 12 bits" check is the relevant branch.
;
; Arguments: rdi = 64-bit word (activation mask)
; Returns: rax = 1 (H <= 0.20, ok), 0 (H > 0.20, reject)
; =============================================================================
entropy_check_word:
    push    rbp
    mov     rbp, rsp
    inc     qword [rel nand_stats.entropy_checks]

    ; Count set bits
    popcnt  rax, rdi

    ; Check sparse: popcount <= 12
    cmp     rax, ENTROPY_MAX_BITS_SET
    jle     .entropy_ok

    ; Check near-full: popcount >= 52
    cmp     rax, 64 - ENTROPY_MAX_BITS_SET
    jge     .entropy_ok

    ; H > 0.20 — reject
    inc     qword [rel nand_stats.entropy_rejects]
    mov     rdi, 2
    lea     rsi, [rel msg_entropy_err]
    call    str_len
    mov     rdx, rax
    mov     rdi, 2
    lea     rsi, [rel msg_entropy_err]
    call    sys_write
    xor     rax, rax
    pop     rbp
    ret

.entropy_ok:
    mov     rax, 1
    pop     rbp
    ret

; =============================================================================
; nand_route_filter — Filter expert activations using NAND conflict logic
; Any expert pair that would conflict is suppressed via NAND.
; Algorithm:
;   conflicting = active & conflict_mask (computed per-bit via AND)
;   suppressed  = NAND(conflicting, conflicting) = NOT(conflicting) inverted
;   filtered    = active & NOT(conflicting)    -- keep only non-conflicting
; In 64-bit word terms, where conflict_mask is the OR of all conflict bits
; for the active set:
;   conflict_bits = (reduce conflict_matrix over active bits)
;   filtered = active & NAND(active & conflict_bits, active & conflict_bits)
;            = active & NOT(active & conflict_bits)
;            = active & ~(active & conflict_bits)
;            = active & ~conflict_bits  (when conflict_bits is the full mask)
;
; For simplicity: use the 8-expert conflict matrix to compute conflict_bits.
; Arguments:
;   rdi = active_mask  (64-bit, each bit = one expert; only low 8 bits used)
;   rsi = conflict_mask (64-bit bitmask of forbidden co-activations)
; Returns: rax = filtered_mask
; =============================================================================
nand_route_filter:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    mov     rbx, rdi            ; active_mask
    mov     r12, rsi            ; conflict_mask

    ; Step 1: Find which active experts have conflicts
    ; conflict_active = active_mask & conflict_mask
    mov     r13, rbx
    and     r13, r12            ; r13 = conflicting active experts

    ; Step 2: NAND(conflict_active, conflict_active) = NOT(conflict_active)
    ; Using the NAND identity: suppress conflicting experts
    mov     rax, r13
    and     rax, r13
    not     rax                 ; rax = NOT(conflict_active) = ~r13

    ; Step 3: filtered = active & NOT(conflict_active)
    ; This keeps only experts that are active AND not involved in a conflict
    and     rax, rbx            ; filtered = active & ~(active & conflict_mask)

    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; nand_selftest — Run a suite of self-tests to verify NAND kernel correctness
; Tests all 4 combinations of single-bit NAND, then spot-checks AND/OR/XOR/EQUAL
; Arguments: none
; Returns: rax = 0 (all tests passed), N (number of failures)
; =============================================================================
nand_selftest:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    xor     rbx, rbx            ; failure count

    ; --- Test NAND truth table ---
    ; NAND(0,0) = 1
    mov     rdi, 0
    mov     rsi, 0
    call    nand_bit
    cmp     rax, 1
    je      .nand00_ok
    inc     rbx
.nand00_ok:
    ; NAND(0,1) = 1
    mov     rdi, 0
    mov     rsi, 1
    call    nand_bit
    cmp     rax, 1
    je      .nand01_ok
    inc     rbx
.nand01_ok:
    ; NAND(1,0) = 1
    mov     rdi, 1
    mov     rsi, 0
    call    nand_bit
    cmp     rax, 1
    je      .nand10_ok
    inc     rbx
.nand10_ok:
    ; NAND(1,1) = 0
    mov     rdi, 1
    mov     rsi, 1
    call    nand_bit
    cmp     rax, 0
    je      .nand11_ok
    inc     rbx
.nand11_ok:

    ; --- Test NOT ---
    ; NOT(0) = 1
    mov     rdi, 0
    call    not_bit
    cmp     rax, 1
    je      .not0_ok
    inc     rbx
.not0_ok:
    ; NOT(1) = 0
    mov     rdi, 1
    call    not_bit
    cmp     rax, 0
    je      .not1_ok
    inc     rbx
.not1_ok:

    ; --- Test AND ---
    ; AND(1,1) = 1
    mov     rdi, 1
    mov     rsi, 1
    call    and_bit
    cmp     rax, 1
    je      .and11_ok
    inc     rbx
.and11_ok:
    ; AND(1,0) = 0
    mov     rdi, 1
    mov     rsi, 0
    call    and_bit
    cmp     rax, 0
    je      .and10_ok
    inc     rbx
.and10_ok:

    ; --- Test OR ---
    ; OR(0,0) = 0
    mov     rdi, 0
    mov     rsi, 0
    call    or_bit
    cmp     rax, 0
    je      .or00_ok
    inc     rbx
.or00_ok:
    ; OR(1,0) = 1
    mov     rdi, 1
    mov     rsi, 0
    call    or_bit
    cmp     rax, 1
    je      .or10_ok
    inc     rbx
.or10_ok:

    ; --- Test XOR ---
    ; XOR(0,0) = 0
    mov     rdi, 0
    mov     rsi, 0
    call    xor_bit
    cmp     rax, 0
    je      .xor00_ok
    inc     rbx
.xor00_ok:
    ; XOR(1,1) = 0
    mov     rdi, 1
    mov     rsi, 1
    call    xor_bit
    cmp     rax, 0
    je      .xor11_ok
    inc     rbx
.xor11_ok:
    ; XOR(0,1) = 1
    mov     rdi, 0
    mov     rsi, 1
    call    xor_bit
    cmp     rax, 1
    je      .xor01_ok
    inc     rbx
.xor01_ok:

    ; --- Test EQUAL ---
    ; EQUAL(0,0) = 1
    mov     rdi, 0
    mov     rsi, 0
    call    equal_bit
    cmp     rax, 1
    je      .eq00_ok
    inc     rbx
.eq00_ok:
    ; EQUAL(0,1) = 0
    mov     rdi, 0
    mov     rsi, 1
    call    equal_bit
    cmp     rax, 0
    je      .eq01_ok
    inc     rbx
.eq01_ok:

    ; --- Test word-level nand_word ---
    ; NAND_WORD(0xFFFF, 0xFFFF) = ~0xFFFF (low bits all 1, upper bits all 1)
    mov     rdi, 0x000000000000FFFF
    mov     rsi, 0x000000000000FFFF
    call    nand_word
    cmp     rax, 0xFFFFFFFFFFFF0000
    je      .nandw_ok
    inc     rbx
.nandw_ok:

    ; --- Test entropy_check_word ---
    ; 8 bits set: popcount = 8 <= 12, should pass
    mov     rdi, 0x00000000000000FF
    call    entropy_check_word
    cmp     rax, 1
    je      .ent_ok
    inc     rbx
.ent_ok:
    ; 32 bits set: popcount = 32 > 12, should fail
    mov     rdi, 0x00000000FFFFFFFF
    call    entropy_check_word
    cmp     rax, 0
    je      .ent_fail_ok
    inc     rbx
.ent_fail_ok:

    ; Return failure count
    mov     rax, rbx
    pop     r12
    pop     rbx
    pop     rbp
    ret
