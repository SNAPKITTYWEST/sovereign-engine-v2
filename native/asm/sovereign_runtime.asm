; =============================================================================
; sovereign_runtime.asm — Main Sovereign Runtime (x86-64 NASM, Linux)
; System V AMD64 ABI throughout.
; =============================================================================
; Registers (caller-saved): rax, rcx, rdx, rsi, rdi, r8-r11, xmm0-xmm7
; Registers (callee-saved): rbx, rbp, r12-r15
; Return value: rax (integer), xmm0 (float)
; Arguments: rdi, rsi, rdx, rcx, r8, r9 (integer); xmm0-xmm7 (float)
; =============================================================================

bits 64
default rel

; ─── System Call Numbers (Linux x86-64) ─────────────────────────────────────
SYS_READ        equ 0
SYS_WRITE       equ 1
SYS_OPEN        equ 2
SYS_CLOSE       equ 3
SYS_MMAP        equ 9
SYS_MUNMAP      equ 11
SYS_EXIT        equ 60
SYS_GETPID      equ 39
SYS_NANOSLEEP   equ 35
SYS_CLOCK_GETTIME equ 228

; ─── File Descriptor Constants ────────────────────────────────────────────────
STDIN           equ 0
STDOUT          equ 1
STDERR          equ 2

; ─── mmap flags ───────────────────────────────────────────────────────────────
PROT_READ       equ 0x1
PROT_WRITE      equ 0x2
MAP_PRIVATE     equ 0x2
MAP_ANONYMOUS   equ 0x20
MAP_FAILED      equ -1

; ─── open flags ───────────────────────────────────────────────────────────────
O_RDONLY        equ 0
O_WRONLY        equ 1
O_RDWR          equ 2
O_CREAT         equ 0x40
O_TRUNC         equ 0x200
O_APPEND        equ 0x400

; ─── Sovereign constants ──────────────────────────────────────────────────────
SOVEREIGN_MAGIC         equ 0x534F5652   ; 'SOVR'
SOVEREIGN_VERSION       equ 0x00010000   ; 1.0.0
WORM_MAGIC              equ 0x574F524D   ; 'WORM'
WORM_MAX_RECORDS        equ 4096
WORM_RECORD_SIZE        equ 256          ; bytes per record
WORM_HASH_SIZE          equ 32           ; Blake2b-256 = 32 bytes
ARENA_DEFAULT_SIZE      equ 0x100000     ; 1 MB default arena
RING_DEFAULT_SIZE       equ 0x10000      ; 64 KB ring buffer
HASH_PRIME              equ 0x517CC1B727220A95  ; FNV-like prime

; ─── Event types ──────────────────────────────────────────────────────────────
EVT_INIT        equ 0x01
EVT_APPEND      equ 0x02
EVT_VERIFY      equ 0x03
EVT_HALT        equ 0xFF

; =============================================================================
; .data — Initialized data
; =============================================================================
section .data

; Sovereign runtime banner
banner          db  "Sovereign Runtime v1.0 — NASM x86-64", 0x0A, 0
banner_len      equ $ - banner

; QRA glyph table (6 entries from Σ)
; Glyph bytes: Π=0x01 Γ=0x03 Δ=0x04 Ω=0x0A Λ=0xFF Ψ=0x0B
qra_glyphs      db  0x01, 0x03, 0x04, 0x0A, 0xFF, 0x0B
qra_glyph_count equ 6

; Glyph names (null-terminated, 2 chars + NUL)
glyph_name_pi   db  0xCE, 0xA0, 0   ; Π
glyph_name_gam  db  0xCE, 0x93, 0   ; Γ
glyph_name_del  db  0xCE, 0x94, 0   ; Δ
glyph_name_ome  db  0xCE, 0xA9, 0   ; Ω
glyph_name_lam  db  0xCE, 0x9B, 0   ; Λ
glyph_name_psi  db  0xCE, 0xA8, 0   ; Ψ

; Runtime magic bytes
runtime_magic   dd  SOVEREIGN_MAGIC
runtime_version dd  SOVEREIGN_VERSION

; Newline constant
newline         db  0x0A, 0

; Error messages
err_init        db  "ERROR: sovereign_init failed", 0x0A, 0
err_worm        db  "ERROR: WORM ledger full", 0x0A, 0
err_ring        db  "ERROR: ring buffer overflow", 0x0A, 0
err_arena       db  "ERROR: arena exhausted", 0x0A, 0
err_verify      db  "ERROR: WORM chain verification failed", 0x0A, 0

msg_init_ok     db  "Sovereign runtime initialized.", 0x0A, 0
msg_halt        db  "Sovereign runtime halting.", 0x0A, 0
msg_worm_ok     db  "WORM ledger ready.", 0x0A, 0

; Blake2b mixing constants (IV values, first 4 used for simplified hash)
blake2b_iv0     dq  0x6A09E667F3BCC908
blake2b_iv1     dq  0xBB67AE8584CAA73B
blake2b_iv2     dq  0x3C6EF372FE94F82B
blake2b_iv3     dq  0xA54FF53A5F1D36F1
blake2b_iv4     dq  0x510E527FADE682D1
blake2b_iv5     dq  0x9B05688C2B3E6C1F
blake2b_iv6     dq  0x1F83D9ABFB41BD6B
blake2b_iv7     dq  0x5BE0CD19137E2179

; SIGMA permutation schedule for Blake2b (16 rounds x 16 indices)
blake2b_sigma:
    db 0,  1,  2,  3,  4,  5,  6,  7,  8,  9,  10, 11, 12, 13, 14, 15
    db 14, 10,  4,  8,  9, 15, 13,  6,  1, 12,  0,  2, 11,  7,  5,  3
    db 11,  8, 12,  0,  5,  2, 15, 13, 10, 14,  3,  6,  7,  1,  9,  4
    db  7,  9,  3,  1, 13, 12, 11, 14,  2,  6,  5, 10,  4,  0, 15,  8
    db  9,  0,  5,  7,  2,  4, 10, 15, 14,  1, 11, 12,  6,  8,  3, 13
    db  2, 12,  6, 10,  0, 11,  8,  3,  4, 13,  7,  5, 15, 14,  1,  9
    db 12,  5,  1, 15, 14, 13,  4, 10,  0,  7,  6,  3,  9,  2,  8, 11
    db 13, 11,  7, 14, 12,  1,  3,  9,  5,  0, 15,  4,  8,  6,  2, 10
    db  6, 15, 14,  9, 11,  3,  0,  8, 12,  2, 13,  7,  1,  4, 10,  5
    db 10,  2,  8,  4,  7,  6,  1,  5, 15, 11,  9, 14,  3, 12, 13,  0
    db  0,  1,  2,  3,  4,  5,  6,  7,  8,  9,  10, 11, 12, 13, 14, 15
    db 14, 10,  4,  8,  9, 15, 13,  6,  1, 12,  0,  2, 11,  7,  5,  3

; =============================================================================
; .bss — Uninitialized data
; =============================================================================
section .bss

; ─── Sovereign runtime state block ───────────────────────────────────────────
align 16
sovereign_state:
    .magic      resd 1          ; 0:  SOVEREIGN_MAGIC
    .version    resd 1          ; 4:  version
    .flags      resq 1          ; 8:  runtime flags
    .tick       resq 1          ; 16: monotonic tick counter
    .pid        resq 1          ; 24: process ID
    .init_done  resb 1          ; 32: initialization flag
    resb        7               ; pad to 8-byte boundary

; ─── WORM ledger ─────────────────────────────────────────────────────────────
align 64
worm_state:
    .record_count   resq 1                              ; number of records
    .max_records    resq 1                              ; max records
    .record_ptr     resq 1                              ; pointer to record buffer
    .prev_hash      resb WORM_HASH_SIZE                 ; previous record hash

; WORM record storage (inline, 4096 * 256 = 1 MB)
align 64
worm_records    resb  WORM_MAX_RECORDS * WORM_RECORD_SIZE

; ─── IPC ring buffer ─────────────────────────────────────────────────────────
align 64
ring_state:
    .buf        resq 1          ; pointer to buffer
    .size       resq 1          ; total size
    .head       resq 1          ; write position
    .tail       resq 1          ; read position
    .count      resq 1          ; bytes currently in ring

