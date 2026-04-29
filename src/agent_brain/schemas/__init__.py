"""Knowledge graph schema exports.

This module exports all schema classes to simplify imports.
Rather than importing from individual schema files, you can
import everything from agent_brain.schemas.
"""

# Base types and models
from agent_brain.schemas.base import (
    Observation,
    NoteType,
    RelationType,
    Relation,
    Entity,
)

# Delete operation models
from agent_brain.schemas.delete import (
    DeleteEntitiesRequest,
)

# Request models
from agent_brain.schemas.request import (
    SearchNodesRequest,
    GetEntitiesRequest,
    CreateRelationsRequest,
)

# Response models
from agent_brain.schemas.response import (
    SQLAlchemyModel,
    ObservationResponse,
    RelationResponse,
    EntityResponse,
    EntityListResponse,
    SearchNodesResponse,
    DeleteEntitiesResponse,
)

from agent_brain.schemas.project_info import (
    ProjectStatistics,
    ActivityMetrics,
    SystemStatus,
    EmbeddingStatus,
    ProjectInfoResponse,
)

from agent_brain.schemas.directory import (
    DirectoryNode,
)

from agent_brain.schemas.sync_report import (
    SyncReportResponse,
)

# For convenient imports, export all models
__all__ = [
    # Base
    "Observation",
    "NoteType",
    "RelationType",
    "Relation",
    "Entity",
    # Requests
    "SearchNodesRequest",
    "GetEntitiesRequest",
    "CreateRelationsRequest",
    # Responses
    "SQLAlchemyModel",
    "ObservationResponse",
    "RelationResponse",
    "EntityResponse",
    "EntityListResponse",
    "SearchNodesResponse",
    "DeleteEntitiesResponse",
    # Delete Operations
    "DeleteEntitiesRequest",
    # Project Info
    "ProjectStatistics",
    "ActivityMetrics",
    "SystemStatus",
    "EmbeddingStatus",
    "ProjectInfoResponse",
    # Directory
    "DirectoryNode",
    # Sync
    "SyncReportResponse",
]
