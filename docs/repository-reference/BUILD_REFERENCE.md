# SOVEREIGN ENGINE V2 — BUILD REFERENCE

**Created:** 2026-09-19  
**Status:** Complete build system documentation

---

## BUILD SYSTEM OVERVIEW

Sovereign Engine v2 uses **multiple independent build systems** per language:

1. **Python:** setuptools (pip) — primary entry point
2. **Haskell:** Cabal — compiler package
3. **Rust:** Cargo — multiple crates
4. **Lean 4:** Lake — formal verification
5. **Agda:** agda-mode — formal verification
6. **CUDA:** nvcc — GPU kernels
7. **NASM:** nasm — x86-64 assembly
8. **C/C++:** CMake/MSVC — IDE + dispatcher
9. **Swift:** Swift PM — training/visualization
10. **TypeScript:** Vite — Electron IDE

---

## PYTHON BUILD (PRIMARY)

### Configuration File: pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "sovereign-engine"
version = "2.0.0"
description = "Production-grade LLM agent framework..."
requires-python = ">=3.11"

[project.scripts]
sovereign = "src.cli.main:main"

[project.optional-dependencies]
bedrock = ["boto3>=1.28"]
pytorch = ["torch>=2.0"]

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]
```

### Build Commands

```bash
# Development install (editable)
pip install -e .

# Production install
pip install .

# Install with optional dependencies
pip install -e ".[bedrock,pytorch]"

# Build wheel
python -m build

# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
ruff check src/ tests/

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Entry Points

```
CLI: sovereign [args]
    ↓
src.cli.main:main()

Direct: python run.py
    ↓
Loads tools → RoutingPipeline → ReActAgent → Bedrock

HTTP Server: uvicorn src.bridge.http_server:app
    ↓
FastAPI app on port 8000
```

### Dependency Groups

```
Core (Layer 0-5):
  ├─ PyNaCl, aiofiles, httpx
  ├─ pydantic, jsonschema
  ├─ numpy, scipy
  ├─ torch, transformers, sentence-transformers
  ├─ boto3, botocore
  └─ beautifulsoup4, lxml

Testing:
  ├─ pytest, pytest-asyncio, pytest-cov
  └─ pytest-mock

Development:
  ├─ black, mypy, ruff
  └─ mkdocs, mkdocs-material
```

### Build Artifacts

```
dist/
├─ sovereign-engine-2.0.0.tar.gz    # Source distribution
└─ sovereign_engine-2.0.0-py3-*.whl # Wheel (binary)

.egg-info/                           # Installed metadata
site-packages/src/                   # (after pip install -e)
```

---

## HASKELL BUILD (cobalt/)

### Configuration File: cobalt/cobalt.cabal

```cabal
name:          cobalt
version:       0.1.0.0
build-type:   Simple
cabal-version: >=2.0

library
  exposed-modules:     Core.Group, Core.Nat
                       Calculus.Derivative, Calculus.Integral
                       Language.Fixpoint.LiquidOps.Kernel
                       ISA.Core, ISA.Macro
                       Physics.Godel, Physics.WormholeBH
  build-depends:       base, ghc-lib-parser, liquid-fixpoint, ghc-lib
  hs-source-dirs:      src

executable cobalt
  main-is:             Main.hs
  build-depends:       base, cobalt
  hs-source-dirs:      src
```

### Build Commands

```bash
cd cobalt/

# Build library
cabal build

# Build and run
cabal run cobalt

# Run tests
cabal test

# Generate API documentation
cabal haddock

# Install locally
cabal install --installdir=./bin

# Clean build artifacts
cabal clean
```

### Compiler Requirements

```
GHC 9.2+ (Glasgow Haskell Compiler)
Cabal 3.6+
```

### Build Artifacts

```
dist-newstyle/
├─ build/
│   ├─ x86_64-linux/
│   │   └─ ghc-9.X.X/
│   │       └─ cobalt-0.1.0.0/
│   │           ├─ l/cobalt/
│   │           └─ x/cobalt/
│   └─ [other platforms]
└─ [caches]

bin/
└─ cobalt               # Executable (after cabal install)
```

