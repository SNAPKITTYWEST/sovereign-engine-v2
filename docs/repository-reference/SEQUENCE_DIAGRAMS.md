# Sequence Diagrams

Temporal interaction diagrams showing component communication, message ordering, and timing constraints for complex multi-actor flows.

---

## 1. HTTP Request Processing Sequence

```mermaid
sequenceDiagram
    actor Client
    participant Bridge as HTTPBridge
    participant Parser as RequestParser
    participant Router as RoutingPipeline
    participant Agent as ReActAgent
    participant Model as BedrockBackend
    participant Tools as ToolRegistry
    
    Client->>Bridge: POST /chat {messages, max_tokens}
    activate Bridge
    
    Bridge->>Parser: Parse request
    activate Parser
    Parser->>Parser: Validate schema
    Parser-->>Bridge: Task entity
    deactivate Parser
    
    Bridge->>Router: route(task_text)
    activate Router
    Router->>Router: 11-stage pipeline
    Router-->>Bridge: DispatchResult
    deactivate Router
    
    Bridge->>Agent: run(Task)
    activate Agent
    
    Agent->>Agent: Step 0: Generate thought
    Agent->>Model: invoke(prompt)
    activate Model
    Model->>Model: Bedrock API call
    Model-->>Agent: model response
    deactivate Model
    
    Agent->>Agent: Parse response
    alt Tool call
        Agent->>Tools: execute(tool_name, args)
        activate Tools
        Tools->>Tools: Run tool subprocess
        Tools-->>Agent: ToolResult
        deactivate Tools
        Agent->>Agent: Record observation
        Agent->>Agent: Reflection if error
    else Final answer
        Agent->>Agent: Build trajectory
    end
    
    loop While steps < max_steps
        Agent->>Model: invoke(next_prompt)
        activate Model
        Model-->>Agent: model response
        deactivate Model
        Agent->>Agent: Process response
    end
    
    Agent->>Agent: Verify with ERE gate
    Agent->>Agent: Seal to WORM ledger
    Agent-->>Bridge: AgentTrajectory
    deactivate Agent
    
    Bridge->>Bridge: Format JSON response
    Bridge-->>Client: 200 OK {result, metadata}
    deactivate Bridge
```

**Key timing constraints:**
- Model call: <60s timeout
- Tool call: <30s timeout
- Total request: <5m timeout
- Agent loop: max 10 steps

---

## 2. Routing Pipeline Internal Message Flow

```mermaid
sequenceDiagram
    participant Input as TaskInput
    participant Parse as RegexParser
    participant AST as ASTBuilder
    participant Graph as SymbolicGraph
    participant Jordan as JordanTransformer
    participant Jacob as JacobianLens
    participant Constraint as ConstraintEval
    participant Sparse as SparseActivation
    participant Nodes as RoutingNodes
    participant NAND as NANDFilter
    participant Dispatch as AgentDispatch
    
    Input->>Parse: text + tokens
    Parse->>AST: tokenized input
    AST->>Graph: parse tree
    Graph->>Jordan: adjacency matrix
    Jordan->>Jacob: eigenvalues + eigenvectors
    Jacob->>Constraint: condition number + features
    Constraint->>Sparse: constraint violations
    Sparse->>Nodes: active experts + top-k
    Nodes->>NAND: routing scores per expert
    NAND->>Dispatch: conflict-free expert list
    Dispatch->>Input: DispatchResult
```

**Pipeline order:**
1. Parse → 2. AST → 3. Graph → 4. Jordan → 5. Jacobian
6. Constraint → 7. Sparse → 8. Nodes → 9. NAND → 10. Dispatch

---

## 3. Tool Execution with Approval

