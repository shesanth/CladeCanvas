from pydantic import BaseModel, ConfigDict
from typing import Optional, List

class NodeMetadata(BaseModel):
    node_id: str
    ott_id: Optional[int] = None
    common_name: Optional[str]
    description: Optional[str]
    full_description: Optional[str]
    image_url: Optional[str]
    wiki_page_url: Optional[str]
    rank: Optional[str] = None
    enriched_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

class SearchResult(BaseModel):
    node_id: str
    ott_id: Optional[int] = None
    common_name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    wiki_page_url: Optional[str] = None
    enriched_score: Optional[float] = None
    match_field: str
    match_snippet: str

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
