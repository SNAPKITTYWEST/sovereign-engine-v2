"""
Layer 4: Filesystem Effects
Part of SOVEREIGN PYTHON LLM ENGINE

Explicit filesystem effect handling with async I/O.
All effects are isolated and auditable.
"""

from pathlib import Path
from typing import AsyncIterator
import aiofiles
import aiofiles.os
from datetime import datetime

from ..core.types import ValidatedPath, ValidatedDirectory, ValidatedFile
from ..core.crypto import ContentHash, hash_content


# ==========================================
# File Operations
# ==========================================

class FilesystemRuntime:
    """
    Explicit filesystem effect handler.

    All operations are async and return explicit results.
    No hidden mutations or side effects.
    """

    async def read_file(self, path: Path) -> bytes:
        """
        Read file contents.

        Args:
            path: File path

        Returns:
            File contents as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file is not readable
        """
        async with aiofiles.open(path, 'rb') as f:
            return await f.read()

    async def read_text(self, path: Path, encoding: str = 'utf-8') -> str:
        """
        Read file contents as text.

        Args:
            path: File path
            encoding: Text encoding

        Returns:
            File contents as string
        """
        async with aiofiles.open(path, 'r', encoding=encoding) as f:
            return await f.read()

    async def write_file(self, path: Path, content: bytes) -> None:
        """
        Write file contents.

        Creates parent directories if they don't exist.

        Args:
            path: File path
            content: Content to write

        Raises:
            PermissionError: If file is not writable
        """
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(path, 'wb') as f:
            await f.write(content)

    async def write_text(self, path: Path, content: str, encoding: str = 'utf-8') -> None:
        """
        Write text file.

        Args:
            path: File path
            content: Text content
            encoding: Text encoding
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(path, 'w', encoding=encoding) as f:
            await f.write(content)

    async def append_file(self, path: Path, content: bytes) -> None:
        """
        Append to file.

        Args:
            path: File path
            content: Content to append
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(path, 'ab') as f:
            await f.write(content)

    async def append_text(self, path: Path, content: str, encoding: str = 'utf-8') -> None:
        """
        Append text to file.

        Args:
            path: File path
            content: Text to append
            encoding: Text encoding
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(path, 'a', encoding=encoding) as f:
            await f.write(content)

    async def delete_file(self, path: Path) -> None:
        """
        Delete file.

        Args:
            path: File path

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        await aiofiles.os.remove(path)

    async def file_exists(self, path: Path) -> bool:
        """
        Check if file exists.

        Args:
            path: File path

        Returns:
            True if file exists
        """
        return path.exists()

    async def get_file_size(self, path: Path) -> int:
        """
        Get file size in bytes.

        Args:
            path: File path

        Returns:
            File size in bytes
        """
        stat = await aiofiles.os.stat(path)
        return stat.st_size

    async def get_file_hash(self, path: Path) -> ContentHash:
        """
        Compute file hash.

        Args:
            path: File path

        Returns:
            Blake2b content hash
        """
        content = await self.read_file(path)
        return hash_content(content)

    async def copy_file(self, source: Path, dest: Path) -> None:
        """
        Copy file from source to destination.

        Args:
            source: Source file path
            dest: Destination file path
        """
        content = await self.read_file(source)
        await self.write_file(dest, content)

    async def move_file(self, source: Path, dest: Path) -> None:
        """
        Move file from source to destination.

        Args:
            source: Source file path
            dest: Destination file path
        """
        await self.copy_file(source, dest)
        await self.delete_file(source)


# ==========================================
# Directory Operations
# ==========================================

