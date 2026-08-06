"""
Dependency Analyzer
Part of SOVEREIGN PYTHON LLM ENGINE

Analyzes dependencies between modules and builds dependency graphs.
"""

from typing import Set
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import re

from ..models.entities import DependencyEdge, DependencyGraph as DependencyGraphEntity
from .ast_analyzer import PythonASTAnalyzer


class DependencyType(Enum):
    """Types of dependencies"""
    IMPORT = "import"
    FROM_IMPORT = "from_import"
    RELATIVE_IMPORT = "relative_import"
    DYNAMIC_IMPORT = "dynamic_import"


@dataclass
class ModuleNode:
    """Node in dependency graph"""
    module_path: str
    imports: Set[str] = field(default_factory=set)
    imported_by: Set[str] = field(default_factory=set)
    is_external: bool = False
    is_stdlib: bool = False


class DependencyAnalyzer:
    """
    Analyzes Python module dependencies.

    Builds dependency graphs showing:
    - What each module imports
    - What imports each module
    - Circular dependencies
    - External vs internal dependencies
    """

    STDLIB_MODULES = {
        "os", "sys", "re", "json", "math", "datetime", "pathlib",
        "asyncio", "typing", "dataclasses", "enum", "abc", "collections",
        "functools", "itertools", "operator", "io", "tempfile", "shutil",
        "subprocess", "threading", "multiprocessing", "logging", "unittest",
        "http", "urllib", "email", "html", "xml", "csv", "sqlite3",
        "hashlib", "hmac", "secrets", "random", "time", "calendar",
        "contextlib", "copy", "pickle", "struct", "array", "heapq",
        "bisect", "queue", "weakref", "gc", "inspect", "ast", "dis",
        "importlib", "pkgutil", "zipfile", "tarfile", "gzip", "bz2",
        "socket", "ssl", "select", "signal", "errno", "platform",
    }

    def __init__(self, project_root: Path):
        """
        Initialize dependency analyzer.

        Args:
            project_root: Root directory of project
        """
        self.project_root = project_root
        self.ast_analyzer = PythonASTAnalyzer()
        self.modules: dict[str, ModuleNode] = {}

    def analyze_directory(self, directory: Path | None = None) -> DependencyGraphEntity:
        """
        Analyze all Python files in directory.

        Args:
            directory: Directory to analyze (defaults to project_root)

        Returns:
            DependencyGraph with all relationships
        """
        if directory is None:
            directory = self.project_root

        # Find all Python files
        python_files = list(directory.rglob("*.py"))

        # Analyze each file
        for file_path in python_files:
            self._analyze_file(file_path)

        # Build graph entity
        edges = []
        for module_path, node in self.modules.items():
            for imported in node.imports:
                edges.append(DependencyEdge(
                    source=module_path,
                    target=imported,
                    dependency_type="import"
                ))

        return DependencyGraphEntity(
            nodes=list(self.modules.keys()),
            edges=edges
        )

    def _analyze_file(self, file_path: Path) -> None:
        """Analyze single Python file"""
        # Get module path relative to project root
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            # File outside project root
            return

        module_path = self._path_to_module(rel_path)

        # Create or get module node
        if module_path not in self.modules:
            self.modules[module_path] = ModuleNode(module_path=module_path)

        node = self.modules[module_path]

        # Parse AST
        file_info = self.ast_analyzer.analyze_file(file_path)

        # Extract imports
        for import_name in file_info.imports:
            # Resolve import
            resolved = self._resolve_import(import_name, module_path)

            # Add to graph
            node.imports.add(resolved)

            # Create target node if doesn't exist
            if resolved not in self.modules:
                is_external = not self._is_internal_module(resolved)
                is_stdlib = resolved.split(".")[0] in self.STDLIB_MODULES

                self.modules[resolved] = ModuleNode(
                    module_path=resolved,
                    is_external=is_external,
                    is_stdlib=is_stdlib
                )

            # Add reverse link
            self.modules[resolved].imported_by.add(module_path)

    def _path_to_module(self, path: Path) -> str:
        """Convert file path to module path"""
        # Remove .py extension
        parts = list(path.parts)
        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]

        # Remove __init__
        if parts[-1] == "__init__":
            parts = parts[:-1]

        return ".".join(parts)

    def _resolve_import(self, import_name: str, current_module: str) -> str:
        """Resolve import to canonical module path"""
        # Handle relative imports
        if import_name.startswith("."):
            # Get parent module
            parts = current_module.split(".")
            level = len(import_name) - len(import_name.lstrip("."))

            if level > len(parts):
                # Invalid relative import
                return import_name

            parent_parts = parts[:-level] if level > 0 else parts
            rest = import_name.lstrip(".")

            if rest:
                return ".".join(parent_parts + [rest])
            else:
                return ".".join(parent_parts)

        return import_name

    def _is_internal_module(self, module: str) -> bool:
        """Check if module is internal to project"""
        # Check if any file in project matches this module
        module_file = self.project_root / module.replace(".", "/")

        return (
            (module_file.with_suffix(".py")).exists() or
            (module_file / "__init__.py").exists()
        )

    def find_circular_dependencies(self) -> list[list[str]]:
        """
        Find circular dependencies.

        Returns:
            List of cycles (each cycle is list of module names)
        """
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(module: str, path: list[str]) -> None:
            visited.add(module)
            rec_stack.add(module)
            path.append(module)

            node = self.modules.get(module)
            if node:
                for imported in node.imports:
                    if imported not in visited:
                        dfs(imported, path.copy())
                    elif imported in rec_stack:
                        # Found cycle
                        cycle_start = path.index(imported)
                        cycle = path[cycle_start:] + [imported]
                        cycles.append(cycle)

            rec_stack.remove(module)

        for module in self.modules:
            if module not in visited:
                dfs(module, [])

        return cycles

    def get_external_dependencies(self) -> Set[str]:
        """Get all external (non-project) dependencies"""
        external = set()

        for module, node in self.modules.items():
            if node.is_external and not node.is_stdlib:
                external.add(module.split(".")[0])  # Top-level package

        return external

    def get_module_dependents(self, module: str) -> Set[str]:
        """
        Get all modules that depend on given module.

        Args:
            module: Module to check

        Returns:
            Set of dependent modules
        """
        node = self.modules.get(module)
        if not node:
            return set()

        return node.imported_by.copy()

    def get_module_dependencies(self, module: str) -> Set[str]:
        """
        Get all modules that given module depends on.

        Args:
            module: Module to check

        Returns:
            Set of dependencies
        """
        node = self.modules.get(module)
        if not node:
            return set()

        return node.imports.copy()

    def calculate_coupling(self, module: str) -> dict[str, int]:
        """
        Calculate coupling metrics for module.

        Args:
            module: Module to analyze

        Returns:
            Dictionary with metrics:
            - afferent: Number of modules that depend on this
            - efferent: Number of modules this depends on
            - instability: Efferent / (Afferent + Efferent)
        """
        node = self.modules.get(module)
        if not node:
            return {"afferent": 0, "efferent": 0, "instability": 0.0}

        afferent = len(node.imported_by)
        efferent = len(node.imports)
        total = afferent + efferent

        instability = efferent / total if total > 0 else 0.0

        return {
            "afferent": afferent,
            "efferent": efferent,
            "instability": instability
        }

    def generate_dot_graph(self) -> str:
        """
        Generate DOT graph representation.

        Returns:
            DOT format string for visualization
        """
        lines = ["digraph Dependencies {"]
        lines.append("  rankdir=LR;")
        lines.append('  node [shape=box];')

        # Add nodes
        for module, node in self.modules.items():
            if node.is_stdlib:
                color = "lightblue"
            elif node.is_external:
                color = "lightgray"
            else:
                color = "lightgreen"

            lines.append(f'  "{module}" [fillcolor={color}, style=filled];')

        # Add edges
        for module, node in self.modules.items():
            for imported in node.imports:
                lines.append(f'  "{module}" -> "{imported}";')

        lines.append("}")
        return "\n".join(lines)


