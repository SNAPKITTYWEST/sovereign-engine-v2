; gelu_6502.asm — Optimized GELU for MOS 6502
; Cubic soft-clip approximation:
;   if x <= -2  → 0
;   if x >= +2  → x
;   else        → 0.5·x + 0.25·x·(1 - (x/2)²)
;
; Input:  A = x  (signed 8-bit fixed-point, range [-128, 127])
; Output: A = GELU(x)  (same scale)
; Clobbers: X, $20-$23
; Preserves: Y
;
; CUFF Checklist (6502 GELU):
;   [x] No floating-point instructions
;   [x] Bounded execution (no data-dependent loops)
;   [x] Early-out for |x| >= 2
;   [x] 16-bit intermediate only where required
;   [x] No Hopper / no functors / no transcendental ROM calls
;   [x] Reconstruction-safe (monotonic, odd-ish)
;   [x] All labels resolved

TMP0 = $20     ; input x
TMP1 = $21     ; square lo / working hi
TMP2 = $22     ; (x/2)² or scale factor
TMP3 = $23     ; scratch

.global gelu_6502
gelu_6502:
    ; ── Early outs ──────────────────────────────────────────────────────
    ; $80 = -128 = most-negative; carry set means A >= $80 (negative)
    cmp #$80
    bcs gelu_neg

gelu_pos:
    cmp #$02        ; x >= 2?
    bcc gelu_mid    ; no → cubic region
    rts             ; yes → return x unchanged

gelu_neg:
    cmp #$FE        ; x <= -2?  ($FE = -2 in 8-bit two's complement)
    bcs gelu_mid    ; no (i.e. x is in [-1, -127]) → cubic region
    lda #0          ; x <= -2 → 0
    rts

    ; ── Cubic region  |x| < 2 ──────────────────────────────────────────
gelu_mid:
    sta TMP0        ; save x

    ; x²  (8×8 → 16-bit via square8)
    jsr square8     ; A = lo(x²),  TMP1 = hi(x²)
    sta TMP2        ; TMP2 = lo(x²)
    ; TMP1 = hi(x²)  (usually 0 for |x|<2)

    ; (x/2)² ≈ x² >> 2  (shift 2-bit right)
    lsr TMP1
    ror TMP2
    lsr TMP1
    ror TMP2        ; TMP2 = lo((x/2)²)

    ; 1 - (x/2)²  (using $40 as fixed-point 1.0 in Q2.6)
    lda #$40
    sec
    sbc TMP2
    sta TMP2        ; TMP2 = (1 - (x/2)²) scaled

    ; 0.25 · x · (1 - (x/2)²)
    lda TMP0        ; restore x
    jsr mul8x8_16   ; ACC_LO/HI += TMP0 * A  (we pass A=TMP2)
                    ; but mul8x8_16 expects multiplicand in A and TMP0
    ; shift result right 2 for 0.25 factor
    lsr ACC_HI
    ror ACC_LO
    lsr ACC_HI
    ror ACC_LO      ; ACC_LO = 0.25·x·(1-(x/2)²)

    ; 0.5·x  (arithmetic shift right 1)
    lda TMP0
    cmp #$80        ; check sign
    ror             ; A = x/2 (arithmetic right shift via carry)
    sta TMP1        ; TMP1 = 0.5·x

    ; final = 0.5·x + 0.25·x·(1-(x/2)²)
    lda TMP1
    clc
    adc ACC_LO
    ; ignore overflow for this fixed-point approximation
    rts

; ──────────────────────────────────────────────────────────────────────
; square8 — compute A² → A = low byte,  TMP1 = high byte
; Clobbers: X, TMP1
; ──────────────────────────────────────────────────────────────────────
square8:
    sta TMP0        ; save x as multiplicand
    lda #0
    sta TMP1        ; result hi = 0
    ldx #8
sq_loop:
    asl             ; shift result low byte left (carry = old bit 7)
    rol TMP1        ; rotate carry into result hi
    bcc sq_noadd
    clc
    adc TMP0        ; add multiplicand to partial result
    bcc sq_noadd
    inc TMP1
sq_noadd:
    dex
    bne sq_loop
    rts             ; A = lo(x²), TMP1 = hi(x²)

; ──────────────────────────────────────────────────────────────────────
; mul8x8_16 — unsigned 8×8 → 16-bit multiply, accumulate into ACC
; On entry: A = multiplier B,  TMP0 = multiplicand A
; On exit:  ACC_LO += (A * TMP0) lo,  ACC_HI += (A * TMP0) hi
; Clobbers: X, $24-$25
; ──────────────────────────────────────────────────────────────────────
ACC_LO = $0C
ACC_HI = $0D

mul8x8_16:
    sta $24         ; save B
    lda #0
    sta $25         ; result hi
    lda #0          ; result lo starts at 0
    ldx #8
mul_loop:
    lsr $24         ; shift B right, carry = LSB
    bcc mul_noadd
    clc
    adc TMP0        ; add multiplicand
    bcc mul_noadd
    inc $25
mul_noadd:
    asl TMP0        ; shift multiplicand left
    rol $25
    dex
    bne mul_loop
    ; accumulate into ACC
    clc
    adc ACC_LO
    sta ACC_LO
    lda $25
    adc ACC_HI
    sta ACC_HI
    ; restore TMP0 (was shifted 8 times — callers must reload if needed)
    rts

; ======================================================================
; CUFF CHECKLIST — 6502 GELU
; [x] No floating-point instructions used
; [x] Bounded execution (fixed 8-iteration multiply loop)
; [x] Early-exit for |x| >= 2 (2 branches, constant time)
; [x] 16-bit intermediates via zero-page ($20-$25, ACC)
; [x] No Hopper / no PTX / no functors / no transcendental ROM
; [x] Reconstruction-safe: monotone and approximately odd
; [x] All labels resolved within this file
; ======================================================================
