; ═══════════════════════════════════════════════════════════════════════════
; PART III — GA144 / HARDWARE FORTH
; GreenArrays GA144 · F18A node · asynchronous mesh · root of trust
; ═══════════════════════════════════════════════════════════════════════════

; ───────────────────────────────────────────────────────────────────────────
; SECTION 40 — GA144 / F18A CONSTANTS
; ───────────────────────────────────────────────────────────────────────────

GA_NODE_COUNT = 144
GA_MESH_W = 18
GA_MESH_H = 8
GA_RAM_WORDS = 64
GA_ROM_WORDS = 64
GA_WORD_BITS = 18
GA_WORD_MASK = 0x3FFFF
GA_STACK_DEPTH = 8
GA_RSTACK_DEPTH = 8

F18_OP_NOP = 0x00
F18_OP_EX = 0x01
F18_OP_JUMP = 0x02
F18_OP_CALL = 0x03
F18_OP_UNEXT = 0x04
F18_OP_RET = 0x05
F18_OP_LIT = 0x06
F18_OP_LITP = 0x07
F18_OP_DUP = 0x08
F18_OP_DROP = 0x09
F18_OP_SWAP = 0x0A
F18_OP_OVER = 0x0B
F18_OP_ROT = 0x0C
F18_OP_NIP = 0x0D
F18_OP_TUCK = 0x0E
F18_OP_2DUP = 0x0F
F18_OP_2DROP = 0x10
F18_OP_ADD = 0x11
F18_OP_ADDstar = 0x12
F18_OP_SUB = 0x13
F18_OP_AND = 0x14
F18_OP_OR = 0x15
F18_OP_XOR = 0x16
F18_OP_SHL = 0x17
F18_OP_SHR = 0x18
F18_OP_FETCH = 0x19
F18_OP_STORE = 0x1A
F18_OP_FETCHP = 0x1B
F18_OP_STOREP = 0x1C
F18_OP_COMFETCH = 0x1D
F18_OP_COMSTORE = 0x1E
F18_OP_EMIT = 0x1F

GA_PORT_UP = 0
GA_PORT_RIGHT = 1
GA_PORT_DOWN = 2
GA_PORT_LEFT = 3
GA_PORT_COUNT = 4

GA_STATE_RESET = 0
GA_STATE_BOOTING = 1
GA_STATE_VERIFYING = 2
GA_STATE_READY = 3
GA_STATE_HALTED = 4
GA_STATE_FAULT = 5

ROT_MAGIC = 0x47413434
ROT_VERSION = 0x00010000
ROT_HASH_WORDS = 8
ROT_CHAIN_DEPTH = GA_NODE_COUNT
ROT_KEY_WORDS = 8
ROT_SIG_WORDS = 8

HASH_A = 0x1F123BB5
HASH_B = 0x2C1B3C6D
HASH_C = 0x3F7A1E2B
HASH_MASK = 0x3FFFF

; ───────────────────────────────────────────────────────────────────────────
; SECTION 41 — F18A NODE STATE
; ───────────────────────────────────────────────────────────────────────────

section '.gabss' align 64

align 64
ga_node_p: times GA_NODE_COUNT dw 0
ga_node_i: times GA_NODE_COUNT dw 0
ga_node_a: times GA_NODE_COUNT dw 0
ga_node_b: times GA_NODE_COUNT dw 0
ga_node_t: times GA_NODE_COUNT dw 0
ga_node_s: times GA_NODE_COUNT dw 0
ga_node_r: times GA_NODE_COUNT dw 0
ga_node_dstack: times GA_NODE_COUNT * GA_STACK_DEPTH dw 0
ga_node_rstack: times GA_NODE_COUNT * GA_RSTACK_DEPTH dw 0
ga_node_dsp: times GA_NODE_COUNT db 0
ga_node_rsp: times GA_NODE_COUNT db 0
ga_node_state: times GA_NODE_COUNT db GA_STATE_RESET
ga_node_ram: times GA_NODE_COUNT * GA_RAM_WORDS dw 0
ga_node_rom: times GA_NODE_COUNT * GA_ROM_WORDS dw 0
ga_node_ports: times GA_NODE_COUNT * GA_PORT_COUNT * 4 db 0
ga_node_cycles: times GA_NODE_COUNT dq 0
ga_node_instrs: times GA_NODE_COUNT dq 0
ga_node_halts: times GA_NODE_COUNT dq 0
ga_node_hash: times GA_NODE_COUNT * ROT_HASH_WORDS dw 0

