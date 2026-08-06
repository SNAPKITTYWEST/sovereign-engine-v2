; =============================================================================
; jordan_blocks.asm — Jordan Algebra Operations (x86-64 NASM, SSE2/AVX2)
; Implements SpinFactor operations from jordan_moe.py in assembly.
; =============================================================================
; SpinFactor element: (alpha: f64, v: f64[6])
; Memory layout (56 bytes per element):
;   offset 0:   alpha   (8 bytes, f64)
;   offset 8:   v[0]    (8 bytes, f64)
;   offset 16:  v[1]    (8 bytes, f64)
;   offset 24:  v[2]    (8 bytes, f64)
;   offset 32:  v[3]    (8 bytes, f64)
;   offset 40:  v[4]    (8 bytes, f64)
;   offset 48:  v[5]    (8 bytes, f64)
; =============================================================================
; Jordan product: (α,v) ∘ (β,w) = (αβ + v·w, αw + βv)
; Eigenvalues:    λ± = α ± ‖v‖
; Spectral gap:   λ+ - λ- = 2‖v‖
; =============================================================================

bits 64
default rel

; ─── Element layout constants ─────────────────────────────────────────────────
ELEM_ALPHA      equ 0           ; offset of alpha (f64)
ELEM_V0         equ 8           ; offset of v[0]  (f64)
ELEM_V1         equ 16
ELEM_V2         equ 24
ELEM_V3         equ 32
ELEM_V4         equ 40
ELEM_V5         equ 48
ELEM_SIZE       equ 56          ; total bytes per element

; ─── Convergence constants ────────────────────────────────────────────────────
MAX_ITER_DEFAULT    equ 1000    ; default max iterations for fixed-point solve
ALIGN_BOUNDARY      equ 16      ; SSE2 alignment for loads/stores

; =============================================================================
; .data
; =============================================================================
section .data

msg_jordan_init db  "Jordan algebra kernel initialized.", 0x0A, 0
msg_jordan_conv db  "Jordan: fixed-point converged.", 0x0A, 0
msg_jordan_fail db  "Jordan: fixed-point did not converge.", 0x0A, 0
msg_idempotent  db  "Jordan: element is idempotent.", 0x0A, 0

; Floating-point constants (64-bit)
align 16
f64_zero        dq  0.0
f64_one         dq  1.0
f64_two         dq  2.0
f64_half        dq  0.5
f64_tol_default dq  1.0e-12    ; default convergence tolerance

; Sign-mask for fabs via andpd (clears sign bit)
align 16
f64_abs_mask    dq  0x7FFFFFFFFFFFFFFF, 0x7FFFFFFFFFFFFFFF

; =============================================================================
; .bss
; =============================================================================
section .bss

align 16
jordan_tmp_a    resb ELEM_SIZE  ; temp element A
jordan_tmp_b    resb ELEM_SIZE  ; temp element B
jordan_tmp_c    resb ELEM_SIZE  ; temp element C (result)

; =============================================================================
; .text
; =============================================================================
section .text

extern sys_write
extern str_len

global jordan_init_element
global jordan_set_scalar
global jordan_set_vector
global jordan_product
global jordan_dot_product
global jordan_scale_vector
global jordan_add_vectors
global jordan_norm
global jordan_normalize
global jordan_square
global jordan_is_idempotent
global jordan_eigenvalue_lo
global jordan_eigenvalue_hi
global jordan_spectral_gap
global jordan_fixed_point_iter
global jordan_fixed_point_solve
global jordan_kernel_init

; =============================================================================
; jordan_kernel_init — Print banner
; Arguments: none
; Returns: rax = 0
; =============================================================================
jordan_kernel_init:
    push    rbp
    mov     rbp, rsp
    mov     rdi, 1
    lea     rsi, [rel msg_jordan_init]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_jordan_init]
    call    sys_write
    xor     rax, rax
    pop     rbp
    ret

; =============================================================================
; jordan_init_element — Zero-initialize a SpinFactor element
; Arguments: rdi = ptr (pointer to 56-byte element)
; Returns: rax = 0
; =============================================================================
jordan_init_element:
    push    rbp
    mov     rbp, rsp
    ; Zero 56 bytes = 7 qwords
    mov     qword [rdi],        0
    mov     qword [rdi + 8],    0
    mov     qword [rdi + 16],   0
    mov     qword [rdi + 24],   0
    mov     qword [rdi + 32],   0
    mov     qword [rdi + 40],   0
    mov     qword [rdi + 48],   0
    xor     rax, rax
    pop     rbp
    ret

