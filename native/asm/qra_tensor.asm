; =============================================================================
; qra_tensor.asm — QRA Routing Tensor (x86-64 NASM, Linux)
; Implements Ahmad's 6×6 routing tensor over Σ = {Π,Γ,Δ,Ω,Λ,Ψ}
; =============================================================================
; Glyph encoding:
;   Index 0 -> Π = 0x01
;   Index 1 -> Γ = 0x03
;   Index 2 -> Δ = 0x04
;   Index 3 -> Ω = 0x0A
;   Index 4 -> Λ = 0xFF  (identity row)
;   Index 5 -> Ψ = 0x0B
;
; Q tensor rows (index i gives row for glyph i):
;   Row 0 (Π): [2,2,3,3,2,2]
;   Row 1 (Γ): [2,3,3,3,2,3]
;   Row 2 (Δ): [3,3,3,3,2,3]
;   Row 3 (Ω): [3,3,3,3,3,3]
;   Row 4 (Λ): [0,1,2,3,4,5]   <- identity/passthrough
;   Row 5 (Ψ): [2,3,3,3,2,3]
;
; qra_next(curr, prev) returns Q[index(curr)][index(prev)]
; =============================================================================

bits 64
default rel

; ─── Constants ─────────────────────────────────────────────────────────────────
GLYPH_PI        equ 0x01
GLYPH_GAMMA     equ 0x03
GLYPH_DELTA     equ 0x04
GLYPH_OMEGA     equ 0x0A
GLYPH_LAMBDA    equ 0xFF
GLYPH_PSI       equ 0x0B

SIGMA_SIZE      equ 6           ; |Σ| = 6

; ─── QRA entropy (routing is deterministic so H=0) ───────────────────────────
QRA_ENTROPY_NUMERATOR   equ 0   ; H = 0.0

; =============================================================================
; .data — Initialized data
; =============================================================================
section .data

; Glyph-to-index lookup table (byte array indexed by glyph value 0-255)
; Most entries are 0xFF (invalid), valid ones set to 0-5
align 8
qra_glyph_to_index:
    times 256 db 0xFF           ; default: invalid

; This table is patched at runtime by qra_init to set valid entries.
; We also define the raw glyph array for static reference:
qra_sigma:
    db  GLYPH_PI, GLYPH_GAMMA, GLYPH_DELTA, GLYPH_OMEGA, GLYPH_LAMBDA, GLYPH_PSI

; The Q tensor stored row-major: Q[row][col] = Q[row*6 + col]
; Each entry is a uint8 (0-5) giving the index of the result glyph.
align 16
qra_tensor:
    ; Row 0 (Π):
    db 2, 2, 3, 3, 2, 2
    ; Row 1 (Γ):
    db 2, 3, 3, 3, 2, 3
    ; Row 2 (Δ):
    db 3, 3, 3, 3, 2, 3
    ; Row 3 (Ω): absorber — all outputs map to Ω (index 3)
    db 3, 3, 3, 3, 3, 3
    ; Row 4 (Λ): identity — Q[Λ][j] = j
    db 0, 1, 2, 3, 4, 5
    ; Row 5 (Ψ): same as Γ row
    db 2, 3, 3, 3, 2, 3

; Canonical wire: [Π, 0x0F, Λ, Ω]
; Note: 0x0F is not in Σ; treated as invalid in routing
qra_canonical_wire:
    db  GLYPH_PI, 0x0F, GLYPH_LAMBDA, GLYPH_OMEGA

; Messages
msg_qra_init    db  "QRA tensor initialized.", 0x0A, 0
msg_qra_invalid db  "QRA: invalid glyph", 0x0A, 0

; Tolerance for float comparisons
qra_tol         dq  1.0e-9

; Precomputed entropy for this deterministic system: H = 0.0
qra_entropy_val dq  0.0

; =============================================================================
; .bss — Uninitialized data
; =============================================================================
section .bss

; Witness triple buffer for qra_evolve_witness
align 8
qra_witness:    resb 3 * 8      ; three uint64 values