---

## RUST BUILD (CARGO)

### Workspace Structure

```
Cargo.toml (workspace root) — NOT PRESENT (independent crates)

catn/Cargo.toml
kernels/rust/Cargo.toml
runtime/Cargo.toml
the-49th-call/Cargo.toml
magma/Cargo.toml
```

### Build Commands (catn/ as example)

```bash
cd catn/

# Debug build
cargo build

# Release build (optimized)
cargo build --release

# Run executable
cargo run --release

# Run tests
cargo test --release

# Generate documentation
cargo doc --open

# Check for errors without compiling
cargo check

# Format code
cargo fmt

# Lint
cargo clippy

# Clean build artifacts
cargo clean
```

### Configuration: Cargo.toml

```toml
[package]
name = "catn"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
rayon = "1.7"
ndarray = { version = "0.15", features = ["serde"] }
num-complex = "0.4"

[profile.release]
opt-level = 3
lto = true
codegen-units = 1
```

### Build Artifacts

```
catn/target/
├─ debug/
│   ├─ catn                 # Debug executable
│   └─ deps/
└─ release/
    ├─ catn                 # Release executable
    └─ deps/
        ├─ libcatn.rlib     # Static library
        ├─ libcatn.so       # Dynamic library (Unix)
        └─ libcatn.dll      # Dynamic library (Windows)
```

### Cross-Compilation

```bash
# List available targets
rustup target list

# Add target
rustup target add x86_64-pc-windows-gnu

# Build for target
cargo build --target x86_64-pc-windows-gnu
```

---

## LEAN 4 BUILD (LAKE)

### Configuration: lake.toml (if present)

Not present in current setup; proofs are standalone .lean files.

### Build Commands

```bash
# Individual Lean file (verification only)
lake build research/formal/subleq/SUBLEQ.lean

# Or using Lean standalone:
lean research/formal/subleq/SUBLEQ.lean

# Verify all proofs
cd research/formal/
for file in *.lean; do lean "$file" || exit 1; done
```

### Compiler Requirements

```
Lean 4.0+
Lake 0.2+ (Lean package manager)
```

### Proof Verification

```
Each .lean file compiles to bytecode.
No sorry terms (100% proven).
Output: Proof object or error.
```

---

## AGDA BUILD (agda-mode)

### Build Commands

```bash
# Verify proof
agda research/formal/IronicMirror/XInvariant.agda

# Compile to Haskell
agda --compile research/formal/IronicMirror/XInvariant.agda

# Typecheck without compilation
agda --no-unicode research/formal/IronicMirror/XInvariant.agda
```

### Compiler Requirements

```
Agda 2.6+
```

---

## CUDA BUILD (nvcc)

### Build Commands

```bash
# Compile CUDA kernel
nvcc -c kernels/cuda/cuda_pipeline.cu -o cuda_pipeline.o

# Link with C/C++ code
nvcc -o cuda_app kernels/cuda/cuda_pipeline.o main.cpp

# With optimization
nvcc -O3 -c kernels/cuda/cuda_pipeline.cu -o cuda_pipeline.o

# For specific GPU architecture
nvcc -arch=sm_80 -c kernels/cuda/cuda_pipeline.cu
```

### Compiler Requirements

```
CUDA Toolkit 11.0+ (nvcc compiler)
```

### Build Artifacts

```
cuda_pipeline.o          # Object file
cuda_app                 # Executable
```

---

## NASM BUILD (x86-64 Assembly)

### Build Commands

```bash
# Assemble to object file
nasm -f elf64 -o native/asm/qra.o native/asm/qra.asm  # Linux

nasm -f win64 -o native/asm/qra.obj native/asm/qra.asm # Windows

# Link with C/C++ object
gcc native/asm/qra.o native/dispatcher/dispatcher.c -o runtime.so -shared

# Verify syntax without assembling
nasm -f elf64 -e native/asm/qra.asm
```

### Compiler Requirements

```
NASM (Netwide Assembler) 2.14+
```

### Build Artifacts