ga_active_node: dw 0
ga_cycle_count: dq 0
ga_total_instrs: dq 0
ga_boot_complete: db 0
ga_rot_chain: times ROT_CHAIN_DEPTH * ROT_HASH_WORDS dw 0
ga_rot_root: times ROT_HASH_WORDS dw 0
ga_rot_key: times ROT_KEY_WORDS dw 0
ga_rot_valid: db 0
ga_rot_faults: dq 0

ga_tensor_src: dw 0
ga_tensor_dst: dw 0
ga_tensor_len: dw 0
ga_tensor_route: times 64 db 0
ga_tensor_route_len: db 0
ga_tensor_buffer: times 1024 dw 0

; ───────────────────────────────────────────────────────────────────────────
; SECTION 42 — F18A OPCODE TABLE
; ───────────────────────────────────────────────────────────────────────────

section '.gadata' align 64

align 64
f18_opcode_names:
    db "nop  ", 0 , "ex   ", 0 , "jump ", 0 , "call ", 0
    db "unext", 0 , "ret  ", 0 , "lit  ", 0 , "litp ", 0
    db "dup  ", 0 , "drop ", 0 , "swap ", 0 , "over ", 0
    db "rot  ", 0 , "nip  ", 0 , "tuck ", 0 , "2dup ", 0
    db "2drop", 0 , "add  ", 0 , "add* ", 0 , "sub  ", 0
    db "and  ", 0 , "or   ", 0 , "xor  ", 0 , "shl  ", 0
    db "shr  ", 0 , "fetch", 0 , "store", 0 , "fetcp", 0
    db "stocp", 0 , "cfetc", 0 , "cstoc", 0 , "emit ", 0

rot_msg_init: db "[GA144] Root of Trust initialising", 10
rot_msg_init_len = $ - rot_msg_init
rot_msg_node: db "[GA144] measuring node "
rot_msg_node_len = $ - rot_msg_node
rot_msg_ok: db " OK", 10
rot_msg_ok_len = $ - rot_msg_ok
rot_msg_fail: db " FAULT", 10
rot_msg_fail_len = $ - rot_msg_fail
rot_msg_boot: db "[GA144] boot complete, mesh ready", 10
rot_msg_boot_len = $ - rot_msg_boot
rot_msg_chain: db "[GA144] hash chain verified", 10
rot_msg_chain_len = $ - rot_msg_chain
rot_msg_root: db "[GA144] root hash: "
rot_msg_root_len = $ - rot_msg_root
rot_msg_tensor: db "[GA144] routing tensor ", 0
rot_msg_tensor_len = $ - rot_msg_tensor

section '.gabss' align 64
scratch_rom: times 8 dw 0

; ───────────────────────────────────────────────────────────────────────────
; SECTION 43 — F18A INSTRUCTION DECODER
; ───────────────────────────────────────────────────────────────────────────

section '.gatext' executable align 64

public ga_node_index
ga_node_index:
    mov eax, esi
    imul eax, GA_MESH_W
    add eax, edi
    and eax, GA_NODE_COUNT - 1
    ret

public ga_node_xy
ga_node_xy:
    mov eax, edi
    xor edx, edx
    mov ecx, GA_MESH_W
    div ecx
    ret

public ga_port_for_dir
ga_port_for_dir:
    push rbx
    mov ebx, edi
    call ga_node_xy
    cmp esi, GA_PORT_UP
    je .up
    cmp esi, GA_PORT_RIGHT
    je .right
    cmp esi, GA_PORT_DOWN
    je .down
    cmp esi, GA_PORT_LEFT
    je .left
    mov eax, -1
    jmp .done
.up:
    test edx, edx
    jz .edge
    dec edx
    mov edi, eax
    mov esi, edx
    call ga_node_index
    jmp .done
.right:
    cmp eax, GA_MESH_W - 1
    je .edge
    inc eax
    mov edi, eax
    mov esi, edx
    call ga_node_index
    jmp .done
.down:
    cmp edx, GA_MESH_H - 1
    je .edge
    inc edx
    mov edi, eax
    mov esi, edx
    call ga_node_index
    jmp .done
.left:
    test eax, eax
    jz .edge
    dec eax
    mov edi, eax
    mov esi, edx
    call ga_node_index
    jmp .done
.edge:
    mov eax, -1
.done:
    pop rbx
    ret

; ───────────────────────────────────────────────────────────────────────────
; SECTION 44 — ASYNCHRONOUS TENSOR ROUTER
; ───────────────────────────────────────────────────────────────────────────

public ga_route_tensor
ga_route_tensor:
    push rbx
    push r12
    push r13
    mov ebx, edi
    mov r12d, esi
    mov edi, ebx
    call ga_node_xy
    mov r8d, eax
    mov r9d, edx
    mov edi, r12d
    call ga_node_xy
    mov r10d, eax
    mov r11d, edx
    xor r13d, r13d
    mov eax, r8d
    mov edx, r9d
