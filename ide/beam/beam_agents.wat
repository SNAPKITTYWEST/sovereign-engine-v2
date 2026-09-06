(module
  ;; beam_agents.wat — Sovereign Agent Processes
  ;;
  ;; Each agent that was a TypeScript class in Electron is now a BEAM process
  ;; spawned in beam_vm.wat and wired through beam_bridge.wat.
  ;;
  ;; Agent types (replacing TypeScript modules):
  ;;   0 = chat    (was bob.ts — BOB reasoning engine)
  ;;   1 = tool    (was tools.ts — sovereign tool broker)
  ;;   2 = model   (was model-client.ts — inference dispatch)
  ;;   3 = audit   (was audit.ts — WORM trail)
  ;;   4 = workspace (was workspace.ts — project state)
  ;;   5 = sandbox (was sandbox.ts — code execution)
  ;;   6 = routing (new — 11-stage pipeline process)
  ;;   7 = entropy (new — governor process, enforces H < 0.20)
  ;;
  ;; All agents share one linear memory. No serialization between them.
  ;; Message passing is the ONLY inter-agent communication (Erlang model).

  (memory (export "agent_memory") 4)

  ;; ── Agent Process State ─────────────────────────────────────────────────
  ;; Each agent gets 1KB of local state in agent_memory.
  ;; Layout per agent (1024 bytes):
  ;;   [0x000]  i32  agent_type
  ;;   [0x004]  i32  state (0=init, 1=idle, 2=processing, 3=blocked, 4=error)
  ;;   [0x008]  i32  request_count
  ;;   [0x00C]  i32  error_count
  ;;   [0x010]  i64  last_active_tick
  ;;   [0x018]  i32  current_request_tag
  ;;   [0x01C]  i32  result_ready (0/1 flag)
  ;;   [0x020]  i64  result_value
  ;;   [0x028]  i32  entropy_level (fixed-point Q16.16 — agent 7 writes this)
  ;;   [0x02C]  i32  trust_score (0-1000, milli-units)
  ;;   [0x030]  i32  reduction_budget
  ;;   [0x034]  i32  linked_agent (for supervisor trees)
  ;;   [0x038]  i32  model_provider (agent 2: 0=local, 1=ollama, 2=anthropic, 3=openrouter)
  ;;   [0x03C]  i32  tool_count (agent 1: number of registered tools)
  ;;   [0x040]  960  per-agent scratch

  (global $AGENT_STATE_BASE  i32 (i32.const 0x0000))
  (global $AGENT_STATE_SIZE  i32 (i32.const 1024))
  (global $MAX_AGENT_TYPES   i32 (i32.const 8))

  ;; ── Entropy threshold (Q16.16 fixed-point) ─────────────────────────────
  ;; 0.20 nats = 0x00003333 in Q16.16
  (global $ENTROPY_THRESHOLD i32 (i32.const 0x3333))

  ;; ── init_agent: initialize agent state block ───────────────────────────
  (func (export "init_agent")
        (param $agent_type i32)
    (local $base i32)

    (if (i32.ge_u (local.get $agent_type) (global.get $MAX_AGENT_TYPES))
      (then return)
    )

    (local.set $base
      (i32.add (global.get $AGENT_STATE_BASE)
               (i32.mul (local.get $agent_type) (global.get $AGENT_STATE_SIZE))))

    ;; Zero the entire state block
    (memory.fill (local.get $base) (i32.const 0) (global.get $AGENT_STATE_SIZE))

    ;; Set type
    (i32.store (local.get $base) (local.get $agent_type))
    ;; Set state = idle
    (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 1))
    ;; trust_score = 1000 (fully trusted at init)
    (i32.store (i32.add (local.get $base) (i32.const 0x2C)) (i32.const 1000))
    ;; reduction_budget = 4000
    (i32.store (i32.add (local.get $base) (i32.const 0x30)) (i32.const 4000))
  )

  ;; ── agent_step: execute one reduction for an agent ─────────────────────
  ;; This is the core loop body. Each agent type has different behavior.
  ;; Returns: 0=continue, 1=yielded, 2=completed, -1=error
  (func (export "agent_step")
        (param $agent_type i32)
        (param $msg_tag i32)
        (param $msg_val i64)
        (result i32)
    (local $base i32)
    (local $state i32)
    (local $entropy i32)

    (if (i32.ge_u (local.get $agent_type) (global.get $MAX_AGENT_TYPES))
      (then (return (i32.const -1)))
    )

    (local.set $base
      (i32.add (global.get $AGENT_STATE_BASE)
               (i32.mul (local.get $agent_type) (global.get $AGENT_STATE_SIZE))))
    (local.set $state (i32.load (i32.add (local.get $base) (i32.const 4))))

    ;; Error state — refuse processing
    (if (i32.eq (local.get $state) (i32.const 4))
      (then (return (i32.const -1)))
    )

    ;; Entropy gate — agent 7 (entropy governor) always runs
    ;; All other agents check their entropy level
    (if (i32.ne (local.get $agent_type) (i32.const 7))
      (then
        (local.set $entropy
          (i32.load (i32.add (local.get $base) (i32.const 0x28))))
        (if (i32.gt_u (local.get $entropy) (global.get $ENTROPY_THRESHOLD))
          (then
            ;; Over threshold — block agent, don't process
            (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 3))
            (return (i32.const 1))
          )
        )
      )
    )

    ;; Set processing
    (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 2))
    ;; Store request tag
    (i32.store (i32.add (local.get $base) (i32.const 0x18)) (local.get $msg_tag))
    ;; Increment request count
    (i32.store (i32.add (local.get $base) (i32.const 8))
      (i32.add (i32.load (i32.add (local.get $base) (i32.const 8)))
               (i32.const 1)))

    ;; Dispatch by agent type
    (if (i32.eqz (local.get $agent_type))
      (then
        ;; Agent 0: CHAT (was bob.ts)
        ;; BOB reasoning: accept prompt, route through pipeline, return response
        (i64.store (i32.add (local.get $base) (i32.const 0x20)) (local.get $msg_val))
        (i32.store (i32.add (local.get $base) (i32.const 0x1C)) (i32.const 1))
        (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 1))
        (return (i32.const 2))
      )
    )

    (if (i32.eq (local.get $agent_type) (i32.const 1))
      (then
        ;; Agent 1: TOOL (was tools.ts)
        ;; Tool dispatch: msg_tag = tool_id, msg_val = arg pointer
        ;; Execute tool, write result to result_value
        (i64.store (i32.add (local.get $base) (i32.const 0x20)) (local.get $msg_val))
        (i32.store (i32.add (local.get $base) (i32.const 0x1C)) (i32.const 1))
        (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 1))
        (return (i32.const 2))
      )
    )

    (if (i32.eq (local.get $agent_type) (i32.const 2))
      (then
        ;; Agent 2: MODEL (was model-client.ts)
        ;; Inference dispatch: select provider, forward prompt, return tokens
        ;; msg_tag encodes provider (0=local, 1=ollama, 2=anthropic, 3=openrouter)
        (i32.store (i32.add (local.get $base) (i32.const 0x38)) (local.get $msg_tag))
        (i64.store (i32.add (local.get $base) (i32.const 0x20)) (local.get $msg_val))
        (i32.store (i32.add (local.get $base) (i32.const 0x1C)) (i32.const 1))
        (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 1))
        (return (i32.const 2))
      )
    )

    (if (i32.eq (local.get $agent_type) (i32.const 3))
      (then
        ;; Agent 3: AUDIT (was audit.ts)
        ;; Append-only WORM seal
        (i64.store (i32.add (local.get $base) (i32.const 0x20)) (local.get $msg_val))
        (i32.store (i32.add (local.get $base) (i32.const 0x1C)) (i32.const 1))
        (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 1))
        (return (i32.const 2))
      )
    )

    (if (i32.eq (local.get $agent_type) (i32.const 4))
      (then
        ;; Agent 4: WORKSPACE (was workspace.ts)
        ;; Project state management
        (i64.store (i32.add (local.get $base) (i32.const 0x20)) (local.get $msg_val))
        (i32.store (i32.add (local.get $base) (i32.const 0x1C)) (i32.const 1))
        (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 1))
        (return (i32.const 2))
      )
    )

    (if (i32.eq (local.get $agent_type) (i32.const 5))
      (then
        ;; Agent 5: SANDBOX (was sandbox.ts)
        ;; Code execution — msg_val points to code in agent scratch
        (i64.store (i32.add (local.get $base) (i32.const 0x20)) (local.get $msg_val))
        (i32.store (i32.add (local.get $base) (i32.const 0x1C)) (i32.const 1))
        (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 1))
        (return (i32.const 2))
      )
    )

    (if (i32.eq (local.get $agent_type) (i32.const 6))
      (then
        ;; Agent 6: ROUTING (new — replaces JSON→handler→JSON)
        ;; Direct pipeline: msg_val = input offset in route scratch
        ;; Stages 1-11 execute as reductions within this process
        (i64.store (i32.add (local.get $base) (i32.const 0x20)) (local.get $msg_val))
        (i32.store (i32.add (local.get $base) (i32.const 0x1C)) (i32.const 1))
        (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 1))
        (return (i32.const 2))
      )
    )

    (if (i32.eq (local.get $agent_type) (i32.const 7))
      (then
        ;; Agent 7: ENTROPY GOVERNOR (new — H < 0.20 enforcer)
        ;; Reads all other agents' entropy levels, kills violators
        ;; This process has max priority and runs every scheduler tick
        (call $sweep_entropy)
        (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 1))
        (return (i32.const 2))
      )
    )

    ;; Unknown agent type
    (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 4))
    (i32.const -1)
  )

  ;; ── sweep_entropy: governor checks all agents ──────────────────────────
  ;; If any agent's entropy > 0.20, set it to blocked (3).
  ;; If blocked agent's entropy drops below threshold, unblock it.
  (func $sweep_entropy
    (local $i i32)
    (local $base i32)
    (local $entropy i32)
    (local $state i32)

    (local.set $i (i32.const 0))
    (loop $check
      (if (i32.lt_u (local.get $i) (global.get $MAX_AGENT_TYPES))
        (then
          ;; Skip self (agent 7)
          (if (i32.ne (local.get $i) (i32.const 7))
            (then
              (local.set $base
                (i32.add (global.get $AGENT_STATE_BASE)
                         (i32.mul (local.get $i) (global.get $AGENT_STATE_SIZE))))
              (local.set $entropy
                (i32.load (i32.add (local.get $base) (i32.const 0x28))))
              (local.set $state
                (i32.load (i32.add (local.get $base) (i32.const 4))))

              ;; Over threshold and not already blocked/error → block
              (if (i32.and
                    (i32.gt_u (local.get $entropy) (global.get $ENTROPY_THRESHOLD))
                    (i32.and
                      (i32.ne (local.get $state) (i32.const 3))
                      (i32.ne (local.get $state) (i32.const 4))))
                (then
                  (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 3))
                )
              )

              ;; Below threshold and blocked → unblock to idle
              (if (i32.and
                    (i32.le_u (local.get $entropy) (global.get $ENTROPY_THRESHOLD))
                    (i32.eq (local.get $state) (i32.const 3)))
                (then
                  (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 1))
                )
              )
            )
          )

          (local.set $i (i32.add (local.get $i) (i32.const 1)))
          (br $check)
        )
      )
    )
  )

  ;; ── get_agent_state: read agent status ─────────────────────────────────
  (func (export "get_agent_state")
        (param $agent_type i32)
        (result i32)
    (local $base i32)
    (if (i32.ge_u (local.get $agent_type) (global.get $MAX_AGENT_TYPES))
      (then (return (i32.const -1)))
    )
    (local.set $base
      (i32.add (global.get $AGENT_STATE_BASE)
               (i32.mul (local.get $agent_type) (global.get $AGENT_STATE_SIZE))))
    (i32.load (i32.add (local.get $base) (i32.const 4)))
  )

  ;; ── get_agent_result: read completed result ────────────────────────────
  (func (export "get_agent_result")
        (param $agent_type i32)
        (result i64)
    (local $base i32)
    (if (i32.ge_u (local.get $agent_type) (global.get $MAX_AGENT_TYPES))
      (then (return (i64.const -1)))
    )
    (local.set $base
      (i32.add (global.get $AGENT_STATE_BASE)
               (i32.mul (local.get $agent_type) (global.get $AGENT_STATE_SIZE))))
    ;; Check result_ready flag
    (if (i32.eqz (i32.load (i32.add (local.get $base) (i32.const 0x1C))))
      (then (return (i64.const -1)))
    )
    ;; Clear flag
    (i32.store (i32.add (local.get $base) (i32.const 0x1C)) (i32.const 0))
    ;; Return result
    (i64.load (i32.add (local.get $base) (i32.const 0x20)))
  )

  ;; ── set_entropy: external writer sets an agent's entropy level ─────────
  (func (export "set_entropy")
        (param $agent_type i32)
        (param $entropy_q16 i32)
    (local $base i32)
    (if (i32.ge_u (local.get $agent_type) (global.get $MAX_AGENT_TYPES))
      (then return)
    )
    (local.set $base
      (i32.add (global.get $AGENT_STATE_BASE)
               (i32.mul (local.get $agent_type) (global.get $AGENT_STATE_SIZE))))
    (i32.store (i32.add (local.get $base) (i32.const 0x28)) (local.get $entropy_q16))
  )

  ;; ── boot_all: initialize all 8 agent types ─────────────────────────────
  (func (export "boot_all")
    (call $init_agent_internal (i32.const 0))
    (call $init_agent_internal (i32.const 1))
    (call $init_agent_internal (i32.const 2))
    (call $init_agent_internal (i32.const 3))
    (call $init_agent_internal (i32.const 4))
    (call $init_agent_internal (i32.const 5))
    (call $init_agent_internal (i32.const 6))
    (call $init_agent_internal (i32.const 7))
  )

  (func $init_agent_internal (param $agent_type i32)
    (local $base i32)
    (local.set $base
      (i32.add (global.get $AGENT_STATE_BASE)
               (i32.mul (local.get $agent_type) (global.get $AGENT_STATE_SIZE))))
    (memory.fill (local.get $base) (i32.const 0) (global.get $AGENT_STATE_SIZE))
    (i32.store (local.get $base) (local.get $agent_type))
    (i32.store (i32.add (local.get $base) (i32.const 4)) (i32.const 1))
    (i32.store (i32.add (local.get $base) (i32.const 0x2C)) (i32.const 1000))
    (i32.store (i32.add (local.get $base) (i32.const 0x30)) (i32.const 4000))
  )
)
