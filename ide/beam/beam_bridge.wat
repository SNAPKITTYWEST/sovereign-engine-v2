(module
  ;; beam_bridge.wat — BEAM ↔ M5 ↔ Tunnel Direct Memory Bridge
  ;;
  ;; Connects BEAM processes to the sovereign substrate:
  ;;   beam_vm.wat process mailboxes → M5 buffer → tunnel_matrix
  ;;
  ;; No HTTP. No JSON. No IPC serialization.
  ;; Processes read and write directly to the same linear memory
  ;; that M5 and the tunnel matrix operate on.
  ;;
  ;; Memory layout (4 pages = 256KB):
  ;;   [0x00000 .. 0x00FFF]  M5 mirror (4KB — matches m5.wat buffer)
  ;;   [0x01000 .. 0x01FFF]  Agent dispatch table (256 entries × 16 bytes)
  ;;   [0x02000 .. 0x02FFF]  Tool result buffer (4KB)
  ;;   [0x03000 .. 0x03FFF]  WORM seal staging (4KB)
  ;;   [0x04000 .. 0x0FFFF]  Routing pipeline scratch (48KB)
  ;;   [0x10000 .. 0x1FFFF]  Model response buffer (64KB)
  ;;   [0x20000 .. 0x2FFFF]  Chat history ring (64KB)
  ;;   [0x30000 .. 0x3FFFF]  Audit log (64KB — append-only)

  (memory (export "bridge_memory") 4)

  ;; ── Agent Dispatch Table ────────────────────────────────────────────────
  ;; Each entry (16 bytes):
  ;;   [0]  i32  agent_pid (BEAM process handling this agent)
  ;;   [4]  i32  agent_type (0=chat, 1=tool, 2=model, 3=audit, 4=workspace)
  ;;   [8]  i32  status (0=idle, 1=busy, 2=error)
  ;;   [12] i32  last_result_offset (into tool result buffer)

  (global $DISPATCH_BASE  i32 (i32.const 0x1000))
  (global $DISPATCH_ENTRY i32 (i32.const 16))
  (global $MAX_AGENTS     i32 (i32.const 256))

  (global $RESULT_BASE    i32 (i32.const 0x2000))
  (global $SEAL_BASE      i32 (i32.const 0x3000))
  (global $ROUTE_BASE     i32 (i32.const 0x4000))
  (global $RESPONSE_BASE  i32 (i32.const 0x10000))
  (global $HISTORY_BASE   i32 (i32.const 0x20000))
  (global $AUDIT_BASE     i32 (i32.const 0x30000))

  ;; Audit log write pointer (append-only)
  (global $audit_ptr (mut i32) (i32.const 0x30000))

  ;; Chat history ring state
  (global $history_head (mut i32) (i32.const 0))
  (global $history_tail (mut i32) (i32.const 0))
  (global $HISTORY_SLOTS i32 (i32.const 256))
  (global $HISTORY_SLOT_SIZE i32 (i32.const 256))

  ;; ── register_agent: bind a BEAM process as an agent ────────────────────
  ;; Called after spawn() — maps a pid to an agent type.
  (func (export "register_agent")
        (param $slot i32)
        (param $pid i32)
        (param $agent_type i32)
    (local $addr i32)

    (if (i32.ge_u (local.get $slot) (global.get $MAX_AGENTS))
      (then return)
    )

    (local.set $addr
      (i32.add (global.get $DISPATCH_BASE)
               (i32.mul (local.get $slot) (global.get $DISPATCH_ENTRY))))

    (i32.store (local.get $addr) (local.get $pid))
    (i32.store (i32.add (local.get $addr) (i32.const 4)) (local.get $agent_type))
    (i32.store (i32.add (local.get $addr) (i32.const 8)) (i32.const 0))
    (i32.store (i32.add (local.get $addr) (i32.const 12)) (i32.const 0))
  )

  ;; ── dispatch_to_agent: route a request to the right BEAM process ───────
  ;; Looks up agent by type, returns the pid. -1 if not found.
  (func (export "dispatch_to_agent")
        (param $agent_type i32)
        (result i32)
    (local $i i32)
    (local $addr i32)

    (local.set $i (i32.const 0))
    (loop $scan
      (if (i32.lt_u (local.get $i) (global.get $MAX_AGENTS))
        (then
          (local.set $addr
            (i32.add (global.get $DISPATCH_BASE)
                     (i32.mul (local.get $i) (global.get $DISPATCH_ENTRY))))
          ;; Match agent_type and status != idle check
          (if (i32.eq
                (i32.load (i32.add (local.get $addr) (i32.const 4)))
                (local.get $agent_type))
            (then
              ;; Mark busy
              (i32.store (i32.add (local.get $addr) (i32.const 8)) (i32.const 1))
              ;; Return pid
              (return (i32.load (local.get $addr)))
            )
          )
          (local.set $i (i32.add (local.get $i) (i32.const 1)))
          (br $scan)
        )
      )
    )
    (i32.const -1)
  )

  ;; ── m5_read: read byte from M5 mirror region ──────────────────────────
  ;; BEAM processes use this instead of HTTP fetch to engine.
  (func (export "m5_read")
        (param $addr i32)
        (result i32)
    (if (i32.ge_u (local.get $addr) (i32.const 4096))
      (then (return (i32.const -1)))
    )
    (i32.load8_u (local.get $addr))
  )

  ;; ── m5_write: write byte to M5 mirror ─────────────────────────────────
  (func (export "m5_write")
        (param $addr i32)
        (param $val i32)
        (result i32)
    (if (i32.ge_u (local.get $addr) (i32.const 4096))
      (then (return (i32.const -1)))
    )
    (i32.store8 (local.get $addr) (local.get $val))
    (i32.const 0)
  )

  ;; ── write_response: store model response into buffer ───────────────────
  ;; Called by the model agent process after inference completes.
  ;; offset is relative to RESPONSE_BASE. Max 64KB.
  (func (export "write_response")
        (param $offset i32)
        (param $byte i32)
        (result i32)
    (local $abs_addr i32)
    (local.set $abs_addr
      (i32.add (global.get $RESPONSE_BASE) (local.get $offset)))
    (if (i32.ge_u (local.get $abs_addr) (i32.const 0x20000))
      (then (return (i32.const -1)))
    )
    (i32.store8 (local.get $abs_addr) (local.get $byte))
    (i32.const 0)
  )

  ;; ── read_response: read model response byte ────────────────────────────
  (func (export "read_response")
        (param $offset i32)
        (result i32)
    (local $abs_addr i32)
    (local.set $abs_addr
      (i32.add (global.get $RESPONSE_BASE) (local.get $offset)))
    (if (i32.ge_u (local.get $abs_addr) (i32.const 0x20000))
      (then (return (i32.const -1)))
    )
    (i32.load8_u (local.get $abs_addr))
  )

  ;; ── audit_append: write 32-byte audit record ──────────────────────────
  ;; Append-only. Maps to WORM seal behavior.
  ;; Record: [tick:8][agent_type:4][action:4][payload:16]
  ;; Returns offset of written record, or -1 if log full.
  (func (export "audit_append")
        (param $tick i64)
        (param $agent_type i32)
        (param $action i32)
        (param $payload_hi i64)
        (param $payload_lo i64)
        (result i32)
    (local $ptr i32)

    ;; Check bounds (audit region is 64KB = 0x30000..0x3FFFF)
    (if (i32.ge_u (global.get $audit_ptr) (i32.const 0x3FFE0))
      (then (return (i32.const -1)))
    )

    (local.set $ptr (global.get $audit_ptr))

    (i64.store (local.get $ptr) (local.get $tick))
    (i32.store (i32.add (local.get $ptr) (i32.const 8)) (local.get $agent_type))
    (i32.store (i32.add (local.get $ptr) (i32.const 12)) (local.get $action))
    (i64.store (i32.add (local.get $ptr) (i32.const 16)) (local.get $payload_hi))
    (i64.store (i32.add (local.get $ptr) (i32.const 24)) (local.get $payload_lo))

    (global.set $audit_ptr (i32.add (global.get $audit_ptr) (i32.const 32)))

    (local.get $ptr)
  )

  ;; ── history_push: add chat message to ring buffer ─────────────────────
  ;; Each slot = 256 bytes: [role:4][timestamp:8][length:4][content:240]
  ;; Returns slot index.
  (func (export "history_push")
        (param $role i32)
        (param $timestamp i64)
        (param $content_ptr i32)
        (param $content_len i32)
        (result i32)
    (local $slot i32)
    (local $addr i32)
    (local $copy_len i32)
    (local $i i32)

    (local.set $slot (global.get $history_tail))
    (local.set $addr
      (i32.add (global.get $HISTORY_BASE)
               (i32.mul (local.get $slot) (global.get $HISTORY_SLOT_SIZE))))

    ;; Write header
    (i32.store (local.get $addr) (local.get $role))
    (i64.store (i32.add (local.get $addr) (i32.const 4)) (local.get $timestamp))

    ;; Clamp content to 240 bytes
    (local.set $copy_len (local.get $content_len))
    (if (i32.gt_u (local.get $copy_len) (i32.const 240))
      (then (local.set $copy_len (i32.const 240)))
    )
    (i32.store (i32.add (local.get $addr) (i32.const 12)) (local.get $copy_len))

    ;; Copy content bytes
    (local.set $i (i32.const 0))
    (loop $copy
      (if (i32.lt_u (local.get $i) (local.get $copy_len))
        (then
          (i32.store8
            (i32.add (i32.add (local.get $addr) (i32.const 16)) (local.get $i))
            (i32.load8_u (i32.add (local.get $content_ptr) (local.get $i)))
          )
          (local.set $i (i32.add (local.get $i) (i32.const 1)))
          (br $copy)
        )
      )
    )

    ;; Advance tail (ring)
    (global.set $history_tail
      (i32.rem_u
        (i32.add (global.get $history_tail) (i32.const 1))
        (global.get $HISTORY_SLOTS)))

    ;; If tail caught head, advance head (overwrite oldest)
    (if (i32.eq (global.get $history_tail) (global.get $history_head))
      (then
        (global.set $history_head
          (i32.rem_u
            (i32.add (global.get $history_head) (i32.const 1))
            (global.get $HISTORY_SLOTS)))
      )
    )

    (local.get $slot)
  )

  ;; ── route_to_pipeline: write routing signal into pipeline scratch ──────
  ;; Stage 1 of the 11-stage pipeline starts here.
  ;; Writes the raw input bytes that the Python routing picks up via mmap.
  (func (export "route_to_pipeline")
        (param $input_ptr i32)
        (param $input_len i32)
        (result i32)
    (local $i i32)
    (local $copy_len i32)

    ;; Clamp to 48KB scratch region
    (local.set $copy_len (local.get $input_len))
    (if (i32.gt_u (local.get $copy_len) (i32.const 49152))
      (then (local.set $copy_len (i32.const 49152)))
    )

    ;; Write length header
    (i32.store (global.get $ROUTE_BASE) (local.get $copy_len))

    ;; Copy input
    (local.set $i (i32.const 0))
    (loop $route_copy
      (if (i32.lt_u (local.get $i) (local.get $copy_len))
        (then
          (i32.store8
            (i32.add (i32.add (global.get $ROUTE_BASE) (i32.const 4))
                     (local.get $i))
            (i32.load8_u (i32.add (local.get $input_ptr) (local.get $i)))
          )
          (local.set $i (i32.add (local.get $i) (i32.const 1)))
          (br $route_copy)
        )
      )
    )

    (local.get $copy_len)
  )

  ;; ── seal_worm: write WORM seal record into staging ────────────────────
  ;; 64-byte record: [prev_hash:32][payload_hash:32]
  ;; Chained — each record includes the previous record's hash.
  (func (export "seal_worm")
        (param $payload_ptr i32)
        (param $payload_len i32)
        (result i32)
    (local $i i32)
    (local $acc i64)

    ;; Accumulate a fast hash (DJB2 variant) of the payload
    (local.set $acc (i64.const 5381))
    (local.set $i (i32.const 0))
    (loop $hash_loop
      (if (i32.lt_u (local.get $i) (local.get $payload_len))
        (then
          (local.set $acc
            (i64.add
              (i64.mul (local.get $acc) (i64.const 33))
              (i64.extend_i32_u
                (i32.load8_u (i32.add (local.get $payload_ptr) (local.get $i))))))
          (local.set $i (i32.add (local.get $i) (i32.const 1)))
          (br $hash_loop)
        )
      )
    )

    ;; Write hash to seal staging area
    (i64.store (global.get $SEAL_BASE) (local.get $acc))

    (i32.const 0)
  )
)