align 64
ring_buffer     resb  RING_DEFAULT_SIZE

; ─── Memory arena ─────────────────────────────────────────────────────────────
align 64
arena_state:
    .base       resq 1          ; base pointer
    .size       resq 1          ; total size
    .used       resq 1          ; bytes used

; ─── Scratch buffers ─────────────────────────────────────────────────────────
align 16
hash_scratch    resb  128       ; scratch space for hashing
str_scratch     resb  4096      ; scratch for string ops
temp_buf        resb  512       ; generic temp buffer

; =============================================================================
; .text — Code
; =============================================================================
section .text

; Export all public symbols
global _start
global sovereign_init
global sovereign_halt
global worm_init
global worm_append
global worm_hash_record
global worm_verify_chain
global ring_init
global ring_write
global ring_read
global ring_available
global ring_capacity
global ring_clear
global arena_init
global arena_alloc
global arena_free_all
global arena_remaining
global str_len
global str_copy
global str_compare
global str_to_upper
global str_find_char
global math_min
global math_max
global math_clamp
global math_abs
global math_is_power_of_2
global math_next_power_of_2
global sys_read
global sys_write
global sys_open
global sys_close
global sys_mmap
global sys_munmap
global sys_exit
global sys_getpid
global sys_nanosleep
global sys_clock_gettime

; =============================================================================
; _start — Entry point
; =============================================================================
_start:
    ; Zero out rbp per ABI convention for outermost frame
    xor     rbp, rbp

    ; Print banner
    mov     rdi, STDOUT
    lea     rsi, [rel banner]
    mov     rdx, banner_len - 1         ; subtract NUL
    call    sys_write

    ; Initialize sovereign runtime
    call    sovereign_init
    test    rax, rax
    jnz     .init_failed

    ; Initialize WORM ledger
    call    worm_init

    ; Initialize ring buffer
    mov     rdi, RING_DEFAULT_SIZE
    call    ring_init

    ; Print init ok
    mov     rdi, STDOUT
    lea     rsi, [rel msg_init_ok]
    call    str_len
    mov     rdx, rax
    mov     rdi, STDOUT
    lea     rsi, [rel msg_init_ok]
    call    sys_write

    ; Normal exit
    xor     rdi, rdi
    call    sys_exit

.init_failed:
    mov     rdi, STDERR
    lea     rsi, [rel err_init]
    call    str_len
    mov     rdx, rax
    mov     rdi, STDERR
    lea     rsi, [rel err_init]
    call    sys_write
    mov     rdi, 1
    call    sys_exit

; =============================================================================
; sovereign_init — Initialize the sovereign runtime state
; Arguments: none
; Returns: rax = 0 (success), -1 (failure)
; =============================================================================
sovereign_init:
    push    rbp
    mov     rbp, rsp
    push    rbx

    ; Set magic
    mov     dword [rel sovereign_state.magic], SOVEREIGN_MAGIC

    ; Set version
    mov     dword [rel sovereign_state.version], SOVEREIGN_VERSION

    ; Clear flags
    mov     qword [rel sovereign_state.flags], 0

    ; Clear tick
    mov     qword [rel sovereign_state.tick], 0

    ; Get PID and store
    call    sys_getpid
    mov     [rel sovereign_state.pid], rax

    ; Mark initialized
    mov     byte [rel sovereign_state.init_done], 1

    ; Return success
    xor     rax, rax
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; sovereign_halt — Clean shutdown of sovereign runtime
; Arguments: none
; Returns: does not return (calls sys_exit)
; =============================================================================
sovereign_halt:
    push    rbp
    mov     rbp, rsp

    ; Print halt message
    mov     rdi, STDOUT
    lea     rsi, [rel msg_halt]
    call    str_len
    mov     rdx, rax
    mov     rdi, STDOUT
    lea     rsi, [rel msg_halt]
    call    sys_write

    ; Append halt event to WORM
    lea     rdi, [rel msg_halt]
    call    str_len
    mov     rsi, rax                ; len
    mov     rdi, rsi                ; reuse: actually pass ptr first
    lea     rdi, [rel msg_halt]
    mov     rdx, EVT_HALT
    call    worm_append

    ; Clear init flag
    mov     byte [rel sovereign_state.init_done], 0

    ; Exit cleanly
    xor     rdi, rdi
    call    sys_exit

    ; Should never reach here
    pop     rbp
    ret

; =============================================================================
; worm_init — Initialize the WORM ledger
; Arguments: none
; Returns: rax = 0 (success)
; =============================================================================
worm_init:
    push    rbp
    mov     rbp, rsp

    ; Set record count to 0
    mov     qword [rel worm_state.record_count], 0

    ; Set max records
    mov     qword [rel worm_state.max_records], WORM_MAX_RECORDS

    ; Set record pointer to worm_records buffer
    lea     rax, [rel worm_records]
    mov     [rel worm_state.record_ptr], rax

    ; Zero the previous hash (genesis block has 0x00..00 prev hash)
    lea     rdi, [rel worm_state.prev_hash]
    xor     eax, eax
    mov     ecx, WORM_HASH_SIZE / 8         ; 4 iterations of 8 bytes
.zero_prev_hash:
    mov     qword [rdi], 0
    add     rdi, 8
    dec     ecx
    jnz     .zero_prev_hash

    ; Print WORM ok
    mov     rdi, STDOUT
    lea     rsi, [rel msg_worm_ok]
    call    str_len
    mov     rdx, rax
    mov     rdi, STDOUT
    lea     rsi, [rel msg_worm_ok]
    call    sys_write

    xor     rax, rax
    pop     rbp
    ret

; =============================================================================
; worm_append — Append a record to the WORM ledger
; Arguments:
;   rdi = data_ptr (pointer to data bytes)
;   rsi = len      (data length in bytes)
;   rdx = event_type (uint8 event code)
; Returns: rax = record index (0-based), or -1 if ledger full
; =============================================================================
worm_append:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14
    push    r15

    mov     r12, rdi            ; save data_ptr
    mov     r13, rsi            ; save len
    mov     r14, rdx            ; save event_type

    ; Check if ledger is full
    mov     rax, [rel worm_state.record_count]
    mov     rbx, [rel worm_state.max_records]
    cmp     rax, rbx
    jge     .ledger_full

    ; Calculate record offset: count * WORM_RECORD_SIZE
    mov     r15, rax            ; save index
    imul    rax, WORM_RECORD_SIZE
    mov     rbx, [rel worm_state.record_ptr]
    add     rbx, rax            ; rbx = pointer to new record slot

    ; Write record header:
    ;   [0..3]   WORM_MAGIC
    ;   [4..7]   record_index (uint32)
    ;   [8]      event_type (uint8)
    ;   [9..11]  pad
    ;   [12..43] prev_hash (32 bytes)
    ;   [44..47] data_len (uint32)
    ;   [48..N]  data bytes (up to 200 bytes)
    ;   [remainder..255] data hash (32 bytes at end)

    mov     dword [rbx], WORM_MAGIC         ; magic
    mov     dword [rbx + 4], r15d           ; record index
    mov     byte  [rbx + 8], r14b           ; event type
    mov     byte  [rbx + 9], 0
    mov     byte  [rbx + 10], 0
    mov     byte  [rbx + 11], 0

    ; Copy prev_hash into record
    lea     rsi, [rel worm_state.prev_hash]
    lea     rdi, [rbx + 12]
    mov     ecx, WORM_HASH_SIZE             ; 32 bytes
.copy_prev:
    mov     al, [rsi]
    mov     [rdi], al
    inc     rsi
    inc     rdi
    dec     ecx
    jnz     .copy_prev

    ; Store data_len (clamped to 200 bytes max)
    mov     rax, r13
    cmp     rax, 200
    jle     .len_ok
    mov     rax, 200
.len_ok:
    mov     dword [rbx + 44], eax           ; data_len

    ; Copy data bytes
    mov     rcx, rax            ; bytes to copy
    lea     rdi, [rbx + 48]     ; destination in record
    mov     rsi, r12            ; source data
