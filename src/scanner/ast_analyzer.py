"""
Python AST Analyzer
Part of SOVEREIGN PYTHON LLM ENGINE

Analyzes Python code using AST to extract symbols, functions, classes, imports.
"""

import ast
from typing import Any
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

from ..models.entities import SymbolInfo, FileInfo


class SymbolType(Enum):
    """Types of symbols"""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"
    CONSTANT = "constant"


@dataclass
class FunctionSignature:
    """Function signature information"""
    name: str
    args: list[str]
    returns: str | None
    decorators: list[str]
    is_async: bool
    docstring: str | None
    line_start: int
    line_end: int


@dataclass
class ClassDefinition:
    """Class definition information"""
    name: str
    bases: list[str]
    methods: list[str]
    attributes: list[str]
    decorators: list[str]
    docstring: str | None
    line_start: int
    line_end: int


@dataclass
class ImportStatement:
    """Import statement information"""
    module: str
    names: list[str]
    is_from_import: bool
    line: int


class PythonASTAnalyzer:
    """
    Analyzes Python code using AST.

    Extracts:
    - Functions and their signatures
    - Classes and their methods
    - Imports
    - Variables and constants
    - Docstrings
    - Call graphs
    """

    def __init__(self):
        self.tree: ast.AST | None = None
        self.source: str = ""
        self.file_path: Path | None = None

    def analyze_file(self, file_path: Path) -> FileInfo:
        """
        Analyze Python file.

        Args:
            file_path: Path to Python file

        Returns:
            FileInfo with all extracted information
        """
        self.file_path = file_path
        self.source = file_path.read_text(encoding="utf-8")

        return self.analyze_source(self.source, str(file_path))

    def analyze_source(self, source: str, file_path: str = "<source>") -> FileInfo:
        """
        Analyze Python source code.

        Args:
            source: Python source code
            file_path: Path for identification

        Returns:
            FileInfo with extracted information
        """
        self.source = source
        self.file_path = Path(file_path)

        try:
            self.tree = ast.parse(source)
        except SyntaxError as e:
            # Return FileInfo with error
            return FileInfo(
                file_path=file_path,
                language="python",
                symbols=[],
                imports=[],
                errors=[f"Syntax error at line {e.lineno}: {e.msg}"]
            )

        # Extract all information
        functions = self._extract_functions()
        classes = self._extract_classes()
        imports = self._extract_imports()
        constants = self._extract_constants()

        # Convert to SymbolInfo
        symbols = []

        for func in functions:
            symbols.append(SymbolInfo(
                name=func.name,
                kind="function",
                line=func.line_start,
                column=0,
                signature=self._format_function_signature(func),
                docstring=func.docstring
            ))

        for cls in classes:
            symbols.append(SymbolInfo(
                name=cls.name,
                kind="class",
                line=cls.line_start,
                column=0,
                signature=f"class {cls.name}({', '.join(cls.bases)})",
                docstring=cls.docstring
            ))

        return FileInfo(
            file_path=file_path,
            language="python",
            symbols=symbols,
            imports=[imp.module for imp in imports],
            errors=[]
        )

    def _extract_functions(self) -> list[FunctionSignature]:
        """Extract all function definitions"""
        functions = []

        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                func = self._parse_function(node)
                functions.append(func)

        return functions

    def _extract_classes(self) -> list[ClassDefinition]:
        """Extract all class definitions"""
        classes = []

        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                cls = self._parse_class(node)
                classes.append(cls)

        return classes

    def _extract_imports(self) -> list[ImportStatement]:
        """Extract all import statements"""
        imports = []

        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportStatement(
                        module=alias.name,
                        names=[alias.asname or alias.name],
                        is_from_import=False,
                        line=node.lineno
                    ))

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]
                imports.append(ImportStatement(
                    module=module,
                    names=names,
                    is_from_import=True,
                    line=node.lineno
                ))

        return imports

    def _extract_constants(self) -> list[tuple[str, Any]]:
        """Extract module-level constants"""
        constants = []

        if not isinstance(self.tree, ast.Module):
            return constants

        for node in self.tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        # Convention: UPPER_CASE = constant
                        if name.isupper():
                            value = self._extract_constant_value(node.value)
                            constants.append((name, value))

        return constants

    def _parse_function(self, node: ast.FunctionDef) -> FunctionSignature:
        """Parse function definition node"""
        # Extract arguments
        args = []
        for arg in node.args.args:
            args.append(arg.arg)

        # Extract return type
        returns = None
        if node.returns:
            returns = ast.unparse(node.returns)

        # Extract decorators
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)

        # Extract docstring
        docstring = ast.get_docstring(node)

        # Line numbers
        line_start = node.lineno
        line_end = node.end_lineno or line_start

        return FunctionSignature(
            name=node.name,
            args=args,
            returns=returns,
            decorators=decorators,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            docstring=docstring,
            line_start=line_start,
            line_end=line_end
        )

    def _parse_class(self, node: ast.ClassDef) -> ClassDefinition:
        """Parse class definition node"""
        # Extract base classes
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            else:
                bases.append(ast.unparse(base))

        # Extract methods
        methods = []
        attributes = []

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attributes.append(target.id)

        # Extract decorators
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)

        # Extract docstring
        docstring = ast.get_docstring(node)

        # Line numbers
        line_start = node.lineno
        line_end = node.end_lineno or line_start

        return ClassDefinition(
            name=node.name,
            bases=bases,
            methods=methods,
            attributes=attributes,
            decorators=decorators,
            docstring=docstring,
            line_start=line_start,
            line_end=line_end
        )

    def _extract_constant_value(self, node: ast.expr) -> Any:
        """Extract constant value from AST node"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.List):
            return [self._extract_constant_value(elt) for elt in node.elts]
        elif isinstance(node, ast.Dict):
            return {
                self._extract_constant_value(k): self._extract_constant_value(v)
                for k, v in zip(node.keys, node.values)
            }
        else:
            return None

    def _format_function_signature(self, func: FunctionSignature) -> str:
        """Format function signature as string"""
        args_str = ", ".join(func.args)
        returns_str = f" -> {func.returns}" if func.returns else ""
        async_str = "async " if func.is_async else ""

        return f"{async_str}def {func.name}({args_str}){returns_str}"

    def find_function_calls(self, function_name: str) -> list[int]:
        """
        Find all calls to a specific function.

        Args:
            function_name: Name of function to find

        Returns:
            List of line numbers where function is called
        """
        calls = []

        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id == function_name:
                        calls.append(node.lineno)
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr == function_name:
                        calls.append(node.lineno)

        return calls

    def find_class_usages(self, class_name: str) -> list[int]:
        """
        Find all usages of a class.

        Args:
            class_name: Name of class to find

        Returns:
            List of line numbers
        """
        usages = []

        for node in ast.walk(self.tree):
            # Class instantiation
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id == class_name:
                        usages.append(node.lineno)

            # Inheritance
            elif isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        if base.id == class_name:
                            usages.append(node.lineno)

        return usages

    def extract_complexity_metrics(self) -> dict[str, int]:
        """
        Extract code complexity metrics.

        Returns:
            Dictionary with metrics
        """
        metrics = {
            "total_lines": len(self.source.splitlines()),
            "functions": 0,
            "classes": 0,
            "imports": 0,
            "branches": 0,  # if/elif/else
            "loops": 0,  # for/while
        }

        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                metrics["functions"] += 1
            elif isinstance(node, ast.ClassDef):
                metrics["classes"] += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                metrics["imports"] += 1
            elif isinstance(node, ast.If):
                metrics["branches"] += 1
            elif isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
                metrics["loops"] += 1

        return metrics

    def generate_call_graph(self) -> dict[str, list[str]]:
        """
        Generate call graph showing function → functions_it_calls.

        Returns:
            Dictionary mapping function names to called functions
        """
        call_graph: dict[str, list[str]] = {}

        # First, extract all function definitions
        functions = self._extract_functions()
        function_names = {func.name for func in functions}

        # For each function, find what it calls
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                caller = node.name
                callees = []

                # Walk function body
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name):
                            callee = child.func.id
                            if callee in function_names:
                                callees.append(callee)

                call_graph[caller] = callees

        return call_graph
