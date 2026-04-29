"""UI resources for MCP Apps integration."""

from agent_brain.mcp.server import mcp
from agent_brain.mcp.ui import load_html, load_variant_html

# FastMCP's MIME type validator currently accepts only type/subtype, so we
# use text/html here. MCP Apps hosts typically expect text/html;profile=mcp-app.
MIME_TYPE = "text/html"


@mcp.resource(
    uri="ui://agent-brain/search-results",
    name="Agent Brain Search Results",
    description="Search results UI for Agent Brain tools.",
    mime_type=MIME_TYPE,
)
def search_results_ui() -> str:
    return load_variant_html("search-results")


@mcp.resource(
    uri="ui://agent-brain/note-preview",
    name="Agent Brain Note Preview",
    description="Note preview UI for Agent Brain read_note tool.",
    mime_type=MIME_TYPE,
)
def note_preview_ui() -> str:
    return load_variant_html("note-preview")


# Variant-specific resource URIs for bakeoff comparisons.
@mcp.resource(
    uri="ui://agent-brain/search-results/vanilla",
    name="Agent Brain Search Results (Vanilla)",
    description="Vanilla HTML search results UI.",
    mime_type=MIME_TYPE,
)
def search_results_ui_vanilla() -> str:
    return load_html("search-results-vanilla.html")


@mcp.resource(
    uri="ui://agent-brain/search-results/tool-ui",
    name="Agent Brain Search Results (Tool UI)",
    description="Tool UI styled search results UI.",
    mime_type=MIME_TYPE,
)
def search_results_ui_tool_ui() -> str:
    return load_html("search-results-tool-ui.html")


@mcp.resource(
    uri="ui://agent-brain/search-results/mcp-ui",
    name="Agent Brain Search Results (MCP UI)",
    description="MCP UI styled search results UI.",
    mime_type=MIME_TYPE,
)
def search_results_ui_mcp_ui() -> str:
    return load_html("search-results-mcp-ui.html")


@mcp.resource(
    uri="ui://agent-brain/note-preview/vanilla",
    name="Agent Brain Note Preview (Vanilla)",
    description="Vanilla HTML note preview UI.",
    mime_type=MIME_TYPE,
)
def note_preview_ui_vanilla() -> str:
    return load_html("note-preview-vanilla.html")


@mcp.resource(
    uri="ui://agent-brain/note-preview/tool-ui",
    name="Agent Brain Note Preview (Tool UI)",
    description="Tool UI styled note preview UI.",
    mime_type=MIME_TYPE,
)
def note_preview_ui_tool_ui() -> str:
    return load_html("note-preview-tool-ui.html")


@mcp.resource(
    uri="ui://agent-brain/note-preview/mcp-ui",
    name="Agent Brain Note Preview (MCP UI)",
    description="MCP UI styled note preview UI.",
    mime_type=MIME_TYPE,
)
def note_preview_ui_mcp_ui() -> str:
    return load_html("note-preview-mcp-ui.html")