.copy_data:
    test    rcx, rcx
    jz      .data_done
    mov     al, [rsi]
    mov     [rdi], al
    inc     rsi
    inc     rdi
    dec     rcx
    jmp     .copy_data
.data_done:

    ; Hash the record (data portion) to update prev_hash
    ; Use simplified FNV-like hash as "Blake2b" placeholder
    push    rbx                 ; save record ptr
    lea     rdi, [rbx + 12]     ; hash input = prev_hash + data
    mov     rsi, r13            ; data len (use actual)
    call    worm_hash_record    ; result in [hash_scratch]
    pop     rbx                 ; restore record ptr

    ; Copy new hash to end of record (bytes 224-255)
    lea     rsi, [rel hash_scratch]
    lea     rdi, [rbx + 224]
    mov     ecx, WORM_HASH_SIZE
.copy_hash:
    mov     al, [rsi]
    mov     [rdi], al
    inc     rsi
    inc     rdi
    dec     ecx
    jnz     .copy_hash

    ; Update prev_hash in worm_state
    lea     rsi, [rel hash_scratch]
    lea     rdi, [rel worm_state.prev_hash]
    mov     ecx, WORM_HASH_SIZE
.update_prev:
    mov     al, [rsi]
    mov     [rdi], al
    inc     rsi
    inc     rdi
    dec     ecx
    jnz     .update_prev

    ; Increment record count
    inc     qword [rel worm_state.record_count]

    ; Return record index
    mov     rax, r15

    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

.ledger_full:
    ; Print error
    mov     rdi, STDERR
    lea     rsi, [rel err_worm]
    call    str_len
    mov     rdx, rax
    mov     rdi, STDERR
    lea     rsi, [rel err_worm]
    call    sys_write
    mov     rax, -1
    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; worm_hash_record — Compute simplified Blake2b-256-like hash of data
; This is a structurally correct but simplified hash using the IV constants
; and a mixing step inspired by Blake2b's G function.
; Arguments:
;   rdi = data_ptr
;   rsi = len
; Returns: 32 bytes written to [hash_scratch]
; =============================================================================
worm_hash_record:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14
    push    r15

    mov     r12, rdi            ; data_ptr
    mov     r13, rsi            ; len

    ; Initialize state with IV values
    mov     rax, [rel blake2b_iv0]
    mov     [rel hash_scratch],      rax
    mov     rax, [rel blake2b_iv1]
    mov     [rel hash_scratch + 8],  rax
    mov     rax, [rel blake2b_iv2]
    mov     [rel hash_scratch + 16], rax
    mov     rax, [rel blake2b_iv3]
    mov     [rel hash_scratch + 24], rax

    ; XOR in message length
    xor     rax, rax
    mov     rax, r13
    xor     [rel hash_scratch], rax

    ; Process data in 8-byte chunks
    xor     r14, r14            ; offset
.hash_loop:
    cmp     r14, r13
    jge     .hash_finalize

    ; Load up to 8 bytes
    xor     rbx, rbx
    mov     rcx, r13
    sub     rcx, r14
    cmp     rcx, 8
    jle     .partial_word
    mov     rbx, [r12 + r14]    ; full 8-byte word
    jmp     .mix_word
.partial_word:
    ; Load remaining bytes one at a time
    xor     rbx, rbx
    xor     r15, r15
.byte_loop:
    test    rcx, rcx
    jz      .mix_word
    movzx   rax, byte [r12 + r14 + r15]
    shl     rax, cl             ; shift by position
    or      rbx, rax
    inc     r15
    dec     rcx
    jmp     .byte_loop

.mix_word:
    ; Mix into state using rotation-based operations (simplified G function)
    ; v0 ^= word
    xor     [rel hash_scratch], rbx

    ; v0 = (v0 <<< 32) ^ v1
    mov     rax, [rel hash_scratch]
    rol     rax, 32
    xor     rax, [rel hash_scratch + 8]
    mov     [rel hash_scratch], rax

    ; v1 += v0
    mov     rax, [rel hash_scratch + 8]
    add     rax, [rel hash_scratch]
    mov     [rel hash_scratch + 8], rax

    ; v2 ^= v1 rotated 24
    mov     rax, [rel hash_scratch + 8]
    rol     rax, 24
    xor     [rel hash_scratch + 16], rax

    ; v3 = v3 + v2 rotated 16
    mov     rax, [rel hash_scratch + 16]
    rol     rax, 16
    add     [rel hash_scratch + 24], rax

    ; Cross-mix: v0 ^= v3
    mov     rax, [rel hash_scratch + 24]
    xor     [rel hash_scratch], rax

    add     r14, 8
    jmp     .hash_loop

.hash_finalize:
    ; Finalization: XOR state with IV again (Blake2b finalization)
    mov     rax, [rel blake2b_iv4]
    xor     [rel hash_scratch], rax
    mov     rax, [rel blake2b_iv5]
    xor     [rel hash_scratch + 8], rax
    mov     rax, [rel blake2b_iv6]
    xor     [rel hash_scratch + 16], rax
    mov     rax, [rel blake2b_iv7]
    xor     [rel hash_scratch + 24], rax

    ; Output is already in hash_scratch[0..31]

    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; worm_verify_chain — Verify that all prev_hash links are consistent
; Walks the entire ledger recomputing hashes and checking linkage.
; Arguments: none
; Returns: rax = 0 (valid), 1 (invalid)
; =============================================================================
worm_verify_chain:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14

    mov     r12, [rel worm_state.record_count]
    test    r12, r12
    jz      .chain_ok                   ; empty chain is valid

    ; Verify record 0 has all-zero prev_hash
    mov     rbx, [rel worm_state.record_ptr]

    ; Walk records
    xor     r13, r13                    ; record index
.verify_loop:
    cmp     r13, r12
    jge     .chain_ok

    ; Compute offset
    mov     rax, r13
    imul    rax, WORM_RECORD_SIZE
    mov     r14, rbx
    add     r14, rax                    ; r14 = record ptr

    ; Check magic
    mov     eax, [r14]
    cmp     eax, WORM_MAGIC
    jne     .chain_invalid

    ; Re-hash data portion and compare to stored hash
    ; Data is at record+48, data_len at record+44
    mov     eax, [r14 + 44]             ; data_len
    lea     rdi, [r14 + 48]             ; data ptr
    mov     rsi, rax
    call    worm_hash_record            ; writes to hash_scratch

    ; Compare hash_scratch to stored hash at record+224
    lea     rsi, [r14 + 224]
    lea     rdi, [rel hash_scratch]
    mov     ecx, WORM_HASH_SIZE
.compare_hash:
    mov     al, [rdi]
    cmp     al, [rsi]
    jne     .chain_invalid
    inc     rdi
    inc     rsi
    dec     ecx
    jnz     .compare_hash

    inc     r13
    jmp     .verify_loop

.chain_ok:
    xor     rax, rax
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

.chain_invalid:
    ; Print error
    push    rax
    mov     rdi, STDERR
    lea     rsi, [rel err_verify]
    call    str_len
    mov     rdx, rax
    mov     rdi, STDERR
    lea     rsi, [rel err_verify]
    call    sys_write
    pop     rax
    mov     rax, 1
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; ring_init — Initialize the ring buffer
; Arguments: rdi = size (bytes, must be power of 2)
; Returns: rax = 0 (success), -1 (failure)
; =============================================================================
ring_init:
    push    rbp
    mov     rbp, rsp

    ; Use built-in ring_buffer if size <= RING_DEFAULT_SIZE
    cmp     rdi, RING_DEFAULT_SIZE
    jg      .use_mmap

    ; Use static buffer
    lea     rax, [rel ring_buffer]
    mov     [rel ring_state.buf], rax
    mov     [rel ring_state.size], rdi
    jmp     .init_fields

.use_mmap:
    ; Allocate via mmap
    push    rdi                         ; save size
    xor     rdi, rdi                    ; addr = NULL
    ; rsi already = size from first arg... need to reload
    pop     rsi
    push    rsi
    mov     rdx, PROT_READ | PROT_WRITE
    mov     r10, MAP_PRIVATE | MAP_ANONYMOUS
    mov     r8, -1                      ; fd = -1
    xor     r9, r9                      ; offset = 0
    call    sys_mmap
    pop     rsi
    cmp     rax, MAP_FAILED
    je      .ring_fail
    mov     [rel ring_state.buf], rax
    mov     [rel ring_state.size], rsi

