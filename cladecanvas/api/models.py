from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional, List, Dict, Literal


class FieldSource(BaseModel):
    source_label: Optional[str] = None
    source_url: Optional[str] = None
    fallback: bool = False

class NodeMetadata(BaseModel):
    node_id: str
    ott_id: Optional[int] = None
    wikidata_q: Optional[str] = None
    common_name: Optional[str]
    description: Optional[str]
    full_description: Optional[str]
    image_url: Optional[str]
    image_thumb: Optional[str] = None
    wiki_page_url: Optional[str]
    rank: Optional[str] = None
    last_updated: Optional[datetime] = None
    enriched_score: Optional[float] = None
    source_label: Optional[str] = None
    source_url: Optional[str] = None
    source_match_method: Optional[str] = None
    enriched_at: Optional[datetime] = None
    provenance_confidence: Optional[float] = None
    field_sources: Dict[str, FieldSource] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)

class SearchResult(BaseModel):
    node_id: str
    ott_id: Optional[int] = None
    common_name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    wiki_page_url: Optional[str] = None
    enriched_score: Optional[float] = None
    source_label: Optional[str] = None
    enriched_at: Optional[datetime] = None
    provenance_confidence: Optional[float] = None
    match_field: str
    match_snippet: str
    match_type: str
    score: float
    score_breakdown: dict[str, Any]

class TreeNode(BaseModel):
    node_id: str
    ott_id: Optional[int] = None
    name: str
    parent_node_id: Optional[str] = None
    child_count: Optional[int]
    has_metadata: Optional[bool]
    num_tips: Optional[int] = None
    display_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class LineageResponse(BaseModel):
    lineage: List[TreeNode]

class SubtreeResponse(BaseModel):
    nodes: List[TreeNode]

class ContextGraphNode(TreeNode):
    kind: Literal["lineage", "sibling", "child"]
    depth: int
    is_focus: bool = False

class ContextGraphEdge(BaseModel):
    source: str
    target: str
    kind: Literal["lineage", "sibling", "child"]

class ContextGraphResponse(BaseModel):
    focus_node_id: str
    lineage: List[TreeNode]
    nodes: List[ContextGraphNode]
    edges: List[ContextGraphEdge]
    omitted_by_parent: dict[str, int]
