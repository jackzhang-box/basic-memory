import os
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import AsyncIterator, Callable, Optional

from httpx import ASGITransport, AsyncClient, Timeout
from loguru import logger

from agent_brain.api.app import app as fastapi_app

# Track whether we've done a one-time DB/project reconciliation for ASGI clients.
# The FastAPI lifespan handles this for HTTP servers, but ASGI transport
# (used by CLI commands) bypasses the lifespan entirely.
_initialized = False


def _force_local_mode() -> bool:
    """Check if local mode is forced via environment variable."""
    return os.environ.get("AGENT_BRAIN_FORCE_LOCAL", "").lower() in ("true", "1", "yes")


def _build_timeout() -> Timeout:
    """Create a standard timeout config used across all clients."""
    return Timeout(
        connect=10.0,
        read=30.0,
        write=30.0,
        pool=30.0,
    )


def _asgi_client(timeout: Timeout) -> AsyncClient:
    """Create a local ASGI client."""
    return AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test", timeout=timeout
    )


# Optional factory override for dependency injection
_client_factory: Optional[Callable[[], AbstractAsyncContextManager[AsyncClient]]] = None


def set_client_factory(factory: Callable[[], AbstractAsyncContextManager[AsyncClient]]) -> None:
    """Override the default client factory (for testing, etc)."""
    global _client_factory
    _client_factory = factory


def is_factory_mode() -> bool:
    """Return True when a client factory override is active."""
    return _client_factory is not None


async def _ensure_initialized() -> None:
    """One-time project reconciliation for ASGI transport clients.

    The FastAPI lifespan handles full initialization (migrations + project sync)
    for HTTP servers, but ASGI transport (used by CLI commands) bypasses the
    lifespan entirely. Without this, projects from config.json never get
    registered in the database and every CLI command fails with "Project not found".

    We skip Alembic migrations for speed (~500ms savings) — the MCP server
    lifespan or `bm project add` handles migrations. CLI commands just need
    the project rows to exist in an already-migrated DB.
    """
    global _initialized
    if _initialized:
        return

    # Deferred imports to avoid circular dependency
    from agent_brain import db
    from agent_brain.config import ConfigManager
    from agent_brain.repository import ProjectRepository
    from agent_brain.services.project_service import ProjectService

    app_config = ConfigManager().config

    # Skip migrations (ensure_migrations=False) — the DB schema is managed by
    # the MCP server lifespan or `bm project add`. This avoids the ~500ms
    # Alembic overhead on every CLI invocation.
    _, session_maker = await db.get_or_create_db(
        db_path=app_config.database_path,
        db_type=db.DatabaseType.FILESYSTEM,
        ensure_migrations=False,
    )

    project_service = ProjectService(repository=ProjectRepository(session_maker))
    try:
        await project_service.synchronize_projects()
    except Exception as e:
        logger.warning(f"Project reconciliation failed: {e}")

    _initialized = True
    logger.debug("ASGI client project reconciliation completed")


@asynccontextmanager
async def get_client(
    project_name: Optional[str] = None,
) -> AsyncIterator[AsyncClient]:
    """Get an AsyncClient as a context manager.

    Routing: factory injection if set, otherwise local ASGI transport.
    The project_name parameter is retained for backward compatibility but
    does not affect routing.
    """
    if _client_factory:
        async with _client_factory() as client:
            yield client
        return

    # Trigger: first ASGI client use in this process
    # Why: ASGI transport bypasses FastAPI lifespan, so DB/project setup never runs
    # Outcome: projects from config.json are registered in the database
    await _ensure_initialized()

    timeout = _build_timeout()
    logger.debug("Using ASGI client for local Agent Brain API")
    async with _asgi_client(timeout) as client:
        yield client