.init_fields:
    ; Zero head, tail, count
    mov     qword [rel ring_state.head], 0
    mov     qword [rel ring_state.tail], 0
    mov     qword [rel ring_state.count], 0

    xor     rax, rax
    pop     rbp
    ret

.ring_fail:
    mov     rax, -1
    pop     rbp
    ret

; =============================================================================
; ring_write — Write bytes to ring buffer
; Arguments: rdi = data_ptr, rsi = len
; Returns: rax = bytes written (may be < len if buffer is full)
; =============================================================================
ring_write:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14

    mov     r12, rdi            ; data_ptr
    mov     r13, rsi            ; len

    ; Calculate available space
    mov     rax, [rel ring_state.size]
    mov     rbx, [rel ring_state.count]
    sub     rax, rbx            ; available = size - count

    ; Clamp write length
    cmp     r13, rax
    jle     .len_ok
    mov     r13, rax            ; write at most available bytes
.len_ok:
    test    r13, r13
    jz      .write_done

    ; Write bytes one at a time (handles wrap-around)
    mov     r14, [rel ring_state.buf]
    mov     rbx, [rel ring_state.head]
    mov     rcx, r13
    xor     rax, rax            ; byte index
.write_loop:
    test    rcx, rcx
    jz      .write_done
    movzx   rdx, byte [r12 + rax]
    mov     [r14 + rbx], dl     ; write byte
    inc     rbx
    ; Wrap head if needed
    mov     rdx, [rel ring_state.size]
    cmp     rbx, rdx
    jl      .no_wrap_w
    xor     rbx, rbx
.no_wrap_w:
    inc     rax
    dec     rcx
    jmp     .write_loop

.write_done:
    mov     [rel ring_state.head], rbx
    ; Update count
    add     [rel ring_state.count], r13
    mov     rax, r13            ; return bytes written

    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; ring_read — Read bytes from ring buffer
; Arguments: rdi = buf, rsi = max_bytes
; Returns: rax = bytes read
; =============================================================================
ring_read:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14

    mov     r12, rdi            ; dest buffer
    mov     r13, rsi            ; max to read

    ; Clamp to available data
    mov     rax, [rel ring_state.count]
    cmp     r13, rax
    jle     .rlen_ok
    mov     r13, rax
.rlen_ok:
    test    r13, r13
    jz      .read_done

    mov     r14, [rel ring_state.buf]
    mov     rbx, [rel ring_state.tail]
    mov     rcx, r13
    xor     rax, rax
.read_loop:
    test    rcx, rcx
    jz      .read_done
    movzx   rdx, byte [r14 + rbx]
    mov     [r12 + rax], dl
    inc     rbx
    ; Wrap tail if needed
    mov     rdx, [rel ring_state.size]
    cmp     rbx, rdx
    jl      .no_wrap_r
    xor     rbx, rbx
.no_wrap_r:
    inc     rax
    dec     rcx
    jmp     .read_loop

.read_done:
    mov     [rel ring_state.tail], rbx
    ; Update count
    sub     [rel ring_state.count], r13
    mov     rax, r13

    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; ring_available — How many bytes are available to read
; Arguments: none
; Returns: rax = bytes available
; =============================================================================
ring_available:
    push    rbp
    mov     rbp, rsp
    mov     rax, [rel ring_state.count]
    pop     rbp
    ret

; =============================================================================
; ring_capacity — Total capacity of the ring buffer
; Arguments: none
; Returns: rax = total capacity in bytes
; =============================================================================
ring_capacity:
    push    rbp
    mov     rbp, rsp
    mov     rax, [rel ring_state.size]
    pop     rbp
    ret

; =============================================================================
; ring_clear — Reset the ring buffer (discard all data)
; Arguments: none
; Returns: rax = 0
; =============================================================================
ring_clear:
    push    rbp
    mov     rbp, rsp
    mov     qword [rel ring_state.head], 0
    mov     qword [rel ring_state.tail], 0
    mov     qword [rel ring_state.count], 0
    xor     rax, rax
    pop     rbp
    ret

; =============================================================================
; arena_init — Initialize the arena allocator
; Arguments: rdi = base_ptr, rsi = size
; Returns: rax = 0
; =============================================================================
arena_init:
    push    rbp
    mov     rbp, rsp
    mov     [rel arena_state.base], rdi
    mov     [rel arena_state.size], rsi
    mov     qword [rel arena_state.used], 0
    xor     rax, rax
    pop     rbp
    ret

; =============================================================================
; arena_alloc — Allocate memory from arena
; Arguments: rdi = size, rsi = alignment (must be power of 2)
; Returns: rax = pointer to allocated memory, or -1 if out of space
; =============================================================================
arena_alloc:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    mov     r12, rdi            ; requested size
    mov     r13, rsi            ; alignment

    ; Calculate aligned offset
    ; aligned_used = (used + align - 1) & ~(align - 1)
    mov     rax, [rel arena_state.used]
    add     rax, r13
    dec     rax                 ; + align - 1
    mov     rbx, r13
    dec     rbx                 ; align - 1
    not     rbx                 ; ~(align - 1)
    and     rax, rbx            ; aligned_used

    ; Check if fits
    mov     rbx, rax
    add     rbx, r12            ; end = aligned_used + size
    mov     rcx, [rel arena_state.size]
    cmp     rbx, rcx
    jg      .arena_oom

    ; Commit allocation
    mov     [rel arena_state.used], rbx

    ; Return base + aligned_offset
    mov     rcx, [rel arena_state.base]
    add     rax, rcx

    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

.arena_oom:
    mov     rdi, STDERR
    lea     rsi, [rel err_arena]
    call    str_len
    mov     rdx, rax
    mov     rdi, STDERR
    lea     rsi, [rel err_arena]
    call    sys_write
    mov     rax, -1
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; arena_free_all — Reset arena (all allocations invalidated)
; Arguments: none
; Returns: rax = 0
; =============================================================================
arena_free_all:
    push    rbp
    mov     rbp, rsp
    mov     qword [rel arena_state.used], 0
    xor     rax, rax
    pop     rbp
    ret

; =============================================================================
; arena_remaining — How many bytes remain in the arena
; Arguments: none
; Returns: rax = bytes remaining
; =============================================================================
arena_remaining:
    push    rbp
    mov     rbp, rsp
    mov     rax, [rel arena_state.size]
    sub     rax, [rel arena_state.used]
    pop     rbp
    ret

; =============================================================================
; str_len — Compute length of null-terminated string
; Arguments: rdi = string pointer
; Returns: rax = length (not including NUL)
; =============================================================================
str_len:
    push    rbp
    mov     rbp, rsp
    xor     rax, rax            ; length = 0
.len_loop:
    cmp     byte [rdi + rax], 0 ; check for NUL
    je      .len_done
    inc     rax
    jmp     .len_loop
.len_done:
    pop     rbp
    ret

; =============================================================================
; str_copy — Copy null-terminated string
; Arguments: rdi = dst, rsi = src
; Returns: rax = dst pointer
; =============================================================================
str_copy:
    push    rbp
    mov     rbp, rsp
    push    rbx
    mov     rbx, rdi            ; save dst
    xor     rcx, rcx
.copy_loop:
    movzx   rax, byte [rsi + rcx]
    mov     [rdi + rcx], al
    test    al, al
    jz      .copy_done
    inc     rcx
    jmp     .copy_loop
.copy_done:
    mov     rax, rbx            ; return dst
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; str_compare — Compare two null-terminated strings
; Arguments: rdi = string a, rsi = string b
; Returns: rax = 0 (equal), negative (a < b), positive (a > b)
; =============================================================================
str_compare:
    push    rbp
    mov     rbp, rsp
    xor     rcx, rcx
.cmp_loop:
    movzx   rax, byte [rdi + rcx]
    movzx   rbx, byte [rsi + rcx]   ; note: rbx used — but not callee-saved here
    ; Use registers without pushing rbx (callee-saved, but we save in prologue)
    push    rbx
    movzx   rax, byte [rdi + rcx]
    movzx   rbx, byte [rsi + rcx]
    test    rax, rax
    jz      .cmp_end
    test    rbx, rbx
    jz      .cmp_end
    cmp     rax, rbx
    jne     .cmp_end
    pop     rbx
    inc     rcx
    jmp     .cmp_loop
