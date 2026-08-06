# 3-Phase Sprint Plan — Sovereign Engine v2

## Current State (Audit)

**Tracked:** 137 files on remote
**Untracked (needs commit):** ide/, docs/, routing_trace.py, qra_router.py, tests/
**Broken:** ere.py had syntax error (FIXED locally, not pushed)
**Missing docs:** ROUTING.md, TOOLS.md, CONTINUITY.md, SECURITY.md

---

## PHASE 1: Structural Integrity (This Sprint)

Goal: Every file compiles, imports resolve, repo structure is clean.

- [x] Fix ere.py syntax error (smart quotes → ASCII)
- [ ] Full syntax check — 0 errors across all .py files
- [ ] Commit IDE (ide/native/ — 47 C files, 4,459 lines)
- [ ] Commit Gap 2 (qra_router.py — QRA 6-glyph routing)
- [ ] Commit Gap 5 (routing_trace.py — trace collector for IDE bridge)
- [ ] Commit docs/ (GETTING_STARTED.md, CONFIGURATION.md)
- [ ] Remove Codex planning artifacts (AGENT_BRIEF, gaps/, architecture/)
- [ ] Verify all __init__.py exports resolve
- [ ] Push to remote — single clean commit

**Acceptance:** `python -c "from src import SovereignEngine"` works. Zero syntax errors. No stale files.

---

## PHASE 2: Documentation + User Guides (Next Sprint)

Goal: Someone can clone this repo and understand + use it without asking.

- [ ] docs/ROUTING.md — 11-stage pipeline explained, tuning, custom experts
- [ ] docs/TOOLS.md — All 34 tools, registration, IPC, supervisor
- [ ] docs/CONTINUITY.md — 4 paradigms, crash recovery, replay
- [ ] docs/SECURITY.md — PathJail, SSRF, WORM, ERE, inverted AST
- [ ] docs/IDE.md — How to build the C IDE, connect to engine, use ConPTY
- [ ] docs/MACHINE_CODE.md — What the bytecode assembler / VM / x86 gen actually do
- [ ] README cross-references all docs (already done in new README)
- [ ] Each doc has runnable code examples

**Acceptance:** A developer can read docs/ top-to-bottom and set up the full system.

---

## PHASE 3: Version Control + Release + Packaging (Final Sprint)

Goal: Proper tagged release with installable package.

- [ ] pyproject.toml verified (already exists)
- [ ] `python -m build` produces .whl
- [ ] GitHub Release v2.0.0 with changelog
- [ ] Git tag v2.0.0
- [ ] LICENSE file (BSL 1.1)
- [ ] CHANGELOG.md
- [ ] .github/workflows/ci.yml (Python 3.11-3.13 matrix, pytest, pyright)
- [ ] requirements.txt is empty (stdlib only — but document optional deps)
- [ ] Verify `pip install .` works from clean clone

**Acceptance:** `pip install .` → `sovereign --help` works. Tagged release on GitHub.

---

## Rules

1. No rushing. Every file gets syntax-checked before commit.
2. No planning docs in the repo. Only code, docs, and config.
3. Line counts in README must be verified (`wc -l`) not guessed.
4. If an agent writes something broken, I fix it or rewrite it. No shipping broken code.
5. One clean commit per phase. Not 50 micro-commits.
