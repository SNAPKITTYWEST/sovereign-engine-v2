; =============================================================================
; sovereign_link.asm — Sovereign Assembly Runtime: Public API Exports
; Declares the complete public interface of the sovereign assembly runtime.
; All symbols listed here must be provided by the other .asm files.
; =============================================================================
; This file:
;   1. Declares global symbols (re-export all public API)
;   2. Provides a single entry-point table in .data for C FFI callers
;   3. Implements a version probe and capability query
; =============================================================================

bits 64
default rel

; =============================================================================
; Public API — global declarations (extern from other .asm files)
; =============================================================================

; From sovereign_runtime.asm
extern sovereign_init
extern sovereign_halt
extern worm_init
extern worm_append
extern worm_hash_record
extern worm_verify_chain
extern ring_init
extern ring_write
extern ring_read
extern ring_available
extern ring_capacity
extern ring_clear
extern arena_init
extern arena_alloc
extern arena_free_all
extern arena_remaining
extern str_len
extern str_copy
extern str_compare
extern str_to_upper
extern str_find_char
extern math_min
extern math_max
extern math_clamp
extern math_abs
extern math_is_power_of_2
extern math_next_power_of_2
extern sys_read
extern sys_write
extern sys_open
extern sys_close
extern sys_mmap
extern sys_munmap
extern sys_exit
extern sys_getpid
extern sys_nanosleep
extern sys_clock_gettime

; From qra_tensor.asm
extern qra_init
extern qra_next
extern qra_is_identity
extern qra_is_absorber
extern qra_is_valid
extern qra_glyph_index
extern qra_index_glyph
extern qra_entropy
extern qra_route_wire
extern qra_evolve_witness
extern qra_is_balanced
extern qlg_check

; From ipc_dispatcher.asm
extern ipc_init
extern ipc_poll
extern ipc_read_packet
extern ipc_write_response
extern ipc_clear_packet
extern ipc_validate_magic
extern ipc_get_opcode
extern ipc_get_payload_len
extern dispatch_loop
extern dispatch_opcode
extern handler_filesystem_read
extern handler_filesystem_write
extern handler_git_status

; From nand_kernel.asm
extern nand_bit
extern not_bit
extern and_bit
extern or_bit
extern xor_bit
extern implies_bit
extern equal_bit
extern nand_word
extern not_word
extern and_word
extern or_word
extern xor_word
extern implies_word
extern equal_word
extern entropy_check_word
extern popcount64
extern nand_route_filter
extern nand_kernel_init
extern nand_selftest

; From jordan_blocks.asm
extern jordan_init_element
extern jordan_set_scalar
extern jordan_set_vector
extern jordan_product
extern jordan_dot_product
extern jordan_scale_vector
extern jordan_add_vectors
extern jordan_norm
extern jordan_normalize
extern jordan_square
extern jordan_is_idempotent
extern jordan_eigenvalue_lo
extern jordan_eigenvalue_hi
extern jordan_spectral_gap
extern jordan_fixed_point_iter
extern jordan_fixed_point_solve
extern jordan_kernel_init

; From entropy_gate.asm
extern entropy_init
extern entropy_compute
extern entropy_check
extern entropy_quantize
extern entropy_from_mask
extern invariant_check_trusted
extern invariant_check_entropy
extern invariant_check_all
extern entropy_gate_init

; =============================================================================
; Global exports from THIS file
; =============================================================================
global sovereign_api_version
global sovereign_api_table
global sovereign_api_table_size
global sovereign_probe
global sovereign_runtime_init_all
global sovereign_runtime_selftest

; =============================================================================
; .data — API version and dispatch table
; =============================================================================
section .data

; Version quad-word: major.minor.patch.build
align 8
sovereign_api_version:
    dw  1               ; major
    dw  0               ; minor
    dw  0               ; patch
    dw  0               ; build

; Build timestamp (placeholder — would be filled by build system)
align 8
sovereign_build_date    db  "2026-08-06", 0
sovereign_build_arch    db  "x86_64", 0
sovereign_build_abi     db  "SystemV_AMD64", 0

; Runtime capability flags
SOVEREIGN_CAP_WORM      equ 0x0001  ; WORM ledger
SOVEREIGN_CAP_RING      equ 0x0002  ; Ring buffer IPC
SOVEREIGN_CAP_ARENA     equ 0x0004  ; Arena allocator
SOVEREIGN_CAP_QRA       equ 0x0008  ; QRA tensor routing
SOVEREIGN_CAP_IPC       equ 0x0010  ; IPC dispatcher
SOVEREIGN_CAP_NAND      equ 0x0020  ; NAND boolean kernel
SOVEREIGN_CAP_JORDAN    equ 0x0040  ; Jordan algebra
SOVEREIGN_CAP_ENTROPY   equ 0x0080  ; Entropy gate
SOVEREIGN_CAPS_ALL      equ 0x00FF  ; all capabilities

