#!/bin/bash
# =============================================================================
# build.sh — Build sovereign assembly runtime
# Usage: ./build.sh [clean|objects|link|all]
# Requires: nasm (>= 2.14), ld (binutils), Linux x86-64
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Build flags
NASM_FLAGS="-f elf64 -g -F dwarf -w+all"
LD_FLAGS="-m elf_x86_64"

# Source files in link order (sovereign_runtime must be first for _start)
ASM_SOURCES=(
    "sovereign_runtime.asm"
    "qra_tensor.asm"
    "ipc_dispatcher.asm"
    "nand_kernel.asm"
    "jordan_blocks.asm"
    "entropy_gate.asm"
    "sovereign_link.asm"
)

OUTPUT_BIN="sovereign_runtime"

# ─── Functions ───────────────────────────────────────────────────────────────

clean() {
    echo "[clean] Removing object files and binary..."
    rm -f ./*.o "$OUTPUT_BIN"
    echo "[clean] Done."
}

build_objects() {
    echo "[build] Assembling NASM sources..."
    for src in "${ASM_SOURCES[@]}"; do
        if [[ ! -f "$src" ]]; then
            echo "  [SKIP] $src not found"
            continue
        fi
        obj="${src%.asm}.o"
        echo "  [NASM] $src -> $obj"
        nasm $NASM_FLAGS -o "$obj" "$src"
        echo "  [OK]   $obj ($(stat -c%s "$obj") bytes)"
    done
}

link_binary() {
    echo "[link] Linking object files -> $OUTPUT_BIN ..."
    OBJECTS=()
    for src in "${ASM_SOURCES[@]}"; do
        obj="${src%.asm}.o"
        if [[ -f "$obj" ]]; then
            OBJECTS+=("$obj")
        fi
    done
    if [[ ${#OBJECTS[@]} -eq 0 ]]; then
        echo "[ERROR] No object files found. Run: $0 objects"
        exit 1
    fi
    ld $LD_FLAGS -o "$OUTPUT_BIN" "${OBJECTS[@]}"
    echo "[link] Done: $OUTPUT_BIN ($(stat -c%s "$OUTPUT_BIN") bytes)"
}

show_symbols() {
    if [[ -f "$OUTPUT_BIN" ]]; then
        echo "[symbols] Public API symbols in $OUTPUT_BIN:"
        nm "$OUTPUT_BIN" | grep ' T ' | sort -k3 | head -60
    fi
}

count_lines() {
    echo "[stats] Line counts:"
    total=0
    for src in "${ASM_SOURCES[@]}"; do
        if [[ -f "$src" ]]; then
            lc=$(wc -l < "$src")
            total=$((total + lc))
            printf "  %6d  %s\n" "$lc" "$src"
        fi
    done
    printf "  %6d  TOTAL\n" "$total"
}

# ─── Main ────────────────────────────────────────────────────────────────────

CMD="${1:-all}"

case "$CMD" in
    clean)
        clean
        ;;
    objects)
        build_objects
        ;;
    link)
        link_binary
        ;;
    symbols)
        show_symbols
        ;;
    lines)
        count_lines
        ;;
    all)
        count_lines
        build_objects
        link_binary
        show_symbols
        echo ""
        echo "=== BUILD COMPLETE ==="
        echo "Binary: $SCRIPT_DIR/$OUTPUT_BIN"
        ;;
    *)
        echo "Usage: $0 [clean|objects|link|symbols|lines|all]"
        exit 1
        ;;
esac