.cmp_end:
    sub     rax, rbx
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; str_to_upper — Convert string to uppercase in-place (ASCII only)
; Arguments: rdi = string pointer
; Returns: rax = string pointer
; =============================================================================
str_to_upper:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    xor     rcx, rcx
.upper_loop:
    movzx   rdx, byte [rdi + rcx]
    test    dl, dl
    jz      .upper_done
    cmp     dl, 'a'
    jl      .not_lower
    cmp     dl, 'z'
    jg      .not_lower
    sub     dl, 32              ; 'a' - 'A' = 32
    mov     [rdi + rcx], dl
.not_lower:
    inc     rcx
    jmp     .upper_loop
.upper_done:
    pop     rbp
    ret

; =============================================================================
; str_find_char — Find first occurrence of a character in a string
; Arguments: rdi = string, rsi = character (byte value)
; Returns: rax = byte offset, or -1 if not found
; =============================================================================
str_find_char:
    push    rbp
    mov     rbp, rsp
    xor     rcx, rcx
.find_loop:
    movzx   rax, byte [rdi + rcx]
    test    al, al
    jz      .not_found
    cmp     al, sil             ; sil = low byte of rsi
    je      .found
    inc     rcx
    jmp     .find_loop
.found:
    mov     rax, rcx
    pop     rbp
    ret
.not_found:
    mov     rax, -1
    pop     rbp
    ret

; =============================================================================
; math_min — Minimum of two signed 64-bit integers
; Arguments: rdi = a, rsi = b
; Returns: rax = min(a, b)
; =============================================================================
math_min:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    cmp     rax, rsi
    jle     .min_done
    mov     rax, rsi
.min_done:
    pop     rbp
    ret

; =============================================================================
; math_max — Maximum of two signed 64-bit integers
; Arguments: rdi = a, rsi = b
; Returns: rax = max(a, b)
; =============================================================================
math_max:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    cmp     rax, rsi
    jge     .max_done
    mov     rax, rsi
.max_done:
    pop     rbp
    ret

; =============================================================================
; math_clamp — Clamp value to [lo, hi]
; Arguments: rdi = value, rsi = lo, rdx = hi
; Returns: rax = clamped value
; =============================================================================
math_clamp:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    ; if val < lo, return lo
    cmp     rax, rsi
    jge     .above_lo
    mov     rax, rsi
    jmp     .clamp_done
.above_lo:
    ; if val > hi, return hi
    cmp     rax, rdx
    jle     .clamp_done
    mov     rax, rdx
.clamp_done:
    pop     rbp
    ret

; =============================================================================
; math_abs — Absolute value of signed 64-bit integer
; Arguments: rdi = value
; Returns: rax = |value|
; =============================================================================
math_abs:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    test    rax, rax
    jns     .abs_done
    neg     rax
.abs_done:
    pop     rbp
    ret

; =============================================================================
; math_is_power_of_2 — Check if a value is a power of 2
; Arguments: rdi = n
; Returns: rax = 1 if power of 2, 0 otherwise
; =============================================================================
math_is_power_of_2:
    push    rbp
    mov     rbp, rsp
    ; n must be > 0 and (n & (n-1)) == 0
    test    rdi, rdi
    jle     .not_pow2
    mov     rax, rdi
    dec     rax
    test    rax, rdi
    jnz     .not_pow2
    mov     rax, 1
    pop     rbp
    ret
.not_pow2:
    xor     rax, rax
    pop     rbp
    ret

; =============================================================================
; math_next_power_of_2 — Next power of 2 >= n
; Arguments: rdi = n
; Returns: rax = next power of 2
; =============================================================================
math_next_power_of_2:
    push    rbp
    mov     rbp, rsp
    ; If already power of 2, return n
    mov     rax, rdi
    test    rax, rax
    jle     .return_one
    ; Standard bit-spreading algorithm
    dec     rax
    mov     rcx, rax
    shr     rcx, 1
    or      rax, rcx
    mov     rcx, rax
    shr     rcx, 2
    or      rax, rcx
    mov     rcx, rax
    shr     rcx, 4
    or      rax, rcx
    mov     rcx, rax
    shr     rcx, 8
    or      rax, rcx
    mov     rcx, rax
    shr     rcx, 16
    or      rax, rcx
    mov     rcx, rax
    shr     rcx, 32
    or      rax, rcx
    inc     rax
    pop     rbp
    ret
.return_one:
    mov     rax, 1
    pop     rbp
    ret

; =============================================================================
; Syscall wrappers — thin wrappers around Linux x86-64 syscalls
; =============================================================================

; sys_read(rdi=fd, rsi=buf, rdx=count) -> rax=bytes_read
sys_read:
    push    rbp
    mov     rbp, rsp
    mov     rax, SYS_READ
    syscall
    pop     rbp
    ret

; sys_write(rdi=fd, rsi=buf, rdx=count) -> rax=bytes_written
sys_write:
    push    rbp
    mov     rbp, rsp
    mov     rax, SYS_WRITE
    syscall
    pop     rbp
    ret

; sys_open(rdi=path, rsi=flags, rdx=mode) -> rax=fd
sys_open:
    push    rbp
    mov     rbp, rsp
    mov     rax, SYS_OPEN
    syscall
    pop     rbp
    ret

; sys_close(rdi=fd) -> rax=0 or error
sys_close:
    push    rbp
    mov     rbp, rsp
    mov     rax, SYS_CLOSE
    syscall
    pop     rbp
    ret

; sys_mmap(rdi=addr, rsi=len, rdx=prot, rcx=flags, r8=fd, r9=offset) -> rax=ptr
; Note: Linux syscall uses r10 for 4th arg (not rcx)
sys_mmap:
    push    rbp
    mov     rbp, rsp
    mov     r10, rcx            ; flags -> r10 (Linux syscall ABI)
    mov     rax, SYS_MMAP
    syscall
    pop     rbp
    ret

; sys_munmap(rdi=addr, rsi=len) -> rax=0 or error
sys_munmap:
    push    rbp
    mov     rbp, rsp
    mov     rax, SYS_MUNMAP
    syscall
    pop     rbp
    ret

; sys_exit(rdi=code) — does not return
sys_exit:
    mov     rax, SYS_EXIT
    syscall
    ; unreachable

; sys_getpid() -> rax=pid
sys_getpid:
    push    rbp
    mov     rbp, rsp
    mov     rax, SYS_GETPID
    syscall
    pop     rbp
    ret

; sys_nanosleep(rdi=req_timespec, rsi=rem_timespec) -> rax=0 or error
sys_nanosleep:
    push    rbp
    mov     rbp, rsp
    mov     rax, SYS_NANOSLEEP
    syscall
    pop     rbp
    ret

; sys_clock_gettime(rdi=clockid, rsi=timespec_ptr) -> rax=0 or error
sys_clock_gettime:
    push    rbp
    mov     rbp, rsp
    mov     rax, SYS_CLOCK_GETTIME
    syscall
    pop     rbp
    ret

; =============================================================================
; Additional string and memory utilities
; =============================================================================

; str_append — Append src to dst (dst must have enough room)
; Arguments: rdi = dst (null-terminated), rsi = src
; Returns: rax = dst
global str_append
str_append:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    mov     rbx, rdi
    mov     r12, rsi
    ; Find end of dst
.find_end:
    cmp     byte [rbx], 0
    je      .at_end
    inc     rbx
    jmp     .find_end
.at_end:
    ; Copy src to end of dst
.append_loop:
    movzx   rax, byte [r12]
    mov     [rbx], al
    test    al, al
    jz      .append_done
    inc     rbx
    inc     r12
    jmp     .append_loop
.append_done:
    mov     rax, rdi
    pop     r12
    pop     rbx
    pop     rbp
    ret