```
native/asm/qra.o         # Object file (Linux)
native/asm/qra.obj       # Object file (Windows)
runtime.so               # Shared library (Linux)
runtime.dll              # Shared library (Windows)
```

---

## C/C++ BUILD (CMAKE / MSVC)

### Configuration: ide/CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.10)
project(SovereignIDE)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(sovereign-ide
  ide/desktop/main.cpp
  native/dispatcher/dispatcher.c
)

target_link_libraries(sovereign-ide
  pthread
  m
)
```

### Build Commands

```bash
# Create build directory
mkdir build && cd build

# Configure
cmake ..

# Build
cmake --build . --config Release

# Install
cmake --install . --prefix /usr/local

# Run
./sovereign-ide
```

### Windows Build (MSVC)

```bash
# Visual Studio generator
cmake .. -G "Visual Studio 16 2019"

# Build
cmake --build . --config Release

# Run
.\Release\sovereign-ide.exe
```

### Build Artifacts

```
build/
├─ CMakeFiles/
├─ CMakeCache.txt
├─ Makefile (or Visual Studio solution)
└─ sovereign-ide              # Executable (Linux/macOS)
   sovereign-ide.exe          # Executable (Windows)
```

---

## SWIFT BUILD (SPM)

### Configuration: training/Package.swift

```swift
// swift-tools-version:5.5
import PackageDescription

let package = Package(
    name: "AgentFishTank",
    platforms: [
        .macOS(.v12),
        .iOS(.v15)
    ],
    products: [
        .library(name: "AgentFishTank", targets: ["AgentFishTank"])
    ],
    dependencies: [
        // SceneKit is built-in; no external deps needed
    ],
    targets: [
        .target(name: "AgentFishTank", path: "Sources/AgentFishTank"),
        .testTarget(name: "AgentFishTankTests", dependencies: ["AgentFishTank"])
    ]
)
```

### Build Commands

```bash
cd training/

# Build library
swift build

# Build release (optimized)
swift build -c release

# Run tests
swift test

# Generate documentation
swift package generate-documentation

# Build for specific platform
swift build -Xswiftc -target -Xswiftc x86_64-apple-macosx12
```

### Build Artifacts

```
.build/
├─ debug/
│   ├─ libAgentFishTank.a      # Static library
│   └─ [dependencies]
└─ release/
    ├─ libAgentFishTank.a
    └─ [dependencies]
```

---

## TYPESCRIPT/VITE BUILD (ide/desktop/)

### Configuration: ide/desktop/package.json

```json
{
  "name": "sovereign-ide",
  "version": "1.0.0",
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "electron": "electron .",
    "start": "npm run build && npm run electron"
  },
  "dependencies": {
    "vue": "^3.3.0",
    "axios": "^1.4.0"
  },
  "devDependencies": {
    "vite": "^4.0.0",
    "@vitejs/plugin-vue": "^4.0.0",
    "typescript": "^5.0.0",
    "electron": "^20.0.0"
  }
}
```

### Build Commands

```bash
cd ide/desktop/

# Install dependencies
npm install

# Development server (hot reload)
npm run dev

# Production build
npm run build

# Preview production build
npm run preview

# Run Electron app
npm run electron

# Full build + launch
npm start

# Code formatting
npm run format

# Linting
npm run lint
```

### Build Artifacts

```
ide/desktop/dist/
├─ index.html
├─ index.js                # Bundled JavaScript
├─ index.css               # Bundled CSS
├─ assets/
│   ├─ main-*.js          # Code-split bundles
│   └─ style-*.css        # Code-split styles
└─ [other static assets]

node_modules/              # Installed dependencies
```

---

## BUILD ORDER AND DEPENDENCIES

### Recommended Build Sequence

```
1. Python (required for main engine)
   pip install -e .

2. Formal proofs (optional; for verification)
   lean research/formal/subleq/SUBLEQ.lean
   agda research/formal/IronicMirror/XInvariant.agda

3. Haskell (optional; compiler reference)
   cd cobalt/ && cabal build

4. Rust (optional; performance components)
   cd catn/ && cargo build --release