.x_loop:
    cmp eax, r10d
    je .y_loop
    jl .move_right
    mov byte [ga_tensor_route + r13], GA_PORT_LEFT
    inc r13d
    dec eax
    jmp .x_loop
.move_right:
    mov byte [ga_tensor_route + r13], GA_PORT_RIGHT
    inc r13d
    inc eax
    jmp .x_loop
.y_loop:
    cmp edx, r11d
    je .done
    jl .move_down
    mov byte [ga_tensor_route + r13], GA_PORT_UP
    inc r13d
    dec edx
    jmp .y_loop
.move_down:
    mov byte [ga_tensor_route + r13], GA_PORT_DOWN
    inc r13d
    inc edx
    jmp .y_loop
.done:
    mov [ga_tensor_route_len], r13b
    mov eax, r13d
    pop r13
    pop r12
    pop rbx
    ret

public ga_stream_tensor
ga_stream_tensor:
    push rbx
    push r12
    push r13
    push r14
    push r15
    mov r12d, edi
    mov r13d, esi
    mov r14, rdx
    mov r15d, ecx
    mov edi, r12d
    mov esi, r13d
    call ga_route_tensor
    movzx ebx, byte [ga_tensor_route_len]
    xor r8d, r8d
.word_loop:
    cmp r8d, r15d
    jae .done
    movzx edx, word [r14 + r8*2]
    mov eax, r12d
    xor r9d, r9d
.route_loop:
    cmp r9d, ebx
    jae .delivered
    movzx esi, byte [ga_tensor_route + r9]
    mov edi, eax
    ; send word to port (simplified: write to port register)
    mov ecx, esi
    shl ecx, 2
    add ecx, 0x100
    mov esi, ecx
    ; ga_store(edi, esi, edx)
    push rdx
    call ga_store
    pop rdx
    ; advance node
    mov edi, eax
    movzx esi, byte [ga_tensor_route + r9]
    call ga_port_for_dir
    cmp eax, -1
    je .edge
    inc r9d
    jmp .route_loop
.delivered:
    mov edi, r13d
    mov esi, r8d
    add esi, GA_ROM_WORDS
    call ga_store
    inc r8d
    jmp .word_loop
.edge:
    inc qword [ga_rot_faults]
    jmp .done
.done:
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

; ───────────────────────────────────────────────────────────────────────────
; SECTION 45 — ROOT OF TRUST MICROROM
; ───────────────────────────────────────────────────────────────────────────

public rot_hash_word
rot_hash_word:
    mov eax, edi
    xor eax, esi
    mov ecx, eax
    imul ecx, ecx, HASH_A
    and ecx, HASH_MASK
    mov edx, ecx
    shr edx, 7
    xor ecx, edx
    imul ecx, ecx, HASH_B
    and ecx, HASH_MASK
    mov edx, ecx
    shr edx, 13
    xor ecx, edx
    mov eax, ecx
    and eax, HASH_MASK
    ret

public rot_hash_rom
rot_hash_rom:
    push rbx
    push r12
    mov ebx, edi
    mov r12d, esi
    mov ecx, ebx
    imul ecx, GA_ROM_WORDS
    xor r8d, r8d
.loop:
    cmp r8d, GA_ROM_WORDS
    jae .done
    movzx esi, word [ga_node_rom + rcx*2 + r8*2]
    mov edi, r12d
    call rot_hash_word
    mov r12d, eax
    inc r8d
    jmp .loop
.done:
    mov eax, r12d
    pop r12
    pop rbx
    ret

public rot_measure_node
rot_measure_node:
    push rbx
    push r12
    mov ebx, edi
    mov esi, ROT_MAGIC
    call rot_hash_rom
    mov r12d, eax
    mov edi, ebx
    mov esi, r12d
    ; hash RAM
    mov ecx, ebx
    imul ecx, GA_RAM_WORDS
    xor r8d, r8d
.ram_loop:
    cmp r8d, GA_RAM_WORDS
    jae .ram_done
    movzx esi, word [ga_node_ram + rcx*2 + r8*2]
    mov edi, r12d
    call rot_hash_word
    mov r12d, eax
    inc r8d
    jmp .ram_loop
.ram_done:
    mov ecx, ebx
    imul ecx, ROT_HASH_WORDS
    mov [ga_node_hash + rcx*2], r12w
    mov [ga_rot_chain + rcx*2], r12w
    mov eax, r12d
    pop r12
    pop rbx
    ret

