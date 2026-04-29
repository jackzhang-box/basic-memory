"""Tests for project context utilities (no standard-library mock usage).

These functions are config/env driven, so we use the real ConfigManager-backed
test config file and pytest monkeypatch for environment variables.
"""

from __future__ import annotations

import pytest


class _ContextState:
    """Minimal FastMCP context-state stub for unit tests."""

    def __init__(self):
        self._state: dict[str, object] = {}

    async def get_state(self, key: str):
        return self._state.get(key)

    async def set_state(self, key: str, value: object, **kwargs) -> None:
        self._state[key] = value


@pytest.mark.asyncio
async def test_returns_none_when_no_default_and_no_project(config_manager, monkeypatch):
    from agent_brain.mcp.project_context import resolve_project_parameter

    cfg = config_manager.load_config()
    cfg.default_project = None
    config_manager.save_config(cfg)

    monkeypatch.delenv("AGENT_BRAIN_MCP_PROJECT", raising=False)

    # Prevent API fallback from returning a project via stale dependency overrides
    async def _no_api_fallback():
        return None

    monkeypatch.setattr(
        "agent_brain.mcp.project_context._resolve_default_project_from_api",
        _no_api_fallback,
    )
    assert await resolve_project_parameter(project=None, allow_discovery=False) is None


@pytest.mark.asyncio
async def test_allows_discovery_when_enabled(config_manager, monkeypatch):
    from agent_brain.mcp.project_context import resolve_project_parameter

    cfg = config_manager.load_config()
    cfg.default_project = None
    config_manager.save_config(cfg)

    # Prevent API fallback from returning a project via stale dependency overrides
    async def _no_api_fallback():
        return None

    monkeypatch.setattr(
        "agent_brain.mcp.project_context._resolve_default_project_from_api",
        _no_api_fallback,
    )
    assert await resolve_project_parameter(project=None, allow_discovery=True) is None


@pytest.mark.asyncio
async def test_returns_project_when_specified(config_manager):
    from agent_brain.mcp.project_context import resolve_project_parameter

    cfg = config_manager.load_config()
    config_manager.save_config(cfg)

    assert await resolve_project_parameter(project="my-project") == "my-project"


@pytest.mark.asyncio
async def test_uses_env_var_priority(config_manager, monkeypatch):
    from agent_brain.mcp.project_context import resolve_project_parameter

    cfg = config_manager.load_config()
    config_manager.save_config(cfg)

    monkeypatch.setenv("AGENT_BRAIN_MCP_PROJECT", "env-project")
    assert await resolve_project_parameter(project="explicit-project") == "env-project"


@pytest.mark.asyncio
async def test_uses_explicit_project_when_no_env(config_manager, monkeypatch):
    from agent_brain.mcp.project_context import resolve_project_parameter

    cfg = config_manager.load_config()
    config_manager.save_config(cfg)

    monkeypatch.delenv("AGENT_BRAIN_MCP_PROJECT", raising=False)
    assert await resolve_project_parameter(project="explicit-project") == "explicit-project"


@pytest.mark.asyncio
async def test_canonicalizes_case_insensitive_project_reference(
    config_manager, config_home, monkeypatch
):
    from agent_brain.config import ProjectEntry
    from agent_brain.mcp.project_context import resolve_project_parameter

    cfg = config_manager.load_config()
    project_name = "Personal-Project"
    project_path = config_home / "personal-project"
    project_path.mkdir(parents=True, exist_ok=True)
    cfg.projects[project_name] = ProjectEntry(path=str(project_path))
    config_manager.save_config(cfg)

    monkeypatch.delenv("AGENT_BRAIN_MCP_PROJECT", raising=False)

    assert await resolve_project_parameter(project="personal-project") == project_name
    assert await resolve_project_parameter(project="PERSONAL-PROJECT") == project_name


@pytest.mark.asyncio
async def test_uses_default_project(config_manager, config_home, monkeypatch):
    from agent_brain.mcp.project_context import resolve_project_parameter
    from agent_brain.config import ProjectEntry

    cfg = config_manager.load_config()
    (config_home / "default-project").mkdir(parents=True, exist_ok=True)
    cfg.projects["default-project"] = ProjectEntry(path=str(config_home / "default-project"))
    cfg.default_project = "default-project"
    config_manager.save_config(cfg)

    monkeypatch.delenv("AGENT_BRAIN_MCP_PROJECT", raising=False)
    assert await resolve_project_parameter(project=None) == "default-project"


@pytest.mark.asyncio
async def test_returns_none_when_no_default(config_manager, monkeypatch):
    from agent_brain.mcp.project_context import resolve_project_parameter

    cfg = config_manager.load_config()
    cfg.default_project = None
    config_manager.save_config(cfg)

    monkeypatch.delenv("AGENT_BRAIN_MCP_PROJECT", raising=False)

    # Prevent API fallback from returning a project via stale dependency overrides
    async def _no_api_fallback():
        return None

    monkeypatch.setattr(
        "agent_brain.mcp.project_context._resolve_default_project_from_api",
        _no_api_fallback,
    )
    assert await resolve_project_parameter(project=None) is None


