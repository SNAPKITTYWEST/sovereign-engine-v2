; =============================================================================
; ipc_dispatcher.asm — IPC Dispatcher (x86-64 NASM, Linux)
; Shared-memory polling + opcode dispatch in pure assembly.
; Mirrors the C dispatcher in native/dispatcher/ipc_core.c
; =============================================================================
; Packet layout (12-byte header):
;   [0..3]  magic    (uint32) = DISP_MAGIC
;   [4..5]  opcode   (uint16)
;   [6..7]  flags    (uint16)
;   [8..11] payload_len (uint32)
;   [12..]  payload data
; =============================================================================

bits 64
default rel

; ─── Constants ─────────────────────────────────────────────────────────────────
DISP_MAGIC      equ 0x50534944  ; 'DISP' little-endian
RESP_MAGIC      equ 0x50534552  ; 'RESP' little-endian
HEADER_SIZE     equ 12          ; magic(4)+opcode(2)+flags(2)+payload_len(4)
RING_SIZE       equ 65536       ; 64 KB ring buffer
POLL_USEC       equ 50          ; 50 microsecond poll interval

; ─── Packet offsets ───────────────────────────────────────────────────────────
PKT_MAGIC       equ 0
PKT_OPCODE      equ 4
PKT_FLAGS       equ 6
PKT_PAYLOAD_LEN equ 8
PKT_PAYLOAD     equ 12

; ─── Opcode constants ─────────────────────────────────────────────────────────
OP_NOP                  equ 0x0000
OP_FILESYSTEM_READ      equ 0x0001
OP_FILESYSTEM_WRITE     equ 0x0002
OP_FILESYSTEM_STAT      equ 0x0003
OP_FILESYSTEM_LIST      equ 0x0004
OP_PROCESS_SPAWN        equ 0x0005
OP_PROCESS_KILL         equ 0x0006
OP_PROCESS_LIST         equ 0x0007
OP_MEMORY_ALLOC         equ 0x0008
OP_GIT_STATUS           equ 0x0009
OP_GIT_COMMIT           equ 0x000A
OP_GIT_PUSH             equ 0x000B
OP_WORM_APPEND          equ 0x0010
OP_WORM_VERIFY          equ 0x0011
OP_QRA_ROUTE            equ 0x0020
OP_ENTROPY_CHECK        equ 0x0021
OP_SHUTDOWN             equ 0xFFFF

; ─── Flag bits ────────────────────────────────────────────────────────────────
FLAG_REPLY_EXPECTED     equ 0x0001
FLAG_URGENT             equ 0x0002
FLAG_ENCRYPTED          equ 0x0004

; ─── Response codes ───────────────────────────────────────────────────────────
RESP_OK                 equ 0x00000000
RESP_ERR_UNKNOWN_OP     equ 0x00000001
RESP_ERR_INVALID_PKT    equ 0x00000002
RESP_ERR_INTERNAL       equ 0x00000003
RESP_ERR_TOO_LARGE      equ 0x00000004

; ─── SHM layout ───────────────────────────────────────────────────────────────
; The shared memory block is:
;   [0..3]   control_magic   = DISP_MAGIC
;   [4..7]   flags           (ready bit = bit 0)
;   [8..11]  packet_len
;   [12..HEADER_SIZE+payload-1]  incoming packet
;   [32768..65535]  response area
SHM_CONTROL_MAGIC   equ 0
SHM_CONTROL_FLAGS   equ 4
SHM_CONTROL_PKTLEN  equ 8
SHM_INCOMING        equ 12
SHM_RESPONSE_OFFSET equ 32768
SHM_FLAG_READY      equ 0x00000001
SHM_FLAG_PROCESSED  equ 0x00000002

; ─── Syscall numbers ──────────────────────────────────────────────────────────
SYS_WRITE       equ 1
SYS_MMAP        equ 9
SYS_MUNMAP      equ 11
SYS_NANOSLEEP   equ 35
SYS_EXIT        equ 60

PROT_READ       equ 0x1
PROT_WRITE      equ 0x2
MAP_PRIVATE     equ 0x2
MAP_ANONYMOUS   equ 0x20