class DirectoryRuntime:
    """Directory-specific operations"""

    async def create_directory(self, path: Path, parents: bool = True) -> None:
        """
        Create directory.

        Args:
            path: Directory path
            parents: Create parent directories if they don't exist
        """
        path.mkdir(parents=parents, exist_ok=True)

    async def delete_directory(self, path: Path, recursive: bool = False) -> None:
        """
        Delete directory.

        Args:
            path: Directory path
            recursive: Delete recursively (rmtree)

        Raises:
            OSError: If directory is not empty and recursive=False
        """
        if recursive:
            import shutil
            shutil.rmtree(path)
        else:
            path.rmdir()

    async def list_directory(self, path: Path) -> list[Path]:
        """
        List directory contents.

        Args:
            path: Directory path

        Returns:
            List of paths in directory
        """
        return list(path.iterdir())

    async def list_files(self, path: Path, pattern: str = "*") -> list[Path]:
        """
        List files matching pattern.

        Args:
            path: Directory path
            pattern: Glob pattern (e.g., "*.py")

        Returns:
            List of file paths
        """
        return [p for p in path.glob(pattern) if p.is_file()]

    async def list_directories(self, path: Path) -> list[Path]:
        """
        List subdirectories.

        Args:
            path: Directory path

        Returns:
            List of subdirectory paths
        """
        return [p for p in path.iterdir() if p.is_dir()]

    async def walk_directory(self, path: Path, pattern: str = "*") -> AsyncIterator[Path]:
        """
        Recursively walk directory.

        Args:
            path: Root directory path
            pattern: Glob pattern to match

        Yields:
            Matching file paths
        """
        for p in path.rglob(pattern):
            if p.is_file():
                yield p

    async def get_directory_size(self, path: Path) -> int:
        """
        Get total size of directory (recursive).

        Args:
            path: Directory path

        Returns:
            Total size in bytes
        """
        total = 0
        async for file_path in self.walk_directory(path):
            try:
                stat = await aiofiles.os.stat(file_path)
                total += stat.st_size
            except (FileNotFoundError, PermissionError):
                continue
        return total

    async def count_files(self, path: Path, pattern: str = "*") -> int:
        """
        Count files in directory.

        Args:
            path: Directory path
            pattern: Glob pattern

        Returns:
            Number of matching files
        """
        count = 0
        async for _ in self.walk_directory(path, pattern):
            count += 1
        return count


# ==========================================
# Path Utilities
# ==========================================

class PathUtils:
    """Path manipulation utilities"""

    @staticmethod
    def make_absolute(path: Path) -> Path:
        """Convert to absolute path"""
        return path.resolve()

    @staticmethod
    def make_relative(path: Path, base: Path) -> Path:
        """Make path relative to base"""
        return path.relative_to(base)

    @staticmethod
    def normalize_path(path: Path) -> Path:
        """Normalize path (resolve symlinks, remove ..)"""
        return path.resolve()

    @staticmethod
    def get_extension(path: Path) -> str:
        """Get file extension (including dot)"""
        return path.suffix

    @staticmethod
    def get_stem(path: Path) -> str:
        """Get filename without extension"""
        return path.stem

    @staticmethod
    def join_paths(*parts: str | Path) -> Path:
        """Join path components"""
        result = Path(parts[0])
        for part in parts[1:]:
            result = result / part
        return result

    @staticmethod
    def is_subpath(path: Path, parent: Path) -> bool:
        """Check if path is under parent directory"""
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False


# ==========================================
# Temporary File Management
# ==========================================

