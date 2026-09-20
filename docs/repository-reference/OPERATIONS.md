# Operations Guide

Operational procedures for running, monitoring, debugging, and maintaining Sovereign Engine v2 in production and development environments.

---

## 1. Starting the System

### 1.1 Development Startup

```bash
# Activate virtual environment
source .venv/bin/activate

# Set environment variables
export PYTHONPATH=.
export SOVEREIGN_LOG_LEVEL=DEBUG
export BEDROCK_MODEL=anthropic.claude-3-haiku-20240307-v1:0

# Run directly
python run.py

# Or via CLI
sovereign route --task "explain fibonacci" --verbose
```

**Expected output:**
```
Booting Sovereign Engine...

Routing: active experts = 1, success_count = 1
Routing decision: Lambda expert

=================================================
RESULT:
=================================================
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
```

### 1.2 HTTP Bridge Startup

```bash
# Run HTTP bridge server
python -m src.bridge.http_server --host 0.0.0.0 --port 8000 --workers 4

# Or via uvicorn directly
uvicorn src.bridge.http_server:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 1.3 Test the Startup

```bash
# Health check
curl http://localhost:8000/health

# Response
{"status": "healthy", "model": "haiku", "tools": 23, "version": "2.0.0"}
```

---

## 2. Monitoring

### 2.1 System Health Metrics

```python
# Query system health
import requests

response = requests.get("http://localhost:8000/health")
health = response.json()

print(f"Status: {health['status']}")
print(f"Tools loaded: {health['tools']}")
print(f"Model: {health['model']}")
print(f"Uptime: {health.get('uptime_seconds', 'N/A')}s")
```

### 2.2 Request Metrics

```
GET /metrics

Response (Prometheus format):
    sovereign_requests_total{endpoint="/chat"} 1234
    sovereign_request_duration_ms{endpoint="/chat"} 450
    sovereign_tool_calls_total{tool="file_read"} 56
    sovereign_errors_total{type="timeout"} 3
```

### 2.3 Live Monitoring Dashboard

```bash
# Install monitoring
pip install prometheus-client grafana-api

# View dashboards
open http://localhost:3000  # Grafana
```

### 2.4 Log Monitoring

```bash
# Stream logs in real-time
tail -f ~/.sovereign/logs/engine.log | grep -E "ERROR|CRITICAL"

# Search logs for errors
grep "ERROR\|CRITICAL" ~/.sovereign/logs/engine.log

# Count errors by type
grep -o "ERROR: [^:]*" ~/.sovereign/logs/engine.log | sort | uniq -c
```

### 2.5 Performance Metrics

Key metrics to monitor:

| Metric | Target | Alert Level |
|--------|--------|------------|
| Request latency (p95) | <1s | >2s |
| Routing latency | <50ms | >100ms |
| Tool timeout rate | <1% | >5% |
| Model availability | >99% | <95% |
| WORM ledger size | <100MB/day | >500MB/day |
| Memory usage | <2GB | >5GB |
| CPU usage | <50% | >80% |

---

## 3. Debugging

### 3.1 Enable Debug Logging

```bash
# Run with debug logging
export SOVEREIGN_LOG_LEVEL=DEBUG
export RUST_LOG=debug

python run.py
```

### 3.2 Interactive Debugger

```python
# Add breakpoint in code
import pdb

def route_task(task):
    pdb.set_trace()  # Execution stops here
    # Now can inspect variables, step through code
    result = routing.route(task)
    return result

# In debugger:
# (Pdb) print(task)
# (Pdb) n (next line)
# (Pdb) c (continue)
# (Pdb) l (list code)
```

### 3.3 Execution Trace

```bash
# Run with execution tracing
python -m trace --trace run.py 2>&1 | head -100

# Or with profiling
python -m cProfile -s cumulative run.py
```

### 3.4 Routing Trace

```bash
# Get detailed routing trace via API
curl -X POST http://localhost:8000/routing/trace \
  -H "Content-Type: application/json" \
  -d '{"prompt": "write a function"}'