; =============================================================================
; .data
; =============================================================================
section .data

msg_ipc_init    db  "IPC dispatcher initialized.", 0x0A, 0
msg_ipc_poll    db  "IPC polling...", 0x0A, 0
msg_pkt_ready   db  "IPC: packet ready.", 0x0A, 0
msg_bad_magic   db  "IPC: bad magic bytes, dropping.", 0x0A, 0
msg_unknown_op  db  "IPC: unknown opcode.", 0x0A, 0
msg_dispatch_ok db  "IPC: dispatch ok.", 0x0A, 0
msg_shutdown    db  "IPC: shutdown received.", 0x0A, 0
msg_fs_read     db  "HANDLER: filesystem_read", 0x0A, 0
msg_fs_write    db  "HANDLER: filesystem_write", 0x0A, 0
msg_fs_stat     db  "HANDLER: filesystem_stat", 0x0A, 0
msg_fs_list     db  "HANDLER: filesystem_list", 0x0A, 0
msg_proc_spawn  db  "HANDLER: process_spawn", 0x0A, 0
msg_proc_kill   db  "HANDLER: process_kill", 0x0A, 0
msg_proc_list   db  "HANDLER: process_list", 0x0A, 0
msg_mem_alloc   db  "HANDLER: memory_alloc", 0x0A, 0
msg_git_status  db  "HANDLER: git_status", 0x0A, 0
msg_git_commit  db  "HANDLER: git_commit", 0x0A, 0
msg_git_push    db  "HANDLER: git_push", 0x0A, 0
msg_worm_app    db  "HANDLER: worm_append", 0x0A, 0
msg_worm_ver    db  "HANDLER: worm_verify", 0x0A, 0
msg_qra_route   db  "HANDLER: qra_route", 0x0A, 0
msg_entropy_chk db  "HANDLER: entropy_check", 0x0A, 0

; Nanosleep timespec for POLL_USEC = 50 microseconds
; struct timespec { time_t tv_sec; long tv_nsec; }
align 8
poll_timespec:
    dq  0                       ; tv_sec = 0
    dq  50000                   ; tv_nsec = 50,000 ns = 50 us

; =============================================================================
; .bss
; =============================================================================
section .bss

; IPC state block
align 8
ipc_state:
    .shm_ptr        resq 1      ; pointer to shared memory
    .shm_size       resq 1      ; size of shared memory
    .initialized    resb 1
    resb 7                      ; pad

; Receive / send buffers
align 16
ipc_recv_buf    resb 65536      ; 64 KB receive buffer
ipc_send_buf    resb 65536      ; 64 KB send buffer

; Opcode jump table (256 entries x 8 bytes = 2048 bytes)
align 8
opcode_table    resq 256

; Dispatch statistics
align 8
ipc_stats:
    .packets_rx     resq 1
    .packets_tx     resq 1
    .errors         resq 1
    .unknown_ops    resq 1

; =============================================================================
; .text
; =============================================================================
section .text

extern sys_write
extern sys_nanosleep
extern sys_mmap
extern sys_munmap
extern str_len
extern worm_append
extern worm_verify_chain
extern qra_next
extern qra_evolve_witness
extern entropy_check

global ipc_init
global ipc_poll
global ipc_read_packet
global ipc_write_response
global ipc_clear_packet
global ipc_validate_magic
global ipc_get_opcode
global ipc_get_payload_len
global dispatch_loop
global dispatch_opcode
global handler_filesystem_read
global handler_filesystem_write
global handler_git_status