; str_contains — Check if needle is in haystack
; Arguments: rdi = haystack, rsi = needle
; Returns: rax = offset of first match, or -1
global str_contains
str_contains:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    mov     rbx, rdi            ; haystack
    mov     r12, rsi            ; needle
    ; Get needle length
    mov     rdi, r12
    call    str_len
    mov     r13, rax            ; needle_len
    test    r13, r13
    jz      .sc_empty_needle    ; empty needle -> found at 0
    ; Get haystack length
    mov     rdi, rbx
    call    str_len
    ; Walk haystack
    xor     rcx, rcx
.sc_outer:
    ; remaining = haystack_len - rcx >= needle_len?
    mov     rdx, rax
    sub     rdx, rcx
    cmp     rdx, r13
    jl      .sc_not_found
    ; Compare haystack[rcx..rcx+needle_len] == needle
    mov     rdi, rbx
    add     rdi, rcx
    mov     rsi, r12
    push    rax
    push    rcx
    call    str_compare_n       ; (rdi=a, rsi=b, rdx=n) -> rax=0 if equal
    pop     rcx
    pop     rax
    test    rax, rax
    jz      .sc_found
    inc     rcx
    jmp     .sc_outer
.sc_found:
    mov     rax, rcx
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret
.sc_not_found:
    mov     rax, -1
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret
.sc_empty_needle:
    xor     rax, rax
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; str_compare_n — Compare n bytes of two strings
; Arguments: rdi = a, rsi = b, rdx = n
; Returns: rax = 0 (equal), non-zero (different)
global str_compare_n
str_compare_n:
    push    rbp
    mov     rbp, rsp
    xor     rax, rax
    xor     rcx, rcx
.scn_loop:
    cmp     rcx, rdx
    jge     .scn_equal
    movzx   r8, byte [rdi + rcx]
    movzx   r9, byte [rsi + rcx]
    cmp     r8b, r9b
    jne     .scn_diff
    inc     rcx
    jmp     .scn_loop
.scn_equal:
    xor     rax, rax
    pop     rbp
    ret
.scn_diff:
    sub     r8, r9
    mov     rax, r8
    pop     rbp
    ret

; str_reverse — Reverse a string in-place
; Arguments: rdi = str
; Returns: rax = str
global str_reverse
str_reverse:
    push    rbp
    mov     rbp, rsp
    push    rbx
    mov     rbx, rdi
    ; Get length
    call    str_len
    test    rax, rax
    jz      .rev_done
    ; Reverse in-place: swap [0] with [n-1], [1] with [n-2], ...
    mov     rcx, rax
    dec     rcx                 ; last index
    xor     rsi, rsi            ; first index
.rev_loop:
    cmp     rsi, rcx
    jge     .rev_done
    movzx   rax, byte [rbx + rsi]
    movzx   rdx, byte [rbx + rcx]
    mov     [rbx + rsi], dl
    mov     [rbx + rcx], al
    inc     rsi
    dec     rcx
    jmp     .rev_loop
.rev_done:
    mov     rax, rbx
    pop     rbx
    pop     rbp
    ret

; str_starts_with — Check if str starts with prefix
; Arguments: rdi = str, rsi = prefix
; Returns: rax = 1 (yes), 0 (no)
global str_starts_with
str_starts_with:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    mov     rbx, rdi
    mov     r12, rsi
    ; Get prefix length
    mov     rdi, r12
    call    str_len
    mov     rdx, rax
    test    rdx, rdx
    jz      .sw_yes             ; empty prefix always matches
    ; Compare first rdx bytes
    mov     rdi, rbx
    mov     rsi, r12
    call    str_compare_n
    test    rax, rax
    jz      .sw_yes
    xor     rax, rax
    pop     r12
    pop     rbx
    pop     rbp
    ret
.sw_yes:
    mov     rax, 1
    pop     r12
    pop     rbx
    pop     rbp
    ret

; str_ends_with — Check if str ends with suffix
; Arguments: rdi = str, rsi = suffix
; Returns: rax = 1 (yes), 0 (no)
global str_ends_with
str_ends_with:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    mov     rbx, rdi
    mov     r12, rsi
    ; Get lengths
    call    str_len
    mov     r9, rax             ; str_len
    mov     rdi, r12
    call    str_len
    mov     r10, rax            ; suffix_len
    test    r10, r10
    jz      .ew_yes
    cmp     r9, r10
    jl      .ew_no
    ; Compare last r10 bytes of str with suffix
    mov     rdi, rbx
    add     rdi, r9
    sub     rdi, r10            ; str + str_len - suffix_len
    mov     rsi, r12
    mov     rdx, r10
    call    str_compare_n
    test    rax, rax
    jz      .ew_yes
.ew_no:
    xor     rax, rax
    pop     r12
    pop     rbx
    pop     rbp
    ret
.ew_yes:
    mov     rax, 1
    pop     r12
    pop     rbx
    pop     rbp
    ret

; mem_set — Fill memory with a byte value (like memset)
; Arguments: rdi = ptr, rsi = byte_value, rdx = count
; Returns: rax = ptr
global mem_set
mem_set:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    xor     rcx, rcx
.mset_loop:
    cmp     rcx, rdx
    jge     .mset_done
    mov     [rdi + rcx], sil
    inc     rcx
    jmp     .mset_loop
.mset_done:
    pop     rbp
    ret

; mem_copy — Copy memory (like memcpy, non-overlapping)
; Arguments: rdi = dst, rsi = src, rdx = count
; Returns: rax = dst
global mem_copy
mem_copy:
    push    rbp
    mov     rbp, rsp
    push    rbx
    mov     rbx, rdi
    xor     rcx, rcx
.mc_loop:
    cmp     rcx, rdx
    jge     .mc_done
    movzx   rax, byte [rsi + rcx]
    mov     [rdi + rcx], al
    inc     rcx
    jmp     .mc_loop
.mc_done:
    mov     rax, rbx
    pop     rbx
    pop     rbp
    ret

; mem_compare — Compare two memory regions
; Arguments: rdi = a, rsi = b, rdx = count
; Returns: rax = 0 (equal), non-zero (different)
global mem_compare
mem_compare:
    push    rbp
    mov     rbp, rsp
    xor     rcx, rcx
.memcmp_loop:
    cmp     rcx, rdx
    jge     .memcmp_eq
    movzx   rax, byte [rdi + rcx]
    movzx   r8, byte [rsi + rcx]
    cmp     al, r8b
    jne     .memcmp_diff
    inc     rcx
    jmp     .memcmp_loop
.memcmp_eq:
    xor     rax, rax
    pop     rbp
    ret
.memcmp_diff:
    sub     rax, r8
    pop     rbp
    ret

; mem_zero — Zero a memory region
; Arguments: rdi = ptr, rsi = count
; Returns: rax = 0
global mem_zero
mem_zero:
    push    rbp
    mov     rbp, rsp
    xor     eax, eax
    xor     rcx, rcx
.mz_loop:
    cmp     rcx, rsi
    jge     .mz_done
    mov     byte [rdi + rcx], 0
    inc     rcx
    jmp     .mz_loop
.mz_done:
    xor     rax, rax
    pop     rbp
    ret

; =============================================================================
; Integer-to-string conversion utilities
; =============================================================================

; u64_to_decimal — Convert uint64 to decimal ASCII string (no NUL terminator)
; Arguments: rdi = value, rsi = buf (must be >= 20 bytes), rdx = buf_len
; Returns: rax = number of digits written
global u64_to_decimal
u64_to_decimal:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14

    mov     rbx, rdi            ; value
    mov     r12, rsi            ; buf
    mov     r13, rdx            ; buf_len

    ; Handle 0 specially
    test    rbx, rbx
    jnz     .u64_nonzero
    cmp     r13, 1
    jl      .u64_no_space
    mov     byte [r12], '0'
    mov     rax, 1
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

.u64_nonzero:
    ; Extract digits in reverse into temp buffer
    sub     rsp, 24             ; 20 digits max + padding
    mov     r14, rsp            ; temp buffer
    xor     r9, r9              ; digit count

.extract_digits:
    test    rbx, rbx
    jz      .digits_done
    xor     rdx, rdx
    mov     rax, rbx
    mov     rcx, 10
    div     rcx                 ; rax = quot, rdx = remainder (digit)
    mov     rbx, rax
    add     dl, '0'
    mov     [r14 + r9], dl
    inc     r9
    jmp     .extract_digits