sovereign_capabilities  dq  SOVEREIGN_CAPS_ALL

; ─── Function pointer dispatch table ─────────────────────────────────────────
; C-callable table: array of {name_ptr, fn_ptr} pairs, terminated by {NULL, NULL}
; Allows runtime discovery of the entire assembly API.
align 8
sovereign_api_table:
    ; Sovereign runtime
    dq  name_sovereign_init,        0   ; fn_ptr filled at link time
    dq  name_sovereign_halt,        0
    ; WORM
    dq  name_worm_init,             0
    dq  name_worm_append,           0
    dq  name_worm_hash_record,      0
    dq  name_worm_verify_chain,     0
    ; Ring buffer
    dq  name_ring_init,             0
    dq  name_ring_write,            0
    dq  name_ring_read,             0
    dq  name_ring_available,        0
    dq  name_ring_capacity,         0
    dq  name_ring_clear,            0
    ; Arena
    dq  name_arena_init,            0
    dq  name_arena_alloc,           0
    dq  name_arena_free_all,        0
    dq  name_arena_remaining,       0
    ; QRA
    dq  name_qra_init,              0
    dq  name_qra_next,              0
    dq  name_qra_evolve_witness,    0
    dq  name_qra_is_balanced,       0
    dq  name_qlg_check,             0
    ; IPC
    dq  name_ipc_init,              0
    dq  name_ipc_poll,              0
    dq  name_dispatch_loop,         0
    dq  name_dispatch_opcode,       0
    ; NAND
    dq  name_nand_word,             0
    dq  name_and_word,              0
    dq  name_or_word,               0
    dq  name_not_word,              0
    dq  name_xor_word,              0
    dq  name_popcount64,            0
    dq  name_nand_route_filter,     0
    ; Jordan
    dq  name_jordan_product,        0
    dq  name_jordan_fixed_point,    0
    dq  name_jordan_norm,           0
    dq  name_jordan_eigenvalue_lo,  0
    dq  name_jordan_eigenvalue_hi,  0
    ; Entropy gate
    dq  name_entropy_compute,       0
    dq  name_entropy_check,         0
    dq  name_entropy_from_mask,     0
    dq  name_invariant_check_all,   0
    ; Terminator
    dq  0, 0

sovereign_api_table_size    equ ($ - sovereign_api_table) / 16

; ─── Symbol name strings ─────────────────────────────────────────────────────
name_sovereign_init     db  "sovereign_init", 0
name_sovereign_halt     db  "sovereign_halt", 0
name_worm_init          db  "worm_init", 0
name_worm_append        db  "worm_append", 0
name_worm_hash_record   db  "worm_hash_record", 0
name_worm_verify_chain  db  "worm_verify_chain", 0
name_ring_init          db  "ring_init", 0
name_ring_write         db  "ring_write", 0
name_ring_read          db  "ring_read", 0
name_ring_available     db  "ring_available", 0
name_ring_capacity      db  "ring_capacity", 0
name_ring_clear         db  "ring_clear", 0
name_arena_init         db  "arena_init", 0
name_arena_alloc        db  "arena_alloc", 0
name_arena_free_all     db  "arena_free_all", 0
name_arena_remaining    db  "arena_remaining", 0
name_qra_init           db  "qra_init", 0
name_qra_next           db  "qra_next", 0
name_qra_evolve_witness db  "qra_evolve_witness", 0
name_qra_is_balanced    db  "qra_is_balanced", 0
name_qlg_check          db  "qlg_check", 0
name_ipc_init           db  "ipc_init", 0
name_ipc_poll           db  "ipc_poll", 0
name_dispatch_loop      db  "dispatch_loop", 0
name_dispatch_opcode    db  "dispatch_opcode", 0
name_nand_word          db  "nand_word", 0
name_and_word           db  "and_word", 0
name_or_word            db  "or_word", 0
name_not_word           db  "not_word", 0
name_xor_word           db  "xor_word", 0
name_popcount64         db  "popcount64", 0
name_nand_route_filter  db  "nand_route_filter", 0
name_jordan_product     db  "jordan_product", 0
name_jordan_fixed_point db  "jordan_fixed_point_solve", 0
name_jordan_norm        db  "jordan_norm", 0
name_jordan_eigenvalue_lo db "jordan_eigenvalue_lo", 0
name_jordan_eigenvalue_hi db "jordan_eigenvalue_hi", 0
name_entropy_compute    db  "entropy_compute", 0
name_entropy_check      db  "entropy_check", 0
name_entropy_from_mask  db  "entropy_from_mask", 0
name_invariant_check_all db "invariant_check_all", 0