class TemporaryFileManager:
    """Manage temporary files with automatic cleanup"""

    def __init__(self, base_dir: Path | None = None):
        """
        Initialize temporary file manager.

        Args:
            base_dir: Base directory for temp files (None = system temp)
        """
        if base_dir is None:
            import tempfile
            self.base_dir = Path(tempfile.gettempdir())
        else:
            self.base_dir = base_dir

        self.created_files: list[Path] = []

    async def create_temp_file(self, suffix: str = "", prefix: str = "tmp") -> Path:
        """
        Create temporary file.

        Args:
            suffix: File suffix (e.g., ".py")
            prefix: File prefix

        Returns:
            Path to temporary file
        """
        import tempfile
        import asyncio

        # Create temp file in thread pool
        fd, path_str = await asyncio.to_thread(
            tempfile.mkstemp,
            suffix=suffix,
            prefix=prefix,
            dir=self.base_dir
        )

        # Close file descriptor
        import os
        os.close(fd)

        path = Path(path_str)
        self.created_files.append(path)
        return path

    async def create_temp_directory(self, prefix: str = "tmpdir") -> Path:
        """
        Create temporary directory.

        Args:
            prefix: Directory prefix

        Returns:
            Path to temporary directory
        """
        import tempfile
        import asyncio

        path_str = await asyncio.to_thread(
            tempfile.mkdtemp,
            prefix=prefix,
            dir=self.base_dir
        )

        path = Path(path_str)
        self.created_files.append(path)
        return path

    async def cleanup(self) -> None:
        """Delete all created temporary files/directories"""
        for path in self.created_files:
            try:
                if path.is_file():
                    await aiofiles.os.remove(path)
                elif path.is_dir():
                    import shutil
                    shutil.rmtree(path)
            except (FileNotFoundError, PermissionError):
                pass

        self.created_files.clear()

    async def __aenter__(self):
        """Context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (auto-cleanup)"""
        await self.cleanup()


# ==========================================
# File Watcher (Optional)
# ==========================================

class FileWatcher:
    """
    Watch file for changes.

    Simple polling-based implementation.
    For production, use watchdog library.
    """

    def __init__(self, path: Path, poll_interval: float = 1.0):
        """
        Initialize file watcher.

        Args:
            path: File to watch
            poll_interval: Polling interval in seconds
        """
        self.path = path
        self.poll_interval = poll_interval
        self._last_mtime: float | None = None

    async def has_changed(self) -> bool:
        """
        Check if file has changed since last check.

        Returns:
            True if file was modified
        """
        try:
            stat = await aiofiles.os.stat(self.path)
            current_mtime = stat.st_mtime

            if self._last_mtime is None:
                self._last_mtime = current_mtime
                return False

            changed = current_mtime > self._last_mtime
            if changed:
                self._last_mtime = current_mtime

            return changed
        except FileNotFoundError:
            return False

    async def watch_for_changes(self) -> AsyncIterator[datetime]:
        """
        Watch for file changes continuously.

        Yields:
            Timestamp when change was detected
        """
        import asyncio

        while True:
            if await self.has_changed():
                yield datetime.now()

            await asyncio.sleep(self.poll_interval)


# ==========================================
# Safe File Operations
# ==========================================

class SafeFileOperations:
    """
    Safe file operations with automatic backup.
    """

    def __init__(self, fs: FilesystemRuntime):
        self.fs = fs

    async def safe_write(self, path: Path, content: bytes, backup: bool = True) -> None:
        """
        Write file with optional backup.

        Args:
            path: File path
            content: Content to write
            backup: Create .bak backup if file exists
        """
        # Create backup if file exists
        if backup and path.exists():
            backup_path = path.with_suffix(path.suffix + '.bak')
            await self.fs.copy_file(path, backup_path)

        # Write new content
        try:
            await self.fs.write_file(path, content)
        except Exception as e:
            # Restore backup on failure
            if backup and backup_path.exists():
                await self.fs.copy_file(backup_path, path)
            raise e

    async def atomic_write(self, path: Path, content: bytes) -> None:
        """
        Atomic write (write to temp, then rename).

        Args:
            path: Target file path
            content: Content to write
        """
        import tempfile
        import os

        # Write to temporary file in same directory
        temp_fd, temp_path_str = tempfile.mkstemp(dir=path.parent)
        temp_path = Path(temp_path_str)

        try:
            # Write content
            os.write(temp_fd, content)
            os.close(temp_fd)

            # Atomic rename
            temp_path.replace(path)
        except Exception:
            # Clean up temp file on failure
            if temp_path.exists():
                temp_path.unlink()
            raise
