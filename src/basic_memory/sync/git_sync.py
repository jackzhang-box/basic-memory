"""Git sync backend for Basic Memory.

Provides push/pull synchronization via git subprocess calls.
Git sync is an overlay on top of the existing filesystem sync —
it doesn't replace the core watch/sync loop, but adds the ability
to share knowledge between team members via an internal git remote.
"""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger


# --- Result types ---


@dataclass
class GitSyncStatus:
    """Current git sync state for a project."""

    is_repo: bool = False
    has_remote: bool = False
    remote_url: str | None = None
    branch: str | None = None
    is_clean: bool = True
    files_changed: int = 0
    ahead: int = 0
    behind: int = 0


@dataclass
class GitPushResult:
    """Result of a git push operation."""

    success: bool
    commit_sha: str | None = None
    files_committed: int = 0
    message: str = ""


@dataclass
class GitPullResult:
    """Result of a git pull operation."""

    success: bool
    files_updated: int = 0
    has_conflicts: bool = False
    conflict_files: list[str] = field(default_factory=list)
    message: str = ""


# --- Git subprocess helpers ---


def _run_git(
    args: list[str],
    cwd: Path,
    *,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a git command as a subprocess.

    Args:
        args: Git subcommand and arguments (e.g. ["status", "--porcelain"])
        cwd: Working directory (the project path)
        check: Raise on non-zero exit code
        capture: Capture stdout/stderr
    """
    cmd = ["git"] + args
    logger.debug(f"Running: {' '.join(cmd)} in {cwd}")
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        capture_output=capture,
        text=True,
    )


async def _run_git_async(
    args: list[str],
    cwd: Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a git command asynchronously via asyncio.to_thread."""
    return await asyncio.to_thread(_run_git, args, cwd, check=check)


# --- GitSyncBackend ---


class GitSyncBackend:
    """Wraps git subprocess calls for push/pull sync."""

    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path

    # --- Queries ---

    async def is_git_repo(self) -> bool:
        """Check if the project path is inside a git repository."""
        try:
            result = await _run_git_async(
                ["rev-parse", "--is-inside-work-tree"],
                self.project_path,
                check=False,
            )
            return result.returncode == 0 and result.stdout.strip() == "true"
        except Exception:
            return False

    async def status(self) -> GitSyncStatus:
        """Get the current sync status of the repo."""
        is_repo = await self.is_git_repo()
        if not is_repo:
            return GitSyncStatus(is_repo=False)

        # Branch name
        branch_result = await _run_git_async(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            self.project_path,
            check=False,
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None

        # Remote URL
        remote_url = None
        has_remote = False
        remote_result = await _run_git_async(
            ["remote", "get-url", "origin"],
            self.project_path,
            check=False,
        )
        if remote_result.returncode == 0:
            remote_url = remote_result.stdout.strip()
            has_remote = bool(remote_url)

        # Working tree status
        porcelain = await _run_git_async(
            ["status", "--porcelain"],
            self.project_path,
            check=False,
        )
        changed_lines = [l for l in porcelain.stdout.strip().splitlines() if l.strip()]
        files_changed = len(changed_lines)
        is_clean = files_changed == 0

        # Ahead/behind (requires tracking branch)
        ahead, behind = 0, 0
        if has_remote and branch:
            await _run_git_async(["fetch", "origin"], self.project_path, check=False)
            rev_list = await _run_git_async(
                ["rev-list", "--left-right", "--count", f"HEAD...origin/{branch}"],
                self.project_path,
                check=False,
            )
            if rev_list.returncode == 0:
                parts = rev_list.stdout.strip().split()
                if len(parts) == 2:
                    ahead, behind = int(parts[0]), int(parts[1])

        return GitSyncStatus(
            is_repo=True,
            has_remote=has_remote,
            remote_url=remote_url,
            branch=branch,
            is_clean=is_clean,
            files_changed=files_changed,
            ahead=ahead,
            behind=behind,
        )

    async def get_conflicts(self) -> list[str]:
        """Return list of files with merge conflicts."""
        result = await _run_git_async(
            ["diff", "--name-only", "--diff-filter=U"],
            self.project_path,
            check=False,
        )
        if result.returncode != 0:
            return []
        return [f for f in result.stdout.strip().splitlines() if f.strip()]

    # --- Mutations ---

    async def init_repo(self) -> None:
        """Initialize a git repository at the project path."""
        if not await self.is_git_repo():
            await _run_git_async(["init"], self.project_path)
            logger.info(f"Initialized git repo at {self.project_path}")

        # Ensure .gitignore includes the database file
        gitignore = self.project_path / ".gitignore"
        patterns = {"*.db", "*.db-journal", "*.db-wal", ".basic-memory/"}
        existing = set()
        if gitignore.exists():
            existing = set(gitignore.read_text().splitlines())
        missing = patterns - existing
        if missing:
            with gitignore.open("a") as f:
                for pattern in sorted(missing):
                    f.write(f"{pattern}\n")

    async def configure_remote(self, remote_url: str) -> None:
        """Set or update the origin remote URL."""
        # Check if origin exists
        result = await _run_git_async(
            ["remote", "get-url", "origin"],
            self.project_path,
            check=False,
        )
        if result.returncode == 0:
            await _run_git_async(
                ["remote", "set-url", "origin", remote_url],
                self.project_path,
            )
        else:
            await _run_git_async(
                ["remote", "add", "origin", remote_url],
                self.project_path,
            )
        logger.info(f"Configured remote origin: {remote_url}")

    async def push(self, message: str | None = None) -> GitPushResult:
        """Stage all changes, commit, and push to origin.

        Args:
            message: Custom commit message. Defaults to timestamp-based message.
        """
        if not await self.is_git_repo():
            return GitPushResult(success=False, message="Not a git repository")

        # Stage all changes
        await _run_git_async(["add", "-A"], self.project_path)

        # Check if there's anything to commit
        status_result = await _run_git_async(
            ["status", "--porcelain"],
            self.project_path,
        )
        staged_lines = [l for l in status_result.stdout.strip().splitlines() if l.strip()]
        if not staged_lines:
            return GitPushResult(success=True, files_committed=0, message="Nothing to commit")

        # Commit
        commit_msg = message or f"sync: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} via basic-memory"
        await _run_git_async(["commit", "-m", commit_msg], self.project_path)

        # Get commit SHA
        sha_result = await _run_git_async(
            ["rev-parse", "HEAD"],
            self.project_path,
        )
        commit_sha = sha_result.stdout.strip()

        # Push
        branch_result = await _run_git_async(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            self.project_path,
        )
        branch = branch_result.stdout.strip()

        push_result = await _run_git_async(
            ["push", "-u", "origin", branch],
            self.project_path,
            check=False,
        )
        if push_result.returncode != 0:
            return GitPushResult(
                success=False,
                commit_sha=commit_sha,
                files_committed=len(staged_lines),
                message=f"Push failed: {push_result.stderr.strip()}",
            )

        return GitPushResult(
            success=True,
            commit_sha=commit_sha,
            files_committed=len(staged_lines),
            message=f"Pushed {len(staged_lines)} file(s)",
        )

    async def pull(self) -> GitPullResult:
        """Pull changes from origin, reporting conflicts if any."""
        if not await self.is_git_repo():
            return GitPullResult(success=False, message="Not a git repository")

        branch_result = await _run_git_async(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            self.project_path,
        )
        branch = branch_result.stdout.strip()

        # Count files before pull for change detection
        result = await _run_git_async(
            ["pull", "origin", branch],
            self.project_path,
            check=False,
        )

        if result.returncode != 0:
            # Check for merge conflicts
            conflicts = await self.get_conflicts()
            if conflicts:
                return GitPullResult(
                    success=False,
                    has_conflicts=True,
                    conflict_files=conflicts,
                    message=f"Merge conflicts in {len(conflicts)} file(s)",
                )
            return GitPullResult(
                success=False,
                message=f"Pull failed: {result.stderr.strip()}",
            )

        # Parse output for file count
        output = result.stdout.strip()
        if "Already up to date" in output:
            return GitPullResult(success=True, files_updated=0, message="Already up to date")

        # Count updated files from diffstat in pull output
        diff_result = await _run_git_async(
            ["diff", "--stat", "HEAD@{1}", "HEAD"],
            self.project_path,
            check=False,
        )
        files_updated = 0
        if diff_result.returncode == 0:
            lines = diff_result.stdout.strip().splitlines()
            # Last line is summary like " 3 files changed, ..."
            files_updated = max(0, len(lines) - 1)

        return GitPullResult(
            success=True,
            files_updated=files_updated,
            message=f"Pulled {files_updated} file(s)",
        )
