# State Machines Documentation

Formal state machines and state diagrams for complex stateful components in Sovereign Engine.

---

## 1. Agent State Machine

The ReActAgent maintains explicit state throughout task execution.

```mermaid
stateDiagram-v2
    [*] --> Initialized
    
    Initialized --> Thought: new_task()
    
    Thought --> ModelCall: generate_thought()
    ModelCall --> ResponseParsed: model returns
    
    ResponseParsed --> Decision: parse_response()
    
    Decision --> ToolCall: tool_call detected
    Decision --> FinalAnswer: final_answer detected
    
    ToolCall --> Approval: tool_requires_approval?
    
    Approval --> ApprovalWait: yes
    Approval --> ToolExecution: no
    
    ApprovalWait --> ApprovalDecision: user responds
    ApprovalDecision --> ToolExecution: approved
    ApprovalDecision --> ToolRejected: rejected
    
    ToolRejected --> Observation: record rejection
    
    ToolExecution --> ToolSuccess: tool succeeds
    ToolExecution --> ToolError: tool fails
    
    ToolSuccess --> Observation: record result
    ToolError --> Reflection: error occurred
    
    Reflection --> ErrorHandling: analyze error
    ErrorHandling --> Thought: recovered
    ErrorHandling --> FinalAnswer: give up
    
    Observation --> StepCount: increment step
    StepCount --> ContinueCheck: check max steps
    
    ContinueCheck --> Thought: steps < max
    ContinueCheck --> FinalAnswer: steps >= max
    
    FinalAnswer --> BuildTrajectory: gather all steps
    
    BuildTrajectory --> Verify: run ERE gate
    Verify --> VerifyPass: passed
    Verify --> VerifyFail: failed
    
    VerifyFail --> RegenerateAnswer: retry
    RegenerateAnswer --> ModelCall: ask model to fix
    
    VerifyPass --> Sealing: seal trajectory
    
    Sealing --> Complete: WORM sealed
    Complete --> [*]
    
    state Decision {
        [*] --> CheckResponse
    }
    
    style Complete fill:#90EE90
    style VerifyPass fill:#90EE90
    style ToolError fill:#FFE4B5
    style Reflection fill:#FFE4B5
```

### State Descriptions

| State | Entry | Exit | Timeout |
|-------|-------|------|---------|
| Thought | Previous step done | Thought generated | 30s |
| ModelCall | Thought ready | Model responds | 60s |
| ToolCall | Tool invoked | Tool completes | 30s |
| ApprovalWait | Approval needed | User responds | 30s |
| Reflection | Error detected | Recovery attempted | 10s |
| Verify | Final answer ready | Verification complete | 5s |
| Sealing | Verification passed | WORM entry complete | 1s |

---

## 2. Continuity Manager State Machine

Hot-restart capability with state persistence.

```mermaid
stateDiagram-v2
    [*] --> CheckState: system init
    
    CheckState --> NoState: no state found
    CheckState --> StateExists: state file exists
    
    NoState --> Fresh: create fresh context
    Fresh --> Running: start execution
    
    StateExists --> LoadState: load from disk
    LoadState --> ValidateState: check integrity
    
    ValidateState --> StateValid: hash verified
    ValidateState --> StateCorrupt: hash mismatch
    
    StateCorrupt --> Fresh: revert to fresh
    
    StateValid --> HotRestart: resume mode
    HotRestart --> Resume: load step offset
    Resume --> Running: continue from checkpoint
    
    Running --> Active: executing task
    
    Active --> Checkpoint: checkpoint interval
    Checkpoint --> CheckpointWrite: serialize state
    CheckpointWrite --> CheckpointSuccess: saved
    CheckpointSuccess --> Active: continue
    
    Active --> Complete: task done
    Complete --> Cleanup: cleanup state
    Cleanup --> [*]
    
    Active --> Crash: exception/signal
    Crash --> EmergencyCheckpoint: save state
    EmergencyCheckpoint --> [*]
    
    state Running {
        [*] --> Active
    }
    
    style Complete fill:#90EE90
    style HotRestart fill:#87CEEB
    style Checkpoint fill:#FFD700
    style Crash fill:#FFE4B5
```

### Checkpoint Lifecycle

```
NORMAL FLOW:
  Running → [checkpoint every 10 steps] → Save to disk → Continue

CRASH SCENARIO:
  Running → Exception → Emergency checkpoint → Disk write → Exit

RECOVERY:
  Next run → Check for checkpoint → Load state → Resume from step N
```

---

## 3. Router Circuit Breaker

Protects system from cascade failures.

