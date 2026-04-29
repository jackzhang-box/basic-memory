"""Schema system for Agent Brain.

Provides Picoschema-based validation for notes using observation/relation mapping.
Schemas are just notes with type: schema — no new data model, no migration.
"""

from agent_brain.schema.parser import (
    SchemaField,
    SchemaDefinition,
    parse_picoschema,
    parse_schema_note,
)
from agent_brain.schema.resolver import resolve_schema
from agent_brain.schema.validator import (
    FieldResult,
    ValidationResult,
    validate_note,
)
from agent_brain.schema.inference import (
    FieldFrequency,
    InferenceResult,
    ObservationData,
    RelationData,
    NoteData,
    infer_schema,
    analyze_observations,
    analyze_relations,
)
from agent_brain.schema.diff import (
    SchemaDrift,
    diff_schema,
)

__all__ = [
    # Parser
    "SchemaField",
    "SchemaDefinition",
    "parse_picoschema",
    "parse_schema_note",
    # Resolver
    "resolve_schema",
    # Validator
    "FieldResult",
    "ValidationResult",
    "validate_note",
    # Inference
    "FieldFrequency",
    "InferenceResult",
    "ObservationData",
    "RelationData",
    "NoteData",
    "infer_schema",
    "analyze_observations",
    "analyze_relations",
    # Diff
    "SchemaDrift",
    "diff_schema",
]