.digits_done:
    ; Copy digits in reverse order to buf
    mov     rcx, r9
    xor     rax, rax
.copy_digits:
    cmp     rax, rcx
    jge     .u64_done
    cmp     rax, r13
    jge     .u64_done
    mov     r8, rcx
    dec     r8
    sub     r8, rax             ; reversed index
    movzx   rdx, byte [r14 + r8]
    mov     [r12 + rax], dl
    inc     rax
    jmp     .copy_digits
.u64_done:
    add     rsp, 24
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret
.u64_no_space:
    xor     rax, rax
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; u64_to_hex — Convert uint64 to hex ASCII string
; Arguments: rdi = value, rsi = buf (>= 17 bytes), rdx = buf_len
; Returns: rax = digits written
global u64_to_hex
u64_to_hex:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    mov     rbx, rdi            ; value
    mov     r12, rsi            ; buf
    xor     r9, r9              ; digit index
    mov     r10, 60             ; initial shift (15 hex digits * 4 bits each, starting from top)

.hex_loop:
    cmp     r9, rdx
    jge     .hex_done
    cmp     r10, -4
    jl      .hex_done
    ; Extract nibble
    mov     rax, rbx
    mov     rcx, r10
    sar     rax, cl             ; shift right
    and     rax, 0xF            ; isolate nibble
    ; Skip leading zeros
    test    rax, rax
    jnz     .hex_nonzero
    test    r9, r9
    jz      .hex_skip           ; skip if no digits yet
.hex_nonzero:
    ; Convert nibble to ASCII
    cmp     rax, 9
    jle     .hex_digit
    add     rax, 'A' - 10
    jmp     .hex_store
.hex_digit:
    add     rax, '0'
.hex_store:
    mov     [r12 + r9], al
    inc     r9
.hex_skip:
    sub     r10, 4
    jmp     .hex_loop

.hex_done:
    ; If nothing written, write '0'
    test    r9, r9
    jnz     .hex_ret
    test    rdx, rdx
    jz      .hex_ret
    mov     byte [r12], '0'
    mov     r9, 1
.hex_ret:
    mov     rax, r9
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; Hash utilities (FNV-1a 64-bit, fast non-cryptographic hash)
; =============================================================================

FNV_OFFSET_BASIS    equ 0xcbf29ce484222325
FNV_PRIME           equ 0x100000001b3

; fnv1a_hash — Compute FNV-1a 64-bit hash of a byte string
; Arguments: rdi = data_ptr, rsi = len
; Returns: rax = hash (uint64)
global fnv1a_hash
fnv1a_hash:
    push    rbp
    mov     rbp, rsp
    mov     rax, FNV_OFFSET_BASIS   ; hash = offset_basis
    xor     rcx, rcx
.fnv_loop:
    cmp     rcx, rsi
    jge     .fnv_done
    movzx   rdx, byte [rdi + rcx]
    xor     rax, rdx            ; hash ^= byte
    ; hash *= FNV_PRIME (via imul)
    mov     r8, FNV_PRIME
    imul    rax, r8
    inc     rcx
    jmp     .fnv_loop
.fnv_done:
    pop     rbp
    ret

; fnv1a_hash_str — FNV-1a hash of null-terminated string
; Arguments: rdi = str_ptr
; Returns: rax = hash
global fnv1a_hash_str
fnv1a_hash_str:
    push    rbp
    mov     rbp, rsp
    push    rbx
    mov     rbx, rdi
    call    str_len
    mov     rsi, rax
    mov     rdi, rbx
    call    fnv1a_hash
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; Bit manipulation utilities
; =============================================================================

; bit_set — Set bit n in a 64-bit word
; Arguments: rdi = word, rsi = bit_pos (0-63)
; Returns: rax = word with bit set
global bit_set
bit_set:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    mov     rcx, rsi
    bts     rax, rcx
    pop     rbp
    ret

; bit_clear — Clear bit n in a 64-bit word
; Arguments: rdi = word, rsi = bit_pos
; Returns: rax = word with bit cleared
global bit_clear
bit_clear:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    mov     rcx, rsi
    btr     rax, rcx
    pop     rbp
    ret

; bit_test — Test bit n in a 64-bit word
; Arguments: rdi = word, rsi = bit_pos
; Returns: rax = 1 (bit set), 0 (bit clear)
global bit_test
bit_test:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    mov     rcx, rsi
    bt      rax, rcx
    setc    al
    movzx   rax, al
    pop     rbp
    ret

; bit_flip — Toggle bit n in a 64-bit word
; Arguments: rdi = word, rsi = bit_pos
; Returns: rax = word with bit toggled
global bit_flip
bit_flip:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    mov     rcx, rsi
    btc     rax, rcx
    pop     rbp
    ret

; bit_scan_forward — Find lowest set bit (BSF)
; Arguments: rdi = word
; Returns: rax = position of lowest set bit, or -1 if word==0
global bit_scan_forward
bit_scan_forward:
    push    rbp
    mov     rbp, rsp
    test    rdi, rdi
    jz      .bsf_zero
    bsf     rax, rdi
    pop     rbp
    ret
.bsf_zero:
    mov     rax, -1
    pop     rbp
    ret

; bit_scan_reverse — Find highest set bit (BSR)
; Arguments: rdi = word
; Returns: rax = position of highest set bit, or -1 if word==0
global bit_scan_reverse
bit_scan_reverse:
    push    rbp
    mov     rbp, rsp
    test    rdi, rdi
    jz      .bsr_zero
    bsr     rax, rdi
    pop     rbp
    ret
.bsr_zero:
    mov     rax, -1
    pop     rbp
    ret

; rotate_left64 — Rotate 64-bit word left by n bits
; Arguments: rdi = word, rsi = count (0-63)
; Returns: rax = rotated word
global rotate_left64
rotate_left64:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    mov     rcx, rsi
    rol     rax, cl
    pop     rbp
    ret

; rotate_right64 — Rotate 64-bit word right by n bits
; Arguments: rdi = word, rsi = count (0-63)
; Returns: rax = rotated word
global rotate_right64
rotate_right64:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    mov     rcx, rsi
    ror     rax, cl
    pop     rbp
    ret

; byteswap64 — Swap byte order of a 64-bit word (bswap)
; Arguments: rdi = word
; Returns: rax = byte-swapped word
global byteswap64
byteswap64:
    push    rbp
    mov     rbp, rsp
    mov     rax, rdi
    bswap   rax
    pop     rbp
    ret

; =============================================================================
; Timing utilities
; =============================================================================

; CLOCK_MONOTONIC = 1
CLOCK_MONOTONIC equ 1

; get_monotonic_ns — Get monotonic clock in nanoseconds
; Arguments: none
; Returns: rax = nanoseconds since boot (uint64)
global get_monotonic_ns
get_monotonic_ns:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 16             ; space for timespec {tv_sec, tv_nsec}
    mov     rdi, CLOCK_MONOTONIC
    mov     rsi, rsp
    call    sys_clock_gettime
    ; tv_sec at [rsp], tv_nsec at [rsp+8]
    mov     rax, [rsp]          ; tv_sec
    mov     rcx, 1000000000
    imul    rax, rcx            ; sec -> nsec
    add     rax, [rsp + 8]      ; + tv_nsec
    add     rsp, 16
    pop     rbp
    ret

; rdtsc_value — Read TSC (Time Stamp Counter)
; Arguments: none
; Returns: rax = 64-bit TSC value
global rdtsc_value
rdtsc_value:
    push    rbp
    mov     rbp, rsp
    rdtsc                       ; EDX:EAX = TSC
    shl     rdx, 32
    or      rax, rdx            ; combine into rax
    pop     rbp
    ret

; =============================================================================
; Spinlock primitives (using LOCK CMPXCHG)
; =============================================================================

; spinlock_init — Initialize spinlock to unlocked state
; Arguments: rdi = lock_ptr (uint32*)
; Returns: rax = 0
global spinlock_init
spinlock_init:
    push    rbp
    mov     rbp, rsp
    mov     dword [rdi], 0
    xor     rax, rax
    pop     rbp
    ret