```mermaid
stateDiagram-v2
    [*] --> CLOSED
    
    CLOSED --> CLOSED: success (reset counter)
    CLOSED --> OPEN: failure_count >= threshold
    
    OPEN --> OPEN: wait for timeout
    OPEN --> HALF_OPEN: timeout exceeded
    
    HALF_OPEN --> CLOSED: test call succeeds
    HALF_OPEN --> OPEN: test call fails
    
    state CLOSED {
        [*] --> AcceptingCalls
        AcceptingCalls --> FailureCounter: on failure
        FailureCounter --> ResetCounter: on success
    }
    
    state OPEN {
        [*] --> RejectingCalls
        RejectingCalls --> TimerRunning: wait Timeout_s
    }
    
    state HALF_OPEN {
        [*] --> ProbeCall
        ProbeCall --> TestResult: call completes
    }
    
    style CLOSED fill:#90EE90
    style OPEN fill:#FFB6C6
    style HALF_OPEN fill:#FFE4B5
```

### Parameters

- `failure_threshold` — failures before opening (default: 5)
- `timeout_s` — how long to keep circuit open (default: 60)
- `half_open_max_calls` — calls allowed in half-open state (default: 1)

---

## 4. Tool Execution State Machine

State flow for tool invocation and result handling.

```mermaid
stateDiagram-v2
    [*] --> Scheduled
    
    Scheduled --> Validation: tool call received
    Validation --> ValidFail: schema mismatch
    Validation --> ValidPass: schema OK
    
    ValidFail --> Rejected: return error
    ValidPass --> Approved: approval not needed
    ValidPass --> AwaitingApproval: approval required
    
    AwaitingApproval --> UserDenied: user rejects
    AwaitingApproval --> UserApproved: user approves
    AwaitingApproval --> ApprovalTimeout: timeout
    
    UserDenied --> Rejected
    ApprovalTimeout --> Rejected
    
    UserApproved --> Executing: start subprocess
    Approved --> Executing
    
    Executing --> Timeout: > timeout_ms
    Executing --> Success: exit code 0
    Executing --> Error: exit code != 0
    
    Timeout --> KilledProcess: SIGKILL process
    KilledProcess --> TimedOut: mark as timeout
    
    Success --> Captured: capture stdout/stderr
    Error --> Captured
    TimedOut --> Captured
    
    Captured --> Result: return ToolResult
    
    Rejected --> Result
    Result --> [*]
    
    state Executing {
        [*] --> Running
        Running --> StderrCapture: live capture
    }
    
    style Success fill:#90EE90
    style Error fill:#FFE4B5
    style Timeout fill:#FFE4B5
    style Rejected fill:#FFB6C6
```

---

## 5. Request Lifecycle State Machine

HTTP request state progression.

```mermaid
stateDiagram-v2
    [*] --> Received
    
    Received --> Parsing: body received
    Parsing --> ParseFail: JSON error
    Parsing --> ParseSuccess: valid JSON
    
    ParseFail --> ValidationError: malformed
    
    ParseSuccess --> Validation: check schema
    Validation --> ValidationFail: invalid
    Validation --> ValidationPass: valid
    
    ValidationFail --> ValidationError
    ValidationPass --> Queued: add to queue
    
    ValidationError --> ErrorResponse: 400/413
    
    Queued --> Routing: routing pipeline
    Routing --> Dispatched: expert selected
    Dispatched --> Processing: agent running
    Processing --> ProcessFail: error/timeout
    Processing --> ProcessSuccess: complete
    
    ProcessFail --> ErrorResponse
    ProcessSuccess --> Formatting: format result
    Formatting --> Sealed: WORM sealed
    Sealed --> Response: send JSON
    Response --> [*]
    
    ErrorResponse --> [*]
    
    state Processing {
        [*] --> AgentLoop
        AgentLoop --> Steps: 1..N
    }
    
    style Response fill:#90EE90
    style Sealed fill:#FFD700
    style ProcessFail fill:#FFE4B5
    style ErrorResponse fill:#FFB6C6
```

---

## 6. WORM Ledger Chain Validation State Machine

Chain integrity verification.

