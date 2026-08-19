"""TDS pydantic models. Fields ARE the spec (cursor §2 + Phase-1 backend addendum)."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

DType = Literal["keyword", "integer", "float", "boolean", "datetime", "keyword[]"]
LcdOp = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "nin"]
ExtOp = Literal["exists", "is_null", "contains_any", "contains_all", "like", "text_match"]
Op = Union[LcdOp, ExtOp]
ToolName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")]
FieldPath = Annotated[
    str,
    Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,2}$"),
]


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow")  # loader walks model_extra → VB0001 warnings


class BuiltinToolsSpec(_Base):
    semantic_search: bool = False
    get_by_id: bool = False
    count: bool = False
    list_collections: bool = False


class StaticFilter(_Base):
    path: FieldPath
    op: LcdOp = "eq"
    value: object


class OutputSpec(_Base):
    fields: list[FieldPath] | None = None
    limit_default: int = Field(default=10, ge=1, le=500)
    limit_max: int = Field(default=50, ge=1, le=500)
    include_score: bool = True


class BuiltinDefaults(_Base):
    collections: list[str] | None = None
    static_filters: list[StaticFilter] = Field(default_factory=list)
    output: OutputSpec | None = None
    descriptions: dict[str, str] | None = None


class _ConnBase(_Base):
    builtin_tools: BuiltinToolsSpec = BuiltinToolsSpec()
    builtin_defaults: BuiltinDefaults = BuiltinDefaults()


class QdrantConn(_ConnBase):
    backend: Literal["qdrant"]
    url: str
    api_key: str | None = None


class PgvectorConn(_ConnBase):
    backend: Literal["pgvector"]
    dsn: str
    table: str | None = None
    vector_column: str | None = "embedding"  # None or explicit `mode: table` ⇒ TABLE MODE
    mode: Literal["vector", "table"] | None = None
    id_column: str = "id"


class ChromaConn(_ConnBase):
    backend: Literal["chroma"]
    url: str
    auth_token: str | None = None


class PineconeConn(_ConnBase):
    backend: Literal["pinecone"]
    api_key: str
    host: str
    namespace: str | None = None


class WeaviateConn(_ConnBase):
    backend: Literal["weaviate"]
    url: str
    api_key: str | None = None
    tenant: str | None = None


class MilvusConn(_ConnBase):
    backend: Literal["milvus"]
    uri: str
    token: str | None = None
    user: str | None = None
    password: str | None = None
    database: str | None = None


ConnectionSpec = Annotated[
    QdrantConn | PgvectorConn | ChromaConn | PineconeConn | WeaviateConn | MilvusConn,
    Field(discriminator="backend"),
]


class Target(_Base):
    connection: str
    collection: str | object  # object = ParamRef — SYNTHETIC ONLY (VB2015 guards users)


class QuerySpec(_Base):
    param: str = "query"
    required: bool = False
    embedding: str | None = None
    mode: Literal["dense", "hybrid"] = "dense"
    alpha: float = Field(default=0.5, ge=0.0, le=1.0)


class ParamSpec(_Base):
    name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")]
    path: FieldPath | None = None
    dtype: DType | Literal["unknown"] = "keyword"
    op: Op | None = None
    required: bool = False
    description: str | None = None
    enum: list[str | int | float] | None = Field(default=None, max_length=100)
    default: object | None = None
    max: float | None = None


class FetchSpec(_Base):
    k_param: str = "limit"
    overfetch_factor: int = Field(default=10, ge=1, le=50)
    max_candidates: int = Field(default=2000, ge=10, le=20000)


class RetrieveBody(_Base):
    target: Target
    query: QuerySpec | None = None
    filter: dict[str, Any] | None = None
    fetch: FetchSpec = FetchSpec()


class RetrieveStep(_Base):
    retrieve: RetrieveBody


class PostFilterBody(_Base):
    expr: str


class PostFilterStep(_Base):
    post_filter: PostFilterBody


class PerGroup(_Base):
    sort_by: FieldPath
    desc: bool = True
    take: int | str = 3


class GroupByBody(_Base):
    keys: list[FieldPath] = Field(min_length=1, max_length=3)
    per_group: PerGroup | None = None


class GroupByStep(_Base):
    group_by: GroupByBody


class SortBody(_Base):
    by: FieldPath
    desc: bool = True


class SortStep(_Base):
    sort: SortBody


class ProjectBody(_Base):
    fields: list[FieldPath] = Field(min_length=1)


class ProjectStep(_Base):
    project: ProjectBody


PipelineStep = Union[RetrieveStep, PostFilterStep, GroupByStep, SortStep, ProjectStep]


class ToolSpec(_Base):
    name: ToolName
    description: Annotated[str, Field(min_length=20, max_length=1024)]
    kind: Literal["search", "lookup", "count", "scroll", "pipeline", "meta"] = "search"
    target: Target | None = None
    query: QuerySpec | None = None
    parameters: list[ParamSpec] = Field(default_factory=list, max_length=12)
    static_filters: list[StaticFilter] = Field(default_factory=list)
    filter_logic: Literal["and"] = "and"
    steps: list[PipelineStep] | None = None
    output: OutputSpec = OutputSpec()
    _synthetic: bool = PrivateAttr(default=False)

    @model_validator(mode="after")
    def _shape(self) -> ToolSpec:
        if self.kind == "pipeline":
            assert self.steps and isinstance(self.steps[0], RetrieveStep), (
                "pipeline: retrieve first"
            )
            assert self.target is None
        elif self.kind == "meta":
            assert not self.query and not self.parameters and not self.static_filters
        else:
            assert self.target is not None
            assert not self.steps
        return self


class Defaults(_Base):
    embedding: str = "fastembed/BAAI/bge-small-en-v1.5"


class AuthoringSpec(_Base):
    define_tool: bool = False


class TDSFile(_Base):
    tds_version: Literal["1"]
    connections: dict[str, ConnectionSpec]
    defaults: Defaults = Defaults()
    authoring: AuthoringSpec = AuthoringSpec()
    tools: list[ToolSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _refs(self) -> TDSFile:
        names = [t.name for t in self.tools]
        assert len(names) == len(set(names)), "duplicate tool names"
        for t in self.tools:
            targets = (
                [t.target]
                if t.target
                else [
                    s.retrieve.target
                    for s in (t.steps or [])
                    if isinstance(s, RetrieveStep)
                ]
            )
            for tg in targets:
                assert tg is not None
                assert tg.connection in self.connections, (
                    f"{t.name}: unknown connection '{tg.connection}'"
                )
        return self


def is_table_mode(conn: PgvectorConn) -> bool:
    """Table mode when ``mode=='table'`` or ``vector_column is None``."""
    return conn.mode == "table" or conn.vector_column is None


TDSFile.model_rebuild()
ToolSpec.model_rebuild()