public rot_measure_mesh
rot_measure_mesh:
    push rbx
    push r12
    mov r12d, ROT_MAGIC
    xor ebx, ebx
.loop:
    cmp ebx, GA_NODE_COUNT
    jae .done
    mov edi, ebx
    call rot_measure_node
    mov edi, r12d
    mov esi, eax
    call rot_hash_word
    mov r12d, eax
    inc ebx
    jmp .loop
.done:
    mov ecx, 0
.store:
    cmp ecx, ROT_HASH_WORDS
    jae .fin
    mov edi, r12d
    mov esi, ecx
    call rot_hash_word
    mov [ga_rot_root + rcx*2], ax
    mov r12d, eax
    inc ecx
    jmp .store
.fin:
    mov eax, r12d
    pop r12
    pop rbx
    ret

public rot_verify_chain
rot_verify_chain:
    push rbx
    push r12
    mov ebx, 0
    mov r12d, 1
.loop:
    cmp ebx, ROT_HASH_WORDS
    jae .done
    mov ax, [ga_rot_root + rbx*2]
    cmp ax, [ga_rot_key + rbx*2]
    je .next
    xor r12d, r12d
.next:
    inc ebx
    jmp .loop
.done:
    mov al, r12b
    mov [ga_rot_valid], al
    pop r12
    pop rbx
    ret

public rot_release_node
rot_release_node:
    cmp byte [ga_rot_valid], 0
    je .deny
    mov byte [ga_node_state + rdi], GA_STATE_READY
    mov word [ga_node_p + rdi*2], 0
    ret
.deny:
    mov byte [ga_node_state + rdi], GA_STATE_RESET
    inc qword [ga_rot_faults]
    ret

public rot_release_mesh
rot_release_mesh:
    push rbx
    xor ebx, ebx
.loop:
    cmp ebx, GA_NODE_COUNT
    jae .done
    mov edi, ebx
    call rot_release_node
    inc ebx
    jmp .loop
.done:
    mov byte [ga_boot_complete], 1
    pop rbx
    ret

; ───────────────────────────────────────────────────────────────────────────
; SECTION 46 — GA144 BOOT ROM
; ───────────────────────────────────────────────────────────────────────────

public ga_reset_mesh
ga_reset_mesh:
    push rbx
    xor ebx, ebx
.loop:
    cmp ebx, GA_NODE_COUNT
    jae .done
    mov word [ga_node_p + rbx*2], 0
    mov byte [ga_node_state + rbx], GA_STATE_RESET
    mov qword [ga_node_cycles + rbx*8], 0
    mov qword [ga_node_instrs + rbx*8], 0
    inc ebx
    jmp .loop
.done:
    mov qword [ga_cycle_count], 0
    mov qword [ga_total_instrs], 0
    mov byte [ga_boot_complete], 0
    mov byte [ga_rot_valid], 0
    mov qword [ga_rot_faults], 0
    pop rbx
    ret

public ga_load_rom
ga_load_rom:
    push rbx
    push r12
    mov ebx, edi
    mov r12d, edx
    mov ecx, ebx
    imul ecx, GA_ROM_WORDS
    xor r8d, r8d
.loop:
    cmp r8d, r12d
    jae .done
    mov ax, [rsi + r8*2]
    mov [ga_node_rom + rcx*2 + r8*2], ax
    inc r8d
    jmp .loop
.done:
    pop r12
    pop rbx
    ret

ga_load_default_roms:
    push rbx
    push r12
    xor ebx, ebx
.node_loop:
    cmp ebx, GA_NODE_COUNT
    jae .done
    mov eax, F18_OP_LIT
    shl eax, 13
    or eax, 0x40
    and eax, GA_WORD_MASK
    mov [scratch_rom], ax
    mov eax, F18_OP_LIT
    shl eax, 13
    or eax, 1
    mov [scratch_rom + 2], ax
    mov eax, F18_OP_ADD
    shl eax, 13
    mov [scratch_rom + 4], ax
    mov eax, F18_OP_EMIT
    shl eax, 13
    mov [scratch_rom + 6], ax
    mov edi, ebx
    lea rsi, [scratch_rom]
    mov edx, 4
    call ga_load_rom
    inc ebx
    jmp .node_loop
.done:
    pop r12
    pop rbx
    ret