@pytest.mark.asyncio
async def test_env_constraint_overrides_default(config_manager, config_home, monkeypatch):
    from agent_brain.mcp.project_context import resolve_project_parameter
    from agent_brain.config import ProjectEntry

    cfg = config_manager.load_config()
    (config_home / "default-project").mkdir(parents=True, exist_ok=True)
    cfg.projects["default-project"] = ProjectEntry(path=str(config_home / "default-project"))
    cfg.default_project = "default-project"
    config_manager.save_config(cfg)

    monkeypatch.setenv("AGENT_BRAIN_MCP_PROJECT", "env-project")
    assert await resolve_project_parameter(project=None) == "env-project"


@pytest.mark.asyncio
async def test_resolve_project_parameter_uses_cached_active_project_before_api_default_lookup(
    config_manager, monkeypatch
):
    from agent_brain.mcp.project_context import resolve_project_parameter
    from agent_brain.schemas.project_info import ProjectItem

    config = config_manager.load_config()
    config.default_project = None
    config_manager.save_config(config)

    context = _ContextState()
    cached_project = ProjectItem(
        id=1,
        external_id="11111111-1111-1111-1111-111111111111",
        name="Cached Project",
        path="/tmp/cached-project",
        is_default=True,
    )
    await context.set_state("active_project", cached_project.model_dump())

    async def fail_if_called():  # pragma: no cover
        raise AssertionError("Default project API lookup should not run when project is cached")

    monkeypatch.setattr(
        "agent_brain.mcp.project_context._resolve_default_project_from_api",
        fail_if_called,
    )

    resolved = await resolve_project_parameter(project=None, context=context)
    assert resolved == cached_project.name


@pytest.mark.asyncio
async def test_resolve_project_parameter_caches_api_default_project_name(
    config_manager, monkeypatch
):
    from agent_brain.mcp.project_context import resolve_project_parameter

    config = config_manager.load_config()
    config.default_project = None
    config_manager.save_config(config)

    context = _ContextState()
    api_calls = {"count": 0}

    async def fake_default_lookup():
        api_calls["count"] += 1
        return "api-default"

    monkeypatch.setattr(
        "agent_brain.mcp.project_context._resolve_default_project_from_api",
        fake_default_lookup,
    )

    first = await resolve_project_parameter(project=None, context=context)
    second = await resolve_project_parameter(project=None, context=context)

    assert first == "api-default"
    assert second == "api-default"
    assert api_calls["count"] == 1


@pytest.mark.asyncio
async def test_get_active_project_uses_cached_project_before_resolution(monkeypatch):
    from agent_brain.mcp.project_context import get_active_project
    from agent_brain.schemas.project_info import ProjectItem

    context = _ContextState()
    cached_project = ProjectItem(
        id=1,
        external_id="11111111-1111-1111-1111-111111111111",
        name="Cached Project",
        path="/tmp/cached-project",
        is_default=True,
    )
    await context.set_state("active_project", cached_project.model_dump())

    async def fail_if_called(*args, **kwargs):  # pragma: no cover
        raise AssertionError("Project resolution should not run when cache matches")

    monkeypatch.setattr(
        "agent_brain.mcp.project_context.resolve_project_parameter",
        fail_if_called,
    )

    resolved = await get_active_project(client=None, context=context)
    assert resolved == cached_project


@pytest.mark.asyncio
async def test_get_active_project_uses_cached_project_for_explicit_permalink(monkeypatch):
    from agent_brain.mcp.project_context import get_active_project
    from agent_brain.schemas.project_info import ProjectItem

    context = _ContextState()
    cached_project = ProjectItem(
        id=1,
        external_id="11111111-1111-1111-1111-111111111111",
        name="My Research",
        path="/tmp/my-research",
        is_default=False,
    )
    await context.set_state("active_project", cached_project.model_dump())

    async def fail_if_called(*args, **kwargs):  # pragma: no cover
        raise AssertionError(
            "Project resolution should not run when explicit project matches cache"
        )

    monkeypatch.setattr(
        "agent_brain.mcp.project_context.resolve_project_parameter",
        fail_if_called,
    )

    resolved = await get_active_project(client=None, project="my-research", context=context)
    assert resolved == cached_project


@pytest.mark.asyncio
async def test_resolve_project_and_path_uses_cached_project_for_memory_url_prefix(
    config_manager, monkeypatch
):
    from agent_brain.mcp.project_context import resolve_project_and_path
    from agent_brain.schemas.project_info import ProjectItem

    config = config_manager.load_config()
    config.permalinks_include_project = False
    config_manager.save_config(config)

    context = _ContextState()
    cached_project = ProjectItem(
        id=1,
        external_id="11111111-1111-1111-1111-111111111111",
        name="My Research",
        path="/tmp/my-research",
        is_default=False,
    )
    await context.set_state("active_project", cached_project.model_dump())

    async def fail_if_called(*args, **kwargs):  # pragma: no cover
        raise AssertionError("Project resolve API should not run when memory URL matches cache")

    async def fake_resolve_project_parameter(project=None, **kwargs):
        return cached_project.name if project else cached_project.name

    monkeypatch.setattr("agent_brain.mcp.tools.utils.call_post", fail_if_called)
    monkeypatch.setattr(
        "agent_brain.mcp.project_context.resolve_project_parameter",
        fake_resolve_project_parameter,
    )

    active_project, resolved_path, is_memory_url = await resolve_project_and_path(
        client=None,
        identifier="memory://my-research/notes/roadmap.md",
        context=context,
    )

    assert active_project == cached_project
    assert resolved_path == "notes/roadmap.md"
    assert is_memory_url is True