; =============================================================================
; jordan_set_scalar — Set the alpha component of a SpinFactor element
; Arguments: rdi = ptr, xmm0 = alpha (f64)
; Returns: rax = 0
; =============================================================================
jordan_set_scalar:
    push    rbp
    mov     rbp, rsp
    movsd   [rdi + ELEM_ALPHA], xmm0   ; store alpha
    xor     rax, rax
    pop     rbp
    ret

; =============================================================================
; jordan_set_vector — Copy a vector into the v component of an element
; Arguments: rdi = elem_ptr, rsi = vec_ptr (f64 array), rdx = dim (1-6)
; Returns: rax = 0
; =============================================================================
jordan_set_vector:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    mov     rbx, rdi            ; elem_ptr
    mov     r12, rsi            ; vec_ptr
    mov     r13, rdx            ; dim

    ; Clamp dim to 6
    cmp     r13, 6
    jle     .dim_ok
    mov     r13, 6
.dim_ok:
    ; Copy min(dim, 6) f64 values
    xor     rcx, rcx
.setvec_loop:
    cmp     rcx, r13
    jge     .setvec_done
    ; Load from vec_ptr[rcx]
    movsd   xmm0, [r12 + rcx * 8]
    ; Store to elem.v[rcx] = elem + 8 + rcx*8
    lea     rax, [rbx + 8]
    movsd   [rax + rcx * 8], xmm0
    inc     rcx
    jmp     .setvec_loop

.setvec_done:
    xor     rax, rax
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; jordan_dot_product — Compute dot product of two f64 vectors
; Arguments: rdi = v_ptr (f64*), rsi = w_ptr (f64*), rdx = dim
; Returns: xmm0 = dot(v, w)
; =============================================================================
jordan_dot_product:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    mov     rbx, rdi            ; v_ptr
    mov     r12, rsi            ; w_ptr

    ; Clamp dim to 6
    cmp     rdx, 6
    jle     .dot_dim_ok
    mov     rdx, 6
.dot_dim_ok:
    xorpd   xmm0, xmm0          ; accumulator = 0.0
    xor     rcx, rcx
.dot_loop:
    cmp     rcx, rdx
    jge     .dot_done
    movsd   xmm1, [rbx + rcx * 8]  ; v[i]
    movsd   xmm2, [r12 + rcx * 8]  ; w[i]
    mulsd   xmm1, xmm2              ; v[i] * w[i]
    addsd   xmm0, xmm1              ; accumulate
    inc     rcx
    jmp     .dot_loop
.dot_done:
    ; xmm0 = dot(v, w)
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; jordan_product — Compute the Jordan product of two SpinFactor elements
; (α,v) ∘ (β,w) = (αβ + v·w, αw + βv)
; Arguments: rdi = result_ptr, rsi = a_ptr, rdx = b_ptr
; Returns: rax = 0
; =============================================================================
jordan_product:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14
    push    r15

    mov     rbx, rdi            ; result_ptr
    mov     r12, rsi            ; a_ptr
    mov     r13, rdx            ; b_ptr

    ; Load a.alpha and b.alpha
    movsd   xmm0, [r12 + ELEM_ALPHA]   ; a.alpha
    movsd   xmm1, [r13 + ELEM_ALPHA]   ; b.alpha

    ; scalar_part = a.alpha * b.alpha
    movsd   xmm4, xmm0
    mulsd   xmm4, xmm1          ; xmm4 = alpha * beta

    ; v.dot.w = dot(a.v, b.v)
    lea     rdi, [r12 + ELEM_V0]    ; a.v
    lea     rsi, [r13 + ELEM_V0]    ; b.v
    mov     rdx, 6
    call    jordan_dot_product  ; xmm0 = v·w

    ; scalar_part += v·w
    addsd   xmm4, xmm0          ; xmm4 = αβ + v·w

    ; Store result.alpha = αβ + v·w
    movsd   [rbx + ELEM_ALPHA], xmm4

    ; vector_part = αw + βv
    ; For each i: result.v[i] = a.alpha * b.v[i] + b.alpha * a.v[i]
    movsd   xmm0, [r12 + ELEM_ALPHA]   ; reload a.alpha
    movsd   xmm1, [r13 + ELEM_ALPHA]   ; reload b.alpha

    xor     rcx, rcx