public ga_boot_rom_root
ga_boot_rom_root:
    push rbx
    push r12
    lea rsi, [rot_msg_init]
    mov edx, rot_msg_init_len
    call rot_emit_stdout
    call ga_reset_mesh
    call ga_load_default_roms
    call rot_measure_mesh
    call rot_verify_chain
    test al, al
    jz .fault
    lea rsi, [rot_msg_chain]
    mov edx, rot_msg_chain_len
    call rot_emit_stdout
    call rot_release_mesh
    lea rsi, [rot_msg_boot]
    mov edx, rot_msg_boot_len
    call rot_emit_stdout
    mov al, 1
    jmp .done
.fault:
    lea rsi, [rot_msg_fail]
    mov edx, rot_msg_fail_len
    call rot_emit_stdout
    xor al, al
.done:
    pop r12
    pop rbx
    ret

rot_emit_stdout:
    mov eax, SYS_WRITE
    mov edi, 1
    syscall
    ret

; ───────────────────────────────────────────────────────────────────────────
; SECTION 47 — BRIDGE TO PARTS I AND II
; ───────────────────────────────────────────────────────────────────────────

public ga_bridge_avx
ga_bridge_avx:
    push rbx
    push r12
    mov ebx, edi
    movzx r12d, word [ga_node_t + rbx*2]
    movzx esi, word [ga_node_s + rbx*2]
    mov edi, r12d
    mov rdx, rsi
    mov r8, 16
    xor r9d, r9d
    call nn_exec_layer
    mov [ga_node_t + rbx*2], ax
    pop r12
    pop rbx
    ret

; ───────────────────────────────────────────────────────────────────────────
; SECTION 48 — GA144 SELF-TEST
; ───────────────────────────────────────────────────────────────────────────

public ga_selftest
ga_selftest:
    push rbx
    call ga_boot_rom_root
    test al, al
    jz .fault
    ; run demo pipeline
    xor ebx, ebx
.fill:
    cmp ebx, 16
    jae .filled
    mov [ga_tensor_buffer + rbx*2], bx
    inc ebx
    jmp .fill
.filled:
    xor edi, edi
    mov esi, 143
    lea rdx, [ga_tensor_buffer]
    mov ecx, 16
    call ga_stream_tensor
    jmp .done
.fault:
    lea rsi, [rot_msg_fail]
    mov edx, rot_msg_fail_len
    call rot_emit_stdout
.done:
    pop rbx
    ret

; ───────────────────────────────────────────────────────────────────────────
; SECTION 49 — MEMORY STUBS (ga_fetch / ga_store referenced above)
; ───────────────────────────────────────────────────────────────────────────

public ga_fetch
ga_fetch:
    push rbx
    mov ebx, edi
    mov eax, esi
    and eax, GA_WORD_MASK
    cmp eax, GA_ROM_WORDS
    jb .rom
    cmp eax, GA_ROM_WORDS + GA_RAM_WORDS
    jb .ram
    cmp eax, 0x100
    jb .unknown
    sub eax, 0x100
    shr eax, 2
    and eax, GA_PORT_COUNT - 1
    mov edx, ebx
    imul edx, GA_PORT_COUNT
    add edx, eax
    mov eax, [ga_node_ports + rdx*4]
    jmp .done
.ram:
    sub eax, GA_ROM_WORDS
    mov edx, ebx
    imul edx, GA_RAM_WORDS
    add edx, eax
    movzx eax, word [ga_node_ram + rdx*2]
    jmp .done
.rom:
    mov edx, ebx
    imul edx, GA_ROM_WORDS
    add edx, eax
    movzx eax, word [ga_node_rom + rdx*2]
    jmp .done
.unknown:
    xor eax, eax
.done:
    pop rbx
    ret

public ga_store
ga_store:
    push rbx
    mov ebx, edi
    mov eax, esi
    and eax, GA_WORD_MASK
    cmp eax, GA_ROM_WORDS + GA_RAM_WORDS
    jb .ram
    cmp eax, 0x100
    jb .unknown
    sub eax, 0x100
    shr eax, 2
    and eax, GA_PORT_COUNT - 1
    mov ecx, ebx
    imul ecx, GA_PORT_COUNT
    add ecx, eax
    mov [ga_node_ports + rcx*4], edx
    jmp .done
.ram:
    sub eax, GA_ROM_WORDS
    mov ecx, ebx
    imul ecx, GA_RAM_WORDS
    add ecx, eax
    mov [ga_node_ram + rcx*2], dx
.unknown:
.done:
    pop rbx
    ret

; ═══════════════════════════════════════════════════════════════════════════
; END OF PART III — GA144 / HARDWARE FORTH
;
; Part I   — AVX-512 neural kernels (libavx512nn.asm)
; Part II  — ColorForth hosted environment (colorforth_env.asm)
; Part III — GA144 asynchronous mesh (this file)
; ═══════════════════════════════════════════════════════════════════════════
