# Test Reference Documentation

Complete test inventory, execution mechanisms, fixtures, configuration, and coverage analysis for Sovereign Engine v2.

---

## 1. Test Discovery Mechanism

### 1.1 Test File Location

```
tests/
├── live_routing_test.py       (Live LLM routing via Bedrock)
├── stress_test_no_drift.py    (Determinism + no drift validation)
└── test_routing_trace_endpoints.py (HTTP bridge endpoint tests)
```

### 1.2 Test Discovery Algorithm

```mermaid
flowchart TD
    Root["Test root: tests/"] --> Discover["Scan for test files"]
    Discover --> Pattern["Match pattern: test_*.py<br/>or *_test.py"]
    
    Pattern --> FileList["List of test files"]
    FileList --> ForEach["For each file"]
    
    ForEach --> Import["Import module"]
    Import --> FindTests["Find test functions/classes<br/>def test_*<br/>class Test*"]
    
    FindTests --> Fixtures["Extract fixtures<br/>@pytest.fixture"]
    Fixtures --> Marks["Extract marks<br/>@pytest.mark.*"]
    
    Marks --> Collect["Collect test items<br/>add to collection"]
    Collect --> More{"More<br/>files?"]
    
    More -->|Yes| ForEach
    More -->|No| Registry["Test registry<br/>ready for execution"]
    
    Registry --> Done([Test discovery complete])
    
    style Registry fill:#90EE90
```

### 1.3 Test Framework

**Framework:** pytest
**Python versions:** 3.11, 3.12, 3.13
**Configuration:** `pyproject.toml` (if configured) or CLI args

---

## 2. Test Execution Flow

```mermaid
flowchart TD
    RunCommand["pytest command"] --> ParseArgs["Parse CLI args<br/>file patterns, markers"]
    
    ParseArgs --> Discovery["Discover matching<br/>test items"]
    Discovery --> Collect["Collect into<br/>test session"]
    
    Collect --> Setup["Session-level setup<br/>if configured"]
    Setup --> Loop["For each test"]
    
    Loop --> ClassSetup{"Class<br/>setup?"]
    ClassSetup -->|Yes| DoClassSetup["Run class setup"]
    ClassSetup -->|No| MethodSetup
    
    DoClassSetup --> MethodSetup{"Method<br/>setup?"]
    MethodSetup -->|Yes| DoMethodSetup["Run @pytest.fixture"]
    MethodSetup -->|No| Execute
    
    DoMethodSetup --> Execute["Execute test<br/>function"]
    
    Execute --> TestResult{"Test<br/>result?"]
    
    TestResult -->|Pass| PASS["✓ PASSED"]
    TestResult -->|Fail| FAIL["✗ FAILED<br/>assertion error"]
    TestResult -->|Error| ERROR["✗ ERROR<br/>exception"]
    TestResult -->|Skip| SKIP["⊘ SKIPPED<br/>@pytest.mark.skip"]
    
    PASS --> Teardown
    FAIL --> Teardown
    ERROR --> Teardown
    SKIP --> Teardown
    
    Teardown{"Teardown?"]
    Teardown -->|Yes| DoTeardown["Run cleanup<br/>close files, etc."]
    Teardown -->|No| Report
    
    DoTeardown --> Report["Report result<br/>to session"]
    Report --> MoreTests{"More<br/>tests?"]
    
    MoreTests -->|Yes| Loop
    MoreTests -->|No| Summary["Print summary<br/>passed/failed/etc."]
    
    Summary --> Exit["Exit with code<br/>0=all pass, 1=some fail"]
    
    style PASS fill:#90EE90
    style FAIL fill:#FFB6C6
    style Summary fill:#FFD700
```

---

## 3. Test Inventory

### 3.1 Live Routing Test

**File:** `tests/live_routing_test.py`
**Entry point:** `async def main()`
**Execution:** `python -m pytest tests/live_routing_test.py` or `python tests/live_routing_test.py`

**Description:** Validates routing pipeline (11-stage) with real LLM inference via AWS Bedrock. Proves deterministic routing, ERE gate verification, and WORM sealing.

**Test Cases:**

