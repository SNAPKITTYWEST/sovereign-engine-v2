; ac_vm.asm — Hand-rolled Accumulator Computer Virtual Machine
; Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust
;
; Assemble: nasm -f elf64 ac_vm.asm -o ac_vm.o
; Link:     ld ac_vm.o -o ac_vm
; Run:      ./ac_vm    (expected: "HALT. AC = 55")
;
; AC ISA (16-bit word, opcode=hi byte, addr=lo byte):
;   0x00 HALT        stop
;   0x01 LOAD addr   AC ← Mem[addr]
;   0x02 STORE addr  Mem[addr] ← AC
;   0x03 ADD addr    AC ← AC + Mem[addr]
;   0x04 SUB addr    AC ← AC - Mem[addr]
;   0x05 AND addr    AC ← AC ∧ Mem[addr]
;   0x06 OR  addr    AC ← AC ∨ Mem[addr]
;   0x07 XOR addr    AC ← AC ⊕ Mem[addr]
;   0x08 JMP addr    PC ← addr
;   0x09 JZ  addr    if AC==0 PC ← addr
;   0x0A JNZ addr    if AC!=0 PC ← addr
;   0x0B SHL         AC ← AC << 1
;   0x0C SHR         AC ← AC >> 1
;   0x0D NOP
;
; Connection to MAGMA virtual circuit board:
;   AC register    → magma_666.adb Core_State.cells bit-0
;   Mem[addr]      → Core_State.cells[addr]
;   STORE          → M.Pulse(Core, Input) + M.Latch(Core)
;   HALT           → M.Persist(Core)
;   XOR            → M.Imaginary / M.Fold
;   MicroROM ops   → LOAD_CELL(0) XOR_UPDATE(rule) STORE_CELL(0)

bits 64
default rel

section .data

    mem        times 256 dw 0          ; 256×16-bit word memory

    ac         dw 0                    ; Accumulator
    pc         db 0                    ; Program Counter
    flags      db 0                    ; bit0=Zero, bit1=Carry

    ; Demo: Σ(1..10) = 55
    program:
        dw 0x0120   ; LOAD  0x20  (load 0)
        dw 0x0221   ; STORE 0x21  (sum = 0)
        dw 0x0122   ; LOAD  0x22  (load counter=10)
    .loop:
        dw 0x0321   ; ADD   0x21  (sum += AC)
        dw 0x0221   ; STORE 0x21
        dw 0x0122   ; LOAD  0x22
        dw 0x0423   ; SUB   0x23  (counter -= 1)
        dw 0x0222   ; STORE 0x22
        dw 0x0A04   ; JNZ   .loop (address 4 = word offset 4)
        dw 0x0000   ; HALT

    msg_start  db "AC VM starting...", 10
    msg_halt   db "HALT. AC = ", 0
    msg_nl     db 10, 0

section .bss
    tmp resw 1

section .text
global _start

_start:
    ; Load program into memory
    mov rsi, program
    mov rdi, mem
    mov rcx, 10
.load_prog:
    mov ax, [rsi]
    mov [rdi], ax
    add rsi, 2
    add rdi, 2
    loop .load_prog

    ; Initialize data segment
    mov word [mem + 0x20*2], 0     ; 0x20 = 0
    mov word [mem + 0x21*2], 0     ; 0x21 = sum
    mov word [mem + 0x22*2], 10    ; 0x22 = counter
    mov word [mem + 0x23*2], 1     ; 0x23 = 1

    ; Print banner
    mov rax, 1
    mov rdi, 1
    mov rsi, msg_start
    mov rdx, 18
    syscall