class DependencyGraph:
    """
    Wrapper around DependencyAnalyzer with convenience methods.
    """

    def __init__(self, project_root: Path):
        self.analyzer = DependencyAnalyzer(project_root)
        self.graph: DependencyGraphEntity | None = None

    def build(self, directory: Path | None = None) -> None:
        """Build dependency graph"""
        self.graph = self.analyzer.analyze_directory(directory)

    def get_orphaned_modules(self) -> list[str]:
        """
        Get modules with no imports and not imported by anyone.

        Returns:
            List of orphaned module names
        """
        orphaned = []

        for module, node in self.analyzer.modules.items():
            if not node.imports and not node.imported_by:
                if not node.is_external:
                    orphaned.append(module)

        return orphaned

    def get_most_depended_on(self, limit: int = 10) -> list[tuple[str, int]]:
        """
        Get most depended-on modules.

        Args:
            limit: Number of results

        Returns:
            List of (module, dependent_count) tuples
        """
        modules_with_counts = [
            (module, len(node.imported_by))
            for module, node in self.analyzer.modules.items()
            if not node.is_external
        ]

        return sorted(modules_with_counts, key=lambda x: x[1], reverse=True)[:limit]

    def get_most_dependent(self, limit: int = 10) -> list[tuple[str, int]]:
        """
        Get modules with most dependencies.

        Args:
            limit: Number of results

        Returns:
            List of (module, dependency_count) tuples
        """
        modules_with_counts = [
            (module, len(node.imports))
            for module, node in self.analyzer.modules.items()
            if not node.is_external
        ]

        return sorted(modules_with_counts, key=lambda x: x[1], reverse=True)[:limit]

    def export_json(self) -> dict:
        """Export graph as JSON"""
        if not self.graph:
            return {}

        return {
            "nodes": [
                {
                    "id": module,
                    "is_external": node.is_external,
                    "is_stdlib": node.is_stdlib,
                    "imports_count": len(node.imports),
                    "imported_by_count": len(node.imported_by),
                }
                for module, node in self.analyzer.modules.items()
            ],
            "edges": [
                {"source": edge.source, "target": edge.target}
                for edge in self.graph.edges
            ]
        }