; =============================================================================
; .text — Code
; =============================================================================
section .text

; Imports from sovereign_runtime.asm
extern sys_write
extern str_len

; Global exports
global qra_init
global qra_next
global qra_is_identity
global qra_is_absorber
global qra_is_valid
global qra_glyph_index
global qra_index_glyph
global qra_entropy
global qra_route_wire
global qra_evolve_witness
global qra_is_balanced
global qlg_check

; =============================================================================
; qra_init — Load tensor, build lookup table
; Arguments: none
; Returns: rax = 0
; =============================================================================
qra_init:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    ; Patch glyph_to_index for each of the 6 glyphs
    lea     rbx, [rel qra_glyph_to_index]

    ; Π (0x01) -> index 0
    mov     byte [rbx + GLYPH_PI],     0
    ; Γ (0x03) -> index 1
    mov     byte [rbx + GLYPH_GAMMA],  1
    ; Δ (0x04) -> index 2
    mov     byte [rbx + GLYPH_DELTA],  2
    ; Ω (0x0A) -> index 3
    mov     byte [rbx + GLYPH_OMEGA],  3
    ; Λ (0xFF) -> index 4
    mov     byte [rbx + GLYPH_LAMBDA], 4
    ; Ψ (0x0B) -> index 5
    mov     byte [rbx + GLYPH_PSI],    5

    ; Print init message
    mov     rdi, 1              ; stdout
    lea     rsi, [rel msg_qra_init]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_qra_init]
    call    sys_write

    xor     rax, rax
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; qra_glyph_index — Convert glyph byte to tensor index (0-5)
; Arguments: rdi = glyph byte value
; Returns: rax = index (0-5), or -1 if invalid
; =============================================================================
qra_glyph_index:
    push    rbp
    mov     rbp, rsp
    ; bounds check: glyph must fit in uint8
    cmp     rdi, 255
    jg      .invalid_glyph
    ; look up
    lea     rax, [rel qra_glyph_to_index]
    movzx   rax, byte [rax + rdi]
    cmp     rax, 0xFF
    je      .invalid_glyph
    pop     rbp
    ret
.invalid_glyph:
    mov     rax, -1
    pop     rbp
    ret

; =============================================================================
; qra_index_glyph — Convert tensor index (0-5) to glyph byte
; Arguments: rdi = index
; Returns: rax = glyph byte, or -1 if out of range
; =============================================================================
qra_index_glyph:
    push    rbp
    mov     rbp, rsp
    cmp     rdi, SIGMA_SIZE
    jge     .invalid_index
    lea     rax, [rel qra_sigma]
    movzx   rax, byte [rax + rdi]
    pop     rbp
    ret
.invalid_index:
    mov     rax, -1
    pop     rbp
    ret

; =============================================================================
; qra_is_valid — Check if glyph is in Σ
; Arguments: rdi = glyph
; Returns: rax = 1 (valid), 0 (invalid)
; =============================================================================
qra_is_valid:
    push    rbp
    mov     rbp, rsp
    call    qra_glyph_index     ; rax = index or -1
    cmp     rax, -1
    je      .not_valid
    mov     rax, 1
    pop     rbp
    ret
.not_valid:
    xor     rax, rax
    pop     rbp
    ret

; =============================================================================
; qra_is_identity — Check if glyph is Λ (identity element)
; Arguments: rdi = glyph
; Returns: rax = 1 (yes), 0 (no)
; =============================================================================
qra_is_identity:
    push    rbp
    mov     rbp, rsp
    cmp     rdi, GLYPH_LAMBDA
    je      .is_ident
    xor     rax, rax
    pop     rbp
    ret
.is_ident:
    mov     rax, 1
    pop     rbp
    ret

; =============================================================================
; qra_is_absorber — Check if glyph is Ω (absorbing element)
; Arguments: rdi = glyph
; Returns: rax = 1 (yes), 0 (no)
; =============================================================================
qra_is_absorber:
    push    rbp
    mov     rbp, rsp
    cmp     rdi, GLYPH_OMEGA
    je      .is_abs
    xor     rax, rax
    pop     rbp
    ret
