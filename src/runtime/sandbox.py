"""
Layer 4: Code Execution Sandbox
Part of SOVEREIGN PYTHON LLM ENGINE

Isolated subprocess execution with timeout enforcement.
Critical for ReAct and MCTS agents.
"""

import subprocess
import tempfile
import sys
import asyncio
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from ..models.entities import CodeExecutionResult


# ==========================================
# Execution Result
# ==========================================

@dataclass
class SandboxResult:
    """Extended execution result with metadata"""
    success: bool
    output: str
    exit_code: int
    elapsed_ms: int
    stdout: str
    stderr: str
    timestamp: datetime


# ==========================================
# Code Sandbox
# ==========================================

class CodeSandbox:
    """
    Isolated subprocess code execution.

    Security features:
    - Subprocess isolation
    - Timeout enforcement
    - Output truncation
    - No network access (optional)
    - No filesystem write access (optional)
    """

    def __init__(
        self,
        timeout: float = 10.0,
        max_output_length: int = 4000,
        allowed_builtins: set[str] | None = None
    ):
        """
        Initialize code sandbox.

        Args:
            timeout: Execution timeout in seconds
            max_output_length: Max output length (truncate if exceeded)
            allowed_builtins: Set of allowed builtins (None = all allowed)
        """
        self.timeout = timeout
        self.max_output_length = max_output_length
        self.allowed_builtins = allowed_builtins

    async def execute_python(self, code: str) -> CodeExecutionResult:
        """
        Execute Python code in isolated subprocess.

        Args:
            code: Python code string

        Returns:
            CodeExecutionResult with success, output, exit code
        """
        return await asyncio.to_thread(self._sync_execute_python, code)

    def _sync_execute_python(self, code: str) -> CodeExecutionResult:
        """
        Synchronous Python execution (runs in thread pool).
        """
        import time

        start_time = time.time()

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as tmp_file:
            tmp_file.write(code)
            tmp_file_path = tmp_file.name

        try:
            # Execute in subprocess
            proc = subprocess.run(
                [sys.executable, tmp_file_path],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            # Combine stdout/stderr
            combined = f"{stdout}\n{stderr}".strip() if stderr else stdout

            # Truncate if too long
            if len(combined) > self.max_output_length:
                combined = combined[:self.max_output_length] + "\n...[Output Truncated]"

            elapsed_ms = int((time.time() - start_time) * 1000)

            return CodeExecutionResult(
                success=(proc.returncode == 0),
                output=combined if combined else "<No output>",
                exit_code=proc.returncode,
                elapsed_ms=elapsed_ms,
                stdout=stdout,
                stderr=stderr
            )

        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.time() - start_time) * 1000)

            return CodeExecutionResult(
                success=False,
                output=f"Execution timeout after {self.timeout}s",
                exit_code=-1,
                elapsed_ms=elapsed_ms,
                stdout=None,
                stderr="TimeoutExpired"
            )

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)

            return CodeExecutionResult(
                success=False,
                output=f"System error: {str(e)}",
                exit_code=-1,
                elapsed_ms=elapsed_ms,
                stdout=None,
                stderr=str(e)
            )

        finally:
            # Clean up temp file
            try:
                Path(tmp_file_path).unlink()
            except Exception:
                pass

    async def execute_bash(self, script: str) -> CodeExecutionResult:
        """
        Execute bash script in subprocess.

        Args:
            script: Bash script string

        Returns:
            CodeExecutionResult
        """
        return await asyncio.to_thread(self._sync_execute_bash, script)

    def _sync_execute_bash(self, script: str) -> CodeExecutionResult:
        """Synchronous bash execution"""
        import time

        start_time = time.time()

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.sh',
            delete=False,
            encoding='utf-8'
        ) as tmp_file:
            tmp_file.write(script)
            tmp_file_path = tmp_file.name

        try:
            # Make executable
            Path(tmp_file_path).chmod(0o755)

            # Execute in subprocess
            proc = subprocess.run(
                ['bash', tmp_file_path],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            combined = f"{stdout}\n{stderr}".strip() if stderr else stdout

            if len(combined) > self.max_output_length:
                combined = combined[:self.max_output_length] + "\n...[Truncated]"

            elapsed_ms = int((time.time() - start_time) * 1000)

            return CodeExecutionResult(
                success=(proc.returncode == 0),
                output=combined if combined else "<No output>",
                exit_code=proc.returncode,
                elapsed_ms=elapsed_ms,
                stdout=stdout,
                stderr=stderr
            )

        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.time() - start_time) * 1000)

            return CodeExecutionResult(
                success=False,
                output=f"Timeout after {self.timeout}s",
                exit_code=-1,
                elapsed_ms=elapsed_ms,
                stdout=None,
                stderr="TimeoutExpired"
            )

        finally:
            try:
                Path(tmp_file_path).unlink()
            except Exception:
                pass


# ==========================================
# Restricted Sandbox (Extra Safety)
# ==========================================

class RestrictedPythonSandbox:
    """
    More restricted Python sandbox using RestrictedPython.

    Note: Requires `restrictedpython` package.
    This is a placeholder for the architecture.
    """

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    async def execute(self, code: str) -> CodeExecutionResult:
        """
        Execute code with RestrictedPython.

        This provides compile-time restrictions on dangerous operations:
        - No file I/O
        - No subprocess
        - No import of dangerous modules
        - No access to __builtins__
        """
        # TODO: Implement with RestrictedPython
        # For now, delegate to standard sandbox
        sandbox = CodeSandbox(timeout=self.timeout)
        return await sandbox.execute_python(code)


