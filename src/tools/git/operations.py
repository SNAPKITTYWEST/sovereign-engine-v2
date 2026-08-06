"""
Git Operations
Part of SOVEREIGN PYTHON LLM ENGINE

Git repository operations using GitPython.
"""

from typing import Any
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from ...core.evidence import WORMLedger


@dataclass
class GitStatus:
    """Git repository status"""
    branch: str
    modified: list[str]
    untracked: list[str]
    staged: list[str]
    deleted: list[str]
    ahead: int
    behind: int


@dataclass
class GitCommit:
    """Git commit information"""
    sha: str
    author: str
    email: str
    date: datetime
    message: str
    files: list[str]


class GitOperations:
    """
    Git repository operations.

    Wraps GitPython for common git operations.
    """

    def __init__(self, repo_path: Path, worm_ledger: WORMLedger | None = None):
        """
        Initialize Git operations.

        Args:
            repo_path: Path to git repository
            worm_ledger: Optional WORM ledger
        """
        self.repo_path = repo_path
        self.worm_ledger = worm_ledger

        try:
            from git import Repo
        except ImportError:
            raise ImportError("GitPython is required. Install: pip install gitpython")

        try:
            self.repo = Repo(repo_path)
        except Exception as e:
            raise ValueError(f"Not a git repository: {repo_path}") from e

    async def status(self) -> GitStatus:
        """
        Get repository status.

        Returns:
            GitStatus with current state
        """
        import asyncio

        def _sync_status():
            # Get current branch
            branch = self.repo.active_branch.name

            # Get modified files
            modified = [item.a_path for item in self.repo.index.diff(None)]

            # Get untracked files
            untracked = self.repo.untracked_files

            # Get staged files
            staged = [item.a_path for item in self.repo.index.diff("HEAD")]

            # Get deleted files
            deleted = [item.a_path for item in self.repo.index.diff(None) if item.deleted_file]

            # Get ahead/behind
            ahead = 0
            behind = 0
            try:
                tracking_branch = self.repo.active_branch.tracking_branch()
                if tracking_branch:
                    ahead, behind = self._get_ahead_behind(tracking_branch)
            except Exception:
                pass

            return GitStatus(
                branch=branch,
                modified=modified,
                untracked=untracked,
                staged=staged,
                deleted=deleted,
                ahead=ahead,
                behind=behind
            )

        return await asyncio.to_thread(_sync_status)

    def _get_ahead_behind(self, tracking_branch) -> tuple[int, int]:
        """Get commits ahead/behind tracking branch"""
        try:
            ahead = len(list(self.repo.iter_commits(f"{tracking_branch}..HEAD")))
            behind = len(list(self.repo.iter_commits(f"HEAD..{tracking_branch}")))
            return ahead, behind
        except Exception:
            return 0, 0

    async def add(self, files: list[str]) -> None:
        """
        Add files to staging area.

        Args:
            files: List of file paths to stage
        """
        import asyncio

        def _sync_add():
            self.repo.index.add(files)

        await asyncio.to_thread(_sync_add)

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "git_add",
                "files": files,
                "timestamp": datetime.utcnow().isoformat()
            })

    async def commit(self, message: str, author: str | None = None) -> str:
        """
        Create a commit.

        Args:
            message: Commit message
            author: Optional author (Name <email>)

        Returns:
            Commit SHA
        """
        import asyncio

        def _sync_commit():
            if author:
                self.repo.index.commit(message, author=author)
            else:
                self.repo.index.commit(message)
            return self.repo.head.commit.hexsha

        sha = await asyncio.to_thread(_sync_commit)

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "git_commit",
                "message": message,
                "sha": sha,
                "timestamp": datetime.utcnow().isoformat()
            })

        return sha

    async def push(self, remote: str = "origin", branch: str | None = None) -> None:
        """
        Push commits to remote.

        Args:
            remote: Remote name
            branch: Branch name (defaults to current)
        """
        import asyncio

        def _sync_push():
            if branch:
                self.repo.remotes[remote].push(branch)
            else:
                self.repo.remotes[remote].push()

        await asyncio.to_thread(_sync_push)

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "git_push",
                "remote": remote,
                "branch": branch or "current",
                "timestamp": datetime.utcnow().isoformat()
            })

    async def pull(self, remote: str = "origin", branch: str | None = None) -> None:
        """
        Pull commits from remote.

        Args:
            remote: Remote name
            branch: Branch name (defaults to current)
        """
        import asyncio

        def _sync_pull():
            if branch:
                self.repo.remotes[remote].pull(branch)
            else:
                self.repo.remotes[remote].pull()

        await asyncio.to_thread(_sync_pull)

    async def clone(self, url: str, target_path: Path) -> "GitOperations":
        """
        Clone repository.

        Args:
            url: Repository URL
            target_path: Where to clone

        Returns:
            GitOperations for cloned repo
        """
        from git import Repo
        import asyncio

        def _sync_clone():
            Repo.clone_from(url, target_path)

        await asyncio.to_thread(_sync_clone)

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "git_clone",
                "url": url,
                "path": str(target_path),
                "timestamp": datetime.utcnow().isoformat()
            })

        return GitOperations(target_path, self.worm_ledger)

    async def log(self, max_count: int = 10) -> list[GitCommit]:
        """
        Get commit history.

        Args:
            max_count: Maximum number of commits

        Returns:
            List of commits
        """
        import asyncio

        def _sync_log():
            commits = []

            for commit in self.repo.iter_commits(max_count=max_count):
                commits.append(GitCommit(
                    sha=commit.hexsha,
                    author=commit.author.name,
                    email=commit.author.email,
                    date=datetime.fromtimestamp(commit.committed_date),
                    message=commit.message.strip(),
                    files=list(commit.stats.files.keys())
                ))

            return commits

        return await asyncio.to_thread(_sync_log)

    async def diff(self, file_path: str | None = None) -> str:
        """
        Get diff of changes.

        Args:
            file_path: Optional specific file

        Returns:
            Diff string
        """
        import asyncio

        def _sync_diff():
            if file_path:
                return self.repo.git.diff(file_path)
            else:
                return self.repo.git.diff()

        return await asyncio.to_thread(_sync_diff)

    async def branch_list(self) -> list[str]:
        """
        List all branches.

        Returns:
            List of branch names
        """
        import asyncio

        def _sync_branch_list():
            return [branch.name for branch in self.repo.branches]

        return await asyncio.to_thread(_sync_branch_list)

    async def branch_create(self, name: str, checkout: bool = False) -> None:
        """
        Create new branch.

        Args:
            name: Branch name
            checkout: Whether to checkout new branch
        """
        import asyncio

        def _sync_branch_create():
            new_branch = self.repo.create_head(name)
            if checkout:
                new_branch.checkout()

        await asyncio.to_thread(_sync_branch_create)

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "git_branch_create",
                "name": name,
                "checkout": checkout,
                "timestamp": datetime.utcnow().isoformat()
            })

    async def checkout(self, branch: str) -> None:
        """
        Checkout branch.

        Args:
            branch: Branch name
        """
        import asyncio

        def _sync_checkout():
            self.repo.heads[branch].checkout()

        await asyncio.to_thread(_sync_checkout)

    async def reset(self, mode: str = "mixed", commit: str = "HEAD") -> None:
        """
        Reset to commit.

        Args:
            mode: Reset mode ("soft", "mixed", "hard")
            commit: Commit reference
        """
        import asyncio

        def _sync_reset():
            self.repo.git.reset(f"--{mode}", commit)

        await asyncio.to_thread(_sync_reset)

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "git_reset",
                "mode": mode,
                "commit": commit,
                "timestamp": datetime.utcnow().isoformat()
            })


# Tool registration helpers
async def git_status_tool(repo_path: str) -> dict:
    """Get git status"""
    git = GitOperations(Path(repo_path))
    status = await git.status()

    return {
        "branch": status.branch,
        "modified": status.modified,
        "untracked": status.untracked,
        "staged": status.staged,
        "ahead": status.ahead,
        "behind": status.behind
    }


async def git_commit_tool(repo_path: str, message: str, files: list[str] | None = None) -> dict:
    """Create git commit"""
    git = GitOperations(Path(repo_path))

    # Stage files if provided
    if files:
        await git.add(files)

    sha = await git.commit(message)

    return {
        "sha": sha,
        "message": message
    }


async def git_push_tool(repo_path: str, remote: str = "origin") -> dict:
    """Push to remote"""
    git = GitOperations(Path(repo_path))
    await git.push(remote)

    return {"status": "pushed", "remote": remote}


async def git_log_tool(repo_path: str, max_count: int = 10) -> dict:
    """Get commit history"""
    git = GitOperations(Path(repo_path))
    commits = await git.log(max_count)

    return {
        "commits": [
            {
                "sha": c.sha[:8],
                "author": c.author,
                "date": c.date.isoformat(),
                "message": c.message
            }
            for c in commits
        ]
    }
