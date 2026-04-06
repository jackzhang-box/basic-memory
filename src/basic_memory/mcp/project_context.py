"""Project context utilities for Basic Memory MCP server.

Provides project lookup utilities for MCP tools.
Handles project validation and context management in one place.

Note: This module uses ProjectResolver for unified project resolution.
The resolve_project_parameter function is a thin wrapper for backwards
compatibility with existing MCP tools.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional, List, Tuple

from httpx import AsyncClient
from httpx._types import (
    HeaderTypes,
)
from loguru import logger
from fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError

from basic_memory import telemetry
from basic_memory.config import BasicMemoryConfig, ConfigManager
from basic_memory.project_resolver import ProjectResolver
from basic_memory.schemas.project_info import ProjectItem, ProjectList
from basic_memory.schemas.v2 import ProjectResolveResponse
from basic_memory.schemas.memory import memory_url_path
from basic_memory.utils import generate_permalink, normalize_project_reference


async def _resolve_default_project_from_api() -> Optional[str]:
    """Query the projects API for the default project.

    Used as a fallback when ConfigManager has no local config (cloud mode).
    """
    from basic_memory.mcp.async_client import get_client

    try:
        async with get_client() as client:
            response = await client.get("/v2/projects/")
            if response.status_code == 200:
                project_list = ProjectList.model_validate(response.json())
                if project_list.default_project:
                    return project_list.default_project
                # Fallback: find project with is_default=True
                for p in project_list.projects:
                    if p.is_default:
                        return p.name
    except Exception:
        pass
    return None


async def _get_cached_active_project(context: Optional[Context]) -> Optional[ProjectItem]:
    """Return the cached active project from context when available."""
    if not context:
        return None

    cached_raw = await context.get_state("active_project")
    if isinstance(cached_raw, dict):
        return ProjectItem.model_validate(cached_raw)
    return None


async def _set_cached_active_project(
    context: Optional[Context],
    active_project: ProjectItem,
) -> None:
    """Persist the active project and known default-project metadata in context."""
    if not context:
        return

    await context.set_state("active_project", active_project.model_dump())
    if active_project.is_default:
        await context.set_state("default_project_name", active_project.name)


async def _get_cached_default_project(context: Optional[Context]) -> Optional[str]:
    """Return the cached default project name from context when available."""
    if not context:
        return None

    cached_default = await context.get_state("default_project_name")
    if isinstance(cached_default, str):
        return cached_default
    return None


def _canonicalize_project_name(
    project_name: Optional[str],
    config: BasicMemoryConfig,
) -> Optional[str]:
    """Return the configured project name when the identifier matches by permalink.

    Project routing happens before API validation, so we normalize explicit inputs
    here to keep routing aligned with the database's case-insensitive project resolver.
    """
    if project_name is None:
        return None

    requested_permalink = generate_permalink(project_name)
    for configured_name in config.projects:
        if generate_permalink(configured_name) == requested_permalink:
            return configured_name

    return project_name


def _project_matches_identifier(project_item: ProjectItem, identifier: Optional[str]) -> bool:
    """Return True when the identifier refers to the cached project."""
    if identifier is None:
        return True

    normalized_identifier = generate_permalink(identifier)
    return normalized_identifier in {
        generate_permalink(project_item.name),
        project_item.permalink,
    }


async def resolve_project_parameter(
    project: Optional[str] = None,
    allow_discovery: bool = False,
    default_project: Optional[str] = None,
    context: Optional[Context] = None,
) -> Optional[str]:
    """Resolve project parameter using unified linear priority chain.

    This is a thin wrapper around ProjectResolver for backwards compatibility.
    New code should consider using ProjectResolver directly for more detailed
    resolution information.

    Resolution order:
    1. ENV_CONSTRAINT: BASIC_MEMORY_MCP_PROJECT env var (highest priority)
    2. EXPLICIT: project parameter passed directly
    3. DEFAULT: default_project from config (if set)
    4. Fallback: discovery (if allowed) → NONE

    Args:
        project: Optional explicit project parameter
        allow_discovery: If True, allows returning None for discovery mode
            (used by tools like recent_activity that can operate across all projects)
        default_project: Optional explicit default project. If not provided, reads from ConfigManager.

    Returns:
        Resolved project name or None if no resolution possible
    """
    with telemetry.span(
        "routing.resolve_project",
        requested_project=project,
        allow_discovery=allow_discovery,
    ):
        config = ConfigManager().config

        # Trigger: project already resolved earlier in the same MCP request
        # Why: the active project is request-constant, so re-discovering the
        #   default project via /v2/projects/ just repeats work
        # Outcome: reuse the cached project name as the explicit candidate
        if project is None:
            cached_project = await _get_cached_active_project(context)
            if cached_project is not None:
                project = cached_project.name

        # Trigger: there is no explicit project after env/context normalization
        # Why: default-project discovery is only needed as a fallback; doing it
        #   for explicit requests adds an avoidable /v2/projects/ round-trip
        # Outcome: skip default lookup when the active project is already known
        if default_project is None and project is None:
            # Load config for any values not explicitly provided.
            # ConfigManager reads from the local config file, which doesn't exist in cloud mode.
            # When it returns None, fall back to querying the projects API for the is_default flag.
            default_project = config.default_project

            if default_project is None:
                default_project = await _get_cached_default_project(context)

            if default_project is None:
                default_project = await _resolve_default_project_from_api()
                if default_project and context:
                    await context.set_state("default_project_name", default_project)

        # Create resolver with configuration and resolve
        resolver = ProjectResolver.from_env(
            default_project=default_project,
        )
        result = resolver.resolve(project=project, allow_discovery=allow_discovery)
        return _canonicalize_project_name(result.project, config)


async def get_project_names(client: AsyncClient, headers: HeaderTypes | None = None) -> List[str]:
    # Deferred import to avoid circular dependency with tools
    from basic_memory.mcp.tools.utils import call_get

    response = await call_get(client, "/v2/projects/", headers=headers)
    project_list = ProjectList.model_validate(response.json())
    return [project.name for project in project_list.projects]


async def get_active_project(
    client: AsyncClient,
    project: Optional[str] = None,
    context: Optional[Context] = None,
    headers: HeaderTypes | None = None,
) -> ProjectItem:
    """Get and validate project, setting it in context if available.

    Args:
        client: HTTP client for API calls
        project: Optional project name (resolved using hierarchy)
        context: Optional FastMCP context to cache the result

    Returns:
        The validated project item

    Raises:
        ValueError: If no project can be resolved
        HTTPError: If project doesn't exist or is inaccessible
    """
    with telemetry.scope(
        "routing.validate_project",
        requested_project=project,
        has_context=context is not None,
    ):
        # Deferred import to avoid circular dependency with tools
        from basic_memory.mcp.tools.utils import call_post

        cached_project = await _get_cached_active_project(context)
        if cached_project and _project_matches_identifier(cached_project, project):
            logger.debug(f"Using cached project from context: {cached_project.name}")
            return cached_project

        resolved_project = await resolve_project_parameter(project, context=context)
        if not resolved_project:
            project_names = await get_project_names(client, headers)
            raise ValueError(
                "No project specified. "
                "Either set 'default_project' in config, or use 'project' argument.\n"
                f"Available projects: {project_names}"
            )

        project = resolved_project

        if cached_project and _project_matches_identifier(cached_project, project):
            logger.debug(f"Using cached project from context: {cached_project.name}")
            return cached_project

        # Validate project exists by calling API
        logger.debug(f"Validating project: {project}")
        response = await call_post(
            client,
            "/v2/projects/resolve",
            json={"identifier": project},
            headers=headers,
        )
        resolved = ProjectResolveResponse.model_validate(response.json())
        active_project = ProjectItem(
            id=resolved.project_id,
            external_id=resolved.external_id,
            name=resolved.name,
            path=resolved.path,
            is_default=resolved.is_default,
        )

        # Cache in context if available
        await _set_cached_active_project(context, active_project)
        if context:
            logger.debug(f"Cached project in context: {project}")

        logger.debug(f"Validated project: {active_project.name}")
        return active_project


def _split_project_prefix(path: str) -> tuple[Optional[str], str]:
    """Split a possible project prefix from a memory URL path."""
    if "/" not in path:
        return None, path

    project_prefix, remainder = path.split("/", 1)
    if not project_prefix or not remainder:
        return None, path

    if "*" in project_prefix:
        return None, path

    return project_prefix, remainder


async def resolve_project_and_path(
    client: AsyncClient,
    identifier: str,
    project: Optional[str] = None,
    context: Optional[Context] = None,
    headers: HeaderTypes | None = None,
) -> tuple[ProjectItem, str, bool]:
    """Resolve project and normalized path for memory:// identifiers.

    Returns:
        Tuple of (active_project, normalized_path, is_memory_url)
    """
    is_memory_url = identifier.strip().startswith("memory://")
    config = ConfigManager().config
    include_project = config.permalinks_include_project if is_memory_url else None
    with telemetry.scope(
        "routing.resolve_memory_url",
        is_memory_url=is_memory_url,
        requested_project=project,
        include_project_prefix=include_project,
    ):
        if not is_memory_url:
            active_project = await get_active_project(client, project, context, headers)
            return active_project, identifier, False

        normalized_path = normalize_project_reference(memory_url_path(identifier))
        project_prefix, remainder = _split_project_prefix(normalized_path)
        include_project = config.permalinks_include_project
        # Trigger: memory URL begins with a potential project segment
        # Why: allow project-scoped memory URLs without requiring a separate project parameter
        # Outcome: attempt to resolve the prefix as a project and route to it
        if project_prefix:
            cached_project = await _get_cached_active_project(context)
            if cached_project and _project_matches_identifier(cached_project, project_prefix):
                resolved_project = await resolve_project_parameter(project_prefix, context=context)
                if resolved_project and generate_permalink(resolved_project) != generate_permalink(
                    project_prefix
                ):
                    raise ValueError(
                        f"Project is constrained to '{resolved_project}', cannot use '{project_prefix}'."
                    )

                resolved_path = (
                    f"{cached_project.permalink}/{remainder}" if include_project else remainder
                )
                return cached_project, resolved_path, True

            try:
                from basic_memory.mcp.tools.utils import call_post

                response = await call_post(
                    client,
                    "/v2/projects/resolve",
                    json={"identifier": project_prefix},
                    headers=headers,
                )
                resolved = ProjectResolveResponse.model_validate(response.json())
            except ToolError as exc:
                if "project not found" not in str(exc).lower():
                    raise
            else:
                resolved_project = await resolve_project_parameter(project_prefix, context=context)
                if resolved_project and generate_permalink(resolved_project) != generate_permalink(
                    project_prefix
                ):
                    raise ValueError(
                        f"Project is constrained to '{resolved_project}', cannot use '{project_prefix}'."
                    )

                active_project = ProjectItem(
                    id=resolved.project_id,
                    external_id=resolved.external_id,
                    name=resolved.name,
                    path=resolved.path,
                    is_default=resolved.is_default,
                )
                await _set_cached_active_project(context, active_project)

                resolved_path = (
                    f"{resolved.permalink}/{remainder}" if include_project else remainder
                )
                return active_project, resolved_path, True

        # Trigger: no resolvable project prefix in the memory URL
        # Why: preserve existing memory URL behavior within the active project
        # Outcome: use the active project and normalize the path for lookup
        active_project = await get_active_project(client, project, context, headers)
        resolved_path = normalized_path
        if include_project:
            # Trigger: project-prefixed permalinks are enabled and the path lacks a prefix
            # Why: ensure memory URL lookups align with canonical permalinks
            # Outcome: prefix the path with the active project's permalink
            project_prefix = active_project.permalink
            if resolved_path != project_prefix and not resolved_path.startswith(
                f"{project_prefix}/"
            ):
                resolved_path = f"{project_prefix}/{resolved_path}"
        return active_project, resolved_path, True


def add_project_metadata(result: str, project_name: str) -> str:
    """Add project context as metadata footer for assistant session tracking.

    Provides clear project context to help the assistant remember which
    project is being used throughout the conversation session.

    Args:
        result: The tool result string
        project_name: The project name that was used

    Returns:
        Result with project session tracking metadata
    """
    return f"{result}\n\n[Session: Using project '{project_name}']"


def detect_project_from_url_prefix(identifier: str, config: BasicMemoryConfig) -> Optional[str]:
    """Check if a memory URL's first path segment matches a known project in config.

    This enables automatic project routing from memory URLs like
    ``memory://specs/in-progress`` without requiring the caller to pass
    an explicit ``project`` parameter.

    Uses local config only — no network calls.

    Args:
        identifier: Raw identifier string (may or may not start with ``memory://``).
        config: Current BasicMemoryConfig with project entries.

    Returns:
        Matching project name from config, or None if no match.
    """
    path = memory_url_path(identifier) if identifier.strip().startswith("memory://") else identifier
    normalized = normalize_project_reference(path)
    prefix, _ = _split_project_prefix(normalized)
    if prefix is None:
        return None

    prefix_permalink = generate_permalink(prefix)
    for project_name in config.projects:
        if generate_permalink(project_name) == prefix_permalink:
            return project_name
    return None


@asynccontextmanager
async def get_project_client(
    project: Optional[str] = None,
    context: Optional[Context] = None,
) -> AsyncIterator[Tuple[AsyncClient, ProjectItem]]:
    """Resolve project, create a local ASGI client, and validate project.

    Solves the bootstrap problem: we need to know the project name to choose
    the right client, but we need the client to validate the project. This
    helper resolves the project from config first (no network), creates the
    client, then validates via API.

    Args:
        project: Optional explicit project parameter
        context: Optional FastMCP context for caching

    Yields:
        Tuple of (client, active_project)

    Raises:
        ValueError: If no project can be resolved
    """
    from basic_memory.mcp.async_client import get_client

    # Step 1: Resolve project name from config (no network call)
    resolved_project = await resolve_project_parameter(project, context=context)
    if not resolved_project:
        # Fall back to local client to discover projects and raise helpful error
        async with get_client() as client:
            project_names = await get_project_names(client)
            raise ValueError(
                "No project specified. "
                "Either set 'default_project' in config, or use 'project' argument.\n"
                f"Available projects: {project_names}"
            )

    # Step 2: Create local ASGI client and validate project
    with telemetry.scope(
        "routing.client_session",
        project_name=resolved_project,
        route_mode="local_asgi",
    ):
        async with get_client(project_name=resolved_project) as client:
            active_project = await get_active_project(client, resolved_project, context)
            yield client, active_project