.prod_vec_loop:
    cmp     rcx, 6
    jge     .prod_done
    ; a.alpha * b.v[i]
    movsd   xmm2, [r13 + ELEM_V0 + rcx * 8]   ; b.v[i]
    movsd   xmm5, xmm0          ; a.alpha
    mulsd   xmm5, xmm2          ; a.alpha * b.v[i]
    ; b.alpha * a.v[i]
    movsd   xmm3, [r12 + ELEM_V0 + rcx * 8]   ; a.v[i]
    movsd   xmm6, xmm1          ; b.alpha
    mulsd   xmm6, xmm3          ; b.alpha * a.v[i]
    ; sum
    addsd   xmm5, xmm6          ; αw_i + βv_i
    movsd   [rbx + ELEM_V0 + rcx * 8], xmm5
    inc     rcx
    jmp     .prod_vec_loop

.prod_done:
    xor     rax, rax
    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; jordan_scale_vector — Scale a vector in-place: v *= scalar
; Arguments: rdi = vec_ptr (f64*), xmm0 = scalar, rsi = dim
; Returns: rax = 0
; =============================================================================
jordan_scale_vector:
    push    rbp
    mov     rbp, rsp
    push    rbx

    mov     rbx, rdi            ; vec_ptr
    ; xmm0 = scalar already
    xor     rcx, rcx
.scale_loop:
    cmp     rcx, rsi
    jge     .scale_done
    movsd   xmm1, [rbx + rcx * 8]
    mulsd   xmm1, xmm0          ; v[i] *= scalar
    movsd   [rbx + rcx * 8], xmm1
    inc     rcx
    jmp     .scale_loop
.scale_done:
    xor     rax, rax
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; jordan_add_vectors — Add two vectors: dst[i] = a[i] + b[i]
; Arguments: rdi = dst_ptr, rsi = a_ptr, rdx = b_ptr, rcx = dim
; Returns: rax = 0
; =============================================================================
jordan_add_vectors:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14

    mov     rbx, rdi            ; dst
    mov     r12, rsi            ; a
    mov     r13, rdx            ; b
    mov     r14, rcx            ; dim

    xor     rcx, rcx
.add_loop:
    cmp     rcx, r14
    jge     .add_done
    movsd   xmm0, [r12 + rcx * 8]
    movsd   xmm1, [r13 + rcx * 8]
    addsd   xmm0, xmm1
    movsd   [rbx + rcx * 8], xmm0
    inc     rcx
    jmp     .add_loop
.add_done:
    xor     rax, rax
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; jordan_norm — Compute Euclidean norm of a SpinFactor element
; ‖(α,v)‖ = sqrt(α² + ‖v‖²)
; Arguments: rdi = elem_ptr
; Returns: xmm0 = norm
; =============================================================================
jordan_norm:
    push    rbp
    mov     rbp, rsp
    push    rbx

    mov     rbx, rdi

    ; alpha^2
    movsd   xmm0, [rbx + ELEM_ALPHA]
    mulsd   xmm0, xmm0          ; xmm0 = alpha^2

    ; ||v||^2 = v·v (6-dimensional)
    lea     rdi, [rbx + ELEM_V0]
    mov     rsi, rdi            ; same pointer for v·v
    mov     rdx, 6
    call    jordan_dot_product  ; xmm0 = ||v||^2

    ; total = alpha^2 + ||v||^2
    movsd   xmm1, [rbx + ELEM_ALPHA]
    mulsd   xmm1, xmm1          ; xmm1 = alpha^2
    addsd   xmm0, xmm1          ; xmm0 = alpha^2 + ||v||^2

    sqrtsd  xmm0, xmm0          ; xmm0 = sqrt(alpha^2 + ||v||^2)

    pop     rbx
    pop     rbp
    ret

; =============================================================================
; jordan_normalize — Normalize element in-place: x /= ||x||
; Arguments: rdi = elem_ptr
; Returns: rax = 0
; =============================================================================
jordan_normalize:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    mov     rbx, rdi

    ; Compute norm
    call    jordan_norm         ; xmm0 = norm

    ; Check for zero norm (avoid division by zero)
    xorpd   xmm1, xmm1
    ucomisd xmm0, xmm1
    je      .norm_zero          ; if norm == 0, skip

    ; Compute reciprocal
    movsd   xmm1, [rel f64_one]
    divsd   xmm1, xmm0          ; inv_norm = 1.0 / norm

    ; Scale alpha
    movsd   xmm2, [rbx + ELEM_ALPHA]
    mulsd   xmm2, xmm1
    movsd   [rbx + ELEM_ALPHA], xmm2

    ; Scale vector components
    xor     rcx, rcx
.norm_vec_loop:
    cmp     rcx, 6
    jge     .norm_done
    movsd   xmm2, [rbx + ELEM_V0 + rcx * 8]
    mulsd   xmm2, xmm1
    movsd   [rbx + ELEM_V0 + rcx * 8], xmm2
    inc     rcx
    jmp     .norm_vec_loop