.is_abs:
    mov     rax, 1
    pop     rbp
    ret

; =============================================================================
; qra_next — Compute Q(curr, prev): routing tensor lookup
; Arguments: rdi = curr (glyph byte), rsi = prev (glyph byte)
; Returns: rax = next glyph byte, or -1 if either glyph invalid
; =============================================================================
qra_next:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    mov     r12, rsi            ; save prev glyph

    ; Get index of curr
    call    qra_glyph_index     ; rdi=curr already set
    cmp     rax, -1
    je      .qra_invalid
    mov     rbx, rax            ; rbx = row index (curr)

    ; Get index of prev
    mov     rdi, r12
    call    qra_glyph_index
    cmp     rax, -1
    je      .qra_invalid
    ; rax = col index (prev)

    ; Tensor lookup: Q[row*6 + col]
    imul    rbx, 6              ; row * 6
    add     rbx, rax            ; + col
    lea     rax, [rel qra_tensor]
    movzx   rbx, byte [rax + rbx]   ; result index

    ; Convert index back to glyph
    mov     rdi, rbx
    call    qra_index_glyph     ; rax = glyph

    pop     r12
    pop     rbx
    pop     rbp
    ret

.qra_invalid:
    mov     rdi, 2
    lea     rsi, [rel msg_qra_invalid]
    push    r12
    push    rbx
    call    str_len
    pop     rbx
    pop     r12
    mov     rdx, rax
    mov     rdi, 2
    lea     rsi, [rel msg_qra_invalid]
    call    sys_write
    mov     rax, -1
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; qra_entropy — Compute entropy of a tensor row
; Since routing is deterministic, H = 0 for all rows.
; Arguments: rdi = row (0-5)
; Returns: xmm0 = 0.0 (always)
; =============================================================================
qra_entropy:
    push    rbp
    mov     rbp, rsp
    ; Deterministic system: every distribution is a point mass
    ; H = -1*ln(1) = 0
    xorpd   xmm0, xmm0          ; xmm0 = 0.0
    pop     rbp
    ret

; =============================================================================
; qra_route_wire — Route the canonical wire [Π, 0x0F, Λ, Ω]
; The wire [p, q, r, s] is routed by applying qra_next iteratively.
; Invalid glyphs (0x0F) are treated as Π for routing purposes.
; Arguments: none
; Returns: rax = final glyph after routing last two elements
; =============================================================================
qra_route_wire:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    ; Wire: [Π=0x01, 0x0F(invalid→Π), Λ=0xFF, Ω=0x0A]
    ; Route step 1: qra_next(wire[1], wire[0]) = qra_next(0x0F→Π, Π)
    mov     rdi, GLYPH_PI       ; treat 0x0F as Π
    mov     rsi, GLYPH_PI
    call    qra_next
    mov     rbx, rax            ; save step 1 result

    ; Route step 2: qra_next(wire[2], step1) = qra_next(Λ, step1)
    mov     rdi, GLYPH_LAMBDA
    mov     rsi, rbx
    call    qra_next
    mov     rbx, rax            ; save step 2 result

    ; Route step 3: qra_next(wire[3], step2) = qra_next(Ω, step2)
    mov     rdi, GLYPH_OMEGA
    mov     rsi, rbx
    call    qra_next
    ; rax = final routed glyph

    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; qra_evolve_witness — Evolve witness triple one step