; =============================================================================
; ipc_init — Initialize IPC subsystem
; Allocates shared memory region and initializes opcode jump table.
; Arguments: none
; Returns: rax = 0 (success), -1 (failure)
; =============================================================================
ipc_init:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12

    ; Allocate shared memory (private anonymous mmap for now)
    xor     rdi, rdi            ; addr = NULL
    mov     rsi, RING_SIZE      ; size = 64KB
    mov     rdx, PROT_READ | PROT_WRITE
    mov     r10, MAP_PRIVATE | MAP_ANONYMOUS
    mov     r8, -1              ; fd = -1
    xor     r9, r9              ; offset = 0
    mov     rax, SYS_MMAP
    syscall
    mov     r12, rax
    cmp     r12, -1
    je      .ipc_fail

    ; Store shm pointer
    mov     [rel ipc_state.shm_ptr], r12
    mov     qword [rel ipc_state.shm_size], RING_SIZE

    ; Initialize control area
    mov     dword [r12 + SHM_CONTROL_MAGIC], DISP_MAGIC
    mov     dword [r12 + SHM_CONTROL_FLAGS], 0
    mov     dword [r12 + SHM_CONTROL_PKTLEN], 0

    ; Build opcode jump table: default all to handler_unknown
    lea     rbx, [rel opcode_table]
    mov     ecx, 256
.fill_table:
    lea     rax, [rel handler_unknown]
    mov     [rbx], rax
    add     rbx, 8
    dec     ecx
    jnz     .fill_table

    ; Wire known opcodes
    lea     rbx, [rel opcode_table]
    lea     rax, [rel handler_nop]
    mov     [rbx + OP_NOP * 8], rax

    lea     rax, [rel handler_filesystem_read]
    mov     [rbx + OP_FILESYSTEM_READ * 8], rax

    lea     rax, [rel handler_filesystem_write]
    mov     [rbx + OP_FILESYSTEM_WRITE * 8], rax

    lea     rax, [rel handler_filesystem_stat]
    mov     [rbx + OP_FILESYSTEM_STAT * 8], rax

    lea     rax, [rel handler_filesystem_list]
    mov     [rbx + OP_FILESYSTEM_LIST * 8], rax

    lea     rax, [rel handler_process_spawn]
    mov     [rbx + OP_PROCESS_SPAWN * 8], rax

    lea     rax, [rel handler_process_kill]
    mov     [rbx + OP_PROCESS_KILL * 8], rax

    lea     rax, [rel handler_process_list]
    mov     [rbx + OP_PROCESS_LIST * 8], rax

    lea     rax, [rel handler_memory_alloc]
    mov     [rbx + OP_MEMORY_ALLOC * 8], rax

    lea     rax, [rel handler_git_status]
    mov     [rbx + OP_GIT_STATUS * 8], rax

    lea     rax, [rel handler_git_commit]
    mov     [rbx + OP_GIT_COMMIT * 8], rax

    lea     rax, [rel handler_git_push]
    mov     [rbx + OP_GIT_PUSH * 8], rax

    lea     rax, [rel handler_worm_append]
    mov     [rbx + OP_WORM_APPEND * 8], rax

    lea     rax, [rel handler_worm_verify]
    mov     [rbx + OP_WORM_VERIFY * 8], rax

    lea     rax, [rel handler_qra_route]
    mov     [rbx + OP_QRA_ROUTE * 8], rax

    lea     rax, [rel handler_entropy_check]
    mov     [rbx + OP_ENTROPY_CHECK * 8], rax

    lea     rax, [rel handler_shutdown]
    mov     [rbx + OP_SHUTDOWN * 8], rax

    ; Mark initialized
    mov     byte [rel ipc_state.initialized], 1

    ; Print init message
    mov     rdi, 1
    lea     rsi, [rel msg_ipc_init]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_ipc_init]
    call    sys_write

    xor     rax, rax
    pop     r12
    pop     rbx
    pop     rbp
    ret

.ipc_fail:
    mov     rax, -1
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; ipc_poll — Poll shared memory for an incoming dispatch packet
; Checks the READY flag in the control area.
; Arguments: none
; Returns: rax = 1 (packet ready), 0 (no packet)
; =============================================================================
ipc_poll:
    push    rbp
    mov     rbp, rsp

    ; Load shm pointer
    mov     rax, [rel ipc_state.shm_ptr]
    test    rax, rax
    jz      .poll_none

    ; Read control flags
    mov     eax, [rax + SHM_CONTROL_FLAGS]
    test    eax, SHM_FLAG_READY
    jnz     .poll_ready

.poll_none:
    xor     rax, rax
    pop     rbp
    ret

.poll_ready:
    mov     rax, 1
    pop     rbp
    ret

