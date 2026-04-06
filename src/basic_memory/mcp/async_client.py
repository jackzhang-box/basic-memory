import os
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import AsyncIterator, Callable, Optional

from httpx import ASGITransport, AsyncClient, Timeout
from loguru import logger

from basic_memory.api.app import app as fastapi_app


def _force_local_mode() -> bool:
    """Check if local mode is forced via environment variable."""
    return os.environ.get("BASIC_MEMORY_FORCE_LOCAL", "").lower() in ("true", "1", "yes")


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

    timeout = _build_timeout()
    logger.debug("Using ASGI client for local Basic Memory API")
    async with _asgi_client(timeout) as client:
        yield client
