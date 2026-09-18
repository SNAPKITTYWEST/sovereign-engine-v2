(module
  ;; beam_vm.wat — BEAM Virtual Machine in WebAssembly
  ;;
  ;; Replaces the Electron/TypeScript desktop shell.
  ;; Erlang-style lightweight processes with preemptive scheduling,
  ;; per-process mailboxes, and reduction-counted execution.
  ;;
  ;; No Chromium. No V8. No Node.js. No npm.
  ;; Processes communicate via direct memory mailboxes on the same
  ;; linear memory substrate as M5 and tunnel_matrix.
  ;;
  ;; Memory layout (8 pages = 512KB):
  ;;   [0x00000 .. 0x0FFFF]  Process table (256 slots × 256 bytes)
  ;;   [0x10000 .. 0x2FFFF]  Mailbox ring buffers (256 × 512 bytes)
  ;;   [0x30000 .. 0x4FFFF]  Heap — per-process term storage
  ;;   [0x50000 .. 0x5FFFF]  Atom table (4096 atoms × 16 bytes)
  ;;   [0x60000 .. 0x6FFFF]  Module table (256 entries × 256 bytes)
  ;;   [0x70000 .. 0x7FFFF]  Stack frames + scratch

  (memory (export "beam_memory") 8)

  ;; ── Process Table Layout (per slot, 256 bytes) ──────────────────────────
  ;; Offset  Size   Field
  ;; 0x00    4      pid
  ;; 0x04    4      status (0=free, 1=ready, 2=running, 3=waiting, 4=dead)
  ;; 0x08    4      reductions_left
  ;; 0x0C    4      mailbox_head (index into ring buffer)
  ;; 0x10    4      mailbox_tail
  ;; 0x14    4      heap_ptr (offset into heap region)
  ;; 0x18    4      stack_ptr
  ;; 0x1C    4      module_idx (which module this process runs)
  ;; 0x20    4      function_idx (entry point within module)
  ;; 0x24    4      trap_handler (linked process for exit signals)
  ;; 0x28    4      priority (0=max, 1=high, 2=normal, 3=low)
  ;; 0x2C    4      message_count
  ;; 0x30    4      parent_pid
  ;; 0x34    4      timer_ref (0 = no timer)
  ;; 0x38    8      creation_tick
  ;; 0x40    192    reserved

  ;; ── Constants ──────────────────────────────────────────────────────────
  ;; Process table
  (global $PROC_TABLE_BASE  i32 (i32.const 0x00000))
  (global $PROC_SLOT_SIZE   i32 (i32.const 256))
  (global $MAX_PROCESSES     i32 (i32.const 256))

  ;; Mailbox region
  (global $MBOX_BASE         i32 (i32.const 0x10000))
  (global $MBOX_SLOT_SIZE    i32 (i32.const 512))
  (global $MBOX_MSG_SIZE     i32 (i32.const 32))
  (global $MBOX_CAPACITY     i32 (i32.const 16))

  ;; Heap
  (global $HEAP_BASE         i32 (i32.const 0x30000))

  ;; Atom table
  (global $ATOM_BASE         i32 (i32.const 0x50000))

  ;; Scheduler state
  (global $current_pid   (export "current_pid")   (mut i32) (i32.const -1))
  (global $next_pid      (export "next_pid")       (mut i32) (i32.const 0))
  (global $tick_counter  (export "tick_counter")   (mut i64) (i64.const 0))
  (global $process_count (export "process_count") (mut i32) (i32.const 0))
  (global $reductions_per_slice i32 (i32.const 4000))

  ;; ── proc_addr: base address of process slot ────────────────────────────
  (func $proc_addr (param $pid i32) (result i32)
    (i32.add
      (global.get $PROC_TABLE_BASE)
      (i32.mul (local.get $pid) (global.get $PROC_SLOT_SIZE))
    )
  )

  ;; ── spawn: create a new lightweight process ────────────────────────────
  ;; Returns pid, or -1 if process table full.
  ;; Maps to: erlang:spawn/3
  (func (export "spawn")
        (param $module_idx i32)
        (param $func_idx i32)
        (param $priority i32)
        (result i32)
    (local $pid i32)
    (local $base i32)
    (local $heap_offset i32)

    ;; Find free slot
    (local.set $pid (i32.const 0))
    (block $found
      (loop $scan
        (if (i32.ge_u (local.get $pid) (global.get $MAX_PROCESSES))
          (then (return (i32.const -1)))
        )
        (local.set $base (call $proc_addr (local.get $pid)))
        ;; Check status field (offset 0x04) == 0 (free)
        (br_if $found
          (i32.eqz (i32.load (i32.add (local.get $base) (i32.const 0x04))))
        )
        (local.set $pid (i32.add (local.get $pid) (i32.const 1)))
        (br $scan)
      )
    )

    ;; Initialize process control block
    (local.set $base (call $proc_addr (local.get $pid)))

    ;; pid
    (i32.store (local.get $base) (local.get $pid))
    ;; status = 1 (ready)
    (i32.store (i32.add (local.get $base) (i32.const 0x04)) (i32.const 1))
    ;; reductions_left
    (i32.store (i32.add (local.get $base) (i32.const 0x08))
               (global.get $reductions_per_slice))
    ;; mailbox head/tail = 0
    (i32.store (i32.add (local.get $base) (i32.const 0x0C)) (i32.const 0))
    (i32.store (i32.add (local.get $base) (i32.const 0x10)) (i32.const 0))
    ;; heap_ptr — each process gets 512 bytes of heap
    (local.set $heap_offset
      (i32.add (global.get $HEAP_BASE)
               (i32.mul (local.get $pid) (i32.const 512))))
    (i32.store (i32.add (local.get $base) (i32.const 0x14)) (local.get $heap_offset))
    ;; stack_ptr
    (i32.store (i32.add (local.get $base) (i32.const 0x18)) (i32.const 0))
    ;; module_idx
    (i32.store (i32.add (local.get $base) (i32.const 0x1C)) (local.get $module_idx))
    ;; function_idx
    (i32.store (i32.add (local.get $base) (i32.const 0x20)) (local.get $func_idx))
    ;; trap_handler = -1 (none)
    (i32.store (i32.add (local.get $base) (i32.const 0x24)) (i32.const -1))
    ;; priority
    (i32.store (i32.add (local.get $base) (i32.const 0x28)) (local.get $priority))
    ;; message_count = 0
    (i32.store (i32.add (local.get $base) (i32.const 0x2C)) (i32.const 0))
    ;; parent_pid
    (i32.store (i32.add (local.get $base) (i32.const 0x30)) (global.get $current_pid))
    ;; timer_ref = 0
    (i32.store (i32.add (local.get $base) (i32.const 0x34)) (i32.const 0))
    ;; creation_tick
    (i64.store (i32.add (local.get $base) (i32.const 0x38)) (global.get $tick_counter))

    (global.set $process_count
      (i32.add (global.get $process_count) (i32.const 1)))

    (local.get $pid)
  )

  ;; ── send: deliver message to process mailbox ───────────────────────────
  ;; Erlang ! operator. Returns 0=OK, -1=full, -2=dead.
  ;; Messages are 32-byte fixed records in the ring buffer.
  (func (export "send")
        (param $dst_pid i32)
        (param $msg_tag i32)
        (param $msg_val i64)
        (result i32)
    (local $base i32)
    (local $status i32)
    (local $tail i32)
    (local $next_tail i32)
    (local $head i32)
    (local $mbox_addr i32)
    (local $msg_addr i32)

    ;; Bounds check
    (if (i32.ge_u (local.get $dst_pid) (global.get $MAX_PROCESSES))
      (then (return (i32.const -2)))
    )

    (local.set $base (call $proc_addr (local.get $dst_pid)))
    (local.set $status (i32.load (i32.add (local.get $base) (i32.const 0x04))))

    ;; Dead process
    (if (i32.eq (local.get $status) (i32.const 4))
      (then (return (i32.const -2)))
    )

    ;; Mailbox ring buffer for this pid
    (local.set $tail (i32.load (i32.add (local.get $base) (i32.const 0x10))))
    (local.set $head (i32.load (i32.add (local.get $base) (i32.const 0x0C))))
    (local.set $next_tail
      (i32.rem_u
        (i32.add (local.get $tail) (i32.const 1))
        (global.get $MBOX_CAPACITY)))

    ;; Full check
    (if (i32.eq (local.get $next_tail) (local.get $head))
      (then (return (i32.const -1)))
    )

    ;; Write message into ring buffer
    ;; mbox_addr = MBOX_BASE + dst_pid * MBOX_SLOT_SIZE
    (local.set $mbox_addr
      (i32.add (global.get $MBOX_BASE)
               (i32.mul (local.get $dst_pid) (global.get $MBOX_SLOT_SIZE))))
    ;; msg_addr = mbox_addr + tail * MBOX_MSG_SIZE
    (local.set $msg_addr
      (i32.add (local.get $mbox_addr)
               (i32.mul (local.get $tail) (global.get $MBOX_MSG_SIZE))))

    ;; Message layout (32 bytes):
    ;;   [0]  i32  sender_pid
    ;;   [4]  i32  msg_tag (atom index)
    ;;   [8]  i64  msg_val (payload)
    ;;   [16] i64  timestamp (tick)
    ;;   [24] i64  reserved
    (i32.store (local.get $msg_addr) (global.get $current_pid))
    (i32.store (i32.add (local.get $msg_addr) (i32.const 4)) (local.get $msg_tag))
    (i64.store (i32.add (local.get $msg_addr) (i32.const 8)) (local.get $msg_val))
    (i64.store (i32.add (local.get $msg_addr) (i32.const 16)) (global.get $tick_counter))

    ;; Advance tail
    (i32.store (i32.add (local.get $base) (i32.const 0x10)) (local.get $next_tail))
    ;; Increment message count
    (i32.store (i32.add (local.get $base) (i32.const 0x2C))
      (i32.add (i32.load (i32.add (local.get $base) (i32.const 0x2C)))
               (i32.const 1)))

    ;; If target was waiting for a message, wake it
    (if (i32.eq (local.get $status) (i32.const 3))
      (then
        (i32.store (i32.add (local.get $base) (i32.const 0x04)) (i32.const 1))
      )
    )

    (i32.const 0)
  )

  ;; ── receive: pop next message from current process mailbox ─────────────
  ;; Returns msg_tag, writes msg_val to out_ptr. Returns -1 if empty.
  (func (export "receive")
        (param $out_ptr i32)
        (result i32)
    (local $base i32)
    (local $head i32)
    (local $tail i32)
    (local $mbox_addr i32)
    (local $msg_addr i32)
    (local $tag i32)

    (if (i32.lt_s (global.get $current_pid) (i32.const 0))
      (then (return (i32.const -1)))
    )

    (local.set $base (call $proc_addr (global.get $current_pid)))
    (local.set $head (i32.load (i32.add (local.get $base) (i32.const 0x0C))))
    (local.set $tail (i32.load (i32.add (local.get $base) (i32.const 0x10))))

    ;; Empty
    (if (i32.eq (local.get $head) (local.get $tail))
      (then
        ;; Set status to waiting (3)
        (i32.store (i32.add (local.get $base) (i32.const 0x04)) (i32.const 3))
        (return (i32.const -1))
      )
    )

    ;; Read message
    (local.set $mbox_addr
      (i32.add (global.get $MBOX_BASE)
               (i32.mul (global.get $current_pid) (global.get $MBOX_SLOT_SIZE))))
    (local.set $msg_addr
      (i32.add (local.get $mbox_addr)
               (i32.mul (local.get $head) (global.get $MBOX_MSG_SIZE))))

    (local.set $tag (i32.load (i32.add (local.get $msg_addr) (i32.const 4))))
    ;; Write sender_pid + msg_val + timestamp to out_ptr
    (i32.store (local.get $out_ptr)
               (i32.load (local.get $msg_addr)))
    (i64.store (i32.add (local.get $out_ptr) (i32.const 4))
               (i64.load (i32.add (local.get $msg_addr) (i32.const 8))))
    (i64.store (i32.add (local.get $out_ptr) (i32.const 12))
               (i64.load (i32.add (local.get $msg_addr) (i32.const 16))))

    ;; Advance head
    (i32.store (i32.add (local.get $base) (i32.const 0x0C))
      (i32.rem_u
        (i32.add (local.get $head) (i32.const 1))
        (global.get $MBOX_CAPACITY)))
    ;; Decrement message count
    (i32.store (i32.add (local.get $base) (i32.const 0x2C))
      (i32.sub (i32.load (i32.add (local.get $base) (i32.const 0x2C)))
               (i32.const 1)))

    (local.get $tag)
  )

  ;; ── schedule: round-robin with priority ────────────────────────────────
  ;; Picks next ready process. Returns pid or -1 if none ready.
  ;; Priority 0 (max) gets checked first in each sweep.
  (func (export "schedule") (result i32)
    (local $scan_start i32)
    (local $i i32)
    (local $pid i32)
    (local $base i32)
    (local $status i32)
    (local $best_pid i32)
    (local $best_prio i32)

    (local.set $best_pid (i32.const -1))
    (local.set $best_prio (i32.const 999))
    (local.set $scan_start (global.get $next_pid))
    (local.set $i (i32.const 0))

    (loop $sweep
      (if (i32.lt_u (local.get $i) (global.get $MAX_PROCESSES))
        (then
          (local.set $pid
            (i32.rem_u
              (i32.add (local.get $scan_start) (local.get $i))
              (global.get $MAX_PROCESSES)))
          (local.set $base (call $proc_addr (local.get $pid)))
          (local.set $status (i32.load (i32.add (local.get $base) (i32.const 0x04))))

          ;; Ready (1) and priority < best
          (if (i32.and
                (i32.eq (local.get $status) (i32.const 1))
                (i32.lt_u
                  (i32.load (i32.add (local.get $base) (i32.const 0x28)))
                  (local.get $best_prio)))
            (then
              (local.set $best_pid (local.get $pid))
              (local.set $best_prio
                (i32.load (i32.add (local.get $base) (i32.const 0x28))))
            )
          )

          (local.set $i (i32.add (local.get $i) (i32.const 1)))
          (br $sweep)
        )
      )
    )

    ;; Update scheduler state
    (if (i32.ge_s (local.get $best_pid) (i32.const 0))
      (then
        ;; Demote current process to ready if it was running
        (if (i32.ge_s (global.get $current_pid) (i32.const 0))
          (then
            (local.set $base (call $proc_addr (global.get $current_pid)))
            (if (i32.eq
                  (i32.load (i32.add (local.get $base) (i32.const 0x04)))
                  (i32.const 2))
              (then
                (i32.store (i32.add (local.get $base) (i32.const 0x04))
                           (i32.const 1))
              )
            )
          )
        )
        ;; Promote selected process
        (local.set $base (call $proc_addr (local.get $best_pid)))
        (i32.store (i32.add (local.get $base) (i32.const 0x04)) (i32.const 2))
        (i32.store (i32.add (local.get $base) (i32.const 0x08))
                   (global.get $reductions_per_slice))
        (global.set $current_pid (local.get $best_pid))
        (global.set $next_pid
          (i32.rem_u
            (i32.add (local.get $best_pid) (i32.const 1))
            (global.get $MAX_PROCESSES)))
      )
    )

    (global.set $tick_counter (i64.add (global.get $tick_counter) (i64.const 1)))
    (local.get $best_pid)
  )

  ;; ── reduce: burn one reduction for current process ─────────────────────
  ;; Returns remaining reductions. 0 = timeslice exhausted, reschedule.
  (func (export "reduce") (result i32)
    (local $base i32)
    (local $remaining i32)

    (if (i32.lt_s (global.get $current_pid) (i32.const 0))
      (then (return (i32.const 0)))
    )

    (local.set $base (call $proc_addr (global.get $current_pid)))
    (local.set $remaining
      (i32.sub
        (i32.load (i32.add (local.get $base) (i32.const 0x08)))
        (i32.const 1)))
    (i32.store (i32.add (local.get $base) (i32.const 0x08))
               (local.get $remaining))

    (local.get $remaining)
  )

  ;; ── kill: terminate a process ──────────────────────────────────────────
  ;; Sets status to dead (4), notifies trap handler if linked.
  (func (export "kill")
        (param $pid i32)
        (param $reason i32)
    (local $base i32)
    (local $trap_pid i32)

    (if (i32.ge_u (local.get $pid) (global.get $MAX_PROCESSES)) (then return))

    (local.set $base (call $proc_addr (local.get $pid)))

    ;; Already dead or free
    (if (i32.le_u (i32.load (i32.add (local.get $base) (i32.const 0x04)))
                  (i32.const 0))
      (then return)
    )

    ;; Set dead
    (i32.store (i32.add (local.get $base) (i32.const 0x04)) (i32.const 4))

    (global.set $process_count
      (i32.sub (global.get $process_count) (i32.const 1)))

    ;; Notify trap handler (linked process) via EXIT message
    (local.set $trap_pid
      (i32.load (i32.add (local.get $base) (i32.const 0x24))))
    (if (i32.ge_s (local.get $trap_pid) (i32.const 0))
      (then
        (drop (call $send_internal
          (local.get $trap_pid)
          (i32.const 1)    ;; atom: 'EXIT'
          (i64.extend_i32_u (local.get $reason))
          (local.get $pid)
        ))
      )
    )
  )

  ;; ── internal send (with explicit sender) ───────────────────────────────
  (func $send_internal
        (param $dst_pid i32)
        (param $msg_tag i32)
        (param $msg_val i64)
        (param $sender i32)
        (result i32)
    (local $base i32)
    (local $tail i32)
    (local $next_tail i32)
    (local $head i32)
    (local $mbox_addr i32)
    (local $msg_addr i32)

    (if (i32.ge_u (local.get $dst_pid) (global.get $MAX_PROCESSES))
      (then (return (i32.const -2)))
    )

    (local.set $base (call $proc_addr (local.get $dst_pid)))
    (local.set $tail (i32.load (i32.add (local.get $base) (i32.const 0x10))))
    (local.set $head (i32.load (i32.add (local.get $base) (i32.const 0x0C))))
    (local.set $next_tail
      (i32.rem_u (i32.add (local.get $tail) (i32.const 1))
                 (global.get $MBOX_CAPACITY)))

    (if (i32.eq (local.get $next_tail) (local.get $head))
      (then (return (i32.const -1)))
    )

    (local.set $mbox_addr
      (i32.add (global.get $MBOX_BASE)
               (i32.mul (local.get $dst_pid) (global.get $MBOX_SLOT_SIZE))))
    (local.set $msg_addr
      (i32.add (local.get $mbox_addr)
               (i32.mul (local.get $tail) (global.get $MBOX_MSG_SIZE))))

    (i32.store (local.get $msg_addr) (local.get $sender))
    (i32.store (i32.add (local.get $msg_addr) (i32.const 4)) (local.get $msg_tag))
    (i64.store (i32.add (local.get $msg_addr) (i32.const 8)) (local.get $msg_val))
    (i64.store (i32.add (local.get $msg_addr) (i32.const 16)) (global.get $tick_counter))

    (i32.store (i32.add (local.get $base) (i32.const 0x10)) (local.get $next_tail))
    (i32.store (i32.add (local.get $base) (i32.const 0x2C))
      (i32.add (i32.load (i32.add (local.get $base) (i32.const 0x2C)))
               (i32.const 1)))

    ;; Wake if waiting
    (if (i32.eq (i32.load (i32.add (local.get $base) (i32.const 0x04)))
                (i32.const 3))
      (then
        (i32.store (i32.add (local.get $base) (i32.const 0x04)) (i32.const 1))
      )
    )

    (i32.const 0)
  )

  ;; ── link: bidirectional process link ───────────────────────────────────
  ;; When either dies, the other gets {EXIT, pid, reason}.
  (func (export "link")
        (param $pid_a i32)
        (param $pid_b i32)
    (local $base_a i32)
    (local $base_b i32)

    (local.set $base_a (call $proc_addr (local.get $pid_a)))
    (local.set $base_b (call $proc_addr (local.get $pid_b)))

    (i32.store (i32.add (local.get $base_a) (i32.const 0x24)) (local.get $pid_b))
    (i32.store (i32.add (local.get $base_b) (i32.const 0x24)) (local.get $pid_a))
  )

  ;; ── process_info: read process status ──────────────────────────────────
  ;; Returns status (0-4) or -1 if invalid pid.
  (func (export "process_info")
        (param $pid i32)
        (result i32)
    (if (i32.ge_u (local.get $pid) (global.get $MAX_PROCESSES))
      (then (return (i32.const -1)))
    )
    (i32.load
      (i32.add (call $proc_addr (local.get $pid)) (i32.const 0x04)))
  )

  ;; ── message_count: how many messages in a process mailbox ──────────────
  (func (export "message_count")
        (param $pid i32)
        (result i32)
    (if (i32.ge_u (local.get $pid) (global.get $MAX_PROCESSES))
      (then (return (i32.const 0)))
    )
    (i32.load
      (i32.add (call $proc_addr (local.get $pid)) (i32.const 0x2C)))
  )

  ;; ── gc_dead: reclaim dead process slots ────────────────────────────────
  ;; Sweeps once, zeroes dead entries. Returns count reclaimed.
  (func (export "gc_dead") (result i32)
    (local $i i32)
    (local $base i32)
    (local $reclaimed i32)

    (local.set $i (i32.const 0))
    (local.set $reclaimed (i32.const 0))

    (loop $gc_loop
      (if (i32.lt_u (local.get $i) (global.get $MAX_PROCESSES))
        (then
          (local.set $base (call $proc_addr (local.get $i)))
          (if (i32.eq
                (i32.load (i32.add (local.get $base) (i32.const 0x04)))
                (i32.const 4))
            (then
              ;; Zero the slot
              (memory.fill (local.get $base) (i32.const 0)
                           (global.get $PROC_SLOT_SIZE))
              (local.set $reclaimed
                (i32.add (local.get $reclaimed) (i32.const 1)))
            )
          )
          (local.set $i (i32.add (local.get $i) (i32.const 1)))
          (br $gc_loop)
        )
      )
    )
    (local.get $reclaimed)
  )
)