```mermaid
sequenceDiagram
    actor Agent
    participant ToolRegistry
    participant ApprovalEngine
    actor User
    participant Tool
    
    Agent->>ToolRegistry: lookup(tool_name)
    ToolRegistry-->>Agent: Tool policy
    
    Agent->>ApprovalEngine: check_approval(tool_name, args)
    activate ApprovalEngine
    
    alt Approval not required
        ApprovalEngine-->>Agent: approved=true
    else Approval required
        ApprovalEngine->>User: Request approval?
        activate User
        alt User approves
            User-->>ApprovalEngine: approved
        else User rejects
            User-->>ApprovalEngine: rejected
        else Timeout (30s)
            ApprovalEngine-->>ApprovalEngine: timeout → rejected
        end
        deactivate User
        ApprovalEngine-->>Agent: approved flag
    end
    deactivate ApprovalEngine
    
    alt Approved
        Agent->>Tool: execute(args)
        activate Tool
        Tool->>Tool: subprocess.run()
        Tool-->>Agent: ToolResult {output, error, rc}
        deactivate Tool
    else Rejected
        Agent->>Agent: Return rejection error
    end
```

**Timing:**
- Approval request: 30s timeout
- Tool execution: 30s timeout

---

## 4. Continuity Checkpoint & Recovery

```mermaid
sequenceDiagram
    participant Agent
    participant ContinuityManager
    participant Disk as FileSystem
    
    Agent->>ContinuityManager: __init__()
    activate ContinuityManager
    
    ContinuityManager->>Disk: Check for prior state
    alt State exists
        Disk-->>ContinuityManager: state.json
        ContinuityManager->>ContinuityManager: Validate state integrity
        ContinuityManager-->>Agent: was_restarted=true, step=5
    else No state
        Disk-->>ContinuityManager: FileNotFoundError
        ContinuityManager-->>Agent: was_restarted=false
    end
    deactivate ContinuityManager
    
    loop Every step
        Agent->>Agent: Execute step
        Agent->>ContinuityManager: checkpoint(step_data)
        activate ContinuityManager
        ContinuityManager->>ContinuityManager: Serialize state
        ContinuityManager->>Disk: Write ~/.sovereign/continuity/{id}/state.json
        Disk-->>ContinuityManager: write ack
        ContinuityManager-->>Agent: checkpoint_saved
        deactivate ContinuityManager
    end
    
    par Recovery scenario
        Agent->>Agent: Crash or interrupt
        activate Agent
        Agent->>ContinuityManager: Emergency checkpoint
        activate ContinuityManager
        ContinuityManager->>Disk: Save emergency state
        deactivate ContinuityManager
        deactivate Agent
    end
    
    Agent->>ContinuityManager: Resume from checkpoint
    activate ContinuityManager
    ContinuityManager->>Disk: Read state.json
    Disk-->>ContinuityManager: state data
    ContinuityManager-->>Agent: Loaded state, resume at step 5
    deactivate ContinuityManager
```

**Checkpoint interval:** Every 10 steps by default

---

## 5. WORM Ledger Sealing Chain

```mermaid
sequenceDiagram
    participant Event
    participant WORMLedger
    participant Hash as Blake3
    participant File as FileSystem
    
    loop Each event to log
        Event->>WORMLedger: append(event_data)
        activate WORMLedger
        
        WORMLedger->>Hash: previous_hash
        WORMLedger->>Hash: event_data
        Hash->>Hash: blake3(data || prev_hash)
        Hash-->>WORMLedger: current_hash
        
        WORMLedger->>WORMLedger: Serialize event + hash
        WORMLedger->>File: Write JSONL entry
        activate File
        
        alt Write success
            File-->>WORMLedger: entry saved
            WORMLedger-->>Event: seq, seal_hash
        else Write failure
            File-->>WORMLedger: I/O error
            WORMLedger->>File: Retry (max 3 attempts)
            alt Retry succeeds
                File-->>WORMLedger: entry saved
            else All retries fail
                File-->>WORMLedger: fatal error
                WORMLedger-->>Event: error, no seal
            end
        end
        deactivate File
        deactivate WORMLedger
    end
    
    WORMLedger->>File: Validate chain integrity
    activate File
    File->>File: Recompute all hashes
    File-->>WORMLedger: valid or invalid
    deactivate File
```

**Chain validation:** Verifies all hashes and sequence continuity

---

## 6. Error Recovery with Retry

```mermaid
sequenceDiagram
    participant Caller
    participant Operation
    participant Logger
    
    Caller->>Operation: execute()
    activate Operation
    
    loop Retry with backoff (max 3)
        Operation->>Operation: Attempt operation
        
        alt Success
            Operation-->>Caller: result
            deactivate Operation
        else Failure
            Operation->>Logger: log(attempt N, error)
            Logger->>Logger: Write to log file
            
            alt Final retry
                Operation->>Logger: error(giving up)
                Logger->>Logger: Write error
                Operation-->>Caller: raise Exception
                deactivate Operation
            else Not final
                Operation->>Operation: wait(exponential backoff)
                Operation->>Logger: log(retrying after Ns)
                Logger->>Logger: Write retry
            end
        end
    end
```

**Backoff schedule:**
- Attempt 1: immediate
- Attempt 2: wait 1s, then retry
- Attempt 3: wait 2s, then retry
- Attempt 4: wait 4s, give up

---

## 7. Model Inference with Fallback

```mermaid
sequenceDiagram
    participant Agent
    participant Bedrock as BedrockBackend
    participant Mock as MockBackend
    
    Agent->>Bedrock: invoke(prompt, max_tokens=500)
    activate Bedrock
    
    alt Primary succeeds (fast path)
        Bedrock->>Bedrock: API call
        Bedrock-->>Agent: response
        deactivate Bedrock
    else Timeout
        Bedrock->>Bedrock: wait 60s
        Bedrock->>Agent: TimeoutError
        deactivate Bedrock
        
        Agent->>Mock: invoke(prompt)
        activate Mock
        Mock->>Mock: Generate template response
        Mock-->>Agent: mock response
        deactivate Mock
    else Auth error
        Bedrock->>Bedrock: check credentials
        Bedrock->>Agent: AuthError
        deactivate Bedrock
        
        Agent->>Mock: invoke(prompt)
        activate Mock
        Mock-->>Agent: mock response
        deactivate Mock
    else Rate limit
        Bedrock->>Agent: RateLimitError
        deactivate Bedrock
        
        Agent->>Agent: wait exponential backoff
        Agent->>Bedrock: retry
        activate Bedrock
        Bedrock-->>Agent: response
        deactivate Bedrock
    end
```

**Fallback strategy:** Mock backend always available

---

## 8. ERE Gate Verification

```mermaid
sequenceDiagram
    participant Agent
    participant EREGate
    participant Validator
    
    Agent->>EREGate: check(agent_id, intent, output)
    activate EREGate
    
    EREGate->>Validator: Validate output format
    activate Validator
    
    Validator->>Validator: Parse output XML
    Validator->>Validator: Check required tags
    Validator-->>EREGate: format_valid?
    deactivate Validator
    
    alt Format invalid
        EREGate-->>Agent: failed, seal=nil
    else Format valid
        EREGate->>Validator: Validate content
        activate Validator
        Validator->>Validator: Check coherence
        Validator->>Validator: Check safety
        Validator->>Validator: Semantic checks
        Validator-->>EREGate: passed?
        deactivate Validator
        
        alt Content invalid
            EREGate-->>Agent: failed, seal=nil
        else Content valid
            EREGate->>EREGate: Compute seal hash
            EREGate-->>Agent: passed, seal=hash
        end
    end
    deactivate EREGate
```

**Validation stages:**
1. Format (XML structure)
2. Content (semantics, safety)
3. Sealing (hash generation)

---

## Summary

**8 key sequence diagrams:**

1. **HTTP Request** — End-to-end task processing
2. **Routing Pipeline** — 11-stage internal flow
3. **Tool Approval** — User interaction for risky tools
4. **Continuity** — State checkpointing and recovery
5. **WORM Sealing** — Immutable ledger chain building
6. **Error Retry** — Exponential backoff recovery
7. **Model Fallback** — Primary → mock fallover
8. **ERE Verification** — Multi-stage result validation

All diagrams show:
- Participant interactions
- Message ordering
- Timing constraints
- Error conditions
- Fallback paths