; =============================================================================
; ipc_read_packet — Read and parse dispatch packet from shared memory
; Copies the packet from shm into the provided buffer.
; Arguments: rdi = buf (destination buffer, at least 64KB)
; Returns: rax = opcode (or -1 on invalid packet)
; =============================================================================
ipc_read_packet:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    mov     r12, rdi            ; dest buffer

    ; Load shm pointer
    mov     rbx, [rel ipc_state.shm_ptr]
    test    rbx, rbx
    jz      .read_fail

    ; Get packet length
    mov     eax, [rbx + SHM_CONTROL_PKTLEN]
    test    eax, eax
    jz      .read_fail
    cmp     eax, RING_SIZE
    jg      .read_fail
    mov     r13d, eax           ; packet_len

    ; Copy packet from shm incoming area to buf
    lea     rsi, [rbx + SHM_INCOMING]
    mov     rdi, r12
    mov     ecx, r13d
.copy_pkt:
    test    ecx, ecx
    jz      .copy_done
    mov     al, [rsi]
    mov     [rdi], al
    inc     rsi
    inc     rdi
    dec     ecx
    jmp     .copy_pkt
.copy_done:

    ; Validate magic
    mov     rdi, r12
    call    ipc_validate_magic
    test    rax, rax
    jz      .read_fail

    ; Extract opcode
    mov     rdi, r12
    call    ipc_get_opcode      ; rax = opcode

    ; Update stats
    inc     qword [rel ipc_stats.packets_rx]

    ; Clear the ready flag (mark as being processed)
    mov     rdx, [rel ipc_state.shm_ptr]
    and     dword [rdx + SHM_CONTROL_FLAGS], ~SHM_FLAG_READY

    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

.read_fail:
    inc     qword [rel ipc_stats.errors]
    mov     rax, -1
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; ipc_write_response — Write a response packet to the response area
; Arguments: rdi = buf (response data), rsi = len, rdx = opcode
; Returns: rax = 0 (success), -1 (failure)
; =============================================================================
ipc_write_response:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14

    mov     r12, rdi            ; response buf
    mov     r13, rsi            ; len
    mov     r14, rdx            ; opcode

    ; Get shm pointer
    mov     rbx, [rel ipc_state.shm_ptr]
    test    rbx, rbx
    jz      .resp_fail

    ; Calculate response area start
    lea     rbx, [rbx + SHM_RESPONSE_OFFSET]

    ; Write response header
    mov     dword [rbx + PKT_MAGIC], RESP_MAGIC
    mov     word  [rbx + PKT_OPCODE], r14w
    mov     word  [rbx + PKT_FLAGS], 0
    mov     dword [rbx + PKT_PAYLOAD_LEN], r13d

    ; Copy response payload
    lea     rdi, [rbx + PKT_PAYLOAD]
    mov     rsi, r12
    mov     rcx, r13
    cmp     rcx, 32768 - HEADER_SIZE
    jle     .do_copy
    mov     rcx, 32768 - HEADER_SIZE   ; clamp to available space
.do_copy:
    test    rcx, rcx
    jz      .resp_done
.resp_copy:
    mov     al, [rsi]
    mov     [rdi], al
    inc     rsi
    inc     rdi
    dec     rcx
    jnz     .resp_copy

.resp_done:
    ; Set the PROCESSED flag in control
    mov     rbx, [rel ipc_state.shm_ptr]
    or      dword [rbx + SHM_CONTROL_FLAGS], SHM_FLAG_PROCESSED

    inc     qword [rel ipc_stats.packets_tx]
    xor     rax, rax
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

.resp_fail:
    mov     rax, -1
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; ipc_clear_packet — Zero the first HEADER_SIZE bytes of packet buffer
; Arguments: rdi = packet_ptr
; Returns: rax = 0
; =============================================================================
ipc_clear_packet:
    push    rbp
    mov     rbp, rsp
    ; Zero 12 bytes (3 dwords)
    mov     dword [rdi],     0
    mov     dword [rdi + 4], 0
    mov     dword [rdi + 8], 0
    xor     rax, rax
    pop     rbp
    ret