class TestDetectProjectFromUrlPrefix:
    """Test detect_project_from_url_prefix for URL-based project detection."""

    def test_detects_project_from_memory_url(self, config_manager):
        from agent_brain.mcp.project_context import detect_project_from_url_prefix

        config = config_manager.load_config()
        # The config has "test-project" from the conftest fixture
        result = detect_project_from_url_prefix("memory://test-project/some-note", config)
        assert result == "test-project"

    def test_detects_project_from_plain_path(self, config_manager):
        from agent_brain.mcp.project_context import detect_project_from_url_prefix

        config = config_manager.load_config()
        result = detect_project_from_url_prefix("test-project/some-note", config)
        assert result == "test-project"

    def test_returns_none_for_unknown_prefix(self, config_manager):
        from agent_brain.mcp.project_context import detect_project_from_url_prefix

        config = config_manager.load_config()
        result = detect_project_from_url_prefix("memory://unknown-project/note", config)
        assert result is None

    def test_returns_none_for_no_slash(self, config_manager):
        from agent_brain.mcp.project_context import detect_project_from_url_prefix

        config = config_manager.load_config()
        result = detect_project_from_url_prefix("memory://single-segment", config)
        assert result is None

    def test_returns_none_for_wildcard_prefix(self, config_manager):
        from agent_brain.mcp.project_context import detect_project_from_url_prefix

        config = config_manager.load_config()
        result = detect_project_from_url_prefix("memory://*/notes", config)
        assert result is None

    def test_matches_case_insensitive_via_permalink(self, config_manager):
        from agent_brain.mcp.project_context import detect_project_from_url_prefix
        from agent_brain.config import ProjectEntry

        config = config_manager.load_config()
        (config_manager.config_dir.parent / "My Research").mkdir(parents=True, exist_ok=True)
        config.projects["My Research"] = ProjectEntry(
            path=str(config_manager.config_dir.parent / "My Research")
        )
        config_manager.save_config(config)

        result = detect_project_from_url_prefix("memory://my-research/notes", config)
        assert result == "My Research"


class TestGetProjectClientRoutingOrder:
    """Test that get_project_client respects explicit routing."""

    @pytest.mark.asyncio
    async def test_local_flag_skips_cloud_routing(self, config_manager, monkeypatch):
        """--local flag should force local routing."""
        from agent_brain.mcp.project_context import get_project_client
        from agent_brain.config import ProjectEntry, ProjectMode

        config = config_manager.load_config()
        config.projects["git-proj"] = ProjectEntry(
            path=str(config_manager.config_dir.parent / "git-proj"),
            mode=ProjectMode.GIT,
        )
        config_manager.save_config(config)

        # Set explicit local routing
        monkeypatch.setenv("AGENT_BRAIN_FORCE_LOCAL", "true")

        # Will fail at project validation (no API running), which proves routing worked
        with pytest.raises(Exception) as exc_info:
            async with get_project_client(project="git-proj"):
                pass

        # The error should NOT be about workspaces
        assert "workspace" not in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_factory_mode_skips_workspace_resolution(self, config_manager, monkeypatch):
        """When a client factory is set (in-process server), skip workspace resolution.

        The cloud MCP server calls set_client_factory() so that get_client() routes
        requests through TenantASGITransport. In this mode, project context
        is already resolved by the transport layer.
        """
        from contextlib import asynccontextmanager

        from agent_brain.mcp import async_client
        from agent_brain.mcp.project_context import get_project_client
        from agent_brain.config import ProjectEntry, ProjectMode

        config = config_manager.load_config()
        config.projects["git-proj"] = ProjectEntry(
            path=str(config_manager.config_dir.parent / "git-proj"),
            mode=ProjectMode.GIT,
        )
        config_manager.save_config(config)

        # Set up a factory (simulates what cloud MCP server does)
        @asynccontextmanager
        async def fake_factory():
            from httpx import ASGITransport, AsyncClient
            from agent_brain.api.app import app as fastapi_app

            async with AsyncClient(
                transport=ASGITransport(app=fastapi_app),
                base_url="http://test",
            ) as client:
                yield client

        original_factory = async_client._client_factory
        async_client.set_client_factory(fake_factory)

        try:
            # Will fail at project validation (no real project in DB), but proves
            # factory routing was selected
            with pytest.raises(Exception) as exc_info:
                async with get_project_client(project="git-proj"):
                    pass

            error_msg = str(exc_info.value).lower()
            # Should not get a workspace resolution error
            assert "workspace" not in error_msg
        finally:
            # Restore original factory to avoid polluting other tests
            async_client._client_factory = original_factory