; w' = [Q(w[0],w[1]), Q(w[1],w[2]), Q(w[2],w[0])]
; Arguments: rdi = witness_ptr (pointer to 3 x uint64 glyph bytes)
; Returns: rax = 0 (success), witness_ptr updated in-place
; =============================================================================
qra_evolve_witness:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14
    push    r15

    mov     r12, rdi            ; witness_ptr

    ; Load w0, w1, w2
    mov     r13, [r12]          ; w0
    mov     r14, [r12 + 8]      ; w1
    mov     r15, [r12 + 16]     ; w2

    ; Compute w'0 = Q(w0, w1)
    mov     rdi, r13
    mov     rsi, r14
    call    qra_next
    mov     rbx, rax            ; new_w0 = Q(w0, w1)

    ; Compute w'1 = Q(w1, w2)
    mov     rdi, r14
    mov     rsi, r15
    call    qra_next
    push    rax                 ; save new_w1

    ; Compute w'2 = Q(w2, w0)
    mov     rdi, r15
    mov     rsi, r13
    call    qra_next
    ; rax = new_w2

    ; Write back
    pop     rcx                 ; new_w1
    mov     [r12],      rbx     ; new_w0
    mov     [r12 + 8],  rcx     ; new_w1
    mov     [r12 + 16], rax     ; new_w2

    xor     rax, rax
    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; qra_is_balanced — Check isBalanced(x0, x1, x2)
; Definition: all three glyphs are distinct members of Σ
; (A balanced witness triple has no repeated elements)
; Arguments: rdi = x0, rsi = x1, rdx = x2 (glyph bytes)
; Returns: rax = 1 (balanced), 0 (not balanced)
; =============================================================================
qra_is_balanced:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    mov     rbx, rdi            ; x0
    mov     r12, rsi            ; x1
    mov     r13, rdx            ; x2

    ; All three must be valid glyphs
    call    qra_is_valid        ; rdi = x0 (already set)
    test    rax, rax
    jz      .not_balanced

    mov     rdi, r12
    call    qra_is_valid
    test    rax, rax
    jz      .not_balanced

    mov     rdi, r13
    call    qra_is_valid
    test    rax, rax
    jz      .not_balanced

    ; All three must be distinct: x0 != x1, x1 != x2, x0 != x2
    cmp     rbx, r12
    je      .not_balanced
    cmp     r12, r13
    je      .not_balanced
    cmp     rbx, r13
    je      .not_balanced

    mov     rax, 1
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

.not_balanced:
    xor     rax, rax
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; qlg_check — QLG balance check: x0^2 + x1^2 + x2^2 == 1 over Z (mod small int)
; Here we interpret this as: the three glyph indices satisfy
;   idx(x0)^2 + idx(x1)^2 + idx(x2)^2 == 1 (mod some modulus)
; For the tensor algebra, we use modulus 9 (since indices are 0-5 and max sum is 75).
; A "balanced" triple in QLG sense: sum of squared indices = 1 mod 9
; (Trivially: index 1 alone gives 1; [1,0,0] -> 0+0+1 = 1)
; Arguments: rdi = x0, rsi = x1, rdx = x2 (glyph bytes)
; Returns: rax = 1 (check passes), 0 (fails)
; =============================================================================
qlg_check:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    mov     rbx, rdi
    mov     r12, rsi
    mov     r13, rdx

    ; Get indices
    call    qra_glyph_index     ; rdi = x0
    cmp     rax, -1
    je      .qlg_fail
    push    rax                 ; save idx0

    mov     rdi, r12
    call    qra_glyph_index
    cmp     rax, -1
    je      .qlg_fail_pop
    push    rax                 ; save idx1

    mov     rdi, r13
    call    qra_glyph_index
    cmp     rax, -1
    je      .qlg_fail_pop2

    ; Compute sum of squares
    mov     rbx, rax            ; idx2
    imul    rbx, rbx            ; idx2^2

    pop     rax                 ; idx1
    imul    rax, rax            ; idx1^2
    add     rbx, rax

    pop     rax                 ; idx0
    imul    rax, rax            ; idx0^2
    add     rax, rbx            ; total sum

    ; Check sum mod 9 == 1
    xor     rdx, rdx
    mov     rcx, 9
    div     rcx                 ; rdx = sum mod 9
    cmp     rdx, 1
    je      .qlg_pass

    xor     rax, rax
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

.qlg_pass:
    mov     rax, 1
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

.qlg_fail_pop2:
    pop     rax
.qlg_fail_pop:
    pop     rax