; =============================================================================
; ipc_validate_magic — Validate packet magic bytes
; Arguments: rdi = packet_ptr
; Returns: rax = 1 (valid), 0 (invalid)
; =============================================================================
ipc_validate_magic:
    push    rbp
    mov     rbp, rsp
    mov     eax, [rdi + PKT_MAGIC]
    cmp     eax, DISP_MAGIC
    je      .magic_ok
    xor     rax, rax
    pop     rbp
    ret
.magic_ok:
    mov     rax, 1
    pop     rbp
    ret

; =============================================================================
; ipc_get_opcode — Extract opcode from packet
; Arguments: rdi = packet_ptr
; Returns: rax = opcode (uint16, zero-extended)
; =============================================================================
ipc_get_opcode:
    push    rbp
    mov     rbp, rsp
    movzx   rax, word [rdi + PKT_OPCODE]
    pop     rbp
    ret

; =============================================================================
; ipc_get_payload_len — Extract payload length from packet
; Arguments: rdi = packet_ptr
; Returns: rax = payload_len (uint32, zero-extended)
; =============================================================================
ipc_get_payload_len:
    push    rbp
    mov     rbp, rsp
    mov     eax, [rdi + PKT_PAYLOAD_LEN]
    pop     rbp
    ret

; =============================================================================
; dispatch_loop — Main dispatch loop
; Polls shared memory and dispatches packets until SIGTERM or OP_SHUTDOWN
; Arguments: none
; Returns: does not normally return
; =============================================================================
dispatch_loop:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

.loop_top:
    ; Poll for packet
    call    ipc_poll
    test    rax, rax
    jz      .sleep_poll         ; no packet — sleep and retry

    ; Read packet into recv buffer
    lea     rdi, [rel ipc_recv_buf]
    call    ipc_read_packet
    cmp     rax, -1
    je      .sleep_poll         ; bad packet — skip

    mov     r12, rax            ; save opcode

    ; Check for shutdown
    cmp     r12, OP_SHUTDOWN
    je      .do_shutdown

    ; Dispatch the opcode
    ; Get payload pointer and length
    lea     rsi, [rel ipc_recv_buf + PKT_PAYLOAD]  ; payload ptr
    mov     eax, [rel ipc_recv_buf + PKT_PAYLOAD_LEN]
    mov     rdx, rax                                ; payload len

    mov     rdi, r12            ; opcode
    call    dispatch_opcode     ; rax = result_len

    jmp     .loop_top

.sleep_poll:
    ; Sleep POLL_USEC microseconds
    lea     rdi, [rel poll_timespec]
    xor     rsi, rsi
    mov     rax, SYS_NANOSLEEP
    syscall
    jmp     .loop_top

.do_shutdown:
    mov     rdi, 1
    lea     rsi, [rel msg_shutdown]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_shutdown]
    call    sys_write

    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; dispatch_opcode — Dispatch to handler via opcode jump table
; Arguments: rdi = opcode, rsi = payload_ptr, rdx = payload_len
; Returns: rax = result_len (bytes of response written)
; =============================================================================
dispatch_opcode:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    mov     rbx, rdi            ; opcode
    mov     r12, rsi            ; payload_ptr
    mov     r13, rdx            ; payload_len

    ; Bounds check opcode
    cmp     rbx, 255
    jg      .dispatch_unknown

    ; Load handler from jump table
    lea     rax, [rel opcode_table]
    mov     rax, [rax + rbx * 8]
    test    rax, rax
    jz      .dispatch_unknown

    ; Call handler: (rdi=payload_ptr, rsi=payload_len, rdx=send_buf)
    mov     rdi, r12
    mov     rsi, r13
    lea     rdx, [rel ipc_send_buf]
    call    rax                 ; rax = result_len

    ; Write response
    push    rax                 ; save result_len
    lea     rdi, [rel ipc_send_buf]
    mov     rsi, rax
    mov     rdx, rbx            ; opcode
    call    ipc_write_response
    pop     rax

    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

.dispatch_unknown:
    inc     qword [rel ipc_stats.unknown_ops]
    mov     rdi, 1
    lea     rsi, [rel msg_unknown_op]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_unknown_op]
    call    sys_write
    xor     rax, rax
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; =============================================================================
; Opcode Handlers
; Each handler receives: rdi=payload_ptr, rsi=payload_len, rdx=response_buf
; Each handler returns: rax=response_len
; =============================================================================

