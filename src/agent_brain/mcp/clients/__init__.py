"""Typed internal API clients for MCP tools.

These clients encapsulate API paths, error handling, and response validation.
MCP tools become thin adapters that call these clients and format results.

Usage:
    from agent_brain.mcp.clients import KnowledgeClient, SearchClient

    async with get_client() as http_client:
        knowledge = KnowledgeClient(http_client, project_id)
        entity = await knowledge.create_entity(entity_data)
"""

from agent_brain.mcp.clients.knowledge import KnowledgeClient
from agent_brain.mcp.clients.search import SearchClient
from agent_brain.mcp.clients.memory import MemoryClient
from agent_brain.mcp.clients.directory import DirectoryClient
from agent_brain.mcp.clients.resource import ResourceClient
from agent_brain.mcp.clients.project import ProjectClient
from agent_brain.mcp.clients.schema import SchemaClient

__all__ = [
    "KnowledgeClient",
    "SearchClient",
    "MemoryClient",
    "DirectoryClient",
    "ResourceClient",
    "ProjectClient",
    "SchemaClient",
]