```mermaid
stateDiagram-v2
    [*] --> LoadEntries
    
    LoadEntries --> LoadFail: cannot read
    LoadFail --> ChainInvalid: [*]
    
    LoadEntries --> InitialEntry: check first entry
    InitialEntry --> EntryOK: valid
    InitialEntry --> EntryBad: invalid
    
    EntryBad --> ChainInvalid
    
    EntryOK --> IterateEntries: start validation loop
    
    IterateEntries --> GetEntry: fetch next
    GetEntry --> NoMoreEntries: end of chain
    GetEntry --> ValidateEntry: entry found
    
    ValidateEntry --> CheckHash: verify Blake3 hash
    CheckHash --> HashMatch: hash OK
    CheckHash --> HashMismatch: hash FAIL
    
    HashMismatch --> ChainInvalid
    
    HashMatch --> CheckSequence: seq == prev+1?
    CheckSequence --> SeqOK: sequence valid
    CheckSequence --> SeqBad: sequence gap
    
    SeqBad --> ChainInvalid
    
    SeqOK --> CheckChain: chain hash valid?
    CheckChain --> ChainOK: links OK
    CheckChain --> ChainBad: links broken
    
    ChainBad --> ChainInvalid
    ChainOK --> IterateEntries
    
    NoMoreEntries --> ChainValid
    
    ChainValid --> [*]
    ChainInvalid --> [*]
    
    style ChainValid fill:#90EE90
    style ChainInvalid fill:#FFB6C6
```

---

## 7. Model Provider Fallback State Machine

Selection and fallover between model providers.

```mermaid
stateDiagram-v2
    [*] --> SelectPrimary
    
    SelectPrimary --> PrimaryHealthy: check health
    PrimaryHealthy --> UsePrimary: healthy
    PrimaryHealthy --> PrimaryDown: unhealthy
    
    UsePrimary --> Invoke: call model
    Invoke --> PrimarySuccess: response OK
    Invoke --> PrimaryTimeout: timeout
    Invoke --> PrimaryError: error
    
    PrimarySuccess --> [*]
    
    PrimaryDown --> SelectSecondary: switch provider
    PrimaryTimeout --> RetryLogic: exponential backoff
    PrimaryError --> SelectSecondary
    
    RetryLogic --> MaxRetries: retries exhausted?
    MaxRetries --> Continue: try again
    MaxRetries --> SelectSecondary: give up
    
    Continue --> Invoke
    
    SelectSecondary --> SecondaryAvail: available?
    SecondaryAvail --> UseSecondary: yes
    SecondaryAvail --> UseMock: no
    
    UseSecondary --> InvokeSecondary: call model
    InvokeSecondary --> SecondarySuccess: response OK
    InvokeSecondary --> SecondaryFail: fails
    
    SecondarySuccess --> [*]
    SecondaryFail --> UseMock
    
    UseMock --> GenerateMock: template response
    GenerateMock --> MockComplete: mock result
    MockComplete --> [*]
    
    style PrimarySuccess fill:#90EE90
    style SecondarySuccess fill:#90EE90
    style MockComplete fill:#FFE4B5
    style PrimaryDown fill:#FFE4B5
```

---

## 8. Error Recovery State Machine

Error detection and recovery flow.

```mermaid
stateDiagram-v2
    [*] --> Normal
    
    Normal --> Normal: success
    Normal --> ErrorDetected: exception
    
    ErrorDetected --> Classify: categorize error
    
    Classify --> UserError: ValueError, TypeError
    Classify --> SystemError: FileNotFoundError, etc
    Classify --> Fatal: SystemExit, SIGSEGV
    
    UserError --> Log: log WARNING
    SystemError --> Log: log ERROR
    Fatal --> Log: log CRITICAL
    
    Log --> Recoverable: can recover?
    
    Recoverable --> NoRecover: not recoverable
    Recoverable --> TryRecover: recoverable
    
    NoRecover --> PropagateUp: raise exception
    TryRecover --> Cleanup: release resources
    Cleanup --> Retry: attempt recovery
    
    Retry --> RetrySuccess: recovery OK
    Retry --> RetryFail: recovery failed
    
    RetrySuccess --> Normal
    RetryFail --> PropagateUp
    
    PropagateUp --> Fallback: use fallback
    Fallback --> Degraded: degraded mode
    
    Degraded --> [*]
    Normal --> [*]
    
    style Normal fill:#90EE90
    style Degraded fill:#FFE4B5
    style Fatal fill:#FFB6C6
```

---

## Summary

**8 state machines:**

1. **Agent** — Task execution loop (thought → action → observe)
2. **Continuity** — Hot-restart with checkpointing
3. **Circuit Breaker** — Cascade failure protection
4. **Tool Execution** — Tool invocation lifecycle
5. **Request Lifecycle** — HTTP request states
6. **WORM Validation** — Chain integrity verification
7. **Model Fallover** — Provider selection & switching
8. **Error Recovery** — Error handling & recovery

All machines use:
- **Explicit states** — clear state transitions
- **Entry/exit conditions** — guards and timeouts
- **Error paths** — recovery and degradation
- **Immutability** — once in state, no reverse without explicit reset

States track system behavior for debugging, monitoring, and resilience.