; ─── handler_nop ─────────────────────────────────────────────────────────────
handler_nop:
    push    rbp
    mov     rbp, rsp
    ; NOP: write zero-length response
    xor     rax, rax
    pop     rbp
    ret

; ─── handler_filesystem_read ─────────────────────────────────────────────────
handler_filesystem_read:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    mov     rbx, rdi            ; payload_ptr (contains null-term path)
    mov     r12, rsi            ; payload_len
    mov     r13, rdx            ; response_buf

    ; Log
    mov     rdi, 1
    lea     rsi, [rel msg_fs_read]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_fs_read]
    call    sys_write

    ; Write RESP_OK into response buffer (4 bytes)
    mov     dword [r13], RESP_OK

    mov     rax, 4              ; response_len = 4
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; ─── handler_filesystem_write ────────────────────────────────────────────────
handler_filesystem_write:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13

    mov     rbx, rdi
    mov     r12, rsi
    mov     r13, rdx

    mov     rdi, 1
    lea     rsi, [rel msg_fs_write]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_fs_write]
    call    sys_write

    mov     dword [r13], RESP_OK
    mov     rax, 4

    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret

; ─── handler_filesystem_stat ─────────────────────────────────────────────────
handler_filesystem_stat:
    push    rbp
    mov     rbp, rsp
    push    r13
    mov     r13, rdx

    mov     rdi, 1
    lea     rsi, [rel msg_fs_stat]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_fs_stat]
    call    sys_write

    mov     dword [r13], RESP_OK
    mov     rax, 4
    pop     r13
    pop     rbp
    ret

; ─── handler_filesystem_list ─────────────────────────────────────────────────
handler_filesystem_list:
    push    rbp
    mov     rbp, rsp
    push    r13
    mov     r13, rdx

    mov     rdi, 1
    lea     rsi, [rel msg_fs_list]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_fs_list]
    call    sys_write

    mov     dword [r13], RESP_OK
    mov     rax, 4
    pop     r13
    pop     rbp
    ret

; ─── handler_process_spawn ───────────────────────────────────────────────────
handler_process_spawn:
    push    rbp
    mov     rbp, rsp
    push    r13
    mov     r13, rdx

    mov     rdi, 1
    lea     rsi, [rel msg_proc_spawn]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_proc_spawn]
    call    sys_write

    mov     dword [r13], RESP_OK
    mov     rax, 4
    pop     r13
    pop     rbp
    ret

; ─── handler_process_kill ────────────────────────────────────────────────────
handler_process_kill:
    push    rbp
    mov     rbp, rsp
    push    r13
    mov     r13, rdx

    mov     rdi, 1
    lea     rsi, [rel msg_proc_kill]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_proc_kill]
    call    sys_write

    mov     dword [r13], RESP_OK
    mov     rax, 4
    pop     r13
    pop     rbp
    ret

; ─── handler_process_list ────────────────────────────────────────────────────
handler_process_list:
    push    rbp
    mov     rbp, rsp
    push    r13
    mov     r13, rdx

    mov     rdi, 1
    lea     rsi, [rel msg_proc_list]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_proc_list]
    call    sys_write

    mov     dword [r13], RESP_OK
    mov     rax, 4
    pop     r13
    pop     rbp
    ret

; ─── handler_memory_alloc ────────────────────────────────────────────────────
handler_memory_alloc:
    push    rbp
    mov     rbp, rsp
    push    r13
    mov     r13, rdx

    mov     rdi, 1
    lea     rsi, [rel msg_mem_alloc]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_mem_alloc]
    call    sys_write

    mov     dword [r13], RESP_OK
    mov     rax, 4
    pop     r13
    pop     rbp
    ret

; ─── handler_git_status ──────────────────────────────────────────────────────
handler_git_status:
    push    rbp
    mov     rbp, rsp
    push    r13
    mov     r13, rdx

    mov     rdi, 1
    lea     rsi, [rel msg_git_status]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_git_status]
    call    sys_write

    mov     dword [r13], RESP_OK
    mov     rax, 4
    pop     r13
    pop     rbp
    ret