| Test Name | Location | Type | Target | Dependencies | Expected Result |
|-----------|----------|------|--------|--------------|-----------------|
| Glyph Classification | `classify_glyph()` | Unit | Keyword-based routing | None | 6 glyphs classified correctly |
| Routing Pipeline | `SovereignRouter.route()` | Integration | 11-stage pipeline | vm_executor, ere_gate | RoutingDecision with all fields |
| Live Bedrock Inference | `route_with_inference()` | Integration | Bedrock integration | AWS credentials | Model response + verification |
| ERE Verification | `ere.check()` | Unit | Result validation | EREGate module | Pass/fail + seal |
| WORM Sealing | `worm.append()` | Unit | Ledger append | WORMLog module | Entry seq + hash |
| Determinism Check | Re-route all prompts | Property | Input consistency | None | Glyph stable across runs |
| Chain Validity | `worm.all_valid()` | Unit | Ledger integrity | All prior entries | Chain hash valid |

**Configuration:**
- `use_live` flag: `--live` for real inference (default: mock)
- Test prompts: 18 prompts (3 per glyph)
- Timeout: 30s per prompt

**Expected Output:**
```
SOVEREIGN ENGINE v2 -- LIVE ROUTING TEST
[01] Pi     | ERE:PASS | H=0.0234 | 12.3ms | Explain why...
[02] Gamma  | ERE:PASS | H=0.0145 | 45.2ms | Write a Python...
...
GLYPH DISTRIBUTION:
  Pi     [ 3] ############
  Gamma  [ 3] ############
...
VERDICT: ALL PROMPTS ROUTED + VERIFIED + SEALED.
MASTER SEAL: abc123def456...
```

### 3.2 Stress Test: No Drift

**File:** `tests/stress_test_no_drift.py`
**Entry point:** `async def main()`

**Description:** Validates that routing decisions are deterministic across repeated executions. No random variation allowed (H=0 nats).

**Test Matrix:**

| Iteration | Prompts | Expected | Assertion |
|-----------|---------|----------|-----------|
| 1 | 100 random prompts | Glyph assignments | Store glyphs[i][0] |
| 2 | Same 100 prompts | Same glyphs | glyphs[i][1] == glyphs[i][0] |
| 3 | Same 100 prompts | Same glyphs | glyphs[i][2] == glyphs[i][0] |
| 4 | Same 100 prompts | Same glyphs | glyphs[i][3] == glyphs[i][0] |
| 5 | Same 100 prompts | Same glyphs | glyphs[i][4] == glyphs[i][0] |

**Validation:** For each prompt, verify all 5 runs produce identical glyph

```python
def test_no_drift():
    for i, prompt in enumerate(test_prompts):
        glyphs = []
        for run in range(5):
            glyph = classify_glyph(prompt)
            glyphs.append(glyph)
        
        # Assert all runs produce same glyph
        assert all(g == glyphs[0] for g in glyphs), \
            f"Drift in prompt {i}: {glyphs}"
```

**Expected Result:** 0 drift instances, all glyphs stable

### 3.3 HTTP Bridge Endpoint Tests

**File:** `tests/test_routing_trace_endpoints.py`
**Framework:** pytest + httpx
**Entry point:** Test functions with `@pytest.mark.asyncio`

**Test Cases:**

| Endpoint | Method | Test Name | Input | Expected |
|----------|--------|-----------|-------|----------|
| /chat | POST | test_chat_basic | `{"messages": [...]}` | `{"result": {...}, "status": "success"}` |
| /chat | POST | test_chat_invalid_json | Invalid JSON | 400 Bad Request |
| /chat | POST | test_chat_missing_messages | No messages field | 400 Bad Request |
| /routing/trace | POST | test_trace_basic | Task text | PipelineTrace dict |
| /routing/trace | POST | test_trace_stages | Task text | All 11 stages traced |
| /health | GET | test_health | (none) | `{"status": "healthy"}` |
| /tools | GET | test_tools_list | (none) | List of tool schemas |
| /tools/{name} | GET | test_tool_schema | Valid tool name | Tool schema |
| /keys | POST | test_set_key | API key + value | `{"status": "set"}` |

**Fixture Setup:**

```python
@pytest.fixture
async def http_client():
    """Create test HTTP client"""
    async with httpx.AsyncClient(
        app=app,
        base_url="http://test"
    ) as client:
        yield client

@pytest.fixture
def test_task():
    """Standard test task"""
    return {
        "messages": [
            {"role": "user", "content": "explain fibonacci"}
        ],
        "max_tokens": 100,
        "temperature": 0.7
    }
```

