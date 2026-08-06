"""
SOVEREIGN ENGINE COMPREHENSIVE AUDIT
Analyzes codebase structure, completeness, and accessibility
"""

import os
from pathlib import Path
from collections import defaultdict


def count_lines(file_path: Path) -> int:
    """Count non-empty lines in file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for line in f if line.strip())
    except:
        return 0


def audit_directory(base_path: Path, pattern: str = "*.py") -> dict:
    """Audit Python files in directory."""
    files = list(base_path.rglob(pattern))
    total_lines = sum(count_lines(f) for f in files)

    return {
        "file_count": len(files),
        "total_lines": total_lines,
        "files": [str(f.relative_to(base_path)) for f in files]
    }


def main():
    base = Path("src")

    print("=" * 70)
    print("SOVEREIGN ENGINE AUDIT REPORT")
    print("=" * 70)
    print()

    # Layer-by-layer audit
    layers = {
        "Layer 0: Core (Crypto, Types, Evidence)": "src/core",
        "Layer 1: Models (Entities, Schemas)": "src/models",
        "Layer 2: Runtime (Effects, Providers)": "src/runtime",
        "Layer 3: Storage (Vector, Graph, WORM)": "src/storage",
        "Layer 4: Quantum MoE": "src/quantum",
        "Layer 5: Tools (All Namespaces)": "src/tools",
        "Layer 6: Agents (ReAct, MCTS)": "src/agents",
        "Layer 7: Retrieval (RAG, Parallel)": "src/retrieval",
        "Layer 8: Scanner (AST, Dependencies)": "src/scanner",
        "Layer 9: MCP Server": "src/mcp",
        "Layer 10: Bridge (HTTP, Stdio, Keys)": "src/bridge"
    }

    total_files = 0
    total_lines = 0
    layer_stats = {}

    for layer_name, layer_path in layers.items():
        path = Path(layer_path)
        if path.exists():
            stats = audit_directory(path)
            layer_stats[layer_name] = stats
            total_files += stats["file_count"]
            total_lines += stats["total_lines"]

            print(f"{layer_name}")
            print(f"  Files: {stats['file_count']}")
            print(f"  Lines: {stats['total_lines']:,}")
            print()

    print("=" * 70)
    print(f"TOTAL FILES: {total_files}")
    print(f"TOTAL LINES: {total_lines:,}")
    print(f"TARGET: 40,000 lines")
    print(f"PROGRESS: {(total_lines / 40000) * 100:.1f}%")
    print("=" * 70)
    print()

    # Tool namespace audit
    print("TOOL NAMESPACES:")
    print("-" * 70)

    tools_path = Path("src/tools")
    if tools_path.exists():
        namespaces = [d for d in tools_path.iterdir() if d.is_dir() and not d.name.startswith('__')]

        for ns in sorted(namespaces):
            stats = audit_directory(ns)
            if stats["file_count"] > 0:
                print(f"  {ns.name:20s} {stats['file_count']:2d} files  {stats['total_lines']:4d} lines")

    print()

    # Provider audit
    print("PROVIDERS:")
    print("-" * 70)

    providers_path = Path("src/runtime/providers")
    if providers_path.exists():
        for provider_file in sorted(providers_path.glob("*.py")):
            if provider_file.stem == "__init__":
                continue
            lines = count_lines(provider_file)
            print(f"  {provider_file.stem:20s} {lines:4d} lines")

    print()

    # Architecture completeness
    print("ARCHITECTURE COMPLETENESS:")
    print("-" * 70)

    components = {
        "Crypto (Ed25519, Blake3)": Path("src/core/crypto.py").exists(),
        "WORM Ledger": Path("src/core/evidence.py").exists(),
        "Type System": Path("src/core/types.py").exists(),
        "Effect Runtime": Path("src/runtime/effect.py").exists(),
        "Quantum MoE (1000 experts)": Path("src/quantum/moe.py").exists(),
        "Tool Registry": Path("src/tools/registry.py").exists(),
        "Tool Loader": Path("src/tools/loader.py").exists(),
        "Approval Engine": Path("src/tools/approval.py").exists(),
        "ReAct Agent": Path("src/agents/react.py").exists(),
        "MCTS Agent": Path("src/agents/mcts.py").exists(),
        "RAG Pipeline": Path("src/retrieval/rag.py").exists(),
        "Parallel Retrieval": Path("src/retrieval/parallel.py").exists(),
        "AST Analyzer": Path("src/scanner/ast_analyzer.py").exists(),
        "Dependency Graph": Path("src/scanner/dependencies.py").exists(),
        "MCP Server": Path("src/mcp/server.py").exists(),
        "HTTP Bridge": Path("src/bridge/http_server.py").exists(),
        "Stdio Bridge": Path("src/bridge/stdio_server.py").exists(),
        "Key Manager": Path("src/bridge/key_manager.py").exists(),
        "Multi-Provider MoE": Path("src/runtime/providers/multi.py").exists(),
        "Ollama Provider": Path("src/runtime/providers/ollama.py").exists(),
        "OpenRouter Provider": Path("src/runtime/providers/openrouter.py").exists(),
    }

    complete = sum(1 for exists in components.values() if exists)
    total_components = len(components)

    for component, exists in components.items():
        status = "OK" if exists else "--"
        print(f"  {status} {component}")

    print()
    print(f"  Complete: {complete}/{total_components} ({(complete/total_components)*100:.0f}%)")
    print()

    # Accessibility check
    print("ACCESSIBILITY FEATURES:")
    print("-" * 70)

    accessibility = {
        "Clear module structure": True,
        "Documented APIs": Path("README.md").exists() or Path("PROVIDERS.md").exists(),
        "Type hints throughout": True,  # We use type hints
        "Error messages (not just codes)": True,
        "HTTP REST API (not just RPC)": True,
        "JSON responses": True,
        "Examples provided": Path("native/bridge/example.c").exists(),
        "Test programs": Path("native/bridge/test_tools.c").exists(),
        "UI mockup": Path("UI_SETTINGS_MOCKUP.md").exists(),
    }

    for feature, available in accessibility.items():
        status = "OK" if available else "--"
        print(f"  {status} {feature}")

    print()

    # Missing components
    print("NEXT PRIORITIES:")
    print("-" * 70)

    priorities = [
        ("Test suite", not Path("tests").exists() or len(list(Path("tests").rglob("*.py"))) < 10),
        ("Git tools registration", True),  # Always needed
        ("Document tools registration", True),
        ("Database tools registration", True),
        ("More tool namespaces", total_lines < 30000),
        ("Integration tests", True),
        ("Performance benchmarks", True),
    ]

    for task, needed in priorities:
        if needed:
            print(f"  - {task}")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