# Response includes all 11-stage pipeline details
{
  "parse": {"intent": "generation", "confidence": 0.95, ...},
  "graph": {"nodes": 5, "edges": 12, ...},
  "jordan": {"eigenvalues": [...], "stability_score": 0.87, ...},
  "jacobian": {"condition_number": 2.34, ...},
  "constraints": {"passed": 3, "blocked": 1, ...},
  "routing": {"active_experts": ["coder", "reasoner"], ...},
  "dispatch": {"active_count": 2, "success_count": 2, ...}
}
```

---

## 4. Configuration

### 4.1 Configuration File

**Location:** `~/.sovereign/config.yaml`

```yaml
# Model configuration
model:
  provider: bedrock
  model_id: anthropic.claude-3-haiku-20240307-v1:0
  max_tokens: 500
  temperature: 0.7

# Routing configuration
routing:
  top_k: 2
  nand_conflicts: []
  merge_strategy: weighted_concat

# Tool configuration
tools:
  timeout_ms: 30000
  require_approval_for_risky: true
  approved_paths: ["/home/user/safe/"]

# Logging
logging:
  level: INFO
  format: verbose
  file: ~/.sovereign/logs/engine.log
  max_file_size_mb: 100
  backup_count: 5

# Continuity
continuity:
  enabled: true
  base_dir: ~/.sovereign/continuity
  checkpoint_interval_steps: 10

# WORM ledger
worm:
  base_dir: ~/.sovereign/worm
  rotate_on_size_mb: 500
```

### 4.2 Environment Variables

```bash
# Model configuration
export BEDROCK_MODEL="anthropic.claude-3-haiku-20240307-v1:0"
export BEDROCK_REGION="us-east-1"

# Engine configuration
export SOVEREIGN_LOG_LEVEL="DEBUG"
export SOVEREIGN_MAX_STEPS=10
export SOVEREIGN_TOOL_TIMEOUT_MS=30000

# Feature flags
export SOVEREIGN_ENABLE_CONTINUITY=true
export SOVEREIGN_ENABLE_WORM=true
export SOVEREIGN_ENABLE_FORMAL_VERIFICATION=false
```

### 4.3 Runtime Configuration

```python
# Programmatic configuration
from src.agents.react import ReActConfig
from src.routing.pipeline import RoutingPipeline

config = ReActConfig(
    max_steps=10,
    reflection_on_error=True,
    log_to_worm=True,
    require_approval_for_risky=True,
    enable_continuity=True
)

pipeline = RoutingPipeline(
    experts={...},
    top_k=2,
    merge_strategy="weighted_concat",
    expert_timeout_ms=30000
)
```

---

## 5. Shutdown

### 5.1 Graceful Shutdown

```bash
# Send SIGTERM (graceful)
kill -TERM <pid>

# Expected: system completes in-flight requests, then exits
```

**Shutdown sequence:**
1. Stop accepting new requests
2. Wait for in-flight requests to complete (with timeout)
3. Close connections gracefully
4. Flush pending writes to WORM ledger
5. Save continuity checkpoints
6. Exit cleanly

### 5.2 Emergency Shutdown

```bash
# Send SIGKILL (immediate, may lose data)
kill -9 <pid>

# Data loss risk: pending WORM entries may be lost
# Solution: periodic checkpoints prevent full loss
```

### 5.3 Restart

```bash
# Restart with state recovery
pkill -TERM sovereign
sleep 2
python run.py  # Resumes from checkpoint if available
```

---

## 6. Maintenance Tasks

### 6.1 Log Rotation

```bash
# Manual log rotation
cd ~/.sovereign/logs
gzip engine.log
mv engine.log.gz engine.log.$(date +%Y%m%d).gz