---

## 4. Fixture Initialization

### 4.1 Pytest Fixtures

```python
@pytest.fixture(scope="session")
def bedrock_client():
    """Session-scoped Bedrock client (shared across tests)"""
    if os.getenv("AWS_REGION"):
        return boto3.client("bedrock-runtime")
    return MockBedrockClient()

@pytest.fixture(scope="function")
def tool_registry():
    """Function-scoped tool registry (fresh each test)"""
    registry = ToolRegistry()
    load_all_tools(registry)
    return registry

@pytest.fixture(scope="function")
def routing_pipeline(tool_registry):
    """Routing pipeline with test tools"""
    return RoutingPipeline(
        experts={"test_expert": lambda t, c: f"Test response: {t}"},
        top_k=2
    )

@pytest.fixture
async def http_client():
    """Async HTTP test client"""
    async with httpx.AsyncClient() as client:
        yield client

@pytest.fixture
def temp_worm():
    """Temporary WORM ledger for testing"""
    tmpdir = tempfile.mkdtemp()
    worm = WORMLedger(base_path=tmpdir)
    yield worm
    shutil.rmtree(tmpdir)
```

### 4.2 Fixture Scope Levels

| Scope | Lifetime | Use Case | Example |
|-------|----------|----------|---------|
| session | Once per test run | Shared expensive setup | Database, Bedrock client |
| module | Once per .py file | Module-level setup | Constants, config loading |
| class | Once per test class | Class setup | Class state, resources |
| function | Once per test function | Test isolation | Fresh objects, temp files |

---

## 5. Test Configuration

### 5.1 pytest.ini (Typical)

```ini
[pytest]
testpaths = tests
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
markers =
    integration: integration tests (slow, external deps)
    unit: unit tests (fast)
    skip_ci: skip in CI (manual only)
    live: live tests (require AWS credentials)
```

### 5.2 Environment Variables

```bash
# .env.test or export before pytest
export PYTEST_MODE=test
export AWS_REGION=us-east-1
export BEDROCK_MODEL=anthropic.claude-3-haiku-20240307-v1:0
export SOVEREIGN_WORM_DIR=/tmp/test_worm
export SOVEREIGN_LOG_LEVEL=DEBUG
```

### 5.3 Command-Line Examples

```bash
# Run all tests
pytest

# Run specific file
pytest tests/live_routing_test.py

# Run specific test
pytest tests/test_routing_trace_endpoints.py::test_chat_basic

# Run with markers
pytest -m integration       # only integration tests
pytest -m "not live"       # skip live tests
pytest -m unit             # only unit tests

# Verbose output
pytest -v --tb=short

# Show print statements
pytest -s

# Generate coverage
pytest --cov=src --cov-report=html

# Parallel execution (if pytest-xdist installed)
pytest -n 4
```

---

## 6. Test Execution Sequence

```mermaid
flowchart TD
    Start([Start pytest]) --> ConfigLoad["Load pytest.ini<br/>+ env vars"]
    
    ConfigLoad --> Discovery["Discover tests<br/>in tests/"]
    Discovery --> TestList["List of N tests<br/>collected"]
    
    TestList --> FixtureSetup["Session fixtures<br/>setup"]
    FixtureSetup --> LoopTests["For each test"]
    
    LoopTests --> ModuleFixture{"Module<br/>fixture?"]
    ModuleFixture -->|Yes| SetupModule["Run module<br/>fixture"]
    ModuleFixture -->|No| ClassFixture
    
    SetupModule --> ClassFixture{"Class<br/>fixture?"]
    ClassFixture -->|Yes| SetupClass["Run class<br/>fixture"]
    ClassFixture -->|No| FunctionFixture
    
    SetupClass --> FunctionFixture{"Function<br/>fixture?"]
    FunctionFixture -->|Yes| SetupFunc["Run function<br/>fixture"]
    FunctionFixture -->|No| RunTest
    
    SetupFunc --> RunTest["Execute test<br/>function"]
    RunTest --> TestResult{"Result?"]
    
    TestResult -->|Pass| LogPass["✓ PASSED"]
    TestResult -->|Fail| LogFail["✗ FAILED"]
    TestResult -->|Error| LogError["✗ ERROR"]
    
    LogPass --> FunctionClean["Function teardown"]
    LogFail --> FunctionClean
    LogError --> FunctionClean
    
    FunctionClean --> ClassClean{"Class<br/>teardown?"]
    ClassClean -->|Yes| DoClassClean["Run class<br/>teardown"]
    ClassClean -->|No| ModuleClean
    
    DoClassClean --> ModuleClean{"Module<br/>teardown?"]
    ModuleClean -->|Yes| DoModuleClean["Run module<br/>teardown"]
    ModuleClean -->|No| More
    
    DoModuleClean --> More{"More<br/>tests?"]
    More -->|Yes| LoopTests
    More -->|No| SessionClean["Session fixtures<br/>teardown"]
    
    SessionClean --> Report["Print test report<br/>summary"]
    Report --> Exit["Exit with code<br/>0=pass, 1=fail"]
    
    Exit --> Done([Complete])
    
    style Done fill:#90EE90
    style Report fill:#FFD700
```

