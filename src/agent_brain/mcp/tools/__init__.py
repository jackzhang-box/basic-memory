"""MCP tools for Agent Brain.

This package provides the complete set of tools for interacting with
Agent Brain through the MCP protocol. Importing this module registers
all tools with the MCP server.
"""

# Import tools to register them with MCP
from agent_brain.mcp.tools.delete_note import delete_note
from agent_brain.mcp.tools.read_content import read_content
from agent_brain.mcp.tools.build_context import build_context
from agent_brain.mcp.tools.recent_activity import recent_activity
from agent_brain.mcp.tools.read_note import read_note

# TODO: re-enable once MCP client rendering is working
# from agent_brain.mcp.tools.ui_sdk import read_note_ui, search_notes_ui
from agent_brain.mcp.tools.view_note import view_note
from agent_brain.mcp.tools.write_note import write_note
from agent_brain.mcp.tools.release_notes import release_notes
from agent_brain.mcp.tools.search import search_notes
from agent_brain.mcp.tools.canvas import canvas
from agent_brain.mcp.tools.list_directory import list_directory
from agent_brain.mcp.tools.edit_note import edit_note
from agent_brain.mcp.tools.move_note import move_note
from agent_brain.mcp.tools.project_management import (
    list_memory_projects,
    create_memory_project,
    delete_project,
)

# ChatGPT-compatible tools
from agent_brain.mcp.tools.chatgpt_tools import search, fetch

# Schema tools
from agent_brain.mcp.tools.schema import schema_validate, schema_infer, schema_diff

__all__ = [
    "build_context",
    "canvas",
    "create_memory_project",
    "delete_note",
    "delete_project",
    "edit_note",
    "fetch",
    "list_directory",
    "list_memory_projects",
    "move_note",
    "read_content",
    "read_note",
    "release_notes",
    # "read_note_ui",
    "recent_activity",
    "schema_diff",
    "schema_infer",
    "schema_validate",
    "search",
    "search_notes",
    # "search_notes_ui",
    "view_note",
    "write_note",
]
