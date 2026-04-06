"""Tests for the git sync backend."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from basic_memory.sync.git_sync import GitSyncBackend, GitPushResult, GitPullResult, GitSyncStatus


def _init_bare_remote(tmp_path: Path) -> Path:
    """Create a bare git repo to act as a remote."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main"],
        cwd=remote, check=True, capture_output=True,
    )
    return remote


def _init_local_repo(path: Path, remote: Path | None = None) -> None:
    """Init a git repo at `path`, optionally with a remote."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path, check=True, capture_output=True,
    )
    if remote:
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote)],
            cwd=path, check=True, capture_output=True,
        )


class TestIsGitRepo:
    @pytest.mark.asyncio
    async def test_returns_false_for_non_repo(self, tmp_path):
        backend = GitSyncBackend(tmp_path)
        assert await backend.is_git_repo() is False

    @pytest.mark.asyncio
    async def test_returns_true_for_repo(self, tmp_path):
        project = tmp_path / "project"
        _init_local_repo(project)
        backend = GitSyncBackend(project)
        assert await backend.is_git_repo() is True


class TestInitRepo:
    @pytest.mark.asyncio
    async def test_init_creates_repo(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        backend = GitSyncBackend(project)

        await backend.init_repo()

        assert (project / ".git").is_dir()

    @pytest.mark.asyncio
    async def test_init_creates_gitignore(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        backend = GitSyncBackend(project)

        await backend.init_repo()

        gitignore = project / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert "*.db" in content
        assert ".basic-memory/" in content

    @pytest.mark.asyncio
    async def test_init_preserves_existing_gitignore(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / ".gitignore").write_text("*.pyc\n")

        backend = GitSyncBackend(project)
        await backend.init_repo()

        content = (project / ".gitignore").read_text()
        assert "*.pyc" in content
        assert "*.db" in content

    @pytest.mark.asyncio
    async def test_init_is_idempotent(self, tmp_path):
        project = tmp_path / "project"
        _init_local_repo(project)
        backend = GitSyncBackend(project)

        # Should not raise on second init
        await backend.init_repo()
        assert await backend.is_git_repo() is True


class TestConfigureRemote:
    @pytest.mark.asyncio
    async def test_adds_remote(self, tmp_path):
        project = tmp_path / "project"
        _init_local_repo(project)
        remote = _init_bare_remote(tmp_path)
        backend = GitSyncBackend(project)

        await backend.configure_remote(str(remote))

        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=project, capture_output=True, text=True,
        )
        assert result.stdout.strip() == str(remote)

    @pytest.mark.asyncio
    async def test_updates_existing_remote(self, tmp_path):
        project = tmp_path / "project"
        remote1 = _init_bare_remote(tmp_path)
        _init_local_repo(project, remote=remote1)

        remote2 = tmp_path / "remote2.git"
        remote2.mkdir()
        subprocess.run(["git", "init", "--bare"], cwd=remote2, check=True, capture_output=True)

        backend = GitSyncBackend(project)
        await backend.configure_remote(str(remote2))

        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=project, capture_output=True, text=True,
        )
        assert result.stdout.strip() == str(remote2)


class TestPush:
    @pytest.mark.asyncio
    async def test_push_with_changes(self, tmp_path):
        remote = _init_bare_remote(tmp_path)
        project = tmp_path / "project"
        _init_local_repo(project, remote=remote)

        # Create a file and do initial commit (needed for push)
        (project / "test.md").write_text("# Test\n")

        backend = GitSyncBackend(project)
        result = await backend.push(message="initial commit")

        assert result.success is True
        assert result.files_committed >= 1
        assert result.commit_sha is not None
        assert len(result.commit_sha) == 40

    @pytest.mark.asyncio
    async def test_push_nothing_to_commit(self, tmp_path):
        remote = _init_bare_remote(tmp_path)
        project = tmp_path / "project"
        _init_local_repo(project, remote=remote)

        # Create, commit, push an initial file
        (project / "test.md").write_text("# Test\n")
        backend = GitSyncBackend(project)
        await backend.push(message="initial")

        # Push again with no changes
        result = await backend.push()

        assert result.success is True
        assert result.files_committed == 0
        assert "Nothing to commit" in result.message

    @pytest.mark.asyncio
    async def test_push_not_a_repo(self, tmp_path):
        backend = GitSyncBackend(tmp_path)
        result = await backend.push()

        assert result.success is False
        assert "Not a git repository" in result.message

    @pytest.mark.asyncio
    async def test_push_default_commit_message(self, tmp_path):
        remote = _init_bare_remote(tmp_path)
        project = tmp_path / "project"
        _init_local_repo(project, remote=remote)

        (project / "note.md").write_text("# Note\n")
        backend = GitSyncBackend(project)
        result = await backend.push()

        assert result.success is True
        # Verify the commit message contains our auto-generated prefix
        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=project, capture_output=True, text=True,
        )
        assert "sync:" in log.stdout


class TestPull:
    @pytest.mark.asyncio
    async def test_pull_new_changes(self, tmp_path):
        remote = _init_bare_remote(tmp_path)

        # Set up project A and push a file
        project_a = tmp_path / "project_a"
        _init_local_repo(project_a, remote=remote)
        (project_a / "note-a.md").write_text("# From A\n")
        backend_a = GitSyncBackend(project_a)
        await backend_a.push(message="from A")

        # Clone into project B
        project_b = tmp_path / "project_b"
        subprocess.run(
            ["git", "clone", str(remote), str(project_b)],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=project_b, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=project_b, check=True, capture_output=True,
        )

        # Push new content from A
        (project_a / "note-b.md").write_text("# New from A\n")
        await backend_a.push(message="new from A")

        # Pull from B
        backend_b = GitSyncBackend(project_b)
        result = await backend_b.pull()

        assert result.success is True
        assert (project_b / "note-b.md").exists()

    @pytest.mark.asyncio
    async def test_pull_already_up_to_date(self, tmp_path):
        remote = _init_bare_remote(tmp_path)
        project = tmp_path / "project"
        _init_local_repo(project, remote=remote)
        (project / "test.md").write_text("# Test\n")

        backend = GitSyncBackend(project)
        await backend.push(message="init")

        result = await backend.pull()
        assert result.success is True
        assert "Already up to date" in result.message

    @pytest.mark.asyncio
    async def test_pull_not_a_repo(self, tmp_path):
        backend = GitSyncBackend(tmp_path)
        result = await backend.pull()

        assert result.success is False
        assert "Not a git repository" in result.message


class TestStatus:
    @pytest.mark.asyncio
    async def test_status_not_a_repo(self, tmp_path):
        backend = GitSyncBackend(tmp_path)
        status = await backend.status()

        assert status.is_repo is False

    @pytest.mark.asyncio
    async def test_status_clean_repo(self, tmp_path):
        remote = _init_bare_remote(tmp_path)
        project = tmp_path / "project"
        _init_local_repo(project, remote=remote)
        (project / "test.md").write_text("# Test\n")

        backend = GitSyncBackend(project)
        await backend.push(message="init")

        status = await backend.status()

        assert status.is_repo is True
        assert status.has_remote is True
        assert status.branch == "main"
        assert status.is_clean is True
        assert status.files_changed == 0

    @pytest.mark.asyncio
    async def test_status_dirty_repo(self, tmp_path):
        project = tmp_path / "project"
        _init_local_repo(project)
        (project / "test.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=project, check=True, capture_output=True,
        )

        # Make uncommitted change
        (project / "new.md").write_text("# New\n")

        backend = GitSyncBackend(project)
        status = await backend.status()

        assert status.is_repo is True
        assert status.is_clean is False
        assert status.files_changed >= 1


class TestGetConflicts:
    @pytest.mark.asyncio
    async def test_no_conflicts(self, tmp_path):
        project = tmp_path / "project"
        _init_local_repo(project)
        (project / "test.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=project, check=True, capture_output=True,
        )

        backend = GitSyncBackend(project)
        conflicts = await backend.get_conflicts()
        assert conflicts == []