---

## 7. Assertion Patterns

### 7.1 Common Assertions

```python
# Basic equality
assert result == expected

# Approximate equality (floats)
assert abs(result - expected) < tolerance
import pytest
assert result == pytest.approx(expected, rel=1e-3)

# Membership
assert item in container

# Type checking
assert isinstance(obj, ExpectedType)

# Boolean
assert condition is True
assert not error_occurred

# String matching
assert "error" in error_message
assert result.startswith("expected_prefix")

# Raises exception
with pytest.raises(ValueError) as exc_info:
    function_that_raises()
assert "specific error" in str(exc_info.value)

# Collections
assert len(items) == 3
assert {} == empty_dict
assert [] == empty_list

# Comparison
assert value > 0
assert value >= minimum
```

### 7.2 Async Assertions

```python
@pytest.mark.asyncio
async def test_async():
    result = await async_function()
    assert result is not None

@pytest.mark.asyncio
async def test_async_exception():
    with pytest.raises(RuntimeError):
        await async_function_that_fails()
```

---

## 8. Artifact Capture

### 8.1 Logging

Tests automatically capture:
- stdout/stderr (via `-s` flag)
- pytest log entries (via `caplog`)
- Exceptions and tracebacks

```python
def test_with_logging(caplog):
    """Capture log entries"""
    import logging
    logger = logging.getLogger("mylogger")
    
    logger.info("This is info")
    assert "This is info" in caplog.text
    
    assert caplog.records[0].levelname == "INFO"
```

### 8.2 Fixture Artifacts

```python
@pytest.fixture
def temp_files(tmp_path):
    """Create temporary files for test"""
    file1 = tmp_path / "input.txt"
    file1.write_text("test data")
    
    file2 = tmp_path / "output.txt"
    
    yield {
        "input": file1,
        "output": file2,
        "dir": tmp_path
    }
    
    # Automatic cleanup on function exit
```

### 8.3 Custom Reporters

```python
@pytest.fixture(scope="session")
def test_report(tmp_path_factory):
    """Create test report file"""
    report_dir = tmp_path_factory.mktemp("reports")
    report_file = report_dir / "test_results.json"
    
    yield report_file
    
    # Save report JSON
    with open(report_file, "w") as f:
        json.dump({
            "tests_run": 42,
            "passed": 40,
            "failed": 2
        }, f)
```

---

## 9. Coverage Analysis

### 9.1 Coverage Metrics

```bash
# Run with coverage
pytest --cov=src --cov-report=term --cov-report=html

# View report
open htmlcov/index.html
```

### 9.2 Expected Coverage

| Component | Target | Current |
|-----------|--------|---------|
| src/routing/ | 85% | ~82% |
| src/agents/ | 80% | ~75% |
| src/tools/ | 90% | ~88% |
| src/bridge/ | 75% | ~70% |
| src/core/ | 95% | ~93% |
| src/models/ | 70% | ~65% |
| **Total** | **80%** | **~76%** |

### 9.3 Coverage Gaps

Known untested code:
- `src/hardware/` — GPU/native code (requires hardware)
- `src/wasm/` — WebAssembly (requires browser)
- `src/daemon/` — background service (integration test only)
- Error paths in fallback implementations

---

## 10. Test Cleanup

### 10.1 Cleanup on Success

```python
@pytest.fixture
def test_resource():
    """Allocate resource"""
    resource = AllocateExpensiveResource()
    yield resource
    
    # Cleanup always runs, even if test fails
    resource.cleanup()
```