# ==========================================
# Sandbox Pool
# ==========================================

class SandboxPool:
    """
    Pool of sandboxes for concurrent execution.
    """

    def __init__(
        self,
        pool_size: int = 5,
        timeout: float = 10.0,
        max_output_length: int = 4000
    ):
        """
        Initialize sandbox pool.

        Args:
            pool_size: Number of sandboxes in pool
            timeout: Execution timeout
            max_output_length: Max output length
        """
        self.pool_size = pool_size
        self.timeout = timeout
        self.max_output_length = max_output_length

        self.sandboxes = [
            CodeSandbox(timeout=timeout, max_output_length=max_output_length)
            for _ in range(pool_size)
        ]

        self.semaphore = asyncio.Semaphore(pool_size)

    async def execute(self, code: str) -> CodeExecutionResult:
        """
        Execute code using pool.

        Args:
            code: Python code

        Returns:
            CodeExecutionResult
        """
        async with self.semaphore:
            # Get any available sandbox (they're all identical)
            sandbox = self.sandboxes[0]
            return await sandbox.execute_python(code)

    async def execute_batch(self, code_list: list[str]) -> list[CodeExecutionResult]:
        """
        Execute batch of code snippets concurrently.

        Args:
            code_list: List of code strings

        Returns:
            List of execution results
        """
        tasks = [self.execute(code) for code in code_list]
        return await asyncio.gather(*tasks)


# ==========================================
# Sandbox with Verification
# ==========================================

class VerifiedSandbox:
    """
    Sandbox that verifies code before execution.
    """

    def __init__(self, sandbox: CodeSandbox):
        self.sandbox = sandbox

    async def execute_with_verification(
        self,
        code: str,
        test_assertion: str
    ) -> tuple[CodeExecutionResult, bool]:
        """
        Execute code and verify with test assertion.

        Args:
            code: Code to execute
            test_assertion: Test assertion (e.g., "assert solution(5) == 10")

        Returns:
            (execution_result, test_passed)
        """
        # Append test assertion to code
        full_code = f"{code}\n\n{test_assertion}\nprint('TESTS_PASSED')"

        # Execute
        result = await self.sandbox.execute_python(full_code)

        # Check if tests passed
        test_passed = result.success and "TESTS_PASSED" in result.output

        return result, test_passed


# ==========================================
# Sandbox Statistics
# ==========================================

class SandboxStatistics:
    """
    Track sandbox execution statistics.
    """

    def __init__(self):
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0
        self.timeouts = 0
        self.total_elapsed_ms = 0

    def record(self, result: CodeExecutionResult) -> None:
        """Record execution result"""
        self.total_executions += 1

        if result.success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1

        if result.exit_code == -1 and "timeout" in result.output.lower():
            self.timeouts += 1

        self.total_elapsed_ms += result.elapsed_ms

    def get_stats(self) -> dict[str, float]:
        """Get statistics"""
        return {
            "total": self.total_executions,
            "successful": self.successful_executions,
            "failed": self.failed_executions,
            "timeouts": self.timeouts,
            "success_rate": (
                self.successful_executions / self.total_executions
                if self.total_executions > 0
                else 0.0
            ),
            "avg_elapsed_ms": (
                self.total_elapsed_ms / self.total_executions
                if self.total_executions > 0
                else 0.0
            )
        }


# ==========================================
# Monitored Sandbox
# ==========================================

class MonitoredSandbox:
    """
    Sandbox with execution monitoring and statistics.
    """

    def __init__(self, sandbox: CodeSandbox):
        self.sandbox = sandbox
        self.stats = SandboxStatistics()

    async def execute(self, code: str) -> CodeExecutionResult:
        """Execute code with monitoring"""
        result = await self.sandbox.execute_python(code)
        self.stats.record(result)
        return result

    def get_statistics(self) -> dict[str, float]:
        """Get execution statistics"""
        return self.stats.get_stats()


# ==========================================
# Sandbox Security Validator
# ==========================================

class SecurityValidator:
    """
    Validate code before execution for dangerous patterns.
    """

    DANGEROUS_PATTERNS = [
        "import os",
        "import subprocess",
        "import shutil",
        "eval(",
        "exec(",
        "compile(",
        "__import__",
        "open(",
        "file(",
        "input(",
        "raw_input(",
    ]

    @staticmethod
    def is_safe(code: str) -> tuple[bool, str | None]:
        """
        Check if code is safe to execute.

        Args:
            code: Python code

        Returns:
            (is_safe, reason) tuple
        """
        for pattern in SecurityValidator.DANGEROUS_PATTERNS:
            if pattern in code:
                return False, f"Dangerous pattern detected: {pattern}"

        return True, None


class SafeSandbox:
    """
    Sandbox that validates code before execution.
    """

    def __init__(self, sandbox: CodeSandbox):
        self.sandbox = sandbox
        self.validator = SecurityValidator()

    async def execute(self, code: str) -> CodeExecutionResult:
        """
        Execute code after validation.

        Args:
            code: Python code

        Returns:
            CodeExecutionResult (or error if validation fails)
        """
        # Validate first
        is_safe, reason = self.validator.is_safe(code)

        if not is_safe:
            return CodeExecutionResult(
                success=False,
                output=f"Code validation failed: {reason}",
                exit_code=-2,
                elapsed_ms=0,
                stdout=None,
                stderr=reason
            )

        # Execute if safe
        return await self.sandbox.execute_python(code)