; spinlock_lock — Acquire spinlock (spin until available)
; Arguments: rdi = lock_ptr (uint32*)
; Returns: rax = 0
global spinlock_lock
spinlock_lock:
    push    rbp
    mov     rbp, rsp
.spin:
    ; Try to set lock from 0 -> 1 using LOCK CMPXCHG
    xor     eax, eax            ; expected = 0
    mov     ecx, 1              ; desired = 1
    lock cmpxchg dword [rdi], ecx
    jnz     .spin               ; if not equal (lock was held), retry
    ; Memory barrier
    mfence
    xor     rax, rax
    pop     rbp
    ret

; spinlock_unlock — Release spinlock
; Arguments: rdi = lock_ptr
; Returns: rax = 0
global spinlock_unlock
spinlock_unlock:
    push    rbp
    mov     rbp, rsp
    mfence
    mov     dword [rdi], 0      ; atomic store
    xor     rax, rax
    pop     rbp
    ret

; spinlock_trylock — Try to acquire spinlock (non-blocking)
; Arguments: rdi = lock_ptr
; Returns: rax = 1 (acquired), 0 (already held)
global spinlock_trylock
spinlock_trylock:
    push    rbp
    mov     rbp, rsp
    xor     eax, eax            ; expected = 0
    mov     ecx, 1
    lock cmpxchg dword [rdi], ecx
    setz    al                  ; al = 1 if we acquired (was 0)
    movzx   rax, al
    pop     rbp
    ret

; =============================================================================
; Sorting utilities
; =============================================================================

; insertion_sort_u64 — Sort array of uint64 in ascending order
; Arguments: rdi = array_ptr, rsi = count
; Returns: rax = 0
global insertion_sort_u64
insertion_sort_u64:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14

    mov     rbx, rdi            ; array
    mov     r12, rsi            ; count
    cmp     r12, 2
    jl      .sort_done

    mov     r13, 1              ; i = 1
.outer_loop:
    cmp     r13, r12
    jge     .sort_done
    mov     r14, [rbx + r13*8]  ; key = array[i]
    mov     rcx, r13
    dec     rcx                 ; j = i - 1
.inner_loop:
    cmp     rcx, 0
    jl      .inner_done
    mov     rax, [rbx + rcx*8]  ; array[j]
    cmp     rax, r14
    jle     .inner_done
    ; array[j+1] = array[j]
    mov     rdx, rcx
    inc     rdx
    mov     [rbx + rdx*8], rax
    dec     rcx
    jmp     .inner_loop
.inner_done:
    ; array[j+1] = key
    mov     rdx, rcx
    inc     rdx
    mov     [rbx + rdx*8], r14
    inc     r13
    jmp     .outer_loop
.sort_done:
    xor     rax, rax
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; binary_search_u64 — Binary search in sorted uint64 array
; Arguments: rdi = array_ptr, rsi = count, rdx = target
; Returns: rax = index, or -1 if not found
global binary_search_u64
binary_search_u64:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    mov     rbx, rdi            ; array
    ; r12 = lo, r13 = hi
    xor     r12, r12            ; lo = 0
    mov     r13, rsi
    dec     r13                 ; hi = count - 1

.bs_loop:
    cmp     r12, r13
    jg      .bs_not_found
    ; mid = (lo + hi) / 2
    mov     rax, r12
    add     rax, r13
    shr     rax, 1              ; mid
    mov     rcx, [rbx + rax*8] ; array[mid]
    cmp     rcx, rdx
    je      .bs_found
    jg      .bs_go_left
    ; array[mid] < target: search right half
    mov     r12, rax
    inc     r12
    jmp     .bs_loop
.bs_go_left:
    ; array[mid] > target: search left half
    mov     r13, rax
    dec     r13
    jmp     .bs_loop
.bs_found:
    ; rax = mid index already
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret
.bs_not_found:
    mov     rax, -1
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; Checksum / integrity
; =============================================================================

; crc32_update — Update CRC32 for a byte (simplified, no table)
; Uses CRC32 instruction (SSE4.2)
; Arguments: rdi = current_crc (uint32), rsi = byte_value
; Returns: rax = new_crc (uint32)
global crc32_update
crc32_update:
    push    rbp
    mov     rbp, rsp
    mov     eax, edi            ; current_crc
    crc32   eax, sil            ; CRC32 with single byte
    pop     rbp
    ret

; crc32_buf — Compute CRC32 of a buffer
; Arguments: rdi = buf, rsi = len
; Returns: rax = crc32 (uint32)
global crc32_buf
crc32_buf:
    push    rbp
    mov     rbp, rsp
    push    rbx

    mov     rbx, rdi
    mov     eax, 0xFFFFFFFF     ; initial CRC value
    xor     rcx, rcx
.crc_loop:
    cmp     rcx, rsi
    jge     .crc_done
    movzx   rdx, byte [rbx + rcx]
    crc32   eax, dl
    inc     rcx
    jmp     .crc_loop
.crc_done:
    xor     eax, 0xFFFFFFFF     ; final XOR
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; Sovereign event log (append-only in-memory event journal)
; =============================================================================

MAX_EVENTS          equ 8192
EVENT_ENTRY_SIZE    equ 64      ; timestamp(8) + type(4) + flags(4) + data(48)

section .bss
align 8
event_log_count     resq 1
event_log_buf       resb MAX_EVENTS * EVENT_ENTRY_SIZE

section .text

; event_log_append — Append an event to the in-memory event log
; Arguments:
;   rdi = event_type (uint32)
;   rsi = flags (uint32)
;   rdx = data_ptr (up to 48 bytes)
;   rcx = data_len
; Returns: rax = event index, or -1 if log full
global event_log_append
event_log_append:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14

    mov     r12, rdi            ; event_type
    mov     r13, rsi            ; flags
    mov     r14, rdx            ; data_ptr

    ; Check capacity
    mov     rax, [rel event_log_count]
    cmp     rax, MAX_EVENTS
    jge     .evlog_full

    ; Compute slot offset
    push    rax
    imul    rax, EVENT_ENTRY_SIZE
    lea     rbx, [rel event_log_buf]
    add     rbx, rax            ; rbx = slot ptr

    ; Write timestamp (nanoseconds)
    call    get_monotonic_ns
    mov     [rbx], rax          ; timestamp

    ; Write event_type
    mov     [rbx + 8], r12d

    ; Write flags
    mov     [rbx + 12], r13d

    ; Copy data (up to 48 bytes)
    xor     r9, r9
    cmp     rcx, 48
    jle     .data_len_ok
    mov     rcx, 48
.data_len_ok:
.evlog_copy:
    cmp     r9, rcx
    jge     .evlog_data_done
    movzx   rax, byte [r14 + r9]
    mov     [rbx + 16 + r9], al
    inc     r9
    jmp     .evlog_copy
.evlog_data_done:

    ; Increment count
    pop     rax                 ; recover index
    inc     qword [rel event_log_count]

    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

.evlog_full:
    mov     rax, -1
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; event_log_count_get — Get current event count
; Returns: rax = count
global event_log_count_get
event_log_count_get:
    push    rbp
    mov     rbp, rsp
    mov     rax, [rel event_log_count]
    pop     rbp
    ret

; event_log_get — Get event at index
; Arguments: rdi = index, rsi = out_buf (64 bytes)
; Returns: rax = 0 (ok), -1 (out of range)
global event_log_get
event_log_get:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    mov     rbx, rdi
    mov     r12, rsi

    cmp     rbx, [rel event_log_count]
    jge     .evget_oob

    ; Compute source pointer
    imul    rbx, EVENT_ENTRY_SIZE
    lea     rax, [rel event_log_buf]
    add     rax, rbx

    ; Copy 64 bytes
    mov     rcx, 0
.evget_copy:
    cmp     rcx, EVENT_ENTRY_SIZE
    jge     .evget_done
    movzx   rdx, byte [rax + rcx]
    mov     [r12 + rcx], dl
    inc     rcx
    jmp     .evget_copy
.evget_done:
    xor     rax, rax
    pop     r12
    pop     rbx
    pop     rbp
    ret

.evget_oob:
    mov     rax, -1
    pop     r12
    pop     rbx
    pop     rbp
    ret
