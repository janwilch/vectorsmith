"""Static per-backend capability flags (validator gating)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Capabilities:
    ops: frozenset[str]
    nested_paths: bool
    arrays: bool
    exists_null: bool
    text_match_in_filter: bool
    filtered_ann_recall_safe: bool
    requires_explicit_index: bool
    introspection: Literal["typed", "names_only", "none"]
    server_side_embedding: bool
    scroll: bool
    count_with_filter: bool
    hybrid: bool


LCD = frozenset({"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin"})

QDRANT_CAPS = Capabilities(
    ops=LCD | frozenset({"exists", "is_null", "text_match"}),
    nested_paths=True,
    arrays=True,
    exists_null=True,
    text_match_in_filter=True,
    filtered_ann_recall_safe=True,
    requires_explicit_index=True,
    introspection="typed",
    server_side_embedding=False,
    scroll=True,
    count_with_filter=True,
    hybrid=True,
)

PGVECTOR_CAPS = Capabilities(
    ops=LCD | frozenset({"exists", "is_null", "like"}),
    nested_paths=True,
    arrays=True,
    exists_null=True,
    text_match_in_filter=False,
    filtered_ann_recall_safe=True,
    requires_explicit_index=True,
    introspection="typed",
    server_side_embedding=False,
    scroll=True,
    count_with_filter=True,
    hybrid=False,
)

CHROMA_CAPS = Capabilities(
    ops=LCD | frozenset({"like"}),
    nested_paths=False,
    arrays=False,
    exists_null=False,
    text_match_in_filter=False,
    filtered_ann_recall_safe=True,
    requires_explicit_index=False,
    introspection="none",
    server_side_embedding=False,
    scroll=True,
    count_with_filter=True,
    hybrid=False,
)

PINECONE_CAPS = Capabilities(
    ops=LCD,
    nested_paths=False,
    arrays=True,
    exists_null=False,
    text_match_in_filter=False,
    filtered_ann_recall_safe=True,
    requires_explicit_index=False,
    introspection="none",
    server_side_embedding=False,
    scroll=False,
    count_with_filter=True,
    hybrid=True,
)

WEAVIATE_CAPS = Capabilities(
    ops=LCD | frozenset({"like", "text_match", "exists", "is_null"}),
    nested_paths=True,
    arrays=True,
    exists_null=True,
    text_match_in_filter=True,
    filtered_ann_recall_safe=True,
    requires_explicit_index=False,
    introspection="typed",
    server_side_embedding=True,
    scroll=True,
    count_with_filter=True,
    hybrid=True,
)

MILVUS_CAPS = Capabilities(
    ops=LCD | frozenset({"like", "exists"}),
    nested_paths=True,
    arrays=True,
    exists_null=True,
    text_match_in_filter=False,
    filtered_ann_recall_safe=True,
    requires_explicit_index=True,
    introspection="typed",
    server_side_embedding=False,
    scroll=True,
    count_with_filter=True,
    hybrid=True,
)

CAPS_BY_BACKEND: dict[str, Capabilities] = {
    "qdrant": QDRANT_CAPS,
    "pgvector": PGVECTOR_CAPS,
    "chroma": CHROMA_CAPS,
    "pinecone": PINECONE_CAPS,
    "weaviate": WEAVIATE_CAPS,
    "milvus": MILVUS_CAPS,
}