; ─── handler_git_commit ──────────────────────────────────────────────────────
handler_git_commit:
    push    rbp
    mov     rbp, rsp
    push    r13
    mov     r13, rdx

    mov     rdi, 1
    lea     rsi, [rel msg_git_commit]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_git_commit]
    call    sys_write

    mov     dword [r13], RESP_OK
    mov     rax, 4
    pop     r13
    pop     rbp
    ret

; ─── handler_git_push ────────────────────────────────────────────────────────
handler_git_push:
    push    rbp
    mov     rbp, rsp
    push    r13
    mov     r13, rdx

    mov     rdi, 1
    lea     rsi, [rel msg_git_push]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_git_push]
    call    sys_write

    mov     dword [r13], RESP_OK
    mov     rax, 4
    pop     r13
    pop     rbp
    ret

; ─── handler_worm_append ─────────────────────────────────────────────────────
handler_worm_append:
    push    rbp
    mov     rbp, rsp
    push    r12
    push    r13

    mov     r12, rdi            ; payload_ptr
    mov     r13, rdx            ; response_buf

    mov     rdi, 1
    lea     rsi, [rel msg_worm_app]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_worm_app]
    call    sys_write

    ; Delegate to WORM append
    mov     rdi, r12
    mov     rsi, rsi            ; payload_len already in rsi
    mov     rdx, 0x02           ; EVT_APPEND
    call    worm_append

    ; Write result index into response
    mov     [r13], rax
    mov     rax, 8              ; 8 bytes response

    pop     r13
    pop     r12
    pop     rbp
    ret

; ─── handler_worm_verify ─────────────────────────────────────────────────────
handler_worm_verify:
    push    rbp
    mov     rbp, rsp
    push    r13
    mov     r13, rdx

    mov     rdi, 1
    lea     rsi, [rel msg_worm_ver]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_worm_ver]
    call    sys_write

    call    worm_verify_chain
    mov     [r13], rax
    mov     rax, 8

    pop     r13
    pop     rbp
    ret

; ─── handler_qra_route ───────────────────────────────────────────────────────
handler_qra_route:
    push    rbp
    mov     rbp, rsp
    push    r12
    push    r13

    mov     r12, rdi            ; payload_ptr (contains 2-byte {curr, prev})
    mov     r13, rdx            ; response_buf

    mov     rdi, 1
    lea     rsi, [rel msg_qra_route]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_qra_route]
    call    sys_write

    ; Extract curr and prev from payload
    movzx   rdi, byte [r12]     ; curr
    movzx   rsi, byte [r12 + 1] ; prev
    call    qra_next

    mov     [r13], rax
    mov     rax, 8

    pop     r13
    pop     r12
    pop     rbp
    ret

; ─── handler_entropy_check ───────────────────────────────────────────────────
handler_entropy_check:
    push    rbp
    mov     rbp, rsp
    push    r13
    mov     r13, rdx

    mov     rdi, 1
    lea     rsi, [rel msg_entropy_chk]
    call    str_len
    mov     rdx, rax
    mov     rdi, 1
    lea     rsi, [rel msg_entropy_chk]
    call    sys_write

    ; Pass entropy value (from payload xmm0) to entropy_check
    ; For now write OK
    mov     dword [r13], RESP_OK
    mov     rax, 4

    pop     r13
    pop     rbp
    ret

; ─── handler_shutdown ────────────────────────────────────────────────────────
handler_shutdown:
    push    rbp
    mov     rbp, rsp
    push    r13
    mov     r13, rdx

    mov     dword [r13], RESP_OK
    mov     rax, 4

    pop     r13
    pop     rbp
    ret

; ─── handler_unknown ─────────────────────────────────────────────────────────
handler_unknown:
    push    rbp
    mov     rbp, rsp
    push    r13
    mov     r13, rdx

    inc     qword [rel ipc_stats.unknown_ops]
    mov     dword [r13], RESP_ERR_UNKNOWN_OP
    mov     rax, 4

    pop     r13
    pop     rbp
    ret