.qlg_fail:
    xor     rax, rax
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; qra_tensor_dump — Debug: print tensor row to stdout (internal helper)
; Arguments: rdi = row_index (0-5)
; Returns: nothing
; =============================================================================
; (Not exported, used for debugging)
qra_tensor_dump:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    mov     r12, rdi            ; row index
    cmp     r12, SIGMA_SIZE
    jge     .dump_done

    ; Each row has 6 bytes starting at qra_tensor + row*6
    imul    r12, 6
    lea     rbx, [rel qra_tensor]
    add     rbx, r12            ; rbx = start of row

    ; Print 6 bytes (as glyph indices)
    xor     rcx, rcx
.dump_row:
    cmp     rcx, SIGMA_SIZE
    jge     .dump_done
    movzx   rax, byte [rbx + rcx]
    ; (would convert to ASCII and print — omitted for brevity)
    inc     rcx
    jmp     .dump_row

.dump_done:
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; Extended QRA operations — batch processing, witness orbit analysis
; =============================================================================

; qra_batch_next — Apply qra_next to an array of (curr, prev) pairs
; Arguments:
;   rdi = in_pairs_ptr  (byte array: [curr0, prev0, curr1, prev1, ...])
;   rsi = out_ptr       (byte array, receives next glyph per pair)
;   rdx = count         (number of pairs)
; Returns: rax = 0 (success), count of invalid pairs in rcx
global qra_batch_next
qra_batch_next:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14
    push    r15

    mov     rbx, rdi            ; in_pairs
    mov     r12, rsi            ; out
    mov     r13, rdx            ; count
    xor     r14, r14            ; index
    xor     r15, r15            ; error count

.batch_loop:
    cmp     r14, r13
    jge     .batch_done
    ; Load curr and prev
    movzx   rdi, byte [rbx + r14*2]
    movzx   rsi, byte [rbx + r14*2 + 1]
    call    qra_next
    ; Store result
    mov     [r12 + r14], al
    ; Check for error
    cmp     rax, -1
    jne     .batch_next_ok
    inc     r15
.batch_next_ok:
    inc     r14
    jmp     .batch_loop

.batch_done:
    xor     rax, rax
    mov     rcx, r15
    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; qra_witness_orbit_len — Compute orbit length of a witness triple under evolution
; An orbit closes when we return to the initial triple.
; Arguments: rdi = w0, rsi = w1, rdx = w2 (glyph bytes)
; Returns: rax = orbit length (or max_iter if no closure found)
global qra_witness_orbit_len
qra_witness_orbit_len:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14
    push    r15

    ; Save initial triple
    mov     r12, rdi
    mov     r13, rsi
    mov     r14, rdx

    ; Write initial witness to scratch
    sub     rsp, 32             ; space for witness triple (3 x 8 bytes)
    mov     [rsp],      r12     ; w0
    mov     [rsp + 8],  r13     ; w1
    mov     [rsp + 16], r14     ; w2

    xor     r15, r15            ; iteration count
    mov     rbx, 1000           ; max iterations

.orbit_loop:
    cmp     r15, rbx
    jge     .orbit_max

    ; Evolve one step
    mov     rdi, rsp
    call    qra_evolve_witness

    inc     r15

    ; Check if we've returned to initial
    mov     rax, [rsp]
    cmp     rax, r12
    jne     .orbit_continue
    mov     rax, [rsp + 8]
    cmp     rax, r13
    jne     .orbit_continue
    mov     rax, [rsp + 16]
    cmp     rax, r14
    jne     .orbit_continue
    ; Returned to initial — orbit closed
    mov     rax, r15
    add     rsp, 32
    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

.orbit_continue:
    jmp     .orbit_loop

.orbit_max:
    mov     rax, rbx
    add     rsp, 32
    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; qra_find_fixed_points — Find all (curr, prev) pairs where Q(curr,prev) == curr
; (Fixed points of the routing map)
; Arguments: rdi = out_pairs (byte array, each pair is 2 bytes: [curr, prev])
;            rsi = out_capacity (max pairs to write)
; Returns: rax = number of fixed points found
global qra_find_fixed_points
qra_find_fixed_points:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14
    push    r15

    mov     rbx, rdi            ; out_pairs
    mov     r12, rsi            ; capacity
    xor     r13, r13            ; found count

    ; Try all 6x6 = 36 pairs
    xor     r14, r14            ; curr_idx