.norm_zero:
.norm_done:
    xor     rax, rax
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; jordan_square — Compute x ∘ x (Jordan square)
; (α,v) ∘ (α,v) = (α² + ‖v‖², 2αv)
; Arguments: rdi = result_ptr, rsi = x_ptr
; Returns: rax = 0
; =============================================================================
jordan_square:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    mov     rbx, rdi            ; result
    mov     r12, rsi            ; x

    ; Call jordan_product(result, x, x)
    mov     rdx, r12            ; b = x
    mov     rsi, r12            ; a = x
    call    jordan_product      ; rdi=result, rsi=x, rdx=x already set above

    xor     rax, rax
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; jordan_eigenvalue_lo — Compute λ- = α - ‖v‖
; Arguments: rdi = elem_ptr
; Returns: xmm0 = α - ‖v‖
; =============================================================================
jordan_eigenvalue_lo:
    push    rbp
    mov     rbp, rsp
    push    rbx

    mov     rbx, rdi

    ; Load alpha
    movsd   xmm2, [rbx + ELEM_ALPHA]   ; xmm2 = alpha

    ; Compute ||v||
    lea     rdi, [rbx + ELEM_V0]
    mov     rsi, rdi
    mov     rdx, 6
    call    jordan_dot_product  ; xmm0 = ||v||^2
    sqrtsd  xmm0, xmm0          ; xmm0 = ||v||

    ; lambda_lo = alpha - ||v||
    subsd   xmm2, xmm0
    movsd   xmm0, xmm2          ; return in xmm0

    pop     rbx
    pop     rbp
    ret

; =============================================================================
; jordan_eigenvalue_hi — Compute λ+ = α + ‖v‖
; Arguments: rdi = elem_ptr
; Returns: xmm0 = α + ‖v‖
; =============================================================================
jordan_eigenvalue_hi:
    push    rbp
    mov     rbp, rsp
    push    rbx

    mov     rbx, rdi

    movsd   xmm2, [rbx + ELEM_ALPHA]

    lea     rdi, [rbx + ELEM_V0]
    mov     rsi, rdi
    mov     rdx, 6
    call    jordan_dot_product
    sqrtsd  xmm0, xmm0          ; xmm0 = ||v||

    addsd   xmm2, xmm0
    movsd   xmm0, xmm2

    pop     rbx
    pop     rbp
    ret

; =============================================================================
; jordan_spectral_gap — Compute 2‖v‖ = λ+ - λ-
; Arguments: rdi = elem_ptr
; Returns: xmm0 = 2*||v||
; =============================================================================
jordan_spectral_gap:
    push    rbp
    mov     rbp, rsp
    push    rbx

    mov     rbx, rdi

    lea     rdi, [rbx + ELEM_V0]
    mov     rsi, rdi
    mov     rdx, 6
    call    jordan_dot_product  ; xmm0 = ||v||^2
    sqrtsd  xmm0, xmm0          ; xmm0 = ||v||

    ; 2 * ||v||
    movsd   xmm1, [rel f64_two]
    mulsd   xmm0, xmm1

    pop     rbx
    pop     rbp
    ret

; =============================================================================
; jordan_is_idempotent — Check if x ∘ x ≈ x
; ‖x ∘ x - x‖ < tol
; Arguments: rdi = elem_ptr
; Returns: rax = 1 (idempotent), 0 (not)
; =============================================================================
jordan_is_idempotent:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    mov     rbx, rdi

    ; Compute x^2 into jordan_tmp_a
    lea     rdi, [rel jordan_tmp_a]
    mov     rsi, rbx
    call    jordan_square       ; jordan_tmp_a = x^2

    ; Compute ||x^2 - x|| by subtracting x from x^2
    ; diff.alpha = x^2.alpha - x.alpha
    movsd   xmm0, [rel jordan_tmp_a + ELEM_ALPHA]
    movsd   xmm1, [rbx + ELEM_ALPHA]
    subsd   xmm0, xmm1          ; diff_alpha
    mulsd   xmm0, xmm0          ; diff_alpha^2

    ; ||diff_v||^2
    xorpd   xmm4, xmm4          ; accumulate
    xor     rcx, rcx
.idem_vec_loop:
    cmp     rcx, 6
    jge     .idem_done_vec
    movsd   xmm1, [rel jordan_tmp_a + ELEM_V0 + rcx * 8]
    movsd   xmm2, [rbx + ELEM_V0 + rcx * 8]
    subsd   xmm1, xmm2          ; diff_v[i]
    mulsd   xmm1, xmm1          ; diff_v[i]^2
    addsd   xmm4, xmm1
    inc     rcx
    jmp     .idem_vec_loop