5. Native (optional; performance critical)
   nasm -f elf64 -o native/asm/qra.o native/asm/qra.asm

6. CUDA (optional; GPU acceleration)
   nvcc -c kernels/cuda/cuda_pipeline.cu

7. C/C++ IDE (optional; Windows client)
   mkdir build && cd build && cmake .. && cmake --build .

8. Swift (optional; training visualization)
   cd training/ && swift build -c release

9. TypeScript IDE (optional; Electron workbench)
   cd ide/desktop && npm install && npm run build
```

**Note:** Python is required. All others are optional and independent.

---

## CI/CD INTEGRATION

### GitHub Actions (Example)

```yaml
name: Build

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install
        run: pip install -e .[bedrock]
      - name: Lint
        run: ruff check src/ tests/
      - name: Type check
        run: mypy src/
      - name: Test
        run: pytest tests/ -v --cov=src
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## LOCAL DEVELOPMENT SETUP

### Initial Setup

```bash
# Clone repository
git clone https://github.com/SNAPKITTYWEST/sovereign-engine-v2.git
cd sovereign-engine-v2

# Create virtual environment
python -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install in development mode
pip install -e ".[bedrock]"

# Install dev dependencies
pip install black mypy ruff pytest pytest-asyncio pytest-cov

# Verify installation
python -c "from src.routing.pipeline import RoutingPipeline; print('OK')"

# Run tests
pytest tests/ -v

# Format code
black src/ tests/

# Run linter
ruff check src/ tests/

# Start direct runner
python run.py

# Start HTTP server
uvicorn src.bridge.http_server:app --reload
```

### Development Workflow

```
1. Edit Python files (src/)
2. Run black to format
3. Run mypy for type checking
4. Run ruff for linting
5. Run pytest for testing
6. Commit changes
7. Push to GitHub
```

---

## TROUBLESHOOTING

### Issue: ImportError: No module named 'src'

**Solution:**
```bash
pip install -e .  # (re)install in editable mode
```

### Issue: ModuleNotFoundError: No module named 'torch'

**Solution:**
```bash
pip install ".[pytorch]"  # Install with PyTorch optional dependency
```

### Issue: boto3 credential error

**Solution:**
```bash
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
# Or: aws configure
```

### Issue: Cabal build fails

**Solution:**
```bash
cd cobalt/
cabal update
cabal install --dependencies-only
cabal build
```

### Issue: Rust compilation error (linking)

**Solution:**
```bash
cd catn/
cargo clean
cargo build --release
# Or: cargo build --verbose (for more details)
```

---

## RELEASE PROCEDURE

### Python Package Release

```bash
# Increment version in pyproject.toml
# Update CHANGELOG.md

# Build artifacts
python -m build

# Upload to PyPI (test first)
python -m twine upload --repository testpypi dist/*

# Verify
pip install --index-url https://test.pypi.org/simple/ sovereign-engine

# Upload to production
python -m twine upload dist/*

# Tag release
git tag -a v2.0.0 -m "Release 2.0.0"
git push origin v2.0.0
```

### GitHub Release

```bash
# Create GitHub release
gh release create v2.0.0 dist/* --title "Sovereign Engine v2.0.0"
```

---

## PERFORMANCE OPTIMIZATION

### Python Build

```python
# Use PyPy for 2-3x speedup (if compatible)
pypy -m pip install -e .

# Profile with cProfile
python -m cProfile -s cumtime run.py

# Use numba for hot loops
from numba import jit
```

### Haskell Build

```bash
# Enable optimization
cabal build -O2

# Profile
cabal build --enable-profiling
cabal run cobalt +RTS -p
```

### Rust Build

```bash
# Release with LTO
cargo build --release

# Profile
cargo flamegraph
```

### CUDA Build

```bash
# Optimize for target GPU
nvcc -arch=sm_80 -O3 kernels/cuda/cuda_pipeline.cu
```

---

## END OF BUILD REFERENCE

For dependency details, see DEPENDENCY_GRAPH.md.  
For language specifics, see LANGUAGE_REFERENCE.md.  
For repository map, see REPOSITORY_MAP.md.
