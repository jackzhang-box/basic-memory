"""Project info tool for Agent Brain MCP server."""

from typing import Optional

from loguru import logger
from fastmcp import Context

from agent_brain.mcp.async_client import get_client
from agent_brain.mcp.project_context import get_active_project
from agent_brain.mcp.server import mcp
from agent_brain.mcp.tools.utils import call_get
from agent_brain.schemas import ProjectInfoResponse


@mcp.resource(
    uri="memory://{project}/info",
    description="Get information and statistics about the current Agent Brain project.",
)
async def project_info(
    project: Optional[str] = None, context: Context | None = None
) -> ProjectInfoResponse:
    """Get comprehensive information about the current Agent Brain project.

    This tool provides detailed statistics and status information about your
    Agent Brain project, including:

    - Project configuration
    - Entity, observation, and relation counts
    - Graph metrics (most connected entities, isolated entities)
    - Recent activity and growth over time
    - System status (database, watch service, version)

    Use this tool to:
    - Verify your Agent Brain installation is working correctly
    - Get insights into your knowledge base structure
    - Monitor growth and activity over time
    - Identify potential issues like unresolved relations

    Args:
        project: Optional project name. If not provided, uses default_project
                from config or CLI constraint. If unknown, use
                list_memory_projects() to discover available projects.
        context: Optional FastMCP context for performance caching.

    Returns:
        Detailed project information and statistics

    Examples:
        # Get information about the current/default project
        info = await project_info()

        # Get information about a specific project
        info = await project_info(project="my-project")

        # Check entity counts
        print(f"Total entities: {info.statistics.total_entities}")

        # Check system status
        print(f"Agent Brain version: {info.system.version}")
    """
    logger.info("Getting project info")

    async with get_client() as client:
        project_config = await get_active_project(client, project, context)

        # Call the API endpoint
        response = await call_get(client, f"/v2/projects/{project_config.external_id}/info")

        # Convert response to ProjectInfoResponse
        return ProjectInfoResponse.model_validate(response.json())