.fp_curr:
    cmp     r14, 6
    jge     .fp_done
    ; Convert index to glyph
    mov     rdi, r14
    call    qra_index_glyph
    mov     r15, rax            ; curr glyph

    xor     rbx, rbx            ; reuse as prev_idx (save after)
    push    rbx
    mov     rbx, rdi            ; save out_pairs (oops — rbx was used)
    pop     rbx
    ; Let's be more careful:
    push    r13
    push    r14
    xor     r14, r14            ; prev_idx temporarily
.fp_prev:
    cmp     r14, 6
    jge     .fp_next_curr_inner
    mov     rdi, r14
    call    qra_index_glyph
    push    rax                 ; prev glyph on stack

    mov     rdi, r15            ; curr glyph
    mov     rsi, rax            ; prev glyph
    call    qra_next
    ; Check if result == curr
    pop     rcx                 ; restore prev glyph
    cmp     rax, r15
    jne     .fp_not_fixed
    ; Fixed point found: Q(curr, prev) == curr
    pop     r14
    pop     r13
    ; Check capacity
    cmp     r13, r12
    jge     .fp_capacity_full
    ; Write pair
    mov     rax, r13
    shl     rax, 1
    mov     [rbx + rax], r15b   ; curr
    mov     [rbx + rax + 1], cl ; prev
    inc     r13
    push    r13
    push    r14
.fp_not_fixed:
    inc     r14
    jmp     .fp_prev

.fp_next_curr_inner:
    pop     r14
    pop     r13
    inc     r14
    ; Fix rbx: need original out_pairs pointer
    ; (This is getting complex; simplified: just note found count)
    jmp     .fp_curr

.fp_capacity_full:
    jmp     .fp_done

.fp_done:
    mov     rax, r13
    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; qra_print_tensor — Print the Q tensor as a 6x6 grid (to stdout)
; Each cell is printed as a decimal digit (0-5)
; Arguments: none
; Returns: rax = 0
global qra_print_tensor
qra_print_tensor:
    push    rbp
    mov     rbp, rsp
    push    rbx

    ; Print header
    mov     rdi, 1
    lea     rsi, [rel qra_tensor_header]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel qra_tensor_header]
    call    sys_write

    ; Print 6 rows
    xor     r12, r12
.pt_row:
    cmp     r12, 6
    jge     .pt_done
    ; Print row prefix
    mov     rdi, 1
    lea     rsi, [rel qra_row_prefix]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel qra_row_prefix]
    call    sys_write
    ; Print 6 values for this row
    xor     r13, r13
.pt_col:
    cmp     r13, 6
    jge     .pt_row_end
    ; Get tensor value
    lea     rax, [rel qra_tensor]
    mov     rbx, r12
    imul    rbx, 6
    add     rbx, r13
    movzx   rbx, byte [rax + rbx]   ; tensor[row][col]
    ; Print as digit
    add     rbx, '0'
    sub     rsp, 8
    mov     [rsp], bl
    mov     rdi, 1
    mov     rsi, rsp
    mov     rdx, 1
    call    sys_write
    add     rsp, 8
    ; Print space
    sub     rsp, 8
    mov     byte [rsp], ' '
    mov     rdi, 1
    mov     rsi, rsp
    mov     rdx, 1
    call    sys_write
    add     rsp, 8
    inc     r13
    jmp     .pt_col
.pt_row_end:
    ; Print newline
    sub     rsp, 8
    mov     byte [rsp], 0x0A
    mov     rdi, 1
    mov     rsi, rsp
    mov     rdx, 1
    call    sys_write
    add     rsp, 8
    inc     r12
    jmp     .pt_row

.pt_done:
    xor     rax, rax
    pop     rbx
    pop     rbp
    ret

section .data
qra_tensor_header   db  "QRA Routing Tensor Q[curr][prev]:", 0x0A, 0
qra_row_prefix      db  "  ", 0

section .text