.idem_done_vec:
    addsd   xmm0, xmm4          ; total squared norm of (x^2 - x)

    sqrtsd  xmm0, xmm0          ; ||x^2 - x||

    ; Compare with tolerance 1e-9
    movsd   xmm1, [rel f64_tol_default]
    ucomisd xmm0, xmm1
    ja      .not_idem           ; ||x^2-x|| > tol -> not idempotent

    ; Print idempotent message
    push    xmm0                ; align stack (optional, for C calling)
    mov     rdi, 1
    lea     rsi, [rel msg_idempotent]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_idempotent]
    call    sys_write
    pop     xmm0

    mov     rax, 1
    pop     r12
    pop     rbx
    pop     rbp
    ret

.not_idem:
    xor     rax, rax
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; jordan_fixed_point_iter — Single iteration: x = normalize(x ∘ x)
; Arguments: rdi = elem_ptr
; Returns: rax = 0
; =============================================================================
jordan_fixed_point_iter:
    push    rbp
    mov     rbp, rsp
    push    rbx

    mov     rbx, rdi

    ; Compute x^2 into jordan_tmp_b
    lea     rdi, [rel jordan_tmp_b]
    mov     rsi, rbx
    call    jordan_square

    ; Normalize jordan_tmp_b in-place
    lea     rdi, [rel jordan_tmp_b]
    call    jordan_normalize

    ; Copy jordan_tmp_b back into x
    ; (56 bytes = 7 qwords)
    lea     rsi, [rel jordan_tmp_b]
    mov     rdi, rbx
    mov     rcx, 7
.copy_back:
    mov     rax, [rsi]
    mov     [rdi], rax
    add     rsi, 8
    add     rdi, 8
    dec     rcx
    jnz     .copy_back

    xor     rax, rax
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; jordan_fixed_point_solve — Iterate until convergence
; Runs jordan_fixed_point_iter until:
;   ‖x_new - x_old‖ < tol  OR  iterations >= max_iter
; Arguments:
;   rdi = elem_ptr
;   rsi = max_iter (uint64)
;   xmm0 = tol (f64)
; Returns: rax = iterations_taken
; =============================================================================
jordan_fixed_point_solve:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14

    mov     rbx, rdi            ; elem_ptr
    mov     r12, rsi            ; max_iter
    movsd   [rsp - 8], xmm0     ; save tol on stack (below sp, safe in leaf)
    ; Actually use sub rsp for safety
    sub     rsp, 16
    movsd   [rsp], xmm0         ; tol on stack

    xor     r13, r13            ; iteration count

.solve_loop:
    cmp     r13, r12
    jge     .solve_max_iter     ; hit max iterations

    ; Save current x into jordan_tmp_c (for convergence check)
    lea     rdi, [rel jordan_tmp_c]
    mov     rsi, rbx
    mov     rcx, 7
.save_old:
    mov     rax, [rsi]
    mov     [rdi], rax
    add     rsi, 8
    add     rdi, 8
    dec     rcx
    jnz     .save_old

    ; Perform one iteration
    mov     rdi, rbx
    call    jordan_fixed_point_iter

    ; Compute ||x_new - x_old|| (7 components as doubles)
    xorpd   xmm4, xmm4
    xor     rcx, rcx
.convergence_check:
    cmp     rcx, 7
    jge     .check_done
    movsd   xmm0, [rbx + rcx * 8]
    movsd   xmm1, [rel jordan_tmp_c + rcx * 8]   ; wrong offset? fix:
    subsd   xmm0, xmm1
    mulsd   xmm0, xmm0
    addsd   xmm4, xmm0
    inc     rcx
    jmp     .convergence_check
.check_done:
    sqrtsd  xmm4, xmm4          ; ||x_new - x_old||

    ; Compare to tol
    movsd   xmm1, [rsp]         ; reload tol
    ucomisd xmm4, xmm1
    jb      .converged          ; ||delta|| < tol -> converged

    inc     r13
    jmp     .solve_loop

.converged:
    ; Print convergence message
    push    r13
    mov     rdi, 1
    lea     rsi, [rel msg_jordan_conv]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_jordan_conv]
    call    sys_write
    pop     r13
    jmp     .solve_done

.solve_max_iter:
    ; Print failure message
    push    r13
    mov     rdi, 1
    lea     rsi, [rel msg_jordan_fail]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_jordan_fail]
    call    sys_write
    pop     r13

.solve_done:
    mov     rax, r13            ; return iterations taken
    add     rsp, 16
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret
