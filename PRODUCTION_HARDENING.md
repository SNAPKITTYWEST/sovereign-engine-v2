# PRODUCTION HARDENING PLAN — SOVEREIGN PYTHON LLM ENGINE

**Target Audience:** Codex AI assistant (code implementation agent)  
**Purpose:** Specification for hardening the Sovereign engine for production deployment  
**Scope:** 8 major sections, ~200 actionable items  
**Timeline Estimate:** 4-6 weeks at standard velocity  
**Status:** Requirement specification (pre-implementation)

---

## CRITICAL SUCCESS CRITERIA

All work must preserve or enhance these invariants:

```
✓ ACTIVE(I) ⟹ TRUSTED(I)              — No untrusted agent execution
✓ ENTROPY(I) ≤ 0.20 nats              — Determinism bound
✓ WORM append-only + tamper-detect    — No log mutation
✓ PathJail + SSRFGuard hold all I/O   — Zero filesystem/network escape
✓ ReAct max_steps enforced            — Runaway prevention
✓ Tool approval + rate limit gates    — Malicious tool calls blocked
✓ Continuity 4-paradigm restart cycle — No state loss on crash
```

---

## 1. TERMINAL ACCESS IDE

### Goal
Rich terminal UI (pure Python curses) that displays live agent execution with routing visualization, tool latency, and continuity status.

### 1.1 Core Terminal UI (`src/terminal/ui.py` — ~500 lines)

**Deliverables:**
- Split-pane layout: left = agent output, right = tool/routing activity
- Live update loop (async, non-blocking)
- Event queue from agent → UI bridge

**Function Signatures:**

```python
class TerminalUI:
    """Rich terminal interface for Sovereign engine."""
    
    def __init__(self, width: int = 200, height: int = 50):
        """Initialize curses screen and panes."""
        pass
    
    async def run(self, agent: ReActAgent) -> None:
        """Main loop: poll agent, update panes, handle input."""
        pass
    
    def render_left_pane(self, trajectory: AgentTrajectory) -> None:
        """
        Display agent thought/action/observation stream.
        
        Format per step:
          [STEP 3]
          💭 Thought: "Need to search for recent frameworks..."
          ⚙️  Action: tool_call(web_search, {"query": "LLM frameworks 2026"})
          👁️  Observation: "Found 14 results..."
          ✅ Reflection: "Progress made, continue"
        """
        pass
    
    def render_right_pane(
        self,
        routing_state: dict[str, float],
        tool_latencies: dict[str, float],
        continuity_status: dict[str, Any]
    ) -> None:
        """
        Display routing tree, tool performance, continuity flags.
        
        Sections:
          ▶ Jordan MoE Routing
            [Expert 0] weight=0.45 ████████░░
            [Expert 1] weight=0.30 ██████░░░░
            ...
          ▶ Tool Performance (last 10 calls)
            web_search    avg=42ms   max=105ms  calls=8
            db_query      avg=15ms   max=67ms   calls=3
          ▶ Continuity Status
            env_bitmask: 0x001f (seed restored)
            shared_mem: OK (4095/4096 bytes)
            worm_ledger: 127 records
        """
        pass
    
    def render_status_bar(self, current_step: int, max_steps: int) -> None:
        """Bottom status line: step count, elapsed time, agent state."""
        pass
```

**Implementation Notes:**
- Use Python `curses` (stdlib, all platforms)
- Non-blocking input via `timeout(100)` (100ms refresh)
- Queue-based communication from agent to UI (thread-safe)
- WORM ledger tail displayed as a compact scrollable log

---

### 1.2 Reusable Curses Widgets (`src/terminal/widgets.py` — ~250 lines)

**Deliverables:**
- Pane container (split layout)
- Progress bar / bar chart
- Text scroller / log viewer
- Notification banner

**Class Signatures:**

```python
class Panel:
    """Named rectangular region with border and title."""
    
    def __init__(self, x: int, y: int, width: int, height: int, title: str = ""):
        pass
    
    def write(self, x: int, y: int, text: str, color: int = 7) -> None:
        """Write text at (x, y) relative to panel origin."""
        pass
    
    def clear(self) -> None:
        """Erase all content."""
        pass
    
    def border(self, style: str = "box") -> None:
        """Draw border (box | rounded | none)."""
        pass
    
    def render(self, stdscr) -> None:
        """Write to curses screen."""
        pass


class ProgressBar:
    """Horizontal bar showing percentage (0–100)."""
    
    def __init__(self, width: int = 40, filled_char: str = "█", empty_char: str = "░"):
        pass
    
    def set_progress(self, value: float) -> None:
        """Update progress (0.0–1.0)."""
        pass
    
    def render(self) -> str:
        """Return string representation."""
        pass


class ScrollableLog:
    """Scrollable text buffer (vim-style navigation)."""
    
    def __init__(self, max_lines: int = 1000):
        pass
    
    def append(self, line: str) -> None:
        """Add line to log."""
        pass
    
    def scroll(self, offset: int) -> None:
        """Scroll by offset lines (negative = up)."""
        pass
    
    def render(self, height: int) -> list[str]:
        """Return visible lines."""
        pass
```

---

### 1.3 Vim-Style Keybindings (`src/terminal/keybinds.py` — ~150 lines)

**Deliverables:**
- Command mode (`:` prefix)
- Navigation (hjkl, Page Up/Down, gg/G)
- Pause/resume agent

**Function Signatures:**

```python
class KeybindRegistry:
    """Map terminal input to actions."""
    
    def __init__(self):
        self.bindings: dict[str, Callable] = {}
    
    def register(self, key: str, action: Callable, mode: str = "normal") -> None:
        """
        Register key binding.
        
        Args:
            key: Key code (e.g., "j", "Page_Down", "C-c")
            action: Callable to invoke
            mode: "normal" or "command"
        """
        pass
    
    def handle_input(self, ch: int, mode: str = "normal") -> tuple[str, Callable | None]:
        """
        Convert curses input to action.
        
        Returns:
            (mode, action_func) or (mode, None) if no binding
        """
        pass


# Predefined bindings:
BINDINGS = {
    "j":           scroll_down,
    "k":           scroll_up,
    "Page_Down":   scroll_page_down,
    "Page_Up":     scroll_page_up,
    "g":           scroll_top,
    "G":           scroll_bottom,
    "q":           quit,
    " ":           pause_agent,
    "r":           resume_agent,
    "C-c":         emergency_stop,
}
```

---

## 2. ACCESSIBILITY

### Goal
All output (terminal, logs, errors) must support screen readers, high-contrast mode, and dyslexia-friendly rendering. Keyboard-only navigation. No color dependency.

### 2.1 Screen Reader Support (`src/accessibility/screen_reader.py` — ~200 lines)

**Deliverables:**
- Semantic text descriptions for all UI elements
- Status change announcements
- Error message plain English

**Function Signatures:**

```python
class AccessibilityBridge:
    """Convert UI events to screen-reader-friendly text."""
    
    def __init__(self, output_file: Path | None = None):
        """
        Args:
            output_file: Optional file to log accessibility text.
                         If None, print to stdout for screen reader capture.
        """
        pass
    
    def announce(self, text: str, priority: str = "normal") -> None:
        """
        Announce text immediately.
        
        Args:
            text: Plain English description (no emoji, no color codes)
            priority: "normal" (queue) | "alert" (immediate) | "polite" (deferred)
        
        Example:
            announce("Agent entered THINKING state. Step 3 of 10.")
            announce("ERROR: Database query timeout. Retry with longer timeout.", priority="alert")
        """
        pass
    
    def format_tool_call(self, tool_name: str, args: dict[str, Any]) -> str:
        """
        Convert tool call to descriptive text.
        
        Example output:
            "Called web_search with query: 'LLM frameworks 2026', max_results: 10"
        """
        pass
    
    def format_routing_decision(self, experts: dict[str, float]) -> str:
        """
        Describe which experts were activated.
        
        Example output:
            "Routing decision: Expert0 weighted 0.45, Expert1 weighted 0.30, others suppressed"
        """
        pass
    
    def format_error(self, error: Exception, recovery: str | None = None) -> str:
        """
        Convert exception to plain English with recovery steps.
        
        Example:
            format_error(
                PathJailError("Path escapes jail"),
                recovery="Ensure file path is within /workspace"
            )
            # Output: "Error: Cannot access that file path. It is outside the allowed directory. 
            #          Solution: Ensure file path is within /workspace"
        """
        pass
```

---

### 2.2 Contrast & Dyslexia (`src/accessibility/contrast.py` — ~200 lines)

**Deliverables:**
- High-contrast color palette (WCAG AAA compatible)
- Dyslexia-friendly fonts (monospace, anti-aliased)
- No ambiguous characters (0/O, 1/l/I, 5/S confusion)

**Function Signatures:**

```python
class ContrastManager:
    """Ensure terminal colors meet accessibility standards."""
    
    def __init__(self, mode: str = "normal"):
        """
        Args:
            mode: "normal" | "high_contrast" | "dyslexia_friendly"
        """
        self.mode = mode
        self.palette = self._init_palette()
    
    def get_color_pair(self, role: str) -> tuple[int, int]:
        """
        Get foreground, background curses color indices.
        
        Roles:
            "text"           -> (fg, bg) for normal text
            "thought"        -> for agent thinking
            "action"         -> for tool calls
            "observation"    -> for tool results
            "error"          -> for errors
            "success"        -> for completed steps
            "warning"        -> for warnings
            "status_active"  -> for active components
            "status_idle"    -> for idle components
        
        Returns:
            (fg_color_code, bg_color_code) per curses
        """
        pass
    
    def sanitize_output(self, text: str) -> str:
        """
        Remove ambiguous characters, add spacing.
        
        Rules:
            - Replace 0/O ambiguity: 0 → O (context-aware) or use distinct rendering
            - Replace 1/l/I: use font distinguishing
            - Increase line spacing in output
            - Ensure monospace rendering
        """
        pass
    
    def validate_contrast(self, fg: int, bg: int) -> float:
        """
        Return contrast ratio (1–21, target ≥7 for WCAG AAA).
        
        Raises:
            AccessibilityError if ratio < 7
        """
        pass
```

---

### 2.3 Keyboard-Only Navigation

**Requirements (no implementation, validation only):**
- All UI features reachable via keyboard
- Tab order documented
- Vim keybindings supported (j/k/hjkl)
- Emergency stop (Ctrl+C) always works
- No mouse clicks required

**Test Cases:**
```python
# tests/accessibility/test_keyboard_nav.py

def test_tab_order():
    """Verify Tab cycles through all interactive elements."""
    pass

def test_vim_navigation():
    """Verify j/k/hjkl/gg/G work without vim mode enabled."""
    pass

def test_no_mouse_required():
    """Verify all features work with keyboard only."""
    pass
```

---

## 3. EDGE CASES & ERROR HANDLING

### Goal
Gracefully handle all failure modes: disk full, corrupt files, path traversal attempts, DNS rebinding, hung tools, queue overflow, model timeouts, C frontend crash.

### 3.1 PathJail Extensions (`src/core/path_jail.py` — extend by ~100 lines)

**Add Functions:**

```python
def detect_junction(path: Path) -> bool:
    """
    Detect Windows NTFS junction points (directory symlinks).
    
    On Windows, junctions are not symlinks but still can escape jail.
    Use Windows API reparse point detection.
    
    Returns:
        True if path is a junction, False otherwise
    """
    pass

def safe_open_nofollow(path: Path, mode: str = 'r') -> io.IOBase:
    """
    Open file with O_NOFOLLOW equivalent (no symlink dereference).
    
    On POSIX: Use os.open with os.O_NOFOLLOW
    On Windows: Check is_symlink() before opening
    
    Raises:
        PathJailError if file is a symlink
    """
    pass

def prevent_toctou_race(path: Path, operation: Callable) -> Any:
    """
    Execute operation on path with TOCTOU race prevention.
    
    Pattern: Stat → resolve → stat-again → assert unchanged → execute
    
    Args:
        path: Path to operate on
        operation: Callable(path) to execute
    
    Returns:
        Result of operation
    
    Raises:
        PathJailError if file changed between checks
    """
    pass
```

**Add to PathJail class:**

```python
def set_max_file_size(self, max_bytes: int) -> None:
    """
    Enforce max read size per operation.
    
    Args:
        max_bytes: Maximum bytes to read (e.g., 1GB)
    
    Prevents: DoS by huge file read
    """
    self.max_file_size = max_bytes

def read_safe(self, path: str | Path, max_size: int | None = None) -> bytes:
    """
    Read file with size enforcement.
    
    Checks available space before read.
    
    Raises:
        PathJailError if file exceeds max_size
    """
    pass
```

---

### 3.2 SSRFGuard Extensions (`src/core/path_jail.py` — extend SSRFGuard by ~80 lines)

**Add Method:**

```python
class SSRFGuard:
    """Prevent Server-Side Request Forgery."""
    
    async def resolve_and_check(self, hostname: str, port: int = 443) -> str:
        """
        DNS rebinding prevention: resolve hostname, check IP, then connect.
        
        Algorithm:
          1. Resolve hostname to IP
          2. Check IP against blocklist (private ranges, metadata, etc)
          3. If OK, return IP
          4. Return IP (not hostname) to caller for actual connection
          5. On connect, verify IP matches resolved value
        
        Args:
            hostname: Domain name
            port: Port (only used for validation, not connection)
        
        Returns:
            Verified IP address
        
        Raises:
            SSRFError if IP is blocked or doesn't resolve
        
        Prevents:
          - DNS rebinding: resolve → check → rebind → connect-to-different-IP
          - Time-of-check-time-of-use: re-resolve before connect
        """
        pass
    
    def add_blocked_ip(self, ip: str) -> None:
        """Dynamically add blocked IP."""
        pass
    
    def is_blocked(self, ip: str) -> bool:
        """Check if IP is in blocklist."""
        pass
```

---

### 3.3 Storage: Disk Full Handling (`src/core/storage.py` — extend by ~60 lines)

**Add Functions:**

```python
def check_disk_space_before_write(
    file_path: Path,
    estimated_size: int
) -> bool:
    """
    Pre-check available disk space.
    
    Args:
        file_path: Target file path
        estimated_size: Bytes to write
    
    Returns:
        True if space available, False if full
    
    Raises:
        OSError if path invalid
    """
    pass

def write_with_space_check(
    file_path: Path,
    data: bytes,
    min_free_space: int = 1_000_000  # 1MB minimum free
) -> None:
    """
    Write to file, abort if disk nearly full.
    
    Raises:
        IOError if insufficient space
    """
    pass

# Update WORMFile class:
class WORMFile:
    def append_safe(self, record: WORMRecord) -> None:
        """
        Append record with disk-full protection.
        
        - Check space before write
        - Write atomically (temp file + rename)
        - On failure, truncate corrupt tail (not head)
        """
        pass
```

---

### 3.4 Continuity: Shared Memory Cleanup (`src/continuity/shared_mem.py` — extend by ~100 lines)

**Add Functions:**

```python
def cleanup_stale_shm_segments(max_age_seconds: int = 3600) -> int:
    """
    Clean up shared memory segments from dead processes.
    
    Algorithm:
      1. List all /dev/shm/* or Windows shared memory
      2. Check mtime (modification time)
      3. If older than max_age_seconds AND no process holding it, delete
      4. Log deletion
    
    Args:
        max_age_seconds: Time threshold (default 1 hour)
    
    Returns:
        Number of segments cleaned
    
    Raises:
        OSError if cannot read /dev/shm
    """
    pass

def detect_orphaned_shm(agent_id: str) -> bool:
    """
    Detect if agent has orphaned shared memory from crash.
    
    Returns:
        True if orphaned SHM found, False if clean or in use
    """
    pass

# Update SharedMemory class:
class SharedMemory:
    def __init__(self, agent_id: str, size: int = 4096):
        """
        Initialize shared memory with crash-recovery.
        
        - Detect orphaned segment from prior crash
        - Zero-out if corrupted
        - Initialize checksum
        """
        pass
    
    def validate_checksum(self) -> bool:
        """
        Verify ring buffer header checksum.
        
        Returns:
            True if checksum valid, False if corrupted
        """
        pass
    
    def recover_from_corruption(self) -> None:
        """
        Reset SHM to safe state if checksum fails.
        
        Logs recovery action.
        """
        pass
```

---

### 3.5 IPC: Mmap Corruption Detection (`src/tools/ipc_router.py` — extend by ~80 lines)

**Add Functions:**

```python
def validate_ring_buffer_header(mmap_obj: mmap.mmap) -> tuple[bool, str]:
    """
    Verify ring buffer header integrity.
    
    Returns:
        (is_valid, error_message)
    
    Checks:
      - Magic bytes at offset 0
      - Version byte at offset 4
      - CRC32 at offset 8
      - Write pointer in valid range
      - Read pointer in valid range
    """
    pass

def repair_corrupted_ring_buffer(mmap_obj: mmap.mmap) -> None:
    """
    Reset ring buffer to safe state.
    
    - Zero-out entire header
    - Reset pointers to 0
    - Recalculate checksum
    - Log repair event
    """
    pass

# Update IPCRouter class:
class IPCRouter:
    async def dispatch_with_corruption_check(self, opcode: int, payload: bytes) -> Any:
        """
        Dispatch opcode, detecting and recovering from mmap corruption.
        
        Raises:
            IPCCorruptionError if corruption detected and unrecoverable
        """
        pass
```

---

### 3.6 Routing: All-Experts-Masked Fallback (`src/routing/jordan_moe.py` — extend by ~40 lines)

**Add Method:**

```python
class JordanMoERouter:
    def route_with_fallback(self, signal: dict[str, float]) -> dict[str, float]:
        """
        Route signal to experts, with fallback if all masked.
        
        Algorithm:
          1. Compute routing normally
          2. If all weights = 0 (all masked):
             a. Log warning
             b. Fall back to uniform random distribution
             c. OR use prior distribution (if available)
             d. Return fallback weights
        
        Returns:
            Expert → weight mapping (always sums to 1.0)
        """
        pass
    
    def get_current_masks(self) -> dict[str, bool]:
        """Return which experts are currently masked."""
        pass
    
    def set_emergency_fallback_mode(self, enabled: bool) -> None:
        """
        Enable/disable emergency fallback routing.
        
        When enabled and all experts masked, use uniform random.
        When disabled, raise RoutingError.
        """
        pass
```

---

### 3.7 Agent: Model Timeout & Backoff (`src/agents/react.py` — extend by ~100 lines)

**Add to ReActAgent:**

```python
class ReActAgent:
    def __init__(self, ..., timeout_config: TimeoutConfig | None = None):
        """
        Args:
            timeout_config: Timeout and retry strategy
        """
        self.timeout_config = timeout_config or TimeoutConfig()
    
    async def call_model_with_retry(
        self,
        prompt: str,
        max_retries: int = 3
    ) -> str:
        """
        Call LLM with exponential backoff on timeout/rate-limit.
        
        Algorithm:
          - Attempt 1: 30s timeout
          - Attempt 2: 60s timeout, wait 2s before retry
          - Attempt 3: 90s timeout, wait 4s before retry
          - Raise ModelTimeoutError if all attempts fail
        
        Detects:
          - Timeout (socket/asyncio timeout)
          - Rate limit (429 HTTP status)
          - Server error (500–599 HTTP)
        
        Args:
            prompt: Input to model
            max_retries: Max attempts
        
        Returns:
            Model output
        
        Raises:
            ModelTimeoutError
            ModelRateLimitError
        """
        pass
```

**Add TimeoutConfig dataclass:**

```python
@dataclass
class TimeoutConfig:
    initial_timeout_sec: float = 30
    max_timeout_sec: float = 120
    backoff_multiplier: float = 2.0
    initial_retry_delay_sec: float = 2
    max_retry_delay_sec: float = 60
    jitter_enabled: bool = True  # Add random noise to prevent thundering herd
```

---

### 3.8 Shadow: Queue Overflow (`src/agents/shadow.py` — extend by ~60 lines)

**Add to ShadowAgent:**

```python
class ShadowAgent:
    def __init__(self, ..., max_queue_size: int = 10000):
        """
        Args:
            max_queue_size: Max observations in queue before dropping
        """
        self.max_queue_size = max_queue_size
        self.queue_depth_warn_threshold = 0.8 * max_queue_size
    
    async def append_observation(self, obs: str) -> None:
        """
        Append observation, dropping oldest if queue full.
        
        - If queue at 80% capacity, log warning
        - If queue at 100% capacity, drop oldest, log error
        - Track drop count for metrics
        """
        pass
    
    def get_queue_stats(self) -> dict[str, int]:
        """
        Return queue stats.
        
        Returns:
            {
                "size": current_size,
                "max": max_size,
                "dropped": total_dropped,
                "utilization_percent": 100 * size / max
            }
        """
        pass
```

---

### 3.9 Tools: Per-Tool Timeout (`src/tools/registry.py` — extend by ~50 lines)

**Add to ToolDefinition:**

```python
@dataclass
class ToolDefinition:
    # ... existing fields ...
    
    timeout_sec: float = 60  # Default 60s per tool call
    max_retries: int = 1
    retry_backoff_sec: float = 2.0
```

**Add function:**

```python
async def call_tool_with_timeout(
    tool: ToolDefinition,
    args: dict[str, Any],
    logger: logging.Logger
) -> Any:
    """
    Call tool with per-tool timeout enforcement.
    
    - Set asyncio timeout to tool.timeout_sec
    - If timeout, cancel task and log
    - Raise ToolTimeoutError
    
    Raises:
        ToolTimeoutError
        asyncio.TimeoutError (caught and converted)
    """
    pass
```

---

### 3.10 Bridge: C Frontend Heartbeat (`src/bridge/http_server.py` — extend by ~80 lines)

**Add heartbeat mechanism:**

```python
class HTTPBridge:
    def __init__(self, ..., heartbeat_interval_sec: float = 5.0):
        """
        Args:
            heartbeat_interval_sec: Interval to send heartbeats to C frontend
        """
        self.heartbeat_interval = heartbeat_interval_sec
        self.last_frontend_ping: float | None = None
    
    async def heartbeat_monitor(self) -> None:
        """
        Periodically send heartbeat to frontend.
        
        - Send HTTP GET /health every heartbeat_interval seconds
        - If no response for 3x interval, assume frontend dead
        - Clean up resources (close WebSocket, free memory)
        - Log frontend crash
        """
        pass
    
    async def handle_frontend_disconnect(self) -> None:
        """
        Called when frontend heartbeat fails.
        
        - Cancel any in-progress requests
        - Save agent state (WORM checkpoint)
        - Release mmap/IPC resources
        - Log event
        """
        pass
    
    @property
    def frontend_alive(self) -> bool:
        """True if frontend responded to recent heartbeat."""
        pass
```

---

## 4. SECURITY HARDENING

### Goal
Extend PathJail/SSRFGuard, add rate limiting, cost tracking, emergency kill switch, validate inputs, prevent regex DoS.

### 4.1 PathJail & SSRFGuard (See Section 3.1–3.2)

---

### 4.2 Rate Limiting (`src/tools/approval.py` — extend by ~150 lines)

**Add class:**

```python
@dataclass
class RateLimitPolicy:
    """Per-tool rate limiting configuration."""
    tool_name: str
    max_calls_per_minute: int
    max_calls_per_hour: int
    burst_allowed: int = 5  # Allow burst up to 5 calls
    
@dataclass
class RateLimitViolation:
    """Result of rate limit check."""
    violated: bool
    calls_made: int
    calls_remaining: int
    reset_time_sec: float


class RateLimiter:
    """Token bucket rate limiter per tool."""
    
    def __init__(self, policy: RateLimitPolicy):
        pass
    
    def check_rate_limit(self) -> RateLimitViolation:
        """
        Check if tool call allowed.
        
        Uses token bucket algorithm:
          - Bucket has capacity = max_calls_per_minute
          - Tokens regenerate at rate = capacity / 60 per second
          - Each call consumes 1 token
          - Burst = allow 5 calls above steady-state
        
        Returns:
            RateLimitViolation with status
        """
        pass
    
    def get_stats(self) -> dict[str, int]:
        """Return current rate limit stats."""
        pass


# Update ApprovalEngine:
class ApprovalEngine:
    def __init__(self, ..., rate_limit_policies: dict[str, RateLimitPolicy] | None = None):
        """
        Args:
            rate_limit_policies: Tool name → RateLimitPolicy mapping
        """
        self.rate_limiters = {
            name: RateLimiter(policy)
            for name, policy in (rate_limit_policies or {}).items()
        }
    
    async def check_rate_limit(self, tool_name: str) -> RateLimitViolation:
        """Check if tool call violates rate limit."""
        if tool_name not in self.rate_limiters:
            return RateLimitViolation(violated=False, ...)
        return self.rate_limiters[tool_name].check_rate_limit()
    
    async def check_approval(self, ...) -> ApprovalResult:
        """Extended to also check rate limit."""
        # Check rate limit first
        rate_check = await self.check_rate_limit(tool.name)
        if rate_check.violated:
            return ApprovalResult(
                approved=False,
                reason=f"Rate limit exceeded: {rate_check.calls_remaining} calls remaining",
                ...
            )
        # Then check existing approval logic
        pass
```

---

### 4.3 Cost Tracking (`src/tools/approval.py` — extend by ~120 lines)

**Add class:**

```python
@dataclass
class ToolCost:
    """Cost of a single tool call."""
    tool_name: str
    cost_usd: float
    timestamp: str
    actor: str
    duration_sec: float
    tokens_used: int | None = None  # For LLM calls


class CostTracker:
    """Track cumulative cost of tool calls."""
    
    def __init__(self, ledger: WORMLedger):
        self.ledger = ledger
    
    def log_cost(self, cost: ToolCost) -> None:
        """
        Log tool call cost to WORM.
        
        Records:
          - tool_name
          - cost_usd (e.g., 0.0012)
          - duration
          - tokens (if applicable)
          - timestamp
        """
        pass
    
    async def get_total_cost(self, actor: str | None = None, since: datetime | None = None) -> float:
        """
        Compute total cost incurred.
        
        Args:
            actor: Filter by actor (None = all)
            since: Filter by time (None = all time)
        
        Returns:
            Total cost in USD
        """
        pass
    
    async def get_cost_by_tool(self) -> dict[str, float]:
        """Break down cost by tool."""
        pass
    
    def set_monthly_budget_usd(self, budget: float) -> None:
        """Set max monthly spending."""
        pass
    
    async def check_budget(self, actor: str) -> tuple[bool, str]:
        """
        Check if remaining budget allows next tool call.
        
        Returns:
            (budget_ok, reason)
        """
        pass


# Update ApprovalEngine:
class ApprovalEngine:
    def __init__(self, ..., cost_tracker: CostTracker | None = None):
        self.cost_tracker = cost_tracker
    
    async def check_approval(self, tool: ToolDefinition, ...) -> ApprovalResult:
        """Extended to check cost budget."""
        if self.cost_tracker:
            budget_ok, reason = await self.cost_tracker.check_budget(actor)
            if not budget_ok:
                return ApprovalResult(approved=False, reason=reason, ...)
        # Continue with existing checks
        pass
```

---

### 4.4 Emergency Kill Switch (`src/tools/supervisor.py` — extend by ~80 lines)

**Add class:**

```python
class EmergencyKillSwitch:
    """
    Emergency stop: disable all tools immediately.
    """
    
    def __init__(self, approval_engine: ApprovalEngine):
        self.approval_engine = approval_engine
        self._kill_switch_engaged = False
    
    def engage(self, reason: str, actor: str) -> None:
        """
        Engage kill switch: disable all tool execution.
        
        Args:
            reason: Why kill switch engaged (logged)
            actor: Who engaged it (logged)
        
        Effect:
          - All subsequent tool calls return ApprovalResult(approved=False)
          - WORM record created
          - Alert sent to admin
        """
        pass
    
    def disengage(self, reason: str, actor: str) -> None:
        """Disable kill switch (requires auth)."""
        pass
    
    def is_engaged(self) -> bool:
        """Check current state."""
        pass
    
    def force_stop_all_agents(self) -> int:
        """
        Stop all running agents immediately.
        
        Returns:
            Number of agents stopped
        """
        pass


# Add to main engine init:
def __init__(self, ...):
    self.kill_switch = EmergencyKillSwitch(self.approval_engine)
```

---

### 4.5 Input Validation (`src/core/types.py` — new file, ~150 lines)

**Add validators:**

```python
class InputValidator:
    """Validate all untrusted input."""
    
    MAX_MESSAGE_LENGTH = 100_000  # 100KB
    MAX_QUERY_LENGTH = 10_000     # 10KB
    REGEX_TIMEOUT_MS = 100
    
    @staticmethod
    def validate_message_length(msg: str) -> None:
        """Enforce max message length."""
        if len(msg) > InputValidator.MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message exceeds max length: {len(msg)} > {InputValidator.MAX_MESSAGE_LENGTH}"
            )
    
    @staticmethod
    def validate_unicode_normalization(text: str) -> str:
        """
        Normalize Unicode to prevent homograph attacks.
        
        - Decompose combining characters
        - Detect confusable scripts (Latin + Cyrillic)
        - Raise error if mixing detected
        
        Returns:
            Normalized text
        """
        import unicodedata
        nfc = unicodedata.normalize('NFC', text)
        # TODO: Homograph detection
        return nfc
    
    @staticmethod
    def validate_regex_safe(pattern: str) -> bool:
        """
        Check regex for potential DoS (catastrophic backtracking).
        
        Algorithm:
          - Use timeout-based check: compile pattern with timeout
          - Test against sample inputs
          - Raise error if timeout
        
        Or: Require patterns to match RE2 spec (no backtracking).
        
        Returns:
            True if safe
        
        Raises:
            RegexDoSError if pattern dangerous
        """
        pass
    
    @staticmethod
    def validate_json_safe(json_str: str) -> Any:
        """
        Parse JSON with size limits.
        
        - Enforce max nesting depth (10)
        - Enforce max string length (1MB)
        - Reject duplicate keys (potential collision attack)
        """
        pass
    
    @staticmethod
    def sanitize_sql_parameter(param: str) -> str:
        """
        Sanitize SQL parameter (for parameterized queries).
        
        Note: Should use parameterized queries, not escaping!
        This is fallback only.
        """
        pass
```

---

### 4.6 Crypto Verification (`src/core/crypto.py` — extend by ~100 lines)

**Verify existing functionality and extend:**

```python
class CryptoManager:
    """Manage cryptographic keys and operations."""
    
    def __init__(self, master_secret: bytes | None = None):
        """
        Args:
            master_secret: 32-byte master secret (or load from secure store)
        """
        self.master_secret = master_secret
    
    def derive_key(self, context: str, length: int = 32) -> bytes:
        """
        Derive key from master secret using HKDF.
        
        Args:
            context: String context (e.g., "worm_signing", "aes_encryption")
            length: Byte length of derived key
        
        Returns:
            Derived key
        
        Algorithm:
            HKDF-SHA256(master_secret, context.encode(), length)
        """
        pass
    
    def rotate_key(self, old_key_id: str) -> str:
        """
        Rotate signing key: generate new key, mark old as retired.
        
        Args:
            old_key_id: ID of key to retire
        
        Returns:
            ID of new key
        
        Records rotation in WORM for audit trail.
        """
        pass
    
    def verify_signature_on_read(self, data: bytes, signature: bytes, key_id: str) -> bool:
        """
        Verify Ed25519 signature on data read from storage.
        
        Args:
            data: Data to verify
            signature: Signature bytes
            key_id: ID of key to use for verification
        
        Returns:
            True if signature valid
        
        Raises:
            CryptoError if key_id not found
        """
        pass
    
    def get_key_metadata(self, key_id: str) -> dict[str, Any]:
        """Get metadata about a key (created_at, retired_at, etc)."""
        pass
```

---

## 5. TESTING

### Goal
Comprehensive pytest suite (~2000 lines) covering unit, integration, and property-based tests.

### 5.1 Unit Tests

#### `tests/test_routing.py` (~400 lines)

```python
"""Test Jordan algebra MoE routing properties."""

import pytest
from src.routing.jordan_moe import SpinFactor, JordanMoERouter

class TestSpinFactorAlgebra:
    """Verify Jordan algebra axioms."""
    
    def test_commutativity(self):
        """A ∘ B = B ∘ A"""
        a = SpinFactor(2.0, [1.0, 0.0])
        b = SpinFactor(3.0, [0.0, 1.0])
        assert a.compose(b) == b.compose(a)
    
    def test_non_associativity(self):
        """(A ∘ B) ∘ C ≠ A ∘ (B ∘ C) in general"""
        a = SpinFactor(1.0, [1.0, 0.0])
        b = SpinFactor(1.0, [0.0, 1.0])
        c = SpinFactor(1.0, [1.0, 1.0])
        
        left = a.compose(b).compose(c)
        right = a.compose(b.compose(c))
        # Should differ (non-associative)
        assert left != right
    
    def test_idempotent_convergence(self):
        """x ∘ x ∘ x... converges to idempotent e where e ∘ e = e"""
        x = SpinFactor(0.5, [0.2, 0.3])
        
        for _ in range(100):
            x_new = x.compose(x)
            # Eventually x ≈ e and e ∘ e ≈ e
            if abs(x_new.scalar - x.scalar) < 1e-6:
                # Converged, verify idempotency
                e_squared = x_new.compose(x_new)
                assert abs(e_squared.scalar - x_new.scalar) < 1e-6
                break
            x = x_new
```

#### `tests/test_storage.py` (~300 lines)

```python
"""Test WORM append-only and tamper detection."""

import pytest
from src.core.storage import WORMFile, WORMRecord
from pathlib import Path

class TestWORMAppendOnly:
    """WORM records cannot be modified."""
    
    def test_append_writes_record(self, tmp_path):
        """Appending writes record correctly."""
        worm = WORMFile(tmp_path / "test.worm")
        rec = WORMRecord(event_type="test", payload=b"hello")
        
        worm.append(rec)
        
        records = list(worm.read())
        assert len(records) == 1
        assert records[0].payload == b"hello"
    
    def test_chain_verification(self, tmp_path):
        """Each record hashes the previous."""
        worm = WORMFile(tmp_path / "test.worm")
        rec1 = WORMRecord(event_type="evt1", payload=b"data1")
        rec2 = WORMRecord(event_type="evt2", payload=b"data2")
        
        worm.append(rec1)
        worm.append(rec2)
        
        records = list(worm.read())
        # rec2.prev_hash should match rec1's content hash
        assert records[1].prev_hash == records[0].content_hash
    
    def test_tamper_detection(self, tmp_path):
        """Corrupt file fails verification."""
        worm = WORMFile(tmp_path / "test.worm")
        rec = WORMRecord(event_type="test", payload=b"data")
        worm.append(rec)
        
        # Corrupt payload byte
        with open(worm.path, 'r+b') as f:
            f.seek(152 + 10)  # Skip header
            f.write(b'X')
        
        # Reading should detect corruption
        with pytest.raises(Exception):  # WORM corruption error
            list(worm.read())
```

#### `tests/test_continuity.py` (~250 lines)

```python
"""Test 4-paradigm state save/restore/restart."""

import pytest
import os
from src.continuity.manager import ContinuityManager

class TestContinuityRestart:
    """Agent state survives restart."""
    
    def test_env_state_preserved(self, tmp_path, monkeypatch):
        """Environment bitmask restored on hot restart."""
        base_dir = tmp_path / "continuity"
        
        # First session
        mgr1 = ContinuityManager(base_dir=base_dir, agent_id="agent1")
        mgr1.set_env_bitmask(0x001f)
        mgr1.checkpoint()
        
        # Simulate restart
        monkeypatch.delenv("SOVEREIGN_STEP", raising=False)
        
        # Second session
        mgr2 = ContinuityManager(base_dir=base_dir, agent_id="agent1")
        assert mgr2.was_restarted
        assert mgr2.get_env_bitmask() == 0x001f
    
    def test_seed_chain_deterministic_replay(self, tmp_path):
        """Seed-derived randomness is deterministic."""
        base_dir = tmp_path / "continuity"
        
        # Session 1: record sequence
        mgr1 = ContinuityManager(base_dir=base_dir, agent_id="agent1")
        mgr1.set_seed_chain(b'test_seed')
        values1 = [mgr1.derive_random() for _ in range(5)]
        
        # Session 2: replay
        mgr2 = ContinuityManager(base_dir=base_dir, agent_id="agent1")
        mgr2.set_seed_chain(b'test_seed')
        values2 = [mgr2.derive_random() for _ in range(5)]
        
        assert values1 == values2
```

#### `tests/test_path_jail.py` (~250 lines)

```python
"""Test PathJail directory traversal prevention."""

import pytest
from src.core.path_jail import PathJail, PathJailError

class TestPathJail:
    """Verify all escapes blocked."""
    
    def test_relative_traversal_blocked(self, tmp_path):
        """../.. escapes rejected."""
        jail = PathJail([tmp_path])
        
        with pytest.raises(PathJailError, match="escapes jail"):
            jail.resolve(tmp_path / "subdir" / ".." / ".." / "etc" / "passwd")
    
    def test_symlink_escape_blocked(self, tmp_path):
        """Symlink outside root rejected."""
        jail = PathJail([tmp_path])
        (tmp_path / "etc").mkdir()
        (tmp_path / "workspace").mkdir()
        
        # Create symlink inside jail pointing outside
        import os
        os.symlink("/etc/passwd", tmp_path / "workspace" / "link")
        
        with pytest.raises(PathJailError, match="escapes jail"):
            jail.resolve(tmp_path / "workspace" / "link")
    
    def test_null_byte_injection_blocked(self, tmp_path):
        """Null byte in path rejected."""
        jail = PathJail([tmp_path])
        
        with pytest.raises(PathJailError, match="Null byte"):
            jail.resolve(str(tmp_path) + "\x00/etc/passwd")
    
    def test_safe_path_allowed(self, tmp_path):
        """Valid path inside root allowed."""
        jail = PathJail([tmp_path])
        (tmp_path / "safe.txt").touch()
        
        result = jail.resolve(tmp_path / "safe.txt")
        assert result.exists()
```

#### `tests/test_ipc.py` (~200 lines)

```python
"""Test IPC ring buffer and opcode dispatch."""

import pytest
from src.tools.ipc_router import IPCRouter

class TestIPCDispatch:
    """Verify opcode routing and concurrency."""
    
    async def test_opcode_dispatch(self):
        """Opcode routes to correct handler."""
        router = IPCRouter()
        handler_called = False
        
        async def mock_handler(payload):
            nonlocal handler_called
            handler_called = True
            return b"result"
        
        router.register_opcode(0x10, mock_handler)
        result = await router.dispatch(0x10, b"test")
        
        assert handler_called
        assert result == b"result"
    
    def test_ring_buffer_overflow(self):
        """Ring buffer wraps at boundary."""
        router = IPCRouter()
        # Write beyond buffer size
        # Verify wrap-around works correctly
        pass
    
    async def test_concurrent_dispatch(self):
        """Multiple concurrent dispatch calls work."""
        import asyncio
        router = IPCRouter()
        
        async def handler(payload):
            await asyncio.sleep(0.01)
            return payload
        
        router.register_opcode(0x20, handler)
        
        # Launch 10 concurrent calls
        tasks = [router.dispatch(0x20, f"msg{i}".encode()) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
```

#### `tests/test_agent.py` (~200 lines)

```python
"""Test ReAct agent loop and continuity."""

import pytest
from src.agents.react import ReActAgent, ReActConfig

class TestReActLoop:
    """Verify agent reasoning loop."""
    
    async def test_thought_action_observation_cycle(self, mock_model, mock_tool_registry):
        """Agent loops through thought → action → observation."""
        agent = ReActAgent(mock_model, mock_tool_registry)
        trajectory = await agent.run(task="test task")
        
        assert len(trajectory.steps) > 0
        assert any(step.action_type == "tool_call" for step in trajectory.steps)
    
    async def test_max_steps_enforced(self, mock_model, mock_tool_registry):
        """Agent stops at max_steps."""
        config = ReActConfig(max_steps=3)
        agent = ReActAgent(mock_model, mock_tool_registry, config=config)
        
        trajectory = await agent.run(task="test task")
        
        assert len(trajectory.steps) <= 3
    
    async def test_error_reflection(self, mock_model, mock_tool_registry):
        """Agent reflects on errors."""
        # Configure mock to return error on first tool call
        mock_tool_registry.get_tool("test").side_effect = Exception("Tool error")
        
        config = ReActConfig(reflection_on_error=True)
        agent = ReActAgent(mock_model, mock_tool_registry, config=config)
        
        trajectory = await agent.run(task="test")
        
        # Should include reflection step after error
        assert any("reflection" in str(step).lower() for step in trajectory.steps)
```

### 5.2 Integration Tests

#### `tests/integration/test_full_pipeline.py` (~250 lines)

```python
"""End-to-end task execution."""

import pytest

class TestFullPipeline:
    """Task → agent → tools → result."""
    
    async def test_simple_task_execution(self, engine_fixture):
        """Execute simple task end-to-end."""
        task = "Search for 'LLM frameworks' and summarize top 3 results"
        
        result = await engine_fixture.run_task(task)
        
        assert result is not None
        assert "framework" in result.lower() or "llm" in result.lower()
    
    async def test_tool_chain_execution(self, engine_fixture):
        """Execute multi-tool task."""
        task = "Download paper from arXiv, summarize key findings"
        
        result = await engine_fixture.run_task(task)
        
        # Verify multiple tools were used
        assert engine_fixture.tool_call_count > 1
    
    async def test_failure_recovery(self, engine_fixture):
        """Agent handles tool failure gracefully."""
        # Simulate tool failure
        engine_fixture.tools["web_search"].fail_next_call()
        
        task = "Search for something"
        result = await engine_fixture.run_task(task)
        
        # Should succeed despite failure (agent reflects and recovers)
        assert result is not None
```

#### `tests/integration/test_bridge.py` (~200 lines)

```python
"""Test HTTP bridge request/response cycle."""

import pytest
from src.bridge.http_server import HTTPBridge

class TestHTTPBridge:
    """Bridge between C frontend and Python engine."""
    
    async def test_request_response_cycle(self, bridge_fixture):
        """Send request, receive response."""
        request = {
            "method": "run_task",
            "params": {"task": "test"}
        }
        
        response = await bridge_fixture.send(request)
        
        assert "result" in response or "error" in response
    
    async def test_heartbeat_keeps_bridge_alive(self, bridge_fixture):
        """Heartbeat prevents timeout."""
        # Simulate frontend not sending requests
        import asyncio
        await asyncio.sleep(10)
        
        # Bridge should still be alive
        assert bridge_fixture.is_alive()
    
    async def test_frontend_crash_cleanup(self, bridge_fixture):
        """Frontend crash triggers cleanup."""
        # Simulate frontend crash
        bridge_fixture.frontend_connection.close()
        
        # Wait for heartbeat to detect
        await asyncio.sleep(bridge_fixture.heartbeat_interval * 3)
        
        # Cleanup should have occurred
        assert bridge_fixture.agent_state_saved()
```

### 5.3 Property-Based Tests (Hypothesis)

#### `tests/property/test_jordan.py` (~150 lines)

```python
"""Property-based testing of Jordan algebra."""

from hypothesis import given, strategies as st
import pytest

class TestJordanProperties:
    """Verify Jordan axioms hold for random inputs."""
    
    @given(
        scalar1=st.floats(min_value=-1e6, max_value=1e6),
        vector1=st.lists(st.floats(min_value=-100, max_value=100), min_size=3, max_size=3),
        scalar2=st.floats(min_value=-1e6, max_value=1e6),
        vector2=st.lists(st.floats(min_value=-100, max_value=100), min_size=3, max_size=3),
    )
    def test_commutativity_holds(self, scalar1, vector1, scalar2, vector2):
        """A ∘ B = B ∘ A for all A, B"""
        from src.routing.jordan_moe import SpinFactor
        
        a = SpinFactor(scalar1, vector1)
        b = SpinFactor(scalar2, vector2)
        
        assert a.compose(b) == b.compose(a)
    
    @given(
        scalars=st.lists(st.floats(min_value=-10, max_value=10), min_size=3, max_size=5)
    )
    def test_convergence_to_idempotent(self, scalars):
        """Repeated squaring converges to idempotent."""
        # TODO: Implement
        pass
```

#### `tests/property/test_worm.py` (~150 lines)

```python
"""Property-based testing of WORM append-only."""

from hypothesis import given, strategies as st

class TestWORMInvariants:
    """WORM append-only invariant never violated."""
    
    @given(
        payloads=st.lists(st.binary(min_size=1, max_size=1000), min_size=1, max_size=100)
    )
    def test_append_only_never_loses_data(self, payloads, tmp_path):
        """Every appended record remains readable."""
        from src.core.storage import WORMFile, WORMRecord
        
        worm = WORMFile(tmp_path / "test.worm")
        
        for i, payload in enumerate(payloads):
            rec = WORMRecord(event_type=f"event_{i}", payload=payload)
            worm.append(rec)
        
        # Read all and verify
        records = list(worm.read())
        
        assert len(records) == len(payloads)
        for i, rec in enumerate(records):
            assert rec.payload == payloads[i]
```

---

## 6. PERFORMANCE OPTIMIZATION

### Goal
Profile hot paths, optimize to targets, lazy-load modules, cache results, use memory-mapping for large files.

### 6.1 Routing Latency (`src/routing/jordan_moe.py` — profile + optimize)

**Target:** <10ms for 8 experts

```python
# Add to JordanMoERouter:

def profile_routing_latency(self, iterations: int = 1000) -> dict[str, float]:
    """
    Profile routing latency.
    
    Returns:
        {
            "mean_ms": average latency,
            "p50_ms": 50th percentile,
            "p99_ms": 99th percentile,
            "max_ms": maximum,
        }
    """
    pass

# Optimization: Cache fixed-point results
class JordanMoERouterCached:
    def __init__(self):
        self.cache = {}  # signal_hash -> weights
    
    def route_cached(self, signal: dict[str, float]) -> dict[str, float]:
        """Route with memoization."""
        signal_hash = hash(frozenset(signal.items()))
        
        if signal_hash in self.cache:
            return self.cache[signal_hash]
        
        result = self.route(signal)
        self.cache[signal_hash] = result
        return result
```

---

### 6.2 IPC Round-Trip (`src/tools/ipc_router.py` — profile + optimize)

**Target:** <100μs mmap, <1ms HTTP fallback

```python
async def profile_ipc_latency(router: IPCRouter) -> dict[str, float]:
    """
    Profile IPC round-trip latency.
    
    Returns:
        {
            "mmap_mean_us": microseconds,
            "mmap_p99_us": 99th percentile,
            "http_mean_ms": milliseconds,
        }
    """
    pass
```

---

### 6.3 Connection Pooling (`src/runtime/providers/*.py`)

**Add to all providers:**

```python
class ModelProvider:
    def __init__(self, pool_size: int = 10):
        self.pool = asyncio.Queue(maxsize=pool_size)
        # Pre-populate with connections
        for _ in range(pool_size):
            self.pool.put_nowait(self._create_connection())
    
    async def get_connection(self):
        """Get connection from pool."""
        return await self.pool.get()
    
    async def release_connection(self, conn):
        """Return connection to pool."""
        await self.pool.put(conn)
```

---

### 6.4 Lazy Module Loading (`src/tools/loader.py` — new/extend)

```python
class ToolLoader:
    """Lazy-load tools on demand."""
    
    def __init__(self):
        self.loaded_tools = {}  # tool_name -> module
        self.loading_lock = asyncio.Lock()
    
    async def load_tool(self, tool_name: str):
        """Load tool module on first use."""
        async with self.loading_lock:
            if tool_name in self.loaded_tools:
                return self.loaded_tools[tool_name]
            
            module = __import__(f"src.tools.{tool_name}")
            self.loaded_tools[tool_name] = module
            return module
```

---

### 6.5 Binary IR Memory-Mapping (`src/runtime/machine/binary_ir.py` — extend)

```python
class BinaryIRExecutor:
    def execute_large_file_with_mmap(self, file_path: Path) -> Any:
        """
        Load large binary files via mmap instead of full read.
        
        Benefit: O(1) memory regardless of file size.
        """
        import mmap
        
        with open(file_path, 'rb') as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                # Execute against mmap view
                return self.execute_ir(mm)
```

---

## 7. DOCUMENTATION

### Goal
Complete docstrings, architecture diagrams, API reference, deployment guide, configuration reference.

### 7.1 Docstring Convention

**All public methods must include:**

```python
def my_function(param1: str, param2: int) -> dict[str, Any]:
    """
    One-line summary of what this does.
    
    Longer description if needed. Mention any important side effects.
    
    Args:
        param1: Description of param1
        param2: Description of param2 (default: X)
    
    Returns:
        Description of return value
    
    Raises:
        MyError: When condition occurs
        OtherError: When other condition occurs
    
    Example:
        >>> result = my_function("test", 42)
        >>> print(result)
        {...}
    """
    pass
```

### 7.2 Architecture Diagram (in README)

Mermaid diagram showing:
- Routing pipeline (input → JordanMoE → expert selection)
- Continuity layer (4 paradigms, checkpoint/restore)
- Tool dispatch (opcode registry → IPC)
- Agent loop (ReAct + Shadow)
- Bridge (HTTP server + C frontend)

---

### 7.3 API Reference

Auto-generated from docstrings:

```
src/routing/
  - jordan_moe.py
    - SpinFactor
    - JordanMoERouter
src/agents/
  - react.py
    - ReActAgent
    - ReActConfig
src/tools/
  - registry.py
    - ToolRegistry
    - ToolDefinition
  - approval.py
    - ApprovalEngine
    - RateLimiter
...
```

### 7.4 Deployment Guide

Sections:
- Prerequisites (Python 3.11+)
- Installation (pip, virtual env)
- Configuration (EngineConfig options)
- Starting daemon (systemd / Docker / bare metal)
- Health checks (HTTP /health endpoint)
- Monitoring (WORM ledger queries, metrics)
- Troubleshooting (common errors + recovery)

### 7.5 Configuration Reference

```python
# All options documented:
@dataclass
class EngineConfig:
    """Complete engine configuration."""
    
    model_provider: str = "bedrock"  # Which model provider
    model_name: str = "claude-opus"
    
    continuity_base_dir: Path = Path.home() / ".sovereign" / "continuity"
    enable_continuity: bool = True
    
    worm_ledger_path: Path | None = None
    
    approval_required_for_risky: bool = True
    rate_limit_policies: dict[str, RateLimitPolicy] = field(default_factory=dict)
    
    # ... all documented with explanations
```

---

## 8. CI/CD PIPELINE

### Goal
GitHub Actions workflow with tests, type checking, security scan, coverage reporting.

### 8.1 `.github/workflows/ci.yml` (~150 lines)

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pyright bandit
      
      - name: Run pytest
        run: pytest tests/ --cov=src --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
  
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      
      - name: Install pyright
        run: pip install pyright
      
      - name: Type check
        run: pyright src/
  
  nasm_check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install NASM
        run: sudo apt-get install -y nasm
      
      - name: Syntax check
        run: nasm -f elf64 -o /dev/null native/*.asm
  
  c_compile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Compile C core
        run: gcc -c -o /dev/null native/ipc_core.c -Wall -Wextra
  
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      
      - name: Bandit security scan
        run: |
          pip install bandit
          bandit -r src/ -f json -o bandit-report.json
      
      - name: Upload security report
        uses: actions/upload-artifact@v3
        with:
          name: bandit-report
          path: bandit-report.json
```

### 8.2 Pre-Commit Hooks (`.pre-commit-config.yaml`)

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
        language_version: python3.11
  
  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: [--profile=black]
  
  - repo: https://github.com/RobertCraigie/pyright-python
    rev: v1.1.280
    hooks:
      - id: pyright
```

---

## IMPLEMENTATION PRIORITY

### Phase 1: Crash Prevention (Week 1–2)
1. Edge cases (3.1–3.10) — all error handling
2. Input validation (4.5)
3. Unit tests (5.1) — at least 50% coverage

### Phase 2: Security (Week 2–3)
1. PathJail extensions (3.1)
2. SSRFGuard extensions (3.2)
3. Rate limiting (4.2)
4. Cost tracking (4.3)
5. Emergency kill switch (4.4)
6. Security tests

### Phase 3: Features (Week 3–4)
1. Terminal IDE (1.1–1.3)
2. Accessibility (2.1–2.3)
3. Integration tests (5.2)

### Phase 4: Polish (Week 4–6)
1. Performance optimization (6)
2. Property-based tests (5.3)
3. Documentation (7)
4. CI/CD pipeline (8)

---

## DEFINITION OF DONE

- [ ] All code passes pytest (2000+ lines coverage)
- [ ] All public methods have docstrings (format: § 7.1)
- [ ] CI/CD pipeline green on all Python 3.11–3.13
- [ ] Security scan (bandit) passes
- [ ] Type check (pyright) passes with 0 errors
- [ ] WORM append-only invariant holds (proven by tests)
- [ ] Routing latency < 10ms (profiled)
- [ ] PathJail blocks all 20 traversal attacks (test cases)
- [ ] Terminal IDE renders without flicker
- [ ] Accessibility complies with WCAG 2.1 AA (screen reader compatible)
- [ ] No external dependencies beyond Python 3.11 stdlib
- [ ] Deployment guide tested on 3 platforms (Linux/macOS/Windows)

---

## CRITICAL NOTES FOR CODEX

1. **No external deps** — Use only Python stdlib. No pip packages except dev tools (pytest, pyright, etc).
2. **WORM immutability** — Every test must verify chain integrity. If one byte changes, chain breaks.
3. **Continuity restart** — Test that agent survives daemon restart and can resume from exact step.
4. **PathJail escape** — Try 50+ creative escapes (UNC paths, drive letters, junctions on Windows). All must fail.
5. **Async/await** — All I/O must be async. No blocking calls in agent loop.
6. **Error messages** — Plain English. No jargon. Include recovery steps.
7. **Performance** — Profile before optimizing. Targets are hard (10ms routing, 100us IPC).
8. **Docstrings** — Non-negotiable. Every public function must be documented.

---

**End of Specification**

Document version: 1.0  
Generated: 2026-08-06  
Scope: Full production hardening of Sovereign Python LLM Engine  
Target audience: Codex AI code implementation agent