; ── Fetch-Decode-Execute loop ─────────────────────────────────────────────────
.vm_loop:
    movzx rbx, byte [pc]
    mov ax, [mem + rbx*2]
    movzx rcx, ah                   ; opcode
    movzx rdx, al                   ; address/immediate

    cmp rcx, 0x00 ; HALT
    je  .op_halt
    cmp rcx, 0x01 ; LOAD
    je  .op_load
    cmp rcx, 0x02 ; STORE
    je  .op_store
    cmp rcx, 0x03 ; ADD
    je  .op_add
    cmp rcx, 0x04 ; SUB
    je  .op_sub
    cmp rcx, 0x05 ; AND
    je  .op_and
    cmp rcx, 0x06 ; OR
    je  .op_or
    cmp rcx, 0x07 ; XOR
    je  .op_xor
    cmp rcx, 0x08 ; JMP
    je  .op_jmp
    cmp rcx, 0x09 ; JZ
    je  .op_jz
    cmp rcx, 0x0A ; JNZ
    je  .op_jnz
    cmp rcx, 0x0B ; SHL
    je  .op_shl
    cmp rcx, 0x0C ; SHR
    je  .op_shr

.op_nop:
    inc byte [pc]
    jmp .vm_loop

.op_halt:
    jmp .print_result

.op_load:
    mov ax, [mem + rdx*2]
    mov [ac], ax
    call .update_flags
    inc byte [pc]
    jmp .vm_loop

.op_store:
    mov ax, [ac]
    mov [mem + rdx*2], ax
    inc byte [pc]
    jmp .vm_loop

.op_add:
    mov ax, [ac]
    add ax, [mem + rdx*2]
    mov [ac], ax
    call .update_flags
    inc byte [pc]
    jmp .vm_loop

.op_sub:
    mov ax, [ac]
    sub ax, [mem + rdx*2]
    mov [ac], ax
    call .update_flags
    inc byte [pc]
    jmp .vm_loop

.op_and:
    mov ax, [ac]
    and ax, [mem + rdx*2]
    mov [ac], ax
    call .update_flags
    inc byte [pc]
    jmp .vm_loop

.op_or:
    mov ax, [ac]
    or ax, [mem + rdx*2]
    mov [ac], ax
    call .update_flags
    inc byte [pc]
    jmp .vm_loop

.op_xor:
    mov ax, [ac]
    xor ax, [mem + rdx*2]
    mov [ac], ax
    call .update_flags
    inc byte [pc]
    jmp .vm_loop

.op_jmp:
    mov [pc], dl
    jmp .vm_loop

.op_jz:
    test word [ac], 0xFFFF
    jnz .jz_not_taken
    mov [pc], dl
    jmp .vm_loop
.jz_not_taken:
    inc byte [pc]
    jmp .vm_loop

.op_jnz:
    test word [ac], 0xFFFF
    jz  .jnz_not_taken
    mov [pc], dl
    jmp .vm_loop
.jnz_not_taken:
    inc byte [pc]
    jmp .vm_loop

.op_shl:
    mov ax, [ac]
    shl ax, 1
    mov [ac], ax
    call .update_flags
    inc byte [pc]
    jmp .vm_loop

.op_shr:
    mov ax, [ac]
    shr ax, 1
    mov [ac], ax
    call .update_flags
    inc byte [pc]
    jmp .vm_loop

.update_flags:
    mov byte [flags], 0
    cmp word [ac], 0
    jne .uf_done
    or  byte [flags], 1
.uf_done:
    ret

; ── Print result ──────────────────────────────────────────────────────────────
.print_result:
    mov rax, 1
    mov rdi, 1
    mov rsi, msg_halt
    mov rdx, 11
    syscall

    movzx rax, word [ac]
    call print_uint16

    mov rax, 1
    mov rdi, 1
    mov rsi, msg_nl
    mov rdx, 1
    syscall

    mov rax, 60
    xor rdi, rdi
    syscall

; ── Helper: print uint16 in rax ───────────────────────────────────────────────
print_uint16:
    mov rbp, rsp
    sub rsp, 16
    mov rdi, rsp
    add rdi, 15
    mov byte [rdi], 0
    mov rbx, 10
.p_conv:
    dec rdi
    xor rdx, rdx
    div rbx
    add dl, '0'
    mov [rdi], dl
    test rax, rax
    jnz .p_conv
    mov rax, 1
    mov rsi, rdi
    mov rdx, rsp
    add rdx, 16
    sub rdx, rdi
    mov rdi, 1
    syscall
    mov rsp, rbp
    ret