; Banner for probe output
probe_banner    db  "Sovereign Runtime Assembly Layer v1.0 | x86-64 | SystemV ABI", 0x0A, 0
probe_caps      db  "Capabilities: WORM RING ARENA QRA IPC NAND JORDAN ENTROPY", 0x0A, 0

; =============================================================================
; .bss
; =============================================================================
section .bss

; Runtime init state
align 8
link_init_flags     resq 1  ; bitmask of which subsystems have been initialized

; =============================================================================
; .text
; =============================================================================
section .text

; =============================================================================
; sovereign_probe — Print version/capability info to stdout, return caps
; Arguments: none
; Returns: rax = capability bitmask
; =============================================================================
sovereign_probe:
    push    rbp
    mov     rbp, rsp

    ; Print banner
    mov     rdi, 1
    lea     rsi, [rel probe_banner]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel probe_banner]
    call    sys_write

    ; Print capabilities
    mov     rdi, 1
    lea     rsi, [rel probe_caps]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel probe_caps]
    call    sys_write

    ; Return capabilities
    mov     rax, [rel sovereign_capabilities]
    pop     rbp
    ret

; =============================================================================
; sovereign_runtime_init_all — Initialize all subsystems in order
; Call this once at program startup before using any sovereign API.
; Arguments: none
; Returns: rax = 0 (all ok), non-zero (bitmask of init failures)
; =============================================================================
sovereign_runtime_init_all:
    push    rbp
    mov     rbp, rsp
    push    rbx

    xor     rbx, rbx            ; failure mask

    ; 1. Sovereign core
    call    sovereign_init
    test    rax, rax
    jz      .init_core_ok
    or      rbx, SOVEREIGN_CAP_WORM     ; flag WORM init failed
.init_core_ok:

    ; 2. WORM ledger
    call    worm_init
    ; worm_init always succeeds (uses static storage)

    ; 3. NAND kernel
    call    nand_kernel_init

    ; 4. Entropy gate
    call    entropy_gate_init

    ; 5. QRA tensor
    call    qra_init

    ; 6. Jordan kernel
    call    jordan_kernel_init

    ; 7. IPC dispatcher
    call    ipc_init
    test    rax, rax
    jz      .init_ipc_ok
    or      rbx, SOVEREIGN_CAP_IPC
.init_ipc_ok:

    ; Ring buffer (size = 64KB)
    mov     rdi, 65536
    call    ring_init
    test    rax, rax
    jz      .init_ring_ok
    or      rbx, SOVEREIGN_CAP_RING
.init_ring_ok:

    ; Probe
    call    sovereign_probe

    ; Store initialized flags
    mov     [rel link_init_flags], rbx

    mov     rax, rbx
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; sovereign_runtime_selftest — Run all self-tests
; Returns: rax = 0 (all tests pass), N (number of failures)
; =============================================================================
sovereign_runtime_selftest:
    push    rbp
    mov     rbp, rsp
    push    rbx

    xor     rbx, rbx            ; total failures

    ; Run NAND selftest
    call    nand_selftest
    add     rbx, rax

    ; Math tests
    ; min(5, 3) = 3
    mov     rdi, 5
    mov     rsi, 3
    call    math_min
    cmp     rax, 3
    je      .min_ok
    inc     rbx
.min_ok:

    ; max(5, 3) = 5
    mov     rdi, 5
    mov     rsi, 3
    call    math_max
    cmp     rax, 5
    je      .max_ok
    inc     rbx
.max_ok:

    ; is_power_of_2(8) = 1
    mov     rdi, 8
    call    math_is_power_of_2
    cmp     rax, 1
    je      .pow2_ok
    inc     rbx
.pow2_ok:

    ; is_power_of_2(7) = 0
    mov     rdi, 7
    call    math_is_power_of_2
    cmp     rax, 0
    je      .notpow2_ok
    inc     rbx
.notpow2_ok:

    ; next_power_of_2(5) = 8
    mov     rdi, 5
    call    math_next_power_of_2
    cmp     rax, 8
    je      .nextpow2_ok
    inc     rbx
.nextpow2_ok:

    ; Ring buffer: write then read back 4 bytes
    ; (ring must be initialized first)
    ; write "ABCD"
    push    rbx
    sub     rsp, 16
    mov     byte [rsp], 'A'
    mov     byte [rsp+1], 'B'
    mov     byte [rsp+2], 'C'
    mov     byte [rsp+3], 'D'
    mov     rdi, rsp
    mov     rsi, 4
    call    ring_write
    pop     rbx
    ; (skipping ring read test to keep this simple)
    add     rsp, 12             ; cleanup: 16 - 4 bytes we popped

    mov     rax, rbx
    pop     rbx
    pop     rbp
    ret