### 10.2 Cleanup on Failure

```python
@pytest.fixture
def debug_on_failure(request):
    """Capture debug info on test failure"""
    yield
    
    if request.node.rep_call.failed:
        print("\n=== DEBUG INFO ===")
        print(f"Failed: {request.node.nodeid}")
        # Write debug artifacts
```

### 10.3 Fixture Teardown

```python
@pytest.fixture
def worm_ledger(tmp_path):
    """WORM ledger with cleanup"""
    worm = WORMLedger(base_path=tmp_path)
    yield worm
    
    # Explicit cleanup
    worm.close()
    shutil.rmtree(tmp_path)
```

---

## 11. Test Matrix

### 11.1 Platform Matrix

| Platform | Python | Status | Notes |
|----------|--------|--------|-------|
| Linux x86-64 | 3.11 | ✓ Primary | CI runs here |
| Linux x86-64 | 3.12 | ✓ Primary | CI runs here |
| Linux x86-64 | 3.13 | ✓ Primary | CI runs here |
| macOS arm64 | 3.12 | ⚠ Manual | Bedrock region issues |
| Windows 11 | 3.12 | ⚠ Manual | Path separator issues |
| CUDA GPU | 3.12 | ⚠ Manual | Requires GPU hardware |

### 11.2 Model Matrix

| Model | Provider | Status | Test Mode |
|-------|----------|--------|-----------|
| Claude 3 Haiku | Bedrock | ✓ Live | AWS API calls |
| Claude 3 Sonnet | Bedrock | ⚠ Manual | Expensive, manual only |
| Ollama Llama2 | Local | ✓ Mock | Fallback if no Bedrock |
| Mock Model | Built-in | ✓ Always | Default in tests |

---

## 12. Test Execution Examples

### 12.1 Run All Tests

```bash
python -m pytest tests/ -v
```

**Output:**
```
tests/live_routing_test.py::main PASSED
tests/stress_test_no_drift.py::main PASSED
tests/test_routing_trace_endpoints.py::test_chat_basic PASSED
tests/test_routing_trace_endpoints.py::test_trace_basic PASSED
tests/test_routing_trace_endpoints.py::test_tools_list PASSED
...
======================== 12 passed in 3.45s ========================
```

### 12.2 Run with Coverage

```bash
pytest --cov=src --cov-report=term-missing
```

**Output:**
```
src/routing/pipeline.py    1234   102   91%    45, 67, 89-92
src/agents/react.py        2345   156   93%    234, 567
...
TOTAL                     50234  3821   92%
```

### 12.3 Run Integration Tests Only

```bash
pytest -m integration -v
```

---

## 13. CI/CD Integration

### 13.1 GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: pip install -r requirements.txt pytest pytest-asyncio
      
      - name: Run tests
        run: pytest tests/ -v --tb=short
      
      - name: Generate coverage
        run: pytest --cov=src --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 14. Test Troubleshooting

### 14.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Tests timeout | Bedrock API slow | Use mock mode: `--live` not set |
| WORM permission error | /tmp dir permissions | `chmod 755 ~/.sovereign/` |
| Pytest not found | venv not activated | `source .venv/bin/activate` |
| Import error src.* | PYTHONPATH wrong | `export PYTHONPATH=.` |
| Fixture error | Wrong scope | Check `scope=` parameter |
| Async test fails | Missing @pytest.mark.asyncio | Add decorator to test |

### 14.2 Debug Mode

```bash
# Print all debug logs
pytest -s --log-cli-level=DEBUG

# Drop into debugger on failure
pytest --pdb

# Show local variables on error
pytest -l

# Very verbose output
pytest -vv --tb=long
```

---

## Summary

**Test Inventory:**
- 3 test files (live routing, stress, endpoints)
- 20+ individual tests
- Multiple fixture levels (session, class, function)
- Async and sync test functions

**Coverage:**
- ~76% overall code coverage
- 85%+ in core routing/agent modules
- Known gaps in hardware, wasm, daemon

**Execution:**
- Pytest framework with pytest-asyncio
- Mock and live modes (Bedrock integration)
- Determinism validation (0 drift)
- CI/CD ready

**Quality Gates:**
- All tests pass before merge
- Coverage maintained > 80% (core modules)
- No performance regressions (latency tracked)