# Automated rotation (logrotate)
# /etc/logrotate.d/sovereign
/home/user/.sovereign/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
}
```

### 6.2 WORM Ledger Maintenance

```bash
# Check ledger integrity
python -c "
from src.core.evidence import WORMLedger
worm = WORMLedger()
valid, msg = worm.validate_chain()
print(f'Chain valid: {valid}')
print(f'Total entries: {worm.count()}')
"

# Output:
# Chain valid: True
# Total entries: 12345
```

### 6.3 Clean Up Old State

```bash
# Remove old continuity checkpoints (>7 days)
find ~/.sovereign/continuity -type f -mtime +7 -delete

# Archive old WORM ledgers
cd ~/.sovereign/worm
for f in *.jsonl.*(m+7); do
  gzip "$f"
  mv "$f.gz" archive/
done
```

### 6.4 Disk Space Management

```bash
# Check current usage
du -sh ~/.sovereign/*

# Clean up large files
# Remove old logs
rm ~/.sovereign/logs/*.gz

# Archive WORM entries >30 days
find ~/.sovereign/worm -name "*.jsonl" -mtime +30 -exec gzip {} \;

# Remove temp files
rm -rf /tmp/sovereign_*
```

### 6.5 Database Maintenance (if applicable)

```bash
# Vacuum database (SQLite)
sqlite3 ~/.sovereign/cache.db VACUUM;

# Analyze for optimization
sqlite3 ~/.sovereign/cache.db ANALYZE;
```

---

## 7. Scaling Operations

### 7.1 Multi-Instance Setup

```bash
# Run multiple workers
python -m uvicorn src.bridge.http_server:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 8

# Load balance across instances
upstream sovereign_backend {
  server 127.0.0.1:8000;
  server 127.0.0.1:8001;
  server 127.0.0.1:8002;
}

server {
  listen 80;
  location / {
    proxy_pass http://sovereign_backend;
  }
}
```

### 7.2 Distributed State (Advanced)

```python
# Use Redis for shared state (optional)
import redis

class DistributedContinuity:
    def __init__(self):
        self.redis = redis.Redis(host='localhost', port=6379)
    
    def save_state(self, agent_id: str, state: dict):
        self.redis.set(f"continuity:{agent_id}", json.dumps(state))
    
    def load_state(self, agent_id: str) -> dict:
        data = self.redis.get(f"continuity:{agent_id}")
        return json.loads(data) if data else None
```

---

## 8. Troubleshooting Common Issues

### 8.1 High Memory Usage

```
Symptom: Memory usage > 5GB

Investigation:
  1. Check what's using memory
     ps aux | grep python
  
  2. Check WORM ledger size
     du -sh ~/.sovereign/worm
  
  3. Check cache size
     du -sh ~/.sovereign/cache
  
  4. Check logs
     du -sh ~/.sovereign/logs

Solutions:
  - Archive old WORM entries
  - Clear cache: rm ~/.sovereign/cache/*
  - Rotate logs more frequently
  - Reduce model context window
```

### 8.2 Slow Responses

```
Symptom: Request latency > 5s

Investigation:
  1. Check routing latency
     curl /metrics | grep routing
  
  2. Check tool execution time
     grep "tool_duration" ~/.sovereign/logs/engine.log
  
  3. Check model inference time
     grep "model_latency" ~/.sovereign/logs/engine.log
  
  4. Check system resources
     top, iostat, vmstat

Solutions:
  - Increase model timeout
  - Reduce tool timeout (fail faster)
  - Cache routing decisions
  - Use faster model (e.g., Haiku vs Sonnet)
```

### 8.3 Tool Timeouts

```
Symptom: Many tool timeout errors

Investigation:
  1. Check tool execution logs
     grep "ToolTimeoutError" ~/.sovereign/logs/engine.log
  
  2. Check which tools are slow
     grep "tool_duration" ~/.sovereign/logs/engine.log | sort

Solutions:
  - Increase tool timeout
  - Optimize tool implementations
  - Use faster alternatives
  - Enable tool caching
```

### 8.4 WORM Ledger Corruption

```
Symptom: WORM chain validation fails

Investigation:
  1. Validate chain
     python -c "from src.core.evidence import WORMLedger; print(WORMLedger().validate_chain())"
  
  2. Check last entries
     tail -20 ~/.sovereign/worm/*.jsonl

Solutions:
  - Restore from backup
  - Rebuild from evidence artifacts
  - Switch to new ledger file
```

---

## 9. Backup & Recovery

### 9.1 Backup Strategy

```bash
# Daily backup script
#!/bin/bash

BACKUP_DIR="/backups/sovereign/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup WORM ledger
cp -r ~/.sovereign/worm "$BACKUP_DIR/"

# Backup continuity state
cp -r ~/.sovereign/continuity "$BACKUP_DIR/"

# Backup configuration
cp -r ~/.sovereign/config.yaml "$BACKUP_DIR/"

# Compress
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"

# Remove uncompressed
rm -rf "$BACKUP_DIR"

echo "Backup complete: $BACKUP_DIR.tar.gz"
```

### 9.2 Restore from Backup

```bash
# Extract backup
tar -xzf /backups/sovereign/20260919.tar.gz

# Restore files
cp -r backup/worm ~/.sovereign/
cp -r backup/continuity ~/.sovereign/
cp backup/config.yaml ~/.sovereign/

# Validate
python -c "from src.core.evidence import WORMLedger; WORMLedger().validate_chain()"
```

---

## 10. Disaster Recovery

### 10.1 Complete System Failure

```
Scenario: /home/user/.sovereign/ corrupted beyond repair

Recovery steps:
1. Stop Sovereign Engine
2. Restore latest backup to /home/user/.sovereign/
3. Verify WORM ledger integrity
4. Start Sovereign Engine
5. Monitor logs for anomalies
6. Validate all functionality
```

### 10.2 Data Loss Mitigation

**Measures already in place:**
- Immutable WORM ledger (append-only, no overwrites)
- Periodic continuity checkpoints
- Multiple backup locations
- Blake3 hashing for integrity verification

---

## 11. Deployment Checklist

Before deploying to production:

```
□ Environment variables configured
□ Database/cache initialized
□ SSL certificates installed
□ Monitoring configured
□ Logging configured
□ Backup strategy tested
□ Disaster recovery tested
□ Load testing completed
□ Security audit passed
□ Documentation reviewed
□ Team trained
□ Incident response plan ready
```

---

## 12. Performance Tuning

```
# Optimize for throughput
export SOVEREIGN_BATCH_SIZE=32
export SOVEREIGN_WORKERS=8

# Optimize for latency
export SOVEREIGN_BATCH_SIZE=1
export SOVEREIGN_MAX_QUEUE_DEPTH=100

# Optimize for memory
export SOVEREIGN_CACHE_MAX_SIZE_MB=512
export SOVEREIGN_LOG_RETENTION_DAYS=3

# Optimize for cost
export BEDROCK_MODEL=anthropic.claude-3-haiku-20240307-v1:0
export SOVEREIGN_TOOL_CACHE_ENABLED=true
```

---

## Summary

**Starting:** Run `python run.py` or HTTP server
**Monitoring:** Check `/health`, logs, metrics
**Debugging:** Enable DEBUG logging, use tracing
**Configuration:** Via config.yaml or env vars
**Shutdown:** Graceful SIGTERM for clean exit
**Maintenance:** Rotate logs, verify WORM, clean cache
**Scaling:** Multi-worker setup with load balancer
**Recovery:** Regular backups, validated restore procedure
**Troubleshooting:** Memory/latency/timeout diagnostics
**Safety:** WORM immutability, checkpoint continuity

All operations maintain audit trails and system resilience.
